import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FilteredUnreadThreadContractTests(unittest.TestCase):
    def test_postbox_exposes_read_only_thread_scan_with_hole_metadata(self) -> None:
        postbox = source("submodules/Postbox/Sources/Postbox.swift")
        self.assertIn("public func scanLocalUnreadThreadMessages(", postbox)
        scan = postbox[postbox.find("public func scanLocalUnreadThreadMessages(") :]
        self.assertIn("threadId: Int64", scan[:1800])
        self.assertIn("getMessagesWithThreadId", scan[:5000])
        self.assertIn("getThreadIndexHoles", scan[:5000])
        self.assertIn("LocalUnreadMessageScanResult", scan[:1800])

    def test_coordinator_materializes_threads_and_preserves_unknown_counts(self) -> None:
        coordinator = source(
            "submodules/AyuGramFeatures/Sources/GRVMFilteredUnreadCoordinator.swift"
        )
        self.assertIn("getMessageHistoryThreadIndex", coordinator)
        self.assertIn("scanLocalUnreadThreadMessages", coordinator)
        self.assertIn("threadSnapshots", coordinator)
        self.assertIn("hasIncompleteThreadScan", coordinator)
        self.assertIn("threadAggregateRawCount", coordinator)

    def test_thread_badges_use_an_account_scoped_display_only_hook(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        entries = source("submodules/ChatListUI/Sources/Node/ChatListNodeEntries.swift")
        account = source("submodules/TelegramUI/Sources/AccountContext.swift")
        self.assertIn(
            "public static var adjustedUnreadThreadCount: ((PeerId, PeerId, Int64, Int32) -> Int32)?",
            hooks,
        )
        self.assertIn("AyuGramHooks.adjustedUnreadThreadCount?", entries)
        self.assertIn("AyuGramHooks.adjustedUnreadThreadCount?", account)


if __name__ == "__main__":
    unittest.main()
