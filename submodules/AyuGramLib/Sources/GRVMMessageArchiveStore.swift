import Foundation
import TelegramCore
import sqlcipher

private let grvmSQLiteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private struct GRVMStoredMediaKey: Hashable {
    let accountId: Int64
    let resourceId: String
}

public enum GRVMArchiveError: Error {
    case openDatabase(String)
    case sqlite(String)
    case unsupportedSchema(Int32)
}

public final class GRVMMessageArchiveStore {
    private static let sqliteVariableBatchSize = 500

    static let schemaV2 = """
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS archived_messages (
        account_id INTEGER NOT NULL,
        peer_id INTEGER NOT NULL,
        message_namespace INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        thread_id INTEGER NOT NULL DEFAULT 0,
        sender_id INTEGER NOT NULL DEFAULT 0,
        message_timestamp INTEGER NOT NULL,
        deleted_at INTEGER NOT NULL,
        deletion_source INTEGER NOT NULL DEFAULT 0,
        text TEXT NOT NULL DEFAULT '',
        entities BLOB NOT NULL DEFAULT X'',
        media_summary TEXT NOT NULL DEFAULT '',
        peer_title TEXT NOT NULL DEFAULT '',
        sender_name TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (account_id, peer_id, message_namespace, message_id, thread_id)
    );
    CREATE INDEX IF NOT EXISTS archived_messages_dialog
    ON archived_messages(account_id, peer_id, thread_id, deleted_at DESC);

    CREATE TABLE IF NOT EXISTS edit_revisions (
        row_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        peer_id INTEGER NOT NULL,
        message_namespace INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        thread_id INTEGER NOT NULL DEFAULT 0,
        version INTEGER NOT NULL,
        fingerprint TEXT NOT NULL,
        saved_at INTEGER NOT NULL,
        text TEXT NOT NULL DEFAULT '',
        entities BLOB NOT NULL DEFAULT X'',
        media_summary TEXT NOT NULL DEFAULT '',
        resource_ids BLOB NOT NULL DEFAULT X'',
        editable_content BLOB NOT NULL DEFAULT X'',
        UNIQUE(account_id, peer_id, message_namespace, message_id, thread_id, version),
        UNIQUE(account_id, peer_id, message_namespace, message_id, thread_id, fingerprint)
    );
    CREATE INDEX IF NOT EXISTS edit_revisions_message
    ON edit_revisions(account_id, peer_id, message_namespace, message_id, thread_id, version);

    CREATE TABLE IF NOT EXISTS archived_media_blobs (
        account_id INTEGER NOT NULL,
        resource_id TEXT NOT NULL,
        relative_path TEXT NOT NULL,
        byte_count INTEGER NOT NULL DEFAULT 0,
        kind TEXT NOT NULL DEFAULT '',
        copy_state INTEGER NOT NULL DEFAULT 0,
        generation INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (account_id, resource_id)
    );

    CREATE TABLE IF NOT EXISTS archived_message_media (
        account_id INTEGER NOT NULL,
        peer_id INTEGER NOT NULL,
        message_namespace INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        thread_id INTEGER NOT NULL DEFAULT 0,
        revision_id INTEGER NOT NULL DEFAULT 0,
        resource_id TEXT NOT NULL,
        PRIMARY KEY (account_id, peer_id, message_namespace, message_id, thread_id, revision_id, resource_id),
        FOREIGN KEY (account_id, resource_id)
          REFERENCES archived_media_blobs(account_id, resource_id) ON DELETE CASCADE
    );
    """

    static let cleanupSchemaV3 = """
    CREATE TABLE IF NOT EXISTS cleanup_jobs (
        job_id TEXT PRIMARY KEY,
        account_id INTEGER NOT NULL,
        scope_peer_id INTEGER NOT NULL DEFAULT 0,
        scope_thread_id INTEGER NOT NULL DEFAULT 0,
        phase INTEGER NOT NULL,
        created_at INTEGER NOT NULL,
        message_keys BLOB NOT NULL,
        media_records BLOB NOT NULL,
        UNIQUE(account_id, scope_peer_id, scope_thread_id)
    );
    CREATE INDEX IF NOT EXISTS cleanup_jobs_account
    ON cleanup_jobs(account_id, created_at);
    """

    static let lifecycleSchemaV4Migration = """
    ALTER TABLE archived_messages
    ADD COLUMN deletion_source INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE edit_revisions
    ADD COLUMN editable_content BLOB NOT NULL DEFAULT X'';
    ALTER TABLE archived_media_blobs
    ADD COLUMN generation INTEGER NOT NULL DEFAULT 0;
    """

    static let mediaAdmissionSQL = """
    INSERT INTO archived_media_blobs (
        account_id, resource_id, relative_path, byte_count, kind, copy_state, generation
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(account_id, resource_id) DO UPDATE SET
        relative_path = excluded.relative_path,
        byte_count = excluded.byte_count,
        kind = excluded.kind,
        copy_state = excluded.copy_state,
        generation = excluded.generation
    """

    static let mediaTerminalUpdateSQL = """
    UPDATE archived_media_blobs
    SET relative_path = ?, byte_count = ?, kind = ?, copy_state = ?
    WHERE account_id = ? AND resource_id = ? AND generation = ?
    """

    static let mediaCleanupClaimSQL = """
    UPDATE archived_media_blobs
    SET byte_count = 0, copy_state = ?, generation = generation + 1
    WHERE account_id = ? AND resource_id = ? AND relative_path = ? AND generation = ?
    """

    static let migrateDeletedV1 = """
    INSERT OR IGNORE INTO archived_messages (
        account_id, peer_id, message_namespace, message_id, thread_id,
        sender_id, message_timestamp, deleted_at, text, entities,
        media_summary, peer_title, sender_name
    )
    SELECT ?1, peer_id, 0, message_id, 0,
           sender_id, date, entity_create_date, text, X'',
           media_description, peer_title, sender_name
    FROM deleted_messages_legacy_v1
    """

    static let migrateEditedV1 = """
    INSERT OR IGNORE INTO edit_revisions (
        account_id, peer_id, message_namespace, message_id, thread_id,
        version, fingerprint, saved_at, text, entities, media_summary, resource_ids
    )
    SELECT ?1, peer_id, 0, message_id, 0,
           version, printf('legacy:%lld', id), edit_date, text, X'',
           media_description, CAST(media_resources AS BLOB)
    FROM edited_messages_legacy_v1
    """

