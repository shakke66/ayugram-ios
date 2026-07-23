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

    def test_feature_manager_uses_component_values_without_a_master_runtime_gate(self) -> None:
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
        self.assertNotIn("settings.ghostModeEnabled", ghost)
        self.assertNotIn("settings.goOfflineAfterOnline", ghost)
        for token in (
            "return settings.suppressReadReceipts",
            "return settings.suppressStoryReads",
            "return settings.suppressOnlineStatus",
            "return settings.suppressTypingAndUploads",
        ):
            self.assertIn(token, ghost)
        self.assertEqual(2, ghost.count("return settings.suppressReadReceipts"))
        self.assertEqual(1, ghost.count("return settings.suppressOnlineStatus"))
        self.assertIn(
            "AyuGramHooks.shouldSuppressTyping = shouldSuppressTypingAndUploads", ghost
        )
        self.assertIn(
            "AyuGramHooks.shouldSuppressUploadProgress = shouldSuppressTypingAndUploads",
            ghost,
        )
        self.assertNotIn("AyuGramHooks.shouldForceOfflineAfterOnline", ghost)

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

    def test_presence_suppression_flip_forces_offline_once_after_current_request_succeeds(self) -> None:
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
            "|> ignoreValues\n"
            "        |> map { _ -> Bool in\n"
            "        }\n"
            "        |> then(Signal<Bool, MTRpcError>.single(true))",
            presence,
        )
        self.assertIn("requestSucceeded", presence)
        suppression_hook = "AyuGramHooks.shouldSuppressPresence?(self.accountPeerId)"
        self.assertEqual(2, presence.count(suppression_hook))
        self.assertNotIn("shouldForceOfflineAfterOnline", presence)
        self.assertIn("self.onlineTimer?.invalidate()", presence)
        self.assertIn("self.onlineTimer = nil", presence)
        self.assertEqual(1, presence.count("self.updatePresence(false)"))
        self.assertLess(
            presence.index("shouldSuppressPresence?"),
            presence.index("self.presenceUpdateId &+= 1"),
        )
        self.assertLess(
            presence.index("requestSucceeded"),
            presence.rindex(suppression_hook),
        )
        self.assertLess(
            presence.rindex(suppression_hook),
            presence.index("self.updatePresence(false)"),
        )

    def test_reply_threads_keep_local_updates_but_gate_direct_reads(self) -> None:
        reply = swift_block(
            source(
                "submodules/TelegramCore/Sources/TelegramEngine/Messages/ReplyThreadHistory.swift"
            ),
            "func applyMaxReadIndex(messageIndex: MessageIndex, mode: GRVMReadMode = .automatic)",
        )
        self.assertIn("setMessageHistoryThreadInfo", reply)
        self.assertIn("_internal_applyMaxReadIndexInteractively", reply)
        self.assertIn("strongSelf.unreadCountValue = unreadCountValue", reply)
        self.assertIn(
            "shouldSuppressReadReceipts?(self.account.peerId)", reply
        )
        gate = re.search(
            r"guard shouldSendReadReceipt\s+else\s*\{\s*return\s*\}", reply
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

    def test_ghost_ui_has_exactly_four_component_rows(self) -> None:
        ui = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        )
        entries = swift_block(ui, "private func ayuGramCoreEntries(")
        for token in (
            ".ghostComponentReadReceipts(",
            ".ghostComponentStoryReads(",
            ".ghostComponentOnlineStatus(",
            ".ghostComponentTypingAndUploads(",
        ):
            self.assertIn(token, entries)
        self.assertEqual(4, entries.count("entries.append(.ghostComponent"))
        self.assertNotIn(".ghostComponentGoOfflineAfterOnline(", entries)
        self.assertNotIn(".ghostComponentTypingStatus(", entries)
        self.assertNotIn(".ghostComponentUploadProgress(", entries)

        controller = swift_block(ui, "public func ayuGramCoreController(")
        self.assertIn("settings.setGhostModeEnabled(value)", controller)
        self.assertIn("settings.suppressTypingAndUploads = value", controller)
        self.assertNotIn("settings.suppressTypingStatus = value", controller)
        self.assertNotIn("settings.suppressUploadProgress = value", controller)
        self.assertNotIn("settings.goOfflineAfterOnline = value", controller)

    def test_removed_locked_components_have_no_screen_counter_or_model(self) -> None:
        ui = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        )
        for token in (
            "strings[.ghostLockedComponents]",
            "strings.format(.ghostLockedCount",
            "ayuGramGhostLockedComponentsController",
            "ghostLockedComponents",
            "GRVMGhostComponent",
        ):
            self.assertNotIn(token, ui)
        self.assertFalse(
            (ROOT / "submodules/AyuGramLib/Sources/GRVMGhostModels.swift").exists()
        )

    def test_schedule_policy_distinguishes_uploads_and_clamps_overflow(self) -> None:
        schedule_path = (
            ROOT / "submodules/AyuGramLib/Sources/GRVMGhostSchedule.swift"
        )
        self.assertTrue(schedule_path.exists(), "Ghost schedule helper is missing")
        schedule = swift_block(
            schedule_path.read_text(encoding="utf-8"),
            "public func grvmGhostScheduleDelay(",
        )
        for token in (
            "messages: [EnqueueMessage]",
            "proxyEnabled: Bool",
            "var baseDelay = 12.0",
            "file.isVoice || file.isInstantVideo",
            "baseDelay = max(baseDelay, 17.0)",
            "case .standalone",
            "as? LocalFileMediaResource",
            "localResource.size",
            "Double(resourceSize)",
            "1_048_576.0",
            "ceil(sizeMiB * 0.7)",
            "13.0 + max(6.0, sizeDelay)",
            "max(19.0, uploadDelay)",
            "proxyEnabled ? ceil(baseDelay * 1.2) : baseDelay",
            "Double(Int32.max)",
            "Int32(min(",
        ):
            self.assertIn(token, schedule)
        self.assertRegex(
            schedule,
            r"guard let resourceSize = localResource\.size, resourceSize >= 0 else \{\s*continue\s*\}",
        )
        self.assertNotIn("4.5", schedule)

    def test_ghost_schedule_reads_one_proxy_snapshot_inside_the_ghost_gate(self) -> None:
        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        send = swift_block(chat, "func sendMessages(_ messages:")
        gate_signature = (
            "if !commit && !isScheduledMessages "
            "&& AyuGramHooks.shouldUseScheduledMessages?(self.context.account.peerId) == true"
        )
        gate = swift_block(send, gate_signature)
        for token in (
            "accountManager.sharedData(keys: [SharedDataKeys.proxySettings])",
            "|> take(1)",
            "SharedDataKeys.proxySettings]?.get(ProxySettings.self)",
            "effectiveActiveServer != nil",
            "grvmGhostScheduleDelay(messages: messages, proxyEnabled: proxyEnabled)",
            "Int32(clamping:",
            "commit: true",
            "return",
        ):
            self.assertIn(token, gate)
        self.assertEqual(1, send.count("grvmGhostScheduleDelay("))
        self.assertNotIn("fileSizeMB * 4.5", send)
        self.assertLess(send.index(gate_signature), send.index("accountManager.sharedData"))
        self.assertLess(send.index(gate_signature), send.index("grvmGhostScheduleDelay("))
        self.assertGreater(
            send.rindex("enqueueMessages(account:"),
            send.index("grvmGhostScheduleDelay("),
        )

    def test_ghost_schedule_retains_send_until_proxy_snapshot_commit(self) -> None:
        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        send = swift_block(chat, "func sendMessages(_ messages:")
        gate = swift_block(
            send,
            "if !commit && !isScheduledMessages "
            "&& AyuGramHooks.shouldUseScheduledMessages?(self.context.account.peerId) == true",
        )
        callback = swift_block(gate, ".startStandalone(next:")

        self.assertNotIn("[weak self]", callback)
        self.assertNotIn("guard let self else", callback)
        self.assertIn("self.sendMessages(", callback)
        self.assertIn("commit: true", callback)

    def test_removed_read_after_action_has_no_runtime_wiring(self) -> None:
        paths = (
            "submodules/TelegramCore/Sources/AyuGramHooks.swift",
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift",
            "submodules/TelegramUI/Sources/ChatController.swift",
            "submodules/TelegramUI/Sources/Chat/ChatControllerOpenMessageContextMenu.swift",
            "submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift",
        )
        runtime = "\n".join(source(path) for path in paths)
        self.assertNotIn("shouldMarkReadAfterAction", runtime)
        self.assertNotIn("grvmMarkCurrentChatReadAfterAction", runtime)
        self.assertNotIn("readOnAction", runtime)

    def test_schedule_is_independent_of_master_and_removed_read_on_action(self) -> None:
        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        schedule = swift_block(
            manager, "AyuGramHooks.shouldUseScheduledMessages ="
        )
        self.assertIn("settings.useScheduledMessages", schedule)
        self.assertNotIn("settings.ghostModeEnabled", schedule)
        self.assertNotIn("readOnAction", schedule)

    def test_silent_send_uses_the_canonical_three_mode_selector(self) -> None:
        manager = swift_block(
            source("submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"),
            "AyuGramHooks.sendWithoutSoundMode =",
        )
        self.assertIn("settings.sendWithoutSoundMode", manager)
        self.assertNotIn("settings.sendWithoutSoundOption", manager)
        self.assertNotIn("settings.sendWithoutSound ", manager)
        self.assertIn("case 1:", manager)
        self.assertIn("self.isGhostActive(settings) ? 1 : 0", manager)
        self.assertNotIn("settings.ghostModeEnabled", manager)
        self.assertIn("case 2:", manager)

        active = swift_block(
            source("submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"),
            "private func isGhostActive(_ settings:",
        )
        for token in (
            "settings.suppressReadReceipts",
            "settings.suppressStoryReads",
            "settings.suppressOnlineStatus",
            "settings.suppressTypingAndUploads",
        ):
            self.assertIn(token, active)
        self.assertNotIn("settings.ghostModeEnabled", active)
        self.assertNotIn("settings.useScheduledMessages", active)

        chat = swift_block(
            source("submodules/TelegramUI/Sources/ChatController.swift"),
            "func transformEnqueueMessages(_ messages: [EnqueueMessage], postpone:",
        )
        self.assertIn(
            "AyuGramHooks.sendWithoutSoundMode?(self.context.account.peerId)", chat
        )
        self.assertIn(
            "sendWithoutSoundMode == 1 || sendWithoutSoundMode == 2", chat
        )

    def test_composer_send_reaches_the_shared_silent_policy_boundary(self) -> None:
        controller_node = source(
            "submodules/TelegramUI/Sources/ChatControllerNode.swift"
        )
        composer_start = controller_node.index("func sendCurrentMessage(")
        composer_call = controller_node.index(
            "self.sendMessages(messages, silentPosting, scheduleTime, repeatPeriod",
            composer_start,
        )
        self.assertGreater(composer_call, composer_start)

        load_display_node = source(
            "submodules/TelegramUI/Sources/Chat/ChatControllerLoadDisplayNode.swift"
        )
        send_boundary = swift_block(
            load_display_node, "self.chatDisplayNode.sendMessages ="
        )
        self.assertIn(
            "strongSelf.transformEnqueueMessages(messages, silentPosting: silentPosting ?? false",
            send_boundary,
        )

        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        deepest_transform = swift_block(
            chat,
            "func transformEnqueueMessages(_ messages: [EnqueueMessage], silentPosting: Bool",
        )
        self.assertIn(
            "let sendWithoutSoundMode = AyuGramHooks.sendWithoutSoundMode?(self.context.account.peerId) ?? 0",
            deepest_transform,
        )
        self.assertIn(
            "let effectiveSilentPosting = silentPosting || (sendWithoutSoundMode == 1 || sendWithoutSoundMode == 2)",
            deepest_transform,
        )
        self.assertIn(
            "if effectiveSilentPosting || scheduleTime != nil", deepest_transform
        )
        self.assertIn("if effectiveSilentPosting {", deepest_transform)


    def test_story_gate_precedes_mark_and_waits_for_coordinator_snapshot(self) -> None:
        story_path = (
            "submodules/TelegramUI/Components/Stories/StoryContainerScreen/"
            "Sources/StoryContainerScreen.swift"
        )
        story = source(story_path)
        build = source(
            "submodules/TelegramUI/Components/Stories/StoryContainerScreen/BUILD"
        )
        self.assertIn("import TelegramPresentationData", story)
        self.assertIn('"//submodules/TelegramPresentationData"', build)
        self.assertIn("import AyuGramLib", story)
        self.assertIn('"//submodules/AyuGramLib:AyuGramLib"', build)
        self.assertIn("private var didHandleGhostStorySuggestion", story)
        self.assertIn("private var isAwaitingGhostStoryChoice", story)
        self.assertIn("private let ghostStorySettingsDisposable = MetaDisposable()", story)
        self.assertIn("private var ghostStoryAcknowledgementTimer", story)

        mark_callback = swift_block(story, "markAsSeen: {")
        self.assertIn("self.grvmMarkStoryAsSeen(id: id)", mark_callback)
        self.assertNotIn("component.content.markAsSeen(id: id)", mark_callback)

        gate = swift_block(story, "private func grvmMarkStoryAsSeen(id:")
        self.assertIn("self.didHandleGhostStorySuggestion = true", gate)
        self.assertIn("AyuGramHooks.shouldSuggestGhostForStories?(accountPeerId)", gate)
        self.assertIn("AyuGramHooks.shouldSuppressStoryRead?(accountPeerId)", gate)
        self.assertIn("let grvmStrings = GRVMgramStrings(presentationData.strings)", gate)
        self.assertIn("title: grvmStrings[.storyGhostTitle]", gate)
        self.assertIn("text: grvmStrings[.storyGhostText]", gate)
        self.assertIn("title: grvmStrings[.storyGhostEnable]", gate)
        self.assertIn("title: grvmStrings[.storyGhostOpen]", gate)
        self.assertIn("dismissOnOutsideTap: false", gate)
        missing_controller = swift_block(
            gate, "guard let controller = self.environment?.controller()"
        )
        self.assertIn("self.didHandleGhostStorySuggestion = false", missing_controller)
        self.assertNotIn("component.content.markAsSeen(id: id)", missing_controller)

        enable = swift_block(story, "private func grvmEnableGhostForStory(id:")
        self.assertIn("updateGRVMSettings(", enable)
        self.assertIn("accountId: component.context.account.peerId", enable)
        self.assertIn("settings.suppressStoryReads = true", enable)
        self.assertNotIn("settings.ghostModeEnabled", enable)
        self.assertIn("|> deliverOnMainQueue", enable)
        self.assertIn("grvmWaitForStoryGhostSnapshot(id: id)", enable)
        self.assertNotIn("component.content.markAsSeen(id: id)", enable)

        acknowledgement = swift_block(
            story, "private func grvmWaitForStoryGhostSnapshot(id:"
        )
        self.assertIn(
            "AyuGramHooks.shouldSuppressStoryRead?(accountPeerId) == true",
            acknowledgement,
        )
        self.assertIn("SwiftSignalKit.Timer", acknowledgement)
        self.assertIn("queue: .mainQueue()", acknowledgement)
        self.assertLess(
            acknowledgement.index("shouldSuppressStoryRead?"),
            acknowledgement.index("grvmFinishStoryGhostChoice(id: id)"),
        )

        finish = swift_block(story, "private func grvmFinishStoryGhostChoice(id:")
        self.assertIn("self.isAwaitingGhostStoryChoice = false", finish)
        self.assertEqual(1, finish.count("component.content.markAsSeen(id: id)"))
        story_view = swift_block(story, "final class View: UIView")
        deinit = swift_block(story_view, "deinit {")
        self.assertIn("self.ghostStorySettingsDisposable.dispose()", deinit)
        self.assertIn("self.ghostStoryAcknowledgementTimer?.invalidate()", deinit)
        self.assertNotIn("Enable Ghost Mode to view stories privately", story)


if __name__ == "__main__":
    unittest.main()
