import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVIDER = ROOT / "submodules/TelegramCore/Sources/GRVMTranslationProvider.swift"
EXTERNAL = ROOT / "submodules/TelegramCore/Sources/GRVMExternalTranslation.swift"
TRANSLATE = ROOT / "submodules/TelegramCore/Sources/TelegramEngine/Messages/Translate.swift"
ENGINE = (
    ROOT
    / "submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift"
)
CHAT_TRANSLATION = ROOT / "submodules/TranslateUI/Sources/ChatTranslation.swift"
FEATURE_MANAGER = ROOT / "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
GENERAL = ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


class GeneralTranslationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provider = read(PROVIDER)
        cls.external = read(EXTERNAL)
        cls.translate = read(TRANSLATE)
        cls.engine = read(ENGINE)
        cls.chat_translation = read(CHAT_TRANSLATION)
        cls.feature_manager = read(FEATURE_MANAGER)
        cls.general = read(GENERAL)

    def test_provider_has_exactly_three_cases(self) -> None:
        cases = re.findall(r"^\s*case\s+(\w+)\s*=", self.provider, re.MULTILINE)
        self.assertEqual(cases, ["telegram", "google", "yandex"])
        self.assertNotIn("case native", self.provider.lower())

    def test_external_requests_are_bounded_keyless_and_strict(self) -> None:
        for token in (
            "translate.googleapis.com",
            "translate.yandex.net",
            "URLComponents",
            "URLQueryItem",
            "URLSession.shared.dataTask(with: request)",
            "request.timeoutInterval = 15.0",
            "200 ..< 300",
            "maximumConcurrentGoogleRequests = 4",
            "responseTexts.count == texts.count",
        ):
            self.assertIn(token, self.external)
        lowered = self.external.lower()
        for forbidden in ("api_key", "apikey", "api-key", "aiza"):
            self.assertNotIn(forbidden, lowered)

    def test_provider_is_threaded_through_all_translation_paths(self) -> None:
        self.assertRegex(
            self.engine,
            r"public func translateMessages\([\s\S]*?"
            r"provider: GRVMTranslationProvider = \.telegram,[\s\S]*?"
            r"tone: TranslationTone = \.neutral",
        )
        for token in (
            "provider: provider",
            "provider: GRVMTranslationProvider",
            "switch provider",
            "case .telegram:",
            "grvmExternalTranslate(",
            "pollSignals",
            "audioTranscriptionsSignals",
            "Api.functions.messages.translateText",
        ):
            self.assertIn(token, self.translate)

    def test_external_message_batch_skips_empty_text_without_losing_id_order(self) -> None:
        for token in (
            "let externalMessages = messages.filter { !$0.text.isEmpty }",
            "let translatedMessageIds: [MessageId]",
            "translatedMessageIds = externalMessages.map(\\.id)",
            "texts: externalMessages.map(\\.text)",
            "let messageId = translatedMessageIds[index]",
        ):
            self.assertIn(token, self.translate)
        self.assertNotIn("texts: messages.map(\\.text)", self.translate)

    def test_signal_payload_types_and_json_outputs_are_explicitly_validated(self) -> None:
        for token in (
            "let translatedTexts: [(String, [MessageTextEntity])]",
            "let translatedText: (String, [MessageTextEntity])?",
            "let translatedResult: Api.messages.TranslatedText?",
        ):
            self.assertIn(token, self.translate)
        self.assertIn("guard !result.isEmpty else", self.external)
        self.assertIn("responseTexts.allSatisfy", self.external)
        self.assertNotIn('return .single("")', self.external)

    def test_provider_selection_is_account_scoped_and_has_no_native_row(self) -> None:
        for token in (
            "AyuGramHooks.translationProvider =",
            "settings(accountPeerId: accountPeerId)",
            "GRVMTranslationProvider(rawValue:",
        ):
            self.assertIn(token, self.feature_manager)
        for token in (
            "AyuGramHooks.translationProvider?(context.account.peerId)",
            "provider: provider",
        ):
            self.assertIn(token, self.chat_translation)
        self.assertIn('["Telegram", "Google", "Yandex"]', self.general)
        self.assertIn("(value + 1) % 3", self.general)
        self.assertNotIn('"Native"', self.general)
        self.assertIn("updateGRVMSettings(accountId: context.account.peerId", self.general)


if __name__ == "__main__":
    unittest.main()
