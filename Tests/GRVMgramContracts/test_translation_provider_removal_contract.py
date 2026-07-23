import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVIDER = ROOT / "submodules/TelegramCore/Sources/GRVMTranslationProvider.swift"
EXTERNAL = ROOT / "submodules/TelegramCore/Sources/GRVMExternalTranslation.swift"
TRANSLATE = ROOT / "submodules/TelegramCore/Sources/TelegramEngine/Messages/Translate.swift"
SETTINGS = ROOT / "submodules/AyuGramLib/Sources/AyuGramSettings.swift"
STRINGS_ENUM = ROOT / "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
ENGLISH = ROOT / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings"
RUSSIAN = ROOT / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


class TranslationProviderRemovalContractTests(unittest.TestCase):
    def test_provider_surface_contains_only_telegram_and_google(self) -> None:
        source = read(PROVIDER)
        cases = re.findall(r"^\s*case\s+(\w+)\s*=\s*(-?\d+)", source, re.MULTILINE)
        self.assertEqual(cases, [("telegram", "0"), ("google", "1")])
        self.assertNotIn("yandex", source.lower())

    def test_translation_runtime_has_no_yandex_transport_or_switch_case(self) -> None:
        external = read(EXTERNAL)
        translate = read(TRANSLATE)
        self.assertIn("translate.googleapis.com", external)
        self.assertIn("case .google:", external)
        for forbidden in (
            "case .yandex",
            ".google, .yandex",
            "grvmYandex",
            "translate.yandex.net",
        ):
            self.assertNotIn(forbidden, external)
            self.assertNotIn(forbidden, translate)

    def test_legacy_raw_value_two_normalizes_to_telegram(self) -> None:
        provider = read(PROVIDER)
        cases = {
            int(raw_value): name
            for name, raw_value in re.findall(
                r"^\s*case\s+(\w+)\s*=\s*(-?\d+)", provider, re.MULTILINE
            )
        }
        self.assertEqual(cases, {0: "telegram", 1: "google"})
        self.assertEqual(cases.get(2, cases[0]), "telegram")

        settings = read(SETTINGS)
        normalization = swift_block(
            settings, "private static func normalizedTranslationProvider"
        )
        self.assertIn("GRVMTranslationProvider(rawValue: value)?.rawValue", normalization)
        self.assertIn("?? GRVMTranslationProvider.telegram.rawValue", normalization)
        self.assertGreaterEqual(
            settings.count(
                "self.translationProvider = Self.normalizedTranslationProvider(translationProvider)"
            ),
            2,
        )
        mutation = swift_block(settings, "public var translationProvider")
        self.assertIn("Self.normalizedTranslationProvider(translationProvider)", mutation)
        self.assertIn(
            "let translationProvider = try container.decodeIfPresent(Int32.self, forKey: \"translationProvider\") ?? 0",
            settings,
        )
        self.assertIn(
            'container.encode(self.translationProvider, forKey: "translationProvider")',
            settings,
        )

    def test_yandex_translation_copy_is_removed_and_privacy_is_google_only(self) -> None:
        strings_enum = read(STRINGS_ENUM)
        english = read(ENGLISH)
        russian = read(RUSSIAN)
        for source in (strings_enum, english, russian):
            self.assertNotIn("GRVMgram.Translation.Yandex", source)
            self.assertNotIn("translationYandex", source)
        self.assertIn(
            '"GRVMgram.Translation.Privacy" = "Google receives the text you translate only when you select it.";',
            english,
        )
        self.assertIn(
            '"GRVMgram.Translation.Privacy" = "Google получает переводимый текст, только когда вы выбираете этот сервис.";',
            russian,
        )


if __name__ == "__main__":
    unittest.main()
