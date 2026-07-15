import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"


class ArchiveContractTests(unittest.TestCase):
    def test_message_key_contains_account_namespace_and_thread(self) -> None:
        source = MODELS.read_text(encoding="utf-8")
        for field in ("accountId", "peerId", "namespace", "messageId", "threadId"):
            self.assertIn(f"let {field}:", source)

    def test_cross_module_records_have_public_initializers(self) -> None:
        source = MODELS.read_text(encoding="utf-8")
        names = (
            "GRVMMessageKey",
            "GRVMArchivedMessage",
            "GRVMEditRevision",
            "GRVMEditRevisionDraft",
            "GRVMArchivedMedia",
            "GRVMArchiveQuery",
        )
        starts = [source.index(f"public struct {name}") for name in names]
        starts.append(source.index("public func grvmContentFingerprint"))
        for name, start, end in zip(names, starts, starts[1:]):
            self.assertIn("public init(", source[start:end], name)
