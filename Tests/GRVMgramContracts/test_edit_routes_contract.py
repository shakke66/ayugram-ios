import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "submodules/TelegramCore/Sources"
HOOKS = CORE / "AyuGramHooks.swift"
EDITABLE_CONTENT = CORE / "SyncCore/GRVMEditableMessageContent.swift"
REQUEST_EDIT = CORE / "PendingMessages/RequestEditMessage.swift"
ACCOUNT_STATE = CORE / "State/AccountStateManagementUtils.swift"
COORDINATOR = ROOT / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
MANAGER = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"


def window(value: str, anchor: str, size: int) -> str:
    offset = value.index(anchor)
    return value[offset : offset + size]


class EditRouteContractTests(unittest.TestCase):
    def test_account_scoped_revision_hook_is_wired(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        manager = MANAGER.read_text(encoding="utf-8")
        self.assertIn(
            "preserveEditRevision: ((PeerId, Message, GRVMEditableMessageContent) -> Bool)?",
            hooks,
        )
        self.assertIn(
            "content: content",
            manager,
        )
        self.assertNotIn("shouldSaveEditHistory: (() -> Bool)?", hooks)
        self.assertNotIn("onMessageEdited: ((Message) -> Void)?", hooks)

    def test_outgoing_response_routes_preserve_before_update(self) -> None:
        value = REQUEST_EDIT.read_text(encoding="utf-8")
        hooks = HOOKS.read_text(encoding="utf-8")
        self.assertIn("func grvmApplyEditedMessage(", hooks)
        helper = window(hooks, "func grvmApplyEditedMessage(", 5500)
        decision = window(hooks, "func grvmPreserveEditRevisionIfNeeded(", 3500)
        self.assertIn("transaction.getMessage(id)", decision)
        self.assertIn("GRVMEditableMessageContent(message: previous)", decision)
        self.assertIn(
            "GRVMEditableMessageContent(message: grvmMergedEditedMessage(",
            decision,
        )
        self.assertIn("markHistory: false", decision)
        self.assertNotIn("GRVMEditableMessageContent(message: incoming)", decision)
        self.assertIn("previousContent != incomingContent", decision)
        self.assertIn(
            "AyuGramHooks.preserveEditRevision?(accountPeerId, previous, previousContent)",
            decision,
        )
        self.assertIn("grvmPreserveEditRevisionIfNeeded(", helper)
        self.assertIn("transaction.updateMessage(id", helper)
        self.assertLess(
            decision.index("previousContent != incomingContent"),
            decision.index("preserveEditRevision"),
        )
        self.assertLess(
            helper.index("grvmPreserveEditRevisionIfNeeded("),
            helper.index("transaction.updateMessage(id"),
        )
        for anchor in (
            "case .updateEditMessage(let data):",
            "case .updateNewMessage(let data):",
            "case .updateEditChannelMessage(let data):",
            "case .updateNewChannelMessage(let data):",
        ):
            with self.subTest(anchor=anchor):
                self.assertIn("grvmApplyEditedMessage(", window(value, anchor, 1800))

        self.assertIn("for update in result.allUpdates", value)
        self.assertIn("let users = result.users", value)
        self.assertIn("let chats = result.chats", value)
        self.assertIn("case .updateNewScheduledMessage(let data):", value)
        self.assertIn("namespace: Namespaces.Message.ScheduledCloud", value)
        self.assertIn("case .updateQuickReplyMessage(let data):", value)
        self.assertIn("namespace: Namespaces.Message.QuickReplyCloud", value)
        self.assertNotIn("case let .updates(updatesData):", value)

    def test_incoming_edit_preserves_before_mutation_and_marks_history(self) -> None:
        value = ACCOUNT_STATE.read_text(encoding="utf-8")
        section = window(value, "case let .EditMessage(id, message):", 9000)
        self.assertIn("grvmPreserveEditRevisionIfNeeded(", section)
        self.assertIn("transaction.updateMessage(id", section)
        self.assertLess(
            section.index("grvmPreserveEditRevisionIfNeeded("),
            section.index("transaction.updateMessage(id"),
        )
        self.assertIn("grvmMergedEditStateAttributes(", section)
        self.assertNotIn("shouldSaveForBots", section)

    def test_merge_retains_persistent_state_and_adds_one_history_marker(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        anchor = "func grvmMergedEditedMessage("
        self.assertIn(anchor, hooks)
        helper = window(hooks, anchor, 5000)
        self.assertIn("grvmMergedEditStateAttributes(", helper)
        self.assertIn("withUpdatedAttributes", helper)
        state_anchor = "func grvmMergedEditStateAttributes("
        self.assertIn(state_anchor, hooks)
        state_helper = window(hooks, state_anchor, 4000)
        self.assertIn("GRVMDeletedMessageAttribute", state_helper)
        self.assertIn("GRVMEditHistoryMessageAttribute", state_helper)
        self.assertIn("markHistory", state_helper)

    def test_replayed_identical_update_compares_one_canonical_payload(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        anchor = "func grvmPreserveEditRevisionIfNeeded("
        self.assertIn(anchor, hooks)
        helper = hooks[hooks.index(anchor) : hooks.index("func grvmMergedEditedMessage(")]
        self.assertEqual(1, helper.count("GRVMEditableMessageContent(message: previous)"))
        self.assertEqual(
            1,
            helper.count("GRVMEditableMessageContent(message: grvmMergedEditedMessage("),
        )
        self.assertEqual(1, helper.count("markHistory: false"))
        self.assertNotIn("GRVMEditableMessageContent(message: incoming)", helper)
        self.assertIn("guard previousContent != incomingContent else", helper)
        self.assertIn("previousContent)", helper)

    def test_paid_full_to_preview_noop_compares_effective_merged_media(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        decision = hooks[
            hooks.index("func grvmPreserveEditRevisionIfNeeded(") :
            hooks.index("func grvmMergedEditedMessage(")
        ]
        merge = hooks[
            hooks.index("func grvmMergedEditedMessage(") :
            hooks.index("func grvmApplyEditedMessage(")
        ]
        uses_effective_merge = (
            "GRVMEditableMessageContent(message: grvmMergedEditedMessage(" in decision
            and "markHistory: false" in decision
        )
        retains_previous_full_media = (
            "case .full = previousPaidContent.extendedMedia.first" in merge
            and "updatedMedia = previous.media" in merge
        )

        previous = ("unchanged", "full")

        def effective_incoming(text: str, paid_media: str) -> tuple[str, str]:
            if uses_effective_merge and retains_previous_full_media and paid_media == "preview":
                paid_media = "full"
            return (text, paid_media)

        no_op = effective_incoming("unchanged", "preview")
        real_edit = effective_incoming("changed", "preview")
        replay = effective_incoming("unchanged", "preview")

        self.assertEqual(previous, no_op)
        self.assertNotEqual(previous, real_edit)
        self.assertEqual(no_op, replay)
        self.assertNotIn("GRVMEditableMessageContent(message: incoming)", decision)

    def test_live_map_timeout_and_proximity_are_distinct_canonical_edits(self) -> None:
        source = EDITABLE_CONTENT.read_text(encoding="utf-8")
        projection = source[
            source.index("} else if let map = media as? TelegramMediaMap {") :
            source.index("} else if let invoice = media as? TelegramMediaInvoice {")
        ]
        projected_fields = [
            field
            for field in (
                "latitude",
                "longitude",
                "heading",
                "accuracyRadius",
                "venue",
                "address",
                "liveBroadcastingTimeout",
                "liveProximityNotificationRadius",
            )
            if f"{field}: map.{field}" in projection
        ]

        def canonical_map(timeout: int | None, proximity: int | None) -> tuple[object, ...]:
            values = {
                "latitude": 55.7558,
                "longitude": 37.6173,
                "heading": 90,
                "accuracyRadius": 15.0,
                "venue": ("Office", "Main street"),
                "address": ("RU", "Moscow"),
                "liveBroadcastingTimeout": timeout,
                "liveProximityNotificationRadius": proximity,
            }
            return tuple(values[field] for field in projected_fields)

        baseline = canonical_map(timeout=60, proximity=100)
        timeout_edit = canonical_map(timeout=120, proximity=100)
        proximity_edit = canonical_map(timeout=60, proximity=250)

        self.assertNotEqual(baseline, timeout_edit)
        self.assertNotEqual(baseline, proximity_edit)

        map_content = source[
            source.index("public struct GRVMEditableMapContent:") :
            source.index("public struct GRVMEditableInvoiceContent:")
        ]
        self.assertIn("public let liveBroadcastingTimeout: Int32?", map_content)
        self.assertIn("public let liveProximityNotificationRadius: Int32?", map_content)

    def test_existing_scheduled_and_quick_reply_rows_use_shared_apply_helper(self) -> None:
        value = ACCOUNT_STATE.read_text(encoding="utf-8")
        scheduled_offset = value.rindex("case let .AddScheduledMessages(messages):")
        quick_reply_offset = value.rindex("case let .AddQuickReplyMessages(messages):")
        scheduled = value[scheduled_offset : scheduled_offset + 2200]
        quick_reply = value[quick_reply_offset : quick_reply_offset + 2200]
        for section in (scheduled, quick_reply):
            self.assertIn("grvmApplyEditedMessage(", section)
            self.assertIn("transaction.addMessages", section)
            self.assertNotIn("transaction.updateMessage(id) { _", section)

    def test_coordinator_fingerprints_then_atomically_saves_and_copies_media(self) -> None:
        value = COORDINATOR.read_text(encoding="utf-8")
        signature = (
            "public func preserveEditRevision(_ message: Message, "
            "content: GRVMEditableMessageContent) -> Bool"
        )
        self.assertIn(signature, value)
        section = window(value, signature, 9000)
        for anchor in (
            "guard settings.saveEditHistory",
            "grvmContentFingerprint(content)",
            "editableContent: content",
            "self.store.saveRevision(",
            "self.index.insertRevised(",
            "self.mediaStore.archive(",
        ):
            self.assertIn(anchor, section)
        self.assertLess(section.index("grvmContentFingerprint("), section.index("self.store.saveRevision("))
        self.assertNotIn("saveForBots", section)

    def test_canonical_payload_is_owned_by_telegram_core(self) -> None:
        self.assertTrue(EDITABLE_CONTENT.exists())
        value = EDITABLE_CONTENT.read_text(encoding="utf-8")
        self.assertIn("public struct GRVMEditableMessageContent: Codable, Equatable", value)
        self.assertIn("public init(message: Message)", value)
        self.assertIn("public init(message: StoreMessage)", value)


if __name__ == "__main__":
    unittest.main()
