import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


class RuntimeRemovalCompatibilityContractTests(unittest.TestCase):
    def test_removed_hooks_are_neither_declared_nor_wired(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        for symbol in (
            "shouldForceOfflineAfterOnline",
            "shouldMarkReadAfterAction",
            "shouldSpoofWebviewAsAndroid",
            "shouldIncreaseWebviewHeight",
            "shouldIncreaseWebviewWidth",
            "shouldUseAdaptiveSavedMusicCover",
            "shouldUseMD3Switches",
            "messageBubbleRadius",
            "shouldUseSingleCornerRadius",
            "shouldShowMessageShot",
            "shouldSendWithoutSound",
        ):
            with self.subTest(symbol=symbol):
                self.assertNotIn(symbol, hooks)
                self.assertNotIn(symbol, manager)

    def test_surviving_ghost_runtime_uses_only_final_schema_names(self) -> None:
        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        ghost = manager[
            manager.index("// MARK: - Ghost Mode") : manager.index(
                "// MARK: - Premium & Ads"
            )
        ]
        for token in (
            "settings.suppressReadReceipts",
            "settings.suppressStoryReads",
            "settings.suppressOnlineStatus",
            "settings.suppressTypingAndUploads",
        ):
            self.assertIn(token, ghost)
        self.assertNotIn("ghostModeEnabled", ghost)

        schedule = swift_block(manager, "AyuGramHooks.shouldUseScheduledMessages =")
        self.assertIn("settings.useScheduledMessages", schedule)
        self.assertNotIn("ghostModeEnabled", schedule)
        self.assertNotIn("readOnAction", schedule)

        silent = swift_block(manager, "AyuGramHooks.sendWithoutSoundMode =")
        self.assertIn("settings.sendWithoutSoundMode", silent)
        self.assertNotIn("sendWithoutSoundOption", silent)

    def test_history_presentation_predicate_ignores_removed_bubble_radius(self) -> None:
        history = source("submodules/TelegramUI/Sources/ChatHistoryListNode.swift")
        appearance_start = history.index(
            "let chatAppearance: Signal<GRVMAppearanceSettings, NoError>"
        )
        distinct = swift_block(
            history[appearance_start:], "|> distinctUntilChanged(isEqual:"
        )
        self.assertIn("lhs.codeFontName == rhs.codeFontName", distinct)
        self.assertIn(
            "lhs.removeMessageBubbleTail == rhs.removeMessageBubbleTail", distinct
        )
        self.assertNotIn("messageBubbleRadius", distinct)

        update_start = history.index("if !didSetPresentationData")
        update = history[update_start : history.index("{", update_start)]
        self.assertIn(
            "previousChatAppearance?.codeFontName != chatAppearance.codeFontName",
            update,
        )
        self.assertIn(
            "previousChatAppearance?.removeMessageBubbleTail != chatAppearance.removeMessageBubbleTail",
            update,
        )
        self.assertNotIn("messageBubbleRadius", update)


if __name__ == "__main__":
    unittest.main()
