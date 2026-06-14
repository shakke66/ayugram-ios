import Foundation
import SQLite3
import Postbox
import TelegramCore
import SwiftSignalKit

public struct AyuSavedMessage: Equatable {
    public let id: Int64
    public let peerId: Int64
    public let messageId: Int32
    public let senderId: Int64
    public let date: Int32
    public let text: String
    public let mediaDescription: String
    public let entityCreateDate: Int32
    public let isEdited: Bool
    public let editVersion: Int32
    public let peerTitle: String
    public let senderName: String
    public let mediaResourceIds: String

    public init(id: Int64, peerId: Int64, messageId: Int32, senderId: Int64, date: Int32, text: String, mediaDescription: String, entityCreateDate: Int32, isEdited: Bool, editVersion: Int32, peerTitle: String = "", senderName: String = "", mediaResourceIds: String = "") {
        self.id = id
        self.peerId = peerId
        self.messageId = messageId
        self.senderId = senderId
        self.date = date
        self.text = text
        self.mediaDescription = mediaDescription
        self.entityCreateDate = entityCreateDate
        self.isEdited = isEdited
        self.editVersion = editVersion
        self.peerTitle = peerTitle
        self.senderName = senderName
        self.mediaResourceIds = mediaResourceIds
    }
}

public final class AyuDeletedMessagesDB {
    public static let shared = AyuDeletedMessagesDB()

    private var db: OpaquePointer?
    private let queue = DispatchQueue(label: "com.ayugram.deletedMessagesDB", qos: .userInitiated)

    private init() {
        self.openDatabase()
        self.createTables()
    }

    deinit {
        if let db = self.db {
            sqlite3_close(db)
        }
    }

    private func openDatabase() {
        let documentsPath = NSSearchPathForDirectoriesInDomains(.documentDirectory, .userDomainMask, true).first!
        let dbPath = (documentsPath as NSString).appendingPathComponent("ayugram_messages.db")

        if sqlite3_open(dbPath, &self.db) != SQLITE_OK {
            print("[AyuGram] Failed to open database at \(dbPath)")
        }

        sqlite3_exec(self.db, "PRAGMA journal_mode=WAL", nil, nil, nil)
        sqlite3_exec(self.db, "PRAGMA synchronous=NORMAL", nil, nil, nil)
    }

    private func createTables() {
        let createDeletedMessages = """
        CREATE TABLE IF NOT EXISTS deleted_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            date INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            media_description TEXT NOT NULL DEFAULT '',
            entity_create_date INTEGER NOT NULL,
            UNIQUE(peer_id, message_id, entity_create_date)
        );
        CREATE INDEX IF NOT EXISTS idx_deleted_peer ON deleted_messages(peer_id);
        CREATE INDEX IF NOT EXISTS idx_deleted_msg ON deleted_messages(peer_id, message_id);
        """

        let createEditedMessages = """
        CREATE TABLE IF NOT EXISTS edited_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            date INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            media_description TEXT NOT NULL DEFAULT '',
            edit_date INTEGER NOT NULL,
            version INTEGER NOT NULL DEFAULT 0,
            UNIQUE(peer_id, message_id, version)
        );
        CREATE INDEX IF NOT EXISTS idx_edited_peer ON edited_messages(peer_id);
        CREATE INDEX IF NOT EXISTS idx_edited_msg ON edited_messages(peer_id, message_id);
        """

        sqlite3_exec(self.db, createDeletedMessages, nil, nil, nil)
        sqlite3_exec(self.db, createEditedMessages, nil, nil, nil)

        // Denormalized names (added in W3 phase 2). ADD COLUMN is idempotent here:
        // it succeeds on tables created before these columns existed, and the error
        // when the column already exists is intentionally ignored.
        sqlite3_exec(self.db, "ALTER TABLE deleted_messages ADD COLUMN peer_title TEXT NOT NULL DEFAULT ''", nil, nil, nil)
        sqlite3_exec(self.db, "ALTER TABLE deleted_messages ADD COLUMN sender_name TEXT NOT NULL DEFAULT ''", nil, nil, nil)
        sqlite3_exec(self.db, "ALTER TABLE edited_messages ADD COLUMN peer_title TEXT NOT NULL DEFAULT ''", nil, nil, nil)
        sqlite3_exec(self.db, "ALTER TABLE edited_messages ADD COLUMN sender_name TEXT NOT NULL DEFAULT ''", nil, nil, nil)

        // Preserved media resource ids (comma-separated). Bytes live in the shared
        // mediaBox; storing the ids keeps the reference alive for future rendering.
        sqlite3_exec(self.db, "ALTER TABLE deleted_messages ADD COLUMN media_resources TEXT NOT NULL DEFAULT ''", nil, nil, nil)
        sqlite3_exec(self.db, "ALTER TABLE edited_messages ADD COLUMN media_resources TEXT NOT NULL DEFAULT ''", nil, nil, nil)
    }

