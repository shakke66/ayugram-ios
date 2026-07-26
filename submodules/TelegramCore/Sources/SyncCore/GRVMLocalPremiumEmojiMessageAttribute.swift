import Foundation
import Postbox

public final class GRVMLocalPremiumEmojiMessageAttribute: MessageAttribute, Equatable {
    public let fileIds: [Int64]

    public init(fileIds: [Int64]) {
        self.fileIds = fileIds.filter { $0 > 0 }
    }

    public required init(decoder: PostboxDecoder) {
        self.fileIds = decoder.decodeInt64ArrayForKey("f").filter { $0 > 0 }
    }

    public func encode(_ encoder: PostboxEncoder) {
        encoder.encodeInt64Array(self.fileIds, forKey: "f")
    }

    public static func == (lhs: GRVMLocalPremiumEmojiMessageAttribute, rhs: GRVMLocalPremiumEmojiMessageAttribute) -> Bool {
        return lhs.fileIds == rhs.fileIds
    }
}
