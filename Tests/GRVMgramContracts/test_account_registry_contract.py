import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift"
COORDINATOR = ROOT / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
MANAGER = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
APP_DELEGATE = ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift"
HOOKS = ROOT / "submodules/TelegramCore/Sources/AyuGramHooks.swift"
PEER_UTILS = ROOT / "submodules/TelegramCore/Sources/Utils/PeerUtils.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"
MEDIA_STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift"


class AccountRegistryContractTests(unittest.TestCase):
    def test_registry_uses_explicit_atomic_account_lookups(self) -> None:
        self.assertTrue(REGISTRY.exists())
        source = REGISTRY.read_text(encoding="utf-8")
        self.assertIn("private struct RuntimeState", source)
        self.assertIn("Atomic<RuntimeState>", source)
        self.assertIn("func service(accountPeerId: PeerId)", source)
        self.assertIn("state.services[accountPeerId]", source)
        self.assertIn("state.primaryAccountPeerId", source)
        self.assertNotIn("services.values.first", source)
        self.assertNotIn("currentAccount", source)

    def test_registry_waits_for_exact_settings_before_publishing_service(self) -> None:
        self.assertTrue(REGISTRY.exists())
        source = REGISTRY.read_text(encoding="utf-8")
        settings = source.index("grvmSettings(accountId: accountPeerId")
        coordinator = source.index("GRVMMessageArchiveCoordinator(", settings)
        publish = source.index("state.services[accountPeerId] = coordinator", coordinator)
        self.assertLess(settings, coordinator)
        self.assertLess(coordinator, publish)
        self.assertIn("guard state.prepared", source)
        self.assertIn(
            "service.isBound(to: accountRecordId, postbox: postbox, mediaBox: mediaBox)",
            source,
        )
        self.assertIn(
            "self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: false)",
            source,
        )
        self.assertIn(
            "self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: true)",
            source,
        )

    def test_app_delegate_migrates_then_registers_active_contexts(self) -> None:
        source = APP_DELEGATE.read_text(encoding="utf-8")
        for token in (
            "activeAccountContexts",
            "migrateGRVMSettings",
            "prepare(activeAccountRecordIds:",
            "register(accountPeerId:",
        ):
            self.assertIn(token, source)
        context = source.index("SharedAccountContextImpl(")
        active = source.index("activeAccountContexts", context)
        migrate = source.index("migrateGRVMSettings", active)
        prepare = source.index("prepare(activeAccountRecordIds:", migrate)
        register = source.index("register(accountPeerId:", prepare)
        self.assertLess(context, active)
        self.assertLess(active, migrate)
        self.assertLess(migrate, prepare)
        self.assertLess(prepare, register)
        self.assertIn('appendingPathComponent("ayugram_messages.db")', source)
        self.assertIn('appendingPathComponent("GRVMgramDeletedMedia"', source)
        self.assertIn("grvmSettings(accountId: primary.account.peerId", source)
        self.assertNotIn("ayuGramSettings(accountManager: accountManager)", source)

    def test_feature_manager_has_no_mutable_global_settings_or_legacy_archive(self) -> None:
        source = MANAGER.read_text(encoding="utf-8")
        self.assertNotIn("currentSettings: AyuGramSettings =", source)
        self.assertNotIn("settingsDisposable", source)
        self.assertNotIn("ayuGramSettings(accountManager:", source)
        self.assertNotIn("AyuDeletedMessagesDB.shared", source)
        self.assertIn("registry.primaryService()?.settingsSnapshot()", source)

    def test_local_premium_applies_only_to_primary_own_peer(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        peer_utils = PEER_UTILS.read_text(encoding="utf-8")
        manager = MANAGER.read_text(encoding="utf-8")
        self.assertIn("isLocalPremiumEnabled: ((PeerId) -> Bool)?", hooks)
        self.assertIn("isLocalPremiumEnabled?(self.id)", peer_utils)
        self.assertIn("service.accountPeerId == peerId", manager)
        self.assertIn("service.settingsSnapshot().localTelegramPremium", manager)

    def test_coordinator_primes_one_index_snapshot_and_restores_media(self) -> None:
        self.assertTrue(COORDINATOR.exists())
        source = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("store.deletedKeys(accountId: accountRecordId.int64)", source)
        self.assertIn("store.revisedKeys(accountId: accountRecordId.int64)", source)
        self.assertEqual(source.count("index.replace("), 1)
        self.assertIn("mediaBox.didRemoveResourceIds", source)
        self.assertIn("mediaStore.restore(record, to: mediaBox)", source)
        self.assertIn("func hasEditHistory(_ id: MessageId) -> Bool", source)

    def test_startup_reconciliation_has_complete_blob_inventory(self) -> None:
        store = STORE.read_text(encoding="utf-8")
        media_store = MEDIA_STORE.read_text(encoding="utf-8")
        self.assertIn("func archivedMedia(accountId: Int64) throws", store)
        self.assertIn("func reconcile(", media_store)
        self.assertIn('pathExtension == "tmp"', media_store)
        self.assertIn("referencedRelativePaths", media_store)
        self.assertIn("copyState: .missing", media_store)


if __name__ == "__main__":
    unittest.main()
