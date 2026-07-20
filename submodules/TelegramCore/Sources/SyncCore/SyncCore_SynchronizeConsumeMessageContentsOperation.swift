import Foundation
import Postbox

public final class SynchronizeConsumeMessageContentsOperation: PostboxCoding {
    public let messageIds: [MessageId]
    public let force: Bool
    
    public init(messageIds: [MessageId], force: Bool = false) {
        self.messageIds = messageIds
        self.force = force
    }
    
    public init(decoder: PostboxDecoder) {
        self.messageIds = MessageId.decodeArrayFromBuffer(decoder.decodeBytesForKeyNoCopy("i")!)
        self.force = decoder.decodeInt32ForKey("f", orElse: 0) != 0
    }
    
    public func encode(_ encoder: PostboxEncoder) {
        let buffer = WriteBuffer()
        MessageId.encodeArrayToBuffer(self.messageIds, buffer: buffer)
        encoder.encodeBytes(buffer, forKey: "i")
        encoder.encodeInt32(self.force ? 1 : 0, forKey: "f")
    }
}
