import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def window(text: str, marker: str, size: int = 12000) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    return text[start : start + size]


class FilterRuntimeSurfacesContractTests(unittest.TestCase):
    def test_filter_revision_hook_is_account_scoped(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        self.assertIn(
            "public static var messageFilterStateUpdates: ((PeerId) -> Signal<Int64, NoError>)?",
            hooks,
        )

    def test_history_reacts_to_filter_revision_without_changing_full_message_predicate(self) -> None:
        history = source("submodules/TelegramUI/Sources/ChatHistoryListNode.swift")
        self.assertIn(
            "AyuGramHooks.messageFilterStateUpdates?(context.account.peerId)",
            history,
        )
        self.assertIn("historyViewUpdate = combineLatest(", history)
        entries = source("submodules/TelegramUI/Sources/ChatHistoryEntriesForView.swift")
        self.assertIn(
            "AyuGramHooks.isMessageHiddenByFilter?(context.account.peerId, message)",
            entries,
        )
        self.assertNotIn("message.text", window(entries, "isMessageHiddenByFilter?(", 1000))

    def test_chat_list_reacts_and_filters_preview_messages_by_full_message(self) -> None:
        node = source("submodules/ChatListUI/Sources/Node/ChatListNode.swift")
        self.assertIn(
            "AyuGramHooks.messageFilterStateUpdates?(context.account.peerId)",
            node,
        )
        self.assertIn(
            "AyuGramHooks.filteredUnreadStateUpdates?(context.account.peerId)",
            node,
        )
        self.assertIn("chatListViewUpdate = combineLatest(", node)

        entries = source("submodules/ChatListUI/Sources/Node/ChatListNodeEntries.swift")
        self.assertIn(
            "AyuGramHooks.isMessageHiddenByFilter?(accountPeerId, $0._asMessage()) != true",
            entries,
        )
        self.assertIn("let visibleTopMessage = groupReference.topMessage", entries)
        self.assertIn(
            "AyuGramHooks.isMessageHiddenByFilter?(accountPeerId, message._asMessage())",
            entries,
        )
        peer_entry = window(entries, "let entry: ChatListNodeEntry = .PeerEntry(", 3000)
        self.assertIn("messages: updatedMessages", peer_entry)

    def test_in_app_notifications_drop_hidden_message_groups_before_enqueue(self) -> None:
        application = source("submodules/TelegramUI/Sources/ApplicationContext.swift")
        notification_window = window(
            application,
            "context.account.stateManager.notificationMessages",
            7000,
        )
        self.assertIn(
            "AyuGramHooks.isMessageHiddenByFilter?(context.account.peerId, message)",
            notification_window,
        )
        self.assertIn("compactMap", notification_window)
        self.assertIn("visibleMessages.isEmpty", notification_window)
        self.assertIn("return (visibleMessages, item.1, item.2, item.3)", notification_window)
        self.assertIn("let (messages, _, notify, threadData) = messageList.last", notification_window)

    def test_unread_contract_does_not_subtract_only_chat_list_top_messages(self) -> None:
        # The aggregate unread boundary is intentionally coordinator-owned. This
        # guard keeps Stream B from shipping a mathematically incorrect UI-only
        # subtraction while the lower Postbox seam is assigned.
        node_entries = source("submodules/ChatListUI/Sources/Node/ChatListNodeEntries.swift")
        self.assertNotIn("readState.count -", node_entries)
        self.assertNotIn("combinedReadState.count -", node_entries)


if __name__ == "__main__":
    unittest.main()
