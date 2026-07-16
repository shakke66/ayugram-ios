import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"


class CleanupJournalContractTests(unittest.TestCase):
    def test_schema_v3_is_migration_safe(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS cleanup_jobs", source)
        self.assertIn("message_keys BLOB NOT NULL", source)
        self.assertIn("media_records BLOB NOT NULL", source)
        self.assertIn("PRAGMA user_version = 3", source)
        self.assertIn("case 2:", source)
        self.assertIn("case 3:", source)

    def test_cleanup_models_are_codable(self) -> None:
        source = MODELS.read_text(encoding="utf-8")
        self.assertIn("enum GRVMCleanupPhase: Int32, Codable", source)
        self.assertIn("struct GRVMCleanupJob: Codable, Equatable", source)
        self.assertIn("enum GRVMClearDeletedError: Error, Equatable", source)
        self.assertIn("struct GRVMArchivedMedia: Codable, Equatable", source)

    def test_store_has_staged_atomic_boundaries(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        for name in ("beginDeletedCleanup(", "pendingCleanupJobs(", "markCleanupFilesRemoved(", "finalizeDeletedCleanup("):
            self.assertIn(name, source)
        begin = source[source.index("public func beginDeletedCleanup(") :]
        self.assertIn("revisionId: 0", begin[:12000])
        self.assertIn("references == Int64(targetedReferences)", begin[:12000])
        finalize = source[source.index("public func finalizeDeletedCleanup(") :]
        self.assertIn("DELETE FROM archived_messages", finalize[:16000])
        self.assertIn("DELETE FROM cleanup_jobs", finalize[:16000])
        self.assertIn("SELECT COUNT(*) FROM archived_message_media", finalize[:16000])

    def test_invalid_media_copy_state_fails_closed_at_shared_reader(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        reader = source[
            source.index("private func readMedia(") :
            source.index("private func mappedResourceIds(")
        ]
        self.assertIn("throws -> GRVMArchivedMedia", reader)
        self.assertIn(
            'throw GRVMArchiveError.sqlite("invalid archived media copy state")',
            reader,
        )
        self.assertNotIn("return nil", reader)
        self.assertIn("result.append(try self.readMedia(statement))", source)
        self.assertIn("return try self.readMedia(statement)", source)
