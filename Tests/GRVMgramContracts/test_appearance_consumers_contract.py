from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AppearanceConsumerContractTests(unittest.TestCase):
    def test_app_icon_picker_uses_native_bindings_and_persists_after_success(self) -> None:
        text = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift"
        )
        for fragment in [
            "getAvailableAlternateIcons()",
            "getAlternateIconName()",
            "sharedContext.mainWindow?.present(",
            "grvmAppIconPicker(",
            "on: .root",
            'let storedName = icon.isDefault ? "default" : icon.name',
            "icon.isDefault ? currentName == nil : icon.name == currentName",
            "requestSetAlternateIconName(icon.isDefault ? nil : icon.name",
            "var requestInFlight = false",
            "guard !requestInFlight else",
            "requestInFlight = true",
            "Queue.mainQueue().async",
            "requestInFlight = false",
            "guard success else",
            "updateString(\\.selectedAppIcon, storedName)",
            'let title = icon.isDefault ? "Default" : icon.name',
            r'"\u{2713} \(title)"',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        self.assertRegex(
            text,
            re.compile(
                r"Queue\.mainQueue\(\)\.async\s*\{\s*"
                r"requestInFlight = false\s*guard success else",
                re.DOTALL,
            ),
        )
        self.assertNotIn("ayuGramAppIconOptions", text)
        self.assertNotIn("updateString(\\.selectedAppIcon, icon.name)", text)

    def test_badge_consumers_receive_the_exact_active_account(self) -> None:
        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        for fragment in [
            "Signal<(AuthorizedApplicationContext?, Int32), NoError>",
            "map { (context, $0) }",
            "context.context.account.peerId",
            "appearance.hideNotificationBadge",
        ]:
            self.assertIn(fragment, app_delegate)
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

    def test_folder_layout_uses_one_account_snapshot_and_one_visible_filter_set(self) -> None:
        text = source(
            "submodules/TelegramUI/Components/ChatList/"
            "ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift"
        )
        self.assertEqual(text.count("AyuGramHooks.chatAppearance("), 2)
        self.assertGreaterEqual(
            text.count("accountPeerId: self.context.account.peerId"), 2
        )
        for fragment in [
            "appearance.hideFolderCounters",
            "appearance.hideAllChatsFolder",
            "let visibleFilters: [ChatListFilterTabEntry]",
            "visibleFilters = reorderedFilters.filter",
            "visibleFilters = reorderedFilters",
            "resolvedSelectedFilter = visibleFilters.first?.id",
            "for i in 0 ..< visibleFilters.count",
            "let filter = visibleFilters[i]",
            "resolvedSelectedFilter == visibleFilters[i - 1].id",
            "resolvedSelectedFilter == visibleFilters[i + 1].id",
            "if !visibleFilters.contains(where:",
            "for filter in visibleFilters",
            "visibleFilters.firstIndex(where:",
            "currentIndex != visibleFilters.count - 1",
            "resolvedSelectedFilter == visibleFilters.first?.id",
            "resolvedSelectedFilter == visibleFilters.last?.id",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)
        self.assertNotIn("shouldHideFolderCounters?()", text)
        self.assertNotIn("shouldHideAllChatsFolder?()", text)
        self.assertNotIn("selectedFilter == visibleFilters.first?.id", text)
        self.assertNotIn("selectedFilter == visibleFilters.last?.id", text)


if __name__ == "__main__":
    unittest.main()
