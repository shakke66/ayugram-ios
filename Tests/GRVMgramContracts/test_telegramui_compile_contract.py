import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_DELEGATE = ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift"
HISTORY = ROOT / "submodules/TelegramUI/Sources/ChatHistoryListNode.swift"
CONTEXT_MENUS = (
    ROOT / "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
)


def section(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


class TelegramUICompileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app_delegate = APP_DELEGATE.read_text(encoding="utf-8")
        cls.history = HISTORY.read_text(encoding="utf-8")
        cls.context_menus = CONTEXT_MENUS.read_text(encoding="utf-8")

    def test_shared_context_pipeline_has_explicit_signal_boundaries(self) -> None:
        pipeline = section(
            self.app_delegate,
            "var systemUserInterfaceStyle: WindowUserInterfaceStyle",
            "self.context.set(self.sharedContextPromise.get()",
        )
        for fragment in (
            "let sharedContextInputSignal: Signal<(AccountManager<TelegramAccountManagerTypes>, InitialPresentationDataAndSettings), NoError> =",
            "-> (AccountManager<TelegramAccountManagerTypes>, InitialPresentationDataAndSettings) in",
            "let sharedContextSignal: Signal<(SharedApplicationContext, LoggingSettings), NoError> = sharedContextInputSignal",
            "let configuredSharedContextSignal: Signal<SharedApplicationContext, NoError> = sharedContextSignal",
            "self.sharedContextPromise.set(configuredSharedContextSignal)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, pipeline)

    def test_shared_context_grvm_bindings_are_isolated_from_producer(self) -> None:
        pipeline = section(
            self.app_delegate,
            "let sharedContextSignal: Signal<",
            "presentationDataPromise.set(sharedContext.presentationData)",
        )
        helper_start = self.app_delegate.find(
            "private func bindGRVMSharedContext("
        )
        helper_end = self.app_delegate.find(
            "private func bindGRVMLocalCrashLifecycle(", helper_start
        )
        self.assertGreaterEqual(helper_start, 0)
        self.assertGreater(helper_end, helper_start)
        helper = self.app_delegate[helper_start:helper_end]

        self.assertIn("self.bindGRVMSharedContext(", pipeline)
        self.assertNotIn("let grvmActiveAccounts =", pipeline)
        for fragment in (
            "sharedContext: SharedAccountContextImpl,",
            "accountManager: AccountManager<TelegramAccountManagerTypes>,",
            "application: UIApplication",
            "let screenCaptureEnabledSignal: Signal<Bool, NoError> =",
            "setEnabledSignal(screenCaptureEnabledSignal)",
            "setPresentationDataSignal(",
            "self.bindGRVMLocalCrashLifecycle(",
            "let grvmActiveAccounts: Signal<GRVMActiveAccountsSnapshot, NoError> =",
            "self.grvmAppIconDisposable.set(",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, helper)

    def test_grvm_active_accounts_pipeline_has_staged_type_boundaries(self) -> None:
        helper = section(
            self.app_delegate,
            "private func bindGRVMSharedContext(",
            "private func bindGRVMLocalCrashLifecycle(",
        )
        self.assertIn("private struct GRVMActiveAccountsSnapshot {", self.app_delegate)
        for fragment in (
            "private static func makeGRVMActiveAccountsSnapshotSignal(",
            "let settingsSignals: [Signal<(PeerId, AyuGramSettings), NoError>] =",
            "let settingsSignal: Signal<[(PeerId, AyuGramSettings)], NoError> = combineLatest(settingsSignals)",
            "let migratedSettingsSignal: Signal<Void, NoError> = migrateGRVMSettings(",
            "let migrationCompletionSignal: Signal<GRVMActiveAccountsSnapshot, NoError> = migratedSettingsSignal",
            "return .complete()",
            "let snapshotSignal: Signal<GRVMActiveAccountsSnapshot, NoError> = settingsSignal",
            "return migrationCompletionSignal",
            "|> then(snapshotSignal)",
            "let grvmActiveAccountsSignal: Signal<GRVMActiveAccountsSnapshot, NoError> = sharedContext.activeAccountContexts",
            "let grvmActiveAccounts: Signal<GRVMActiveAccountsSnapshot, NoError> = grvmActiveAccountsSignal",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, helper)
        self.assertNotIn("return migratedSettingsSignal\n        |> then(snapshotSignal)", helper)

    def test_chat_appearance_pipeline_has_explicit_signal_boundaries(self) -> None:
        method = section(
            self.history,
            "private func beginPresentationDataManagement(",
            "private func attemptReadingReactions()",
        )
        for fragment in (
            "let settingsSignal: Signal<AyuGramSettings, NoError> = grvmSettings(",
            "let chatAppearanceValues: Signal<GRVMAppearanceSettings, NoError> = settingsSignal",
            "let chatAppearance: Signal<GRVMAppearanceSettings, NoError> = chatAppearanceValues",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, method)
        self.assertNotIn("let chatAppearance = grvmSettings(", method)

    def test_local_copy_fallback_groups_nil_coalescing_before_pipe(self) -> None:
        method = section(
            self.context_menus,
            "private func grvmCanForwardLocalCopy(",
            "func canEditMessage(context:",
        )
        # ST22 makes availability a pure query: restoration is performed only
        # after the user selects a peer, so this route must not trigger it.
        self.assertIn("let media = marker?.media ?? message.media", method)
        self.assertIn("return .single(marker != nil)", method)
        self.assertNotIn("AyuGramHooks.restoreConsumableMedia?", method)
        self.assertNotIn("|> map", method)

    def test_combined_data_discards_unused_privacy_tip(self) -> None:
        menu = section(
            self.context_menus,
            "func contextMenuForChatPresentationInterfaceState(",
            "private final class ChatReadReportContextItemNode",
        )
        binding = re.search(r"let\s*\((?P<items>[^)]*)\)\s*=\s*combinedData", menu)
        self.assertIsNotNone(binding)
        items = [item.strip() for item in binding.group("items").split(",")]
        self.assertEqual(11, len(items))
        self.assertEqual("_", items[5])


if __name__ == "__main__":
    unittest.main()
