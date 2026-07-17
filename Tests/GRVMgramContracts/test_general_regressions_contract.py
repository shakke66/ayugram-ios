import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.index(signature)
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


class GeneralRegressionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )

    def assert_hook(self, hook: str, setting: str) -> None:
        producer = swift_block(self.manager, f"AyuGramHooks.{hook} =")
        self.assertIn("accountPeerId", producer)
        self.assertIn("settings(accountPeerId: accountPeerId)", producer)
        self.assertIn(setting, producer)

    def test_ads_stories_and_similar_channels_keep_exact_account_consumers(self) -> None:
        self.assert_hook("shouldDisableAds", "disableAds")
        self.assert_hook("shouldHideStories", "hideStories")
        self.assert_hook("shouldDisableSimilarChannels", "disableSimilarChannels")
        expected = {
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/AdMessages.swift":
                "shouldDisableAds?(self.account.peerId)",
            "submodules/TelegramUI/Components/ChatListHeaderComponent/Sources/ChatListHeaderComponent.swift":
                "shouldHideStories?(component.context.account.peerId)",
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoData.swift":
                "shouldDisableSimilarChannels?(context.account.peerId)",
        }
        for path, token in expected.items():
            self.assertIn(token, source(path), path)

    def test_notification_delay_uses_message_account_or_primary_background_snapshot(self) -> None:
        self.assert_hook("shouldDisableNotificationDelay", "disableNotificationDelay")
        notifications = source(
            "submodules/TelegramUI/Sources/SharedNotificationManager.swift"
        )
        self.assertIn(
            "shouldDisableNotificationDelay?(account.peerId)", notifications
        )
        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        background = swift_block(app_delegate, "private func addBackgroundDownloadTask()")
        self.assertIn(
            "grvmAccountFeatureRegistry?.primaryService()?.settingsSnapshot().disableNotificationDelay",
            background,
        )
        self.assertNotIn("shouldDisableNotificationDelay?", background)

    def test_zalgo_seconds_and_dialog_id_keep_exact_account_consumers(self) -> None:
        self.assert_hook("shouldFilterZalgo", "filterZalgo")
        self.assert_hook("shouldShowSeconds", "showSecondsInMessages")
        self.assert_hook("shouldShowDialogID", "showDialogId")
        self.assert_hook("peerIdDisplayMode", "showDialogId")
        expected = {
            "submodules/TelegramUI/Components/Chat/ChatMessageTextBubbleContentNode/Sources/ChatMessageTextBubbleContentNode.swift":
                "shouldFilterZalgo?(item.context.account.peerId)",
            "submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/StringForMessageTimestampStatus.swift":
                "shouldShowSeconds?(accountPeerId)",
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift":
                "peerIdDisplayMode?(context.account.peerId)",
        }
        for path, token in expected.items():
            self.assertIn(token, source(path), path)

    def test_send_confirmations_keep_chat_account_consumers(self) -> None:
        self.assert_hook("shouldConfirmStickers", "confirmSendSticker")
        self.assert_hook("shouldConfirmGIF", "confirmSendGIF")
        self.assert_hook("shouldConfirmVoice", "confirmSendVoice")
        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        media = source(
            "submodules/TelegramUI/Sources/Chat/ChatControllerMediaRecording.swift"
        )
        self.assertIn(
            "shouldConfirmStickers?(strongSelf.context.account.peerId)", chat
        )
        self.assertIn("shouldConfirmGIF?(strongSelf.context.account.peerId)", chat)
        self.assertIn("shouldConfirmVoice?(self.context.account.peerId)", media)

    def test_sticker_and_gif_confirmation_bypasses_are_one_shot(self) -> None:
        chat = source("submodules/TelegramUI/Sources/ChatController.swift")
        cases = (
            (
                "sendSticker: {",
                "bypassNextStickerConfirmation",
                "shouldConfirmStickers",
                "controllerInteraction?.sendSticker(",
            ),
            (
                "sendGif: {",
                "bypassNextGIFConfirmation",
                "shouldConfirmGIF",
                "controllerInteraction?.sendGif(",
            ),
        )
        for signature, flag, hook, recursive_send in cases:
            with self.subTest(hook=hook):
                self.assertIn(f"private var {flag} = false", chat)
                send = swift_block(chat, signature)
                read_bypass = f"let bypassConfirmation = strongSelf.{flag}"
                clear_bypass = f"strongSelf.{flag} = false"
                gate = (
                    f"if !bypassConfirmation && AyuGramHooks.{hook}?"
                    "(strongSelf.context.account.peerId) == true"
                )
                self.assertIn(read_bypass, send)
                self.assertIn(clear_bypass, send)
                self.assertIn(gate, send)
                self.assertLess(send.index(read_bypass), send.index(clear_bypass))
                self.assertLess(send.index(clear_bypass), send.index(gate))

                ok_action = swift_block(
                    send, "TextAlertAction(type: .defaultAction"
                )
                for token in (
                    f"strongSelf.{flag} = true",
                    f"strongSelf.{flag} = false",
                    "defer {",
                    recursive_send,
                ):
                    self.assertIn(token, ok_action)
                self.assertLess(
                    ok_action.index(f"strongSelf.{flag} = true"),
                    ok_action.index("defer {"),
                )
                self.assertLess(
                    ok_action.index("defer {"), ok_action.index(recursive_send)
                )
                self.assertNotIn("async", ok_action)

    def test_android_spoof_remains_an_independent_account_toggle(self) -> None:
        self.assert_hook("shouldSpoofWebviewAsAndroid", "spoofWebviewAsAndroid")
        webview = source("submodules/WebUI/Sources/WebAppWebView.swift")
        android = swift_block(
            webview, "if AyuGramHooks.shouldSpoofWebviewAsAndroid?(account.peerId)"
        )
        self.assertIn("customUserAgent", android)
        self.assertNotIn("shouldIncreaseWebviewHeight", android)
        self.assertNotIn("shouldIncreaseWebviewWidth", android)


if __name__ == "__main__":
    unittest.main()
