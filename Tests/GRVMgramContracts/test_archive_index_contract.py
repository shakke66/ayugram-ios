import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveIndex.swift"


class ArchiveIndexContractTests(unittest.TestCase):
    def test_snapshot_is_owned_by_one_atomic(self) -> None:
        source = INDEX.read_text(encoding="utf-8")
        self.assertEqual(1, source.count("Atomic<GRVMMessageArchiveSnapshot>"))
        self.assertNotIn("DispatchQueue.main.sync", source)
        self.assertNotIn("private var deleted: Set", source)
        self.assertNotIn("private var revised: Set", source)

    def test_snapshot_can_be_constructed_cross_module(self) -> None:
        source = INDEX.read_text(encoding="utf-8")
        snapshot = source[source.index("public struct GRVMMessageArchiveSnapshot") :]
        self.assertIn("public init(", snapshot[: snapshot.index("public final class")])

    def test_all_updates_replace_immutable_snapshots(self) -> None:
        source = INDEX.read_text(encoding="utf-8")
        for method in (
            "func snapshot()",
            "func replace(",
            "func insertDeleted(",
            "func insertRevised(",
            "func removeDeleted(",
        ):
            self.assertIn(method, source)
        self.assertIn("self.state.modify", source)
        self.assertIn("self.state.swap", source)


if __name__ == "__main__":
    unittest.main()
