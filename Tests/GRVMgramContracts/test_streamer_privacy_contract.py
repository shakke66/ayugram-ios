import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = ROOT / "submodules/AyuGramLib/Sources/AyuGramSettings.swift"
OTHER_PATH = ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift"
APPEARANCE_PATH = ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift"
CONTROLLER_PATH = ROOT / "submodules/TelegramUI/Sources/GRVMScreenCapturePrivacyController.swift"
APP_DELEGATE_PATH = ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift"


class StreamerPrivacyContractTests(unittest.TestCase):
    def test_setting_has_full_codable_chain_without_legacy_consent_migration(self) -> None:
        source = SETTINGS_PATH.read_text(encoding="utf-8")
        self.assertIn("public var streamerModeEnabled: Bool", source)
        self.assertIn("streamerModeEnabled: false", source)
        self.assertIn("streamerModeEnabled: Bool", source)
        self.assertIn("self.streamerModeEnabled = streamerModeEnabled", source)
        self.assertRegex(
            source,
            r'self\.streamerModeEnabled\s*=\s*try container\.decodeIfPresent\(Bool\.self, forKey: "streamerModeEnabled"\) \?\? false',
        )
        self.assertIn('try container.encode(self.streamerModeEnabled, forKey: "streamerModeEnabled")', source)
        self.assertIn('forKey: "showStreamerToggleInDrawer"', source)
        self.assertNotRegex(source, r"streamerModeEnabled\s*=\s*.*showStreamerToggleInDrawer")

    def test_other_settings_exposes_account_scoped_switch_with_honest_copy(self) -> None:
        source = OTHER_PATH.read_text(encoding="utf-8")
        self.assertIn("ItemListSwitchItem", source)
        self.assertIn("streamerModeEnabled", source)
        self.assertIn("updateGRVMSettings(accountId: context.account.peerId", source)
        self.assertRegex(source, r"recording|AirPlay|screen sharing")
        self.assertRegex(source, r"does not hide|doesn't hide|not hide")
        self.assertRegex(source, r"screenshots?")
        self.assertNotIn("showStreamerToggleInDrawer", source)

    def test_obsolete_drawer_producer_is_removed(self) -> None:
        source = APPEARANCE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("streamerInDrawer", source)
        self.assertNotIn("showStreamerToggleInDrawer", source)

    def test_public_per_window_capture_state_and_exact_predicate(self) -> None:
        source = CONTROLLER_PATH.read_text(encoding="utf-8")
        self.assertIn("public final class GRVMScreenCapturePrivacyController", source)
        self.assertIn("public init(window: UIWindow, enabled: Signal<Bool, NoError>)", source)
        self.assertIn("public func dispose()", source)
        self.assertIn("UIScreen.capturedDidChangeNotification", source)
        self.assertIn("queue: .main", source)
        self.assertIn("window.screen.isCaptured", source)
        self.assertIn("UIScreen.main.isCaptured", source)
        self.assertIn("#available(iOS 11.0, *)", source)
        self.assertRegex(
            source,
            r"static func shouldShowCover\(enabled: Bool, isCaptured: Bool\) -> Bool\s*\{\s*return enabled && isCaptured\s*\}",
        )
        expected = {
            (False, False): False,
            (False, True): False,
            (True, False): False,
            (True, True): True,
        }
        for inputs, result in expected.items():
            self.assertEqual(inputs[0] and inputs[1], result)

    def test_cover_layout_accessibility_and_disposal_are_complete(self) -> None:
        source = CONTROLLER_PATH.read_text(encoding="utf-8")
        self.assertIn("weak var window", source)
        self.assertIn("MetaDisposable", source)
        self.assertIn("notificationToken", source)
        self.assertIn("refreshCaptureState()", source)
        self.assertIn("window.bounds", source)
        self.assertIn("window.addSubview", source)
        self.assertIn(".flexibleWidth", source)
        self.assertIn(".flexibleHeight", source)
        self.assertIn("numberOfLines = 0", source)
        self.assertIn("textAlignment = .center", source)
        self.assertIn("isAccessibilityElement = true", source)
        self.assertIn("accessibilityViewIsModal = true", source)
        self.assertIn("UIAccessibility.post(notification: .screenChanged", source)
        self.assertIn("removeObserver", source)
        self.assertIn("settingsDisposable.dispose()", source)
        self.assertIn("coverView?.removeFromSuperview()", source)
        self.assertRegex(source, r"private var isDisposed = false")
        self.assertRegex(source, r"guard !self\.isDisposed else")
        self.assertRegex(source, r"deinit\s*\{\s*self\.dispose\(\)\s*\}")

    def test_app_delegate_owns_rebinds_refreshes_and_disposes_controller(self) -> None:
        source = APP_DELEGATE_PATH.read_text(encoding="utf-8")
        self.assertIn("private var grvmScreenCapturePrivacyController", source)
        self.assertIn("GRVMScreenCapturePrivacyController(window: window", source)
        self.assertIn("activeAccountContexts", source)
        self.assertIn("mapToSignal", source)
        self.assertIn("grvmSettings(accountId: primary.account.peerId", source)
        self.assertIn("return .single(false)", source)
        self.assertIn("distinctUntilChanged", source)
        self.assertIn("deliverOnMainQueue", source)
        self.assertIn("applicationWillResignActive", source)
        self.assertIn("applicationWillEnterForeground", source)
        self.assertGreaterEqual(source.count("grvmScreenCapturePrivacyController?.refreshCaptureState()"), 2)
        self.assertGreaterEqual(source.count("grvmScreenCapturePrivacyController?.dispose()"), 2)
        self.assertRegex(
            source,
            r"deinit\s*\{\s*self\.grvmScreenCapturePrivacyController\?\.dispose\(\)\s*self\.grvmScreenCapturePrivacyController = nil\s*\}",
        )

    def test_forbidden_capture_tricks_and_overclaims_are_absent(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (CONTROLLER_PATH, OTHER_PATH)
        )
        for forbidden in (
            "UITextField",
            "isSecureTextEntry",
            "userDidTakeScreenshotNotification",
            "UIApplicationUserDidTakeScreenshotNotification",
            "NSClassFromString",
            "value(forKey:",
            "UIWindow()",
            "prevents screenshots",
            "blocks screenshots",
            "screenshot prevention",
        ):
            self.assertNotIn(forbidden, sources)


if __name__ == "__main__":
    unittest.main()
