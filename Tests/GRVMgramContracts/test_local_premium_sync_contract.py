import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


class LocalPremiumCleanupCoordinatorModel:
    def __init__(self, account_ids: list[str]) -> None:
        self.marked_accounts = set(account_ids)
        self.known_account_ids: list[str] = []
        self.active_account_ids: set[str] = set()
        self.enabled: bool | None = None
        self.setting_events: list[bool] = []
        self.queued_account_ids: list[str] = []
        self.queued_account_id_set: set[str] = set()
        self.reconciled_account_ids: set[str] = set()
        self.cleanup_counts: dict[str, int] = {}

    def publish_setting(self, enabled: bool) -> None:
        self.setting_events.append(enabled)

    def update_accounts(self, account_ids: list[str]) -> None:
        previous_ids = self.active_account_ids
        self.active_account_ids = set(account_ids)
        for account_id in account_ids:
            if account_id not in self.known_account_ids:
                self.known_account_ids.append(account_id)
        if self.enabled is True:
            self.known_account_ids = [
                account_id
                for account_id in self.known_account_ids
                if account_id in self.active_account_ids
            ]
        elif self.enabled is False:
            self.reconciled_account_ids.difference_update(
                set(account_ids).difference(previous_ids)
            )
            self.known_account_ids = [
                account_id
                for account_id in self.known_account_ids
                if account_id in self.active_account_ids
                or account_id in self.queued_account_id_set
                or account_id not in self.reconciled_account_ids
            ]
            self._enqueue_current_accounts()

    def deliver_next_setting(self) -> None:
        enabled = self.setting_events.pop(0)
        previous_enabled = self.enabled
        self.enabled = enabled
        if enabled:
            self.known_account_ids = [
                account_id
                for account_id in self.known_account_ids
                if account_id in self.active_account_ids
                or account_id in self.queued_account_id_set
            ]
            return
        if previous_enabled is not False:
            self.reconciled_account_ids.clear()
        self._enqueue_current_accounts()

    def deliver_all_settings(self) -> None:
        while self.setting_events:
            self.deliver_next_setting()

    def _enqueue_current_accounts(self) -> None:
        for account_id in self.known_account_ids:
            if (
                account_id in self.queued_account_id_set
                or account_id in self.reconciled_account_ids
            ):
                continue
            self.queued_account_ids.append(account_id)
            self.queued_account_id_set.add(account_id)

    def complete_next_cleanup(self) -> None:
        if not self.queued_account_ids:
            return
        account_id = self.queued_account_ids.pop(0)
        self.queued_account_id_set.remove(account_id)
        self.marked_accounts.discard(account_id)
        self.cleanup_counts[account_id] = self.cleanup_counts.get(account_id, 0) + 1
        if self.enabled is False:
            self.reconciled_account_ids.add(account_id)
            if account_id not in self.active_account_ids:
                self.known_account_ids.remove(account_id)
                self.reconciled_account_ids.remove(account_id)

    def complete_all_cleanup(self) -> None:
        while self.queued_account_ids:
            self.complete_next_cleanup()


