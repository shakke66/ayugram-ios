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
        for name in (
            "beginDeletedCleanup(",
            "revalidateDeletedCleanup(",
            "pendingCleanupJobs(",
            "markCleanupFilesRemoved(",
            "finalizeDeletedCleanup(",
        ):
            self.assertIn(name, source)
        planning = source[
            source.index("private func cleanupMediaRecords(") :
            source.index("public func beginDeletedCleanup(")
        ]
        self.assertIn("revisionId: 0", planning)
        self.assertIn("references == Int64(targetedReferences)", planning)
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
        planning = source[
            source.index("private func cleanupMediaRecords(") :
            source.index("public func beginDeletedCleanup(")
        ]
        self.assertIn("guard let record = try self.media(", planning)
        self.assertIn(
            'throw GRVMArchiveError.sqlite("targeted archived media is missing")',
            planning,
        )
        self.assertNotIn("if let record = try self.media(", planning)

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
        self.assertLess(clear.index("beginDeletedCleanup("), clear.index("addCleanupWaiter("))
        self.assertLess(clear.index("addCleanupWaiter("), clear.index("startCleanupExecutorIfNeeded()"))

        runner = coordinator[coordinator.index("private func runCleanupJob(") :]
        anchors = [
            "revalidateDeletedCleanup(",
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

    def test_planned_job_revalidates_current_mappings_and_persists_before_unlink(self) -> None:
        store = STORE.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("private func cleanupMediaRecords(", store)
        self.assertIn("public func revalidateDeletedCleanup(", store)
        self.assertIn("job = try self.store.revalidateDeletedCleanup(id: job.id)", coordinator)

        helper = store[
            store.index("private func cleanupMediaRecords(") :
            store.index("public func beginDeletedCleanup(")
        ]
        for token in (
            "revisionId: 0",
            "targetedReferencesByResourceId",
            "SELECT COUNT(*) FROM archived_message_media",
            "references == Int64(targetedReferences)",
            "guard let record = try self.media(",
            'throw GRVMArchiveError.sqlite("targeted archived media is missing")',
            "mediaRecords.sort",
        ):
            with self.subTest(token=token):
                self.assertIn(token, helper)

        begin = store[
            store.index("public func beginDeletedCleanup(") :
            store.index("public func revalidateDeletedCleanup(")
        ]
        self.assertIn("self.cleanupMediaRecords(", begin)

        revalidate = store[
            store.index("public func revalidateDeletedCleanup(") :
            store.index("public func pendingCleanupJobs(")
        ]
        anchors = [
            "try self.transaction(database)",
            "guard let job = try self.cleanupJob(database, id: id)",
            "guard job.phase == .planned",
            "let mediaRecords = try self.cleanupMediaRecords(",
            "UPDATE cleanup_jobs SET media_records = ?",
            ".data(try self.jsonEncoder.encode(mediaRecords))",
            "guard let refreshed = try self.cleanupJob(database, id: id)",
            "return refreshed",
        ]
        positions = [revalidate.index(anchor) for anchor in anchors]
        self.assertEqual(positions, sorted(positions))

        runner = coordinator[
            coordinator.index("private func runCleanupJob(") :
            coordinator.index("private func reconcileArchivedMedia()")
        ]
        planned = runner[runner.index("if job.phase == .planned") : runner.index("let ids =")]
        self.assertLess(
            planned.index("job = try self.store.revalidateDeletedCleanup(id: job.id)"),
            planned.index("self.mediaStore.removeArchivedFiles(job.mediaRecords)"),
        )
        self.assertLess(
            planned.index("self.mediaStore.removeArchivedFiles(job.mediaRecords)"),
            planned.index("self.store.markCleanupFilesRemoved(id: job.id)"),
        )

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
        self.assertLess(clear.index("beginDeletedCleanup("), clear.index("addCleanupWaiter("))
        self.assertLess(clear.index("addCleanupWaiter("), clear.index("startCleanupExecutorIfNeeded()"))

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
            coordinator.index("private func startCleanupExecutorIfNeeded()")
        ]
        self.assertIn("startCleanupExecutorIfNeeded()", resume)
        self.assertNotIn("pendingCleanupJobs(accountId:", resume)

        drain = coordinator[
            coordinator.index("private func drainNextCleanupJob(") :
            coordinator.index("private func runCleanupJob(")
        ]
        self.assertIn("pendingCleanupJobs(accountId:", drain)
        self.assertIn(".first", drain)
        empty = drain[drain.index("guard let job else") : drain.index("let disposable =")]
        self.assertIn("reconcileArchivedMedia()", empty)
        self.assertIn("drainNextCleanupJob()", drain[drain.index("next: { [weak self] ids in") :])
        failure = coordinator[
            coordinator.index("private func failCleanupExecutor(") :
            coordinator.index("private func runCleanupJob(")
        ]
        self.assertNotIn("reconcileArchivedMedia()", failure)

    def test_clear_and_resume_share_one_fresh_query_executor_with_safe_waiters(self) -> None:
        source = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("private var isCleanupExecutorRunning = false", source)
        self.assertIn(
            "private var cleanupWaiters: [UUID: [UUID: Subscriber<[MessageId], GRVMClearDeletedError>]] = [:]",
            source,
        )
        self.assertNotIn("isResumingCleanupJobs", source)
        self.assertNotIn("private func resumeCleanupJobs(", source)

        clear = source[source.index("public func clearDeleted(") :]
        for token in (
            "let waiterId = UUID()",
            "self.addCleanupWaiter(jobId: job.id, waiterId: waiterId, subscriber: subscriber)",
            "self.startCleanupExecutorIfNeeded()",
            "return ActionDisposable",
            "self.removeCleanupWaiter(waiterId)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, clear)
        self.assertNotIn("self.runCleanupJob(job).start", clear)
        self.assertNotIn("let disposable = MetaDisposable()", clear)

        add_waiter = source[
            source.index("private func addCleanupWaiter(") :
            source.index("private func removeCleanupWaiter(")
        ]
        self.assertIn("self.cleanupWaiters[jobId, default: [:]][waiterId] = subscriber", add_waiter)
        self.assertIn("self.cleanupWaiterJobs[waiterId] = jobId", add_waiter)

        start = source[
            source.index("private func startCleanupExecutorIfNeeded()") :
            source.index("private func drainNextCleanupJob(")
        ]
        accepting_guard = "guard self.isAcceptingOperations, !self.isCleanupExecutorRunning"
        self.assertLess(start.index(accepting_guard), start.index("self.isCleanupExecutorRunning = true"))
        self.assertLess(start.index("self.isCleanupExecutorRunning = true"), start.index("self.drainNextCleanupJob()"))

        drain = source[
            source.index("private func drainNextCleanupJob(") :
            source.index("private func finishCleanupWaiters(")
        ]
        self.assertIn("try self.store.pendingCleanupJobs(accountId: self.accountRecordId.int64).first", drain)
        pending = STORE.read_text(encoding="utf-8")
        pending = pending[pending.index("public func pendingCleanupJobs(") : pending.index("public func markCleanupFilesRemoved(")]
        self.assertIn("ORDER BY created_at ASC, job_id ASC", pending)
        self.assertEqual(drain.count("self.runCleanupJob("), 1)
        self.assertIn("self.cleanupRunnerDisposable.set(disposable)", drain)
        success = drain[drain.index("next: { [weak self] ids in") : drain.index("}, error: { [weak self] error in")]
        self.assertIn("self.finishCleanupWaiters(jobId: job.id, ids: ids)", success)
        self.assertIn("self.drainNextCleanupJob()", success)
        error = drain[drain.index("}, error: { [weak self] error in") :]
        self.assertIn("self.failCleanupExecutor(error)", error)
        self.assertNotIn("reconcileArchivedMedia()", error)

        finish = source[
            source.index("private func finishCleanupWaiters(") :
            source.index("private func failCleanupExecutor(")
        ]
        self.assertLess(finish.index("takeCleanupWaiters(jobId: jobId)"), finish.index("subscriber.putNext(ids)"))
        self.assertEqual(finish.count("subscriber.putNext(ids)"), 1)
        self.assertEqual(finish.count("subscriber.putCompletion()"), 1)

        failure = source[
            source.index("private func failCleanupExecutor(") :
            source.index("private func runCleanupJob(")
        ]
        self.assertIn("self.isCleanupExecutorRunning = false", failure)
        self.assertIn("self.takeAllCleanupWaiters()", failure)
        self.assertIn("subscriber.putError(error)", failure)
        self.assertNotIn("subscriber.putNext", failure)
        self.assertNotIn("reconcileArchivedMedia()", failure)

    def test_shutdown_quiesces_cleanup_and_rejects_stale_generation_operations(self) -> None:
        source = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("private var isAcceptingOperations = true", source)
        self.assertIn("private let cleanupRunnerDisposable = MetaDisposable()", source)
        self.assertIn("func shutdownForReplacement()", source)

        deinit = source[source.index("deinit {") : source.index("func prepare() throws")]
        self.assertLess(
            deinit.index("self.cleanupRunnerDisposable.dispose()"),
            deinit.index("self.disposables.dispose()"),
        )

        shutdown = source[
            source.index("func shutdownForReplacement()") :
            source.index("public func resumePendingCleanupJobs()")
        ]
        anchors = [
            "self.queue.sync",
            "guard self.isAcceptingOperations else",
            "self.isAcceptingOperations = false",
            "self.cleanupRunnerDisposable.dispose()",
            "self.isCleanupExecutorRunning = false",
            "let waiters = self.takeAllCleanupWaiters()",
            "subscriber.putError(.archiveUnavailable)",
        ]
        positions = [shutdown.index(anchor) for anchor in anchors]
        self.assertEqual(positions, sorted(positions))
        for forbidden in (
            "reconcileArchivedMedia()",
            "markCleanupFilesRemoved(",
            "finalizeDeletedCleanup(",
        ):
            self.assertNotIn(forbidden, shutdown)

        resume = source[
            source.index("public func resumePendingCleanupJobs()") :
            source.index("private func addCleanupWaiter(")
        ]
        self.assertIn("guard self.isAcceptingOperations else", resume)

        deleted = source[
            source.index("public func preserveDeletedMessages(") :
            source.index("public func preserveEditRevision(")
        ]
        revision = source[
            source.index("public func preserveEditRevision(") :
            source.index("public func clearDeleted(")
        ]
        clear = source[source.index("public func clearDeleted(") : source.index("public func hasEditHistory(")]
        for operation in (deleted, revision, clear):
            self.assertIn("guard self.isAcceptingOperations else", operation)

        drain = source[
            source.index("private func drainNextCleanupJob(") :
            source.index("private func finishCleanupWaiters(")
        ]
        self.assertIn("guard self.isAcceptingOperations else", drain)
        self.assertIn("self.cleanupRunnerDisposable.set(disposable)", drain)
        self.assertNotIn("self.disposables.add(disposable)", drain)
        self.assertGreaterEqual(drain.count("guard self.isAcceptingOperations else"), 3)

        runner = source[
            source.index("private func runCleanupJob(") :
            source.index("private func reconcileArchivedMedia()")
        ]
        finalization = runner[runner.index("}.start(next: { ids in") :]
        self.assertLess(
            finalization.index("guard self.isAcceptingOperations else"),
            finalization.index("self.store.finalizeDeletedCleanup(id: job.id)"),
        )

    def test_obsolete_best_effort_cleanup_apis_are_removed(self) -> None:
        store = STORE.read_text(encoding="utf-8")
        media_store = MEDIA_STORE.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")

        self.assertNotIn("public func removeDeleted(", store)
        self.assertNotIn("public func remove(_ records:", media_store)
        self.assertNotIn("mediaStore.remove(", coordinator)
        self.assertNotIn("try? self.fileManager.removeItem", media_store)
