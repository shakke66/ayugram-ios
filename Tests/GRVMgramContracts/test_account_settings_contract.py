import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = ROOT / "submodules/TelegramUIPreferences/Sources/PostboxKeys.swift"
ACCOUNT_SETTINGS = ROOT / "submodules/AyuGramLib/Sources/GRVMAccountSettings.swift"
SETTINGS = ROOT / "submodules/AyuGramLib/Sources/AyuGramSettings.swift"
CONTROLLERS = (
    "AyuGramFiltersController.swift",
    "AyuGramShadowBanController.swift",
    "AyuGramGeneralController.swift",
    "AyuGramChatsController.swift",
    "AyuGramOtherController.swift",
    "AyuGramAppearanceController.swift",
    "AyuGramCoreController.swift",
)


class AccountSettingsContractTests(unittest.TestCase):
    def test_new_key_keeps_the_legacy_key(self) -> None:
        source = KEYS.read_text(encoding="utf-8")
        self.assertIn("case ayuGramSettings = 23", source)
        self.assertIn("case grvmAccountSettings = 24", source)
        self.assertIn("static let grvmAccountSettings", source)

    def test_envelope_and_updates_are_account_scoped(self) -> None:
        source = ACCOUNT_SETTINGS.read_text(encoding="utf-8")
        self.assertIn("public var values: [Int64: AyuGramSettings]", source)
        self.assertIn("accountId.toInt64()", source)
        self.assertIn("ApplicationSpecificSharedDataKeys.grvmAccountSettings", source)
        self.assertIn("ApplicationSpecificSharedDataKeys.ayuGramSettings", source)
        self.assertIn("values[accountKey]", source)
        self.assertIn("if values[accountKey] == nil", source)

    def test_every_settings_controller_reads_and_writes_its_account(self) -> None:
        directory = ROOT / "submodules/AyuGramSettingsUI/Sources"
        for name in CONTROLLERS:
            source = (directory / name).read_text(encoding="utf-8")
            self.assertNotIn("updateAyuGramSettings(", source, name)
            self.assertNotIn("ayuGramSettings(", source, name)
            self.assertIn("context.account.peerId", source, name)

    def test_mutually_exclusive_ghost_settings_use_mutators(self) -> None:
        settings = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("mutating func setReadOnAction", settings)
        self.assertIn("mutating func setScheduledMessages", settings)
        core = (
            ROOT
            / "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("settings.setReadOnAction(value)", core)
        self.assertIn("settings.setScheduledMessages(value)", core)
        self.assertNotIn("settings.readOnAction = value", core)
        self.assertNotIn("settings.useScheduledMessages = value", core)


if __name__ == "__main__":
    unittest.main()
