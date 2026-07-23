import AccountContext
import AyuGramFeatures
import ContextUI
import Display
import Postbox
import SwiftSignalKit
import TelegramPresentationData

/// Builds account- and topic-scoped GRVMgram archive actions for chat menus.
public func grvmArchiveContextMenuItems(
    context: AccountContext,
    sourceController: ViewController,
    peerId: PeerId,
    threadId: Int64?
) -> [ContextMenuItem] {
    let presentationData = context.sharedContext.currentPresentationData.with { $0 }
    let strings = GRVMgramStrings(presentationData.strings)
    return [.action(ContextMenuActionItem(
        text: strings[.chatMenuTitle],
        icon: { _ in nil },
        action: { [weak sourceController] controller, _ in
            let items: [ContextMenuItem] = [
                .action(ContextMenuActionItem(
                    text: presentationData.strings.Common_Back,
                    icon: { _ in nil },
                    iconPosition: .left,
                    action: { controller, _ in
                        controller?.popItems()
                    }
                )),
                .separator,
                .action(ContextMenuActionItem(
                    text: strings[.chatMenuViewDeleted],
                    icon: { _ in nil },
                    action: { [weak sourceController] _, dismiss in
                        dismiss(.default)
                        sourceController?.push(grvmDeletedMessagesController(
                            context: context,
                            peerId: peerId,
                            threadId: threadId
                        ))
                    }
                )),
                .action(ContextMenuActionItem(
                    text: strings[.chatMenuClearDeleted],
                    textColor: .destructive,
                    icon: { _ in nil },
                    action: { [weak sourceController] _, dismiss in
                        dismiss(.default)
                        let alert = standardTextAlertController(
                            theme: AlertControllerTheme(presentationData: presentationData),
                            title: strings[.deletedClearTitle],
                            text: strings[.deletedClearText],
                            actions: [
                                TextAlertAction(
                                    type: .genericAction,
                                    title: presentationData.strings.Common_Cancel,
                                    action: {}
                                ),
                                TextAlertAction(type: .destructiveAction, title: strings[.deletedClearAction], action: {
                                    let cleanup = AyuGramFeatures.clearDeleted?(
                                        context.account.peerId, peerId, threadId
                                    ) ?? .fail(.archiveUnavailable)
                                    let _ = (cleanup
                                    |> deliverOnMainQueue).start(next: { _ in }, error: { error in
                                        sourceController?.present(
                                            grvmClearDeletedErrorController(error, presentationData: presentationData),
                                            in: .window(.root)
                                        )
                                    })
                                })
                            ]
                        )
                        sourceController?.present(alert, in: .window(.root))
                    }
                ))
            ]
            controller?.pushItems(items: .single(ContextController.Items(content: .list(items))))
        }
    ))]
}
