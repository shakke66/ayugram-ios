import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = ROOT / "submodules/AyuGramLib/Sources/GRVMMediaResourceCollector.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift"
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
        self.assertIn("mediaBox.completedResourcePath", reconcile_section)
        self.assertIn("copyState: .complete", reconcile_section)
        self.assertIn("copyState: .unavailable", reconcile_section)
        self.assertNotIn("try? self.fileManager.removeItem", source)

        references_section = reconcile_section[
            reconcile_section.index("let referencedRelativePaths") :
            reconcile_section.index("let blobsURL")
        ]
        self.assertIn("record.copyState == .copying", references_section)
        self.assertIn("self.resourceLocation(", references_section)

    def test_archive_signal_schedules_shared_copy_helper(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        archive_section = source[
            source.index("public func archive(") :
            source.index("public func restore(")
        ]
        self.assertIn("private func archiveRecord(", source)
        self.assertIn("self.archiveRecord(", archive_section)
        self.assertIn("subscriber.putNext", archive_section)

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
