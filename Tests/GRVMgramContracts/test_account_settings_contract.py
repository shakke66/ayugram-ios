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


def swift_block(source: str, signature: str) -> str:
    start = source.find(signature)
    if start == -1:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening_brace = source.index("{", start)
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


class AccountSettingsContractTests(unittest.TestCase):
    def test_new_key_keeps_the_legacy_key(self) -> None:
        source = KEYS.read_text(encoding="utf-8")
        self.assertIn("case ayuGramSettings = 23", source)
        self.assertIn("case grvmAccountSettings = 24", source)
        self.assertIn("static let grvmAccountSettings", source)

    def test_envelope_and_updates_are_client_wide(self) -> None:
        source = ACCOUNT_SETTINGS.read_text(encoding="utf-8")
        envelope = swift_block(source, "public struct GRVMAccountSettings")
        read = swift_block(source, "public func grvmSettings(")
        update = swift_block(source, "public func updateGRVMSettings(")
        self.assertIn("public var settings: AyuGramSettings", envelope)
        self.assertIn("public init(settings: AyuGramSettings)", envelope)
        self.assertNotIn("public var values:", envelope)
        for operation in (read, update):
            self.assertIn("accountId: PeerId", operation)
            self.assertIn("_ = accountId", operation)
            self.assertIn(
                "ApplicationSpecificSharedDataKeys.grvmAccountSettings",
                operation,
            )
            self.assertNotIn("accountId.toInt64()", operation)
            self.assertNotIn("values[", operation)
        self.assertIn("return envelope.settings", read)
        self.assertIn("entry?.get(GRVMAccountSettings.self)?.settings", update)
        self.assertIn("GRVMAccountSettings(settings: f(currentSettings))", update)

    def test_new_snapshot_never_falls_back_to_a_legacy_account_entry(self) -> None:
        source = ACCOUNT_SETTINGS.read_text(encoding="utf-8")
        read = swift_block(source, "public func grvmSettings(")
        update = swift_block(source, "public func updateGRVMSettings(")
        migration = swift_block(source, "public func migrateGRVMSettings(")
        self.assertNotIn("LegacyGRVMAccountSettings", read)
        self.assertNotIn("LegacyGRVMAccountSettings", update)
        self.assertIn("existingEntry?.get(GRVMAccountSettings.self)", migration)
        self.assertIn(
            "existingEntry?.get(LegacyGRVMAccountSettings.self)",
            migration,
        )
        new_snapshot = migration.index("existingEntry?.get(GRVMAccountSettings.self)")
        old_map = migration.index("existingEntry?.get(LegacyGRVMAccountSettings.self)")
        self.assertLess(new_snapshot, old_map)
        self.assertIn("return", migration[new_snapshot:old_map])

    def test_client_envelope_uses_postbox_safe_data_payload(self) -> None:
        source = ACCOUNT_SETTINGS.read_text(encoding="utf-8")
        envelope = swift_block(source, "public struct GRVMAccountSettings")
        legacy = swift_block(source, "private struct LegacyGRVMAccountSettings")
        for fragment in (
            "public init(from decoder: Decoder) throws",
            'container.decode(Data.self, forKey: "settings")',
            "JSONDecoder().decode(AyuGramSettings.self, from: data)",
            "public func encode(to encoder: Encoder) throws",
            "let data = try JSONEncoder().encode(self.settings)",
            'try container.encode(data, forKey: "settings")',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, envelope)
        self.assertNotIn('container.encode(self.settings, forKey: "settings")', envelope)
        for fragment in (
            'container.decode(Data.self, forKey: "values")',
            "JSONDecoder().decode([Int64: AyuGramSettings].self, from: data)",
            'container.decode([Int64: AyuGramSettings].self, forKey: "values")',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, legacy)

    def test_migration_precedence_is_deterministic(self) -> None:
        source = ACCOUNT_SETTINGS.read_text(encoding="utf-8")
        migration = swift_block(source, "public func migrateGRVMSettings(")
        for fragment in (
            "primaryAccountId: PeerId?",
            "primaryAccountId.flatMap { legacyValues[$0.toInt64()] }",
            "accountIds.map { $0.toInt64() }.sorted()",
            ".compactMap { legacyValues[$0] }",
            "primarySettings ?? fallbackSettings ?? legacySettings ?? .defaultSettings",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, migration)
        self.assertNotIn("for accountId in accountIds", migration)

    def test_every_settings_controller_reads_and_writes_its_account(self) -> None:
        directory = ROOT / "submodules/AyuGramSettingsUI/Sources"
        for name in CONTROLLERS:
            source = (directory / name).read_text(encoding="utf-8")
            self.assertNotIn("updateAyuGramSettings(", source, name)
            self.assertNotIn("ayuGramSettings(", source, name)
            self.assertIn("context.account.peerId", source, name)

    def test_removed_scheduled_messages_have_no_settings_or_controller_path(self) -> None:
        settings = SETTINGS.read_text(encoding="utf-8")
        for removed in (
            "public var useScheduledMessages: Bool",
            "mutating func setScheduledMessages",
            'forKey: "useScheduledMessages"',
        ):
            self.assertNotIn(removed, settings)
        self.assertNotIn("setReadOnAction", settings)
        self.assertNotIn("readOnAction", settings)
        core = (
            ROOT
            / "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift"
        ).read_text(encoding="utf-8")
        self.assertNotIn("toggleUseScheduledMessages", core)
        self.assertNotIn("useScheduledMessages", core)
        self.assertNotIn("settings.setReadOnAction(value)", core)


if __name__ == "__main__":
    unittest.main()
