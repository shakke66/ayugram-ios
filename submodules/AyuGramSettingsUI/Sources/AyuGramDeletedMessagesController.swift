import Foundation
import UIKit
import AccountContext
import AyuGramFeatures
import AyuGramLib
import Display
import ItemListUI
import Postbox
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import TelegramUIPreferences

private struct GRVMDeletedArguments {
    let context: AccountContext
    let updateQuery: (String) -> Void
    let openMessage: (MessageId) -> Void
}

private enum GRVMDeletedSection: Int32 {
    case search
    case messages
}

private enum GRVMDeletedEntry: ItemListNodeEntry {
    case search(PresentationTheme, String)
    case empty(PresentationTheme)
    case message(Int32, PresentationTheme, GRVMArchivedMessage)

    var section: ItemListSectionId {
        switch self {
        case .search:
            return GRVMDeletedSection.search.rawValue
        case .empty, .message:
            return GRVMDeletedSection.messages.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .search:
            return 0
        case .empty:
            return 1
        case let .message(index, _, _):
            return 100 + index
        }
    }

    static func ==(lhs: GRVMDeletedEntry, rhs: GRVMDeletedEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.search(_, lhsQuery), .search(_, rhsQuery)):
            return lhsQuery == rhsQuery
        case (.empty, .empty):
            return true
        case let (.message(lhsIndex, _, lhsMessage), .message(rhsIndex, _, rhsMessage)):
            return lhsIndex == rhsIndex && lhsMessage == rhsMessage
        default:
            return false
        }
    }

    static func <(lhs: GRVMDeletedEntry, rhs: GRVMDeletedEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! GRVMDeletedArguments
        switch self {
        case let .search(_, query):
            return ItemListSingleLineInputItem(
                context: arguments.context,
                presentationData: presentationData,
                title: NSAttributedString(),
                text: query,
                placeholder: presentationData.strings.Common_Search,
                type: .regular(capitalization: false, autocorrection: false),
                clearType: .always,
                sectionId: self.section,
                textUpdated: { value in
                    arguments.updateQuery(value)
                },
                action: {
                    arguments.updateQuery(query)
                },
                cleared: {
                    arguments.updateQuery("")
                }
            )
        case .empty:
            return ItemListTextItem(
                presentationData: presentationData,
                text: .plain(presentationData.strings.ChatList_Search_NoResults),
                sectionId: self.section
            )
        case let .message(_, _, message):
            let messageId = MessageId(
                peerId: PeerId(message.key.peerId),
                namespace: message.key.namespace,
                id: message.key.messageId
            )
            var body = message.text
            if body.isEmpty {
                body = message.mediaSummary.isEmpty ? "[empty]" : "[\(message.mediaSummary)]"
            } else if !message.mediaSummary.isEmpty {
                body = "[\(message.mediaSummary)] \(body)"
            }
            let author = [message.senderName, message.peerTitle]
                .filter { !$0.isEmpty }
                .joined(separator: " - ")
            if !author.isEmpty {
                body = "\(author): \(body)"
            }
            if !message.resourceIds.isEmpty {
                body += " [\(message.resourceIds.count) archived resources]"
            }
            let formatter = DateFormatter()
            formatter.dateStyle = .short
            formatter.timeStyle = .short
            return ItemListDisclosureItem(
                presentationData: presentationData,
                icon: nil,
                title: body,
                label: formatter.string(from: Date(timeIntervalSince1970: TimeInterval(message.deletedAt))),
                sectionId: self.section,
                style: .blocks,
                action: {
                    arguments.openMessage(messageId)
                }
            )
        }
    }
}

private func grvmDeletedEntries(
    messages: [GRVMArchivedMessage],
    query: String,
    presentationData: PresentationData
) -> [GRVMDeletedEntry] {
    var entries: [GRVMDeletedEntry] = [.search(presentationData.theme, query)]
    if messages.isEmpty {
        entries.append(.empty(presentationData.theme))
    } else {
        entries.append(contentsOf: messages.enumerated().map { index, message in
            .message(Int32(index), presentationData.theme, message)
        })
    }
    return entries
}

