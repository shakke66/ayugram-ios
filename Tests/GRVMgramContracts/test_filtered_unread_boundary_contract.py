import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def window(text: str, marker: str, size: int = 5000) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    return text[start : start + size]


class FilteredUnreadBoundaryContractTests(unittest.TestCase):
    def test_index_hole_horizon_uses_full_message_index_order(self) -> None:
        history = source("submodules/Postbox/Sources/MessageHistoryTable.swift")
        scan = window(history, "func incomingMessageIndicesAfterIndex(")

        self.assertIn(
            "if let topIndex = self.topIndexEntry(peerId: peerId, namespace: namespace), afterIndex < topIndex",
            scan,
        )
        self.assertIn(
            "range: 1 ... topIndex.id.id",
            scan,
        )
        self.assertNotIn("namespaceAfterIndex.id.id < topIndex.id.id", scan)
        self.assertNotIn("namespaceAfterIndex.id.id + 1", scan)

    def test_id_scan_guards_increment_before_max_incoming_read_id_plus_one(self) -> None:
        postbox = source("submodules/Postbox/Sources/Postbox.swift")
        scan = window(postbox, "fileprivate func scanLocalUnreadMessages(")

        self.assertIn(
            "maxIncomingReadId < upperBoundId, maxIncomingReadId < Int32.max",
            scan,
        )
        self.assertIn("minId: maxIncomingReadId + 1", scan)


if __name__ == "__main__":
    unittest.main()
