import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER = ROOT / "submodules/Postbox/Sources/LocalMessageDeletionMarker.swift"
INDEX = ROOT / "submodules/Postbox/Sources/MessageHistoryIndexTable.swift"
HISTORY = ROOT / "submodules/Postbox/Sources/MessageHistoryTable.swift"


class LocalDeletionContractTests(unittest.TestCase):
    def test_marker_protocol_exists(self) -> None:
        self.assertTrue(MARKER.exists())
        source = MARKER.read_text(encoding="utf-8")
        self.assertIn("public protocol LocalMessageDeletionMarker", source)
        self.assertIn("func isLocallyDeletedMessage", source)

    def test_incoming_counts_skip_marker(self) -> None:
        source = HISTORY.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("!isLocallyDeletedMessage"), 2)

    def test_index_has_local_deletion_bit_and_idempotent_transition(self) -> None:
        source = INDEX.read_text(encoding="utf-8")
        self.assertIn("HistoryEntryMessageFlagLocallyDeleted", source)
        self.assertIn("func markMessageLocallyDeleted(_ id: MessageId) -> Bool", source)
        self.assertIn("flags &= ~HistoryEntryMessageFlagIncoming", source)
        self.assertIn("flags |= HistoryEntryMessageFlagLocallyDeleted", source)
        self.assertIn("isLocallyDeletedMessage(message.attributes)", source)
        self.assertGreaterEqual(
            source.count("(flags & HistoryEntryMessageFlagLocallyDeleted) == 0"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
