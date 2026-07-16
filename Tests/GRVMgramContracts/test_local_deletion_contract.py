import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER = ROOT / "submodules/Postbox/Sources/LocalMessageDeletionMarker.swift"
INDEX = ROOT / "submodules/Postbox/Sources/MessageHistoryIndexTable.swift"
HISTORY = ROOT / "submodules/Postbox/Sources/MessageHistoryTable.swift"
POSTBOX = ROOT / "submodules/Postbox/Sources/Postbox.swift"
SEED = ROOT / "submodules/Postbox/Sources/SeedConfiguration.swift"
TELEGRAM_SEED = (
    ROOT
    / "submodules/TelegramCore/Sources/SyncCore/SyncCore_StandaloneAccountTransaction.swift"
)
DELETED_ATTRIBUTE = (
    ROOT
    / "submodules/TelegramCore/Sources/SyncCore/GRVMDeletedMessageAttribute.swift"
)
EDIT_ATTRIBUTE = (
    ROOT
    / "submodules/TelegramCore/Sources/SyncCore/GRVMEditHistoryMessageAttribute.swift"
)
ACCOUNT_MANAGER = ROOT / "submodules/TelegramCore/Sources/Account/AccountManager.swift"
COORDINATOR = (
    ROOT / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
)
REGISTRY = ROOT / "submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift"


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


