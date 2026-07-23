import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"
INDEX = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveIndex.swift"
COORDINATOR = (
    ROOT
    / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
)
FEATURES = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatures.swift"
MANAGER = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
DELETED_CONTROLLER = (
    ROOT
    / "submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift"
)
TYPED_STRINGS = (
    ROOT / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
)
EN_STRINGS = ROOT / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings"
RU_STRINGS = ROOT / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings"


def section(value: str, start: str, end: str) -> str:
    start_index = value.find(start)
    if start_index < 0:
        raise AssertionError(f"missing section start: {start}")
    end_index = value.find(end, start_index)
    if end_index < 0:
        raise AssertionError(f"missing section end: {end}")
    return value[start_index:end_index]


class ArchiveDeleteSP01ContractTests(unittest.TestCase):
    def test_new_deletions_exclude_the_current_account_before_archive_admission(self) -> None:
        value = COORDINATOR.read_text(encoding="utf-8")
        preservation = section(
            value,
            "private func preserveDeletedMessagesOnQueue(",
            "public func preserveEditRevision(",
        )

        gate = "message.author?.id == self.accountPeerId"
        self.assertIn(gate, preservation)
        self.assertLess(preservation.index(gate), preservation.index("uniqueMessages[self.messageKey(message)]"))
        gate_window = preservation[preservation.index(gate) : preservation.index(gate) + 180]
        self.assertIn("continue", gate_window)

    def test_historical_self_authored_rows_are_hidden_and_scheduled_for_cleanup(self) -> None:
        store = STORE.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")

        prepare = section(coordinator, "func prepare() throws", "func shutdownForReplacement()")
        for token in (
            "excludingSenderId: self.accountPeerId.toInt64()",
            "beginExcludedSenderCleanup(",
            "senderId: self.accountPeerId.toInt64()",
        ):
            with self.subTest(token=token):
                self.assertIn(token, prepare)

        deleted_query = section(
            coordinator,
            "public func deletedMessages(",
            "public func editHistory(",
        )
        self.assertIn(
            "excludingSenderId: self.accountPeerId.toInt64()",
            deleted_query,
        )

        store_query = section(
            store,
            "public func deletedMessages(_ query:",
            "public func deletedMessages(keys:",
        )
        self.assertIn("excludingSenderId: Int64?", store_query)
        self.assertIn('clauses.append("sender_id != ?")', store_query)

    def test_exact_cleanup_removes_all_message_layers_and_only_exact_key(self) -> None:
        value = STORE.read_text(encoding="utf-8")

        targeted = section(
            value,
            "public func beginDeletedCleanup(key:",
            "public func revalidateDeletedCleanup(",
        )
        for token in (
            "key.accountId",
            "key.peerId",
            "key.namespace",
            "key.messageId",
            "key.threadId",
            "messageKeys: [key]",
        ):
            with self.subTest(token=token):
                self.assertIn(token, targeted)

        finalize = section(
            value,
            "public func finalizeDeletedCleanup(",
            "private func perform<",
        )
        for token in (
            "DELETE FROM archived_message_media",
            "DELETE FROM edit_revisions",
            "DELETE FROM archived_messages",
            "values: self.keyValues(key)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, finalize)

        mapping_delete = finalize[
            finalize.index("DELETE FROM archived_message_media") :
            finalize.index("DELETE FROM edit_revisions")
        ]
        self.assertNotIn("revision_id = 0", mapping_delete)

    def test_exact_cleanup_uses_a_reserved_collision_free_synthetic_scope(self) -> None:
        value = STORE.read_text(encoding="utf-8")
        targeted = section(
            value,
            "public func beginDeletedCleanup(key:",
            "public func beginExcludedSenderCleanup(",
        )
        sender_cleanup = section(
            value,
            "public func beginExcludedSenderCleanup(",
            "public func revalidateDeletedCleanup(",
        )

        for token in (
            "let existingJobs = try self.queryCleanupJobs(",
            "if let existing = existingJobs.first(where: { $0.messageKeys == [key] })",
            "let scopePeerId = Int64.min + 1",
            "job.peerId == scopePeerId",
            "job.threadId ?? 0",
            "while occupiedScopeThreadIds.contains(scopeThreadId)",
            "scopeThreadId &+= 1",
        ):
            with self.subTest(token=token):
                self.assertIn(token, targeted)

        self.assertNotIn("let scopePeerId = key.peerId", targeted)
        self.assertIn("let scopePeerId = Int64.min", sender_cleanup)

    def test_cleanup_counts_every_target_mapping_and_never_unlinks_shared_media(self) -> None:
        value = STORE.read_text(encoding="utf-8")
        planning = section(
            value,
            "private func cleanupMediaRecords(",
            "private func revalidatedCleanupMediaRecords(",
        )
        revalidation = section(
            value,
            "private func revalidatedCleanupMediaRecords(",
            "public func beginDeletedCleanup(",
        )

        self.assertIn("mappedResourceIds(database, key: key)", planning)
        self.assertIn("mappedResourceReferenceCounts(database, key: key)", revalidation)
        self.assertIn("targetedReferencesByResourceId[resourceId, default: 0] += referenceCount", revalidation)
        self.assertIn("references == Int64(targetedReferences)", revalidation)

    def test_exact_cleanup_evicts_both_deleted_and_revision_runtime_indexes(self) -> None:
        index = INDEX.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        finalization = section(
            coordinator,
            "let keys = try self.store.finalizeDeletedCleanup(id: job.id)",
            "subscriber.putNext(ids)",
        )

        self.assertIn("public func removeRevised(_ keys: Set<GRVMMessageKey>)", index)
        self.assertIn("revised: current.revised.subtracting(keys)", index)
        self.assertIn("self.index.removeDeleted(keySet)", finalization)
        self.assertIn("self.index.removeRevised(keySet)", finalization)

    def test_exact_cleanup_is_exposed_through_the_account_scoped_bridge(self) -> None:
        features = FEATURES.read_text(encoding="utf-8")
        manager = MANAGER.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")

        self.assertIn(
            "public static var removeDeletedMessage: ((PeerId, GRVMMessageKey) -> Signal<[MessageId], GRVMClearDeletedError>)?",
            features,
        )
        bridge = manager[manager.index("AyuGramFeatures.removeDeletedMessage =") :]
        self.assertIn("service.removeDeletedMessage(key)", bridge[:900])

        removal = section(
            coordinator,
            "public func removeDeletedMessage(",
            "public func hasEditHistory(",
        )
        self.assertIn("key.accountId == self.accountRecordId.int64", removal)
        self.assertIn("self.store.beginDeletedCleanup(key: key)", removal)
        self.assertIn("self.addCleanupWaiter", removal)
        self.assertIn("self.startCleanupExecutorIfNeeded()", removal)

    def test_archive_row_long_press_confirms_exact_removal_and_surfaces_errors(self) -> None:
        value = DELETED_CONTROLLER.read_text(encoding="utf-8")

        for token in (
            "removeMessage: (GRVMMessageKey) -> Void",
            "ItemListTextWithLabelItem(",
            "longTapAction:",
            "arguments.removeMessage(message.key)",
            "AyuGramFeatures.removeDeletedMessage?(",
            "context.account.peerId, key",
            "standardTextAlertController(",
            "strings[.deletedRemoveTitle]",
            "strings[.deletedRemoveText]",
            "strings[.deletedRemoveAction]",
            "strings[.deletedRemoveErrorTitle]",
            "|> deliverOnMainQueue",
            "refreshToken.set",
            "grvmClearDeletedErrorController(",
        ):
            with self.subTest(token=token):
                self.assertIn(token, value)

    def test_permanent_removal_copy_is_typed_and_localized_in_english_and_russian(self) -> None:
        typed = TYPED_STRINGS.read_text(encoding="utf-8")
        english = EN_STRINGS.read_text(encoding="utf-8")
        russian = RU_STRINGS.read_text(encoding="utf-8")

        for case_name, resource_key in (
            ("deletedRemoveTitle", "GRVMgram.Deleted.Remove.Title"),
            ("deletedRemoveText", "GRVMgram.Deleted.Remove.Text"),
            ("deletedRemoveAction", "GRVMgram.Deleted.Remove.Action"),
            ("deletedRemoveErrorTitle", "GRVMgram.Deleted.Remove.ErrorTitle"),
        ):
            with self.subTest(case_name=case_name):
                self.assertIn(f'case {case_name} = "{resource_key}"', typed)
                self.assertIn(f'"{resource_key}" = ', english)
                self.assertIn(f'"{resource_key}" = ', russian)


if __name__ == "__main__":
    unittest.main()
