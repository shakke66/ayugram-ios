import CryptoUtils
import Foundation

public struct AyuMessageFilter: Codable, Equatable, Identifiable {
    public var id: UUID
    public var expression: String
    public var isEnabled: Bool
    public var isReversed: Bool
    public var isCaseInsensitive: Bool
    public var peerId: Int64?
    public var excludedPeerIds: Set<Int64>

    public init(
        id: UUID = UUID(),
        expression: String,
        isEnabled: Bool = true,
        isReversed: Bool = false,
        isCaseInsensitive: Bool = true,
        peerId: Int64? = nil,
        excludedPeerIds: Set<Int64> = []
    ) {
        self.id = id
        self.expression = expression
        self.isEnabled = isEnabled
        self.isReversed = isReversed
        self.isCaseInsensitive = isCaseInsensitive
        self.peerId = peerId
        self.excludedPeerIds = excludedPeerIds
    }

    static func migratingLegacy(
        kind: String, index: Int, expression: String, isReversed: Bool
    ) -> AyuMessageFilter {
        let data = Data("\(kind)\u{0}\(index)\u{0}\(expression)".utf8)
        let digest = data.withUnsafeBytes { bytes in
            CryptoSHA1(bytes.baseAddress!, Int32(data.count))
        }
        var bytes = Array(digest.prefix(16))
        bytes[6] = (bytes[6] & 0x0f) | 0x50
        bytes[8] = (bytes[8] & 0x3f) | 0x80
        let id = UUID(uuid: (
            bytes[0], bytes[1], bytes[2], bytes[3],
            bytes[4], bytes[5], bytes[6], bytes[7],
            bytes[8], bytes[9], bytes[10], bytes[11],
            bytes[12], bytes[13], bytes[14], bytes[15]
        ))
        return AyuMessageFilter(
            id: id,
            expression: expression,
            isReversed: isReversed
        )
    }
}

public struct AyuMessageFilterBackup: Codable, Equatable {
    public let version: Int
    public let filters: [AyuMessageFilter]

    public init(version: Int, filters: [AyuMessageFilter]) {
        self.version = version
        self.filters = filters
    }
}
