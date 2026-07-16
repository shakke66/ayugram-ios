import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "submodules/AyuGramLib/Sources/AyuGramSettings.swift"
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMGhostModels.swift"
FILTER = ROOT / "submodules/AyuGramLib/Sources/AyuMessageFilter.swift"
HOOKS = ROOT / "submodules/TelegramCore/Sources/AyuGramHooks.swift"
PROVIDER = ROOT / "submodules/TelegramCore/Sources/GRVMTranslationProvider.swift"


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


class GhostSettingsContractTests(unittest.TestCase):
    def test_five_components_and_new_fields_exist(self) -> None:
        models = MODELS.read_text(encoding="utf-8")
        for case in ("readReceipts", "storyReads", "onlineStatus", "typingAndUploads", "goOfflineAfterOnline"):
            self.assertIn(f"case {case}", models)
        settings = SETTINGS.read_text(encoding="utf-8")
        for field in ("ghostLockedComponents", "goOfflineAfterOnline", "filters", "disableExternalLinkWarning", "increaseWebviewHeight", "increaseWebviewWidth"):
            self.assertIn(f"var {field}:", settings)

    def test_filter_shape_is_stable(self) -> None:
        source = FILTER.read_text(encoding="utf-8")
        for field in ("id", "expression", "isEnabled", "isReversed", "isCaseInsensitive", "peerId", "excludedPeerIds"):
            self.assertIn(f"var {field}:", source)
        self.assertIn("CryptoSHA1", source)
        self.assertIn("kind: String, index: Int, expression: String", source)
        self.assertIn("bytes[6] = (bytes[6] & 0x0f) | 0x50", source)
        self.assertIn("bytes[8] = (bytes[8] & 0x3f) | 0x80", source)

    def test_decoding_migrates_legacy_values_and_encoding_keeps_downgrade_keys(self) -> None:
        source = SETTINGS.read_text(encoding="utf-8")
        for key in (
            "ghostLockedComponents",
            "goOfflineAfterOnline",
            "filters",
            "disableExternalLinkWarning",
            "increaseWebviewHeight",
            "increaseWebviewWidth",
        ):
            self.assertGreaterEqual(source.count(f'forKey: "{key}"'), 2, key)
        self.assertIn("legacyMessageFilters.enumerated().map", source)
        self.assertIn("legacyReversedFilters.enumerated().map", source)
        self.assertIn("AyuMessageFilter.migratingLegacy", source)
        self.assertIn("self.sendWithoutSound ? 2 : 0", source)
        self.assertIn("?? self.increaseWebviewSize", source)
        self.assertIn("GRVMTranslationProvider(rawValue:", source)
        for legacy_key in (
            "sendWithoutSound",
            "increaseWebviewSize",
            "suppressTypingStatus",
            "suppressUploadProgress",
            "messageFilters",
            "reversedFilters",
        ):
            self.assertIn(f'container.encode(self.{legacy_key}, forKey: "{legacy_key}")', source)

    def test_ghost_count_and_bulk_mutation_use_five_lockable_components(self) -> None:
        source = SETTINGS.read_text(encoding="utf-8")
        count = swift_block(source, "public var ghostModeActiveCount")
        self.assertIn("suppressTypingStatus || suppressUploadProgress", count)
        self.assertIn("goOfflineAfterOnline", count)
        self.assertNotIn("if suppressTypingStatus {", count)
        self.assertNotIn("if suppressUploadProgress {", count)

        mutation = swift_block(source, "public mutating func setGhostModeEnabled")
        for component in (
            "readReceipts",
            "storyReads",
            "onlineStatus",
            "typingAndUploads",
            "goOfflineAfterOnline",
        ):
            self.assertIn(f".{component}", mutation)
        self.assertIn("self.suppressTypingStatus = enabled", mutation)
        self.assertIn("self.suppressUploadProgress = enabled", mutation)
        self.assertNotIn("ghostLockedComponents.removeAll", mutation)

    def test_mutually_exclusive_rows_normalize_every_mutation_path(self) -> None:
        source = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("if readOnAction && useScheduledMessages", source)
        self.assertIn("if useScheduledMessages && readOnAction", source)
        self.assertIn(
            "self.useScheduledMessages = useScheduledMessages && !readOnAction",
            source,
        )
        self.assertIn("&& !self.readOnAction", source)

    def test_identity_sensitive_hooks_are_account_aware(self) -> None:
        source = HOOKS.read_text(encoding="utf-8")
        self.assertNotIn("shouldSuppressReadReceipts: (() -> Bool)", source)
        for signature in (
            "shouldSuppressReadReceipts: ((PeerId) -> Bool)",
            "shouldSuppressPresence: ((PeerId) -> Bool)",
            "shouldSuppressTyping: ((PeerId) -> Bool)",
            "shouldSuppressStoryRead: ((PeerId) -> Bool)",
            "shouldSuppressContentRead: ((PeerId) -> Bool)",
            "shouldSuppressUploadProgress: ((PeerId) -> Bool)",
            "shouldForceOfflineAfterOnline: ((PeerId) -> Bool)",
            "shouldSuggestGhostForStories: ((PeerId) -> Bool)",
            "shouldMarkReadAfterAction: ((PeerId) -> Bool)",
            "shouldUseScheduledMessages: ((PeerId) -> Bool)",
            "sendWithoutSoundMode: ((PeerId) -> Int32)",
            "isMessageHiddenByFilter: ((PeerId, Message) -> Bool)",
            "isShadowBanned: ((PeerId, PeerId) -> Bool)",
            "matchingMessageFilterIds: ((PeerId, Message) -> [String])",
            "isShowingFilteredMessages: ((PeerId, PeerId) -> Bool)",
            "setShowingFilteredMessages: ((PeerId, PeerId, Bool) -> Void)",
            "shouldDisableExternalLinkWarning: ((PeerId) -> Bool)",
            "shouldImproveLinkPreviews: ((PeerId) -> Bool)",
            "translationProvider: ((PeerId) -> GRVMTranslationProvider)",
            "shouldDisableAds: ((PeerId) -> Bool)",
            "shouldHideStories: ((PeerId) -> Bool)",
            "shouldDisableSimilarChannels: ((PeerId) -> Bool)",
            "shouldDisableNotificationDelay: ((PeerId) -> Bool)",
            "shouldFilterZalgo: ((PeerId) -> Bool)",
            "shouldShowSeconds: ((PeerId) -> Bool)",
            "shouldShowDialogID: ((PeerId) -> Bool)",
            "peerIdDisplayMode: ((PeerId) -> Int32)",
            "shouldConfirmStickers: ((PeerId) -> Bool)",
            "shouldConfirmGIF: ((PeerId) -> Bool)",
            "shouldConfirmVoice: ((PeerId) -> Bool)",
            "shouldSpoofWebviewAsAndroid: ((PeerId) -> Bool)",
            "shouldIncreaseWebviewHeight: ((PeerId) -> Bool)",
            "shouldIncreaseWebviewWidth: ((PeerId) -> Bool)",
        ):
            self.assertIn(signature, source)

    def test_translation_provider_lives_in_telegram_core(self) -> None:
        source = PROVIDER.read_text(encoding="utf-8")
        self.assertIn("enum GRVMTranslationProvider: Int32", source)
        self.assertIn("case telegram = 0", source)
        self.assertIn("case google = 1", source)
        self.assertIn("case yandex = 2", source)


if __name__ == "__main__":
    unittest.main()