    // MARK: - Save Deleted Message

    public func saveDeletedMessage(_ message: Message) {
        self.queue.async { [weak self] in
            guard let self = self, let db = self.db else { return }

            let sql = """
            INSERT OR IGNORE INTO deleted_messages (peer_id, message_id, sender_id, date, text, media_description, entity_create_date, peer_title, sender_name, media_resources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }

            let peerId = message.id.peerId.toInt64()
            let messageId = message.id.id
            let senderId = message.author?.id.toInt64() ?? 0
            let date = message.timestamp
            let text = message.text
            let mediaDesc = self.describeMedia(message.media)
            let mediaResources = self.mediaResourceIds(message.media)
            let now = Int32(Date().timeIntervalSince1970)
            let peerTitle = message.peers[message.id.peerId]?.debugDisplayTitle ?? ""
            let senderName = message.author?.debugDisplayTitle ?? ""

            sqlite3_bind_int64(stmt, 1, peerId)
            sqlite3_bind_int(stmt, 2, messageId)
            sqlite3_bind_int64(stmt, 3, senderId)
            sqlite3_bind_int(stmt, 4, date)
            sqlite3_bind_text(stmt, 5, (text as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 6, (mediaDesc as NSString).utf8String, -1, nil)
            sqlite3_bind_int(stmt, 7, now)
            sqlite3_bind_text(stmt, 8, (peerTitle as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 9, (senderName as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 10, (mediaResources as NSString).utf8String, -1, nil)

            sqlite3_step(stmt)
        }
    }

    public func saveDeletedMessages(_ messages: [Message]) {
        for message in messages {
            self.saveDeletedMessage(message)
        }
    }

    // MARK: - Save Edited Message (pre-edit version)

    public func saveEditedMessage(oldMessage: Message) {
        self.queue.async { [weak self] in
            guard let self = self, let db = self.db else { return }

            let countSql = "SELECT COUNT(*) FROM edited_messages WHERE peer_id = ? AND message_id = ?"
            var countStmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, countSql, -1, &countStmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(countStmt) }

            let peerId = oldMessage.id.peerId.toInt64()
            let messageId = oldMessage.id.id

            sqlite3_bind_int64(countStmt, 1, peerId)
            sqlite3_bind_int(countStmt, 2, messageId)

            var version: Int32 = 0
            if sqlite3_step(countStmt) == SQLITE_ROW {
                version = sqlite3_column_int(countStmt, 0)
            }

            let sql = """
            INSERT OR IGNORE INTO edited_messages (peer_id, message_id, sender_id, date, text, media_description, edit_date, version, peer_title, sender_name, media_resources)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }

            let senderId = oldMessage.author?.id.toInt64() ?? 0
            let date = oldMessage.timestamp
            let text = oldMessage.text
            let mediaDesc = self.describeMedia(oldMessage.media)
            let mediaResources = self.mediaResourceIds(oldMessage.media)
            let now = Int32(Date().timeIntervalSince1970)
            let peerTitle = oldMessage.peers[oldMessage.id.peerId]?.debugDisplayTitle ?? ""
            let senderName = oldMessage.author?.debugDisplayTitle ?? ""

            sqlite3_bind_int64(stmt, 1, peerId)
            sqlite3_bind_int(stmt, 2, messageId)
            sqlite3_bind_int64(stmt, 3, senderId)
            sqlite3_bind_int(stmt, 4, date)
            sqlite3_bind_text(stmt, 5, (text as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 6, (mediaDesc as NSString).utf8String, -1, nil)
            sqlite3_bind_int(stmt, 7, now)
            sqlite3_bind_int(stmt, 8, version)
            sqlite3_bind_text(stmt, 9, (peerTitle as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 10, (senderName as NSString).utf8String, -1, nil)
            sqlite3_bind_text(stmt, 11, (mediaResources as NSString).utf8String, -1, nil)

            sqlite3_step(stmt)
        }
    }

    // MARK: - Query

    public func getDeletedMessages(peerId: Int64, limit: Int32 = 100) -> [AyuSavedMessage] {
        var results: [AyuSavedMessage] = []

        self.queue.sync { [weak self] in
            guard let self = self, let db = self.db else { return }

            let sql = "SELECT id, peer_id, message_id, sender_id, date, text, media_description, entity_create_date, peer_title, sender_name, media_resources FROM deleted_messages WHERE peer_id = ? ORDER BY entity_create_date DESC LIMIT ?"

            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }

            sqlite3_bind_int64(stmt, 1, peerId)
            sqlite3_bind_int(stmt, 2, limit)

            while sqlite3_step(stmt) == SQLITE_ROW {
                let msg = AyuSavedMessage(
                    id: sqlite3_column_int64(stmt, 0),
                    peerId: sqlite3_column_int64(stmt, 1),
                    messageId: sqlite3_column_int(stmt, 2),
                    senderId: sqlite3_column_int64(stmt, 3),
                    date: sqlite3_column_int(stmt, 4),
                    text: String(cString: sqlite3_column_text(stmt, 5)),
                    mediaDescription: String(cString: sqlite3_column_text(stmt, 6)),
                    entityCreateDate: sqlite3_column_int(stmt, 7),
                    isEdited: false,
                    editVersion: 0,
                    peerTitle: String(cString: sqlite3_column_text(stmt, 8)),
                    senderName: String(cString: sqlite3_column_text(stmt, 9)),
                    mediaResourceIds: String(cString: sqlite3_column_text(stmt, 10))
                )
                results.append(msg)
            }
        }

        return results
    }

