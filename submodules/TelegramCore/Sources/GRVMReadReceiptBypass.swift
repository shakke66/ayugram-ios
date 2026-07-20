import Foundation
import Postbox
import SwiftSignalKit

/// Short-lived authorization for one explicit server read.
final class GRVMReadReceiptBypass {
    private struct Entry {
        let tokenId: Int64
        let accountPeerId: PeerId
        let peerId: PeerId
        let maxIncomingReadId: MessageId.Id
        let expiresAt: Double
    }

    static let shared = GRVMReadReceiptBypass()

    private let entries = Atomic<[Entry]>(value: [])
    private let nextTokenId = Atomic<Int64>(value: 0)
    private let queue = Queue(name: "GRVMReadReceiptBypass")

    private init() {
    }

    @discardableResult
    func register(accountPeerId: PeerId, peerId: PeerId, maxIncomingReadId: MessageId.Id) -> Int64 {
        let tokenId = self.nextTokenId.modify { value in
            return value &+ 1
        }
        let expiresAt = CFAbsoluteTimeGetCurrent() + 30.0

        let entry = Entry(
            tokenId: tokenId,
            accountPeerId: accountPeerId,
            peerId: peerId,
            maxIncomingReadId: maxIncomingReadId,
            expiresAt: expiresAt
        )
        let _ = self.entries.modify { entries in
            return entries + [entry]
        }

        self.queue.after(30.0, { [weak self] in
            self?.remove(tokenId: tokenId)
        })
        return tokenId
    }

    func consumeIfMatching(accountPeerId: PeerId, peerId: PeerId, maxIncomingReadId: MessageId.Id?) -> Bool {
        var consumed = false
        let now = CFAbsoluteTimeGetCurrent()
        let _ = self.entries.modify { entries in
            var entries = entries

            func consumeMatchingEntry() -> Bool {
                entries.removeAll(where: { $0.expiresAt <= now })
                if let index = entries.firstIndex(where: { entry in
                    return entry.accountPeerId == accountPeerId
                        && entry.peerId == peerId
                        && entry.maxIncomingReadId == maxIncomingReadId
                }) {
                    entries.remove(at: index)
                    return true
                }
                return false
            }

            consumed = consumeMatchingEntry()
            return entries
        }
        return consumed
    }

    private func remove(tokenId: Int64) {
        let _ = self.entries.modify { entries in
            return entries.filter { $0.tokenId != tokenId }
        }
    }
}
