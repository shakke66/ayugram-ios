import Foundation
import Postbox
import TelegramCore

public enum GRVMPeerIdFormat {
    case telegram
    case botAPI
}

public enum GRVMNumericPeerLookup {
    private static let maximumPeerId: Int64 = 0x00ffffffffffffff

    public static func candidates(for query: String) -> [PeerId] {
        var bytes = Array(query.trimmingCharacters(in: .whitespacesAndNewlines).utf8)
        var isExplicit = false

        if bytes.count >= 2,
           (bytes[0] == 0x49 || bytes[0] == 0x69),
           (bytes[1] == 0x44 || bytes[1] == 0x64) {
            guard bytes.count >= 3, bytes[2] == 0x3a || bytes[2] == 0x20 else {
                return []
            }
            isExplicit = true
            bytes.removeFirst(3)
        }

        let isNegative = bytes.first == 0x2d
        let digits = isNegative ? Array(bytes.dropFirst()) : bytes
        guard !digits.isEmpty, digits.allSatisfy({ byte in
            byte >= 0x30 && byte <= 0x39
        }) else {
            return []
        }

        var namespacesAndIds: [(PeerId.Namespace, Int64)] = []
        if isNegative {
            guard !isExplicit else {
                return []
            }
            if digits.starts(with: [0x31, 0x30, 0x30]) {
                let remainderDigits = Array(digits.dropFirst(3))
                guard !remainderDigits.isEmpty,
                      let remainder = parseMagnitude(remainderDigits, maximum: maximumPeerId),
                      remainder != 0 else {
                    return []
                }
                namespacesAndIds.append((Namespaces.Peer.CloudChannel, remainder))
            } else {
                guard let magnitude = parseMagnitude(digits, maximum: maximumPeerId), magnitude != 0 else {
                    return []
                }
                namespacesAndIds.append((Namespaces.Peer.CloudGroup, magnitude))
            }
        } else {
            guard let magnitude = parseMagnitude(digits, maximum: maximumPeerId), magnitude != 0 else {
                return []
            }
            if isExplicit {
                namespacesAndIds.append((Namespaces.Peer.CloudUser, magnitude))
                namespacesAndIds.append((Namespaces.Peer.CloudGroup, magnitude))
                namespacesAndIds.append((Namespaces.Peer.CloudChannel, magnitude))
            } else if digits.count >= 5 {
                namespacesAndIds.append((Namespaces.Peer.CloudUser, magnitude))
            }
        }

        var result: [PeerId] = []
        var existingIds = Set<PeerId>()
        for (namespace, magnitude) in namespacesAndIds {
            let id = PeerId(namespace: namespace, id: PeerId.Id._internalFromInt64Value(magnitude))
            if existingIds.insert(id).inserted {
                result.append(id)
            }
        }
        return result
    }

    private static func parseMagnitude(_ digits: [UInt8], maximum: Int64) -> Int64? {
        var magnitude: Int64 = 0
        for byte in digits {
            let digit = Int64(byte - 0x30)
            if magnitude > (maximum - digit) / 10 {
                return nil
            }
            magnitude = magnitude * 10 + digit
        }
        return magnitude
    }
}

public func grvmFormatPeerId(_ peerId: PeerId, format: GRVMPeerIdFormat) -> String {
    let rawValue = String(peerId.id._internalGetInt64Value())
    switch format {
    case .telegram:
        return rawValue
    case .botAPI:
        break
    }

    let rawMagnitude = rawValue.hasPrefix("-") ? String(rawValue.dropFirst()) : rawValue
    if peerId.namespace == Namespaces.Peer.CloudGroup {
        return "-\(rawMagnitude)"
    } else if peerId.namespace == Namespaces.Peer.CloudChannel {
        return "-100\(rawMagnitude)"
    } else {
        return rawValue
    }
}
