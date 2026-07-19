from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    path = ROOT / relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


class SavedMusicColorContractTests(unittest.TestCase):
    def test_largest_preview_uses_pixel_area_for_cross_axis_sizes(self) -> None:
        sizes = [(320, 100), (200, 200)]
        self.assertEqual(max(sizes, key=lambda size: size[0] * size[1]), (200, 200))

        text = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/"
            "GRVMSavedMusicColor.swift"
        )
        self.assertIn("file.previewRepresentations", text)
        self.assertRegex(
            text,
            re.compile(
                r"Int64\([^\n]*dimensions\.width\)\s*\*\s*"
                r"Int64\([^\n]*dimensions\.height\)",
            ),
        )
        self.assertNotIn("largestImageRepresentation", text)

    def test_hsb_clamping_matches_boundary_table(self) -> None:
        cases = [
            ((0.10, 0.05), (0.28, 0.18)),
            ((0.28, 0.18), (0.28, 0.18)),
            ((0.50, 0.30), (0.50, 0.30)),
            ((0.65, 0.42), (0.65, 0.42)),
            ((0.90, 0.80), (0.65, 0.42)),
        ]
        for (saturation, brightness), expected in cases:
            with self.subTest(saturation=saturation, brightness=brightness):
                actual = (
                    min(0.65, max(0.28, saturation)),
                    min(0.42, max(0.18, brightness)),
                )
                self.assertEqual(actual, expected)

        text = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/"
            "GRVMSavedMusicColor.swift"
        )
        for fragment in [
            "getHue(&hue, saturation: &saturation, brightness: &brightness, alpha: &alpha)",
            "min(0.65, max(0.28, saturation))",
            "min(0.42, max(0.18, brightness))",
            "hue: hue",
            "alpha: 1.0",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_setting_is_fully_codable_with_true_fallback(self) -> None:
        text = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        for fragment in [
            "public var adaptiveCoverColor: Bool",
            "adaptiveCoverColor: true",
            "adaptiveCoverColor: Bool,",
            "self.adaptiveCoverColor = adaptiveCoverColor",
            'decodeIfPresent(Bool.self, forKey: "adaptiveCoverColor") ?? true',
            'encode(self.adaptiveCoverColor, forKey: "adaptiveCoverColor")',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_hook_reads_only_the_exact_account_snapshot(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        self.assertIn(
            "public static var shouldUseAdaptiveSavedMusicCover: ((PeerId) -> Bool)?",
            hooks,
        )

        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        match = re.search(
            r"AyuGramHooks\.shouldUseAdaptiveSavedMusicCover\s*=\s*"
            r"\{(?P<body>.*?)\n\s*\}",
            manager,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body") if match is not None else ""
        self.assertIn(
            "self?.settings(accountPeerId: accountPeerId)?.adaptiveCoverColor ?? true",
            body,
        )
        self.assertNotIn("currentSettings", body)
        self.assertNotIn("primaryService()", body)

    def test_artwork_probe_is_local_only_and_rejects_incomplete_data(self) -> None:
        text = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/"
            "GRVMSavedMusicColor.swift"
        )
        for fragment in [
            "import Foundation",
            "import UIKit",
            "import Postbox",
            "import TelegramCore",
            "import TelegramPresentationData",
            "import SwiftSignalKit",
            "representation.resource.id.stringRepresentation",
            "mediaBox.resourceData(resource, attemptSynchronously: true)",
            "|> take(1)",
            "guard data.complete",
            "UIImage(contentsOfFile: data.path)",
            "averageColor(from: image)",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

        lowered = text.lower()
        for forbidden in [
            "urlsession",
            "itunes",
            "fetchedmediaresource",
            "interactivefetched",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)
        self.assertNotRegex(lowered, r"\bfetch(?:ed|ing)?\b")

    def test_cache_is_resource_scoped_bounded_and_success_only(self) -> None:
        text = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/"
            "GRVMSavedMusicColor.swift"
        )
        for fragment in [
            "static let colorCache = Atomic<[String: UIColor]>(value: [:])",
            "static let colorCacheLimit = 64",
            "colorCache.with",
            "updated.count >= self.colorCacheLimit",
            "updated.removeValue(forKey:",
            "updated[resourceId] = color",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        self.assertNotRegex(text, r"updated\[resourceId\]\s*=\s*nil")

    def test_header_cancels_stale_requests_and_keeps_stock_fallback(self) -> None:
        text = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/"
            "PeerInfoHeaderNode.swift"
        )
        for fragment in [
            "struct GRVMSavedMusicColorRequest: Equatable",
            "let accountPeerId: PeerId",
            "let fileId: MediaId",
            "let resourceId: String",
            "savedMusicColorDisposable = MetaDisposable()",
            "savedMusicColorRequest: GRVMSavedMusicColorRequest?",
            "savedMusicColor: UIColor?",
            "AyuGramHooks.shouldUseAdaptiveSavedMusicCover?(self.context.account.peerId) ?? true",
            "context.account.postbox.mediaBox",
            "self.savedMusicColorDisposable.set(nil)",
            "guard self.savedMusicColorRequest == request",
            "guard receivedResourceId == request.resourceId",
            "currentFile.fileId == request.fileId",
            "currentResourceId == receivedResourceId",
            "self.requestUpdateLayout?(false)",
            "self.savedMusicColorDisposable.dispose()",
            "AnyComponent(Rectangle(color: adaptiveSavedMusicColor))",
            "background: nil",
            "adaptiveSavedMusicColor != nil ? .white : (isOverlay ? .white : presentationData.theme.list.itemAccentColor)",
            "adaptiveSavedMusicColor != nil ? UIColor.white.withAlphaComponent(0.7) : (isOverlay ? UIColor.white.withAlphaComponent(0.7) : presentationData.theme.list.itemSecondaryTextColor)",
            "adaptiveSavedMusicColor != nil ? .white : (isOverlay ? .white : presentationData.theme.list.itemSecondaryTextColor)",
            "musicBackground.backgroundColor = .white",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

        self.assertNotIn(
            "musicBackground.backgroundColor = adaptiveSavedMusicColor", text
        )
        self.assertNotRegex(
            text,
            r"backgroundBannerView\.backgroundColor\s*=\s*adaptiveSavedMusicColor",
        )

    def test_appearance_switch_precedes_folders_and_shifts_stable_ids(self) -> None:
        text = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift"
        )
        for fragment in [
            "case adaptiveCoverColor(PresentationTheme, Bool)",
            "case .adaptiveCoverColor: return 13",
            "case .foldersHeader: return 14",
            "case .hideFolderCounters: return 15",
            "case .hideAllChats: return 16",
            "case .drawerHeader: return 17",
            "case .ghostInDrawer: return 18",
            "arguments.updateBool(\\.adaptiveCoverColor, v)",
            "settings.adaptiveCoverColor",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

        switch_entry = "entries.append(.adaptiveCoverColor"
        folders_entry = "entries.append(.foldersHeader"
        self.assertIn(switch_entry, text)
        self.assertIn(folders_entry, text)
        self.assertLess(text.index(switch_entry), text.index(folders_entry))


if __name__ == "__main__":
    unittest.main()
