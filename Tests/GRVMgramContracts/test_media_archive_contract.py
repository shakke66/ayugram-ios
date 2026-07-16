import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = ROOT / "submodules/AyuGramLib/Sources/GRVMMediaResourceCollector.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift"
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"
MEDIA_BOX = ROOT / "submodules/Postbox/Sources/MediaBox.swift"
BUILD = ROOT / "submodules/AyuGramLib/BUILD"


class MediaArchiveContractTests(unittest.TestCase):
    def test_collector_visits_every_supported_nested_resource(self) -> None:
        source = COLLECTOR.read_text(encoding="utf-8")
        for token in (
            "image.representations",
            "image.videoRepresentations",
            "image.video",
            "file.resource",
            "file.previewRepresentations",
            "file.videoThumbnails",
            "file.videoCover",
            "file.alternativeRepresentations",
            "TelegramMediaWebpage",
            "TelegramMediaGame",
            "TelegramMediaPaidContent",
            "paidContent.extendedMedia",
        ):
            self.assertIn(token, source)
        self.assertIn("Set<MediaResourceId>", source)
        self.assertIn("public init(", source)

    def test_archive_paths_are_hashed_relative_and_streamed(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        for token in (
            "CryptoSHA256",
            'appendingPathComponent("blobs")',
            "relativePath",
            "linkItem",
            "copyItem",
            'appendingPathExtension("tmp")',
            "isExcludedFromBackup",
            "completeUntilFirstUserAuthentication",
        ):
            self.assertIn(token, source)
        self.assertNotIn("Data(contentsOf:", source)
        self.assertNotIn("fetchedResource", source)
        self.assertIn(
            'relativePath.hasPrefix("\\(record.accountId)/blobs/")',
            source,
        )

    def test_removal_reports_explicit_idempotent_outcomes(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("struct GRVMMediaRemovalResult: Equatable", source)
        self.assertIn("func removeArchivedFiles(", source)
        self.assertIn("NSFileNoSuchFileError", source)

        remove_section = source[
            source.index("public func removeArchivedFiles(") :
            source.index("public func reconcile(")
        ]
        self.assertNotIn("try? self.fileManager.removeItem", remove_section)
        self.assertIn('appendingPathExtension("tmp")', remove_section)

        validation_section = source[
            source.index("private func archiveURL(record:") :
            source.index("private func fileSize(")
        ]
        self.assertIn("self.resourceLocation(", validation_section)
        self.assertIn("record.relativePath == expected.relativePath", validation_section)

    def test_reconciliation_recovers_interrupted_copies(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        reconcile_section = source[
            source.index("public func reconcile(") :
            source.index("private func resourceLocation(")
        ]
        self.assertIn("mediaBox: MediaBox", reconcile_section)
        self.assertIn("case .copying", reconcile_section)
        self.assertIn(
            "self.archiveRecord(record, resource: resource, mediaBox: mediaBox)",
            reconcile_section,
        )
        self.assertIn("copyState: .complete", reconcile_section)
        self.assertIn("copyState: .unavailable", reconcile_section)
        self.assertNotIn("try? self.fileManager.removeItem", source)

        references_section = reconcile_section[
            reconcile_section.index("let referencedRelativePaths") :
            reconcile_section.index("let blobsURL")
        ]
        self.assertIn("record.copyState == .copying", references_section)
        self.assertIn("self.resourceLocation(", references_section)

    def test_copying_recovery_rejects_zero_byte_files(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        copying_section = source[
            source.index("case .copying:") :
            source.index("case .complete:")
        ]
        archive_section = source[
            source.index("private func archiveRecord(") :
            source.index("private func copyAtomically(")
        ]
        self.assertIn("byteCount > 0", copying_section)
        self.assertIn("byteCount > 0", archive_section)

    def test_failed_terminal_tmp_cleanup_completes_without_next(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        copying_section = source[
            source.index("case .copying:") :
            source.index("case .complete:")
        ]
        cleanup_gate = "guard self.removeIfPresent(temporaryURL) else"
        self.assertEqual(copying_section.count(cleanup_gate), 1)
        self.assertEqual(copying_section.count("subscriber.putCompletion()"), 1)
        self.assertGreaterEqual(copying_section.count("return"), 1)
        self.assertNotIn("subscriber.putNext", copying_section)

    def test_failed_orphan_cleanup_completes_without_next(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        reconcile_section = source[
            source.index("public func reconcile(") :
            source.index("private func resourceLocation(")
        ]
        cleanup_section = reconcile_section[
            reconcile_section.index("let blobsURL") :
            reconcile_section.index("var updates")
        ]
        self.assertIn("var cleanupFailed = false", cleanup_section)
        self.assertGreaterEqual(cleanup_section.count("cleanupFailed = true"), 2)
        self.assertIn("guard !cleanupFailed else", cleanup_section)
        failure_section = cleanup_section[
            cleanup_section.index("guard !cleanupFailed else") :
        ]
        self.assertIn("subscriber.putCompletion()", failure_section)
        self.assertIn("return", failure_section)
        self.assertNotIn("subscriber.putNext", failure_section)

    def test_archive_signal_schedules_shared_copy_helper(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        archive_section = source[
            source.index("public func archive(") :
            source.index("public func restore(")
        ]
        self.assertIn("private func archiveRecord(", source)
        self.assertIn("self.archiveRecord(", archive_section)
        self.assertIn("subscriber.putNext", archive_section)

    def test_existing_positive_final_blob_wins_before_media_box_lookup(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        archive_section = source[
            source.index("private func archiveRecord(") :
            source.index("private func copyAtomically(")
        ]
        self.assertIn("let archivedByteCount = self.fileSize(at: location.url)", archive_section)
        self.assertIn("archivedByteCount > 0", archive_section)
        self.assertLess(
            archive_section.index("let archivedByteCount = self.fileSize(at: location.url)"),
            archive_section.index("mediaBox.completedResourcePath"),
        )

    def test_missing_complete_and_missing_rows_retry_from_media_box(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        reconcile = source[
            source.index("public func reconcile(") :
            source.index("private func resourceLocation(")
        ]
        self.assertIn("case .missing:", reconcile)
        complete = reconcile[
            reconcile.index("case .complete:") : reconcile.index("case .unavailable")
        ]
        self.assertIn("self.archiveRecord(record, resource: resource, mediaBox: mediaBox)", complete)
        self.assertIn("copyState: .missing", complete)
        missing = reconcile[reconcile.index("case .missing:") :]
        self.assertIn("self.archiveRecord(record, resource: resource, mediaBox: mediaBox)", missing)

    def test_media_records_carry_migration_safe_generation(self) -> None:
        models = MODELS.read_text(encoding="utf-8")
        self.assertIn("public let generation: Int64", models)
        self.assertIn("case generation", models)
        self.assertIn(
            "try container.decodeIfPresent(Int64.self, forKey: .generation) ?? 0",
            models,
        )
        store = STORE.read_text(encoding="utf-8")
        terminal = store[store.index("private func terminalRecord(") :]
        self.assertIn("generation: record.generation", terminal)

    def test_media_box_reports_only_successfully_unlinked_ids(self) -> None:
        source = MEDIA_BOX.read_text(encoding="utf-8")
        self.assertIn("didRemoveResourceIdsPipe", source)
        self.assertIn("didRemoveResourceIds", source)
        for token in (
            "let removedComplete = unlink(paths.complete) == 0",
            "let removedPartial = unlink(paths.partial) == 0",
            'let removedMeta = unlink(paths.partial + ".meta") == 0',
            "if removedComplete || removedPartial || removedMeta",
        ):
            self.assertGreaterEqual(source.count(token), 2, token)
        self.assertGreaterEqual(source.count("didRemoveResourceIdsPipe.putNext(removedIds)"), 2)

    def test_restore_uses_serial_queues_and_refuses_active_contexts(self) -> None:
        source = MEDIA_BOX.read_text(encoding="utf-8")
        self.assertIn("func restoreResourceData", source)
        self.assertIn("copyResourceDataFromArchive", source)
        self.assertIn("self.dataQueue.async", source)
        self.assertIn("self.statusQueue.async", source)
        self.assertIn("self.fileContexts[id] == nil", source)
        self.assertIn("context.status = .Local", source)

    def test_crypto_dependency_is_declared(self) -> None:
        source = BUILD.read_text(encoding="utf-8")
        self.assertIn("//submodules/CryptoUtils:CryptoUtils", source)


if __name__ == "__main__":
    unittest.main()
