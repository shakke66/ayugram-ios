import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TELEGRAM_UI = ROOT / "submodules/TelegramUI"
TIMESTAMP = (
    TELEGRAM_UI
    / "Components/Chat/ChatMessageDateAndStatusNode/Sources/StringForMessageTimestampStatus.swift"
)
BUBBLE = (
    TELEGRAM_UI
    / "Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift"
)
CONTEXT_EXTRACTION = (
    TELEGRAM_UI
    / "Components/ContextControllerImpl/Sources/ContextControllerExtractedPresentationNode.swift"
)
HOOKS = ROOT / "submodules/TelegramCore/Sources/AyuGramHooks.swift"
MANAGER = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
FEATURES = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatures.swift"
HISTORY_CONTROLLER = (
    ROOT / "submodules/AyuGramSettingsUI/Sources/GRVMMessageHistoryController.swift"
)
DELETED_CONTROLLER = (
    ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift"
)
EDITED_CONTROLLER = (
    ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramEditedMessagesController.swift"
)
CONTEXT_MENU = TELEGRAM_UI / "Sources/ChatInterfaceStateContextMenus.swift"
CHAT_CONTROLLER = TELEGRAM_UI / "Sources/ChatController.swift"
BOT_FORUM_MENU = TELEGRAM_UI / "Sources/Chat/ChatControllerOpenPeer.swift"
SAVED_MESSAGES_MENU = (
    TELEGRAM_UI
    / "Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoScreen.swift"
)
CHAT_LIST_MENU = ROOT / "submodules/ChatListUI/Sources/ChatListController.swift"
LEGACY_DB = ROOT / "submodules/AyuGramLib/Sources/AyuDeletedMessagesDB.swift"
ARCHIVE_MENU_ITEMS = (
    ROOT / "submodules/AyuGramSettingsUI/Sources/GRVMArchiveContextMenuItems.swift"
)
TELEGRAM_UI_BUILD = TELEGRAM_UI / "BUILD"
SETTINGS_UI_BUILD = ROOT / "submodules/AyuGramSettingsUI/BUILD"


def window(value: str, anchor: str, size: int) -> str:
    offset = value.index(anchor)
    return value[offset : offset + size]