    public func getAllDeletedMessages(limit: Int32 = 200) -> [AyuSavedMessage] {
        var results: [AyuSavedMessage] = []

        self.queue.sync { [weak self] in
            guard let self = self, let db = self.db else { return }

            let sql = "SELECT id, peer_id, message_id, sender_id, date, text, media_description, entity_create_date, peer_title, sender_name, media_resources FROM deleted_messages ORDER BY entity_create_date DESC LIMIT ?"

            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }

            sqlite3_bind_int(stmt, 1, limit)

            while sqlite3_step(stmt) == SQLITE_ROW {
                let msg = AyuSavedMessage(
                    id: sqlite3_column_int64(stmt, 0),
                    peerId: sqlite3_column_int64(stmt, 1),
                    messageId: sqlite3_column_int(stmt, 2),
                    senderId: sqlite3_column_int64(stmt, 3),
                    date: sqlite3_column_int(stmt, 4),
                    text: String(cString: sqlite3_column_text(stmt, 5)),
                    mediaDescription: String(cString: sqlite3_column_text(stmt, 6)),
                    entityCreateDate: sqlite3_column_int(stmt, 7),
                    isEdited: false,
                    editVersion: 0,
                    peerTitle: String(cString: sqlite3_column_text(stmt, 8)),
                    senderName: String(cString: sqlite3_column_text(stmt, 9)),
                    mediaResourceIds: String(cString: sqlite3_column_text(stmt, 10))
                )
                results.append(msg)
            }
        }

