import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "submodules/TelegramCore/Sources"
APPLY = CORE / "TelegramEngine/Messages/ApplyGRVMMessageDeletion.swift"
HOOKS = CORE / "AyuGramHooks.swift"
COORDINATOR = ROOT / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
MANAGER = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"


def source(path: str) -> str:
    return (CORE / path).read_text(encoding="utf-8")


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
        self.assertGreaterEqual(manager.count("registry.service(accountPeerId: accountPeerId)"), 2)

    def test_every_user_visible_id_route_uses_the_helper(self) -> None:
        routes = {
            "State/AccountStateManagementUtils.swift": 2,
            "TelegramEngine/Messages/DeleteMessagesInteractively.swift": 1,
            "State/ManagedAutoremoveMessageOperations.swift": 1,
            "State/ProcessSecretChatIncomingDecryptedOperations.swift": 1,
            "State/HistoryViewStateValidation.swift": 2,
            "TelegramEngine/Peers/UpdateCachedPeerData.swift": 1,
            "TelegramEngine/Messages/DeleteMessages.swift": 4,
            "TelegramEngine/Peers/RemovePeerChat.swift": 1,
            "TelegramEngine/Messages/TelegramEngineMessages.swift": 1,
        }
        for path, minimum in routes.items():
            with self.subTest(path=path):
                self.assertGreaterEqual(source(path).count("_internal_applyMessageDeletion("), minimum)

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
        allowed_internal = {
            "PendingMessages/EnqueueMessage.swift",
            "State/ManagedSecretChatOutgoingOperations.swift",
            "TelegramEngine/Messages/ApplyGRVMMessageDeletion.swift",
            "TelegramEngine/Messages/DeleteMessages.swift",
        }
        allowed_transaction = {
            "PendingMessages/PendingPeerMediaUploadManager.swift",
            "State/ForumChannelState.swift",
            "TelegramEngine/Messages/DeleteMessages.swift",
            "TelegramEngine/Messages/QuickReplyMessages.swift",
            "TelegramEngine/Messages/ScheduledMessages.swift",
        }
        internal_definition = re.compile(r"func _internal_deleteMessages\(")
        unexpected_internal = []
        unexpected_transaction = []
        for path in CORE.rglob("*.swift"):
            relative = path.relative_to(CORE).as_posix()
            value = path.read_text(encoding="utf-8")
            calls = value.count("_internal_deleteMessages(")
            if internal_definition.search(value):
                calls -= 1
            if calls and relative not in allowed_internal:
                unexpected_internal.append(relative)
            if "transaction.deleteMessages(" in value and relative not in allowed_transaction:
                unexpected_transaction.append(relative)
        self.assertEqual(unexpected_internal, [])
        self.assertEqual(unexpected_transaction, [])


if __name__ == "__main__":
    unittest.main()
