import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ACCOUNT_AWARE_HOOKS = (
    "shouldSuppressReadReceipts",
    "shouldSuppressPresence",
    "shouldSuppressTyping",
    "shouldSuppressStoryRead",
    "shouldSuppressContentRead",
    "shouldSuppressUploadProgress",
    "shouldForceOfflineAfterOnline",
    "shouldSuggestGhostForStories",
    "shouldMarkReadAfterAction",
    "shouldUseScheduledMessages",
    "sendWithoutSoundMode",
    "isMessageHiddenByFilter",
    "isShadowBanned",
    "matchingMessageFilterIds",
    "isShowingFilteredMessages",
    "setShowingFilteredMessages",
    "shouldDisableExternalLinkWarning",
    "shouldImproveLinkPreviews",
    "translationProvider",
    "shouldDisableAds",
    "shouldHideStories",
    "shouldDisableSimilarChannels",
    "shouldDisableNotificationDelay",
    "shouldFilterZalgo",
    "shouldShowSeconds",
    "shouldShowDialogID",
    "peerIdDisplayMode",
    "shouldConfirmStickers",
    "shouldConfirmGIF",
    "shouldConfirmVoice",
    "shouldSpoofWebviewAsAndroid",
    "shouldIncreaseWebviewHeight",
    "shouldIncreaseWebviewWidth",
)


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


class GhostBoundaryFixContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hook_sources = {
            path: path.read_text(encoding="utf-8")
            for path in (ROOT / "submodules").rglob("*.swift")
            if "AyuGramHooks." in path.read_text(encoding="utf-8")
        }

    def test_every_changed_hook_has_no_zero_argument_provider_or_call(self) -> None:
        failures = []
        for path, text in self.hook_sources.items():
            relative = path.relative_to(ROOT)
            for hook in ACCOUNT_AWARE_HOOKS:
                if re.search(rf"AyuGramHooks\.{hook}\?\s*\(\s*\)", text):
                    failures.append(f"zero-argument call: {relative}: {hook}")
                if re.search(
                    rf"AyuGramHooks\.{hook}\s*=\s*\{{\s*(?:\[weak self\]\s*)?in\b",
                    text,
                ):
                    failures.append(f"zero-argument provider: {relative}: {hook}")
        self.assertEqual([], failures)

    def test_existing_consumers_pass_the_authoritative_account(self) -> None:
        expected = {
            "submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift": (
                "shouldSuppressReadReceipts?(self.stateManager.accountPeerId)",
            ),
            "submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift": (
                "shouldSuppressPresence?(self.accountPeerId)",
                "accountPeerId: PeerId",
            ),
            "submodules/TelegramCore/Sources/State/ManagedLocalInputActivities.swift": (
                "shouldSuppressTyping?(accountPeerId)",
                "shouldSuppressUploadProgress?(accountPeerId)",
            ),
            "submodules/TelegramCore/Sources/State/ManagedSynchronizeViewStoriesOperations.swift": (
                "shouldSuppressStoryRead?(stateManager.accountPeerId)",
            ),
            "submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift": (
                "shouldSuppressContentRead?(stateManager.accountPeerId)",
            ),
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift": (
                "accountPeerId: PeerId",
                "shouldSuppressContentRead?(accountPeerId)",
            ),
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift": (
                "accountPeerId: self.account.peerId",
            ),
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/AdMessages.swift": (
                "shouldDisableAds?(self.account.peerId)",
            ),
            "submodules/TelegramUI/Sources/SharedNotificationManager.swift": (
                "shouldDisableNotificationDelay?(account.peerId)",
            ),
            "submodules/TelegramUI/Sources/ChatHistoryEntriesForView.swift": (
                "isMessageHiddenByFilter?(context.account.peerId, message)",
            ),
            "submodules/WebUI/Sources/WebAppWebView.swift": (
                "shouldSpoofWebviewAsAndroid?(account.peerId)",
                "shouldIncreaseWebviewHeight?(account.peerId)",
                "shouldIncreaseWebviewWidth?(account.peerId)",
            ),
            "submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/StringForMessageTimestampStatus.swift": (
                "shouldShowSeconds?(accountPeerId)",
            ),
            "submodules/TelegramUI/Components/Chat/ChatMessageTextBubbleContentNode/Sources/ChatMessageTextBubbleContentNode.swift": (
                "shouldFilterZalgo?(item.context.account.peerId)",
            ),
            "submodules/TelegramUI/Components/Chat/ChatMessageWebpageBubbleContentNode/Sources/ChatMessageWebpageBubbleContentNode.swift": (
                "shouldImproveLinkPreviews?(item.context.account.peerId)",
            ),
            "submodules/TelegramUI/Components/ChatListHeaderComponent/Sources/ChatListHeaderComponent.swift": (
                "shouldHideStories?(component.context.account.peerId)",
            ),
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift": (
                "shouldShowDialogID?(context.account.peerId)",
                "peerIdDisplayMode?(context.account.peerId)",
            ),
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoData.swift": (
                "shouldDisableSimilarChannels?(context.account.peerId)",
            ),
            "submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/StoryContainerScreen.swift": (
                "shouldSuggestGhostForStories?(component.context.account.peerId)",
                "shouldSuppressStoryRead?(component.context.account.peerId)",
            ),
        }
        for path, tokens in expected.items():
            text = source(path)
            for token in tokens:
                self.assertIn(token, text, f"{path}: {token}")

    def test_read_state_suppression_consumes_the_operation(self) -> None:
        text = source(
            "submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift"
        )
        suppression = swift_block(
            text,
            "if AyuGramHooks.shouldSuppressReadReceipts?",
        )
        self.assertIn("confirmSynchronizedIncomingReadState(peerId)", suppression)
        self.assertIn("self.postbox.transaction", suppression)
        self.assertNotIn("signal = .complete()", suppression)

    def test_runtime_uses_canonical_silent_webview_and_combined_typing(self) -> None:
        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        self.assertIn(
            "registry.service(accountPeerId: accountPeerId)?.settingsSnapshot()",
            manager,
        )
        self.assertIn(
            "settings.ghostModeEnabled\n                && (settings.suppressTypingStatus || settings.suppressUploadProgress)",
            manager,
        )
        self.assertIn(
            "AyuGramHooks.shouldSuppressTyping = shouldSuppressTypingAndUploads",
            manager,
        )
        self.assertIn(
            "AyuGramHooks.shouldSuppressUploadProgress = shouldSuppressTypingAndUploads",
            manager,
        )
        send_mode = swift_block(manager, "AyuGramHooks.sendWithoutSoundMode =")
        self.assertIn("settings.sendWithoutSoundOption", send_mode)
        self.assertNotRegex(send_mode, r"\.sendWithoutSound\b")

        runtime_paths = (
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift",
            "submodules/WebUI/Sources/WebAppWebView.swift",
            "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift",
            "submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift",
            "submodules/TelegramUI/Sources/ChatController.swift",
        )
        runtime = "\n".join(source(path) for path in runtime_paths)
        self.assertNotRegex(
            runtime,
            r"\b(?:s|settings|currentSettings)\.sendWithoutSound\b",
        )
        self.assertNotRegex(
            runtime,
            r"\b(?:s|settings|currentSettings)\.increaseWebviewSize\b",
        )
        self.assertNotIn("shouldIncreaseWebviewSize", runtime)
        self.assertNotIn("shouldSendWithoutSound?()", runtime)

        core = source("submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift")
        self.assertIn("settings.sendWithoutSoundOption != 0", core)
        self.assertIn("settings.sendWithoutSoundOption = value ? 2 : 0", core)
        general = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift"
        )
        self.assertIn(
            "settings.increaseWebviewHeight || settings.increaseWebviewWidth",
            general,
        )
        self.assertIn("settings.increaseWebviewHeight = value", general)
        self.assertIn("settings.increaseWebviewWidth = value", general)
        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        self.assertIn(
            "sendWithoutSoundMode?(self.context.account.peerId)",
            chat,
        )
        webview = source("submodules/WebUI/Sources/WebAppWebView.swift")
        self.assertIn(
            "shouldIncreaseWebviewHeight || shouldIncreaseWebviewWidth",
            webview,
        )

    def test_chat_send_gate_preserves_in_ghost_and_always_silent_modes(self) -> None:
        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        send_mode = swift_block(manager, "AyuGramHooks.sendWithoutSoundMode =")
        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        send_gate = swift_block(
            chat,
            "func transformEnqueueMessages(_ messages:",
        )
        comparison = re.search(
            r"silentPosting = .* \|\| sendWithoutSoundMode\s*([!=]=)\s*(-?\d+)",
            send_gate,
        )
        self.assertIsNotNone(comparison)
        operator, raw_value = comparison.groups()
        compared_value = int(raw_value)

        switch_body = re.search(
            r"switch\s+settings\.sendWithoutSoundOption\s*\{\s*"
            r"case\s+2:\s*return\s+(-?\d+)\s*"
            r"case\s+1:\s*return\s+settings\.ghostModeEnabled\s*\?\s*"
            r"(-?\d+)\s*:\s*(-?\d+)\s*"
            r"default:\s*return\s+(-?\d+)\s*\}",
            send_mode,
            re.S,
        )
        self.assertIsNotNone(switch_body)
        always_mode, ghost_on_mode, ghost_off_mode, default_mode = map(
            int,
            switch_body.groups(),
        )
        settings_lookup = swift_block(
            manager,
            "private func settings(accountPeerId:",
        )
        self.assertIn("registry.service(accountPeerId: accountPeerId)", settings_lookup)
        self.assertIn("settings(accountPeerId: accountPeerId)", send_mode)

        def effective_mode(mode: int, ghost_mode_enabled: bool) -> int:
            if mode == 2:
                return always_mode
            if mode == 1:
                return ghost_on_mode if ghost_mode_enabled else ghost_off_mode
            return default_mode

        def gate_is_silent(mode: int) -> bool:
            if operator == "!=":
                return mode != compared_value
            return mode == compared_value

        cases = (
            (0, False, False),
            (0, True, False),
            (1, False, False),
            (1, True, True),
            (2, False, True),
            (2, True, True),
        )
        for mode, ghost_mode_enabled, expected in cases:
            with self.subTest(mode=mode, ghost_mode_enabled=ghost_mode_enabled):
                self.assertEqual(
                    expected,
                    gate_is_silent(effective_mode(mode, ghost_mode_enabled)),
                )

    def test_translation_provider_normalizes_init_decode_and_direct_mutation(self) -> None:
        settings = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        self.assertIn("private static func normalizedTranslationProvider", settings)
        self.assertIn("didSet", swift_block(settings, "public var translationProvider"))
        self.assertGreaterEqual(
            settings.count("Self.normalizedTranslationProvider("),
            3,
        )
        self.assertNotIn(
            "self.translationProvider = translationProvider\n",
            settings,
        )


if __name__ == "__main__":
    unittest.main()