func grvmClearDeletedErrorController(
    _ error: GRVMClearDeletedError,
    presentationData: PresentationData
) -> AlertController {
    let text: String
    switch error {
    case .archiveUnavailable:
        text = "The deleted-message archive is unavailable. Please try again."
    case let .mediaRemovalFailed(count):
        text = "Failed to remove \(count) archived media file(s). The cleanup can be retried."
    case .databaseFinalizationFailed:
        text = "The deleted-message archive could not be finalized. Please try again."
    }
    return standardTextAlertController(
        theme: AlertControllerTheme(presentationData: presentationData),
        title: "Clear Failed",
        text: text,
        actions: [
            TextAlertAction(
                type: .defaultAction,
                title: presentationData.strings.Common_OK,
                action: {}
            )
        ]
    )
}

/// Displays the active account's deleted-message archive for one chat or topic scope.
public func grvmDeletedMessagesController(
    context: AccountContext,
    peerId: PeerId? = nil,
    threadId: Int64? = nil
) -> ViewController {
    let queryPromise = ValuePromise<String>("", ignoreRepeated: true)
    let refreshCounter = Atomic<Int>(value: 0)
    let refreshToken = ValuePromise<Int>(0, ignoreRepeated: true)
    let messages = combineLatest(queryPromise.get(), refreshToken.get())
    |> mapToSignal { queryText, _ -> Signal<(String, [GRVMArchivedMessage]), NoError> in
        let normalized = queryText.trimmingCharacters(in: .whitespacesAndNewlines)
        let query: String? = normalized.isEmpty ? nil : normalized
        let result = AyuGramFeatures.deletedMessages?(
            context.account.peerId, peerId, threadId, query
        ) ?? .single([])
        return result |> map { (queryText, $0) }
    }

    var controller: ItemListController?
    let arguments = GRVMDeletedArguments(
        context: context,
        updateQuery: { value in
            queryPromise.set(value)
        },
        openMessage: { [weak controller] messageId in
            let _ = (context.engine.data.get(
                TelegramEngine.EngineData.Item.Peer.Peer(id: messageId.peerId)
            )
            |> deliverOnMainQueue).startStandalone(next: { [weak controller] peer in
                guard let peer,
                      let navigationController = controller?.navigationController as? NavigationController else {
                    return
                }
                context.sharedContext.navigateToChatController(NavigateToChatControllerParams(
                    navigationController: navigationController,
                    context: context,
                    chatLocation: .peer(peer),
                    subject: .message(id: .id(messageId), highlight: nil, timecode: nil, setupReply: false)
                ))
            })
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, messages)
    |> map { presentationData, result -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let (query, messages) = result
        let clear = ItemListNavigationButton(
            content: .text("Clear"),
            style: .regular,
            enabled: !messages.isEmpty,
            action: { [weak controller] in
                let alert = standardTextAlertController(
                    theme: AlertControllerTheme(presentationData: presentationData),
                    title: "Clear Deleted",
                    text: "Permanently remove the GRVMgram deleted-message archive for this chat?",
                    actions: [
                        TextAlertAction(
                            type: .genericAction,
                            title: presentationData.strings.Common_Cancel,
                            action: {}
                        ),
                        TextAlertAction(type: .destructiveAction, title: "Clear", action: {
                            let cleanup = AyuGramFeatures.clearDeleted?(
                                context.account.peerId, peerId, threadId
                            ) ?? .fail(.archiveUnavailable)
                            let _ = (cleanup
                            |> deliverOnMainQueue).start(next: { _ in
                                refreshToken.set(refreshCounter.modify { $0 + 1 })
                            }, error: { error in
                                controller?.present(
                                    grvmClearDeletedErrorController(error, presentationData: presentationData),
                                    in: .window(.root)
                                )
                            })
                        })
                    ]
                )
                controller?.present(alert, in: .window(.root))
            }
        )
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text("GRVMgram Deleted Messages"),
            leftNavigationButton: nil,
            rightNavigationButton: clear,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: grvmDeletedEntries(
                messages: messages,
                query: query,
                presentationData: presentationData
            ),
            style: .blocks
        )
        return (controllerState, (listState, arguments))
    }

    controller = ItemListController(context: context, state: signal)
    return controller!
}

@available(*, deprecated, message: "Use grvmDeletedMessagesController(context:peerId:threadId:)")
/// Compatibility entry point for the former global archive screen.
public func ayuGramDeletedMessagesController(context: AccountContext) -> ViewController {
    return grvmDeletedMessagesController(context: context)
}
