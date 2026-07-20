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
        self.assertIn("strings[.ghostLockedComponents]", ui)
        self.assertIn("strings.format(.ghostLockedCount", ui)
        self.assertIn(".ghostComponentReadReceipts", ui)
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

    def test_read_after_action_uses_one_helper_after_success(self) -> None:
        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        helper = swift_block(
            chat, "private func grvmMarkCurrentChatReadAfterAction()"
        )
        self.assertIn(
            "AyuGramHooks.shouldMarkReadAfterAction?(self.context.account.peerId)",
            helper,
        )
        self.assertIn("guard self.chatLocation.peerId != nil", helper)
        self.assertIn("latestMessageInCurrentHistoryView()", helper)
        self.assertIn("self.context.applyMaxReadIndex(", helper)
        self.assertEqual(
            1, chat.count("AyuGramHooks.shouldMarkReadAfterAction?(")
        )
        self.assertEqual(6, chat.count("grvmMarkCurrentChatReadAfterAction()"))

        send = swift_block(chat, "func sendMessages(_ messages:")
        self.assertLess(
            send.index("enqueueMessages(account:"),
            send.index("grvmMarkCurrentChatReadAfterAction()"),
        )

        reaction = swift_block(chat, "updateMessageReaction: {")
        reaction_update = reaction[reaction.rindex("updateMessageReactionsInteractively(") :]
        self.assertIn(".startStandalone(completed:", reaction_update)
        self.assertIn("grvmMarkCurrentChatReadAfterAction()", reaction_update)
        stars_success = swift_block(
            reaction, "strongSelf.context.engine.messages.sendStarsReaction("
        )
        self.assertIn("grvmMarkCurrentChatReadAfterAction()", stars_success)

        poll = swift_block(chat, "requestSelectMessagePollOptions: {")
        self.assertIn("guard let strongSelf = self, let resultPoll = resultPoll", poll)
        poll_success = poll[
            poll.index("guard let strongSelf = self, let resultPoll = resultPoll") :
        ]
        self.assertIn("strongSelf.grvmMarkCurrentChatReadAfterAction()", poll_success)
        self.assertLess(
            poll_success.index("strongSelf.grvmMarkCurrentChatReadAfterAction()"),
            poll_success.index(
                "strongSelf.chatDisplayNode.historyNode.messageInCurrentHistoryView(id)"
            ),
        )

    def test_context_menu_reaction_uses_shared_read_helper_after_success(self) -> None:
        interaction = source(
            "submodules/TelegramUI/Components/ChatControllerInteraction/"
            "Sources/ChatControllerInteraction.swift"
        )
        self.assertIn(
            "public var grvmMarkCurrentChatReadAfterAction: (() -> Void)?",
            interaction,
        )

        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        wiring = swift_block(
            chat, "controllerInteraction.grvmMarkCurrentChatReadAfterAction ="
        )
        self.assertIn("self?.grvmMarkCurrentChatReadAfterAction()", wiring)

        context_menu = source(
            "submodules/TelegramUI/Sources/Chat/ChatControllerOpenMessageContextMenu.swift"
        )
        update = context_menu[
            context_menu.rindex("updateMessageReactionsInteractively(") :
        ]
        self.assertIn("|> deliverOnMainQueue", update)
        self.assertIn(".startStandalone(completed:", update)
        self.assertIn(
            "controllerInteraction?.grvmMarkCurrentChatReadAfterAction?()", update
        )

    def test_read_and_schedule_predicates_remain_mutually_exclusive(self) -> None:
        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        schedule = swift_block(
            manager, "AyuGramHooks.shouldUseScheduledMessages ="
        )
        self.assertIn("settings.ghostModeEnabled", schedule)
        self.assertIn("settings.useScheduledMessages", schedule)
        self.assertIn("!settings.readOnAction", schedule)
        read = swift_block(manager, "AyuGramHooks.shouldMarkReadAfterAction =")
        self.assertIn("settings.ghostModeEnabled", read)
        self.assertIn("settings.readOnAction", read)
        self.assertIn("!settings.useScheduledMessages", read)

        ui = swift_block(
            source("submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"),
            "public func ayuGramCoreController(",
        )
        self.assertIn("settings.setReadOnAction(value)", ui)
        self.assertIn("settings.setScheduledMessages(value)", ui)
        settings = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        read_setter = swift_block(settings, "public var readOnAction: Bool")
        schedule_setter = swift_block(settings, "public var useScheduledMessages: Bool")
        self.assertIn("useScheduledMessages = false", read_setter)
        self.assertIn("readOnAction = false", schedule_setter)

    def test_silent_send_uses_the_canonical_three_mode_selector(self) -> None:
        manager = swift_block(
            source("submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"),
            "AyuGramHooks.sendWithoutSoundMode =",
        )
        self.assertIn("settings.sendWithoutSoundOption", manager)
        self.assertNotIn("settings.sendWithoutSound ", manager)
        self.assertIn("case 1:", manager)
        self.assertIn("settings.ghostModeEnabled ? 1 : 0", manager)
        self.assertIn("case 2:", manager)

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

        ui_source = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        )
        entries = swift_block(ui_source, "private func ayuGramCoreEntries(")
        for key in ("commonNever", "commonInGhost", "commonAlways"):
            self.assertIn(f"strings[.{key}]", entries)
        self.assertIn("settings.sendWithoutSoundOption", entries)
        self.assertIn(".sendWithoutSoundMode(", entries)
        self.assertNotIn(".sendWithoutSound(", entries)

        selector = swift_block(ui_source, "case let .sendWithoutSoundMode(")
        self.assertIn("ItemListDisclosureItem", selector)
        self.assertIn("arguments.setSendWithoutSoundMode((value + 1) % 3)", selector)
        controller = swift_block(ui_source, "public func ayuGramCoreController(")
        self.assertIn("settings.sendWithoutSoundOption = value", controller)
        self.assertNotIn("settings.sendWithoutSound =", controller)

    def test_story_gate_precedes_mark_and_waits_for_coordinator_snapshot(self) -> None:
        story_path = (
            "submodules/TelegramUI/Components/Stories/StoryContainerScreen/"
            "Sources/StoryContainerScreen.swift"
        )
        story = source(story_path)
        build = source(
            "submodules/TelegramUI/Components/Stories/StoryContainerScreen/BUILD"
        )
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
        self.assertIn("settings.ghostModeEnabled = true", enable)
        self.assertIn("settings.suppressStoryReads = true", enable)
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
