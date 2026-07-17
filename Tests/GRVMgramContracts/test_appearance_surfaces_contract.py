from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


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


class AppearanceSurfacesContractTests(unittest.TestCase):
    def test_primary_snapshot_drives_real_switch_initialization(self) -> None:
        build = source("submodules/AyuGramFeatures/BUILD")
        self.assertIn('"//submodules/Display:Display"', build)

        policy = source(
            "submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift"
        )
        for fragment in [
            "import Display",
            "Queue.mainQueue().async",
            "AyuGramHooks.updatePrimaryChatAppearance(",
            "SwitchNode.defaultStyle =",
            ".md3",
            ".standard",
        ]:
            self.assertIn(fragment, policy)

        registry = source(
            "submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift"
        )
        self.assertIn("private func publishPrimaryAppearance()", registry)
        self.assertGreaterEqual(registry.count("publishPrimaryAppearance()"), 5)
        self.assertIn(
            "publishPrimaryAppearance()",
            swift_block(registry, "public func setPrimaryAccount("),
        )
        settings_update = swift_block(
            registry,
            "settingsDisposable.set(grvmSettings(",
        )
        self.assertLess(
            settings_update.index("coordinator.updateSettings(settings)"),
            settings_update.index("publishPrimaryAppearance()"),
        )

        switch = source("submodules/Display/Source/SwitchNode.swift")
        for fragment in [
            "public enum Style",
            "case standard",
            "case md3",
            "public static var defaultStyle",
            "private let style: Style",
            "self.style = Self.defaultStyle",
            "case .md3:",
        ]:
            self.assertIn(fragment, switch)

    def test_avatar_geometry_is_account_exact_and_draw_stable(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        self.assertIn("public static private(set) var primaryChatAppearance", hooks)
        self.assertIn("public static func updatePrimaryChatAppearance(", hooks)

        avatar = source("submodules/AvatarNode/Sources/AvatarNode.swift")
        for fragment in [
            "AyuGramHooks.chatAppearance(accountPeerId:",
            "AyuGramHooks.primaryChatAppearance.appearance",
            "min(50, max(0, appearance.avatarCorners))",
            "appearance.singleCornerRadius",
            "let cornerRadius: CGFloat",
            "cornerRadius: cornerRadius",
            "let cornerRadius = effectiveAvatarCornerRadius(",
            "parameters.cornerRadius",
            "AvatarNode.addAvatarBubblePath",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, avatar)
        params = swift_block(avatar, "private struct Params: Equatable")
        self.assertIn("let cornerRadius: CGFloat", params)
        self.assertNotIn("AyuGramHooks.avatarCornerRadius?()", avatar)

    def test_live_chat_presentation_uses_exact_account_font_and_corners(self) -> None:
        data = source(
            "submodules/TelegramPresentationData/Sources/ChatPresentationData.swift"
        )
        for fragment in [
            "public let accountPeerId: PeerId?",
            "accountPeerId: PeerId? = nil",
            "AyuGramHooks.chatAppearance(accountPeerId: accountPeerId).appearance",
            "min(16, max(0, appearance.messageBubbleRadius))",
            "let radiusScale = CGFloat(messageBubbleRadius) / 16.0",
            "mainRadius: chatBubbleCorners.mainRadius * radiusScale",
            "auxiliaryRadius: chatBubbleCorners.auxiliaryRadius * radiusScale",
            "appearance.codeFontName",
            "UIFont(name: fontName, size: baseFontSize) ?? Font.monospace(baseFontSize)",
            "theme: theme",
            "accountPeerId: self.accountPeerId",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, data)
        self.assertNotIn("AyuGramHooks.codeFontName?()", data)

        history = source("submodules/TelegramUI/Sources/ChatHistoryListNode.swift")
        self.assertGreaterEqual(
            history.count("accountPeerId: context.account.peerId"), 2
        )

        images = source(
            "submodules/TelegramPresentationData/Sources/ChatMessageBubbleImages.swift"
        )
        background = source(
            "submodules/ChatMessageBackground/Sources/ChatMessageBackground.swift"
        )
        self.assertNotIn("AyuGramHooks.messageBubbleRadius?()", images)
        self.assertIn("let maxRadius = bubbleCorners.mainRadius", background)
        self.assertIn("let minRadius = bubbleCorners.auxiliaryRadius", background)

    def test_wallpaper_policy_keeps_forced_priority_and_explicit_default(self) -> None:
        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        forced_start = chat.index("if let forcedWallpaper = strongSelf.forcedWallpaper")
        start = chat.rindex("let appearance = AyuGramHooks.chatAppearance(", 0, forced_start)
        wallpaper = chat[start : chat.index("let isFirstTime", start)]
        for fragment in [
            "AyuGramHooks.chatAppearance(",
            "accountPeerId: strongSelf.context.account.peerId",
            "appearance.disableCustomBackgrounds",
            "presentationData.theme.chat.defaultWallpaper",
            "else if let chatWallpaper",
        ]:
            self.assertIn(fragment, wallpaper)
        self.assertLess(
            wallpaper.index("forcedWallpaper"),
            wallpaper.index("appearance.disableCustomBackgrounds"),
        )
        self.assertNotIn("AyuGramHooks.shouldDisableCustomBackgrounds?()", chat)

    def test_all_premium_surfaces_use_typed_account_policy(self) -> None:
        surfaces = [
            (
                "submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleComponent.swift",
                "component.context.account.peerId",
                "titleStatusIcon = .emojiStatus",
            ),
            (
                "submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleView.swift",
                "self.context.account.peerId",
                "titleStatusIcon = .emojiStatus",
            ),
            (
                "submodules/ChatListUI/Sources/Node/ChatListItem.swift",
                "item.context.account.peerId",
                "currentStatusIconContent = .animation",
            ),
            (
                "submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift",
                "item.context.account.peerId",
                "currentCredibilityIcon = (.premium",
            ),
            (
                "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift",
                "self.context.account.peerId",
                "credibilityIcon = .premium",
            ),
            (
                "submodules/ItemListPeerItem/Sources/ItemListPeerItem.swift",
                "context.account.peerId",
                "case .custom:",
            ),
            (
                "submodules/ContactsPeerItem/Sources/ContactsPeerItem.swift",
                "item.context.account.peerId",
                "credibilityIcon = .premium",
            ),
            (
                "submodules/TelegramUI/Components/ChatListHeaderComponent/Sources/ChatListHeaderComponent.swift",
                "component.context.account.peerId",
                "primaryTitlePeerStatus = .emoji",
            ),
        ]
        legacy = "AyuGramHooks.shouldHidePremiumStatuses?()"
        for path, account_expression, status_anchor in surfaces:
            with self.subTest(path=path):
                text = source(path)
                self.assertRegex(
                    text,
                    re.compile(
                        r"AyuGramHooks\.chatAppearance\(\s*accountPeerId:\s*"
                        + re.escape(account_expression)
                        + r"\s*\)",
                        re.DOTALL,
                    ),
                )
                self.assertIn(".appearance.hidePremiumStatuses", text)
                self.assertIn(status_anchor, text)
                self.assertNotIn(legacy, text)

        header = source(
            "submodules/TelegramUI/Components/ChatListHeaderComponent/Sources/ChatListHeaderComponent.swift"
        )
        self.assertGreaterEqual(header.count("AyuGramHooks.chatAppearance("), 2)
        self.assertIn("public func emojiStatus() -> PeerEmojiStatus?", header)

        ordinary_title = source(
            "submodules/TelegramUI/Components/ChatListTitleView/Sources/ChatListTitleView.swift"
        )
        self.assertRegex(
            ordinary_title,
            re.compile(
                r"AyuGramHooks\.chatAppearance\(\s*accountPeerId:\s*"
                r"self\.context\.account\.peerId\s*\)",
                re.DOTALL,
            ),
        )
        self.assertIn("title.peerStatus = nil", ordinary_title)

        producer = source("submodules/ChatListUI/Sources/ChatListController.swift")
        peer_status = swift_block(
            producer, "let peerStatus: Signal<NetworkStatusTitle.Status?, NoError>"
        )
        self.assertIn("context.account.peerId", peer_status)
        self.assertIn(".appearance.hidePremiumStatuses", peer_status)
        self.assertIn("if let emojiStatus = user.emojiStatus", peer_status)
        self.assertIn("else if user.isPremium", peer_status)

    def test_premium_gate_never_wraps_trust_badges(self) -> None:
        paths = [
            "submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleComponent.swift",
            "submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleView.swift",
            "submodules/ChatListUI/Sources/Node/ChatListItem.swift",
            "submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift",
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift",
            "submodules/ItemListPeerItem/Sources/ItemListPeerItem.swift",
            "submodules/ContactsPeerItem/Sources/ContactsPeerItem.swift",
        ]
        trust_tokens = r"isScam|isFake|isVerified|verificationIconFileId|verifiedIcon"
        for path in paths:
            with self.subTest(path=path):
                text = source(path)
                self.assertNotRegex(text, r"guard\s+!?hidePremiumStatuses")
                self.assertNotRegex(text, r"if\s+!hidePremiumStatuses\s*\{")
                for match in re.finditer(
                    r"(?:if|else if)[^{]{0,240}hidePremiumStatuses[^{]{0,240}\{",
                    text,
                    re.DOTALL,
                ):
                    self.assertNotRegex(match.group(0), trust_tokens)


if __name__ == "__main__":
    unittest.main()
