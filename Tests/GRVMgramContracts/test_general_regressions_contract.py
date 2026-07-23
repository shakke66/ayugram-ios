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
            "submodules/ChatListUI/Sources/ChatListController.swift":
                "shouldHideStories?(context.account.peerId)",
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoData.swift":
                "shouldDisableSimilarChannels?(context.account.peerId)",
        }
        for path, token in expected.items():
            self.assertIn(token, source(path), path)

    def test_hide_stories_reactively_removes_the_complete_story_layout(self) -> None:
        controller = source(
            "submodules/ChatListUI/Sources/ChatListController.swift"
        )
        node = source(
            "submodules/ChatListUI/Sources/ChatListControllerNode.swift"
        )
        header = source(
            "submodules/TelegramUI/Components/ChatListHeaderComponent/Sources/ChatListHeaderComponent.swift"
        )

        self.assertIn(
            "var effectiveStorySubscriptions: EngineStorySubscriptions?",
            controller,
        )
        effective_subscriptions = swift_block(
            controller,
            "var effectiveStorySubscriptions: EngineStorySubscriptions?",
        )
        self.assertIn("if self.hideStories", effective_subscriptions)
        self.assertIn("return nil", effective_subscriptions)
        self.assertIn("return self.orderedStorySubscriptions", effective_subscriptions)

        self.assertIn("self.hideStoriesDisposable =", controller)
        settings_start = controller.index("self.hideStoriesDisposable =")
        settings_end = controller.index("self.updateNavigationMetadata()", settings_start)
        settings_subscription = controller[settings_start:settings_end]
        for token in (
            "grvmSettings(",
            "accountId: self.context.account.peerId",
            "map { $0.hideStories }",
            "distinctUntilChanged",
            "deliverOnMainQueue",
            "self.hideStories = hideStories",
            "self.requestLayout(transition:",
        ):
            self.assertIn(token, settings_subscription)
        settings_handler = swift_block(
            settings_subscription,
            ".startStrict(next: { [weak self] hideStories in",
        )
        hide_branch = swift_block(settings_handler, "if hideStories")
        self.assertIn("scrollToTopIfStoriesAreExpanded()", hide_branch)
        self.assertNotIn("requestLayout", hide_branch)
        hide_branch_end = settings_handler.index(hide_branch) + len(hide_branch)
        self.assertIn(
            "self.requestLayout(transition:",
            settings_handler[hide_branch_end:],
        )
        self.assertIn("self.hideStoriesDisposable?.dispose()", controller)

        expansion_blocks = {
            "tracking": swift_block(
                node,
                "itemNode.listNode.contentOffsetChanged =",
            ),
            "dragging": swift_block(
                node,
                "itemNode.listNode.didBeginInteractiveDragging =",
            ),
            "hidden_items": swift_block(
                node,
                "self.mainContainerNode.canExpandHiddenItems =",
            ),
            "navigation": swift_block(node, "private func updateNavigationBar"),
            "scroll_to_stories": swift_block(
                node,
                "func scrollToStories(animated: Bool)",
            ),
            "overscroll": swift_block(
                node,
                "private func contentOffsetChanged(offset:",
            ),
        }
        for name, block in expansion_blocks.items():
            with self.subTest(expansion_gate=name):
                self.assertIn("controller.effectiveStorySubscriptions", block)
                self.assertNotIn("orderedStorySubscriptions", block)

        navigation_update = swift_block(node, "private func updateNavigationBar")
        self.assertIn("self.controller?.hideStories == true", navigation_update)
        self.assertIn("effectiveStorySubscriptions = nil", navigation_update)
        self.assertIn(
            "storySubscriptions: effectiveStorySubscriptions",
            navigation_update,
        )

        self.assertIn("func resetStoryExpansion()", node)
        reset_expansion = swift_block(node, "func resetStoryExpansion()")
        self.assertIn("startedScrollingAtUpperBound = false", reset_expansion)
        self.assertIn("self.tempTopInset = 0.0", reset_expansion)
        collapse = swift_block(node, "func scrollToTopIfStoriesAreExpanded()")
        self.assertIn("self.mainContainerNode.resetStoryExpansion()", collapse)
        self.assertIn("allowAvatarsExpansion: false", collapse)
        self.assertIn("forceUpdate: true", collapse)
        conditional_scroll = swift_block(collapse, "if let contentOffset")
        self.assertNotIn("resetStoryExpansion", conditional_scroll)

        header_update = swift_block(
            header,
            "func update(component: ChatListHeaderComponent",
        )
        self.assertNotIn("shouldHideStories", header_update)
        self.assertIn(
            "else if let storyPeerList = self.storyPeerList",
            header_update,
        )
        self.assertIn("self.storyPeerList = nil", header_update)
        self.assertIn("storyPeerList.view?.removeFromSuperview()", header_update)

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

if __name__ == "__main__":
    unittest.main()