    static let migrateDeletedMediaBlobsV1 = """
    WITH RECURSIVE split(resource_id, rest) AS (
        SELECT '', media_resources || ',' FROM deleted_messages_legacy_v1
        UNION ALL
        SELECT trim(substr(rest, 1, instr(rest, ',') - 1)),
               substr(rest, instr(rest, ',') + 1)
        FROM split WHERE rest <> ''
    )
    INSERT OR IGNORE INTO archived_media_blobs (
        account_id, resource_id, relative_path, byte_count, kind, copy_state
    )
    SELECT ?1, resource_id, '', 0, 'legacy', 0
    FROM split WHERE resource_id <> ''
    """

    static let migrateDeletedMediaMappingsV1 = """
    WITH RECURSIVE split(peer_id, message_id, resource_id, rest) AS (
        SELECT peer_id, message_id, '', media_resources || ','
        FROM deleted_messages_legacy_v1
        UNION ALL
        SELECT peer_id, message_id,
               trim(substr(rest, 1, instr(rest, ',') - 1)),
               substr(rest, instr(rest, ',') + 1)
        FROM split WHERE rest <> ''
    )
    INSERT OR IGNORE INTO archived_message_media (
        account_id, peer_id, message_namespace, message_id, thread_id, revision_id, resource_id
    )
    SELECT ?1, peer_id, 0, message_id, 0, 0, resource_id
    FROM split WHERE resource_id <> ''
    """

    static let migrateEditedMediaBlobsV1 = """
    WITH RECURSIVE split(resource_id, rest) AS (
        SELECT '', media_resources || ',' FROM edited_messages_legacy_v1
        UNION ALL
        SELECT trim(substr(rest, 1, instr(rest, ',') - 1)),
               substr(rest, instr(rest, ',') + 1)
        FROM split WHERE rest <> ''
    )
    INSERT OR IGNORE INTO archived_media_blobs (
        account_id, resource_id, relative_path, byte_count, kind, copy_state
    )
    SELECT ?1, resource_id, '', 0, 'legacy', 0
    FROM split WHERE resource_id <> ''
    """

    static let migrateEditedMediaMappingsV1 = """
    WITH RECURSIVE split(peer_id, message_id, revision_id, resource_id, rest) AS (
        SELECT legacy.peer_id, legacy.message_id, revision.row_id, '', legacy.media_resources || ','
        FROM edited_messages_legacy_v1 AS legacy
        JOIN edit_revisions AS revision
          ON revision.account_id = ?1
         AND revision.peer_id = legacy.peer_id
         AND revision.message_namespace = 0
         AND revision.message_id = legacy.message_id
         AND revision.thread_id = 0
         AND revision.fingerprint = printf('legacy:%lld', legacy.id)
        UNION ALL
        SELECT peer_id, message_id, revision_id,
               trim(substr(rest, 1, instr(rest, ',') - 1)),
               substr(rest, instr(rest, ',') + 1)
        FROM split WHERE rest <> ''
    )
    INSERT OR IGNORE INTO archived_message_media (
        account_id, peer_id, message_namespace, message_id, thread_id, revision_id, resource_id
    )
    SELECT ?1, peer_id, 0, message_id, 0, revision_id, resource_id
    FROM split WHERE resource_id <> ''
    """

    private enum SQLValue {
        case int32(Int32)
        case int64(Int64)
        case text(String)
        case data(Data)
    }

    private let queue = DispatchQueue(label: "com.grvmgram.messageArchiveStore", qos: .userInitiated)
    private let jsonEncoder = JSONEncoder()
    private let jsonDecoder = JSONDecoder()
    private var database: OpaquePointer?
    private var openError: GRVMArchiveError?

    public init(databaseURL: URL) {
        var database: OpaquePointer?
        if sqlite3_open(databaseURL.path, &database) == SQLITE_OK, let database {
            self.database = database
            _ = sqlite3_exec(database, "PRAGMA journal_mode = WAL", nil, nil, nil)
            _ = sqlite3_exec(database, "PRAGMA synchronous = NORMAL", nil, nil, nil)
            _ = sqlite3_exec(database, "PRAGMA foreign_keys = ON", nil, nil, nil)
        } else {
            let message: String
            if let database, let error = sqlite3_errmsg(database) {
                message = String(cString: error)
            } else {
                message = "unknown error"
            }
            self.openError = .openDatabase(message)
            if let database {
                sqlite3_close(database)
            }
        }
    }

    deinit {
        if let database = self.database {
            sqlite3_close(database)
        }
    }

    public func migrate(activeAccountRecordIds: [Int64]) throws {
        try self.perform { database in
            try self.transaction(database) {
                let version = try self.userVersion(database)
                let hasDeleted = try self.tableExists(database, name: "deleted_messages")
                let hasEdited = try self.tableExists(database, name: "edited_messages")
                let hasLegacyTables = hasDeleted || hasEdited

                switch version {
                case 0:
                    if hasDeleted {
                        try self.execute(database, sql: "ALTER TABLE deleted_messages RENAME TO deleted_messages_legacy_v1")
                    }
                    if hasEdited {
                        try self.execute(database, sql: "ALTER TABLE edited_messages RENAME TO edited_messages_legacy_v1")
                    }
                    try self.execute(database, sql: Self.schemaV2)
                    try self.execute(database, sql: Self.cleanupSchemaV3)

                    let accountIds = Array(Set(activeAccountRecordIds))
                    if hasLegacyTables && activeAccountRecordIds.count == 1 && accountIds.count == 1, let accountId = accountIds.first {
                        if hasDeleted {
                            try self.executePrepared(database, sql: Self.migrateDeletedV1, values: [.int64(accountId)])
                            try self.executePrepared(database, sql: Self.migrateDeletedMediaBlobsV1, values: [.int64(accountId)])
                            try self.executePrepared(database, sql: Self.migrateDeletedMediaMappingsV1, values: [.int64(accountId)])
                        }
                        if hasEdited {
                            try self.executePrepared(database, sql: Self.migrateEditedV1, values: [.int64(accountId)])
                            try self.executePrepared(database, sql: Self.migrateEditedMediaBlobsV1, values: [.int64(accountId)])
                            try self.executePrepared(database, sql: Self.migrateEditedMediaMappingsV1, values: [.int64(accountId)])
                        }
                    }
                    try self.execute(database, sql: "PRAGMA user_version = 4")
                case 2:
                    try self.execute(database, sql: Self.schemaV2)
                    try self.execute(database, sql: Self.cleanupSchemaV3)
                    try self.execute(database, sql: Self.lifecycleSchemaV4Migration)
                    try self.execute(database, sql: "PRAGMA user_version = 4")
                case 3:
                    try self.execute(database, sql: Self.schemaV2)
                    try self.execute(database, sql: Self.cleanupSchemaV3)
                    try self.execute(database, sql: Self.lifecycleSchemaV4Migration)
                    try self.execute(database, sql: "PRAGMA user_version = 4")
                case 4:
                    try self.execute(database, sql: Self.schemaV2)
                    try self.execute(database, sql: Self.cleanupSchemaV3)
                default:
                    throw GRVMArchiveError.unsupportedSchema(version)
                }
            }
        }
    }

