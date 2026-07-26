import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"
COORDINATOR = ROOT / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
REGISTRY = ROOT / "submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift"
MEDIA_STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift"


class CleanupJournalContractTests(unittest.TestCase):
    def test_schema_v5_is_migration_safe(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS cleanup_jobs", source)
        self.assertIn("message_keys BLOB NOT NULL", source)
        self.assertIn("media_records BLOB NOT NULL", source)
        self.assertIn("CREATE TABLE IF NOT EXISTS deleted_message_suppressions", source)
        self.assertIn("PRAGMA user_version = 5", source)
        self.assertIn("case 2:", source)
        self.assertIn("case 3:", source)
        self.assertIn("case 4:", source)
        self.assertIn("case 5:", source)

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
            source.index("private func revalidatedCleanupMediaRecords(")
        ]
        self.assertIn("revisionId: 0", planning)
        self.assertNotIn("SELECT COUNT(*) FROM archived_message_media", planning)
        self.assertNotIn("references == Int64(targetedReferences)", planning)
        revalidation = source[
            source.index("private func revalidatedCleanupMediaRecords(") :
            source.index("public func beginDeletedCleanup(")
        ]
        self.assertIn("references == Int64(targetedReferences)", revalidation)
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
            store.index("private func revalidatedCleanupMediaRecords(")
        ]
        for token in (
            "revisionId: 0",
            "mappedResourceIds(",
            "guard let record = try self.media(",
            'throw GRVMArchiveError.sqlite("targeted archived media is missing")',
            "mediaRecords.sort",
        ):
            with self.subTest(token=token):
                self.assertIn(token, helper)
        self.assertNotIn("SELECT COUNT(*) FROM archived_message_media", helper)
        self.assertNotIn("references == Int64(targetedReferences)", helper)

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
            "let mediaRecords = try self.revalidatedCleanupMediaRecords(",
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

    def test_cleanup_revalidation_only_filters_captured_media_generations(self) -> None:
        store = STORE.read_text(encoding="utf-8")
        self.assertIn("private func revalidatedCleanupMediaRecords(", store)
        helper = store[
            store.index("private func revalidatedCleanupMediaRecords(") :
            store.index("public func pendingCleanupJobs(")
        ]
        for token in (
            "for record in job.mediaRecords",
            "current.generation == record.generation",
            "current.relativePath == record.relativePath",
            "references == Int64(targetedReferences)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, helper)
        revalidate = store[
            store.index("public func revalidateDeletedCleanup(") :
            store.index("public func pendingCleanupJobs(")
        ]
        self.assertIn("self.revalidatedCleanupMediaRecords(", revalidate)
        self.assertNotIn("self.cleanupMediaRecords(", revalidate)

    def test_two_pending_scoped_jobs_revalidate_last_shared_blob_from_planned_snapshot(self) -> None:
        store = STORE.read_text(encoding="utf-8")
        planning = store[
            store.index("private func cleanupMediaRecords(") :
            store.index("private func revalidatedCleanupMediaRecords(")
        ]
        revalidation = store[
            store.index("private func revalidatedCleanupMediaRecords(") :
            store.index("public func beginDeletedCleanup(")
        ]
        exclusive_gate = "references == Int64(targetedReferences)"
        planning_has_exclusive_gate = exclusive_gate in planning
        revalidation_has_exclusive_gate = exclusive_gate in revalidation

        mappings = {"first-scope": {"shared"}, "second-scope": {"shared"}}
        blobs = {
            "shared": {"generation": 7, "relativePath": "media/shared.bin"}
        }

        def targeted_counts(scopes: list[str]) -> dict[str, int]:
            result: dict[str, int] = {}
            for scope in scopes:
                for resource_id in mappings.get(scope, set()):
                    result[resource_id] = result.get(resource_id, 0) + 1
            return result

        def plan(scopes: list[str]) -> list[tuple[str, int, str]]:
            result: list[tuple[str, int, str]] = []
            for resource_id, targeted in targeted_counts(scopes).items():
                references = sum(resource_id in resources for resources in mappings.values())
                if planning_has_exclusive_gate and references != targeted:
                    continue
                blob = blobs[resource_id]
                result.append((resource_id, blob["generation"], blob["relativePath"]))
            return result

        def revalidate(
            snapshots: list[tuple[str, int, str]], scopes: list[str]
        ) -> list[str]:
            targets = targeted_counts(scopes)
            result: list[str] = []
            for resource_id, generation, relative_path in snapshots:
                targeted = targets.get(resource_id)
                if targeted is None:
                    continue
                references = sum(resource_id in resources for resources in mappings.values())
                if revalidation_has_exclusive_gate and references != targeted:
                    continue
                blob = blobs[resource_id]
                if (blob["generation"], blob["relativePath"]) != (
                    generation,
                    relative_path,
                ):
                    continue
                result.append(resource_id)
            return result

        first_job = plan(["first-scope"])
        second_job = plan(["second-scope"])

        first_claims = revalidate(first_job, ["first-scope"])
        self.assertEqual([], first_claims)
        mappings.pop("first-scope")
        self.assertIn("shared", blobs)

        second_claims = revalidate(second_job, ["second-scope"])
        self.assertEqual(["shared"], second_claims)
        mappings.pop("second-scope")
        for resource_id in second_claims:
            if not any(resource_id in resources for resources in mappings.values()):
                blobs.pop(resource_id)

        self.assertEqual({}, mappings)
        self.assertEqual({}, blobs)
        self.assertFalse(planning_has_exclusive_gate)
        self.assertTrue(revalidation_has_exclusive_gate)

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
            "self.disposables.dispose()",
            "self.isCleanupExecutorRunning = false",
            "waiters = self.takeAllCleanupWaiters()",
            "return waiters",
        ]
        positions = [shutdown.index(anchor) for anchor in anchors]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("subscriber.putError", shutdown)
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

    def test_shutdown_disposes_all_work_and_guards_stale_mutation_callbacks(self) -> None:
        source = COORDINATOR.read_text(encoding="utf-8")

        shutdown = source[
            source.index("func shutdownForReplacement()") :
            source.index("public func resumePendingCleanupJobs()")
        ]
        self.assertIn("self.disposables.dispose()", shutdown)
        self.assertLess(
            shutdown.index("self.cleanupRunnerDisposable.dispose()"),
            shutdown.index("self.disposables.dispose()"),
        )
        self.assertLess(
            shutdown.index("self.disposables.dispose()"),
            shutdown.index("self.takeAllCleanupWaiters()"),
        )

        prepare = source[source.index("func prepare() throws") : source.index("func shutdownForReplacement()")]
        did_remove = prepare[prepare.index("self.queue.async") :]
        self.assertLess(
            did_remove.index("guard self.isAcceptingOperations else"),
            did_remove.index("self.store.archivedMedia("),
        )
        self.assertLess(
            did_remove.index("guard self.isAcceptingOperations else"),
            did_remove.index("self.restore("),
        )

        reconcile = source[
            source.index("private func reconcileArchivedMedia()") :
            source.index("public func reconcilePersistentMessageState()")
        ]
        reconcile_callback = reconcile[reconcile.index("self.queue.async") :]
        self.assertLess(
            reconcile_callback.index("guard self.isAcceptingOperations else"),
            reconcile_callback.index("self.store.updateMedia(record)"),
        )
        self.assertLess(
            reconcile_callback.index("guard self.isAcceptingOperations else"),
            reconcile_callback.index("self.restore("),
        )

        persistent = source[
            source.index("public func reconcilePersistentMessageState()") :
            source.index("public func settingsSnapshot()")
        ]
        persistent_callback = persistent[persistent.index("self.queue.async") :]
        self.assertLess(
            persistent_callback.index("guard self.isAcceptingOperations else"),
            persistent_callback.index("self.store.deletedMessages("),
        )
        self.assertLess(
            persistent_callback.index("guard self.isAcceptingOperations else"),
            persistent_callback.index("self.postbox.transaction"),
        )

        deleted = source[
            source.index("private func preserveDeletedMessagesOnQueue(") :
            source.index("public func preserveEditRevision(")
        ]
        deleted_callback = deleted[deleted.index(".start(next: { [weak self] record in") :]
        self.assertLess(
            deleted_callback.index("guard self.isAcceptingOperations else"),
            deleted_callback.index("self.store.updateMedia(record)"),
        )

        revision = source[
            source.index("private func preserveEditRevisionOnQueue(") :
            source.index("public func clearDeleted(")
        ]
        revision_callback = revision[revision.index(".start(next: { [weak self] record in") :]
        self.assertLess(
            revision_callback.index("guard self.isAcceptingOperations else"),
            revision_callback.index("self.store.updateMedia(record)"),
        )

        restore = source[source.index("private func restore(") :]
        self.assertLess(
            restore.index("guard self.isAcceptingOperations else"),
            restore.index("self.mediaStore.restore(record, to: mediaBox)"),
        )

    def test_obsolete_best_effort_cleanup_apis_are_removed(self) -> None:
        store = STORE.read_text(encoding="utf-8")
        media_store = MEDIA_STORE.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")

        self.assertNotIn("public func removeDeleted(", store)
        self.assertNotIn("public func remove(_ records:", media_store)
        self.assertNotIn("mediaStore.remove(", coordinator)
        self.assertNotIn("try? self.fileManager.removeItem", media_store)