        return results
    }

    public func getEditHistory(peerId: Int64, messageId: Int32) -> [AyuSavedMessage] {
        var results: [AyuSavedMessage] = []

        self.queue.sync { [weak self] in
            guard let self = self, let db = self.db else { return }

            let sql = "SELECT id, peer_id, message_id, sender_id, date, text, media_description, edit_date, version, peer_title, sender_name, media_resources FROM edited_messages WHERE peer_id = ? AND message_id = ? ORDER BY version ASC"

            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }

            sqlite3_bind_int64(stmt, 1, peerId)
            sqlite3_bind_int(stmt, 2, messageId)

            while sqlite3_step(stmt) == SQLITE_ROW {
                let msg = AyuSavedMessage(
                    id: sqlite3_column_int64(stmt, 0),
                    peerId: sqlite3_column_int64(stmt, 1),
                    messageId: sqlite3_column_int(stmt, 2),
                    senderId: sqlite3_column_int64(stmt, 3),
                    date: sqlite3_column_int(stmt, 4),
                    text: String(cString: sqlite3_column_text(stmt, 5)),
                    mediaDescription: String(cString: sqlite3_column_text(stmt, 6)),
                    entityCreateDate: sqlite3_column_int(stmt, 7),
                    isEdited: true,
                    editVersion: sqlite3_column_int(stmt, 8),
                    peerTitle: String(cString: sqlite3_column_text(stmt, 9)),
                    senderName: String(cString: sqlite3_column_text(stmt, 10)),
                    mediaResourceIds: String(cString: sqlite3_column_text(stmt, 11))
                )
                results.append(msg)
            }
        }

        return results
    }

    public func getAllEditedMessages(limit: Int32 = 200) -> [AyuSavedMessage] {
        var results: [AyuSavedMessage] = []

        self.queue.sync { [weak self] in
            guard let self = self, let db = self.db else { return }

            let sql = "SELECT id, peer_id, message_id, sender_id, date, text, media_description, edit_date, version, peer_title, sender_name, media_resources FROM edited_messages ORDER BY edit_date DESC LIMIT ?"

            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }

            sqlite3_bind_int(stmt, 1, limit)

            while sqlite3_step(stmt) == SQLITE_ROW {
                let msg = AyuSavedMessage(
                    id: sqlite3_column_int64(stmt, 0),
                    peerId: sqlite3_column_int64(stmt, 1),
                    messageId: sqlite3_column_int(stmt, 2),
                    senderId: sqlite3_column_int64(stmt, 3),
                    date: sqlite3_column_int(stmt, 4),
                    text: String(cString: sqlite3_column_text(stmt, 5)),
                    mediaDescription: String(cString: sqlite3_column_text(stmt, 6)),
                    entityCreateDate: sqlite3_column_int(stmt, 7),
                    isEdited: true,
                    editVersion: sqlite3_column_int(stmt, 8),
                    peerTitle: String(cString: sqlite3_column_text(stmt, 9)),
                    senderName: String(cString: sqlite3_column_text(stmt, 10)),
                    mediaResourceIds: String(cString: sqlite3_column_text(stmt, 11))
                )
                results.append(msg)
            }
        }

        return results
    }

    // MARK: - Helpers

    private func describeMedia(_ media: [Media]) -> String {
        var descriptions: [String] = []
        for m in media {
            if let _ = m as? TelegramMediaImage {
                descriptions.append("photo")
            } else if let file = m as? TelegramMediaFile {
                if file.isVideo {
                    if file.isInstantVideo {
                        descriptions.append("video_message")
                    } else {
                        descriptions.append("video")
                    }
                } else if file.isVoice {
                    descriptions.append("voice")
                } else if file.isSticker {
                    descriptions.append("sticker")
                } else if file.isAnimatedSticker {
                    descriptions.append("animated_sticker")
                } else if file.isMusic {
                    descriptions.append("audio")
                } else {
                    descriptions.append("document:\(file.fileName ?? "unknown")")
                }
            } else if let _ = m as? TelegramMediaContact {
                descriptions.append("contact")
            } else if let _ = m as? TelegramMediaMap {
                descriptions.append("location")
            } else if let _ = m as? TelegramMediaPoll {
                descriptions.append("poll")
            }
        }
        return descriptions.joined(separator: ",")
    }

    private func mediaResourceIds(_ media: [Media]) -> String {
        var ids: [String] = []
        for m in media {
            if let image = m as? TelegramMediaImage {
                if let resource = image.representations.last?.resource {
                    ids.append(resource.id.stringRepresentation)
                }
            } else if let file = m as? TelegramMediaFile {
                ids.append(file.resource.id.stringRepresentation)
            }
        }
        return ids.joined(separator: ",")
    }

    // MARK: - Cleanup

    public func clearAll() {
        self.queue.async { [weak self] in
            guard let self = self, let db = self.db else { return }
            sqlite3_exec(db, "DELETE FROM deleted_messages", nil, nil, nil)
            sqlite3_exec(db, "DELETE FROM edited_messages", nil, nil, nil)
        }
    }

    public func clearForPeer(_ peerId: Int64) {
        self.queue.async { [weak self] in
            guard let self = self, let db = self.db else { return }

            let sql1 = "DELETE FROM deleted_messages WHERE peer_id = ?"
            let sql2 = "DELETE FROM edited_messages WHERE peer_id = ?"

            for sql in [sql1, sql2] {
                var stmt: OpaquePointer?
                if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
                    sqlite3_bind_int64(stmt, 1, peerId)
                    sqlite3_step(stmt)
                    sqlite3_finalize(stmt)
                }
            }
        }
    }

    // MARK: - Check Methods

    public func isMessageDeleted(peerId: Int64, messageId: Int32) -> Bool {
        var result = false
        self.queue.sync { [weak self] in
            guard let self = self, let db = self.db else { return }
            let sql = "SELECT COUNT(*) FROM deleted_messages WHERE peer_id = ? AND message_id = ?"
            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }
            sqlite3_bind_int64(stmt, 1, peerId)
            sqlite3_bind_int(stmt, 2, messageId)
            if sqlite3_step(stmt) == SQLITE_ROW {
                result = sqlite3_column_int(stmt, 0) > 0
            }
        }
        return result
    }

    public func hasEditHistory(peerId: Int64, messageId: Int32) -> Bool {
        var result = false
        self.queue.sync { [weak self] in
            guard let self = self, let db = self.db else { return }
            let sql = "SELECT COUNT(*) FROM edited_messages WHERE peer_id = ? AND message_id = ?"
            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
            defer { sqlite3_finalize(stmt) }
            sqlite3_bind_int64(stmt, 1, peerId)
            sqlite3_bind_int(stmt, 2, messageId)
            if sqlite3_step(stmt) == SQLITE_ROW {
                result = sqlite3_column_int(stmt, 0) > 0
            }
        }
        return result
    }
}
