from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXPORT_PATH = ROOT / "submodules/TelegramUI/Sources/GRVMLocalCrashExport.swift"
APP_PATH = ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift"
FEATURES_PATH = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatures.swift"
OTHER_PATH = (
    ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift"
)


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


class CrashExportContractTests(unittest.TestCase):
    def test_public_interface_and_import_boundary_are_exact(self) -> None:
        text = source(EXPORT_PATH)
        imports = re.findall(r"^import (\S+)$", text, re.MULTILINE)
        self.assertEqual(
            imports,
            ["Foundation", "Postbox", "SwiftSignalKit", "TelegramCore"],
        )

        for fragment in (
            "public struct GRVMLocalCrashExportBundle {",
            "public let urls: [URL]",
            "public let fileCount: Int",
            "public let totalBytes: Int64",
            "public final class GRVMLocalCrashExport {",
            "public init(rootPath: String)",
            "public func beginForegroundSession(accountPeerId: PeerId)",
            "public func markSessionClean()",
            "public func previousSessionEndedUnexpectedly(accountPeerId: PeerId) -> Bool",
            "public func stageExport() -> Signal<GRVMLocalCrashExportBundle?, NoError>",
            "public func cleanup(_ bundle: GRVMLocalCrashExportBundle)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

        self.assertEqual(
            re.findall(r"^\s*public func (\w+)\(", text, re.MULTILINE),
            [
                "beginForegroundSession",
                "markSessionClean",
                "previousSessionEndedUnexpectedly",
                "stageExport",
                "cleanup",
            ],
        )
        self.assertEqual(
            re.findall(r"^\s*public let (\w+):", text, re.MULTILINE),
            ["urls", "fileCount", "totalBytes"],
        )

    def test_marker_is_atomic_corruption_safe_and_account_exact(self) -> None:
        text = source(EXPORT_PATH)
        for fragment in (
            'appendingPathComponent("grvm-local-crash", isDirectory: true)',
            'appendingPathComponent("session.json", isDirectory: false)',
            "let accountPeerId: Int64",
            "let foregroundStartedAt: Double",
            "let active: Bool",
            "accountPeerId.toInt64()",
            "JSONEncoder().encode",
            "JSONDecoder().decode",
            "options: .atomic",
            "marker.active && marker.accountPeerId == accountPeerId.toInt64()",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        for forbidden in ("try!", "fatalError(", "preconditionFailure("):
            self.assertNotIn(forbidden, text)

    def test_initializer_builds_marker_urls_before_assigning_stored_properties(self) -> None:
        text = source(EXPORT_PATH)
        init_start = text.find("public init(rootPath: String)")
        init_end = text.find("public func beginForegroundSession", init_start)
        self.assertGreaterEqual(init_start, 0)
        self.assertGreater(init_end, init_start)
        initializer = text[init_start:init_end]
        self.assertIn(
            'let markerDirectoryURL = rootURL.appendingPathComponent("grvm-local-crash"',
            initializer,
        )
        self.assertIn("self.markerDirectoryURL = markerDirectoryURL", initializer)
        self.assertIn(
            'self.markerURL = markerDirectoryURL.appendingPathComponent("session.json"',
            initializer,
        )

    def test_export_sources_are_logger_only_and_never_networked(self) -> None:
        text = source(EXPORT_PATH)
        for fragment in (
            "Logger.shared.sync()",
            "Logger.shared.collectLogs()",
            "Logger.shared.collectShortLogFiles()",
            "combineLatest",
        ):
            self.assertIn(fragment, text)

        lowered = text.lower()
        for forbidden in (
            "urlsession",
            "appcenter",
            "github.com",
            "ayugram",
            "analytics",
            ".ips",
            "fetchedmediaresource",
            "interactivefetched",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)

    def test_canonical_root_containment_rejects_prefix_siblings(self) -> None:
        def is_contained(root: str, candidate: str) -> bool:
            return candidate == root or candidate.startswith(root + "/")

        cases = (
            ("/app/root", "/app/root/logs/log-1", True),
            ("/app/root", "/app/root", True),
            ("/app/root", "/app/root-evil/log-1", False),
            ("/app/root", "/app/other/log-1", False),
        )
        for root, candidate, expected in cases:
            with self.subTest(candidate=candidate):
                self.assertEqual(is_contained(root, candidate), expected)

        text = source(EXPORT_PATH)
        for fragment in (
            "resolvingSymlinksInPath()",
            ".isSymbolicLinkKey",
            ".isRegularFileKey",
            ".fileSizeKey",
            "values.isSymbolicLink == false",
            "canonicalValues.isRegularFile == true",
            "fileSize >= 0",
            'candidatePath == rootPath || candidatePath.hasPrefix(rootPath + "/")',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_newest_first_selection_is_bounded_and_skips_oversize_files(self) -> None:
        mib = 1024 * 1024
        candidates = [17 * mib, 10 * mib, 7 * mib, 6 * mib, 1 * mib]
        selected: list[int] = []
        total = 0
        for size in candidates:
            if len(selected) >= 8:
                break
            if size > 16 * mib - total:
                continue
            selected.append(size)
            total += size
        self.assertEqual(selected, [10 * mib, 6 * mib])
        self.assertEqual(total, 16 * mib)

        text = source(EXPORT_PATH)
        for fragment in (
            "maximumFileCount = 8",
            "maximumTotalBytes: Int64 = 16 * 1024 * 1024",
            ".contentModificationDateKey",
            ".creationDateKey",
            "lhs.date > rhs.date",
            "if fileSize > maximumTotalBytes - totalBytes",
            "continue",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_staging_is_unique_immutable_bounded_and_cleanup_is_idempotent(self) -> None:
        text = source(EXPORT_PATH)
        for fragment in (
            "FileManager.default.temporaryDirectory",
            r'appendingPathComponent("grvm-local-crash-\(UUID().uuidString)"',
            "copyItem(at: candidate.url, to: destinationURL)",
            "let directoryURL: URL",
            "urls: copiedURLs",
            "fileCount: copiedURLs.count",
            "totalBytes: totalBytes",
            "try? FileManager.default.removeItem(at: bundle.directoryURL)",
            "if copiedURLs.isEmpty",
            "return nil",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        self.assertRegex(
            text,
            r"createDirectory\(\s*at: stagingDirectory,",
        )


class CrashLifecycleContractTests(unittest.TestCase):
    def test_account_aware_feature_bridge_is_exact(self) -> None:
        text = source(FEATURES_PATH)
        self.assertIn(
            "public static var exportLocalLogs: ((PeerId) -> Void)?",
            text,
        )

    def test_exporter_is_created_after_logger_and_remote_start_is_absent(self) -> None:
        text = source(APP_PATH)
        logger_index = text.find("Logger.setSharedLogger")
        exporter_index = text.find("GRVMLocalCrashExport(rootPath: rootPath)")
        self.assertGreaterEqual(logger_index, 0)
        self.assertGreater(exporter_index, logger_index)
        self.assertNotIn("AppCenter.start", text)

    def test_primary_account_settings_lifecycle_is_guarded_and_ordered(self) -> None:
        text = source(APP_PATH)
        for fragment in (
            "private var grvmCrashPrimaryAccountPeerId: PeerId?",
            "private var grvmCrashReportingEnabled = false",
            "private var grvmCrashForegroundMarkerActive = false",
            "private var grvmCrashOfferHandled = false",
            "private var grvmCrashExportInFlight = false",
            "private let grvmCrashSettingsDisposable = MetaDisposable()",
            "activeAccountContexts",
            "grvmSettings(accountId: accountPeerId, accountManager: accountManager)",
            "settings.crashReportingEnabled",
            "markSessionClean()",
            "removeSessionMarker()",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

        foreground_start = text.find(
            "private func updateGRVMLocalCrashForegroundSession()"
        )
        foreground_end = text.find(
            "private func markGRVMLocalCrashSessionClean()", foreground_start
        )
        self.assertGreaterEqual(foreground_start, 0)
        self.assertGreater(foreground_end, foreground_start)
        foreground = text[foreground_start:foreground_end]
        self.assertLess(
            foreground.find("previousSessionEndedUnexpectedly"),
            foreground.find("beginForegroundSession"),
        )
        self.assertIn("!self.grvmCrashForegroundMarkerActive", foreground)

        background = text[text.find("func applicationDidEnterBackground"):]
        background = background[: background.find("func applicationWillEnterForeground")]
        self.assertIn("markGRVMLocalCrashSessionClean()", background)

        terminate = text[text.find("func applicationWillTerminate"):]
        terminate = terminate[: terminate.find("func application(")]
        self.assertIn("markGRVMLocalCrashSessionClean()", terminate)

    def test_first_no_primary_snapshot_removes_a_stale_marker(self) -> None:
        text = source(APP_PATH)
        update_start = text.find("private func updateGRVMLocalCrashPrimaryAccount(")
        update_end = text.find(
            "private func updateGRVMLocalCrashForegroundSession()", update_start
        )
        self.assertGreaterEqual(update_start, 0)
        self.assertGreater(update_end, update_start)
        update = text[update_start:update_end]

        no_primary_index = update.find("guard let accountPeerId else")
        same_account_index = update.find(
            "guard self.grvmCrashPrimaryAccountPeerId != accountPeerId"
        )
        self.assertGreaterEqual(no_primary_index, 0)
        self.assertGreater(same_account_index, no_primary_index)
        no_primary = update[no_primary_index:same_account_index]
        self.assertIn("self.grvmCrashSettingsDisposable.set(nil)", no_primary)
        self.assertIn("self.grvmLocalCrashExport?.removeSessionMarker()", no_primary)

    def test_automatic_offer_is_one_shot_local_and_cleans_every_ui_path(self) -> None:
        text = source(APP_PATH)
        for fragment in (
            "guard !self.grvmCrashOfferHandled",
            "self.grvmCrashOfferHandled = true",
            "ByteCountFormatter.string",
            'UIAlertAction(title: "Not Now"',
            'UIAlertAction(title: "Export Local Logs"',
            "preferredStyle: .alert",
            "completionWithItemsHandler",
            "popoverPresentationController?.sourceView",
            "popoverPresentationController?.sourceRect",
            "self.grvmLocalCrashExport?.cleanup(bundle)",
            "self.grvmCrashExportInFlight = false",
            "Nothing is uploaded automatically.",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        self.assertIn("unexpectedly", text.lower())

    def test_automatic_offer_rechecks_account_and_setting_before_share(self) -> None:
        text = source(APP_PATH)
        offer_start = text.find("private func presentGRVMLocalCrashOffer(")
        offer_end = text.find("private func presentGRVMLocalCrashShare", offer_start)
        self.assertGreaterEqual(offer_start, 0)
        self.assertGreater(offer_end, offer_start)
        offer = text[offer_start:offer_end]
        self.assertIn("accountPeerId: PeerId", offer)

        action_index = offer.find(
            'UIAlertAction(title: "Export Local Logs", style: .default'
        )
        account_index = offer.find(
            "self.grvmCrashPrimaryAccountPeerId == accountPeerId", action_index
        )
        enabled_index = offer.find("self.grvmCrashReportingEnabled", action_index)
        share_index = offer.find("self.presentGRVMLocalCrashShare(bundle)", action_index)
        self.assertGreaterEqual(action_index, 0)
        self.assertGreater(account_index, action_index)
        self.assertGreater(enabled_index, action_index)
        self.assertGreater(share_index, max(account_index, enabled_index))

    def test_manual_export_rechecks_exact_account_setting_and_inflight_gate(self) -> None:
        text = source(APP_PATH)
        bridge_match = re.search(
            r"AyuGramFeatures\.exportLocalLogs\s*=\s*\{(?P<body>.*?)\n\s*\}",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(bridge_match)
        bridge = bridge_match.group("body") if bridge_match else ""
        self.assertIn("accountPeerId", bridge)
        self.assertIn("requestManualGRVMLocalCrashExport", bridge)

        manual_start = text.find("private func requestManualGRVMLocalCrashExport")
        manual_end = text.find("private func", manual_start + 1)
        manual = text[manual_start:manual_end]
        self.assertIn(
            "grvmSettings(accountId: accountPeerId, accountManager: accountManager)",
            manual,
        )
        self.assertIn("settings.crashReportingEnabled", manual)
        self.assertIn("guard !self.grvmCrashExportInFlight", manual)

    def test_manual_export_rechecks_setting_after_asynchronous_staging(self) -> None:
        text = source(APP_PATH)
        stage_start = text.find("private func stageGRVMLocalCrashExport(")
        stage_end = text.find("private func presentGRVMLocalCrashOffer", stage_start)
        self.assertGreaterEqual(stage_start, 0)
        self.assertGreater(stage_end, stage_start)
        stage = text[stage_start:stage_end]
        self.assertIn(
            "recheckManualGRVMLocalCrashExport(accountPeerId: accountPeerId, bundle: bundle)",
            stage,
        )

        recheck_start = text.find("private func recheckManualGRVMLocalCrashExport(")
        recheck_end = text.find("private func presentGRVMLocalCrashOffer", recheck_start)
        self.assertGreaterEqual(recheck_start, 0)
        self.assertGreater(recheck_end, recheck_start)
        recheck = text[recheck_start:recheck_end]
        settings_index = recheck.find(
            "grvmSettings(accountId: accountPeerId, accountManager: accountManager)"
        )
        enabled_index = recheck.find("settings.crashReportingEnabled")
        share_index = recheck.find("presentGRVMLocalCrashShare(bundle)")
        self.assertGreaterEqual(settings_index, 0)
        self.assertGreater(enabled_index, settings_index)
        self.assertGreater(share_index, enabled_index)


class ResetContractTests(unittest.TestCase):
    def test_manual_row_is_visible_only_when_the_exact_setting_is_enabled(self) -> None:
        text = source(OTHER_PATH)
        for fragment in (
            "case exportLocalLogs(PresentationTheme)",
            'title: "Export Local Logs"',
            "if settings.crashReportingEnabled {",
            "entries.append(.exportLocalLogs",
            "AyuGramFeatures.exportLocalLogs?(arguments.context.account.peerId)",
            "Nothing is uploaded automatically.",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        self.assertLess(
            text.find("if settings.crashReportingEnabled {"),
            text.find("entries.append(.exportLocalLogs"),
        )

    def test_reset_requires_destructive_confirmation_and_resets_one_account(self) -> None:
        text = source(OTHER_PATH)
        reset_start = text.find("resetSettings: {")
        reset_end = text.find("\n    )", reset_start)
        self.assertGreaterEqual(reset_start, 0)
        self.assertGreater(reset_end, reset_start)
        reset = text[reset_start:reset_end]

        alert_index = reset.find("textAlertController")
        destructive_index = reset.find(".destructiveAction")
        update_index = reset.find("updateGRVMSettings")
        self.assertGreaterEqual(alert_index, 0)
        self.assertGreater(destructive_index, alert_index)
        self.assertGreater(update_index, destructive_index)
        self.assertEqual(reset.count("updateGRVMSettings"), 1)
        self.assertIn(".genericAction", reset)
        self.assertIn("accountId: context.account.peerId", reset)
        self.assertIn("accountManager: context.sharedContext.accountManager", reset)
        self.assertIn("AyuGramSettings.defaultSettings", reset)

        for forbidden in (
            "updateAyuGramSettings(accountManager:",
            "clearDeleted",
            "archive",
            "mediaBox",
            "logout",
            "accountRecords",
            "TelegramUIPreferences",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, reset)


if __name__ == "__main__":
    unittest.main()
