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
    peerId: PeerId?,
    threadId: Int64?
) -> [ContextMenuItem] {
    return [.action(ContextMenuActionItem(
        text: "GRVMgram Archives",
        icon: { _ in nil },
        action: { [weak sourceController] controller, _ in
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
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
                    text: "View Deleted",
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
                    text: "Clear Deleted",
                    textColor: .destructive,
                    icon: { _ in nil },
                    action: { [weak sourceController] _, dismiss in
                        dismiss(.default)
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
                                    ) ?? .single([])
                                    let _ = cleanup.start(next: { _ in })
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
