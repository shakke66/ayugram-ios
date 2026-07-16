import Foundation

public struct GRVMMessageKey: Hashable, Codable {
    public let accountId: Int64
    public let peerId: Int64
    public let namespace: Int32
    public let messageId: Int32
    public let threadId: Int64

    public init(accountId: Int64, peerId: Int64, namespace: Int32, messageId: Int32, threadId: Int64 = 0) {
        self.accountId = accountId
        self.peerId = peerId
        self.namespace = namespace
        self.messageId = messageId
        self.threadId = threadId
    }
}

public struct GRVMArchivedMessage: Equatable {
    public let key: GRVMMessageKey
    public let senderId: Int64
    public let timestamp: Int32
    public let deletedAt: Int32
    public let text: String
    public let entitiesData: Data
    public let mediaSummary: String
    public let resourceIds: [String]
    public let peerTitle: String
    public let senderName: String

    public init(
        key: GRVMMessageKey,
        senderId: Int64,
        timestamp: Int32,
        deletedAt: Int32,
        text: String,
        entitiesData: Data,
        mediaSummary: String,
        resourceIds: [String],
        peerTitle: String,
        senderName: String
    ) {
        self.key = key
        self.senderId = senderId
        self.timestamp = timestamp
        self.deletedAt = deletedAt
        self.text = text
        self.entitiesData = entitiesData
        self.mediaSummary = mediaSummary
        self.resourceIds = resourceIds
        self.peerTitle = peerTitle
        self.senderName = senderName
    }
}

public struct GRVMEditRevision: Equatable {
    public let rowId: Int64
    public let key: GRVMMessageKey
    public let version: Int32
    public let fingerprint: String
    public let savedAt: Int32
    public let text: String
    public let entitiesData: Data
    public let mediaSummary: String
    public let resourceIds: [String]

    public init(
        rowId: Int64,
        key: GRVMMessageKey,
        version: Int32,
        fingerprint: String,
        savedAt: Int32,
        text: String,
        entitiesData: Data,
        mediaSummary: String,
        resourceIds: [String]
    ) {
        self.rowId = rowId
        self.key = key
        self.version = version
        self.fingerprint = fingerprint
        self.savedAt = savedAt
        self.text = text
        self.entitiesData = entitiesData
        self.mediaSummary = mediaSummary
        self.resourceIds = resourceIds
    }
}

public struct GRVMEditRevisionDraft: Equatable {
    public let key: GRVMMessageKey
    public let fingerprint: String
    public let savedAt: Int32
    public let text: String
    public let entitiesData: Data
    public let mediaSummary: String
    public let resourceIds: [String]

    public init(
        key: GRVMMessageKey,
        fingerprint: String,
        savedAt: Int32,
        text: String,
        entitiesData: Data,
        mediaSummary: String,
        resourceIds: [String]
    ) {
        self.key = key
        self.fingerprint = fingerprint
        self.savedAt = savedAt
        self.text = text
        self.entitiesData = entitiesData
        self.mediaSummary = mediaSummary
        self.resourceIds = resourceIds
    }
}

public struct GRVMArchivedMedia: Codable, Equatable {
    public enum CopyState: Int32, Codable {
        case unavailable = 0
        case copying = 1
        case complete = 2
        case missing = 3
    }

    public let accountId: Int64
    public let resourceId: String
    public let relativePath: String
    public let byteCount: Int64
    public let kind: String
    public let copyState: CopyState

    public init(
        accountId: Int64,
        resourceId: String,
        relativePath: String,
        byteCount: Int64,
        kind: String,
        copyState: CopyState
    ) {
        self.accountId = accountId
        self.resourceId = resourceId
        self.relativePath = relativePath
        self.byteCount = byteCount
        self.kind = kind
        self.copyState = copyState
    }
}

public enum GRVMCleanupPhase: Int32, Codable {
    case planned = 0
    case filesRemoved = 1
}

public struct GRVMCleanupJob: Codable, Equatable {
    public let id: UUID
    public let accountId: Int64
    public let peerId: Int64?
    public let threadId: Int64?
    public let phase: GRVMCleanupPhase
    public let createdAt: Int32
    public let messageKeys: [GRVMMessageKey]
    public let mediaRecords: [GRVMArchivedMedia]

    public init(
        id: UUID,
        accountId: Int64,
        peerId: Int64?,
        threadId: Int64?,
        phase: GRVMCleanupPhase,
        createdAt: Int32,
        messageKeys: [GRVMMessageKey],
        mediaRecords: [GRVMArchivedMedia]
    ) {
        self.id = id
        self.accountId = accountId
        self.peerId = peerId
        self.threadId = threadId
        self.phase = phase
        self.createdAt = createdAt
        self.messageKeys = messageKeys
        self.mediaRecords = mediaRecords
    }
}

public enum GRVMClearDeletedError: Error, Equatable {
    case archiveUnavailable
    case mediaRemovalFailed(Int)
    case databaseFinalizationFailed
}

public struct GRVMArchiveQuery: Equatable {
    public let accountId: Int64
    public let peerId: Int64?
    public let threadId: Int64?
    public let limit: Int32

    public init(accountId: Int64, peerId: Int64?, threadId: Int64?, limit: Int32) {
        self.accountId = accountId
        self.peerId = peerId
        self.threadId = threadId
        self.limit = limit
    }
}

public func grvmContentFingerprint(
    text: String,
    entitiesData: Data,
    mediaSummary: String,
    resourceIds: [String]
) -> String {
    let content: [String: Any] = [
        "text": text,
        "entitiesData": entitiesData.base64EncodedString(),
        "mediaSummary": mediaSummary,
        "resourceIds": Set(resourceIds).sorted()
    ]
    let data = try! JSONSerialization.data(withJSONObject: content, options: [.sortedKeys])
    return data.base64EncodedString()
}
