import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FilteredUnreadPhase2ContractTests(unittest.TestCase):
    def test_hooks_expose_account_scoped_display_only_adjustments(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        self.assertIn(
            "public static var adjustedUnreadPeerReadState: ((PeerId, PeerId, CombinedPeerReadState) -> CombinedPeerReadState)?",
            hooks,
        )
        self.assertIn(
            "public static var adjustedTotalUnreadState: ((PeerId, PeerGroupId, ChatListTotalUnreadState) -> ChatListTotalUnreadState)?",
            hooks,
        )
        self.assertIn(
            "public static var filteredUnreadStateUpdates: ((PeerId) -> Signal<Int64, NoError>)?",
            hooks,
        )

    def test_per_chat_consumer_adjusts_read_state_without_mutating_postbox(self) -> None:
        entries = source("submodules/ChatListUI/Sources/Node/ChatListNodeEntries.swift")
        self.assertIn("AyuGramHooks.adjustedUnreadPeerReadState?", entries)
        self.assertIn("EnginePeerReadCounters(", entries)
        self.assertNotIn("applyIncomingReadMaxId", entries)
        self.assertNotIn("withAllMessages", entries)

    def test_aggregate_consumers_use_adjusted_total_state_and_revision(self) -> None:
        rendered = source("submodules/TelegramUIPreferences/Sources/RenderedTotalUnreadCount.swift")
        tab = source("submodules/ChatListUI/Sources/TabBarChatListFilterController.swift")
        self.assertIn("AyuGramHooks.adjustedTotalUnreadState?", rendered)
        self.assertIn("AyuGramHooks.filteredUnreadStateUpdates?", rendered)
        self.assertIn("AyuGramHooks.adjustedTotalUnreadState?", tab)
        self.assertIn("AyuGramHooks.filteredUnreadStateUpdates?", tab)

    def test_coordinator_is_bounded_read_only_and_revision_safe(self) -> None:
        coordinator = source(
            "submodules/AyuGramFeatures/Sources/GRVMFilteredUnreadCoordinator.swift"
        )
        self.assertIn("public final class GRVMFilteredUnreadCoordinator", coordinator)
        self.assertIn("scanLocalUnreadMessages", coordinator)
        self.assertIn("localUnreadMessagePeerIdsUpdates", coordinator)
        self.assertIn("prefix(256)", coordinator)
        self.assertIn("generation == self.generation", coordinator)
        self.assertIn("token == self.scanTokens[peerId]", coordinator)
        self.assertNotIn("withAllMessages", coordinator)
        self.assertNotIn("allMessageIndices", coordinator)
        self.assertIn("ValuePromise<Int64>", coordinator)

    def test_snapshot_retains_hole_and_completeness_metadata(self) -> None:
        coordinator = source(
            "submodules/AyuGramFeatures/Sources/GRVMFilteredUnreadCoordinator.swift"
        )
        self.assertIn("LocalUnreadMessageScanResult", coordinator)
        self.assertIn("scanResultsByNamespace", coordinator)
        self.assertIn("result.hasHoles", coordinator)
        self.assertIn("result.isComplete", coordinator)


if __name__ == "__main__":
    unittest.main()
