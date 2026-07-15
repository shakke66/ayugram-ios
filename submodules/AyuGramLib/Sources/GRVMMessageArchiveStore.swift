import Foundation
import sqlcipher

private let grvmSQLiteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

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
                    try self.execute(database, sql: "PRAGMA user_version = 2")
                case 2:
                    try self.execute(database, sql: Self.schemaV2)
                default:
                    throw GRVMArchiveError.unsupportedSchema(version)
                }
            }
        }
    }

    public func saveDeleted(
        _ messages: [GRVMArchivedMessage],
        media: [GRVMMessageKey: [GRVMArchivedMedia]]
    ) throws {
        try self.perform { database in
            try self.transaction(database) {
                for message in messages {
                    try self.executePrepared(
                        database,
                        sql: """
                        INSERT INTO archived_messages (
                            account_id, peer_id, message_namespace, message_id, thread_id,
                            sender_id, message_timestamp, deleted_at, text, entities,
                            media_summary, peer_title, sender_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(account_id, peer_id, message_namespace, message_id, thread_id)
                        DO UPDATE SET sender_id = excluded.sender_id,
                                      message_timestamp = excluded.message_timestamp,
                                      deleted_at = excluded.deleted_at,
                                      text = excluded.text,
                                      entities = excluded.entities,
                                      media_summary = excluded.media_summary,
                                      peer_title = excluded.peer_title,
                                      sender_name = excluded.sender_name
                        """,
                        values: self.messageValues(message)
                    )
                    for record in media[message.key] ?? [] {
                        try self.upsertMedia(database, record: record)
                        try self.insertMapping(database, key: message.key, revisionId: 0, resourceId: record.resourceId)
                    }
                }
            }
        }
    }

    public func saveRevision(
        _ draft: GRVMEditRevisionDraft,
        media: [GRVMArchivedMedia]
    ) throws -> GRVMEditRevision {
        return try self.perform { database in
            try self.transaction(database) {
                if let existing = try self.revision(database, key: draft.key, fingerprint: draft.fingerprint) {
                    for record in media {
                        try self.upsertMedia(database, record: record)
                        try self.insertMapping(database, key: draft.key, revisionId: existing.rowId, resourceId: record.resourceId)
                    }
                    return existing
                }

                let version = try self.nextRevisionVersion(database, key: draft.key)
                try self.executePrepared(
                    database,
                    sql: """
                    INSERT INTO edit_revisions (
                        account_id, peer_id, message_namespace, message_id, thread_id,
                        version, fingerprint, saved_at, text, entities, media_summary, resource_ids
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values: self.keyValues(draft.key) + [
                        .int32(version),
                        .text(draft.fingerprint),
                        .int32(draft.savedAt),
                        .text(draft.text),
                        .data(draft.entitiesData),
                        .text(draft.mediaSummary),
                        .data(self.encodeResourceIds(draft.resourceIds))
                    ]
                )
                let rowId = sqlite3_last_insert_rowid(database)
                for record in media {
                    try self.upsertMedia(database, record: record)
                    try self.insertMapping(database, key: draft.key, revisionId: rowId, resourceId: record.resourceId)
                }
                return GRVMEditRevision(
                    rowId: rowId,
                    key: draft.key,
                    version: version,
                    fingerprint: draft.fingerprint,
                    savedAt: draft.savedAt,
                    text: draft.text,
                    entitiesData: draft.entitiesData,
                    mediaSummary: draft.mediaSummary,
                    resourceIds: draft.resourceIds
                )
            }
        }
    }

    public func updateMedia(_ record: GRVMArchivedMedia) throws {
        try self.perform { database in
            try self.upsertMedia(database, record: record)
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
                       sender_id, message_timestamp, deleted_at, text, entities,
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
                       sender_id, message_timestamp, deleted_at, text, entities,
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
                       version, fingerprint, saved_at, text, entities, media_summary, resource_ids
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
                    SELECT account_id, resource_id, relative_path, byte_count, kind, copy_state
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
                SELECT account_id, resource_id, relative_path, byte_count, kind, copy_state
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

    public func removeDeleted(_ keys: [GRVMMessageKey]) throws -> [GRVMArchivedMedia] {
        guard !keys.isEmpty else {
            return []
        }
        return try self.perform { database in
            try self.transaction(database) {
                var candidates: [Int64: Set<String>] = [:]
                for key in keys {
                    candidates[key.accountId, default: []].formUnion(
                        try self.mappedResourceIds(database, key: key, revisionId: 0)
                    )
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

                var removed: [GRVMArchivedMedia] = []
                for (accountId, resourceIds) in candidates {
                    for resourceId in resourceIds {
                        let references = try self.scalarInt64(
                            database,
                            sql: """
                            SELECT COUNT(*) FROM archived_message_media
                            WHERE account_id = ? AND resource_id = ?
                            """,
                            values: [.int64(accountId), .text(resourceId)]
                        )
                        guard references == 0 else {
                            continue
                        }
                        if let record = try self.media(database, accountId: accountId, resourceId: resourceId) {
                            removed.append(record)
                        }
                        try self.executePrepared(
                            database,
                            sql: "DELETE FROM archived_media_blobs WHERE account_id = ? AND resource_id = ?",
                            values: [.int64(accountId), .text(resourceId)]
                        )
                    }
                }
                return removed
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

    private func upsertMedia(_ database: OpaquePointer, record: GRVMArchivedMedia) throws {
        try self.executePrepared(
            database,
            sql: """
            INSERT INTO archived_media_blobs (
                account_id, resource_id, relative_path, byte_count, kind, copy_state
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, resource_id) DO UPDATE SET
                relative_path = excluded.relative_path,
                byte_count = CASE
                    WHEN archived_media_blobs.copy_state = 2 AND excluded.copy_state = 1
                    THEN archived_media_blobs.byte_count ELSE excluded.byte_count END,
                kind = excluded.kind,
                copy_state = CASE
                    WHEN archived_media_blobs.copy_state = 2 AND excluded.copy_state = 1
                    THEN archived_media_blobs.copy_state ELSE excluded.copy_state END
            """,
            values: [
                .int64(record.accountId),
                .text(record.resourceId),
                .text(record.relativePath),
                .int64(record.byteCount),
                .text(record.kind),
                .int32(record.copyState.rawValue)
            ]
        )
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
                    text: self.columnText(statement, 8),
                    entitiesData: self.columnData(statement, 9),
                    mediaSummary: self.columnText(statement, 10),
                    resourceIds: try self.mappedResourceIds(database, key: key, revisionId: 0).sorted(),
                    peerTitle: self.columnText(statement, 11),
                    senderName: self.columnText(statement, 12)
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
                   version, fingerprint, saved_at, text, entities, media_summary, resource_ids
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
        return GRVMEditRevision(
            rowId: sqlite3_column_int64(statement, 0),
            key: self.readKey(statement, offset: 1),
            version: sqlite3_column_int(statement, 6),
            fingerprint: self.columnText(statement, 7),
            savedAt: sqlite3_column_int(statement, 8),
            text: self.columnText(statement, 9),
            entitiesData: self.columnData(statement, 10),
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
                if let record = self.readMedia(statement) {
                    result.append(record)
                }
            }
            return result
        }
    }

    private func media(
        _ database: OpaquePointer,
        accountId: Int64,
        resourceId: String
    ) throws -> GRVMArchivedMedia? {
        return try self.withStatement(
            database,
            sql: """
            SELECT account_id, resource_id, relative_path, byte_count, kind, copy_state
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
            return self.readMedia(statement)
        }
    }

    private func readMedia(_ statement: OpaquePointer) -> GRVMArchivedMedia? {
        guard let copyState = GRVMArchivedMedia.CopyState(rawValue: sqlite3_column_int(statement, 5)) else {
            return nil
        }
        return GRVMArchivedMedia(
            accountId: sqlite3_column_int64(statement, 0),
            resourceId: self.columnText(statement, 1),
            relativePath: self.columnText(statement, 2),
            byteCount: sqlite3_column_int64(statement, 3),
            kind: self.columnText(statement, 4),
            copyState: copyState
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
        return (try? JSONEncoder().encode(Array(Set(ids)).sorted())) ?? Data()
    }

    private func decodeResourceIds(_ data: Data) -> [String] {
        if let result = try? JSONDecoder().decode([String].self, from: data) {
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
