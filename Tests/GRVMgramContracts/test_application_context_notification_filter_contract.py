import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def window(text: str, marker: str, size: int = 8000) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    return text[start : start + size]


class ApplicationContextNotificationFilterContractTests(unittest.TestCase):
    def test_notification_pipeline_keeps_revision_recalculation_out_of_enqueue_path(self) -> None:
        application = source("submodules/TelegramUI/Sources/ApplicationContext.swift")
        notification_window = window(
            application,
            "let engine = context.engine",
        )

        self.assertIn("context.account.stateManager.notificationMessages", notification_window)
        self.assertIn("mapToSignal { messageList ->", notification_window)
        self.assertIn(
            "AyuGramHooks.isMessageHiddenByFilter?(context.account.peerId, message)",
            notification_window,
        )
        self.assertIn("notificationController.enqueue(ChatMessageNotificationItem", notification_window)
        self.assertNotIn("combineLatest(", notification_window)

        revision_window = window(
            application,
            "let messageFilterStateUpdates = AyuGramHooks.messageFilterStateUpdates?",
        )
        self.assertIn("messageFilterStateUpdates", revision_window)
        self.assertIn("notificationController.removeItems", revision_window)
        self.assertIn("item as? ChatMessageNotificationItem", revision_window)
        self.assertIn("notificationItem.messages", revision_window)
        self.assertIn(
            "AyuGramHooks.isMessageHiddenByFilter?(context.account.peerId, message)",
            revision_window,
        )
        self.assertNotIn("notificationController.enqueue(ChatMessageNotificationItem", revision_window)

    def test_notification_revision_fallback_is_local_and_account_scoped(self) -> None:
        application = source("submodules/TelegramUI/Sources/ApplicationContext.swift")
        notification_window = window(
            application,
            "let messageFilterStateUpdates = AyuGramHooks.messageFilterStateUpdates?",
        )

        self.assertIn("context.account.peerId", notification_window)
        self.assertIn("Signal<Int64, NoError>.single(0)", notification_window)
        self.assertNotIn("primaryService", notification_window)


if __name__ == "__main__":
    unittest.main()