class HistoryUIContractTests(unittest.TestCase):
    def test_timestamp_reads_persistent_attributes_and_keeps_configurable_marks(self) -> None:
        value = TIMESTAMP.read_text(encoding="utf-8")

        self.assertIn("$0 is GRVMDeletedMessageAttribute", value)
        self.assertIn("$0 is GRVMEditHistoryMessageAttribute", value)
        self.assertIn(
            "AyuGramHooks.chatAppearance(accountPeerId: accountPeerId).chats", value
        )
        self.assertIn("chats.deletedMessageMark", value)
        self.assertIn("chats.editedMessageMark", value)
        self.assertIn('chats.replaceMarksWithIcons ? "\\u{1F5D1}"', value)
        self.assertIn(
            'chats.replaceMarksWithIcons ? "\\u{270F}\\u{FE0F}"', value
        )
        self.assertNotIn("isMessageDeletedCheck", value)
        self.assertNotIn("hasEditHistoryCheck", value)

    def test_layout_components_never_query_the_archive_database(self) -> None:
        offenders = []
        components = TELEGRAM_UI / "Components"
        for path in components.rglob("*.swift"):
            value = path.read_text(encoding="utf-8")
            if any(
                token in value
                for token in (
                    "AyuDeletedMessagesDB",
                    "isMessageDeletedCheck",
                    "hasEditHistoryCheck",
                )
            ):
                offenders.append(str(path.relative_to(ROOT)))

        self.assertEqual([], offenders)

    def test_obsolete_synchronous_layout_hooks_are_removed(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        manager = MANAGER.read_text(encoding="utf-8")

        self.assertNotIn("isMessageDeletedCheck", hooks)
        self.assertNotIn("hasEditHistoryCheck", hooks)
        self.assertNotIn("isMessageDeletedCheck", manager)
        self.assertNotIn("hasEditHistoryCheck", manager)

    def test_deleted_bubble_opacity_is_attribute_driven_and_guarded(self) -> None:
        value = BUBBLE.read_text(encoding="utf-8")
        anchor = "private func grvmDeletedMessageContentAlpha("
        self.assertIn(anchor, value)
        helper = window(value, anchor, 4500)

        for token in (
            "GRVMDeletedMessageAttribute",
            "AyuGramHooks.chatAppearance(accountPeerId: item.context.account.peerId).chats",
            "semiTransparentDeletedMessages",
            "selectionState == nil",
            "isRecentActions",
            "case let .message",
            "item.chatLocation",
            ".messageOptions",
            ".customChatContents",
            "0.7",
        ):
            with self.subTest(token=token):
                self.assertIn(token, helper)
        self.assertNotIn("isContextPreview", helper)

    def test_deleted_alpha_uses_extracting_parent_and_refreshes_for_selection(self) -> None:
        value = BUBBLE.read_text(encoding="utf-8")

        self.assertIn("self.mainContextSourceNode.alpha = grvmDeletedMessageContentAlpha(", value)
        self.assertNotIn("self.mainContextSourceNode.contentNode.alpha =", value)

        apply_section = window(value, "strongSelf.appliedItem = item", 900)
        self.assertIn("updateGRVMDeletedMessageContentAlpha", apply_section)

        main_preview = window(
            value,
            "self.mainContextSourceNode.willUpdateIsExtractedToContextPreview",
            1800,
        )
        self.assertNotIn("updateGRVMDeletedMessageContentAlpha", main_preview)

        grouped_preview = window(
            value,
            "contextSourceNode.willUpdateIsExtractedToContextPreview",
            1800,
        )
        self.assertNotIn("updateGRVMDeletedMessageContentAlpha", grouped_preview)

        selection = window(value, "override public func updateSelectionState", 9000)
        self.assertIn("updateGRVMDeletedMessageContentAlpha", selection)

    def test_context_preview_extracts_content_from_the_dimmed_parent(self) -> None:
        value = CONTEXT_EXTRACTION.read_text(encoding="utf-8")
        section = window(value, "func takeContainingNode()", 1000)
        self.assertIn("addSubnode(containingNode.contentNode)", section)

    def test_shared_timestamp_path_covers_bubble_and_standalone_media_nodes(self) -> None:
        call_sites = []
        chat_components = TELEGRAM_UI / "Components/Chat"
        for path in chat_components.rglob("*.swift"):
            if path == TIMESTAMP:
                continue
            if "stringForMessageTimestampStatus(" in path.read_text(encoding="utf-8"):
                call_sites.append(path.name)

        self.assertGreaterEqual(len(call_sites), 10)
        self.assertTrue(any("Sticker" in name for name in call_sites))
        self.assertTrue(any("File" in name for name in call_sites))

    def test_per_message_history_loads_exact_revisions_and_current_message(self) -> None:
        self.assertTrue(HISTORY_CONTROLLER.exists(), "per-message History controller is missing")
        value = HISTORY_CONTROLLER.read_text(encoding="utf-8")

        for token in (
            "public func grvmMessageHistoryController(",
            "messageId: MessageId",
            "AyuGramFeatures.editHistory?(context.account.peerId, messageId)",
            "context.account.postbox.transaction",
            "transaction.getMessage(messageId)",
            "sorted",
            "versions.append",
            "revision.editableContent",
            "GRVMEditableMessageContent(message: currentMessage)",
            "content.text",
            "content.textEntities",
            "content.media",
            "stringWithAppliedEntities(",
            'case .todo:',
            "strings[.historyMediaTodo]",
            "legacyMediaSummary",
            "legacyResourceIds",
            "ChatList_Search_NoResults",
        ):
            with self.subTest(token=token):
                self.assertIn(token, value)
        revision_mapping = window(value, ".map { revision in", 1600)
        self.assertNotIn("text: revision.text", revision_mapping)
        self.assertNotIn("entitiesData: revision.entitiesData", revision_mapping)
        current_mapping = window(value, "if let currentMessage", 1200)
        self.assertNotIn("text: currentMessage.text", current_mapping)

    def test_history_action_is_exact_and_visible_only_for_one_saved_message(self) -> None:
        value = CONTEXT_MENU.read_text(encoding="utf-8")

        for token in (
            "messages.count == 1",
            "$0 is GRVMEditHistoryMessageAttribute",
            "AyuGramHooks.hasEditHistory?(context.account.peerId, message.id) == true",
            "grvmMessageHistoryController(context: context, messageId: message.id)",
            'UIImage(bundleImageName: "Chat/Context Menu/History")',
        ):
            with self.subTest(token=token):
                self.assertIn(token, value)

    def test_archive_ui_bridge_is_account_scoped(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        manager = MANAGER.read_text(encoding="utf-8")
        self.assertTrue(FEATURES.exists(), "async archive UI bridge is missing")
        features = FEATURES.read_text(encoding="utf-8")

        self.assertIn(
            "public static var hasEditHistory: ((PeerId, MessageId) -> Bool)?",
            hooks,
        )
        for token in ("deletedMessages", "clearDeleted", "editHistory"):
            with self.subTest(token=token):
                self.assertIn("public static var " + token, features)
        self.assertGreaterEqual(manager.count("registry.service(accountPeerId: accountPeerId)"), 6)
        self.assertIn("Signal<[MessageId], GRVMClearDeletedError>", features)
        clear_bridge = window(manager, "AyuGramFeatures.clearDeleted =", 700)
        self.assertIn(".fail(.archiveUnavailable)", clear_bridge)

    def test_deleted_archive_uses_exact_scope_search_and_message_actions(self) -> None:
        value = DELETED_CONTROLLER.read_text(encoding="utf-8")

        for token in (
            "public func grvmDeletedMessagesController(",
            "peerId: PeerId? = nil",
            "threadId: Int64? = nil",
            "context.account.peerId",
            "AyuGramFeatures.deletedMessages?(",
            "peerId, threadId, query",
            "ItemListSingleLineInputItem",
            "textUpdated:",
            "arguments.openMessage(message.key)",
            "subject: .message(id: .id(messageId)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, value)
        message_item = window(value, "case let .message(_, _, message):", 2500)
        self.assertNotIn("action: {}", message_item)
        self.assertIn("arguments.openMessage(message.key)", message_item)

    def test_deleted_archive_navigation_is_late_bound_and_thread_aware(self) -> None:
        value = DELETED_CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("openMessage: (GRVMMessageKey) -> Void", value)
        self.assertIn("arguments.openMessage(message.key)", value)
        self.assertIn("let controllerHolder = GRVMDeletedControllerHolder()", value)
        self.assertIn("controllerHolder.controller = controller", value)

        navigation_start = value.index("openMessage: { key in")
        navigation = value[
            navigation_start : value.index("\n    )\n\n    let signal", navigation_start)
        ]
        self.assertNotIn("[weak controller]", navigation)
        self.assertIn("key.threadId != 0", navigation)
        self.assertIn("peerIsForumOrMonoForum", navigation)
        self.assertIn("let chatLocation: NavigateToChatControllerParams.Location", navigation)
        self.assertIn("chatLocation = .replyThread(ChatReplyThreadMessage(", navigation)
        self.assertIn("peerId: peerId", navigation)
        self.assertIn("threadId: key.threadId", navigation)
        self.assertIn("isForumPost: true", navigation)
        self.assertIn("isMonoforumPost: peerIsMonoforum", navigation)
        self.assertIn("chatLocation = .peer(peer)", navigation)
        self.assertIn("controllerHolder.controller?.navigationController", navigation)

        def location(*, thread_id: int, is_forum: bool) -> str:
            return "replyThread" if thread_id != 0 and is_forum else "peer"

        self.assertEqual("replyThread", location(thread_id=42, is_forum=True))
        self.assertEqual("peer", location(thread_id=0, is_forum=True))
        self.assertEqual("peer", location(thread_id=42, is_forum=False))

    def test_clear_deleted_confirms_waits_for_cleanup_and_refreshes_after_emission(self) -> None:
        value = DELETED_CONTROLLER.read_text(encoding="utf-8")

        for token in (
            "standardTextAlertController(",
            "AyuGramFeatures.clearDeleted?(",
            "context.account.peerId",
            "peerId, threadId",
            ".start(next:",
            "error: { error in",
            "grvmClearDeletedErrorController(error, presentationData: presentationData)",
            "refreshToken.set",
        ):
            with self.subTest(token=token):
                self.assertIn(token, value)

        cleanup = window(value, "let cleanup = AyuGramFeatures.clearDeleted?(", 1800)
        self.assertLess(cleanup.index("refreshToken.set"), cleanup.index("error: { error in"))
        error_handler = cleanup[cleanup.index("error: { error in") :]
        self.assertNotIn("refreshToken.set", error_handler)
        self.assertNotIn("completed:", cleanup)

    def test_clear_deleted_failure_copy_is_centralized_and_visible_in_both_actions(self) -> None:
        deleted = DELETED_CONTROLLER.read_text(encoding="utf-8")
        menu = ARCHIVE_MENU_ITEMS.read_text(encoding="utf-8")

        helper = window(deleted, "func grvmClearDeletedErrorController(", 2200)
        for token in (
            "case .archiveUnavailable:",
            "case let .mediaRemovalFailed(count):",
            "case .databaseFinalizationFailed:",
            "standardTextAlertController(",
        ):
            with self.subTest(token=token):
                self.assertIn(token, helper)

        for value in (deleted, menu):
            cleanup = window(value, "let cleanup = AyuGramFeatures.clearDeleted?(", 1800)
            self.assertIn(".fail(.archiveUnavailable)", cleanup)
            self.assertIn(".start(next:", cleanup)
            self.assertIn("error: { error in", cleanup)
            self.assertIn(
                "grvmClearDeletedErrorController(error, presentationData: presentationData)",
                cleanup,
            )
            self.assertIn("in: .window(.root)", cleanup)
            self.assertNotIn("completed:", cleanup)

        menu_cleanup = window(menu, "let cleanup = AyuGramFeatures.clearDeleted?(", 1800)
        self.assertNotIn("refreshToken.set", menu_cleanup)

    def test_clear_deleted_ui_callbacks_are_delivered_on_main_queue(self) -> None:
        for value in (
            DELETED_CONTROLLER.read_text(encoding="utf-8"),
            ARCHIVE_MENU_ITEMS.read_text(encoding="utf-8"),
        ):
            cleanup = window(value, "let cleanup = AyuGramFeatures.clearDeleted?(", 1800)
            self.assertIn("|> deliverOnMainQueue", cleanup)
            self.assertLess(cleanup.index("|> deliverOnMainQueue"), cleanup.index(".start(next:"))

    def test_regular_and_reply_archive_menu_paths_keep_exact_scopes(self) -> None:
        value = CHAT_CONTROLLER.read_text(encoding="utf-8")
        regular = window(value, "case .peer:", 5000)
        reply = window(value, "case let .replyThread(message):", 26000)

        for token in (
            "grvmArchiveContextMenuItems(",
            "context: context",
            "sourceController: strongSelf",
            "peerId: peer.id",
            "threadId: nil",
        ):
            with self.subTest(route="regular", token=token):
                self.assertIn(token, regular)

        self.assertIn("let threadId = message.threadId", reply)
        nil_thread_data = window(reply, "guard let threadData = threadData else {", 700)
        self.assertNotIn("return []", nil_thread_data)
        for token in (
            "return grvmArchiveContextMenuItems(",
            "context: context",
            "sourceController: strongSelf",
            "peerId: peer.id",
            "threadId: threadId",
        ):
            with self.subTest(route="reply_nil_thread_data", token=token):
                self.assertIn(token, nil_thread_data)

        final_reply_append = reply.rindex("items.append(contentsOf: grvmArchiveContextMenuItems(")
        final_reply = reply[final_reply_append : final_reply_append + 500]
        self.assertIn("peerId: peer.id", final_reply)
        self.assertIn("threadId: threadId", final_reply)

    def test_bot_forum_archive_menu_uses_chat_location_scope(self) -> None:
        value = BOT_FORUM_MENU.read_text(encoding="utf-8")
        section = window(value, "items.append(contentsOf: grvmArchiveContextMenuItems(", 500)

        for token in (
            "context: self.context",
            "sourceController: self",
            "peerId: peerId",
            "threadId: self.chatLocation.threadId",
        ):
            with self.subTest(token=token):
                self.assertIn(token, section)

    def test_forum_root_archive_menu_uses_peer_without_thread(self) -> None:
        value = CHAT_LIST_MENU.read_text(encoding="utf-8")
        section = window(value, "items.append(contentsOf: grvmArchiveContextMenuItems(", 500)

        for token in (
            "context: context",
            "sourceController: sourceController",
            "peerId: peerId",
            "threadId: nil",
        ):
            with self.subTest(token=token):
                self.assertIn(token, section)

    def test_saved_messages_archive_menu_uses_own_peer_scope(self) -> None:
        value = SAVED_MESSAGES_MENU.read_text(encoding="utf-8")
        section = window(value, "items.append(contentsOf: grvmArchiveContextMenuItems(", 500)

        for token in (
            "context: context",
            "sourceController: sourceController",
            "peerId: context.account.peerId",
            "threadId: nil",
        ):
            with self.subTest(token=token):
                self.assertIn(token, section)

    def test_shared_archive_submenu_forwards_scope_to_view_and_clear(self) -> None:
        value = ARCHIVE_MENU_ITEMS.read_text(encoding="utf-8")

        for token in (
            "text: strings[.chatMenuViewDeleted]",
            "text: strings[.chatMenuClearDeleted]",
            "grvmDeletedMessagesController(",
            "peerId: peerId",
            "threadId: threadId",
            "AyuGramFeatures.clearDeleted?(",
            "context.account.peerId, peerId, threadId",
        ):
            with self.subTest(token=token):
                self.assertIn(token, value)

    def test_legacy_global_history_is_informational_and_database_api_is_retired(self) -> None:
        edited = EDITED_CONTROLLER.read_text(encoding="utf-8")
        legacy = LEGACY_DB.read_text(encoding="utf-8")

        self.assertNotIn("AyuDeletedMessagesDB", edited)
        self.assertIn("strings[.historyInfo]", edited)
        self.assertIn("strings[.historyTitle]", edited)
        self.assertIn("@available(*, deprecated", legacy)
        self.assertIn("public enum AyuDeletedMessagesDB", legacy)
        for token in (
            "getDeletedMessages",
            "getAllDeletedMessages",
            "getEditHistory",
            "getAllEditedMessages",
            "isMessageDeleted",
            "hasEditHistory",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, legacy)

    def test_telegram_ui_owns_the_one_way_settings_ui_dependency(self) -> None:
        telegram_ui = TELEGRAM_UI_BUILD.read_text(encoding="utf-8")
        settings_ui = SETTINGS_UI_BUILD.read_text(encoding="utf-8")

        self.assertIn(
            '"//submodules/AyuGramSettingsUI:AyuGramSettingsUI"',
            telegram_ui,
        )
        self.assertNotIn("//submodules/TelegramUI:TelegramUI", settings_ui)


if __name__ == "__main__":
    unittest.main()
