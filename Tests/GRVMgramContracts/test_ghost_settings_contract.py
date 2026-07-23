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
    def test_four_surviving_components_exist_and_removed_models_are_gone(self) -> None:
        self.assertFalse(MODELS.exists())
        settings = SETTINGS.read_text(encoding="utf-8")
        for field in (
            "suppressReadReceipts",
            "suppressStoryReads",
            "suppressOnlineStatus",
            "suppressTypingAndUploads",
            "filters",
            "disableExternalLinkWarning",
        ):
            self.assertIn(f"var {field}:", settings)
        for field in (
            "ghostLockedComponents",
            "goOfflineAfterOnline",
            "readOnAction",
            "increaseWebviewHeight",
            "increaseWebviewWidth",
        ):
            self.assertNotIn(f"var {field}:", settings)

    def test_filter_shape_is_stable(self) -> None:
        source = FILTER.read_text(encoding="utf-8")
        for field in ("id", "expression", "isEnabled", "isReversed", "isCaseInsensitive", "peerId", "excludedPeerIds"):
            self.assertIn(f"var {field}:", source)
        self.assertIn("CryptoSHA1", source)
        self.assertIn("kind: String, index: Int, expression: String", source)
        self.assertIn("bytes[6] = (bytes[6] & 0x0f) | 0x50", source)
        self.assertIn("bytes[8] = (bytes[8] & 0x3f) | 0x80", source)

    def test_decoding_migrates_surviving_values_and_encoding_uses_canonical_ghost_keys(self) -> None:
        source = SETTINGS.read_text(encoding="utf-8")
        for key in (
            "suppressReadReceipts",
            "suppressStoryReads",
            "suppressOnlineStatus",
            "suppressTypingAndUploads",
            "sendWithoutSoundMode",
            "filters",
            "disableExternalLinkWarning",
        ):
            self.assertGreaterEqual(source.count(f'forKey: "{key}"'), 2, key)
        self.assertIn("legacyMessageFilters.enumerated().map", source)
        self.assertIn("legacyReversedFilters.enumerated().map", source)
        self.assertIn("AyuMessageFilter.migratingLegacy", source)
        self.assertIn("self.sendWithoutSoundMode = sendWithoutSound ? 2 : 0", source)
        self.assertIn("GRVMTranslationProvider(rawValue:", source)
        for legacy_key in ("messageFilters", "reversedFilters"):
            self.assertIn(f'container.encode(self.{legacy_key}, forKey: "{legacy_key}")', source)
        for decode_only_key in (
            "sendWithoutSound",
            "sendWithoutSoundOption",
            "suppressTypingStatus",
            "suppressUploadProgress",
        ):
            self.assertIn(f'forKey: "{decode_only_key}"', source)
            self.assertNotIn(
                f'container.encode(self.{decode_only_key}, forKey: "{decode_only_key}")',
                source,
            )
        for removed_key in (
            "ghostLockedComponents",
            "goOfflineAfterOnline",
            "readOnAction",
            "increaseWebviewSize",
            "increaseWebviewHeight",
            "increaseWebviewWidth",
        ):
            self.assertNotIn(f'forKey: "{removed_key}"', source)

    def test_ghost_count_and_bulk_mutation_use_four_independent_components(self) -> None:
        source = SETTINGS.read_text(encoding="utf-8")
        count = swift_block(source, "public var ghostModeActiveCount")
        for component in (
            "suppressReadReceipts",
            "suppressStoryReads",
            "suppressOnlineStatus",
            "suppressTypingAndUploads",
        ):
            self.assertIn(f"if {component}", count)
        self.assertEqual(4, count.count("count += 1"))
        self.assertNotIn("goOfflineAfterOnline", count)

        mutation = swift_block(source, "public mutating func setGhostModeEnabled")
        for component in (
            "suppressReadReceipts",
            "suppressStoryReads",
            "suppressOnlineStatus",
            "suppressTypingAndUploads",
        ):
            self.assertIn(f"self.{component} = enabled", mutation)
        self.assertNotIn("goOfflineAfterOnline", mutation)
        self.assertNotIn("ghostLockedComponents", mutation)

    def test_removed_ghost_settings_have_no_schema_or_mutation_path(self) -> None:
        source = SETTINGS.read_text(encoding="utf-8")
        for removed in (
            "GRVMGhostComponent",
            "ghostLockedComponents",
            "goOfflineAfterOnline",
            "readOnAction",
            "setReadOnAction",
        ):
            self.assertNotIn(removed, source)

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
            "shouldSuggestGhostForStories: ((PeerId) -> Bool)",
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
        ):
            self.assertIn(signature, source)
        for removed_hook in (
            "shouldForceOfflineAfterOnline",
            "shouldMarkReadAfterAction",
            "shouldSpoofWebviewAsAndroid",
            "shouldIncreaseWebviewHeight",
            "shouldIncreaseWebviewWidth",
        ):
            self.assertNotIn(removed_hook, source)

    def test_translation_provider_lives_in_telegram_core(self) -> None:
        source = PROVIDER.read_text(encoding="utf-8")
        self.assertIn("enum GRVMTranslationProvider: Int32", source)
        self.assertIn("case telegram = 0", source)
        self.assertIn("case google = 1", source)
        self.assertNotIn("case yandex", source)


if __name__ == "__main__":
    unittest.main()
