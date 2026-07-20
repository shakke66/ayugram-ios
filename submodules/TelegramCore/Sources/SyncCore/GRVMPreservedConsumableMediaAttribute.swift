import Foundation
import Postbox

public final class GRVMPreservedConsumableMediaAttribute: MessageAttribute, Equatable {
    public let resourceIds: [String]
    public let media: [Media]
    public let preparedAt: Int32

    public init(resourceIds: [String], media: [Media], preparedAt: Int32) {
        self.resourceIds = resourceIds.sorted()
        self.media = media
        self.preparedAt = preparedAt
    }

    public required init(decoder: PostboxDecoder) {
        self.resourceIds = decoder.decodeStringArrayForKey("r").sorted()
        self.media = decoder.decodeObjectArrayForKey("m").compactMap { $0 as? Media }
        self.preparedAt = decoder.decodeInt32ForKey("t", orElse: 0)
    }

    public func encode(_ encoder: PostboxEncoder) {
        encoder.encodeStringArray(self.resourceIds, forKey: "r")
        encoder.encodeObjectArray(self.media, forKey: "m")
        encoder.encodeInt32(self.preparedAt, forKey: "t")
    }

    public static func ==(lhs: GRVMPreservedConsumableMediaAttribute, rhs: GRVMPreservedConsumableMediaAttribute) -> Bool {
        return lhs.resourceIds == rhs.resourceIds
            && lhs.preparedAt == rhs.preparedAt
            && areMediaArraysEqual(lhs.media, rhs.media)
    }
}
