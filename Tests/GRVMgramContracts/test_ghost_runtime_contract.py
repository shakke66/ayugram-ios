import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start == -1:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening_brace = text.index("{", start)
    depth = 0
    for index in range(opening_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


class GhostRuntimeContractTests(unittest.TestCase):
    def test_authoritative_consumers_keep_account_identity_and_remove_operations(self) -> None:
        read_states = source(
            "submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift"
        )
        self.assertIn(
            "shouldSuppressReadReceipts?(self.stateManager.accountPeerId)",
            read_states,
        )
        self.assertIn("confirmSynchronizedIncomingReadState(peerId)", read_states)

        for path, hook in (
            (
                "submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift",
                "shouldSuppressContentRead?(stateManager.accountPeerId)",
            ),
            (
                "submodules/TelegramCore/Sources/State/ManagedSynchronizeViewStoriesOperations.swift",
                "shouldSuppressStoryRead?(stateManager.accountPeerId)",
            ),
        ):
            text = source(path)
            self.assertIn("withTakenOperation", text)
            self.assertIn(hook, text)
            self.assertIn("operationLogRemoveEntry", text)

    def test_feature_manager_wires_all_five_effective_predicates(self) -> None:
        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        lookup = swift_block(manager, "private func settings(accountPeerId:")
        self.assertIn("registry.service(accountPeerId: accountPeerId)", lookup)
        self.assertIn("settingsSnapshot()", lookup)

        ghost = manager[
            manager.index("// MARK: - Ghost Mode") : manager.index(
                "// MARK: - Premium & Ads"
            )
        ]
        self.assertNotIn("primaryService()", ghost)
        for token in (
            "settings.ghostModeEnabled && settings.suppressReadReceipts",
            "settings.ghostModeEnabled && settings.suppressStoryReads",
            "settings.ghostModeEnabled && settings.suppressOnlineStatus",
            "settings.suppressTypingStatus || settings.suppressUploadProgress",
            "settings.ghostModeEnabled && settings.goOfflineAfterOnline",
        ):
            self.assertIn(token, ghost)
        self.assertIn(
            "AyuGramHooks.shouldSuppressTyping = shouldSuppressTypingAndUploads", ghost
        )
        self.assertIn(
            "AyuGramHooks.shouldSuppressUploadProgress = shouldSuppressTypingAndUploads",
            ghost,
        )
        self.assertIn("AyuGramHooks.shouldForceOfflineAfterOnline", ghost)

    def test_background_offline_is_never_suppressed(self) -> None:
        presence = swift_block(
            source(
                "submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift"
            ),
            "private func updatePresence(_ isOnline: Bool)",
        )
        suppression = swift_block(
            presence,
            "if isOnline && AyuGramHooks.shouldSuppressPresence?",
        )
        self.assertIn("return", suppression)
        self.assertIn("account.updateStatus(offline: .boolTrue)", presence)
        self.assertGreater(
            presence.index("account.updateStatus(offline: .boolTrue)"),
            presence.index(suppression),
        )

    def test_force_offline_runs_once_after_success_for_current_request(self) -> None:
        presence_source = source(
            "submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift"
        )
        presence = swift_block(
            presence_source, "private func updatePresence(_ isOnline: Bool)"
        )
        self.assertIn("private var presenceUpdateId: Int = 0", presence_source)
        self.assertIn("let requestId = self.presenceUpdateId", presence)
        self.assertIn("guard requestId == self.presenceUpdateId else", presence)
        self.assertIn(
            "|> ignoreValues\n        |> then(Signal<Bool, MTRpcError>.single(true))",
            presence,
        )
        self.assertIn("requestSucceeded", presence)
        self.assertIn(
            "AyuGramHooks.shouldForceOfflineAfterOnline?(self.accountPeerId)", presence
        )
        self.assertIn("self.onlineTimer?.invalidate()", presence)
        self.assertIn("self.onlineTimer = nil", presence)
        self.assertEqual(1, presence.count("self.updatePresence(false)"))
        self.assertLess(
            presence.index("shouldSuppressPresence?"),
            presence.index("self.presenceUpdateId &+= 1"),
        )
        self.assertLess(
            presence.index("requestSucceeded"),
            presence.index("AyuGramHooks.shouldForceOfflineAfterOnline?"),
        )
        self.assertLess(
            presence.index("AyuGramHooks.shouldForceOfflineAfterOnline?"),
            presence.index("self.updatePresence(false)"),
        )

    def test_reply_threads_keep_local_updates_but_gate_direct_reads(self) -> None:
        reply = swift_block(
            source(
                "submodules/TelegramCore/Sources/TelegramEngine/Messages/ReplyThreadHistory.swift"
            ),
            "func applyMaxReadIndex(messageIndex: MessageIndex)",
        )
        self.assertIn("setMessageHistoryThreadInfo", reply)
        self.assertIn("_internal_applyMaxReadIndexInteractively", reply)
        self.assertIn("strongSelf.unreadCountValue = unreadCountValue", reply)
        self.assertIn(
            "shouldSuppressReadReceipts?(self.account.peerId)", reply
        )
        gate = re.search(
            r"if shouldSuppressReadReceipts\s*\{\s*return\s*\}", reply
        )
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertLess(reply.index("strongSelf.unreadCountValue = unreadCountValue"), gate.start())
        self.assertLess(gate.end(), reply.index("readSavedHistory"))
        self.assertLess(gate.end(), reply.index("readDiscussion"))

    def test_interactive_content_read_uses_the_exact_account(self) -> None:
        producer = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift"
        )
        engine = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift"
        )
        self.assertIn("accountPeerId: PeerId", producer)
        self.assertIn("shouldSuppressContentRead?(accountPeerId)", producer)
        self.assertNotIn("shouldSuppressContentRead?()", producer)
        self.assertIn(
            "_internal_markMessageContentAsConsumedInteractively(accountPeerId: self.account.peerId",
            engine,
        )

    def test_ghost_ui_has_exactly_five_component_rows(self) -> None:
        ui = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        )
        entries = swift_block(ui, "private func ayuGramCoreEntries(")
        for token in (
            ".ghostComponentReadReceipts(",
            ".ghostComponentStoryReads(",
            ".ghostComponentOnlineStatus(",
            ".ghostComponentTypingAndUploads(",
            ".ghostComponentGoOfflineAfterOnline(",
        ):
            self.assertIn(token, entries)
        self.assertNotIn(".ghostComponentTypingStatus(", entries)
        self.assertNotIn(".ghostComponentUploadProgress(", entries)

        controller = swift_block(ui, "public func ayuGramCoreController(")
        self.assertIn("settings.setGhostModeEnabled(value)", controller)
        self.assertRegex(
            controller,
            r"settings\.suppressTypingStatus = value\s+settings\.suppressUploadProgress = value",
        )
        self.assertIn("settings.goOfflineAfterOnline = value", controller)

    def test_locked_components_use_a_native_disclosure_screen(self) -> None:
        ui = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        )
        self.assertIn("ItemListDisclosureItem", ui)
        self.assertIn('"GRVMgram.Ghost.LockedComponents"', ui)
        self.assertIn('fallback: "Locked Components"', ui)
        self.assertIn(r'"\(settings.ghostLockedComponents.count)/5"', ui)
        self.assertIn("ayuGramGhostLockedComponentsController", ui)

        locks = swift_block(
            ui, "private func ayuGramGhostLockedComponentsController("
        )
        for component in (
            "readReceipts",
            "storyReads",
            "onlineStatus",
            "typingAndUploads",
            "goOfflineAfterOnline",
        ):
            self.assertIn(f".{component}", locks)
        self.assertIn("settings.ghostLockedComponents.insert(component)", locks)
        self.assertIn("settings.ghostLockedComponents.remove(component)", locks)
        self.assertNotIn("shift", ui.lower())


if __name__ == "__main__":
    unittest.main()
