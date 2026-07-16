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


def swift_block(source: str, signature: str) -> str:
    start = source.find(signature)
    if start == -1:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening_brace = source.index("{", start)
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


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

    def test_registry_publishes_exact_initial_settings_synchronously_before_subscription(self) -> None:
        self.assertTrue(REGISTRY.exists())
        source = REGISTRY.read_text(encoding="utf-8")
        register = swift_block(source, "public func register(")
        self.assertIn("initialSettings: AyuGramSettings", register)
        self.assertIn("self.lifecycleQueue.sync", register)

        register_on_queue = source[
            source.index("private func registerOnQueue(") :
            source.index("public func unregister(")
        ]
        coordinator = register_on_queue.index("GRVMMessageArchiveCoordinator(")
        prepare = register_on_queue.index("try coordinator.prepare()", coordinator)
        publish = register_on_queue.index("state.services[accountPeerId] = coordinator", prepare)
        settings = register_on_queue.index("grvmSettings(accountId: accountPeerId", publish)
        self.assertIn("settings: initialSettings", register_on_queue)
        self.assertLess(coordinator, prepare)
        self.assertLess(prepare, publish)
        self.assertLess(publish, settings)
        self.assertNotIn("GRVMMessageArchiveCoordinator(", register_on_queue[settings:])
        self.assertIn("coordinator.updateSettings(settings)", register_on_queue[settings:])

        app_delegate = APP_DELEGATE.read_text(encoding="utf-8")
        active_accounts = app_delegate[
            app_delegate.index("let grvmActiveAccounts =") :
            app_delegate.index("if #available(iOS 10.3", app_delegate.index("let grvmActiveAccounts ="))
        ]
        self.assertIn("combineLatest(accounts.map", active_accounts)
        self.assertIn("grvmSettings(accountId: context.account.peerId", active_accounts)
        self.assertIn("|> take(1)", active_accounts)
        self.assertIn("initialSettings: initialSettings", active_accounts)
        snapshot = active_accounts.index("grvmSettings(accountId: context.account.peerId")
        register_call = active_accounts.index("registry.register(", snapshot)
        self.assertLess(snapshot, register_call)

    def test_registry_rebind_still_quiesces_before_exact_snapshot_publication(self) -> None:
        source = REGISTRY.read_text(encoding="utf-8")
        register_on_queue = source[
            source.index("private func registerOnQueue(") :
            source.index("public func unregister(")
        ]
        removal = register_on_queue.index(
            "self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: false)"
        )
        coordinator = register_on_queue.index("GRVMMessageArchiveCoordinator(", removal)
        publish = register_on_queue.index("state.services[accountPeerId] = coordinator", coordinator)
        self.assertLess(removal, coordinator)
        self.assertLess(coordinator, publish)
        self.assertIn(
            "service.isBound(to: accountRecordId, postbox: postbox, mediaBox: mediaBox)",
            register_on_queue,
        )
        self.assertIn("service.updateSettings(initialSettings)", register_on_queue)
        self.assertIn("guard state.prepared", source)
        self.assertIn(
            "self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: false)",
            source,
        )
        self.assertIn(
            "self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: true)",
            source,
        )

    def test_registry_quiesces_old_generation_before_removal_and_replacement(self) -> None:
        source = REGISTRY.read_text(encoding="utf-8")
        self.assertIn('private let lifecycleQueue = Queue(name: "GRVMAccountFeatureRegistry")', source)
        self.assertIn("private func registerOnQueue(", source)

        register = source[
            source.index("public func register(") :
            source.index("private func registerOnQueue(")
        ]
        self.assertIn("self.lifecycleQueue.sync", register)
        self.assertIn("self.registerOnQueue(", register)

        register_on_queue = source[
            source.index("private func registerOnQueue(") :
            source.index("public func unregister(")
        ]
        self.assertLess(
            register_on_queue.index("service.isBound(to: accountRecordId, postbox: postbox, mediaBox: mediaBox)"),
            register_on_queue.index("self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: false)"),
        )
        self.assertIn("self.lifecycleQueue.async", register_on_queue)
        identity = "state.settingsDisposables[accountPeerId] === settingsDisposable"
        self.assertGreaterEqual(register_on_queue.count(identity), 2)
        publish = register_on_queue.index("state.services[accountPeerId] = coordinator")
        resume = register_on_queue.index("coordinator.resumePendingCleanupJobs()", publish)
        self.assertLess(publish, resume)

        unregister = source[
            source.index("public func unregister(") :
            source.index("private func removeRegistration(")
        ]
        self.assertIn("self.lifecycleQueue.sync", unregister)
        self.assertIn("self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: true)", unregister)

        removal = source[
            source.index("private func removeRegistration(") :
            source.index("public func setPrimaryAccount(")
        ]
        anchors = [
            "let service = self.state.with",
            "service?.shutdownForReplacement()",
            "state.services.removeValue(forKey: accountPeerId)",
            "disposable?.dispose()",
        ]
        positions = [removal.index(anchor) for anchor in anchors]
        self.assertEqual(positions, sorted(positions))

    def test_registry_delivers_shutdown_errors_after_lifecycle_sync(self) -> None:
        registry = REGISTRY.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")

        shutdown = swift_block(coordinator, "func shutdownForReplacement()")
        self.assertIn(
            "-> [Subscriber<[MessageId], GRVMClearDeletedError>]",
            shutdown,
        )
        self.assertIn("return waiters", shutdown)
        self.assertNotIn("subscriber.putError", shutdown)

        register = swift_block(registry, "public func register(")
        self.assertIn("var shutdownWaiters", register)
        register_sync = swift_block(register, "self.lifecycleQueue.sync")
        self.assertNotIn("Self.deliverShutdownErrors", register_sync)
        self.assertLess(
            register.index(register_sync) + len(register_sync),
            register.index("Self.deliverShutdownErrors(shutdownWaiters)"),
        )

        unregister = swift_block(registry, "public func unregister(")
        self.assertIn("var shutdownWaiters", unregister)
        unregister_sync = swift_block(unregister, "self.lifecycleQueue.sync")
        self.assertNotIn("Self.deliverShutdownErrors", unregister_sync)
        self.assertLess(
            unregister.index(unregister_sync) + len(unregister_sync),
            unregister.index("Self.deliverShutdownErrors(shutdownWaiters)"),
        )

        removal = swift_block(registry, "private func removeRegistration(")
        self.assertNotIn("subscriber.putError", removal)
        delivery = swift_block(registry, "private static func deliverShutdownErrors(")
        self.assertIn("Queue.concurrentDefaultQueue().async", delivery)
        async_delivery = swift_block(delivery, "Queue.concurrentDefaultQueue().async")
        self.assertIn("subscriber.putError(.archiveUnavailable)", async_delivery)

    def test_registry_deinit_detaches_services_and_terminates_every_waiter(self) -> None:
        events = []

        class Service:
            def __init__(self, name: str, waiter_count: int) -> None:
                self.name = name
                self.waiter_count = waiter_count

            def shutdown_for_replacement(self):
                events.append(("shutdown", self.name))
                return [f"{self.name}:{index}" for index in range(self.waiter_count)]

        class Disposable:
            def __init__(self, name: str) -> None:
                self.name = name

            def dispose(self) -> None:
                events.append(("dispose", self.name))

        services = [Service("a", 2), Service("b", 1)]
        disposables = [Disposable("a"), Disposable("b")]
        waiters = []
        for service in services:
            waiters.extend(service.shutdown_for_replacement())
        for disposable in disposables:
            disposable.dispose()
        for waiter in waiters:
            events.append(("error", waiter))

        self.assertEqual(3, sum(1 for kind, _ in events if kind == "error"))
        self.assertLess(
            max(index for index, event in enumerate(events) if event[0] == "shutdown"),
            min(index for index, event in enumerate(events) if event[0] == "error"),
        )

        registry = REGISTRY.read_text(encoding="utf-8")
        deinit = swift_block(registry, "deinit")
        required = (
            "services = Array(state.services.values)",
            "state.services.removeAll()",
            "state.settingsDisposables.removeAll()",
            "service.shutdownForReplacement()",
            "disposable.dispose()",
            "Self.deliverShutdownErrors(waiters)",
        )
        self.assertEqual([], [token for token in required if token not in deinit])
        self.assertLess(
            deinit.index("service.shutdownForReplacement()"),
            deinit.index("Self.deliverShutdownErrors(waiters)"),
        )
        delivery = swift_block(registry, "private static func deliverShutdownErrors(")
        self.assertIn("Queue.concurrentDefaultQueue().async", delivery)

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
