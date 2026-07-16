from collections import Counter
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "submodules/TelegramCore/Sources"
APPLY = CORE / "TelegramEngine/Messages/ApplyGRVMMessageDeletion.swift"
HOOKS = CORE / "AyuGramHooks.swift"
COORDINATOR = ROOT / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
MANAGER = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
POSTBOX = ROOT / "submodules/Postbox/Sources/Postbox.swift"
MESSAGE_HISTORY_TABLE = ROOT / "submodules/Postbox/Sources/MessageHistoryTable.swift"


def source(path: str) -> str:
    return (CORE / path).read_text(encoding="utf-8")


def occurrence_window(value: str, anchor: str, occurrence: int, size: int = 3000) -> str:
    offset = 0
    for _ in range(occurrence):
        offset = value.index(anchor, offset) + len(anchor)
    return value[offset : offset + size]


class DeleteRouteContractTests(unittest.TestCase):
    def test_central_helper_partitions_persisted_and_physical_deletes(self) -> None:
        self.assertTrue(APPLY.exists())
        value = APPLY.read_text(encoding="utf-8")
        for anchor in (
            "public enum GRVMDeletionMode",
            "func _internal_applyMessageDeletion(",
            "private func grvmCanArchive(",
            "AyuGramHooks.preserveDeletedMessages?(accountPeerId",
            "transaction.markMessageAsLocallyDeleted(",
            "GRVMDeletedMessageAttribute(",
            "_internal_deleteMessages(",
            "case .forceCleanup",
        ):
            self.assertIn(anchor, value)
        self.assertIn("message.flags.intersection([.Unsent, .Failed, .Sending]).isEmpty", value)
        self.assertIn("isLocallyDeletedMessage(message.attributes)", value)

    def test_account_scoped_hook_is_synchronous_and_wired(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        manager = MANAGER.read_text(encoding="utf-8")
        autoremove = source("State/ManagedAutoremoveMessageOperations.swift")
        self.assertIn(
            "preserveDeletedMessages: ((PeerId, [Message], GRVMDeletionSource) -> [MessageId: [String]])?",
            hooks,
        )
        self.assertIn(
            "public func preserveDeletedMessages(_ messages: [Message], source: GRVMDeletionSource) -> [MessageId: [String]]",
            coordinator,
        )
        self.assertIn("guard settings.saveDeletedMessages", coordinator)
        self.assertIn("directBot", coordinator)
        self.assertIn("try self.store.saveDeleted(", coordinator)
        self.assertIn("self.index.insertDeleted(", coordinator)
        self.assertIn("shouldPreserveOneTimeMedia: ((PeerId) -> Bool)?", hooks)
        self.assertIn("shouldPreserveOneTimeMedia?(accountPeerId)", autoremove)
        hook_assignment = occurrence_window(
            manager,
            "AyuGramHooks.shouldPreserveOneTimeMedia = { [weak self] accountPeerId in",
            1,
            500,
        )
        self.assertIn(
            "registry.service(accountPeerId: accountPeerId)?.settingsSnapshot().saveDeletedMessages ?? false",
            hook_assignment,
        )
        self.assertNotIn("primaryService", hook_assignment)
        self.assertGreaterEqual(manager.count("registry.service(accountPeerId: accountPeerId)"), 2)

    def test_clear_call_history_collects_exact_ids_and_uses_preservation_route(self) -> None:
        delete_messages = source("TelegramEngine/Messages/DeleteMessages.swift")
        call_section = occurrence_window(delete_messages, "func _internal_clearCallHistory(", 1, 7000)
        success_anchor = "|> `catch` { success -> Signal<Void, NoError> in"
        success_section = occurrence_window(call_section, success_anchor, 1, 1800)
        self.assertIn("if success {", success_section)
        self.assertIn(
            "let ids = transaction.messageIdsWithGlobalTag(GlobalMessageTags.Calls)",
            success_section,
        )
        self.assertIn("_internal_applyMessageDeletion(", success_section)
        self.assertIn("accountPeerId: account.peerId", success_section)
        self.assertIn("mediaBox: account.postbox.mediaBox", success_section)
        self.assertIn("mode: .server(.localAction)", success_section)
        self.assertNotIn("removeAllMessagesWithGlobalTag", success_section)
        self.assertLess(call_section.index("account.network.request("), call_section.index(success_anchor))
        self.assertLess(success_section.index("if success {"), success_section.index("messageIdsWithGlobalTag"))
        self.assertLess(success_section.index("messageIdsWithGlobalTag"), success_section.index("} else {"))

    def test_global_tag_ids_forward_and_ignore_holes(self) -> None:
        postbox = POSTBOX.read_text(encoding="utf-8")
        transaction_helper = occurrence_window(
            postbox,
            "public func messageIdsWithGlobalTag(_ tag: GlobalMessageTags) -> [MessageId]",
            1,
            500,
        )
        self.assertIn("messageIdsWithGlobalTag(tag: tag)", transaction_helper)

        postbox_helper = occurrence_window(
            postbox,
            "fileprivate func messageIdsWithGlobalTag(tag: GlobalMessageTags) -> [MessageId]",
            1,
            1000,
        )
        self.assertIn("messageHistoryTable.allIndicesWithGlobalTag(tag: tag)", postbox_helper)
        self.assertIn("case let .message(index):", postbox_helper)
        self.assertIn("return index.id", postbox_helper)
        self.assertIn("case .hole:", postbox_helper)
        self.assertIn("return nil", postbox_helper)

        message_history = MESSAGE_HISTORY_TABLE.read_text(encoding="utf-8")
        table_helper = occurrence_window(
            message_history,
            "func allIndicesWithGlobalTag(tag: GlobalMessageTags)",
            1,
            500,
        )
        self.assertIn("globalTagsTable.laterEntries(tag, index: nil, count: 0)", table_helper)
        self.assertIn("assert(tag.isSingleTag)", table_helper)
        self.assertNotIn("globalTagsTable.getAll()", table_helper)

    def test_every_user_visible_id_route_uses_the_helper(self) -> None:
        routes = (
            ("State/AccountStateManagementUtils.swift", "case let .DeleteMessagesWithGlobalIds(ids):", 1, 3000),
            ("State/AccountStateManagementUtils.swift", "case let .DeleteMessages(ids):", 1, 3000),
            ("TelegramEngine/Messages/DeleteMessagesInteractively.swift", "func deleteMessagesInteractively(", 1, 10000),
            ("State/ManagedAutoremoveMessageOperations.swift", "func managedAutoremoveMessageOperations(", 1, 5000),
            ("State/ProcessSecretChatIncomingDecryptedOperations.swift", "case let .deleteMessages(globallyUniqueIds):", 1, 3000),
            ("State/HistoryViewStateValidation.swift", "if let message = transaction.getMessage(id), isLocallyDeletedMessage(message.attributes)", 1, 1000),
            ("State/HistoryViewStateValidation.swift", "if let message = transaction.getMessage(id), isLocallyDeletedMessage(message.attributes)", 2, 1000),
            ("TelegramEngine/Peers/UpdateCachedPeerData.swift", "if let minAvailableMessageId = minAvailableMessageId, minAvailableMessageIdUpdated", 1, 3000),
            ("TelegramEngine/Messages/DeleteMessages.swift", "func _internal_deleteAllMessagesWithAuthor(", 1, 3000),
            ("TelegramEngine/Messages/DeleteMessages.swift", "func _internal_deleteAllMessagesWithForwardAuthor(", 1, 3000),
            ("TelegramEngine/Messages/DeleteMessages.swift", "func _internal_clearHistory(", 1, 3000),
            ("TelegramEngine/Messages/DeleteMessages.swift", "func _internal_clearHistoryInRange(", 1, 3000),
            ("TelegramEngine/Peers/RemovePeerChat.swift", "func _internal_removePeerChat(", 1, 3000),
            ("TelegramEngine/Messages/TelegramEngineMessages.swift", "public func deleteMessages(transaction: Transaction, ids: [MessageId])", 1, 1000),
        )
        for path, anchor, occurrence, size in routes:
            with self.subTest(path=path, anchor=anchor, occurrence=occurrence):
                self.assertIn(
                    "_internal_applyMessageDeletion(",
                    occurrence_window(source(path), anchor, occurrence, size),
                )

    def test_force_cleanup_has_a_real_archive_call_site(self) -> None:
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("public func clearDeleted(", coordinator)
        self.assertIn("self.store.beginDeletedCleanup(", coordinator)
        self.assertIn("self.runCleanupJob(job)", coordinator)
        self.assertIn("self.mediaStore.removeArchivedFiles(", coordinator)
        self.assertIn("self.store.markCleanupFilesRemoved(", coordinator)
        self.assertIn("mode: .forceCleanup", coordinator)
        self.assertIn("self.store.finalizeDeletedCleanup(", coordinator)
        self.assertIn("self.index.removeDeleted(", coordinator)
        self.assertNotIn("self.store.removeDeleted(", coordinator)
        self.assertNotIn("self.mediaStore.remove(", coordinator)

    def test_save_for_bots_never_gates_edit_history(self) -> None:
        value = source("State/AccountStateManagementUtils.swift")
        edit_section = occurrence_window(value, "case let .EditMessage(id, message):", 1)
        self.assertIn("AyuGramHooks.preserveEditRevision?(accountPeerId, oldMessage)", edit_section)
        self.assertNotIn("shouldSaveForBots", edit_section)

    def test_global_range_author_and_forward_routes_collect_exact_ids(self) -> None:
        account_state = source("State/AccountStateManagementUtils.swift")
        delete_messages = source("TelegramEngine/Messages/DeleteMessages.swift")
        cached_peer = source("TelegramEngine/Peers/UpdateCachedPeerData.swift")
        self.assertIn("transaction.messageIdsForGlobalIds(ids)", account_state)
        self.assertGreaterEqual(delete_messages.count("transaction.withAllMessages("), 4)
        self.assertIn("message.author?.id == authorId", delete_messages)
        self.assertIn("message.forwardInfo?.author?.id == forwardAuthorId", delete_messages)
        self.assertIn("AyuGramHooks.shouldSaveDeletedMessages?(accountPeerId)", delete_messages)
        self.assertIn("transaction.withAllMessages(peerId: peerId", cached_peer)
        self.assertGreaterEqual(delete_messages.count("isLocallyDeletedMessage(message.attributes)"), 4)
        self.assertIn("isLocallyDeletedMessage(message.attributes)", account_state)
        self.assertIn("isLocallyDeletedMessage(message.attributes)", cached_peer)

    def test_validation_treats_markers_as_boundaries_and_never_removes_them(self) -> None:
        value = source("State/HistoryViewStateValidation.swift")
        self.assertGreaterEqual(value.count("isLocallyDeletedMessage(entry.message.attributes)"), 2)
        self.assertGreaterEqual(value.count("isLocallyDeletedMessage(message.attributes)"), 2)

    def test_remaining_direct_deletes_are_only_documented_technical_routes(self) -> None:
        expected_internal = Counter({
            ("PendingMessages/EnqueueMessage.swift", "_internal_deleteMessages(transaction: transaction, mediaBox: account.postbox.mediaBox, ids: removeMessageIds, deleteMedia: false)"): 1,
            ("State/ManagedSecretChatOutgoingOperations.swift", "_internal_deleteMessages(transaction: transaction, mediaBox: postbox.mediaBox, ids: [messageId])"): 1,
            ("TelegramEngine/Messages/ApplyGRVMMessageDeletion.swift", "_internal_deleteMessages("): 2,
        })
        expected_transaction = Counter({
            ("PendingMessages/PendingPeerMediaUploadManager.swift", "transaction.deleteMessages([messageId], forEachMedia: nil)"): 2,
            ("TelegramEngine/Messages/DeleteMessages.swift", "transaction.deleteMessages(ids, forEachMedia: { _ in"): 1,
            ("TelegramEngine/Messages/QuickReplyMessages.swift", "transaction.deleteMessages(existingCloudMessages.map(\\.id), forEachMedia: nil)"): 1,
            ("TelegramEngine/Messages/QuickReplyMessages.swift", "transaction.deleteMessages(existingLocalMessages.map(\\.id), forEachMedia: nil)"): 1,
            ("TelegramEngine/Messages/ScheduledMessages.swift", "transaction.deleteMessages([entry.id], forEachMedia: { media in"): 1,
        })
        actual_internal = Counter()
        actual_transaction = Counter()
        for path in CORE.rglob("*.swift"):
            relative = path.relative_to(CORE).as_posix()
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if "_internal_deleteMessages(" in stripped and not re.search(r"func _internal_deleteMessages\(", stripped):
                    actual_internal[(relative, stripped)] += 1
                if "transaction.deleteMessages(" in stripped:
                    actual_transaction[(relative, stripped)] += 1
        self.assertEqual(actual_internal, expected_internal)
        self.assertEqual(actual_transaction, expected_transaction)


if __name__ == "__main__":
    unittest.main()