class LocalDeletionContractTests(unittest.TestCase):
    def test_marker_protocol_exists(self) -> None:
        self.assertTrue(MARKER.exists())
        source = MARKER.read_text(encoding="utf-8")
        self.assertIn("public protocol LocalMessageDeletionMarker", source)
        self.assertIn("func isLocallyDeletedMessage", source)

    def test_incoming_counts_skip_marker(self) -> None:
        source = HISTORY.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("!isLocallyDeletedMessage"), 2)

    def test_marked_incoming_reinsert_and_move_never_reenter_unread(self) -> None:
        def admitted_to_read_state(*, incoming: bool, locally_deleted: bool) -> bool:
            return incoming and not locally_deleted

        scenarios = (
            ("fresh incoming insert", True, False, True),
            ("marked incoming reinsert", True, True, False),
            ("outgoing reinsert", False, True, False),
            ("fresh incoming moving update", True, False, True),
            ("marked incoming moving update", True, True, False),
        )
        for name, incoming, locally_deleted, expected in scenarios:
            with self.subTest(name=name):
                self.assertEqual(
                    expected,
                    admitted_to_read_state(
                        incoming=incoming,
                        locally_deleted=locally_deleted,
                    ),
                )

        source = HISTORY.read_text(encoding="utf-8")
        insert = source[
            source.index("case let .InsertMessage(storeMessage):") :
            source.index("case let .InsertExistingMessage(storeMessage):")
        ]
        moving = source[
            source.index("case let .Update(index, storeMessage):") :
            source.index("case let .UpdateTimestamp(index, timestamp):")
        ]
        predicate = (
            "!message.flags.intersection(.IsIncomingMask).isEmpty "
            "&& !isLocallyDeletedMessage(message.attributes)"
        )
        self.assertIn(predicate, insert)
        self.assertIn(predicate, moving)

    def test_index_has_local_deletion_bit_and_idempotent_transition(self) -> None:
        source = INDEX.read_text(encoding="utf-8")
        self.assertIn("HistoryEntryMessageFlagLocallyDeleted", source)
        self.assertIn("func markMessageLocallyDeleted(_ id: MessageId) -> Bool", source)
        self.assertIn("flags &= ~HistoryEntryMessageFlagIncoming", source)
        self.assertIn("flags |= HistoryEntryMessageFlagLocallyDeleted", source)
        self.assertIn("isLocallyDeletedMessage(message.attributes)", source)
        self.assertGreaterEqual(
            source.count("(flags & HistoryEntryMessageFlagLocallyDeleted) == 0"),
            2,
        )

    def test_atomic_transition_cleans_unread_tags_and_actions(self) -> None:
        source = HISTORY.read_text(encoding="utf-8")
        method = swift_block(source, "func markMessageAsLocallyDeleted(")

        for anchor in (
            "readStateTable.deleteMessages",
            "seedConfiguration.locallyDeletedMessageTags",
            "pendingActionsTable.removeMessage",
            "timeBasedAttributesTable.remove",
            "messageHistoryIndexTable.markMessageLocallyDeleted",
            ".Update(",
        ):
            self.assertIn(anchor, method)
        self.assertEqual(method.count("readStateTable.deleteMessages"), 1)
        self.assertNotIn(
            "deleteMessages(",
            method.replace("readStateTable.deleteMessages", ""),
        )
        self.assertNotIn("justRemove(", method)
        self.assertNotIn("removeMessages(", method)

    def test_marker_guard_precedes_every_mutation(self) -> None:
        source = HISTORY.read_text(encoding="utf-8")
        method = swift_block(source, "func markMessageAsLocallyDeleted(")

        self.assertIn("attribute is LocalMessageDeletionMarker", method)
        attribute_check = method.index("attribute is LocalMessageDeletionMarker")
        marker_check = method.index("!isLocallyDeletedMessage")
        self.assertLess(attribute_check, marker_check)
        self.assertLess(marker_check, method.index("readStateTable.deleteMessages"))
        self.assertLess(marker_check, method.index("pendingActionsTable.removeMessage"))
        self.assertLess(
            marker_check,
            method.index("messageHistoryIndexTable.markMessageLocallyDeleted"),
        )

    def test_transition_preserves_message_shape_and_unrelated_tags(self) -> None:
        source = HISTORY.read_text(encoding="utf-8")
        method = swift_block(source, "func markMessageAsLocallyDeleted(")

        self.assertRegex(
            method,
            r"tags:\s*message\.tags\.subtracting\(self\.seedConfiguration\.locallyDeletedMessageTags\)",
        )
        for field in (
            "groupingKey: message.groupingKey",
            "threadId: message.threadId",
            "flags: message.flags",
            "globalTags: updatedGlobalTags",
            "localTags: message.localTags",
        ):
            self.assertIn(field, method)
        self.assertNotIn("tags: []", method)
        self.assertNotIn("flags: []", method)
        self.assertNotIn("subtracting(.Incoming)", method)

    def test_local_deletion_removes_call_views_but_keeps_other_global_tags(self) -> None:
        calls = 1 << 0
        missed_calls = 1 << 1
        unrelated = 1 << 7
        configured_call_tags = calls | missed_calls
        messages = {
            10: calls | missed_calls | unrelated,
            11: calls,
            12: unrelated,
        }

        before_calls = {message_id for message_id, tags in messages.items() if tags & calls}
        before_missed = {
            message_id for message_id, tags in messages.items() if tags & missed_calls
        }
        messages[10] = messages[10] & ~configured_call_tags
        after_calls = {message_id for message_id, tags in messages.items() if tags & calls}
        after_missed = {
            message_id for message_id, tags in messages.items() if tags & missed_calls
        }

        self.assertEqual({10, 11}, before_calls)
        self.assertEqual({10}, before_missed)
        self.assertEqual({11}, after_calls)
        self.assertEqual(set(), after_missed)
        self.assertEqual(unrelated, messages[10])

        history = HISTORY.read_text(encoding="utf-8")
        method = swift_block(history, "func markMessageAsLocallyDeleted(")
        seed = SEED.read_text(encoding="utf-8")
        telegram_seed = TELEGRAM_SEED.read_text(encoding="utf-8")
        self.assertIn("locallyDeletedMessageGlobalTags: GlobalMessageTags", seed)
        self.assertIn(
            "message.globalTags.intersection(self.seedConfiguration.locallyDeletedMessageGlobalTags)",
            method,
        )
        self.assertIn(
            "message.globalTags.subtracting(removedGlobalTags)",
            method,
        )
        self.assertIn(
            "globalTagsOperations.append(.remove([(removedGlobalTags, index)]))",
            method,
        )
        self.assertRegex(
            telegram_seed,
            r"locallyDeletedMessageGlobalTags:\s*\[\s*\.Calls,\s*\.MissedCalls\s*\]",
        )

    def test_postbox_receives_exact_telegram_cleanup_tags(self) -> None:
        seed_source = SEED.read_text(encoding="utf-8")
        telegram_source = TELEGRAM_SEED.read_text(encoding="utf-8")

        self.assertIn("public let locallyDeletedMessageTags: MessageTags", seed_source)
        self.assertIn("locallyDeletedMessageTags: MessageTags", seed_source)
        self.assertIn(
            "self.locallyDeletedMessageTags = locallyDeletedMessageTags",
            seed_source,
        )

        match = re.search(
            r"locallyDeletedMessageTags:\s*\[(.*?)\]",
            telegram_source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertEqual(
            re.findall(r"\.\w+", match.group(1)),
            [
                ".unseenPersonalMessage",
                ".unseenReaction",
                ".unseenPollVote",
                ".pinned",
            ],
        )

    def test_transaction_forwards_all_transition_accumulators(self) -> None:
        source = POSTBOX.read_text(encoding="utf-8")
        public_method = swift_block(
            source,
            "public func markMessageAsLocallyDeleted(",
        )
        implementation = swift_block(
            source,
            "fileprivate func markMessageAsLocallyDeleted(",
        )

        self.assertIn("self.postbox?.markMessageAsLocallyDeleted(", public_method)
        for accumulator in (
            "currentOperationsByPeerId",
            "currentUpdatedSynchronizeReadStateOperations",
            "currentPendingMessageActionsOperations",
            "currentUpdatedMessageActionsSummaries",
            "currentUpdatedMessageTagSummaries",
            "currentInvalidateMessageTagSummaries",
            "currentLocalTagsOperations",
            "currentTimestampBasedMessageAttributesOperations",
        ):
            self.assertIn(accumulator, implementation)
        self.assertIn(
            "installedStoreOrUpdateMessageActionsByPeerId",
            implementation,
        )

    def test_persistent_state_attributes_are_compact_and_registered(self) -> None:
        self.assertTrue(DELETED_ATTRIBUTE.exists())
        self.assertTrue(EDIT_ATTRIBUTE.exists())
        deleted = DELETED_ATTRIBUTE.read_text(encoding="utf-8")
        edited = EDIT_ATTRIBUTE.read_text(encoding="utf-8")
        declarations = ACCOUNT_MANAGER.read_text(encoding="utf-8")

        self.assertIn(
            "GRVMDeletedMessageAttribute: MessageAttribute, LocalMessageDeletionMarker, Equatable",
            deleted,
        )
        self.assertIn(
            "GRVMEditHistoryMessageAttribute: MessageAttribute, Equatable",
            edited,
        )
        for key in ('forKey: "d"', 'forKey: "s"', 'forKey: "t"', 'forKey: "r"'):
            self.assertIn(key, deleted)
        self.assertIn('forKey: "d"', edited)
        self.assertIn('decodeOptionalInt64ForKey("t")', deleted)
        self.assertIn('decodeStringArrayForKey("r")', deleted)
        self.assertIn(
            "declareEncodable(GRVMDeletedMessageAttribute.self",
            declarations,
        )
        self.assertIn(
            "declareEncodable(GRVMEditHistoryMessageAttribute.self",
            declarations,
        )

    def test_server_merges_retain_both_local_state_attributes(self) -> None:
        source = TELEGRAM_SEED.read_text(encoding="utf-8")
        merge = swift_block(source, "mergeMessageAttributes: { previous, updated in")
        for name in (
            "GRVMDeletedMessageAttribute",
            "GRVMEditHistoryMessageAttribute",
        ):
            self.assertGreaterEqual(merge.count(name), 2)
            self.assertRegex(
                merge,
                rf"updated\.contains\(where: \{{ \$0 is {name} \}}\)",
            )

    def test_reconciliation_is_exact_account_scoped_and_batched(self) -> None:
        source = COORDINATOR.read_text(encoding="utf-8")
        method = swift_block(source, "public func reconcilePersistentMessageState(")

        self.assertEqual(method.count("self.index.snapshot()"), 1)
        self.assertIn("let batchSize = 100", method)
        self.assertIn("key.accountId == self.accountRecordId.int64", method)
        self.assertIn("self.store.deletedMessages(keys:", method)
        self.assertIn("transaction.getMessage(messageId)", method)
        self.assertIn("message.threadId ?? 0", method)
        self.assertIn("GRVMDeletedMessageAttribute(", method)
        self.assertIn("GRVMEditHistoryMessageAttribute(", method)
        self.assertIn("transaction.markMessageAsLocallyDeleted(", method)
        self.assertIn("transaction.addMessageAttribute(", method)
        self.assertNotIn("grvmStoreMessage(", method)

    def test_attribute_only_updates_preserve_unrendered_peer_ids(self) -> None:
        source = POSTBOX.read_text(encoding="utf-8")
        implementation = swift_block(
            source,
            "fileprivate func addMessageAttribute(",
        )

        self.assertIn("intermediateMessage.forwardInfo", implementation)
        self.assertIn("authorId: intermediateMessage.authorId", implementation)
        self.assertIn("attributes: currentMessage.attributes + [attribute]", implementation)
        self.assertIn("installedStoreOrUpdateMessageActionsByPeerId", implementation)

    def test_registry_reconciles_only_after_preparing_the_index(self) -> None:
        source = REGISTRY.read_text(encoding="utf-8")
        registration = swift_block(source, "private func registerOnQueue(")
        prepare = registration.index("try coordinator.prepare()")
        reconcile = registration.index("coordinator.reconcilePersistentMessageState()")
        self.assertLess(prepare, reconcile)

    def test_transition_preserves_unrendered_peer_ids(self) -> None:
        source = POSTBOX.read_text(encoding="utf-8")
        implementation = swift_block(
            source,
            "fileprivate func markMessageAsLocallyDeleted(",
        )

        self.assertIn("if let forwardInfo = intermediateMessage.forwardInfo", implementation)
        self.assertIn("authorId: forwardInfo.authorId", implementation)
        self.assertIn("sourceId: forwardInfo.sourceId", implementation)
        self.assertIn("authorId: intermediateMessage.authorId", implementation)
        self.assertNotIn("currentMessage.forwardInfo.flatMap", implementation)
        self.assertNotIn("authorId: currentMessage.author?.id", implementation)


if __name__ == "__main__":
    unittest.main()
