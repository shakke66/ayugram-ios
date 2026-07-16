import Postbox
import SwiftSignalKit

public final class GRVMFilteredMessageVisibility {
    private struct Key: Hashable {
        let accountPeerId: PeerId
        let chatPeerId: PeerId
    }

    private let showing = Atomic<Set<Key>>(value: [])

    public init() {
    }

    public func isShowing(accountPeerId: PeerId, chatPeerId: PeerId) -> Bool {
        return self.showing.with {
            $0.contains(Key(accountPeerId: accountPeerId, chatPeerId: chatPeerId))
        }
    }

    public func setShowing(accountPeerId: PeerId, chatPeerId: PeerId, value: Bool) {
        _ = self.showing.modify { showing in
            var showing = showing
            let key = Key(accountPeerId: accountPeerId, chatPeerId: chatPeerId)
            if value {
                showing.insert(key)
            } else {
                showing.remove(key)
            }
            return showing
        }
    }

    public func retainAccounts(_ accountPeerIds: Set<PeerId>) {
        _ = self.showing.modify { showing in
            return Set(showing.filter { accountPeerIds.contains($0.accountPeerId) })
        }
    }
}
