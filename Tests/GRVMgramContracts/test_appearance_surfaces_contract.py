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
    def test_avatar_geometry_is_account_exact_and_draw_stable(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        self.assertIn("public static private(set) var primaryChatAppearance", hooks)
        self.assertIn("public static func updatePrimaryChatAppearance(", hooks)

        avatar = source("submodules/AvatarNode/Sources/AvatarNode.swift")
        for fragment in [
            "AyuGramHooks.chatAppearance(accountPeerId:",
            "AyuGramHooks.primaryChatAppearance.appearance",
            "min(50, max(0, appearance.avatarCorners))",
            "let cornerRadius: CGFloat",
            "cornerRadius: cornerRadius",
            "let cornerRadius = effectiveAvatarCornerRadius(",
            "parameters.cornerRadius",
            "AvatarNode.addAvatarBubblePath",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, avatar)
        radius_policy = swift_block(avatar, "private func effectiveAvatarCornerRadius(")
        self.assertIn("case .roundedRect:\n        return 0.25", radius_policy)
        self.assertNotIn("singleCornerRadius", radius_policy)
        params = swift_block(avatar, "private struct Params: Equatable")
        self.assertIn("let cornerRadius: CGFloat", params)
        self.assertNotIn("AyuGramHooks.avatarCornerRadius?()", avatar)

        for fragment in [
            "var normalizedCornerRadius: CGFloat",
            "normalizedCornerRadius: storyPresentationParams.forceRoundedRect ? nil : self.contentNode.normalizedCornerRadius",
        ]:
            self.assertIn(fragment, avatar)
        for signature in [
            "\n    public func setPeer(\n        accountPeerId:",
            "\n    public func setPeerV2(",
            "\n    public func setPeer(\n        context:",
            "\n    public func setCustomLetters(",
        ]:
            with self.subTest(signature=signature):
                self.assertIn(
                    "self.updateStoryIndicator(transition: .immediate)",
                    swift_block(avatar, signature),
                )

        indicator = source(
            "submodules/TelegramUI/Components/Stories/AvatarStoryIndicatorComponent/"
            "Sources/AvatarStoryIndicatorComponent.swift"
        )
        for fragment in [
            "public let normalizedCornerRadius: CGFloat?",
            "normalizedCornerRadius: CGFloat? = nil",
            "self.normalizedCornerRadius = normalizedCornerRadius",
            "lhs.normalizedCornerRadius != rhs.normalizedCornerRadius",
            "let resolvedCornerRadius: CGFloat",
            "let usesRoundedPath: Bool",
            "cornerRadius: resolvedCornerRadius",
            "if let progress = component.progress, !usesRoundedPath",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, indicator)
        self.assertNotIn("cornerRadius: floor(diameter * 0.27)", indicator)

    def test_live_chat_presentation_uses_exact_account_font_and_stock_corners(self) -> None:
        data = source(
            "submodules/TelegramPresentationData/Sources/ChatPresentationData.swift"
        )
        build = source("submodules/TelegramPresentationData/BUILD")
        self.assertIn("import Postbox", data)
        self.assertIn('"//submodules/Postbox:Postbox"', build)
        for fragment in [
            "public let accountPeerId: PeerId?",
            "accountPeerId: PeerId? = nil",
            "AyuGramHooks.chatAppearance(accountPeerId: accountPeerId).appearance",
            "mainRadius: chatBubbleCorners.mainRadius",
            "auxiliaryRadius: chatBubbleCorners.auxiliaryRadius",
            "appearance.codeFontName",
            "UIFont(name: fontName, size: baseFontSize) ?? Font.monospace(baseFontSize)",
            "theme: theme",
            "accountPeerId: self.accountPeerId",
            "private let chatAppearance: GRVMAppearanceSettings?",
            "chatAppearance: GRVMAppearanceSettings? = nil",
            "self.chatAppearance = chatAppearance",
            "chatAppearance: self.chatAppearance",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, data)
        self.assertNotIn("AyuGramHooks.codeFontName?()", data)
        self.assertNotIn("messageBubbleRadius", data)

        history = source("submodules/TelegramUI/Sources/ChatHistoryListNode.swift")
        self.assertIn("accountPeerId: context.account.peerId", history)
        presentation_management = swift_block(
            history, "private func beginPresentationDataManagement("
        )
        for fragment in [
            "grvmSettings(",
            "accountId: self.context.account.peerId",
            "accountManager: self.context.sharedContext.accountManager",
            "settings.grvmChatAppearanceSettings.appearance",
            "lhs.codeFontName == rhs.codeFontName",
            "previousChatAppearance?.codeFontName != chatAppearance.codeFontName",
            "previousChatAppearance = chatAppearance",
            "accountPeerId: strongSelf.context.account.peerId",
            "chatAppearance: chatAppearance",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, presentation_management)
        self.assertNotIn(
            "accountPeerId: context.account.peerId", presentation_management
        )
        self.assertNotIn("messageBubbleRadius", presentation_management)

        telegram_ui_build = source("submodules/TelegramUI/BUILD")
        self.assertIn('"//submodules/AyuGramFeatures:AyuGramFeatures"', telegram_ui_build)
        self.assertIn('"//submodules/AyuGramLib:AyuGramLib"', telegram_ui_build)

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

    def test_other_peer_premium_surfaces_use_typed_account_policy(self) -> None:
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

        ordinary_title = source(
            "submodules/TelegramUI/Components/ChatListTitleView/Sources/ChatListTitleView.swift"
        )
        set_title = swift_block(ordinary_title, "public func setTitle(")
        self.assertNotIn("hidePremiumStatuses", set_title)
        self.assertNotIn("title.peerStatus = nil", set_title)

        producer = source("submodules/ChatListUI/Sources/ChatListController.swift")
        peer_status_start = producer.index(
            "let peerStatus: Signal<NetworkStatusTitle.Status?, NoError>"
        )
        peer_status = producer[
            peer_status_start : producer.index("let networkState:", peer_status_start)
        ]
        for fragment in [
            "context.engine.data.subscribe(",
            "TelegramEngine.EngineData.Item.Peer.Peer(id: context.account.peerId)",
            "if let emojiStatus = user.emojiStatus",
            "else if user.isPremium",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, peer_status)
        self.assertNotIn("combineLatest(", peer_status)
        self.assertNotIn("grvmSettings(", peer_status)
        self.assertNotIn("hidePremiumStatuses", peer_status)
        self.assertNotIn("AyuGramHooks.chatAppearance(", peer_status)

        header = source(
            "submodules/TelegramUI/Components/ChatListHeaderComponent/Sources/ChatListHeaderComponent.swift"
        )
        emoji_status = swift_block(
            header, "public func emojiStatus() -> PeerEmojiStatus?"
        )
        self.assertNotIn("hidePremiumStatuses", emoji_status)
        self.assertIn("case let .emoji(emojiStatus) = peerStatus", emoji_status)

        chat_list_build = source("submodules/ChatListUI/BUILD")
        self.assertIn('"//submodules/AyuGramLib:AyuGramLib"', chat_list_build)

    def test_premium_hiding_compares_displayed_peer_with_exact_account(self) -> None:
        expectations = [
            (
                "submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleComponent.swift",
                "let shouldHidePremiumStatus = hidePremiumStatuses && peer.id != component.context.account.peerId",
                1,
            ),
            (
                "submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleView.swift",
                "let shouldHidePremiumStatus = hidePremiumStatuses && peer.id != self.context.account.peerId",
                1,
            ),
            (
                "submodules/ChatListUI/Sources/Node/ChatListItem.swift",
                "let shouldHidePremiumStatus = hidePremiumStatuses && peer.id != item.context.account.peerId",
                2,
            ),
            (
                "submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift",
                "let shouldHidePremiumStatus = hidePremiumStatuses && effectiveAuthor.id != item.context.account.peerId",
                1,
            ),
            (
                "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift",
                "let shouldHidePremiumStatus = hidePremiumStatuses && peer?.id != self.context.account.peerId",
                1,
            ),
            (
                "submodules/ItemListPeerItem/Sources/ItemListPeerItem.swift",
                "let shouldHidePremiumStatus = hidePremiumStatuses && item.peer.id != item.context.accountPeerId",
                1,
            ),
            (
                "submodules/ContactsPeerItem/Sources/ContactsPeerItem.swift",
                "let shouldHidePremiumStatus = hidePremiumStatuses && peer.id != item.context.account.peerId",
                1,
            ),
        ]
        for path, condition, minimum_count in expectations:
            with self.subTest(path=path):
                text = source(path)
                self.assertGreaterEqual(text.count(condition), minimum_count)
                self.assertIn("!shouldHidePremiumStatus", text)
                self.assertNotRegex(
                    text,
                    r"(?:emojiStatus|isPremium)[^\n]{0,240}!hidePremiumStatuses",
                )

        title_component = source(
            "submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleComponent.swift"
        )
        self.assertNotIn(
            "if peer.id != component.context.account.peerId {", title_component
        )

        title_view = source(
            "submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleView.swift"
        )
        self.assertNotIn("if peer.id != self.context.account.peerId {", title_view)

        chat_list = source("submodules/ChatListUI/Sources/Node/ChatListItem.swift")
        self.assertNotIn("var isAccountPeer = false", chat_list)
        self.assertNotIn("!isPeerGroup && !isAccountPeer", chat_list)

        peer_info = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift"
        )
        peer_info_icons_start = peer_info.index("let premiumConfiguration")
        peer_info_icons = peer_info[
            peer_info_icons_start : peer_info.index("var isForum", peer_info_icons_start)
        ]
        self.assertNotIn(
            "if peer.id == self.context.account.peerId && !self.isSettings && !self.isMyProfile",
            peer_info_icons,
        )

        item_list = source(
            "submodules/ItemListPeerItem/Sources/ItemListPeerItem.swift"
        )
        item_list_icons = item_list[
            item_list.index("var updatedLabelBadgeImage") : item_list.index(
                "var titleIconsWidth", item_list.index("var updatedLabelBadgeImage")
            )
        ]
        self.assertNotIn("threatSelfAsSaved", item_list_icons)

        contacts = source(
            "submodules/ContactsPeerItem/Sources/ContactsPeerItem.swift"
        )
        contacts_icons_start = contacts.index("var credibilityIcon:")
        contacts_icons = contacts[
            contacts_icons_start : contacts.index(
                "var titleAttributedString", contacts_icons_start
            )
        ]
        self.assertNotIn(
            "if let peer = peer, (peer.id != item.context.account.peerId",
            contacts_icons,
        )

    def test_story_header_keeps_the_account_premium_status(self) -> None:
        header = source(
            "submodules/TelegramUI/Components/ChatListHeaderComponent/Sources/ChatListHeaderComponent.swift"
        )
        status_start = header.index("var primaryTitlePeerStatus")
        account_status = header[
            status_start : header.index("let _ = storyPeerList.update", status_start)
        ]
        self.assertNotIn("hidePremiumStatuses", account_status)
        self.assertIn("if let peerStatus = chatListTitle.peerStatus", account_status)

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