    public func saveDeleted(
        _ messages: [GRVMArchivedMessage],
        media: [GRVMMessageKey: [GRVMArchivedMedia]]
    ) throws -> [GRVMMessageKey: [GRVMArchivedMedia]] {
        return try self.perform { database in
            try self.transaction(database) { () -> [GRVMMessageKey: [GRVMArchivedMedia]] in
                var admittedByResource: [GRVMStoredMediaKey: GRVMArchivedMedia] = [:]
                var admittedByMessage: [GRVMMessageKey: [GRVMArchivedMedia]] = [:]
                for message in messages {
                    try self.executePrepared(
                        database,
                        sql: """
                        INSERT INTO archived_messages (
                            account_id, peer_id, message_namespace, message_id, thread_id,
                            sender_id, message_timestamp, deleted_at, deletion_source, text, entities,
                            media_summary, peer_title, sender_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(account_id, peer_id, message_namespace, message_id, thread_id)
                        DO UPDATE SET sender_id = excluded.sender_id,
                                      message_timestamp = excluded.message_timestamp,
                                      deleted_at = excluded.deleted_at,
                                      deletion_source = excluded.deletion_source,
                                      text = excluded.text,
                                      entities = excluded.entities,
                                      media_summary = excluded.media_summary,
                                      peer_title = excluded.peer_title,
                                      sender_name = excluded.sender_name
                        """,
                        values: self.messageValues(message)
                    )
                    for record in media[message.key] ?? [] {
                        let mediaKey = GRVMStoredMediaKey(accountId: record.accountId, resourceId: record.resourceId)
                        let admitted: GRVMArchivedMedia
                        if let current = admittedByResource[mediaKey] {
                            admitted = current
                        } else {
                            admitted = try self.admitMedia(database, record: record)
                            admittedByResource[mediaKey] = admitted
                        }
                        admittedByMessage[message.key, default: []].append(admitted)
                        try self.insertMapping(database, key: message.key, revisionId: 0, resourceId: admitted.resourceId)
                    }
                }
                return admittedByMessage
            }
        }
    }

