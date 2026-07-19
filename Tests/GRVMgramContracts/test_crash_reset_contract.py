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
            "copyItem(at: revalidatedCandidate.url, to: destinationURL)",
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

    def test_source_is_revalidated_immediately_before_copy(self) -> None:
        text = source(EXPORT_PATH)
        loop_start = text.find("for candidate in candidates {")
        loop_end = text.find("if copiedURLs.isEmpty", loop_start)
        self.assertGreaterEqual(loop_start, 0)
        self.assertGreater(loop_end, loop_start)
        copy_loop = text[loop_start:loop_end]

        revalidate_index = copy_loop.find(
            "self.safeCandidate(path: candidate.url.path)"
        )
        size_index = copy_loop.find("let fileSize = revalidatedCandidate.fileSize")
        copy_index = copy_loop.find(
            "copyItem(at: revalidatedCandidate.url, to: destinationURL)"
        )
        self.assertGreaterEqual(revalidate_index, 0)
        self.assertGreater(size_index, revalidate_index)
        self.assertGreater(copy_index, size_index)
        self.assertNotIn("copyItem(at: candidate.url", copy_loop)


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
            "owner.finish()",
            "self.grvmCrashExportInFlight = false",
            "Nothing is uploaded automatically.",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        self.assertIn("unexpectedly", text.lower())

    def test_pending_unexpected_session_retries_after_inactive_staging(self) -> None:
        state = {
            "pending": 1001,
            "offer_handled": False,
            "in_flight": True,
            "active": False,
        }

        # A staged bundle that finishes while inactive is discarded, but the
        # unexpected-session fact remains pending for the next active event.
        state["in_flight"] = False
        self.assertEqual(state["pending"], 1001)
        self.assertFalse(state["offer_handled"])
        state["active"] = True
        if state["pending"] is not None and not state["offer_handled"]:
            state["in_flight"] = True
        self.assertTrue(state["in_flight"])

        text = source(APP_PATH)
        self.assertIn(
            "private var grvmCrashPendingUnexpectedAccountPeerId: PeerId?",
            text,
        )
        foreground_start = text.find(
            "private func updateGRVMLocalCrashForegroundSession()"
        )
        foreground_end = text.find(
            "private func markGRVMLocalCrashSessionClean()", foreground_start
        )
        foreground = text[foreground_start:foreground_end]
        pending_index = max(
            foreground.find(
                "self.grvmCrashPendingUnexpectedAccountPeerId = accountPeerId"
            ),
            foreground.find(
                "self.beginGRVMLocalCrashPendingUnexpectedSession(accountPeerId: accountPeerId)"
            ),
        )
        stage_index = foreground.find(
            "self.stageGRVMLocalCrashExport(accountPeerId: accountPeerId, automatic: true)"
        )
        self.assertGreaterEqual(pending_index, 0)
        self.assertGreater(stage_index, pending_index)
        self.assertNotIn("self.grvmCrashOfferHandled = true", foreground)
        self.assertIn(
            "self.grvmCrashPendingUnexpectedAccountPeerId == accountPeerId",
            foreground,
        )

        primary_start = text.find("private func updateGRVMLocalCrashPrimaryAccount(")
        primary_end = text.find(
            "private func updateGRVMLocalCrashForegroundSession()", primary_start
        )
        primary = text[primary_start:primary_end]
        self.assertGreaterEqual(
            primary.count("self.clearGRVMLocalCrashPendingUnexpectedSession()"),
            2,
        )
        self.assertIn(
            "self.clearGRVMLocalCrashPendingUnexpectedSession()",
            primary[primary.find("if settings.crashReportingEnabled"):],
        )

    def test_offer_handled_is_set_only_for_presented_offer_or_final_no_logs(self) -> None:
        text = source(APP_PATH)
        assignments = [
            match.start()
            for match in re.finditer(
                r"self\.grvmCrashOfferHandled\s*=\s*true", text
            )
        ]
        self.assertEqual(len(assignments), 2)

        no_logs_start = text.find("private func finishGRVMLocalCrashExportWithoutLogs(")
        no_logs_end = text.find("private func", no_logs_start + 1)
        presented_start = text.find("private func markGRVMLocalCrashOfferPresented(")
        presented_end = text.find("private func", presented_start + 1)
        self.assertGreaterEqual(no_logs_start, 0)
        self.assertGreater(no_logs_end, no_logs_start)
        self.assertGreaterEqual(presented_start, 0)
        self.assertGreater(presented_end, presented_start)
        self.assertIn(
            "self.grvmCrashOfferHandled = true",
            text[no_logs_start:no_logs_end],
        )
        self.assertIn(
            "self.grvmCrashOfferHandled = true",
            text[presented_start:presented_end],
        )

    def test_terminal_presentation_owner_cleans_once_and_tokens_stale_callbacks(self) -> None:
        current_request = "new"
        in_flight = True

        def finish(request_id: str) -> None:
            nonlocal current_request, in_flight
            if current_request != request_id:
                return
            current_request = ""
            in_flight = False

        finish("old")
        self.assertEqual(current_request, "new")
        self.assertTrue(in_flight)
        finish("new")
        self.assertEqual(current_request, "")
        self.assertFalse(in_flight)

        text = source(APP_PATH)
        owner_start = text.find(
            "private final class GRVMLocalCrashExportPresentationOwner"
        )
        owner_end = text.find("@objc(AppDelegate)", owner_start)
        self.assertGreaterEqual(owner_start, 0)
        self.assertGreater(owner_end, owner_start)
        owner = text[owner_start:owner_end]
        for fragment in (
            "UIAdaptivePresentationControllerDelegate",
            "let id: UUID",
            "let bundle: GRVMLocalCrashExportBundle",
            "private var isFinished = false",
            "guard !self.isFinished else",
            "self.isFinished = true",
            "self.exporter.cleanup(self.bundle)",
            "self.finished(self.id)",
            "func presentationControllerDidDismiss",
            "self.finish()",
            "deinit",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, owner)

        self.assertIn("private var grvmCrashExportRequestId: UUID?", text)
        finish_start = text.find("private func finishGRVMLocalCrashExportRequest(")
        finish_end = text.find("private func", finish_start + 1)
        finish_window = text[finish_start:finish_end]
        self.assertIn(
            "guard self.grvmCrashExportRequestId == requestId else",
            finish_window,
        )
        self.assertLess(
            finish_window.find("guard self.grvmCrashExportRequestId == requestId"),
            finish_window.find("self.grvmCrashExportInFlight = false"),
        )

        verify_start = text.find("private func verifyGRVMLocalCrashPresentation(")
        verify_end = text.find("private func", verify_start + 1)
        verify = text[verify_start:verify_end]
        self.assertIn("weak controller", verify)
        self.assertIn("controller.presentingViewController != nil", verify)
        self.assertIn("owner.finish()", verify)

        offer_start = text.find("private func presentGRVMLocalCrashOffer(")
        offer_end = text.find("private func presentGRVMLocalCrashShare", offer_start)
        offer = text[offer_start:offer_end]
        self.assertIn("owner: GRVMLocalCrashExportPresentationOwner", offer)
        self.assertIn("owner.finish()", offer)
        self.assertIn("verifyGRVMLocalCrashPresentation", offer)

        share_start = text.find("private func presentGRVMLocalCrashShare(")
        share_end = text.find("private func", share_start + 1)
        share = text[share_start:share_end]
        self.assertIn("owner: GRVMLocalCrashExportPresentationOwner", share)
        self.assertIn("controller.completionWithItemsHandler", share)
        self.assertIn("owner.finish()", share)
        self.assertIn("controller.presentationController?.delegate = owner", share)
        self.assertIn("verifyGRVMLocalCrashPresentation", share)

    def test_invalidated_physical_offer_dismisses_before_cleanup(self) -> None:
        text = source(APP_PATH)
        owner_start = text.find(
            "private final class GRVMLocalCrashExportPresentationOwner"
        )
        owner_end = text.find("@objc(AppDelegate)", owner_start)
        owner = text[owner_start:owner_end]
        dismiss_start = owner.find("func dismissAndFinish(_ controller: UIViewController)")
        dismiss_end = owner.find("\n    }", dismiss_start)
        self.assertGreaterEqual(dismiss_start, 0)
        self.assertGreater(dismiss_end, dismiss_start)
        dismiss = owner[dismiss_start:dismiss_end]
        presenter_guard = dismiss.find(
            "guard controller.presentingViewController != nil else"
        )
        immediate_finish = dismiss.find("self.finish()", presenter_guard)
        immediate_return = dismiss.find("return", immediate_finish)
        dismiss_call = dismiss.find(
            "controller.dismiss(animated: false", immediate_return
        )
        completion = dismiss.find("completion: {", dismiss_call)
        completion_finish = dismiss.find("self.finish()", completion)
        self.assertGreaterEqual(presenter_guard, 0)
        self.assertGreater(immediate_finish, presenter_guard)
        self.assertGreater(immediate_return, immediate_finish)
        self.assertGreater(dismiss_call, immediate_return)
        self.assertGreater(completion, dismiss_call)
        self.assertGreater(completion_finish, completion)
        self.assertNotIn("completion: nil", dismiss)

        verify_start = text.find("private func verifyGRVMLocalCrashPresentation(")
        verify_end = text.find("private func", verify_start + 1)
        verify = text[verify_start:verify_end]
        self.assertIn("presented: @escaping () -> Bool", verify)
        physical_index = verify.find("controller.presentingViewController != nil")
        invalid_index = verify.find("guard presented() else")
        dismiss_index = verify.find("owner.dismissAndFinish(controller)", invalid_index)
        self.assertGreaterEqual(physical_index, 0)
        self.assertGreater(invalid_index, physical_index)
        self.assertGreater(dismiss_index, invalid_index)

        offer_start = text.find("private func presentGRVMLocalCrashOffer(")
        offer_end = text.find("private func markGRVMLocalCrashOfferPresented", offer_start)
        offer = text[offer_start:offer_end]
        self.assertIn("return self.markGRVMLocalCrashOfferPresented(", offer)
        self.assertNotIn("owner.finish()\n                return", offer[offer.find("presented:"):])

    def test_confirmed_automatic_ui_is_cancelled_only_by_account_or_setting(self) -> None:
        confirmed = {"visible": True, "offer_handled": True}
        confirmed_after_resign = dict(confirmed)
        self.assertTrue(confirmed_after_resign["visible"])
        self.assertTrue(confirmed_after_resign["offer_handled"])
        confirmed["visible"] = False
        self.assertFalse(confirmed["visible"])

        text = source(APP_PATH)
        for fragment in (
            "let automaticAccountPeerId: PeerId?",
            "private weak var grvmCrashAutomaticPresentationController: UIViewController?",
            "private weak var grvmCrashAutomaticPresentationOwner: GRVMLocalCrashExportPresentationOwner?",
            "private var grvmCrashAutomaticPresentationRequestId: UUID?",
        ):
            self.assertIn(fragment, text)

        primary_start = text.find("private func updateGRVMLocalCrashPrimaryAccount(")
        primary_end = text.find(
            "private func updateGRVMLocalCrashForegroundSession()", primary_start
        )
        primary = text[primary_start:primary_end]
        self.assertGreaterEqual(
            primary.count("self.cancelGRVMLocalCrashAutomaticPresentation()"),
            2,
        )

        cancel_start = text.find("private func cancelGRVMLocalCrashAutomaticPresentation(")
        cancel_end = text.find("private func", cancel_start + 1)
        cancel = text[cancel_start:cancel_end]
        self.assertIn("owner.dismissAndFinish(controller)", cancel)
        self.assertIn("owner.finish()", cancel)

        offer_start = text.find("private func presentGRVMLocalCrashOffer(")
        offer_end = text.find("private func markGRVMLocalCrashOfferPresented", offer_start)
        share_start = text.find("private func presentGRVMLocalCrashShare(")
        share_end = text.find("private func verifyGRVMLocalCrashPresentation", share_start)
        self.assertIn(
            "self.trackGRVMLocalCrashAutomaticPresentation(controller: controller, owner: owner)",
            text[offer_start:offer_end],
        )
        self.assertIn(
            "self.trackGRVMLocalCrashAutomaticPresentation(controller: controller, owner: owner)",
            text[share_start:share_end],
        )

        resign_start = text.find("func applicationWillResignActive(")
        resign_end = text.find("func applicationDidEnterBackground", resign_start)
        resign = text[resign_start:resign_end]
        self.assertNotIn("cancelGRVMLocalCrashAutomaticPresentation", resign)
        self.assertNotIn("grvmCrashOfferHandled = false", resign)

    def test_pending_event_bounds_offer_presentation_across_active_cycles(self) -> None:
        attempts_remaining = 2
        scheduled_retries = 0

        # Staging that completes while inactive never reaches UIKit and does
        # not consume either physical presentation attempt.
        is_active = False
        if is_active:
            attempts_remaining -= 1
        self.assertEqual(attempts_remaining, 2)

        # The initial physical failure schedules the sole retry. Repeated
        # active callbacks do not replenish the event-owned budget.
        attempts_remaining -= 1
        if attempts_remaining > 0:
            scheduled_retries += 1
        for _ in range(3):
            pass
        attempts_remaining -= 1
        if attempts_remaining > 0:
            scheduled_retries += 1
        self.assertEqual(scheduled_retries, 1)
        self.assertEqual(attempts_remaining, 0)

        text = source(APP_PATH)
        self.assertIn(
            "private var grvmCrashOfferPresentationAttemptsRemaining = 0", text
        )
        self.assertNotIn("grvmCrashPresentationRetryAvailable", text)
        self.assertNotIn("grvmCrashPresentationRetryCycleId", text)

        begin_start = text.find(
            "private func beginGRVMLocalCrashPendingUnexpectedSession("
        )
        begin_end = text.find("private func", begin_start + 1)
        self.assertGreaterEqual(begin_start, 0)
        begin = text[begin_start:begin_end]
        self.assertIn(
            "self.grvmCrashPendingUnexpectedAccountPeerId = accountPeerId", begin
        )
        self.assertIn("self.grvmCrashOfferPresentationAttemptsRemaining = 2", begin)

        clear_start = text.find(
            "private func clearGRVMLocalCrashPendingUnexpectedSession()"
        )
        clear_end = text.find("private func", clear_start + 1)
        clear = text[clear_start:clear_end]
        self.assertIn("self.grvmCrashOfferPresentationAttemptsRemaining = 0", clear)

        for terminal_function in (
            "private func finishGRVMLocalCrashExportWithoutLogs(",
            "private func markGRVMLocalCrashOfferPresented(",
        ):
            terminal_start = text.find(terminal_function)
            terminal_end = text.find("private func", terminal_start + 1)
            terminal = text[terminal_start:terminal_end]
            self.assertIn(
                "self.clearGRVMLocalCrashPendingUnexpectedSession()", terminal
            )
            self.assertNotIn(
                "self.grvmCrashPendingUnexpectedAccountPeerId = nil", terminal
            )

        foreground_start = text.find(
            "private func updateGRVMLocalCrashForegroundSession()"
        )
        foreground_end = text.find("private func", foreground_start + 1)
        foreground = text[foreground_start:foreground_end]
        begin_index = foreground.find(
            "self.beginGRVMLocalCrashPendingUnexpectedSession(accountPeerId: accountPeerId)"
        )
        budget_index = foreground.find(
            "self.grvmCrashOfferPresentationAttemptsRemaining > 0"
        )
        stage_index = foreground.find(
            "self.stageGRVMLocalCrashExport(accountPeerId: accountPeerId, automatic: true)"
        )
        self.assertGreaterEqual(begin_index, 0)
        self.assertGreater(budget_index, begin_index)
        self.assertGreater(stage_index, budget_index)

        stage_start = text.find("private func stageGRVMLocalCrashExport(")
        stage_end = text.find("private func finishGRVMLocalCrashExportWithoutLogs", stage_start)
        self.assertNotIn(
            "grvmCrashOfferPresentationAttemptsRemaining -= 1",
            text[stage_start:stage_end],
        )

        offer_start = text.find("private func presentGRVMLocalCrashOffer(")
        offer_end = text.find("private func markGRVMLocalCrashOfferPresented", offer_start)
        offer = text[offer_start:offer_end]
        consume_index = offer.find(
            "self.consumeGRVMLocalCrashOfferPresentationAttempt("
        )
        present_index = offer.find("mainWindow.presentNative(controller)")
        self.assertGreaterEqual(consume_index, 0)
        self.assertGreater(present_index, consume_index)

        consume_start = text.find(
            "private func consumeGRVMLocalCrashOfferPresentationAttempt("
        )
        consume_end = text.find("private func", consume_start + 1)
        consume = text[consume_start:consume_end]
        self.assertIn("self.grvmCrashOfferPresentationAttemptsRemaining > 0", consume)
        self.assertIn("self.grvmCrashOfferPresentationAttemptsRemaining -= 1", consume)

        failure_start = text.find(
            "private func handleGRVMLocalCrashOfferPhysicalPresentationFailure("
        )
        failure_end = text.find("private func", failure_start + 1)
        self.assertGreaterEqual(failure_start, 0)
        failure = text[failure_start:failure_end]
        self.assertIn("Queue.mainQueue().after(0.5)", failure)
        self.assertIn(
            "self.presentGRVMLocalCrashOffer(owner: owner, accountPeerId: accountPeerId)",
            failure,
        )
        self.assertNotIn("updateGRVMLocalCrashForegroundSession", failure)
        self.assertNotIn("stageGRVMLocalCrashExport", failure)

        launch_active = text[text.find("if application.applicationState == .active {"):]
        launch_active = launch_active[: launch_active.find("DeviceProximityManager")]
        did_become_active = text[text.find("func applicationDidBecomeActive("):]
        did_become_active = did_become_active[:
            did_become_active.find("func applicationWillTerminate")
        ]
        for active_window in (launch_active, did_become_active):
            self.assertNotIn("resetGRVMLocalCrashPresentationRetryAllowance", active_window)
            self.assertNotIn(
                "grvmCrashOfferPresentationAttemptsRemaining = 2", active_window
            )

    def test_confirmed_automatic_share_retries_same_bundle_once(self) -> None:
        retry_available = True
        retry_count = 0
        if retry_available:
            retry_available = False
            retry_count += 1
        if retry_available:
            retry_count += 1
        self.assertEqual(retry_count, 1)

        text = source(APP_PATH)
        owner_start = text.find(
            "private final class GRVMLocalCrashExportPresentationOwner"
        )
        owner_end = text.find("@objc(AppDelegate)", owner_start)
        owner = text[owner_start:owner_end]
        self.assertIn(
            "private var automaticSharePresentationRetryAvailable = true", owner
        )
        self.assertIn("func consumeAutomaticSharePresentationRetry() -> Bool", owner)
        self.assertIn("self.automaticSharePresentationRetryAvailable = false", owner)

        failure_start = text.find(
            "private func handleGRVMLocalCrashSharePhysicalPresentationFailure("
        )
        failure_end = text.find("private func", failure_start + 1)
        self.assertGreaterEqual(failure_start, 0)
        failure = text[failure_start:failure_end]
        request_index = failure.find("self.grvmCrashExportRequestId == owner.id")
        account_index = failure.find(
            "self.grvmCrashPrimaryAccountPeerId == accountPeerId"
        )
        setting_index = failure.find("self.grvmCrashReportingEnabled")
        consume_index = failure.find("owner.consumeAutomaticSharePresentationRetry()")
        defer_index = failure.find("Queue.mainQueue().after(0.5)")
        retry_index = failure.find(
            "self.presentGRVMLocalCrashShare(owner: owner)", defer_index
        )
        self.assertGreaterEqual(request_index, 0)
        self.assertGreater(account_index, request_index)
        self.assertGreater(setting_index, account_index)
        self.assertGreater(consume_index, setting_index)
        self.assertGreater(defer_index, consume_index)
        self.assertGreater(retry_index, defer_index)
        self.assertIn("owner.finish()", failure)
        self.assertNotIn("presentGRVMLocalCrashOffer", failure)
        self.assertNotIn("stageGRVMLocalCrashExport", failure)

        verify_start = text.find("private func verifyGRVMLocalCrashPresentation(")
        verify_end = text.find("private func", verify_start + 1)
        verify = text[verify_start:verify_end]
        self.assertIn("physicalFailure: @escaping () -> Void", verify)
        physical_index = verify.find("controller.presentingViewController != nil")
        failure_index = verify.find("physicalFailure()", physical_index)
        self.assertGreaterEqual(physical_index, 0)
        self.assertGreater(failure_index, physical_index)

        share_start = text.find("private func presentGRVMLocalCrashShare(")
        share_end = text.find("private func verifyGRVMLocalCrashPresentation", share_start)
        share = text[share_start:share_end]
        self.assertIn(
            "self.handleGRVMLocalCrashSharePhysicalPresentationFailure(owner: owner)",
            share,
        )

    def test_ipad_popover_anchor_stays_inside_the_source_view(self) -> None:
        text = source(APP_PATH)
        share_start = text.find("private func presentGRVMLocalCrashShare(")
        share_end = text.find("private func", share_start + 1)
        self.assertGreaterEqual(share_start, 0)
        self.assertGreater(share_end, share_start)
        share = text[share_start:share_end]
        self.assertIn("y: sourceView.bounds.maxY - 1.0", share)
        self.assertNotIn("y: sourceView.bounds.maxY,", share)

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
        share_index = offer.find(
            "self.presentGRVMLocalCrashShare(owner: owner)", action_index
        )
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
            "recheckManualGRVMLocalCrashExport(accountPeerId: accountPeerId, owner: owner)",
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
        share_index = recheck.find("presentGRVMLocalCrashShare(owner: owner)")
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
