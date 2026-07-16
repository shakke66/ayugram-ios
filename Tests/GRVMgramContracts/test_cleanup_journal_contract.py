import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"
COORDINATOR = ROOT / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
REGISTRY = ROOT / "submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift"
MEDIA_STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift"


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

    def test_cleanup_planning_fails_closed_when_targeted_blob_is_missing(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        begin = source[
            source.index("public func beginDeletedCleanup(") :
            source.index("public func pendingCleanupJobs(")
        ]
        self.assertIn("guard let record = try self.media(", begin)
        self.assertIn(
            'throw GRVMArchiveError.sqlite("targeted archived media is missing")',
            begin,
        )
        self.assertNotIn("if let record = try self.media(", begin)

        lookup = source[
            source.index("private func media(") :
            source.index("private func readMedia(")
        ]
        self.assertIn("throws -> GRVMArchivedMedia?", lookup)
        self.assertIn("return nil", lookup)

    def test_reconciliation_persists_updates_before_restoring_media(self) -> None:
        source = COORDINATOR.read_text(encoding="utf-8")
        reconcile = source[
            source.index("private func reconcileArchivedMedia()") :
            source.index("public func reconcilePersistentMessageState()")
        ]
        self.assertIn("mediaBox: self.mediaBox", reconcile)
        self.assertIn("updatedRecords", reconcile)
        self.assertLess(
            reconcile.index("self.store.updateMedia(record)"),
            reconcile.index("self.restore("),
        )
        self.assertIn(
            "updatedRecords.filter { $0.copyState == .complete }",
            reconcile,
        )

    def test_cleanup_runner_uses_durable_destructive_order_and_typed_failure(self) -> None:
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        clear = coordinator[coordinator.index("public func clearDeleted(") :]
        self.assertLess(clear.index("beginDeletedCleanup("), clear.index("runCleanupJob("))

        runner = coordinator[coordinator.index("private func runCleanupJob(") :]
        anchors = [
            "removeArchivedFiles(",
            "markCleanupFilesRemoved(",
            "self.postbox.transaction",
            "finalizeDeletedCleanup(",
            "self.index.removeDeleted",
            "subscriber.putNext(ids)",
        ]
        positions = [runner.index(anchor) for anchor in anchors]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Signal<[MessageId], GRVMClearDeletedError>", coordinator)
        self.assertIn("pendingCleanupJobs(accountId:", coordinator)
        self.assertNotIn("self.store.removeDeleted(keys)", coordinator)

    def test_preservation_and_cleanup_planning_share_the_coordinator_queue(self) -> None:
        source = COORDINATOR.read_text(encoding="utf-8")
        deleted = source[
            source.index("public func preserveDeletedMessages(") :
            source.index("public func preserveEditRevision(")
        ]
        revision = source[
            source.index("public func preserveEditRevision(") :
            source.index("public func clearDeleted(")
        ]
        clear = source[source.index("public func clearDeleted(") :]

        self.assertIn("self.queue.sync", deleted)
        self.assertIn("preserveDeletedMessagesOnQueue", deleted)
        self.assertIn("self.queue.sync", revision)
        self.assertIn("preserveEditRevisionOnQueue", revision)
        self.assertIn("self.queue.async", clear)
        self.assertLess(clear.index("beginDeletedCleanup("), clear.index("runCleanupJob("))

    def test_startup_publishes_then_resumes_oldest_jobs_before_media_reconciliation(self) -> None:
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        registry = REGISTRY.read_text(encoding="utf-8")
        registration = registry[registry.index("public func register(") :]
        self.assertLess(
            registration.index("state.services[accountPeerId] = coordinator"),
            registration.index("coordinator.resumePendingCleanupJobs()"),
        )

        resume = coordinator[
            coordinator.index("public func resumePendingCleanupJobs()") :
            coordinator.index("private func resumeCleanupJobs(")
        ]
        self.assertIn("pendingCleanupJobs(accountId:", resume)
        self.assertLess(resume.index("guard !jobs.isEmpty else"), resume.index("resumeCleanupJobs(jobs, index: 0)"))

        sequence = coordinator[
            coordinator.index("private func resumeCleanupJobs(") :
            coordinator.index("private func runCleanupJob(")
        ]
        terminal = sequence[:sequence.index("self.disposables.add")]
        failure = sequence[sequence.index("}, error: { [weak self] _ in") :]
        self.assertIn("reconcileArchivedMedia()", terminal)
        self.assertIn("index: index + 1", sequence)
        self.assertNotIn("reconcileArchivedMedia()", failure)

    def test_obsolete_best_effort_cleanup_apis_are_removed(self) -> None:
        store = STORE.read_text(encoding="utf-8")
        media_store = MEDIA_STORE.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")

        self.assertNotIn("public func removeDeleted(", store)
        self.assertNotIn("public func remove(_ records:", media_store)
        self.assertNotIn("mediaStore.remove(", coordinator)
        self.assertNotIn("try? self.fileManager.removeItem", media_store)
