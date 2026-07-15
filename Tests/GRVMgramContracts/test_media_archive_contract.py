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
