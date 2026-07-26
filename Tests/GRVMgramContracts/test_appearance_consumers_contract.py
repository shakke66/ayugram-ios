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


class AppearanceConsumerContractTests(unittest.TestCase):
    def test_app_icon_picker_uses_native_bindings_and_persists_after_success(self) -> None:
        picker = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramAppIconPicker.swift"
        )
        appearance = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift"
        )
        for fragment in [
            "getAvailableAlternateIcons()",
            "getAlternateIconName()",
            "public func ayuGramAppIconPicker(",
            'let storedIdentifier = icon.isDefault ? "default" : icon.name',
            "icon.isDefault ? currentName == nil : icon.name == currentName",
            "requestSetAlternateIconName(icon.isDefault ? nil : icon.name",
            "var requestInFlight = false",
            "guard !requestInFlight else",
            "requestInFlight = true",
            "Queue.mainQueue().async",
            "requestInFlight = false",
            "guard success else",
            "onSelect(storedIdentifier)",
            "grvmAppIconDisplayTitle(displayIdentifier, strings: strings)",
            '"default": .appIconDefault',
            r'"\u{2713} \(title)"',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, picker)
        for fragment in [
            "sharedContext.mainWindow?.present(",
            "ayuGramAppIconPicker(",
            "on: .root",
            "arguments.updateString(\\.selectedAppIcon, rawIdentifier)",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, appearance)
        self.assertRegex(
            picker,
            re.compile(
                r"Queue\.mainQueue\(\)\.async\s*\{\s*"
                r"requestInFlight = false\s*guard success else",
                re.DOTALL,
            ),
        )
        self.assertLess(picker.index("guard success else"), picker.index("onSelect(storedIdentifier)"))
        self.assertNotIn("ayuGramAppIconOptions", picker + appearance)
        self.assertNotIn("updateString(\\.selectedAppIcon, icon.name)", appearance)

    def test_badge_consumers_receive_the_exact_active_account(self) -> None:
        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        reset_badge = app_delegate[
            app_delegate.index("    private func resetBadge()") : app_delegate.index(
                "    private func bindGRVMSharedContext", app_delegate.index("    private func resetBadge()")
            )
        ]
        for fragment in [
            "Signal<(AuthorizedApplicationContext?, Int32, Bool), NoError>",
            "combineLatest(",
            "context.applicationBadge",
            "grvmSettings(",
            "context.context.account.peerId",
            "context.context.sharedContext.accountManager",
            "settings.hideNotificationBadge",
            "map { count, hideBadge in",
            "return (context, count, hideBadge)",
            "start(next: { _, count, hideBadge in",
        ]:
            self.assertIn(fragment, reset_badge)
        self.assertNotIn("AyuGramHooks.chatAppearance", reset_badge)
        self.assertNotIn("AyuGramHooks.shouldHideNotificationBadge?()", app_delegate)

        root = source("submodules/TelegramUI/Sources/TelegramRootController.swift")
        self.assertIn("accountPeerId: self.context.account.peerId", root)

        controller = source("submodules/TabBarUI/Sources/TabBarController.swift")
        for fragment in [
            "import Postbox",
            "private let accountPeerId: PeerId?",
            "accountPeerId: PeerId? = nil",
            "self.accountPeerId = accountPeerId",
            "accountPeerId: self.accountPeerId",
        ]:
            self.assertIn(fragment, controller)

        node = source("submodules/TabBarUI/Sources/TabBarContollerNode.swift")
        for fragment in [
            "import Postbox",
            "import TelegramCore",
            "private let accountPeerId: PeerId?",
            "accountPeerId: PeerId?",
            "self.accountPeerId = accountPeerId",
            "AyuGramHooks.chatAppearance(accountPeerId: accountPeerId)",
        ]:
            self.assertIn(fragment, node)

        build = source("submodules/TabBarUI/BUILD")
        self.assertIn('"//submodules/Postbox:Postbox"', build)

        obsolete_node = source("submodules/TabBarUI/Sources/TabBarNode.swift")
        self.assertIn("badgeValue = value", obsolete_node)
        self.assertNotIn("AyuGramHooks", obsolete_node)

    def test_hide_badges_propagates_through_all_component_paths(self) -> None:
        text = source(
            "submodules/TelegramUI/Components/TabBarComponent/Sources/TabBarComponent.swift"
        )
        for fragment in [
            "public let hideBadges: Bool",
            "hideBadges: Bool = false",
            "self.hideBadges = hideBadges",
            "lhs.hideBadges != rhs.hideBadges",
            "let hideBadges: Bool",
            "hideBadges: Bool,",
            "component.hideBadges ? nil : tabBarItem.badgeValue",
        ]:
            self.assertIn(fragment, text)
        self.assertGreaterEqual(text.count("hideBadges: component.hideBadges"), 3)

        chat_list = source("submodules/ChatListUI/Sources/ChatListController.swift")
        chat_list_node = source(
            "submodules/ChatListUI/Sources/ChatListControllerNode.swift"
        )
        peer_selection = source(
            "submodules/TelegramUI/Components/PeerSelectionController/"
            "Sources/PeerSelectionController.swift"
        )
        legacy_tabs = source(
            "submodules/TelegramUI/Components/ChatList/"
            "ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift"
        )
        for consumer in (chat_list, peer_selection):
            reload_filters = swift_block(consumer, "private func reloadFilters(")
            self.assertIn("grvmSettings(", reload_filters)
            self.assertIn("settings.hideFolderCounters", reload_filters)
        self.assertIn(
            "if !controller.hideFolderCounters && unread.value != 0",
            chat_list_node,
        )
        self.assertIn("hideBadges: Bool", legacy_tabs)
        self.assertIn("self.hideBadges = hideBadges", legacy_tabs)
        self.assertIn("let badgeSpacing: CGFloat = self.hideBadges ? 0.0 : 4.0", legacy_tabs)
        self.assertIn("let badgeWidth: CGFloat = self.hideBadges ? 0.0", legacy_tabs)
        self.assertIn("self.hideBadges || self.unreadCount == 0", legacy_tabs)
        self.assertNotIn("AyuGramHooks.chatAppearance(", legacy_tabs)

    def test_folder_layout_uses_one_account_snapshot_and_one_visible_filter_set(self) -> None:
        policy = source(
            "submodules/TelegramUI/Components/ChatList/"
            "ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift"
        )
        chat_list = source("submodules/ChatListUI/Sources/ChatListController.swift")
        chat_list_node = source(
            "submodules/ChatListUI/Sources/ChatListControllerNode.swift"
        )
        peer_selection = source(
            "submodules/TelegramUI/Components/PeerSelectionController/"
            "Sources/PeerSelectionController.swift"
        )
        for fragment in [
            "public struct ChatListFilterTabPresentation: Equatable",
            "public func chatListFilterTabPresentation(",
            "hideAllChatsFolder && filters.contains(where: { $0.id != .all })",
            "let visibleFilters: [ChatListFilterTabEntry]",
            "visibleFilters = filters.filter { $0.id != .all }",
            "visibleFilters = filters",
            "resolvedSelectedFilter = visibleFilters.first?.id",
            "return ChatListFilterTabPresentation(",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, policy)

        for consumer in (chat_list, peer_selection):
            reload_filters = swift_block(consumer, "private func reloadFilters(")
            self.assertEqual(1, reload_filters.count("grvmSettings("))
            self.assertIn("settings.hideAllChatsFolder", reload_filters)
            self.assertIn("chatListFilterTabPresentation(", reload_filters)
            self.assertIn("filterItems.append(.all(unreadCount: 0))", reload_filters)
            self.assertNotIn("insert(.all, at: 0)", reload_filters)

        update_available = swift_block(
            chat_list_node, "public func updateAvailableFilters("
        )
        self.assertIn("let fallbackId = availableFilters.first?.id ?? .all", update_available)
        self.assertIn("self.switchToFilter(id: fallbackId", update_available)

        self.assertIn("let tabPresentation = chatListFilterTabPresentation(", chat_list_node)
        self.assertIn("tabs: tabPresentation.filters.map", chat_list_node)
        self.assertIn("selectedFilter: tabPresentation.selectedFilter", peer_selection)
        self.assertIn("let reorderedVisibleFilterIds", chat_list)
        self.assertIn("let visibleFilterIds", chat_list)
        self.assertNotIn("AyuGramHooks.chatAppearance(", policy)


if __name__ == "__main__":
    unittest.main()
