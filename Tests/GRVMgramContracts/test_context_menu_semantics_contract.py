from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTEXT_MENU = ROOT / "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
CHAT = ROOT / "submodules/TelegramUI/Sources/ChatController.swift"
OPEN_MENU = (
    ROOT
    / "submodules/TelegramUI/Sources/Chat/ChatControllerOpenMessageContextMenu.swift"
)
CONTEXT_GESTURE = ROOT / "submodules/Display/Source/ContextGesture.swift"
TAP_GESTURE = (
    ROOT / "submodules/Display/Source/TapLongTapOrDoubleTapGestureRecognizer.swift"
)
ENQUEUE = ROOT / "submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift"
DETAILS = ROOT / "submodules/TelegramUI/Sources/GRVMMessageDetailsController.swift"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def swift_block(text: str, signature: str) -> str:
    """Return one brace-balanced Swift declaration, ignoring braces in strings/comments."""
    start = text.find(signature)
    if start < 0:
        return ""
    brace = text.find("{", start)
    if brace < 0:
        return ""

    depth = 0
    index = brace
    quote = False
    line_comment = False
    block_comment = 0
    while index < len(text):
        char = text[index]
        pair = text[index : index + 2]
        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if pair == "/*":
                block_comment += 1
                index += 1
            elif pair == "*/":
                block_comment -= 1
                index += 1
        elif quote:
            if char == "\\":
                index += 1
            elif char == '"':
                quote = False
        elif pair == "//":
            line_comment = True
            index += 1
        elif pair == "/*":
            block_comment = 1
            index += 1
        elif char == '"':
            quote = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
        index += 1
    return ""


class ContextMenuSemanticsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context_menu = read(CONTEXT_MENU)
        cls.chat = read(CHAT)
        cls.open_menu = read(OPEN_MENU)
        cls.context_gesture = read(CONTEXT_GESTURE)
        cls.tap_gesture = read(TAP_GESTURE)
        cls.enqueue = read(ENQUEUE)
        cls.details = read(DETAILS)

    def test_modifier_state_is_captured_reset_and_forwarded(self) -> None:
        for gesture in (self.context_gesture, self.tap_gesture):
            with self.subTest(gesture=gesture[:40]):
                self.assertIn("public private(set) var grvmModifierPressed", gesture)
                began = swift_block(gesture, "override public func touchesBegan(")
                self.assertIn("event.modifierFlags", began)
                self.assertIn(".shift", began)
                self.assertIn(".control", began)
                reset = swift_block(gesture, "override public func reset()")
                self.assertIn("self.grvmModifierPressed = false", reset)

        open_menu = swift_block(self.open_menu, "func openMessageContextMenu(")
        self.assertIn("let modifierPressed", open_menu)
        self.assertIn("recognizer?.grvmModifierPressed", open_menu)
        self.assertIn("gesture?.grvmModifierPressed", open_menu)
        self.assertIn("modifierPressed: modifierPressed", open_menu)

    def test_typed_visibility_routes_hidden_visible_and_modifier_modes(self) -> None:
        route = swift_block(self.context_menu, "func grvmContextMenuPlacement(")
        for token in (
            "GRVMContextMenuVisibility",
            "case .hidden",
            "case .visible",
            "case .visibleWithModifier",
            "modifierPressed",
            ".topLevel",
            ".more",
        ):
            self.assertIn(token, route)

        menu = swift_block(
            self.context_menu, "func contextMenuForChatPresentationInterfaceState("
        )
        self.assertIn("modifierPressed: Bool = false", menu)
        self.assertIn(
            "AyuGramHooks.chatAppearance(accountPeerId: context.account.peerId).contextMenu",
            menu,
        )
        self.assertIn("contextMoreActions", menu)
        self.assertEqual(menu.count('text: "GRVMgram Actions"'), 1)
        self.assertIn("pushItems", menu)
        self.assertIn("popItems", menu)
        self.assertNotIn("func ayuVisible", menu)

    def test_local_hide_is_lifecycle_aware_and_never_uses_stock_delete(self) -> None:
        hide = swift_block(self.context_menu, "func grvmLocalHideMessage(")
        for token in (
            "context.account.postbox.transaction",
            "transaction.getMessage(messageId)",
            "isLocallyDeletedMessage(message.attributes)",
            "_internal_applyMessageDeletion(",
            "mode: .server(.localAction)",
        ):
            self.assertIn(token, hide)
        for forbidden in (
            "deleteMessages(",
            "deleteMessagesInteractively",
            "_internal_deleteMessages",
            "network",
        ):
            self.assertNotIn(forbidden, hide)

        menu = swift_block(
            self.context_menu, "func contextMenuForChatPresentationInterfaceState("
        )
        self.assertIn("!isReplyThreadHead", menu)
        self.assertIn("grvmLocalHideMessage(context: context, messageId: message.id)", menu)

    def test_user_messages_searches_each_deduplicated_author(self) -> None:
        authors = swift_block(self.context_menu, "func grvmMessageAuthors(")
        self.assertIn("message.author", authors)
        self.assertIn("message.forwardInfo?.author", authors)
        self.assertIn("Set<PeerId>", authors)

        menu = swift_block(
            self.context_menu, "func contextMenuForChatPresentationInterfaceState("
        )
        self.assertIn('beginMessageSearch(.member(peer), "")', menu)
        self.assertNotIn("openPeer(peer", menu)

    def test_details_action_opens_real_metadata_controller(self) -> None:
        menu = swift_block(
            self.context_menu, "func contextMenuForChatPresentationInterfaceState("
        )
        self.assertIn("grvmMessageDetailsController(context: context, message: message)", menu)

        for token in (
            "public func grvmMessageDetailsController(",
            "ItemListController(",
            "message.id.peerId",
            "message.id.namespace",
            "message.id.id",
            "message.timestamp",
            "EditedMessageAttribute",
            "message.author",
            "message.forwardInfo",
            "ViewCountMessageAttribute",
            "ForwardCountMessageAttribute",
            "TelegramMediaImage",
            "TelegramMediaFile",
        ):
            self.assertIn(token, self.details)

    def test_repeat_uses_normal_enqueue_and_rejects_unsupported_content(self) -> None:
        repeat = swift_block(self.enqueue, "public func enqueueGRVMRepeatedMessage(")
        for token in (
            "account.postbox.transaction",
            "transaction.getMessage(messageId)",
            "TextEntitiesMessageAttribute",
            "TelegramMediaImage",
            "TelegramMediaFile",
            "message.threadId",
            "enqueueMessages(account: account",
            "return .single(false)",
        ):
            self.assertIn(token, repeat)
        for forbidden in (
            "resendMessages",
            "sendScheduledMessagesNow",
            "_internal_deleteMessages",
            'text: "", attributes: [], inlineStickers: [:], mediaReference: nil',
        ):
            self.assertNotIn(forbidden, repeat)

        menu = swift_block(
            self.context_menu, "func contextMenuForChatPresentationInterfaceState("
        )
        self.assertIn("messages.count == 1", menu)
        self.assertIn("!isCopyProtected", menu)
        self.assertIn("enqueueGRVMRepeatedMessage(account: context.account", menu)
        self.assertIn("displayUndo", menu)

    def test_filter_seed_and_independent_views_reactions_modes_are_preserved(self) -> None:
        filters = swift_block(self.chat, "func grvmMessageFilterContextMenuItems(")
        self.assertIn("initialExpression: message.text", filters)
        self.assertIn("initialPeerId: message.id.peerId", filters)
        for token in ("View Filters", "Show Filtered", "Shadow Ban"):
            self.assertIn(token, self.chat)

        menu = swift_block(
            self.context_menu, "func contextMenuForChatPresentationInterfaceState("
        )
        self.assertIn("contextMenuSettings.views", menu)
        self.assertIn("contextMenuSettings.reactions", menu)
        self.assertIn("canViewStats", menu)
        self.assertIn("reactionCount", menu)

        legacy = self.context_menu + self.open_menu
        for hook in (
            "contextMenuHide",
            "contextMenuUserMessages",
            "contextMenuDetails",
            "contextMenuRepeat",
            "contextMenuAddFilter",
            "contextMenuViewsPanel",
            "contextMenuReactionsPanel",
        ):
            self.assertNotIn(f"AyuGramHooks.{hook}", legacy)

    def test_stock_delete_send_now_and_history_remain_independent(self) -> None:
        menu = swift_block(
            self.context_menu, "func contextMenuForChatPresentationInterfaceState("
        )
        self.assertIn("interfaceInteraction.deleteMessages", menu)
        self.assertIn("controllerInteraction.sendScheduledMessagesNow", menu)
        self.assertIn("grvmMessageHistoryController", menu)

        repeat_action = swift_block(menu, "func grvmRepeatContextMenuItem(")
        self.assertNotIn("sendScheduledMessagesNow", repeat_action)
        self.assertNotIn("resendMessages", repeat_action)


if __name__ == "__main__":
    unittest.main()
