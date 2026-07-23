import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def window(text: str, marker: str, size: int = 10000) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    return text[start : start + size]


class FilteredUnreadPostboxContractTests(unittest.TestCase):
    def test_public_transaction_scan_reports_local_completeness(self) -> None:
        postbox = source("submodules/Postbox/Sources/Postbox.swift")

        self.assertIn("public struct LocalUnreadMessageScanResult: Equatable", postbox)
        self.assertIn("public let knownUnreadCount: Int", postbox)
        self.assertIn("public let hasHoles: Bool", postbox)
        self.assertIn("public let isComplete: Bool", postbox)

        transaction_api = window(
            postbox,
            "public func scanLocalUnreadMessages(",
            1800,
        )
        self.assertIn("peerId: PeerId", transaction_api)
        self.assertIn("namespace: MessageId.Namespace", transaction_api)
        self.assertIn("state: PeerReadState", transaction_api)
        self.assertIn("_ f: (Message) -> Void", transaction_api)
        self.assertIn("-> LocalUnreadMessageScanResult", transaction_api)

    def test_scan_uses_both_unread_btree_ranges_and_renders_only_candidates(self) -> None:
        postbox = source("submodules/Postbox/Sources/Postbox.swift")
        id_index = source("submodules/Postbox/Sources/MessageHistoryIndexTable.swift")
        history = source("submodules/Postbox/Sources/MessageHistoryTable.swift")

        id_range = window(id_index, "func incomingMessageIndicesInRange(", 2400)
        self.assertIn("minId: MessageId.Id", id_range)
        self.assertIn("maxId: MessageId.Id", id_range)
        self.assertIn("HistoryEntryMessageFlagIncoming", id_range)
        self.assertIn("HistoryEntryMessageFlagLocallyDeleted", id_range)
        self.assertIn("messageHistoryHoleIndexTable.closest", id_range)
        self.assertIn("readHistoryIndexEntry", id_range)

        index_range = window(history, "func incomingMessageIndicesAfterIndex(", 2600)
        self.assertIn("afterIndex: MessageIndex", index_range)
        self.assertIn(".IsIncomingMask", index_range)
        self.assertIn("isLocallyDeletedMessage", index_range)
        self.assertIn("messageHistoryHoleIndexTable.closest", index_range)
        self.assertIn("afterIndex.withNamespace(namespace)", index_range)
        self.assertIn("entry.message.index > afterIndex", index_range)
        self.assertIn("let timestampPrefix = ValueBoxKey(length: 8 + 4 + 4)", index_range)
        self.assertIn("timestampPrefix.setInt64(0, value: peerId.toInt64())", index_range)
        self.assertIn("timestampPrefix.setInt32(8, value: namespace)", index_range)
        self.assertIn("timestampPrefix.setInt32(8 + 4, value: afterIndex.timestamp)", index_range)
        self.assertNotIn("id: Int32.min", index_range)
        self.assertIn("topIndexEntry(peerId: peerId, namespace: namespace)", index_range)
        self.assertNotIn("precondition(afterIndex.id.namespace == namespace)", index_range)
        self.assertNotIn("range: minId ... (Int32.max - 1)", index_range)

        scan = window(postbox, "fileprivate func scanLocalUnreadMessages(", 5000)
        self.assertIn("case let .idBased", scan)
        self.assertIn("messageHistoryIndexTable.top(peerId, namespace: namespace)", scan)
        self.assertIn("max(maxKnownId, topLocalMessageId)", scan)
        self.assertIn("incomingMessageIndicesInRange", scan)
        self.assertIn("case let .indexBased", scan)
        self.assertIn("incomingMessageIndicesAfterIndex", scan)
        self.assertIn("messageHistoryTable.getMessage(index)", scan)
        self.assertIn("self.renderIntermediateMessage(message)", scan)
        self.assertNotIn("withAllMessages", scan)
        self.assertNotIn("allMessageIndices", scan)
        self.assertNotIn("topMessage", scan)

    def test_scan_is_read_only_and_does_not_repurpose_tags_or_read_mutators(self) -> None:
        postbox = source("submodules/Postbox/Sources/Postbox.swift")
        scan = window(postbox, "fileprivate func scanLocalUnreadMessages(", 5000)
        self.assertIn("fileprivate func scanLocalUnreadMessages(", scan)

        forbidden = (
            "MessageTags",
            "addIncomingMessages",
            "applyIncomingReadMaxId",
            "applyInteractiveMaxReadIndex",
            "resetIncomingReadStates",
            "setCombinedState",
            "withAllMessages",
        )
        for marker in forbidden:
            self.assertNotIn(marker, scan)

    def test_post_commit_update_batches_all_generic_invalidation_sources(self) -> None:
        postbox = source("submodules/Postbox/Sources/Postbox.swift")

        self.assertIn(
            "public func localUnreadMessagePeerIdsUpdates() -> Signal<Set<PeerId>, NoError>",
            postbox,
        )
        invalidation = window(
            postbox,
            "var localUnreadMessagePeerIds = Set(self.currentOperationsByPeerId.keys)",
            2600,
        )
        self.assertIn(
            "localUnreadMessagePeerIds.formUnion(alteredInitialPeerCombinedReadStates.keys)",
            invalidation,
        )
        self.assertIn(
            "localUnreadMessagePeerIds.formUnion(alteredInitialPeerThreadsSummaries.keys)",
            invalidation,
        )
        self.assertIn(
            "localUnreadMessagePeerIds.formUnion(self.currentUpdatedPeerThreadCombinedStates)",
            invalidation,
        )
        self.assertIn("currentPeerHoleOperations.keys", invalidation)
        self.assertIn("updatedPeerThreadInfos", invalidation)

        commit = window(postbox, "self.valueBox.commit()", 900)
        self.assertIn(
            "self.localUnreadMessagePeerIdsUpdatesPipe.putNext(localUnreadMessagePeerIds)",
            commit,
        )
        self.assertLess(
            commit.find("self.valueBox.commit()"),
            commit.find("self.localUnreadMessagePeerIdsUpdatesPipe.putNext"),
        )

    def test_update_signal_is_generic_event_only_without_polling_or_grvm_dependency(self) -> None:
        postbox = source("submodules/Postbox/Sources/Postbox.swift")
        signal_impl = window(
            postbox,
            "func localUnreadMessagePeerIdsUpdates() -> Signal<Set<PeerId>, NoError>",
            800,
        )
        self.assertIn("localUnreadMessagePeerIdsUpdatesPipe.signal()", signal_impl)
        self.assertNotIn("transaction(", signal_impl)
        self.assertNotIn("withAllMessages", signal_impl)
        self.assertNotIn("GRVM", signal_impl)
        self.assertNotIn("MessageTags", signal_impl)
        self.assertNotIn("Signal<Set<PeerId>, NoError>.single", signal_impl)


if __name__ == "__main__":
    unittest.main()
