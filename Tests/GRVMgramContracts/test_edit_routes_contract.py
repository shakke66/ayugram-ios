import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "submodules/TelegramCore/Sources"
HOOKS = CORE / "AyuGramHooks.swift"
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
        self.assertIn("preserveEditRevision: ((PeerId, Message) -> Bool)?", hooks)
        self.assertIn("registry.service(accountPeerId: accountPeerId)?.preserveEditRevision(message)", manager)
        self.assertNotIn("shouldSaveEditHistory: (() -> Bool)?", hooks)
        self.assertNotIn("onMessageEdited: ((Message) -> Void)?", hooks)

    def test_outgoing_response_routes_preserve_before_update(self) -> None:
        value = REQUEST_EDIT.read_text(encoding="utf-8")
        self.assertIn("private func grvmApplyEditedMessage(", value)
        helper = window(value, "private func grvmApplyEditedMessage(", 5000)
        self.assertIn("transaction.getMessage(id)", helper)
        self.assertIn("AyuGramHooks.preserveEditRevision?(accountPeerId, previous)", helper)
        self.assertIn("transaction.updateMessage(id", helper)
        self.assertLess(
            helper.index("AyuGramHooks.preserveEditRevision?(accountPeerId, previous)"),
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

    def test_incoming_edit_preserves_before_mutation_and_marks_history(self) -> None:
        value = ACCOUNT_STATE.read_text(encoding="utf-8")
        section = window(value, "case let .EditMessage(id, message):", 9000)
        self.assertIn("AyuGramHooks.preserveEditRevision?(accountPeerId, oldMessage)", section)
        self.assertIn("!grvmMessageEditContentMatches(previous: oldMessage, incoming: message)", section)
        self.assertIn("transaction.updateMessage(id", section)
        self.assertLess(
            section.index("AyuGramHooks.preserveEditRevision?(accountPeerId, oldMessage)"),
            section.index("transaction.updateMessage(id"),
        )
        self.assertIn("grvmMergedEditStateAttributes(", section)
        self.assertNotIn("shouldSaveForBots", section)

    def test_merge_retains_persistent_state_and_adds_one_history_marker(self) -> None:
        value = REQUEST_EDIT.read_text(encoding="utf-8")
        hooks = HOOKS.read_text(encoding="utf-8")
        anchor = "private func grvmMergedEditedMessage("
        self.assertIn(anchor, value)
        helper = window(value, anchor, 5000)
        self.assertIn("grvmMergedEditStateAttributes(", helper)
        self.assertIn("withUpdatedAttributes", helper)
        state_anchor = "func grvmMergedEditStateAttributes("
        self.assertIn(state_anchor, hooks)
        state_helper = window(hooks, state_anchor, 4000)
        self.assertIn("GRVMDeletedMessageAttribute", state_helper)
        self.assertIn("GRVMEditHistoryMessageAttribute", state_helper)
        self.assertIn("markHistory", state_helper)

    def test_replayed_identical_update_does_not_capture_current_content(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        anchor = "func grvmMessageEditContentMatches("
        self.assertIn(anchor, hooks)
        helper = window(hooks, anchor, 4000)
        self.assertIn("previous.text == incoming.text", helper)
        self.assertIn("TextEntitiesMessageAttribute", helper)
        self.assertIn("isEqual(to:", helper)

    def test_coordinator_fingerprints_then_atomically_saves_and_copies_media(self) -> None:
        value = COORDINATOR.read_text(encoding="utf-8")
        self.assertIn("public func preserveEditRevision(_ message: Message) -> Bool", value)
        section = window(value, "public func preserveEditRevision(_ message: Message) -> Bool", 9000)
        for anchor in (
            "guard settings.saveEditHistory",
            "grvmContentFingerprint(",
            "self.store.saveRevision(",
            "self.index.insertRevised(",
            "self.mediaStore.archive(",
        ):
            self.assertIn(anchor, section)
        self.assertLess(section.index("grvmContentFingerprint("), section.index("self.store.saveRevision("))
        self.assertNotIn("saveForBots", section)


if __name__ == "__main__":
    unittest.main()
