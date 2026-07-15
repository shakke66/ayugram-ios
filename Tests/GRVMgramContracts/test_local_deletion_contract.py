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
            "globalTags: message.globalTags",
            "localTags: message.localTags",
        ):
            self.assertIn(field, method)
        self.assertNotIn("tags: []", method)
        self.assertNotIn("flags: []", method)
        self.assertNotIn("subtracting(.Incoming)", method)

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
