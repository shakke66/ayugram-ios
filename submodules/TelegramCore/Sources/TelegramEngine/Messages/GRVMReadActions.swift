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
              (index.id.peerId.namespace == Namespaces.Peer.CloudUser
                || index.id.peerId.namespace == Namespaces.Peer.CloudGroup
                || index.id.peerId.namespace == Namespaces.Peer.CloudChannel) else {
            return .single(())
        }

        return account.postbox.transaction { transaction -> Void in
            let associatedHistoryMessageId = (transaction.getPeerCachedData(peerId: index.id.peerId) as? CachedChannelData)?.associatedHistoryMessageId
            _internal_applyMaxReadIndexInteractively(
                transaction: transaction,
                stateManager: account.stateManager,
                index: index
            )
            transaction.confirmSynchronizedIncomingReadState(index.id.peerId)
            if let associatedHistoryMessageId = associatedHistoryMessageId,
               associatedHistoryMessageId.peerId != index.id.peerId {
                transaction.confirmSynchronizedIncomingReadState(associatedHistoryMessageId.peerId)
            }
        }
    case .forceServer:
        guard index.id.namespace == Namespaces.Message.Cloud,
              (index.id.peerId.namespace == Namespaces.Peer.CloudUser
                || index.id.peerId.namespace == Namespaces.Peer.CloudGroup
                || index.id.peerId.namespace == Namespaces.Peer.CloudChannel) else {
            return .single(())
        }

        return deferred {
            return account.postbox.transaction { transaction -> Void in
                let associatedHistoryMessageId = (transaction.getPeerCachedData(peerId: index.id.peerId) as? CachedChannelData)?.associatedHistoryMessageId
                _internal_applyMaxReadIndexInteractively(
                    transaction: transaction,
                    stateManager: account.stateManager,
                    index: index
                )

                var forcePeerIds = [index.id.peerId]
                if let associatedHistoryMessageId = associatedHistoryMessageId,
                   associatedHistoryMessageId.peerId != index.id.peerId {
                    forcePeerIds.append(associatedHistoryMessageId.peerId)
                }

                for peerId in forcePeerIds {
                    if let combinedPeerReadState = transaction.getCombinedPeerReadState(peerId) {
                        var maxIncomingReadId: MessageId.Id?
                        if let cloudState = combinedPeerReadState.states.first(where: { namespace, _ in
                           return namespace == Namespaces.Message.Cloud
                       })?.1 {
                            switch cloudState {
                            case let .idBased(incomingReadId, _, _, _, _):
                                maxIncomingReadId = incomingReadId
                            case let .indexBased(incomingReadIndex, _, _, _):
                                if incomingReadIndex.id.namespace == Namespaces.Message.Cloud {
                                    maxIncomingReadId = incomingReadIndex.id.id
                                }
                            }
                        }

                        if let maxIncomingReadId = maxIncomingReadId {
                            let forceTokenId = GRVMReadReceiptBypass.shared.register(
                                accountPeerId: account.peerId,
                                peerId: peerId,
                                maxIncomingReadId: maxIncomingReadId,
                                state: combinedPeerReadState
                            )
                            transaction.forceSynchronizeIncomingReadState(
                                peerId,
                                state: combinedPeerReadState,
                                forceTokenId: forceTokenId
                            )
                        }
                    }
                }
            }
        }
    }
}
