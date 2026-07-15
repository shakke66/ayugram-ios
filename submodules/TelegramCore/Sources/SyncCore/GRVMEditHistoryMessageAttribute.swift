import Foundation
import Postbox

public final class GRVMEditHistoryMessageAttribute: MessageAttribute, Equatable {
    public let latestRevisionAt: Int32

    public init(latestRevisionAt: Int32) {
        self.latestRevisionAt = latestRevisionAt
    }

    public required init(decoder: PostboxDecoder) {
        self.latestRevisionAt = decoder.decodeInt32ForKey("d", orElse: 0)
    }

    public func encode(_ encoder: PostboxEncoder) {
        encoder.encodeInt32(self.latestRevisionAt, forKey: "d")
    }

    public static func == (lhs: GRVMEditHistoryMessageAttribute, rhs: GRVMEditHistoryMessageAttribute) -> Bool {
        return lhs.latestRevisionAt == rhs.latestRevisionAt
    }
}
