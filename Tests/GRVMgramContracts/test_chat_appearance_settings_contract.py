from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class ChatAppearanceSettingsContractTests(unittest.TestCase):
    def test_new_codable_fields_have_declaration_default_decode_and_encode(self) -> None:
        text = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        fields = {
            "showPrivateReactions": "true",
            "showAddFilterInContextMenu": "1",
            "showAttachPopup": "true",
            "showEmojiPopup": "true",
            "messageShotShowBackground": "true",
            "messageShotShowDate": "false",
            "messageShotShowReactions": "false",
            "messageShotShowHeader": "true",
            "messageShotShowHeaderDecorations": "true",
            "messageShotColorfulReplies": "true",
            "messageShotRevealSpoilers": "true",
            "messageShotTheme": "0",
        }
        for name, default in fields.items():
            with self.subTest(name=name):
                self.assertRegex(text, rf"public var {name}: (?:Bool|Int32)")
                self.assertIn(f"{name}: {default}", text)
                self.assertIn(f'forKey: "{name}") ?? {default}', text)
                self.assertIn(f'encode(self.{name}, forKey: "{name}")', text)

    def test_desktop_defaults_and_validation_are_explicit(self) -> None:
        settings = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        self.assertIn("recentStickersCount: 100", settings)
        self.assertIn(r'deletedMessageMark: "\u{1F9F9}"', settings)
        policy = source("submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift")
        required = [
            "min(200, max(1, self.recentStickersCount))",
            "min(50, max(0, self.avatarCorners))",
            "min(16, max(0, self.messageBubbleRadius))",
            "min(4.0, max(0.5, self.messageWidthMultiplier))",
            "(clampedWidth * 20.0).rounded() / 20.0",
            "GRVMContextMenuVisibility(rawValue:",
            "GRVMChannelBottomButtonMode(rawValue:",
            "GRVMMessageShotTheme(rawValue:",
        ]
        for fragment in required:
            self.assertIn(fragment, policy)

    def test_single_account_aware_hook_replaces_zero_argument_appearance_reads(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        self.assertIn(
            "public static var chatAppearanceSettings: ((PeerId) -> GRVMChatAppearanceSettings)?",
            hooks,
        )
        self.assertIn(
            "public static func chatAppearance(accountPeerId: PeerId) -> GRVMChatAppearanceSettings",
            hooks,
        )
        policy = source("submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift")
        self.assertIn("registry.service(accountPeerId: accountPeerId)", policy)
        self.assertIn("service.settingsSnapshot().grvmChatAppearanceSettings", policy)
        self.assertNotIn("primaryService()", policy)

    def test_settings_controllers_use_account_scoped_api(self) -> None:
        for relative_path in [
            "submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift",
            "submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift",
        ]:
            text = source(relative_path)
            self.assertIn(
                "grvmSettings(accountId: context.account.peerId, accountManager:",
                text,
            )
            self.assertIn(
                "updateGRVMSettings(accountId: context.account.peerId, accountManager:",
                text,
            )
            self.assertNotRegex(text, r"(?<!GRVM)ayuGramSettings\(accountManager:")
            self.assertNotRegex(text, r"(?<!GRVM)updateAyuGramSettings\(accountManager:")


if __name__ == "__main__":
    unittest.main()
