import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TELEGRAM_UI = ROOT / "submodules/TelegramUI"
TIMESTAMP = (
    TELEGRAM_UI
    / "Components/Chat/ChatMessageDateAndStatusNode/Sources/StringForMessageTimestampStatus.swift"
)
BUBBLE = (
    TELEGRAM_UI
    / "Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift"
)
CONTEXT_EXTRACTION = (
    TELEGRAM_UI
    / "Components/ContextControllerImpl/Sources/ContextControllerExtractedPresentationNode.swift"
)
HOOKS = ROOT / "submodules/TelegramCore/Sources/AyuGramHooks.swift"
MANAGER = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"


def window(value: str, anchor: str, size: int) -> str:
    offset = value.index(anchor)
    return value[offset : offset + size]


class HistoryUIContractTests(unittest.TestCase):
    def test_timestamp_reads_persistent_attributes_and_keeps_configurable_marks(self) -> None:
        value = TIMESTAMP.read_text(encoding="utf-8")

        self.assertIn("$0 is GRVMDeletedMessageAttribute", value)
        self.assertIn("$0 is GRVMEditHistoryMessageAttribute", value)
        self.assertIn("AyuGramHooks.deletedMessageMark?()", value)
        self.assertIn("AyuGramHooks.editedMessageMark?()", value)
        self.assertIn('replaceMarksWithIcons ? "🗑"', value)
        self.assertIn('replaceMarksWithIcons ? "✏️"', value)
        self.assertNotIn("isMessageDeletedCheck", value)
        self.assertNotIn("hasEditHistoryCheck", value)

    def test_layout_components_never_query_the_archive_database(self) -> None:
        offenders = []
        components = TELEGRAM_UI / "Components"
        for path in components.rglob("*.swift"):
            value = path.read_text(encoding="utf-8")
            if any(
                token in value
                for token in (
                    "AyuDeletedMessagesDB",
                    "isMessageDeletedCheck",
                    "hasEditHistoryCheck",
                )
            ):
                offenders.append(str(path.relative_to(ROOT)))

        self.assertEqual([], offenders)

    def test_obsolete_synchronous_layout_hooks_are_removed(self) -> None:
        hooks = HOOKS.read_text(encoding="utf-8")
        manager = MANAGER.read_text(encoding="utf-8")

        self.assertNotIn("isMessageDeletedCheck", hooks)
        self.assertNotIn("hasEditHistoryCheck", hooks)
        self.assertNotIn("isMessageDeletedCheck", manager)
        self.assertNotIn("hasEditHistoryCheck", manager)

    def test_deleted_bubble_opacity_is_attribute_driven_and_guarded(self) -> None:
        value = BUBBLE.read_text(encoding="utf-8")
        anchor = "private func grvmDeletedMessageContentAlpha("
        self.assertIn(anchor, value)
        helper = window(value, anchor, 4500)

        for token in (
            "GRVMDeletedMessageAttribute",
            "shouldUseSemiTransparentDeleted",
            "selectionState == nil",
            "isRecentActions",
            "case let .message",
            "item.chatLocation",
            ".messageOptions",
            ".customChatContents",
            "0.7",
        ):
            with self.subTest(token=token):
                self.assertIn(token, helper)
        self.assertNotIn("isContextPreview", helper)

    def test_deleted_alpha_uses_extracting_parent_and_refreshes_for_selection(self) -> None:
        value = BUBBLE.read_text(encoding="utf-8")

        self.assertIn("self.mainContextSourceNode.alpha = grvmDeletedMessageContentAlpha(", value)
        self.assertNotIn("self.mainContextSourceNode.contentNode.alpha =", value)

        apply_section = window(value, "strongSelf.appliedItem = item", 900)
        self.assertIn("updateGRVMDeletedMessageContentAlpha", apply_section)

        main_preview = window(
            value,
            "self.mainContextSourceNode.willUpdateIsExtractedToContextPreview",
            1800,
        )
        self.assertNotIn("updateGRVMDeletedMessageContentAlpha", main_preview)

        grouped_preview = window(
            value,
            "contextSourceNode.willUpdateIsExtractedToContextPreview",
            1800,
        )
        self.assertNotIn("updateGRVMDeletedMessageContentAlpha", grouped_preview)

        selection = window(value, "override public func updateSelectionState", 9000)
        self.assertIn("updateGRVMDeletedMessageContentAlpha", selection)

    def test_context_preview_extracts_content_from_the_dimmed_parent(self) -> None:
        value = CONTEXT_EXTRACTION.read_text(encoding="utf-8")
        section = window(value, "func takeContainingNode()", 1000)
        self.assertIn("addSubnode(containingNode.contentNode)", section)

    def test_shared_timestamp_path_covers_bubble_and_standalone_media_nodes(self) -> None:
        call_sites = []
        chat_components = TELEGRAM_UI / "Components/Chat"
        for path in chat_components.rglob("*.swift"):
            if path == TIMESTAMP:
                continue
            if "stringForMessageTimestampStatus(" in path.read_text(encoding="utf-8"):
                call_sites.append(path.name)

        self.assertGreaterEqual(len(call_sites), 10)
        self.assertTrue(any("Sticker" in name for name in call_sites))
        self.assertTrue(any("File" in name for name in call_sites))


if __name__ == "__main__":
    unittest.main()
