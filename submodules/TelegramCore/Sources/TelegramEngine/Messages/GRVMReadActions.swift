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
                    if let currentReadState = transaction.getCombinedPeerReadState(peerId) {
                        // В гост-режиме чат локально прочитан до конца, а собеседнику уходит прочтение ровно
                        // до выбранного сообщения (как AyuGram Desktop, messages.readHistory(max_id)).
                        let combinedPeerReadState = peerId == index.id.peerId
                            ? grvmReadState(currentReadState, readUpTo: index.id.id)
                            : currentReadState
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

/// Состояние прочтения для отправки на сервер: отметка входящих — не дальше `readUpTo`. Число непрочитанных
/// остаётся локальным: по нему проверка после отправки понимает, что состояние не менялось.
private func grvmReadState(_ state: CombinedPeerReadState, readUpTo: MessageId.Id) -> CombinedPeerReadState {
    return CombinedPeerReadState(states: state.states.map { namespace, readState -> (MessageId.Namespace, PeerReadState) in
        guard namespace == Namespaces.Message.Cloud,
              case let .idBased(maxIncomingReadId, maxOutgoingReadId, maxKnownId, count, markedUnread) = readState else {
            return (namespace, readState)
        }
        return (namespace, .idBased(
            maxIncomingReadId: min(maxIncomingReadId, readUpTo),
            maxOutgoingReadId: maxOutgoingReadId,
            maxKnownId: maxKnownId,
            count: count,
            markedUnread: markedUnread
        ))
    })
}

/// «Прочитать сообщение» в гост-режиме, как AyuGram Desktop (`AddReadUntilAction`): у голосового или кружка
/// без самоуничтожения собеседнику уходит и «прослушано» — даже если локально оно уже прослушано в гост-режиме.
func _internal_grvmForceReadMessageContents(account: Account, messageId: MessageId) -> Signal<Void, NoError> {
    let accountPeerId = account.peerId
    let postbox = account.postbox
    return postbox.transaction { transaction -> Bool in
        guard messageId.namespace == Namespaces.Message.Cloud,
              messageId.peerId.namespace != Namespaces.Peer.SecretChat,
              let message = transaction.getMessage(messageId),
              message.flags.contains(.Incoming),
              !message.attributes.contains(where: { $0 is AutoremoveTimeoutMessageAttribute }) else {
            return false
        }
        guard let attribute = message.attributes.first(where: { $0 is ConsumableContentMessageAttribute }) as? ConsumableContentMessageAttribute else {
            return false
        }
        if attribute.consumed {
            addSynchronizeConsumeMessageContentsOperation(transaction: transaction, messageIds: [messageId], force: true)
            return false
        }
        return true
    }
    |> mapToSignal { markInteractively -> Signal<Void, NoError> in
        guard markInteractively else {
            return .single(())
        }
        return _internal_markMessageContentAsConsumedInteractively(accountPeerId: accountPeerId, postbox: postbox, messageId: messageId, force: true)
    }
}

/// GRVMgram: a forum topic or monoforum read from the chat list (swipe, "Mark as Read", reading a folder) sends
/// `readDiscussion` / `readSavedHistory` directly, outside the read-state synchronization the read-receipt
/// suppression hooks into. With read receipts suppressed it stays local (as AyuGram Desktop).
func grvmAllowsServerThreadRead(viewTracker: AccountViewTracker) -> Bool {
    guard let accountPeerId = viewTracker.account?.peerId else {
        return true
    }
    return AyuGramHooks.shouldSuppressReadReceipts?(accountPeerId) != true
}
