import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FilteredUnreadChatConsumersContractTests(unittest.TestCase):
    def test_initial_chat_badge_passes_account_scope_to_total_adjustment(self) -> None:
        content_data = source(
            "submodules/TelegramUI/Sources/ChatControllerContentData.swift"
        )
        marker = "let (count, _) = renderedTotalUnreadCount("
        call = content_data[content_data.index(marker) : content_data.index(marker) + 500]
        self.assertIn(
            "accountPeerId: context.account.peerId",
            call,
        )
        self.assertIn(
            "AyuGramHooks.adjustedUnreadPeerReadState?",
            call,
        )
        self.assertIn("peerReadStateData.readState", call)

    def test_navigation_badge_reacts_to_filtered_unread_revisions(self) -> None:
        load_display = source(
            "submodules/TelegramUI/Sources/Chat/ChatControllerLoadDisplayNode.swift"
        )
        self.assertIn(
            "AyuGramHooks.filteredUnreadStateUpdates?(self.context.account.peerId)",
            load_display,
        )
        self.assertIn(
            "TelegramEngine.EngineData.Item.Messages.PeerReadCounters(id: peerId)",
            load_display,
        )
        self.assertIn(
            "AyuGramHooks.adjustedUnreadPeerReadState?(",
            load_display,
        )
        self.assertIn(
            "accountPeerId: strongSelf.context.account.peerId",
            load_display,
        )
        self.assertIn(
            "TelegramEngine.EngineData.Item.Messages.PeerReadCounters(id: peerId)",
            load_display,
        )
        self.assertIn("AyuGramHooks.adjustedUnreadPeerReadState?", load_display)


if __name__ == "__main__":
    unittest.main()
