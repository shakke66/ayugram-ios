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

    def test_existing_envelope_never_falls_back_to_legacy_for_missing_account(self) -> None:
        source = ACCOUNT_SETTINGS.read_text(encoding="utf-8")
        self.assertIn(
            "return envelope.values[accountKey] ?? .defaultSettings",
            source,
        )
        self.assertIn("let existingEnvelope = entry?.get(GRVMAccountSettings.self)", source)
        self.assertIn("existingEnvelope == nil", source)

    def test_account_envelope_uses_postbox_safe_data_payload(self) -> None:
        source = ACCOUNT_SETTINGS.read_text(encoding="utf-8")
        for fragment in (
            "public init(from decoder: Decoder) throws",
            'container.decode(Data.self, forKey: "values")',
            "JSONDecoder().decode([Int64: AyuGramSettings].self, from: data)",
            'container.decode([Int64: AyuGramSettings].self, forKey: "values")',
            "public func encode(to encoder: Encoder) throws",
            "let data = try JSONEncoder().encode(self.values)",
            'try container.encode(data, forKey: "values")',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, source)
        self.assertNotIn('container.encode(self.values, forKey: "values")', source)

    def test_every_settings_controller_reads_and_writes_its_account(self) -> None:
        directory = ROOT / "submodules/AyuGramSettingsUI/Sources"
        for name in CONTROLLERS:
            source = (directory / name).read_text(encoding="utf-8")
            self.assertNotIn("updateAyuGramSettings(", source, name)
            self.assertNotIn("ayuGramSettings(", source, name)
            self.assertIn("context.account.peerId", source, name)

    def test_scheduled_messages_use_the_surviving_mutator(self) -> None:
        settings = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("mutating func setScheduledMessages", settings)
        self.assertNotIn("setReadOnAction", settings)
        self.assertNotIn("readOnAction", settings)
        core = (
            ROOT
            / "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("settings.setScheduledMessages(value)", core)
        self.assertNotIn("settings.setReadOnAction(value)", core)
        self.assertNotIn("settings.useScheduledMessages = value", core)


if __name__ == "__main__":
    unittest.main()
