import Foundation
import Postbox
import SwiftSignalKit

/// Short-lived authorization for one explicit server read.
final class GRVMReadReceiptBypass {
    private struct Entry {
        let tokenId: PeerReadStateSynchronizationForceTokenId
        let accountPeerId: PeerId
        let peerId: PeerId
        let maxIncomingReadId: MessageId.Id
        let state: CombinedPeerReadState
        let expiresAt: Double
    }

    static let shared = GRVMReadReceiptBypass()

    private let entries = Atomic<[Entry]>(value: [])
    private let queue = Queue(name: "GRVMReadReceiptBypass")

    private init() {
    }

    @discardableResult
    func register(accountPeerId: PeerId, peerId: PeerId, maxIncomingReadId: MessageId.Id, state: CombinedPeerReadState) -> PeerReadStateSynchronizationForceTokenId {
        let now = CFAbsoluteTimeGetCurrent()
        let expiresAt = now + 30.0
        var tokenId = PeerReadStateSynchronizationForceTokenId(high: 0, low: 0)
        let _ = self.entries.modify { entries in
            var entries = entries.filter { entry in
                return entry.expiresAt > now
            }
            repeat {
                tokenId = PeerReadStateSynchronizationForceTokenId(
                    high: Int64(bitPattern: UInt64.random(in: UInt64.min ... UInt64.max)),
                    low: Int64(bitPattern: UInt64.random(in: UInt64.min ... UInt64.max))
                )
            } while (tokenId.high == 0 && tokenId.low == 0) || entries.contains(where: { entry in
                return entry.tokenId == tokenId
            })
            entries.append(Entry(
                tokenId: tokenId,
                accountPeerId: accountPeerId,
                peerId: peerId,
                maxIncomingReadId: maxIncomingReadId,
                state: state,
                expiresAt: expiresAt
            ))
            return entries
        }

        self.queue.after(30.0, { [weak self] in
            self?.remove(tokenId: tokenId)
        })
        return tokenId
    }

    func consumeIfMatching(tokenId: PeerReadStateSynchronizationForceTokenId, accountPeerId: PeerId, peerId: PeerId, maxIncomingReadId: MessageId.Id?, state: CombinedPeerReadState?) -> Bool {
        var consumed = false
        let now = CFAbsoluteTimeGetCurrent()
        let _ = self.entries.modify { entries in
            var entries = entries

            entries.removeAll(where: { $0.expiresAt <= now })
            if let index = entries.firstIndex(where: { entry in
                return entry.tokenId == tokenId
            }) {
                let entry = entries.remove(at: index)
                if let maxIncomingReadId = maxIncomingReadId, let state = state {
                    consumed = entry.accountPeerId == accountPeerId
                        && entry.peerId == peerId
                        && entry.maxIncomingReadId == maxIncomingReadId
                        && entry.state == state
                }
            }
            return entries
        }
        return consumed
    }

    private func remove(tokenId: PeerReadStateSynchronizationForceTokenId) {
        let _ = self.entries.modify { entries in
            return entries.filter { $0.tokenId != tokenId }
        }
    }
}
