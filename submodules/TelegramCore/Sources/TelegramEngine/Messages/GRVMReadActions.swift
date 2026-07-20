import Foundation
import Postbox
import SwiftSignalKit

public enum GRVMReadMode {
    case automatic
    case localOnly
    case forceServer
}

func _internal_grvmApplyMaxReadIndex(account: Account, index: MessageIndex, mode: GRVMReadMode) -> Signal<Void, NoError> {
    switch mode {
    case .automatic:
        return _internal_applyMaxReadIndexInteractively(
            postbox: account.postbox,
            stateManager: account.stateManager,
            index: index
        )
    case .localOnly:
        guard index.id.namespace == Namespaces.Message.Cloud,
              index.id.peerId.namespace == Namespaces.Peer.CloudUser
                || index.id.peerId.namespace == Namespaces.Peer.CloudGroup
                || index.id.peerId.namespace == Namespaces.Peer.CloudChannel else {
            return .single(())
        }

        return account.postbox.transaction { transaction -> Void in
            _internal_applyMaxReadIndexInteractively(
                transaction: transaction,
                stateManager: account.stateManager,
                index: index
            )
            transaction.confirmSynchronizedIncomingReadState(index.id.peerId)
        }
    case .forceServer:
        guard index.id.namespace == Namespaces.Message.Cloud,
              index.id.peerId.namespace == Namespaces.Peer.CloudUser
                || index.id.peerId.namespace == Namespaces.Peer.CloudGroup
                || index.id.peerId.namespace == Namespaces.Peer.CloudChannel else {
            return .single(())
        }

        return deferred {
            let _ = GRVMReadReceiptBypass.shared.register(
                accountPeerId: account.peerId,
                peerId: index.id.peerId,
                maxIncomingReadId: index.id.id
            )
            return _internal_applyMaxReadIndexInteractively(
                postbox: account.postbox,
                stateManager: account.stateManager,
                index: index
            )
        }
    }
}
