from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACK_PREVIEW = ROOT / "submodules/StickerPackPreviewUI/Sources/StickerPackPreviewGridItem.swift"
EMOJI_PAGER = ROOT / "submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiPagerContentComponent.swift"
EMOJI_LAYER = ROOT / "submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiKeyboardItemLayer.swift"
CHAT_BUBBLE = ROOT / "submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift"
CHAT_STICKER = ROOT / "submodules/TelegramUI/Components/Chat/ChatMessageStickerItemNode/Sources/ChatMessageStickerItemNode.swift"
CHAT_ANIMATED_STICKER = ROOT / "submodules/TelegramUI/Components/Chat/ChatMessageAnimatedStickerItemNode/Sources/ChatMessageAnimatedStickerItemNode.swift"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.index(signature)
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


class StickerBadgeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = source(PACK_PREVIEW)
        cls.pager = source(EMOJI_PAGER)
        cls.layer = source(EMOJI_LAYER)
        cls.chat = source(CHAT_BUBBLE)

    def test_pack_preview_clips_only_artwork_in_image_sized_wrapper(self) -> None:
        init_block = swift_block(self.pack, "override init()")
        layout_block = swift_block(self.pack, "override func layout()")

        self.assertIn("private let stickerArtworkCornerRadius: CGFloat = 5.0", self.pack)
        self.assertIn("private let artworkNode: ASDisplayNode", self.pack)
        self.assertIn("self.artworkNode.cornerRadius = stickerArtworkCornerRadius", init_block)
        self.assertIn("self.artworkNode.clipsToBounds = true", init_block)
        self.assertIn("self.containerNode.addSubnode(self.artworkNode)", init_block)
        self.assertIn("self.artworkNode.addSubnode(self.imageNode)", init_block)
        self.assertIn("self.artworkNode.addSubnode(self.placeholderNode)", init_block)
        self.assertIn("self.artworkNode.insertSubnode(animationNode, aboveSubnode: self.imageNode)", self.pack)
        self.assertNotIn("self.containerNode.insertSubnode(animationNode", self.pack)

        self.assertGreaterEqual(layout_block.count("self.artworkNode.frame = imageFrame"), 2)
        self.assertGreaterEqual(layout_block.count("self.imageNode.frame = CGRect(origin: .zero, size: imageSize)"), 2)
        self.assertIn("animationNode.frame = CGRect(origin: .zero, size: imageSize)", layout_block)
        self.assertIn("self.placeholderNode.frame = self.artworkNode.bounds", layout_block)
        self.assertNotIn("self.containerNode.cornerRadius", self.pack)
        self.assertNotIn("self.containerNode.clipsToBounds", self.pack)

    def test_detailed_keyboard_clipping_is_reusable_and_explicitly_reset(self) -> None:
        clipping = swift_block(self.layer, "func updateStickerArtworkClipping(isDetailed: Bool)")
        for layer_name in ("self", "self.underlyingContentLayer", "self.tintContentLayer"):
            self.assertIn(layer_name, clipping)
        self.assertIn("let cornerRadius: CGFloat = isDetailed ? 5.0 : 0.0", clipping)
        self.assertIn("let masksToBounds = isDetailed", clipping)
        self.assertGreaterEqual(clipping.count("cornerRadius = cornerRadius"), 3)
        self.assertGreaterEqual(clipping.count("masksToBounds = masksToBounds"), 3)

        self.assertIn(
            "itemLayer.updateStickerArtworkClipping(isDetailed: component.itemLayoutType == .detailed)",
            self.pager,
        )

    def test_chat_sticker_implementations_remain_unmodified_by_picker_rounding(self) -> None:
        for sticker_source in (source(CHAT_STICKER), source(CHAT_ANIMATED_STICKER)):
            self.assertNotIn("stickerArtworkCornerRadius", sticker_source)
            self.assertNotIn("updateStickerArtworkClipping", sticker_source)

    def test_channel_author_badge_gate_has_exact_truth_table(self) -> None:
        gate = swift_block(self.chat, "private func shouldDisplayChannelAuthorBadge(")
        for token in (
            "incoming",
            "displayHeader",
            "!item.presentationData.isPreview",
            "if case .customChatContents = item.chatLocation",
            "case .group = containingChannel.info",
            "effectiveAuthor is TelegramChannel",
        ):
            self.assertIn(token, gate)
        self.assertNotIn("currentCredibilityIcon", gate)

    def test_channel_author_badge_is_independent_from_credibility_state(self) -> None:
        self.assertIn("private var channelAuthorBadgeNode: ASImageNode?", self.chat)
        self.assertIn("let displayChannelAuthorBadge = shouldDisplayChannelAuthorBadge(", self.chat)
        self.assertIn("displayChannelAuthorBadge: displayChannelAuthorBadge", self.chat)
        credibility = swift_block(self.chat, "if let (currentCredibilityIcon, currentParticleColor) = currentCredibilityIcon")
        self.assertNotIn("shouldDisplayChannelAuthorBadge", credibility)
        self.assertNotIn("channelAuthorBadgeNode = ASImageNode()", credibility)
        self.assertNotIn("channelAuthorBadgeNode.removeFromSupernode()", credibility)
        self.assertIn('UIImage(bundleImageName: "Chat List/Search/Channel")', self.chat)
        self.assertIn("generateTintedImage", self.chat)

    def test_badge_reserves_width_precedes_credibility_and_cleans_up(self) -> None:
        self.assertIn("let channelAuthorBadgeSize = CGSize(width: 16.0, height: 16.0)", self.chat)
        self.assertIn("let channelAuthorBadgeSpacing: CGFloat = 3.0", self.chat)
        self.assertIn("channelAuthorBadgeWidth", self.chat)
        self.assertIn("credibilityIconWidth + channelAuthorBadgeWidth", self.chat)
        self.assertIn("nameNode.frame.maxX + channelAuthorBadgeSpacing", self.chat)
        self.assertIn("channelAuthorBadgeFrame?.maxX ?? nameNode.frame.maxX", self.chat)
        self.assertIn("credibilityIconX + 3.0", self.chat)
        self.assertGreaterEqual(self.chat.count("strongSelf.channelAuthorBadgeNode = nil"), 3)
        self.assertIn("channelAuthorBadgeNode.removeFromSupernode()", self.chat)
        self.assertIn("channelAuthorBadgeNode?.removeFromSupernode()", self.chat)
        self.assertIn("strongSelf.channelAuthorBadgeNode?.removeFromSupernode()", self.chat)


if __name__ == "__main__":
    unittest.main()
