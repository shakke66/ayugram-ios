import Foundation
import Postbox

public enum GRVMDeletionSource: Int32 {
    case server = 0
    case localAction = 1
    case ttl = 2
    case secretRecall = 3
    case validation = 4
    case minimumAvailable = 5
}

public final class GRVMDeletedMessageAttribute: MessageAttribute, LocalMessageDeletionMarker, Equatable {
    public let deletedAt: Int32
    public let source: GRVMDeletionSource
    public let topicId: Int64?
    public let resourceIds: [String]

    public init(deletedAt: Int32, source: GRVMDeletionSource, topicId: Int64?, resourceIds: [String]) {
        self.deletedAt = deletedAt
        self.source = source
        self.topicId = topicId
        self.resourceIds = resourceIds
    }

    public required init(decoder: PostboxDecoder) {
        self.deletedAt = decoder.decodeInt32ForKey("d", orElse: 0)
        self.source = GRVMDeletionSource(rawValue: decoder.decodeInt32ForKey("s", orElse: 0)) ?? .server
        self.topicId = decoder.decodeOptionalInt64ForKey("t")
        self.resourceIds = decoder.decodeStringArrayForKey("r")
    }

    public func encode(_ encoder: PostboxEncoder) {
        encoder.encodeInt32(self.deletedAt, forKey: "d")
        encoder.encodeInt32(self.source.rawValue, forKey: "s")
        if let topicId = self.topicId {
            encoder.encodeInt64(topicId, forKey: "t")
        }
        encoder.encodeStringArray(self.resourceIds, forKey: "r")
    }

    public static func == (lhs: GRVMDeletedMessageAttribute, rhs: GRVMDeletedMessageAttribute) -> Bool {
        return lhs.deletedAt == rhs.deletedAt
            && lhs.source == rhs.source
            && lhs.topicId == rhs.topicId
            && lhs.resourceIds == rhs.resourceIds
    }
}
