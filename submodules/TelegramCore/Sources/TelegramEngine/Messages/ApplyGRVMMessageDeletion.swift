import Foundation
import Postbox

public enum GRVMDeletionMode {
    case server(GRVMDeletionSource)
    case forceCleanup
}

private func grvmCanArchive(_ message: Message) -> Bool {
    switch message.id.namespace {
    case Namespaces.Message.Cloud, Namespaces.Message.SecretIncoming:
        return true
    case Namespaces.Message.Local:
        return message.flags.intersection([.Unsent, .Failed, .Sending]).isEmpty
    default:
        return false
    }
}

@discardableResult
public func _internal_applyMessageDeletion(
    accountPeerId: PeerId,
    transaction: Transaction,
    mediaBox: MediaBox,
    ids: [MessageId],
    mode: GRVMDeletionMode,
    manualAddMessageThreadStatsDifference: ((MessageThreadKey, Int, Int) -> Void)? = nil
) -> [MessageId] {
    var seen = Set<MessageId>()
    let uniqueIds = ids.filter { seen.insert($0).inserted }

    if case .forceCleanup = mode {
        _internal_deleteMessages(
            transaction: transaction,
            mediaBox: mediaBox,
            ids: uniqueIds,
            manualAddMessageThreadStatsDifference: manualAddMessageThreadStatsDifference
        )
        return []
    }

    let source: GRVMDeletionSource
    if case let .server(value) = mode {
        source = value
    } else {
        preconditionFailure()
    }

    var preservedIds: [MessageId] = []
    var candidates: [Message] = []
    var physicalIds: [MessageId] = []
    for id in uniqueIds {
        guard let message = transaction.getMessage(id) else {
            physicalIds.append(id)
            continue
        }
        if isLocallyDeletedMessage(message.attributes) {
            preservedIds.append(id)
        } else if grvmCanArchive(message) {
            candidates.append(message)
        } else {
            physicalIds.append(id)
        }
    }

    let persisted = AyuGramHooks.preserveDeletedMessages?(accountPeerId, candidates, source) ?? [:]
    let deletedAt = Int32(Date().timeIntervalSince1970)
    for message in candidates {
        guard let resourceIds = persisted[message.id] else {
            physicalIds.append(message.id)
            continue
        }
        let marked = transaction.markMessageAsLocallyDeleted(
            id: message.id,
            attribute: GRVMDeletedMessageAttribute(
                deletedAt: deletedAt,
                source: source,
                topicId: message.threadId,
                resourceIds: resourceIds
            )
        )
        if marked {
            preservedIds.append(message.id)
        } else {
            physicalIds.append(message.id)
        }
    }

    if !physicalIds.isEmpty {
        _internal_deleteMessages(
            transaction: transaction,
            mediaBox: mediaBox,
            ids: physicalIds,
            manualAddMessageThreadStatsDifference: manualAddMessageThreadStatsDifference
        )
    }
    return preservedIds
}
