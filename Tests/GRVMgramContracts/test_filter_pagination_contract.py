import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HISTORY = "submodules/TelegramUI/Sources/ChatHistoryListNode.swift"


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FilterPaginationContractTests(unittest.TestCase):
    def test_backfill_uses_raw_boundaries_without_requiring_survivors(self) -> None:
        history = source(HISTORY)
        start = history.index(
            "if let rawFirstEntry = historyView.originalView.entries.first"
        )
        end = history.index("var containsPlayableWithSoundItemNode", start)
        pagination = history[start:end]

        self.assertNotIn(
            "if let loaded = displayedRange.visibleRange, let firstEntry = historyView.filteredEntries.first",
            pagination,
        )
        for token in (
            "let hasNoVisibleEntries = historyView.filteredEntries.isEmpty",
            "!historyView.originalView.entries.isEmpty",
            "historyView.originalView.earlierId != nil",
            "historyView.originalView.laterId != nil",
            "self.currentPrefetchDirectionIsToLater",
            ".message(rawFirstEntry.index)",
            ".message(rawLastEntry.index)",
        ):
            self.assertIn(token, pagination)

    def test_backfill_is_bounded_by_anchor_progress_and_real_history_edges(self) -> None:
        history = source(HISTORY)
        for declaration in (
            "private var filterBackfillEarlierAnchor: MessageIndex?",
            "private var filterBackfillLaterAnchor: MessageIndex?",
        ):
            self.assertIn(declaration, history)

        start = history.index(
            "if let rawFirstEntry = historyView.originalView.entries.first"
        )
        end = history.index("var containsPlayableWithSoundItemNode", start)
        pagination = history[start:end]
        for token in (
            "self.filterBackfillEarlierAnchor != rawFirstEntry.index",
            "self.filterBackfillLaterAnchor != rawLastEntry.index",
            "self.filterBackfillEarlierAnchor = rawFirstEntry.index",
            "self.filterBackfillLaterAnchor = rawLastEntry.index",
            "let canRequestEarlier",
            "let canRequestLater",
        ):
            self.assertIn(token, pagination)
        self.assertIn(
            "historyView.originalView.laterId == nil", pagination
        )
        self.assertIn(
            "historyView.originalView.earlierId == nil", pagination
        )

    def test_stock_upper_bound_and_custom_history_routes_remain(self) -> None:
        history = source(HISTORY)
        start = history.index(
            "if let rawFirstEntry = historyView.originalView.entries.first"
        )
        end = history.index("var containsPlayableWithSoundItemNode", start)
        pagination = history[start:end]
        for token in (
            "historyView.originalView.anchorIndex != .upperBound",
            ".Navigation(index: .upperBound, anchorIndex: .upperBound",
            "case .hashTagSearch = customChatContents.kind",
            "customChatContents.loadMore()",
        ):
            self.assertIn(token, pagination)


if __name__ == "__main__":
    unittest.main()