class LocalPremiumSyncContractTests(unittest.TestCase):
    peer_state_path = (
        "submodules/TelegramCore/Sources/GRVMLocalPremiumPeerState.swift"
    )
    marker_path = (
        "submodules/TelegramCore/Sources/SyncCore/"
        "GRVMLocalPremiumEmojiMessageAttribute.swift"
    )

    def test_outgoing_encoder_is_opt_in_and_preserves_stock_entities(self) -> None:
        encoder = source(
            "submodules/TelegramCore/Sources/ApiUtils/TextEntitiesMessageAttribute.swift"
        )
        function = swift_block(encoder, "func apiEntitiesFromMessageTextEntities(")
        self.assertIn("localPremiumEmojiTransport", function)
        self.assertIn("serverAllowedFileIds", function)
        self.assertIn('url: "tg://emoji?id=\\(fileId)"', function)
        self.assertIn(".messageEntityTextUrl", function)
        self.assertIn(".messageEntityCustomEmoji", function)
        self.assertRegex(
            function,
            r"localPremiumEmojiTransport\.enabled\s*&&\s*fileId\s*>\s*0\s*&&\s*!localPremiumEmojiTransport\.serverAllowedFileIds\.contains\(fileId\)",
        )

    def test_send_gate_uses_exact_account_raw_premium_and_channel_allowlist(self) -> None:
        encoder = source(
            "submodules/TelegramCore/Sources/ApiUtils/TextEntitiesMessageAttribute.swift"
        )
        policy = swift_block(encoder, "func grvmLocalPremiumEmojiTransport(")
        for token in (
            "peerId != accountPeerId",
            "AyuGramHooks.isLocalPremiumEnabled?(accountPeerId) == true",
            "transaction.getPeer(accountPeerId) as? TelegramUser",
            "accountUser.flags.contains(.isPremium)",
            "transaction.getPeerCachedData(peerId: peerId) as? CachedChannelData",
            "cachedData.emojiPack",
            "transaction.getItemCollectionItems(collectionId: emojiPack.id)",
            "item.file.fileId.id",
        ):
            self.assertIn(token, policy)
        self.assertNotIn("accountUser.isPremium", policy)

        pending = source(
            "submodules/TelegramCore/Sources/State/PendingMessageManager.swift"
        )
        self.assertEqual(pending.count("grvmLocalPremiumEmojiTransport("), 2)
        self.assertGreaterEqual(
            pending.count("localPremiumEmojiTransport: grvmEmojiTransport"),
            2,
        )

    def test_edit_path_uses_the_same_transport_policy(self) -> None:
        edit = source(
            "submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift"
        )
        self.assertIn("GRVMLocalPremiumEmojiTransport", edit)
        self.assertIn("grvmLocalPremiumEmojiTransport(", edit)
        self.assertIn("localPremiumEmojiTransport: grvmEmojiTransport", edit)

    def test_reply_quotes_use_the_same_transport_snapshot_on_every_send_route(self) -> None:
        pending = source(
            "submodules/TelegramCore/Sources/State/PendingMessageManager.swift"
        )
        quote_calls = re.findall(
            r"quoteEntities\s*=\s*apiEntitiesFromMessageTextEntities\(\s*"
            r"replyQuote\.entities,\s*associatedPeers:\s*associatedPeers,\s*"
            r"localPremiumEmojiTransport:\s*grvmEmojiTransport\s*\)",
            pending,
        )
        self.assertEqual(4, len(quote_calls))
        self.assertEqual(
            4,
            pending.count("quoteEntities = apiEntitiesFromMessageTextEntities("),
        )

    def test_incoming_decoder_requires_exact_url_range_and_single_emoji(self) -> None:
        decoder = source(
            "submodules/TelegramCore/Sources/ApiUtils/StoreMessage_Telegram.swift"
        )
        url_parser = swift_block(decoder, "private func grvmLocalPremiumEmojiFileId(")
        for token in (
            'let prefix = "tg://emoji?id="',
            "url.hasPrefix(prefix)",
            "48 ... 57",
            "Int64(rawFileId)",
            "fileId > 0",
        ):
            self.assertIn(token, url_parser)

        emoji_guard = swift_block(decoder, "private func grvmIsSingleUnicodeEmoji(")
        self.assertIn("value.count == 1", emoji_guard)
        self.assertIn("value.containsEmoji", emoji_guard)

        conversion = swift_block(decoder, "private func grvmLocalPremiumEmojiEntity(")
        for token in (
            "offset >= 0",
            "length > 0",
            "NSMaxRange(range) <= nsText.length",
            "nsText.substring(with: range)",
            "grvmIsSingleUnicodeEmoji(entityText)",
            ".CustomEmoji(stickerPack: nil, fileId: fileId)",
        ):
            self.assertIn(token, conversion)

        entities = swift_block(decoder, "func messageTextEntitiesFromApiEntities(")
        self.assertIn("text: String? = nil", entities)
        text_url_case = entities[
            entities.index("case let .messageEntityTextUrl") : entities.index(
                "case let .messageEntityMentionName"
            )
        ]
        self.assertIn("grvmLocalPremiumEmojiEntity", text_url_case)
        self.assertIn(".TextUrl(url: url)", text_url_case)

    def test_store_message_supplies_text_to_the_decoder(self) -> None:
        store = source(
            "submodules/TelegramCore/Sources/ApiUtils/StoreMessage_Telegram.swift"
        )
        self.assertIn(
            "messageTextEntitiesFromApiEntities(entities, text: messageText)", store
        )
        self.assertGreaterEqual(
            len(
                re.findall(
                    r"messageTextEntitiesFromApiEntities\(quoteEntities \?\? \[\], text: quoteText \?\? \"\"\)",
                    store,
                )
            ),
            3,
        )

    def test_short_sent_ack_supplies_current_text_to_the_decoder(self) -> None:
        apply_update = source(
            "submodules/TelegramCore/Sources/State/ApplyUpdateMessage.swift"
        )
        short_sent = apply_update[
            apply_update.index("case let .updateShortSentMessage") :
            apply_update.index("if Namespaces.Message.allQuickReply", apply_update.index("case let .updateShortSentMessage"))
        ]
        self.assertIn(
            "messageTextEntitiesFromApiEntities(entities, text: currentMessage.text)",
            short_sent,
        )
        self.assertNotIn(
            "messageTextEntitiesFromApiEntities(entities)", short_sent
        )

    def test_self_status_is_local_only_for_marked_raw_nonpremium_state(self) -> None:
        account_data = source(
            "submodules/TelegramCore/Sources/TelegramEngine/AccountData/"
            "TelegramEngineAccountData.swift"
        )
        status = swift_block(
            account_data,
            "public func setEmojiStatus(file: TelegramMediaFile?",
        )
        for token in (
            "AyuGramHooks.isLocalPremiumEnabled?(peerId) == true",
            "!peer.flags.contains(.isPremium)",
            "grvmStoredLocalPremiumPeerState(",
            "peer.emojiStatus == nil || currentState?.fileId == peer.emojiStatus?.fileId",
            "let useLocalPremiumStatus",
            "grvmSetLocalPremiumPeerState(",
            "expirationDate ?? Int32.max",
            "grvmRemoveLocalPremiumPeerState(",
            "mapToSignal { useLocalPremiumStatus -> Signal<Never, NoError> in",
            "if useLocalPremiumStatus",
            "return .complete()",
            "Api.functions.account.updateEmojiStatus",
        ):
            with self.subTest(token=token):
                self.assertIn(token, status)

        local_branch = status.find("if useLocalPremiumStatus")
        remote_request = status.find("Api.functions.account.updateEmojiStatus")
        self.assertGreaterEqual(local_branch, 0)
        self.assertGreaterEqual(remote_request, 0)
        self.assertLess(local_branch, remote_request)
        self.assertNotIn("peer.isPremium", status)

    def test_off_cleanup_preserves_genuine_premium_and_non_marker_self_status(self) -> None:
        state_path = ROOT / self.peer_state_path
        state = state_path.read_text(encoding="utf-8") if state_path.exists() else ""
        cleanup = swift_block(state, "public func grvmClearLocalPremiumSelfState(")
        for token in (
            "grvmStoredLocalPremiumPeerState(",
            "grvmRemoveLocalPremiumPeerState(",
            "transaction.getPeer(accountPeerId) as? TelegramUser",
            "!peer.flags.contains(.isPremium)",
            "peer.emojiStatus?.fileId == state.fileId",
            "peer.withUpdatedEmojiStatus(nil)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, cleanup)

        marker_removal = cleanup.index("grvmRemoveLocalPremiumPeerState(")
        safety_guard = cleanup.index("guard let state,")
        status_removal = cleanup.index("peer.withUpdatedEmojiStatus(nil)")
        self.assertLess(marker_removal, safety_guard)
        self.assertLess(safety_guard, status_removal)

    def test_client_wide_off_reconciles_each_registered_account_marker(self) -> None:
        account_settings = source(
            "submodules/AyuGramLib/Sources/GRVMAccountSettings.swift"
        )
        read = swift_block(account_settings, "public func grvmSettings(")
        update = swift_block(account_settings, "public func updateGRVMSettings(")
        for operation in (read, update):
            self.assertIn("_ = accountId", operation)
            self.assertIn(
                "ApplicationSpecificSharedDataKeys.grvmAccountSettings",
                operation,
            )

        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        coordinator = swift_block(
            app_delegate, "private final class GRVMLocalPremiumCleanupCoordinator"
        )
        for token in (
            "private let settingsDisposable = MetaDisposable()",
            "private let cleanupDisposable = MetaDisposable()",
            "private let cleanupPipe = ValuePipe<Signal<Never, NoError>>()",
            "private var queuedAccountIds = Set<PeerId>()",
            "private var reconciledAccountIds = Set<PeerId>()",
            "self.cleanupPipe.signal()",
            "|> mapToQueue { cleanup -> Signal<Never, NoError> in",
            "grvmSettings(",
            "accountId: settingsAccountPeerId",
            "|> map(\\.localTelegramPremium)",
            "|> distinctUntilChanged",
            "|> deliverOnMainQueue",
            "grvmClearLocalPremiumSelfState(",
            "postbox: context.account.postbox",
            "accountPeerId: context.account.peerId",
            "self.cleanupPipe.putNext(cleanup)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, coordinator)

    def test_off_cleanup_survives_snapshot_churn_and_off_on_toggle(self) -> None:
        model = LocalPremiumCleanupCoordinatorModel(["A", "B"])
        model.update_accounts(["A", "B"])
        model.publish_setting(enabled=False)

        # Snapshot churn happens before the stable observer delivers OFF.
        model.update_accounts([])
        model.publish_setting(enabled=True)
        model.deliver_all_settings()
        model.complete_all_cleanup()
        self.assertEqual(set(), model.marked_accounts)
        self.assertEqual({"A": 1, "B": 1}, model.cleanup_counts)

        next_generation = LocalPremiumCleanupCoordinatorModel(["A"])
        next_generation.update_accounts(["A"])
        next_generation.publish_setting(enabled=False)
        next_generation.deliver_all_settings()
        next_generation.complete_all_cleanup()
        next_generation.publish_setting(enabled=True)
        next_generation.deliver_all_settings()
        next_generation.marked_accounts.add("A")
        next_generation.publish_setting(enabled=False)
        next_generation.deliver_all_settings()
        next_generation.complete_all_cleanup()
        self.assertEqual({"A": 2}, next_generation.cleanup_counts)
        self.assertEqual(set(), next_generation.marked_accounts)

        completion_after_on = LocalPremiumCleanupCoordinatorModel(["A"])
        completion_after_on.update_accounts(["A"])
        completion_after_on.publish_setting(enabled=False)
        completion_after_on.deliver_all_settings()
        completion_after_on.publish_setting(enabled=True)
        completion_after_on.deliver_all_settings()
        completion_after_on.complete_next_cleanup()
        self.assertEqual([], completion_after_on.queued_account_ids)
        self.assertEqual({"A": 1}, completion_after_on.cleanup_counts)

        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        binding = swift_block(app_delegate, "private func bindGRVMSharedContext(")
        coordinator_init = binding.find(
            "GRVMLocalPremiumCleanupCoordinator(accountManager: accountManager)"
        )
        active_subscription = binding.find(
            "self.grvmActiveAccountsDisposable.set("
        )
        self.assertGreaterEqual(coordinator_init, 0)
        self.assertGreater(active_subscription, coordinator_init)
        self.assertIn(
            "self.grvmLocalPremiumCleanupCoordinator?.updateAccounts(", binding
        )
        self.assertNotIn("grvmLocalPremiumReconciliationDisposable.set(", binding)
        self.assertNotIn("retainGRVMLocalPremiumCleanup", app_delegate)

        coordinator = swift_block(
            app_delegate, "private final class GRVMLocalPremiumCleanupCoordinator"
        )
        update_enabled = swift_block(coordinator, "private func updateEnabled(")
        self.assertIn("if previousEnabled != false", update_enabled)
        self.assertIn("self.reconciledAccountIds.removeAll()", update_enabled)
        self.assertIn("self.enqueueCurrentAccounts()", update_enabled)
        self.assertNotIn("cleanupDisposable.set(", update_enabled)
        enqueue = swift_block(coordinator, "private func enqueueCurrentAccounts(")
        self.assertIn("guard self.isEnabled == false else", enqueue)

    def test_registration_reconciles_stale_marker_from_initial_off_snapshot(self) -> None:
        model = LocalPremiumCleanupCoordinatorModel(["A", "B", "C"])
        model.update_accounts(["A", "B"])
        model.publish_setting(enabled=False)
        model.update_accounts(["A", "B"])
        model.deliver_all_settings()
        model.update_accounts(["A", "B"])
        model.update_accounts(["A", "B", "C"])
        model.update_accounts(["A", "B", "C"])
        model.complete_all_cleanup()
        self.assertEqual({"A": 1, "B": 1, "C": 1}, model.cleanup_counts)

        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        binding = swift_block(app_delegate, "private func bindGRVMSharedContext(")
        snapshot_builder = swift_block(
            app_delegate,
            "private static func makeGRVMActiveAccountsSnapshotSignal(",
        )
        self.assertIn("return migrationCompletionSignal", snapshot_builder)
        self.assertIn("|> then(snapshotSignal)", snapshot_builder)

        coordinator = swift_block(
            app_delegate, "private final class GRVMLocalPremiumCleanupCoordinator"
        )
        self.assertIn("private var activeAccountIds = Set<PeerId>()", coordinator)
        update_accounts = swift_block(coordinator, "func updateAccounts(")
        for token in (
            "let previousAccountIds = self.activeAccountIds",
            "self.accounts[context.account.peerId] = context",
            "self.activeAccountIds = newAccountIds",
            "newAccountIds.subtracting(previousAccountIds)",
            "self.reconciledAccountIds.remove(peerId)",
            "if self.isEnabled == false",
            "self.enqueueCurrentAccounts()",
            "self.startSettingsObservationIfNeeded(",
        ):
            with self.subTest(token=token):
                self.assertIn(token, update_accounts)
        start_observation = swift_block(
            coordinator, "private func startSettingsObservationIfNeeded("
        )
        self.assertIn("guard !self.didStartSettingsObservation", start_observation)
        self.assertIn("self.didStartSettingsObservation = true", start_observation)

        enqueue = swift_block(coordinator, "private func enqueueCurrentAccounts(")
        self.assertIn("!self.queuedAccountIds.contains(peerId)", enqueue)
        self.assertIn("!self.reconciledAccountIds.contains(peerId)", enqueue)

    def test_off_prunes_only_inactive_reconciled_accounts(self) -> None:
        reconciled = LocalPremiumCleanupCoordinatorModel(["A"])
        reconciled.update_accounts(["A"])
        reconciled.publish_setting(enabled=False)
        reconciled.deliver_all_settings()
        reconciled.complete_all_cleanup()
        reconciled.update_accounts([])
        self.assertEqual([], reconciled.known_account_ids)

        queued = LocalPremiumCleanupCoordinatorModel(["A"])
        queued.update_accounts(["A"])
        queued.publish_setting(enabled=False)
        queued.deliver_all_settings()
        queued.update_accounts([])
        self.assertEqual(["A"], queued.known_account_ids)
        self.assertEqual(["A"], queued.queued_account_ids)

        before_off_delivery = LocalPremiumCleanupCoordinatorModel(["A"])
        before_off_delivery.update_accounts(["A"])
        before_off_delivery.publish_setting(enabled=False)
        before_off_delivery.update_accounts([])
        self.assertEqual(["A"], before_off_delivery.known_account_ids)
        before_off_delivery.deliver_all_settings()
        before_off_delivery.complete_all_cleanup()
        self.assertEqual(set(), before_off_delivery.marked_accounts)

        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        coordinator = swift_block(
            app_delegate, "private final class GRVMLocalPremiumCleanupCoordinator"
        )
        update_accounts = swift_block(coordinator, "func updateAccounts(")
        self.assertIn("self.pruneInactiveReconciledAccounts()", update_accounts)
        prune = swift_block(
            coordinator, "private func pruneInactiveReconciledAccounts("
        )
        for token in (
            "!self.activeAccountIds.contains(peerId)",
            "!self.queuedAccountIds.contains(peerId)",
            "self.reconciledAccountIds.contains(peerId)",
            "self.accounts.removeValue(forKey: peerId)",
            "self.reconciledAccountIds.remove(peerId)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, prune)

    def test_stable_on_snapshot_prunes_inactive_accounts_without_new_setting(self) -> None:
        model = LocalPremiumCleanupCoordinatorModel(["A"])
        model.update_accounts(["A"])
        model.publish_setting(enabled=True)
        model.deliver_all_settings()
        model.update_accounts([])
        self.assertEqual([], model.known_account_ids)

        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        coordinator = swift_block(
            app_delegate, "private final class GRVMLocalPremiumCleanupCoordinator"
        )
        update_accounts = swift_block(coordinator, "func updateAccounts(")
        self.assertIn("if self.isEnabled == true", update_accounts)
        self.assertIn("self.pruneInactiveAccounts()", update_accounts)
        self.assertIn("else if self.isEnabled == false", update_accounts)

    def test_off_toggle_persists_setting_before_current_context_cleanup(self) -> None:

        controller = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        )
        toggle_start = controller.index("toggleLocalPremium: { value in")
        toggle_end = controller.index("toggleDisableAds:", toggle_start)
        toggle = controller[toggle_start:toggle_end]
        for token in (
            "let settingsUpdate = updateGRVMSettings(",
            "if value",
            "grvmClearLocalPremiumSelfState(",
            "settingsUpdate |> ignoreValues |> then(cleanup)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, toggle)

    def test_peer_state_cache_is_account_peer_scoped_live_and_expiring(self) -> None:
        state_path = ROOT / self.peer_state_path
        state = state_path.read_text(encoding="utf-8") if state_path.exists() else ""
        for token in (
            "public struct GRVMLocalPremiumPeerState: Codable, Equatable",
            "public let fileId: Int64",
            "public let updatedAt: Int32",
            "public let expiresAt: Int32",
            "applicationSpecificItemCacheCollectionId(15)",
            "ValueBoxKey(length: 16)",
            "key.setInt64(0, value: accountPeerId.toInt64())",
            "key.setInt64(8, value: peerId.toInt64())",
            "PostboxViewKey.cachedItem(entryId)",
            "views.views[viewKey] as? CachedItemView",
            "state.expiresAt <= currentTimestamp",
            "then(.single(nil) |> delay(",
            "grvmLocalPremiumRemoteStateLifetime",
            "current.updatedAt > updatedAt",
        ):
            with self.subTest(token=token):
                self.assertIn(token, state)
        self.assertNotIn("applicationSpecificItemCacheCollectionId(0)", state)

    def test_exact_conversion_provenance_is_persisted_and_registered(self) -> None:
        marker_path = ROOT / self.marker_path
        marker = marker_path.read_text(encoding="utf-8") if marker_path.exists() else ""
        for token in (
            "public final class GRVMLocalPremiumEmojiMessageAttribute",
            "public let fileIds: [Int64]",
            'decoder.decodeInt64ArrayForKey("f")',
            'encoder.encodeInt64Array(self.fileIds, forKey: "f")',
        ):
            with self.subTest(token=token):
                self.assertIn(token, marker)

        manager = source(
            "submodules/TelegramCore/Sources/Account/AccountManager.swift"
        )
        self.assertIn(
            "declareEncodable(GRVMLocalPremiumEmojiMessageAttribute.self",
            manager,
        )

        decoder = source(
            "submodules/TelegramCore/Sources/ApiUtils/StoreMessage_Telegram.swift"
        )
        decoded = swift_block(
            decoder,
            "func messageTextEntitiesAndGRVMLocalPremiumFileIdsFromApiEntities(",
        )
        for token in (
            "var grvmLocalPremiumFileIds: [Int64] = []",
            "grvmLocalPremiumFileIds.append(converted.fileId)",
            "return (result, grvmLocalPremiumFileIds)",
        ):
            self.assertIn(token, decoded)
        native_custom = decoded[
            decoded.index("case let .messageEntityCustomEmoji") :
            decoded.index("case let .messageEntityFormattedDate")
        ]
        self.assertNotIn("grvmLocalPremiumFileIds.append", native_custom)

        message_path = decoder[
            decoder.index("var entitiesAttribute: TextEntitiesMessageAttribute?") :
            decoder.index("if (flags & (1 << 19))", decoder.index("var entitiesAttribute: TextEntitiesMessageAttribute?"))
        ]
        self.assertIn(
            "messageTextEntitiesAndGRVMLocalPremiumFileIdsFromApiEntities(",
            message_path,
        )
        self.assertIn(
            "GRVMLocalPremiumEmojiMessageAttribute(fileIds:", message_path
        )

        apply_update = source(
            "submodules/TelegramCore/Sources/State/ApplyUpdateMessage.swift"
        )
        short_sent = apply_update[
            apply_update.index("case let .updateShortSentMessage") :
            apply_update.index(
                "if Namespaces.Message.allQuickReply",
                apply_update.index("case let .updateShortSentMessage"),
            )
        ]
        for token in (
            "messageTextEntitiesAndGRVMLocalPremiumFileIdsFromApiEntities(",
            "$0 is GRVMLocalPremiumEmojiMessageAttribute",
            "GRVMLocalPremiumEmojiMessageAttribute(fileIds:",
        ):
            self.assertIn(token, short_sent)

    def test_incoming_marker_replaces_cache_before_message_insertion(self) -> None:
        state_path = ROOT / self.peer_state_path
        state = state_path.read_text(encoding="utf-8") if state_path.exists() else ""
        ingest = swift_block(state, "func grvmUpdateLocalPremiumPeerStates(")
        for token in (
            "message.flags.contains(.Incoming)",
            "authorId != accountPeerId",
            "authorId.namespace == Namespaces.Peer.CloudUser",
            "GRVMLocalPremiumEmojiMessageAttribute",
            "marker.fileIds.last",
            "EditedMessageAttribute",
            "max(updatedAt, edited.date)",
            "grvmLocalPremiumRemoteStateLifetime",
            "grvmSetLocalPremiumPeerState(",
        ):
            with self.subTest(token=token):
                self.assertIn(token, ingest)
        self.assertNotIn("grvmRemoveLocalPremiumPeerState", ingest)

        replay = source(
            "submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift"
        )
        update = replay.find("grvmUpdateLocalPremiumPeerStates(")
        insert = replay.find("transaction.addMessages(messages, location: location)")
        self.assertGreaterEqual(update, 0)
        self.assertGreaterEqual(insert, 0)
        self.assertLess(update, insert)

    def test_incoming_edit_marker_updates_cache_from_replayed_merged_message(self) -> None:
        replay = source(
            "submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift"
        )
        edit_start = replay.find("case let .EditMessage(id, message):")
        edit_end = replay.find("case let .UpdateMessagePoll", edit_start)
        self.assertGreaterEqual(edit_start, 0)
        self.assertGreater(edit_end, edit_start)
        edit = replay[edit_start:edit_end]

        update = swift_block(edit, "transaction.updateMessage(id, update:")
        for token in (
            "let grvmUpdatedMessage = message.withUpdatedLocalTags(updatedLocalTags)",
            ".withUpdatedFlags(updatedFlags)",
            ".withUpdatedAttributes(updatedAttributes)",
            ".withUpdatedMedia(updatedMedia)",
            "replayedGRVMLocalPremiumMessage = grvmUpdatedMessage",
            "return .update(grvmUpdatedMessage)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, update)

        for token in (
            "var replayedGRVMLocalPremiumMessage: StoreMessage?",
            "if let replayedGRVMLocalPremiumMessage",
            "grvmUpdateLocalPremiumPeerStates(",
            "messages: [replayedGRVMLocalPremiumMessage]",
        ):
            with self.subTest(token=token):
                self.assertIn(token, edit)

        replay_update = edit.find("transaction.updateMessage(id, update:")
        ingestion = edit.find("grvmUpdateLocalPremiumPeerStates(")
        reaction_event = edit.find("if let generatedEvent = generatedEvent")
        self.assertGreaterEqual(replay_update, 0)
        self.assertGreaterEqual(ingestion, 0)
        self.assertGreaterEqual(reaction_event, 0)
        self.assertLess(replay_update, ingestion)
        self.assertLess(ingestion, reaction_event)

    def test_remote_projection_is_live_and_never_mutates_server_truth(self) -> None:
        state_path = ROOT / self.peer_state_path
        state = state_path.read_text(encoding="utf-8") if state_path.exists() else ""
        presentation = swift_block(state, "public func grvmLocalPremiumPresentation(")
        for token in (
            "let user = peer as? TelegramUser",
            "!user.flags.contains(.isPremium)",
            "user.emojiStatus == nil",
            "GRVMLocalPremiumPresentation(",
            "isPremium: true",
            "PeerEmojiStatus(content: .emoji(fileId: state.fileId)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, presentation)

        title = source(
            "submodules/TelegramUI/Components/ChatTitleView/Sources/"
            "ChatTitleComponent.swift"
        )
        for token in (
            "import SwiftSignalKit",
            "grvmLocalPremiumStateDisposable",
            "grvmLocalPremiumPeerState(",
            "self.state?.updated(transition: .immediate)",
            "grvmLocalPremiumPresentation(",
            "titleStatusIcon = .emojiStatus(grvmPresentation.emojiStatus)",
            "titleCredibilityIcon = .premium",
        ):
            with self.subTest(surface="title", token=token):
                self.assertIn(token, title)

        header = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/"
            "PeerInfoHeaderNode.swift"
        )
        for token in (
            "grvmLocalPremiumStateDisposable",
            "grvmLocalPremiumPeerState(",
            "self.requestUpdateLayout?(false)",
            "grvmLocalPremiumPresentation(",
            "statusIcon = .emojiStatus(grvmPresentation.emojiStatus)",
            "credibilityIcon = .premium",
            "peer.isPremium || grvmPresentation != nil",
        ):
            with self.subTest(surface="header", token=token):
                self.assertIn(token, header)

        peer_utils = source(
            "submodules/TelegramCore/Sources/Utils/PeerUtils.swift"
        )
        self.assertNotIn("GRVMLocalPremiumPeerState", peer_utils)
        self.assertNotIn("GRVMLocalPremiumPresentation", peer_utils)


if __name__ == "__main__":
    unittest.main()
