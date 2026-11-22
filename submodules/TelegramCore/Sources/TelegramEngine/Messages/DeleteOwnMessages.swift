import Postbox
import SwiftSignalKit

public struct GRVMDeleteOwnMessagesResult: Equatable {
    public let matchedCount: Int
    public let submittedCount: Int
}

private enum GRVMDeleteOwnMessagesScanResult {
    case complete([MessageId])
    case incomplete(GRVMDeleteOwnMessagesResult)
}

func _internal_grvmDeleteOwnMessages(
    account: Account,
    peerId: PeerId,
    threadId: Int64?
) -> Signal<GRVMDeleteOwnMessagesResult, NoError> {
    return account.postbox.transaction { transaction -> Bool in
        let invalidResult = false

        guard peerId != account.peerId else {
            return invalidResult
        }
        guard peerId.namespace == Namespaces.Peer.CloudGroup || peerId.namespace == Namespaces.Peer.CloudChannel else {
            return invalidResult
        }
        guard let peer = transaction.getPeer(peerId) else {
            return invalidResult
        }

        if peer is TelegramGroup {
            guard threadId == nil else {
                return invalidResult
            }
            return true
        }

        guard let channel = peer as? TelegramChannel else {
            return invalidResult
        }
        switch channel.info {
        case .broadcast:
            return invalidResult
        case .group:
            if threadId != nil {
                guard let topicChannel = peer as? TelegramChannel else {
                    return invalidResult
                }
                guard topicChannel.isForumOrMonoForum else {
                    return invalidResult
                }
            }
            return true
        }
    }
    |> mapToSignal { isValid -> Signal<GRVMDeleteOwnMessagesResult, NoError> in
        guard isValid else {
            return .single(GRVMDeleteOwnMessagesResult(matchedCount: 0, submittedCount: 0))
        }

        let engine = TelegramEngine(account: account)

        func scan(
            state: SearchMessagesState?,
            previousCount: Int,
            collectedIds: [MessageId],
            collected: Set<MessageId>
        ) -> Signal<GRVMDeleteOwnMessagesScanResult, NoError> {
            return engine.messages.searchMessages(
                location: .peer(
                    peerId: peerId,
                    fromId: account.peerId,
                    tags: nil,
                    reactions: nil,
                    threadId: threadId,
                    minDate: nil,
                    maxDate: nil
                ),
                query: "",
                state: state,
                centerId: nil,
                limit: 100
            )
            |> mapToSignal { result, nextState -> Signal<GRVMDeleteOwnMessagesScanResult, NoError> in
                var nextCollected = collected
                var nextIds = collectedIds

                for message in result.messages {
                    if message.id.namespace == Namespaces.Message.Cloud && message.author?.id == account.peerId && (threadId == nil || message.threadId == threadId) && !nextCollected.contains(message.id) {
                        nextCollected.insert(message.id)
                        nextIds.append(message.id)
                    }
                }

                if result.completed {
                    return .single(.complete(nextIds))
                }

                let stateDidNotAdvance = state.map { $0 == nextState } ?? false
                let countDidNotAdvance = nextIds.count == previousCount
                if stateDidNotAdvance || countDidNotAdvance {
                    return .single(.incomplete(GRVMDeleteOwnMessagesResult(matchedCount: nextIds.count, submittedCount: 0)))
                }

                return scan(
                    state: nextState,
                    previousCount: nextIds.count,
                    collectedIds: nextIds,
                    collected: nextCollected
                )
            }
        }

        func submitBatches(_ messageIds: [MessageId]) -> Signal<Void, NoError> {
            guard !messageIds.isEmpty else {
                return .complete()
            }

            let batch = Array(messageIds.prefix(100))
            let remainingMessageIds = Array(messageIds.dropFirst(batch.count))
            let batchEngine = engine
            return batchEngine.messages.deleteMessagesInteractively(
                messageIds: batch,
                type: .forEveryone
            )
            |> then(deferred {
                return submitBatches(remainingMessageIds)
            })
        }

        return scan(
            state: nil,
            previousCount: 0,
            collectedIds: [],
            collected: Set<MessageId>()
        )
        |> mapToSignal { scanResult -> Signal<GRVMDeleteOwnMessagesResult, NoError> in
            switch scanResult {
            case let .incomplete(result):
                return .single(result)
            case let .complete(messageIds):
                let matchedCount = messageIds.count
                guard !messageIds.isEmpty else {
                    return .single(GRVMDeleteOwnMessagesResult(matchedCount: matchedCount, submittedCount: 0))
                }

                return submitBatches(messageIds)
                |> reduceLeft(value: Void(), f: { _, _ in
                    return Void()
                })
                |> map { _ in
                    return GRVMDeleteOwnMessagesResult(matchedCount: matchedCount, submittedCount: messageIds.count)
                }
            }
        }
    }
}