    public func saveRevision(
        _ draft: GRVMEditRevisionDraft,
        media: [GRVMArchivedMedia]
    ) throws -> (revision: GRVMEditRevision, media: [GRVMArchivedMedia]) {
        return try self.perform { database in
            try self.transaction(database) {
                var admittedByResource: [GRVMStoredMediaKey: GRVMArchivedMedia] = [:]
                var admittedMedia: [GRVMArchivedMedia] = []
                for record in media {
                    let mediaKey = GRVMStoredMediaKey(accountId: record.accountId, resourceId: record.resourceId)
                    let admitted: GRVMArchivedMedia
                    if let current = admittedByResource[mediaKey] {
                        admitted = current
                    } else {
                        admitted = try self.admitMedia(database, record: record)
                        admittedByResource[mediaKey] = admitted
                    }
                    admittedMedia.append(admitted)
                }
                if let existing = try self.revision(database, key: draft.key, fingerprint: draft.fingerprint) {
                    for record in admittedMedia {
                        try self.insertMapping(database, key: draft.key, revisionId: existing.rowId, resourceId: record.resourceId)
                    }
                    return (existing, admittedMedia)
                }

                let version = try self.nextRevisionVersion(database, key: draft.key)
                try self.executePrepared(
                    database,
                    sql: """
                    INSERT INTO edit_revisions (
                        account_id, peer_id, message_namespace, message_id, thread_id,
                        version, fingerprint, saved_at, text, entities, media_summary, resource_ids,
                        editable_content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values: self.keyValues(draft.key) + [
                        .int32(version),
                        .text(draft.fingerprint),
                        .int32(draft.savedAt),
                        .text(draft.text),
                        .data(draft.entitiesData),
                        .text(draft.mediaSummary),
                        .data(self.encodeResourceIds(draft.resourceIds)),
                        .data(try self.encodeEditableContent(draft.editableContent))
                    ]
                )
                let rowId = sqlite3_last_insert_rowid(database)
                for record in admittedMedia {
                    try self.insertMapping(database, key: draft.key, revisionId: rowId, resourceId: record.resourceId)
                }
                return (GRVMEditRevision(
                    rowId: rowId,
                    key: draft.key,
                    version: version,
                    fingerprint: draft.fingerprint,
                    savedAt: draft.savedAt,
                    editableContent: draft.editableContent,
                    text: draft.text,
                    entitiesData: draft.entitiesData,
                    mediaSummary: draft.mediaSummary,
                    resourceIds: draft.resourceIds
                ), admittedMedia)
            }
        }
    }

    public func updateMedia(_ record: GRVMArchivedMedia) throws {
        try self.perform { database in
            try self.executePrepared(
                database,
                sql: Self.mediaTerminalUpdateSQL,
                values: [
                    .text(record.relativePath),
                    .int64(record.byteCount),
                    .text(record.kind),
                    .int32(record.copyState.rawValue),
                    .int64(record.accountId),
                    .text(record.resourceId),
                    .int64(record.generation)
                ]
            )
        }
    }

    public func deletedMessages(_ query: GRVMArchiveQuery) throws -> [GRVMArchivedMessage] {
        return try self.perform { database in
            var clauses = ["account_id = ?"]
            var values: [SQLValue] = [.int64(query.accountId)]
            if let peerId = query.peerId {
                clauses.append("peer_id = ?")
                values.append(.int64(peerId))
            }
            if let threadId = query.threadId {
                clauses.append("thread_id = ?")
                values.append(.int64(threadId))
            }
            values.append(.int32(max(0, query.limit)))
            return try self.queryMessages(
                database,
                sql: """
                SELECT account_id, peer_id, message_namespace, message_id, thread_id,
                       sender_id, message_timestamp, deleted_at, deletion_source, text, entities,
                       media_summary, peer_title, sender_name
                FROM archived_messages
                WHERE \(clauses.joined(separator: " AND "))
                ORDER BY deleted_at DESC
                LIMIT ?
                """,
                values: values
            )
        }
    }

    public func deletedMessages(keys: [GRVMMessageKey]) throws -> [GRVMArchivedMessage] {
        guard !keys.isEmpty else {
            return []
        }
        return try self.perform { database in
            let clause = keys.map { _ in
                "(account_id = ? AND peer_id = ? AND message_namespace = ? AND message_id = ? AND thread_id = ?)"
            }.joined(separator: " OR ")
            return try self.queryMessages(
                database,
                sql: """
                SELECT account_id, peer_id, message_namespace, message_id, thread_id,
                       sender_id, message_timestamp, deleted_at, deletion_source, text, entities,
                       media_summary, peer_title, sender_name
                FROM archived_messages WHERE \(clause)
                """,
                values: keys.flatMap { self.keyValues($0) }
            )
        }
    }

    public func editHistory(_ key: GRVMMessageKey) throws -> [GRVMEditRevision] {
        return try self.perform { database in
            try self.queryRevisions(
                database,
                sql: """
                SELECT row_id, account_id, peer_id, message_namespace, message_id, thread_id,
                       version, fingerprint, saved_at, text, entities, media_summary, resource_ids,
                       editable_content
                FROM edit_revisions
                WHERE account_id = ? AND peer_id = ? AND message_namespace = ? AND message_id = ? AND thread_id = ?
                ORDER BY version ASC
                """,
                values: self.keyValues(key)
            )
        }
    }

    public func deletedKeys(accountId: Int64) throws -> Set<GRVMMessageKey> {
        return try self.perform { database in
            try self.queryKeys(
                database,
                sql: """
                SELECT account_id, peer_id, message_namespace, message_id, thread_id
                FROM archived_messages WHERE account_id = ?
                """,
                values: [.int64(accountId)]
            )
        }
    }

    public func revisedKeys(accountId: Int64) throws -> Set<GRVMMessageKey> {
        return try self.perform { database in
            try self.queryKeys(
                database,
                sql: """
                SELECT DISTINCT account_id, peer_id, message_namespace, message_id, thread_id
                FROM edit_revisions WHERE account_id = ?
                """,
                values: [.int64(accountId)]
            )
        }
    }

    public func archivedMedia(accountId: Int64, resourceIds: [String]) throws -> [GRVMArchivedMedia] {
        guard !resourceIds.isEmpty else {
            return []
        }
        var seenResourceIds = Set<String>()
        let uniqueResourceIds = resourceIds.filter { seenResourceIds.insert($0).inserted }
        return try self.perform { database in
            var result: [GRVMArchivedMedia] = []
            for start in stride(from: 0, to: uniqueResourceIds.count, by: Self.sqliteVariableBatchSize) {
                let end = min(start + Self.sqliteVariableBatchSize, uniqueResourceIds.count)
                let batch = Array(uniqueResourceIds[start ..< end])
                let placeholders = Array(repeating: "?", count: batch.count).joined(separator: ",")
                result.append(contentsOf: try self.queryMedia(
                    database,
                    sql: """
                    SELECT account_id, resource_id, relative_path, byte_count, kind, copy_state, generation
                    FROM archived_media_blobs
                    WHERE account_id = ? AND resource_id IN (\(placeholders))
                    """,
                    values: [.int64(accountId)] + batch.map { .text($0) }
                ))
            }
            return result
        }
    }

    public func archivedMedia(accountId: Int64) throws -> [GRVMArchivedMedia] {
        return try self.perform { database in
            try self.queryMedia(
                database,
                sql: """
                SELECT account_id, resource_id, relative_path, byte_count, kind, copy_state, generation
                FROM archived_media_blobs WHERE account_id = ?
                """,
                values: [.int64(accountId)]
            )
        }
    }

    public func deletedMessageKeys(
        accountId: Int64,
        peerId: Int64?,
        threadId: Int64?
    ) throws -> [GRVMMessageKey] {
        return try self.perform { database in
            var clauses = ["account_id = ?"]
            var values: [SQLValue] = [.int64(accountId)]
            if let peerId {
                clauses.append("peer_id = ?")
                values.append(.int64(peerId))
            }
            if let threadId {
                clauses.append("thread_id = ?")
                values.append(.int64(threadId))
            }
            let keys = try self.queryKeys(
                database,
                sql: """
                SELECT account_id, peer_id, message_namespace, message_id, thread_id
                FROM archived_messages WHERE \(clauses.joined(separator: " AND "))
                """,
                values: values
            )
            return Array(keys)
        }
    }

    private func cleanupMediaRecords(
        _ database: OpaquePointer,
        accountId: Int64,
        messageKeys: [GRVMMessageKey]
    ) throws -> [GRVMArchivedMedia] {
        guard messageKeys.allSatisfy({ $0.accountId == accountId }) else {
            throw GRVMArchiveError.sqlite("invalid cleanup job account")
        }
        var resourceIds = Set<String>()
        for key in messageKeys {
            for resourceId in try self.mappedResourceIds(database, key: key, revisionId: 0) {
                resourceIds.insert(resourceId)
            }
        }

        var mediaRecords: [GRVMArchivedMedia] = []
        for resourceId in resourceIds.sorted() {
            guard let record = try self.media(database, accountId: accountId, resourceId: resourceId) else {
                throw GRVMArchiveError.sqlite("targeted archived media is missing")
            }
            mediaRecords.append(record)
        }
        mediaRecords.sort {
            $0.accountId == $1.accountId
                ? $0.resourceId < $1.resourceId
                : $0.accountId < $1.accountId
        }
        return mediaRecords
    }

    private func revalidatedCleanupMediaRecords(
        _ database: OpaquePointer,
        job: GRVMCleanupJob
    ) throws -> [GRVMArchivedMedia] {
        guard job.messageKeys.allSatisfy({ $0.accountId == job.accountId }) else {
            throw GRVMArchiveError.sqlite("invalid cleanup job account")
        }
        var targetedReferencesByResourceId: [String: Int] = [:]
        for key in job.messageKeys {
            for resourceId in try self.mappedResourceIds(database, key: key, revisionId: 0) {
                targetedReferencesByResourceId[resourceId, default: 0] += 1
            }
        }

        var result: [GRVMArchivedMedia] = []
        for record in job.mediaRecords {
            guard let targetedReferences = targetedReferencesByResourceId[record.resourceId] else {
                continue
            }
            let references = try self.scalarInt64(
                database,
                sql: "SELECT COUNT(*) FROM archived_message_media WHERE account_id = ? AND resource_id = ?",
                values: [.int64(job.accountId), .text(record.resourceId)]
            )
            guard references == Int64(targetedReferences) else {
                continue
            }
            guard let current = try self.media(
                database,
                accountId: job.accountId,
                resourceId: record.resourceId
            ) else {
                throw GRVMArchiveError.sqlite("targeted archived media is missing")
            }
            guard current.generation == record.generation,
                  current.relativePath == record.relativePath else {
                continue
            }
            guard current.generation < Int64.max else {
                throw GRVMArchiveError.sqlite("archived media generation overflow")
            }
            try self.executePrepared(
                database,
                sql: Self.mediaCleanupClaimSQL,
                values: [
                    .int32(GRVMArchivedMedia.CopyState.unavailable.rawValue),
                    .int64(current.accountId),
                    .text(current.resourceId),
                    .text(current.relativePath),
                    .int64(current.generation)
                ]
            )
            guard sqlite3_changes(database) == 1 else {
                throw GRVMArchiveError.sqlite("archived media cleanup claim failed")
            }
            result.append(GRVMArchivedMedia(
                accountId: current.accountId,
                resourceId: current.resourceId,
                relativePath: current.relativePath,
                byteCount: 0,
                kind: current.kind,
                copyState: .unavailable,
                generation: current.generation + 1
            ))
        }
        result.sort {
            $0.accountId == $1.accountId
                ? $0.resourceId < $1.resourceId
                : $0.accountId < $1.accountId
        }
        return result
    }

    public func beginDeletedCleanup(
        accountId: Int64,
        peerId: Int64?,
        threadId: Int64?
    ) throws -> GRVMCleanupJob? {
        return try self.perform { database in
            try self.transaction(database) {
                let scopePeerId = peerId ?? 0
                let scopeThreadId = threadId ?? 0
                if let existing = try self.cleanupJob(
                    database,
                    sql: """
                    SELECT job_id, account_id, scope_peer_id, scope_thread_id,
                           phase, created_at, message_keys, media_records
                    FROM cleanup_jobs
                    WHERE account_id = ? AND scope_peer_id = ? AND scope_thread_id = ?
                    LIMIT 1
                    """,
                    values: [.int64(accountId), .int64(scopePeerId), .int64(scopeThreadId)]
                ) {
                    return existing
                }

                var clauses = ["account_id = ?"]
                var values: [SQLValue] = [.int64(accountId)]
                if let peerId {
                    clauses.append("peer_id = ?")
                    values.append(.int64(peerId))
                }
                if let threadId {
                    clauses.append("thread_id = ?")
                    values.append(.int64(threadId))
                }
                let messageKeys = try self.queryKeys(
                    database,
                    sql: """
                    SELECT account_id, peer_id, message_namespace, message_id, thread_id
                    FROM archived_messages WHERE \(clauses.joined(separator: " AND "))
                    """,
                    values: values
                ).sorted(by: self.messageKeyPrecedes)
                guard !messageKeys.isEmpty else {
                    return nil
                }
                let mediaRecords = try self.cleanupMediaRecords(
                    database,
                    accountId: accountId,
                    messageKeys: messageKeys
                )

                let job = GRVMCleanupJob(
                    id: UUID(),
                    accountId: accountId,
                    peerId: peerId,
                    threadId: threadId,
                    phase: .planned,
                    createdAt: Int32(Date().timeIntervalSince1970),
                    messageKeys: messageKeys,
                    mediaRecords: mediaRecords
                )
                try self.executePrepared(
                    database,
                    sql: """
                    INSERT INTO cleanup_jobs (
                        job_id, account_id, scope_peer_id, scope_thread_id,
                        phase, created_at, message_keys, media_records
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values: [
                        .text(job.id.uuidString),
                        .int64(job.accountId),
                        .int64(scopePeerId),
                        .int64(scopeThreadId),
                        .int32(job.phase.rawValue),
                        .int32(job.createdAt),
                        .data(try self.jsonEncoder.encode(job.messageKeys)),
                        .data(try self.jsonEncoder.encode(job.mediaRecords))
                    ]
                )
                return job
            }
        }
    }

    public func revalidateDeletedCleanup(id: UUID) throws -> GRVMCleanupJob {
        return try self.perform { database in
            try self.transaction(database) {
                guard let job = try self.cleanupJob(database, id: id) else {
                    throw GRVMArchiveError.sqlite("cleanup job not found")
                }
                guard job.phase == .planned else {
                    return job
                }
                let mediaRecords = try self.revalidatedCleanupMediaRecords(database, job: job)
                try self.executePrepared(
                    database,
                    sql: "UPDATE cleanup_jobs SET media_records = ? WHERE job_id = ? AND phase = ?",
                    values: [
                        .data(try self.jsonEncoder.encode(mediaRecords)),
                        .text(id.uuidString),
                        .int32(GRVMCleanupPhase.planned.rawValue)
                    ]
                )
                guard let refreshed = try self.cleanupJob(database, id: id) else {
                    throw GRVMArchiveError.sqlite("cleanup job not found")
                }
                return refreshed
            }
        }
    }

    public func pendingCleanupJobs(accountId: Int64) throws -> [GRVMCleanupJob] {
        return try self.perform { database in
            try self.queryCleanupJobs(
                database,
                sql: """
                SELECT job_id, account_id, scope_peer_id, scope_thread_id,
                       phase, created_at, message_keys, media_records
                FROM cleanup_jobs WHERE account_id = ?
                ORDER BY created_at ASC, job_id ASC
                """,
                values: [.int64(accountId)]
            )
        }
    }

    public func markCleanupFilesRemoved(id: UUID) throws -> GRVMCleanupJob {
        return try self.perform { database in
            try self.transaction(database) {
                try self.executePrepared(
                    database,
                    sql: "UPDATE cleanup_jobs SET phase = ? WHERE job_id = ? AND phase = ?",
                    values: [
                        .int32(GRVMCleanupPhase.filesRemoved.rawValue),
                        .text(id.uuidString),
                        .int32(GRVMCleanupPhase.planned.rawValue)
                    ]
                )
                guard let job = try self.cleanupJob(database, id: id) else {
                    throw GRVMArchiveError.sqlite("cleanup job not found")
                }
                return job
            }
        }
    }

    public func finalizeDeletedCleanup(id: UUID) throws -> [GRVMMessageKey] {
        return try self.perform { database in
            try self.transaction(database) {
                guard let job = try self.cleanupJob(database, id: id) else {
                    throw GRVMArchiveError.sqlite("cleanup job not found")
                }
                guard job.phase == .filesRemoved else {
                    throw GRVMArchiveError.sqlite("cleanup files have not been removed")
                }

                for key in job.messageKeys {
                    try self.executePrepared(
                        database,
                        sql: """
                        DELETE FROM archived_message_media
                        WHERE account_id = ? AND peer_id = ? AND message_namespace = ?
                          AND message_id = ? AND thread_id = ? AND revision_id = 0
                        """,
                        values: self.keyValues(key)
                    )
                    try self.executePrepared(
                        database,
                        sql: """
                        DELETE FROM archived_messages
                        WHERE account_id = ? AND peer_id = ? AND message_namespace = ?
                          AND message_id = ? AND thread_id = ?
                        """,
                        values: self.keyValues(key)
                    )
                }

                for record in job.mediaRecords {
                    let references = try self.scalarInt64(
                        database,
                        sql: "SELECT COUNT(*) FROM archived_message_media WHERE account_id = ? AND resource_id = ?",
                        values: [.int64(record.accountId), .text(record.resourceId)]
                    )
                    if references == 0 {
                        try self.executePrepared(
                            database,
                            sql: "DELETE FROM archived_media_blobs WHERE account_id = ? AND resource_id = ?",
                            values: [.int64(record.accountId), .text(record.resourceId)]
                        )
                    }
                }

                try self.executePrepared(
                    database,
                    sql: "DELETE FROM cleanup_jobs WHERE job_id = ?",
                    values: [.text(id.uuidString)]
                )
                return job.messageKeys
            }
        }
    }

    private func perform<T>(_ f: (OpaquePointer) throws -> T) throws -> T {
        return try self.queue.sync {
            if let openError = self.openError {
                throw openError
            }
            guard let database = self.database else {
                throw GRVMArchiveError.openDatabase("database is unavailable")
            }
            return try f(database)
        }
    }

    private func transaction<T>(_ database: OpaquePointer, _ f: () throws -> T) throws -> T {
        try self.execute(database, sql: "BEGIN IMMEDIATE")
        do {
            let result = try f()
            try self.execute(database, sql: "COMMIT")
            return result
        } catch {
            try? self.execute(database, sql: "ROLLBACK")
            throw error
        }
    }

    private func execute(_ database: OpaquePointer, sql: String) throws {
        guard sqlite3_exec(database, sql, nil, nil, nil) == SQLITE_OK else {
            throw self.sqliteError(database)
        }
    }

    private func executePrepared(_ database: OpaquePointer, sql: String, values: [SQLValue]) throws {
        try self.withStatement(database, sql: sql, values: values) { statement in
            guard sqlite3_step(statement) == SQLITE_DONE else {
                throw self.sqliteError(database)
            }
        }
    }

    private func withStatement<T>(
        _ database: OpaquePointer,
        sql: String,
        values: [SQLValue],
        _ f: (OpaquePointer) throws -> T
    ) throws -> T {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK, let statement else {
            throw self.sqliteError(database)
        }
        defer {
            sqlite3_finalize(statement)
        }
        for (offset, value) in values.enumerated() {
            let index = Int32(offset + 1)
            let result: Int32
            switch value {
            case let .int32(value):
                result = sqlite3_bind_int(statement, index, value)
            case let .int64(value):
                result = sqlite3_bind_int64(statement, index, value)
            case let .text(value):
                result = value.withCString { sqlite3_bind_text(statement, index, $0, -1, grvmSQLiteTransient) }
            case let .data(value):
                if value.isEmpty {
                    result = sqlite3_bind_zeroblob(statement, index, 0)
                } else {
                    result = value.withUnsafeBytes { bytes in
                        sqlite3_bind_blob(statement, index, bytes.baseAddress, Int32(value.count), grvmSQLiteTransient)
                    }
                }
            }
            guard result == SQLITE_OK else {
                throw self.sqliteError(database)
            }
        }
        return try f(statement)
    }

    private func userVersion(_ database: OpaquePointer) throws -> Int32 {
        return try self.withStatement(database, sql: "PRAGMA user_version", values: []) { statement in
            guard sqlite3_step(statement) == SQLITE_ROW else {
                throw self.sqliteError(database)
            }
            return sqlite3_column_int(statement, 0)
        }
    }

    private func tableExists(_ database: OpaquePointer, name: String) throws -> Bool {
        return try self.withStatement(
            database,
            sql: "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            values: [.text(name)]
        ) { statement in
            let result = sqlite3_step(statement)
            if result == SQLITE_ROW {
                return true
            } else if result == SQLITE_DONE {
                return false
            } else {
                throw self.sqliteError(database)
            }
        }
    }

    private func readRows(
        _ database: OpaquePointer,
        statement: OpaquePointer,
        _ f: () throws -> Void
    ) throws {
        while true {
            switch sqlite3_step(statement) {
            case SQLITE_ROW:
                try f()
            case SQLITE_DONE:
                return
            default:
                throw self.sqliteError(database)
            }
        }
    }

    private func nextRevisionVersion(_ database: OpaquePointer, key: GRVMMessageKey) throws -> Int32 {
        return Int32(try self.scalarInt64(
            database,
            sql: """
            SELECT COALESCE(MAX(version), -1) + 1 FROM edit_revisions
            WHERE account_id = ? AND peer_id = ? AND message_namespace = ?
              AND message_id = ? AND thread_id = ?
            """,
            values: self.keyValues(key)
        ))
    }

    private func scalarInt64(
        _ database: OpaquePointer,
        sql: String,
        values: [SQLValue]
    ) throws -> Int64 {
        return try self.withStatement(database, sql: sql, values: values) { statement in
            guard sqlite3_step(statement) == SQLITE_ROW else {
                throw self.sqliteError(database)
            }
            return sqlite3_column_int64(statement, 0)
        }
    }

    private func admitMedia(_ database: OpaquePointer, record: GRVMArchivedMedia) throws -> GRVMArchivedMedia {
        let previousGeneration = try self.media(
            database,
            accountId: record.accountId,
            resourceId: record.resourceId
        )?.generation ?? 0
        guard previousGeneration < Int64.max else {
            throw GRVMArchiveError.sqlite("archived media generation overflow")
        }
        let admitted = GRVMArchivedMedia(
            accountId: record.accountId,
            resourceId: record.resourceId,
            relativePath: record.relativePath,
            byteCount: 0,
            kind: record.kind,
            copyState: .copying,
            generation: previousGeneration + 1
        )
        try self.executePrepared(
            database,
            sql: Self.mediaAdmissionSQL,
            values: [
                .int64(admitted.accountId),
                .text(admitted.resourceId),
                .text(admitted.relativePath),
                .int64(admitted.byteCount),
                .text(admitted.kind),
                .int32(admitted.copyState.rawValue),
                .int64(admitted.generation)
            ]
        )
        return admitted
    }

    private func insertMapping(
        _ database: OpaquePointer,
        key: GRVMMessageKey,
        revisionId: Int64,
        resourceId: String
    ) throws {
        try self.executePrepared(
            database,
            sql: """
            INSERT OR IGNORE INTO archived_message_media (
                account_id, peer_id, message_namespace, message_id, thread_id, revision_id, resource_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            values: self.keyValues(key) + [.int64(revisionId), .text(resourceId)]
        )
    }

    private func messageValues(_ message: GRVMArchivedMessage) -> [SQLValue] {
        return self.keyValues(message.key) + [
            .int64(message.senderId),
            .int32(message.timestamp),
            .int32(message.deletedAt),
            .int32(message.deletionSource),
            .text(message.text),
            .data(message.entitiesData),
            .text(message.mediaSummary),
            .text(message.peerTitle),
            .text(message.senderName)
        ]
    }

    private func keyValues(_ key: GRVMMessageKey) -> [SQLValue] {
        return [
            .int64(key.accountId),
            .int64(key.peerId),
            .int32(key.namespace),
            .int32(key.messageId),
            .int64(key.threadId)
        ]
    }

    private func messageKeyPrecedes(_ lhs: GRVMMessageKey, _ rhs: GRVMMessageKey) -> Bool {
        if lhs.accountId != rhs.accountId {
            return lhs.accountId < rhs.accountId
        }
        if lhs.peerId != rhs.peerId {
            return lhs.peerId < rhs.peerId
        }
        if lhs.namespace != rhs.namespace {
            return lhs.namespace < rhs.namespace
        }
        if lhs.messageId != rhs.messageId {
            return lhs.messageId < rhs.messageId
        }
        return lhs.threadId < rhs.threadId
    }

    private func queryMessages(
        _ database: OpaquePointer,
        sql: String,
        values: [SQLValue]
    ) throws -> [GRVMArchivedMessage] {
        return try self.withStatement(database, sql: sql, values: values) { statement in
            var result: [GRVMArchivedMessage] = []
            try self.readRows(database, statement: statement) {
                let key = self.readKey(statement, offset: 0)
                result.append(GRVMArchivedMessage(
                    key: key,
                    senderId: sqlite3_column_int64(statement, 5),
                    timestamp: sqlite3_column_int(statement, 6),
                    deletedAt: sqlite3_column_int(statement, 7),
                    deletionSource: sqlite3_column_int(statement, 8),
                    text: self.columnText(statement, 9),
                    entitiesData: self.columnData(statement, 10),
                    mediaSummary: self.columnText(statement, 11),
                    resourceIds: try self.mappedResourceIds(database, key: key, revisionId: 0).sorted(),
                    peerTitle: self.columnText(statement, 12),
                    senderName: self.columnText(statement, 13)
                ))
            }
            return result
        }
    }

    private func queryRevisions(
        _ database: OpaquePointer,
        sql: String,
        values: [SQLValue]
    ) throws -> [GRVMEditRevision] {
        return try self.withStatement(database, sql: sql, values: values) { statement in
            var result: [GRVMEditRevision] = []
            try self.readRows(database, statement: statement) {
                result.append(self.readRevision(statement))
            }
            return result
        }
    }

    private func revision(
        _ database: OpaquePointer,
        key: GRVMMessageKey,
        fingerprint: String
    ) throws -> GRVMEditRevision? {
        return try self.withStatement(
            database,
            sql: """
            SELECT row_id, account_id, peer_id, message_namespace, message_id, thread_id,
                   version, fingerprint, saved_at, text, entities, media_summary, resource_ids,
                   editable_content
            FROM edit_revisions
            WHERE account_id = ? AND peer_id = ? AND message_namespace = ?
              AND message_id = ? AND thread_id = ? AND fingerprint = ?
            LIMIT 1
            """,
            values: self.keyValues(key) + [.text(fingerprint)]
        ) { statement in
            let result = sqlite3_step(statement)
            guard result == SQLITE_ROW else {
                if result != SQLITE_DONE {
                    throw self.sqliteError(database)
                }
                return nil
            }
            return self.readRevision(statement)
        }
    }

    private func readRevision(_ statement: OpaquePointer) -> GRVMEditRevision {
        let text = self.columnText(statement, 9)
        let entitiesData = self.columnData(statement, 10)
        return GRVMEditRevision(
            rowId: sqlite3_column_int64(statement, 0),
            key: self.readKey(statement, offset: 1),
            version: sqlite3_column_int(statement, 6),
            fingerprint: self.columnText(statement, 7),
            savedAt: sqlite3_column_int(statement, 8),
            editableContent: self.decodeEditableContent(
                self.columnData(statement, 13),
                text: text,
                entitiesData: entitiesData
            ),
            text: text,
            entitiesData: entitiesData,
            mediaSummary: self.columnText(statement, 11),
            resourceIds: self.decodeResourceIds(self.columnData(statement, 12))
        )
    }

    private func queryKeys(
        _ database: OpaquePointer,
        sql: String,
        values: [SQLValue]
    ) throws -> Set<GRVMMessageKey> {
        return try self.withStatement(database, sql: sql, values: values) { statement in
            var result: Set<GRVMMessageKey> = []
            try self.readRows(database, statement: statement) {
                result.insert(self.readKey(statement, offset: 0))
            }
            return result
        }
    }

    private func queryMedia(
        _ database: OpaquePointer,
        sql: String,
        values: [SQLValue]
    ) throws -> [GRVMArchivedMedia] {
        return try self.withStatement(database, sql: sql, values: values) { statement in
            var result: [GRVMArchivedMedia] = []
            try self.readRows(database, statement: statement) {
                result.append(try self.readMedia(statement))
            }
            return result
        }
    }

    private func cleanupJob(_ database: OpaquePointer, id: UUID) throws -> GRVMCleanupJob? {
        return try self.cleanupJob(
            database,
            sql: """
            SELECT job_id, account_id, scope_peer_id, scope_thread_id,
                   phase, created_at, message_keys, media_records
            FROM cleanup_jobs WHERE job_id = ?
            LIMIT 1
            """,
            values: [.text(id.uuidString)]
        )
    }

    private func cleanupJob(
        _ database: OpaquePointer,
        sql: String,
        values: [SQLValue]
    ) throws -> GRVMCleanupJob? {
        return try self.withStatement(database, sql: sql, values: values) { statement in
            let result = sqlite3_step(statement)
            guard result == SQLITE_ROW else {
                if result != SQLITE_DONE {
                    throw self.sqliteError(database)
                }
                return nil
            }
            return try self.readCleanupJob(statement)
        }
    }

    private func queryCleanupJobs(
        _ database: OpaquePointer,
        sql: String,
        values: [SQLValue]
    ) throws -> [GRVMCleanupJob] {
        return try self.withStatement(database, sql: sql, values: values) { statement in
            var result: [GRVMCleanupJob] = []
            try self.readRows(database, statement: statement) {
                result.append(try self.readCleanupJob(statement))
            }
            return result
        }
    }

    private func readCleanupJob(_ statement: OpaquePointer) throws -> GRVMCleanupJob {
        guard
            let id = UUID(uuidString: self.columnText(statement, 0)),
            let phase = GRVMCleanupPhase(rawValue: sqlite3_column_int(statement, 4))
        else {
            throw GRVMArchiveError.sqlite("invalid cleanup job")
        }
        let storedPeerId = sqlite3_column_int64(statement, 2)
        let storedThreadId = sqlite3_column_int64(statement, 3)
        return GRVMCleanupJob(
            id: id,
            accountId: sqlite3_column_int64(statement, 1),
            peerId: storedPeerId == 0 ? nil : storedPeerId,
            threadId: storedThreadId == 0 ? nil : storedThreadId,
            phase: phase,
            createdAt: sqlite3_column_int(statement, 5),
            messageKeys: try self.jsonDecoder.decode([GRVMMessageKey].self, from: self.columnData(statement, 6)),
            mediaRecords: try self.jsonDecoder.decode([GRVMArchivedMedia].self, from: self.columnData(statement, 7))
        )
    }

    private func media(
        _ database: OpaquePointer,
        accountId: Int64,
        resourceId: String
    ) throws -> GRVMArchivedMedia? {
        return try self.withStatement(
            database,
            sql: """
            SELECT account_id, resource_id, relative_path, byte_count, kind, copy_state, generation
            FROM archived_media_blobs WHERE account_id = ? AND resource_id = ?
            """,
            values: [.int64(accountId), .text(resourceId)]
        ) { statement in
            let result = sqlite3_step(statement)
            guard result == SQLITE_ROW else {
                if result != SQLITE_DONE {
                    throw self.sqliteError(database)
                }
                return nil
            }
            return try self.readMedia(statement)
        }
    }

    private func readMedia(_ statement: OpaquePointer) throws -> GRVMArchivedMedia {
        guard let copyState = GRVMArchivedMedia.CopyState(rawValue: sqlite3_column_int(statement, 5)) else {
            throw GRVMArchiveError.sqlite("invalid archived media copy state")
        }
        return GRVMArchivedMedia(
            accountId: sqlite3_column_int64(statement, 0),
            resourceId: self.columnText(statement, 1),
            relativePath: self.columnText(statement, 2),
            byteCount: sqlite3_column_int64(statement, 3),
            kind: self.columnText(statement, 4),
            copyState: copyState,
            generation: sqlite3_column_int64(statement, 6)
        )
    }

    private func mappedResourceIds(
        _ database: OpaquePointer,
        key: GRVMMessageKey,
        revisionId: Int64
    ) throws -> Set<String> {
        return try self.withStatement(
            database,
            sql: """
            SELECT resource_id FROM archived_message_media
            WHERE account_id = ? AND peer_id = ? AND message_namespace = ?
              AND message_id = ? AND thread_id = ? AND revision_id = ?
            """,
            values: self.keyValues(key) + [.int64(revisionId)]
        ) { statement in
            var result: Set<String> = []
            try self.readRows(database, statement: statement) {
                result.insert(self.columnText(statement, 0))
            }
            return result
        }
    }

    private func readKey(_ statement: OpaquePointer, offset: Int32) -> GRVMMessageKey {
        return GRVMMessageKey(
            accountId: sqlite3_column_int64(statement, offset),
            peerId: sqlite3_column_int64(statement, offset + 1),
            namespace: sqlite3_column_int(statement, offset + 2),
            messageId: sqlite3_column_int(statement, offset + 3),
            threadId: sqlite3_column_int64(statement, offset + 4)
        )
    }

    private func columnText(_ statement: OpaquePointer, _ index: Int32) -> String {
        guard let value = sqlite3_column_text(statement, index) else {
            return ""
        }
        return String(cString: value)
    }

    private func columnData(_ statement: OpaquePointer, _ index: Int32) -> Data {
        guard let bytes = sqlite3_column_blob(statement, index) else {
            return Data()
        }
        return Data(bytes: bytes, count: Int(sqlite3_column_bytes(statement, index)))
    }

    private func encodeResourceIds(_ ids: [String]) -> Data {
        return (try? self.jsonEncoder.encode(Array(Set(ids)).sorted())) ?? Data()
    }

    private func encodeEditableContent(_ content: GRVMEditableMessageContent) throws -> Data {
        return try content.encodedData()
    }

    private func decodeEditableContent(
        _ data: Data,
        text: String,
        entitiesData: Data
    ) -> GRVMEditableMessageContent {
        if !data.isEmpty, let content = try? GRVMEditableMessageContent.decode(data) {
            return content
        }
        return GRVMEditableMessageContent.legacy(text: text, entitiesData: entitiesData)
    }

    private func decodeResourceIds(_ data: Data) -> [String] {
        if let result = try? self.jsonDecoder.decode([String].self, from: data) {
            return result
        }
        guard let legacy = String(data: data, encoding: .utf8), !legacy.isEmpty else {
            return []
        }
        return legacy.split(separator: ",").map(String.init)
    }

    private func sqliteError(_ database: OpaquePointer) -> GRVMArchiveError {
        if let message = sqlite3_errmsg(database) {
            return .sqlite(String(cString: message))
        }
        return .sqlite("unknown sqlite error")
    }
}
