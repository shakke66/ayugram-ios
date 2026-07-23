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
SETTINGS = ROOT / "submodules/AyuGramLib/Sources/AyuGramSettings.swift"
CHAT_CONTROLLER = ROOT / "submodules/TelegramUI/Sources/ChatController.swift"
CHAT_QUERIES = (
    ROOT / "submodules/TelegramUI/Sources/ChatInterfaceStateContextQueries.swift"
)
LINK_REWRITE = ROOT / "submodules/TelegramUI/Sources/GRVMLinkPreviewRewrite.swift"
WEBPAGE_BUBBLE = (
    ROOT
    / "submodules/TelegramUI/Components/Chat/ChatMessageWebpageBubbleContentNode/Sources/ChatMessageWebpageBubbleContentNode.swift"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


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

    def test_provider_has_exactly_two_cases(self) -> None:
        cases = re.findall(r"^\s*case\s+(\w+)\s*=", self.provider, re.MULTILINE)
        self.assertEqual(cases, ["telegram", "google"])
        self.assertNotIn("case native", self.provider.lower())

    def test_external_requests_are_bounded_keyless_and_strict(self) -> None:
        for token in (
            "translate.googleapis.com",
            "URLComponents",
            "URLQueryItem",
            "URLSession.shared.dataTask(with: request)",
            "request.timeoutInterval = 15.0",
            "200 ..< 300",
            "GRVMGoogleRequestScheduler(maxConcurrentRequests: 4)",
            "responseTexts.count == texts.count",
        ):
            self.assertIn(token, self.external)
        lowered = self.external.lower()
        for forbidden in ("api_key", "apikey", "api-key", "aiza"):
            self.assertNotIn(forbidden, lowered)
        for forbidden in ("translate.yandex.net", "grvmYandex", "case .yandex"):
            self.assertNotIn(forbidden, self.external)

    def test_google_request_limit_is_shared_at_the_request_start_boundary(self) -> None:
        for token in (
            "private final class GRVMGoogleRequestScheduler",
            "private let grvmGoogleRequestScheduler = GRVMGoogleRequestScheduler(",
            "let signal: Signal<String, TranslationError>",
            "func wrap(_ signal: Signal<String, TranslationError>)",
            "while activeCount < self.maxConcurrentRequests",
            "self.items.first(where: { !$0.isActive })",
            "let signal = grvmExternalTranslationRequest(request)",
            "return grvmGoogleRequestScheduler.wrap(signal)",
            "item.disposable?.dispose()",
        ):
            self.assertIn(token, self.external)
        self.assertGreaterEqual(self.external.count("strongSelf.items.remove(at: i)"), 3)
        self.assertGreaterEqual(self.external.count("strongSelf.update()"), 3)
        cancellation_start = self.external.index(
            "return ActionDisposable { [weak self, weak item] in"
        )
        cancellation_end = self.external.index(
            "    private func update()", cancellation_start
        )
        cancellation = self.external[cancellation_start:cancellation_end]
        self.assertEqual(cancellation.count("item.disposable?.dispose()"), 1)
        self.assertEqual(cancellation.count("strongSelf.items.remove(at: i)"), 1)
        self.assertEqual(cancellation.count("strongSelf.update()"), 1)
        self.assertNotIn("var batches:", self.external)
        self.assertNotIn("index + maximumConcurrentGoogleRequests", self.external)

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
        self.assertNotIn("grvmParseYandexTranslation", self.external)
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
        for key in (
            ".translationTelegram",
            ".translationGoogle",
        ):
            self.assertIn(f"strings[{key}]", self.general)
        self.assertNotIn("translationNative", self.general)
        self.assertIn("updateGRVMSettings(accountId: context.account.peerId", self.general)

    def test_general_disclosure_labels_and_cycles_normalize_legacy_raw_values(self) -> None:
        for token in (
            "let normalizedTranslationProvider = settings.translationProvider >= 0 && settings.translationProvider < Int32(providerNames.count) ? settings.translationProvider : 0",
            "let providerLabel = providerNames[Int(normalizedTranslationProvider)]",
            ".translationProvider(presentationData.theme, providerLabel, normalizedTranslationProvider)",
            r"arguments.updateInt32(\.translationProvider, (value + 1) % 2)",
            "let normalizedDialogId = settings.showDialogId >= 0 && settings.showDialogId < Int32(dialogIdLabels.count) ? settings.showDialogId : 0",
            "let dialogIdLabel = dialogIdLabels[Int(normalizedDialogId)]",
            ".showDialogId(presentationData.theme, dialogIdLabel, normalizedDialogId)",
            r"arguments.updateInt32(\.showDialogId, (value + 1) % 3)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.general)


class GeneralLinkContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = read(SETTINGS)
        cls.feature_manager = read(FEATURE_MANAGER)
        cls.general = read(GENERAL)
        cls.chat_controller = read(CHAT_CONTROLLER)
        cls.chat_queries = read(CHAT_QUERIES)
        cls.link_rewrite = read(LINK_REWRITE)
        cls.webpage_bubble = read(WEBPAGE_BUBBLE)

    def test_external_link_warning_is_off_by_default_and_account_scoped(self) -> None:
        self.assertIn("disableExternalLinkWarning: false", self.settings)
        self.assertIn(
            'decodeIfPresent(Bool.self, forKey: "disableExternalLinkWarning") ?? false',
            self.settings,
        )
        warning_hook = swift_block(
            self.feature_manager,
            "AyuGramHooks.shouldDisableExternalLinkWarning =",
        )
        self.assertIn("accountPeerId", warning_hook)
        self.assertIn("settings(accountPeerId: accountPeerId)", warning_hook)
        self.assertIn("disableExternalLinkWarning ?? false", warning_hook)
        self.assertIn("case disableExternalLinkWarning(PresentationTheme, Bool)", self.general)
        self.assertIn("title: strings[.generalLinkWarning]", self.general)
        self.assertIn("arguments.updateBool(\\.disableExternalLinkWarning, v)", self.general)

        open_url_start = self.chat_controller.index("func openUrl(")
        open_url_end = self.chat_controller.index("func openUrlIn(", open_url_start)
        open_url = self.chat_controller[open_url_start:open_url_end]
        for token in (
            "let effectiveSkipConcealedAlert = skipConcealedAlert",
            "AyuGramHooks.shouldDisableExternalLinkWarning?(",
            "self.context.account.peerId",
            "skipConcealedAlert: effectiveSkipConcealedAlert",
        ):
            self.assertIn(token, open_url)
        self.assertEqual(open_url.count("effectiveSkipConcealedAlert"), 2)

    def test_preview_rewrite_is_http_only_and_uses_exact_supported_hosts(self) -> None:
        for token in (
            "URLComponents(string: url)",
            'scheme == "http" || scheme == "https"',
            'case "twitter.com", "www.twitter.com", "x.com", "www.x.com":',
            'previewHost = "fixupx.com"',
            'case "tiktok.com", "www.tiktok.com":',
            'previewHost = "kktiktok.com"',
            'host.hasSuffix(".tiktok.com")',
            'previewHost = "\\(subdomain).kktiktok.com"',
            'case "reddit.com", "www.reddit.com":',
            'previewHost = "vxreddit.com"',
            'case "instagram.com", "www.instagram.com":',
            'previewHost = "kkclip.com"',
            'case "pixiv.net", "www.pixiv.net":',
            'previewHost = "phixiv.net"',
            "components.host = previewHost",
            "return components.string ?? url",
        ):
            self.assertIn(token, self.link_rewrite)
        self.assertNotIn("host.contains(", self.link_rewrite)
        self.assertNotIn("url.replacingOccurrences", self.link_rewrite)

    def test_preview_state_keeps_original_urls_and_rewrites_only_request(self) -> None:
        preview = swift_block(self.chat_queries, "func urlPreviewStateForInputText(")
        for token in (
            "let detectedUrls = detectUrls(inputText)",
            "UrlPreviewState(detectedUrls: detectedUrls)",
            "AyuGramHooks.shouldImproveLinkPreviews?(context.account.peerId) == true",
            "detectedUrls.map(grvmRewrittenLinkPreviewUrl)",
            "webpagePreview(account: context.account, urls: previewUrls, forPeerId: forPeerId)",
        ):
            self.assertIn(token, preview)
        self.assertNotIn("UrlPreviewState(detectedUrls: previewUrls)", preview)

    def test_rendered_preview_hint_uses_the_exact_account(self) -> None:
        self.assertIn(
            "AyuGramHooks.shouldImproveLinkPreviews?(item.context.account.peerId)",
            self.webpage_bubble,
        )
        self.assertNotIn("AyuGramHooks.shouldImproveLinkPreviews?()", self.webpage_bubble)


if __name__ == "__main__":
    unittest.main()
