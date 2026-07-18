from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


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


class TimestampNotificationContractTests(unittest.TestCase):
    def test_formatter_seconds_are_opt_in_and_propagate_every_time_branch(self) -> None:
        medium = source("submodules/TelegramStringFormatting/Sources/DateFormat.swift")
        presence = source("submodules/TelegramStringFormatting/Sources/PresenceStrings.swift")

        medium_block = swift_block(medium, "public func stringForMediumDate(")
        self.assertIn("withSeconds: Bool = false", medium_block)
        self.assertIn("seconds: withSeconds ? Int32(timeinfo.tm_sec) : nil", medium_block)

        helper = swift_block(presence, "private func humanReadableStringForTimestamp(")
        self.assertIn("seconds: Int32? = nil", helper)
        self.assertEqual(3, helper.count("seconds: seconds"))

        public = swift_block(presence, "public func humanReadableStringForTimestamp(")
        self.assertIn("withSeconds: Bool = false", public)
        self.assertIn("seconds: withSeconds ? Int32(timeinfo.tm_sec) : nil", public)
        self.assertIn("withSeconds: withSeconds", public)
        self.assertEqual(2, public.count("stringForMediumDate("))
        self.assertEqual(2, public.count("withSeconds: withSeconds"))

    def test_reactions_keep_exact_timestamps_and_request_seconds(self) -> None:
        reactions = source("submodules/TelegramCore/Sources/State/MessageReactions.swift")
        reaction_ui = source(
            "submodules/Components/ReactionListContextMenuContent/Sources/"
            "ReactionListContextMenuContent.swift"
        )
        build = source("submodules/Components/ReactionListContextMenuContent/BUILD")

        self.assertIn("timestamp: recentPeer.timestamp ?? readStats?.readTimestamps[peer.id]", reactions)
        self.assertIn("timestamp: date, timestampIsReaction: true", reactions)
        self.assertIn("if let timestamp = item.timestamp", reaction_ui)
        self.assertIn("timestamp: timestamp, alwaysShowTime: true", reaction_ui)
        self.assertIn("withSeconds: true", reaction_ui)
        self.assertIn("//submodules/TelegramStringFormatting:TelegramStringFormatting", build)

    def test_service_pill_is_exact_account_scoped_separate_and_reusable(self) -> None:
        action = source(
            "submodules/TelegramUI/Components/Chat/"
            "ChatMessageActionBubbleContentNode/Sources/"
            "ChatMessageActionBubbleContentNode.swift"
        )

        for token in (
            "private var timeNode: TextNode?",
            "private let timeBackgroundNode: ASDisplayNode",
            "AyuGramHooks.shouldShowSeconds?(item.context.account.peerId) == true",
            "stringForMessageTimestamp(timestamp: item.message.timestamp, dateTimeFormat: item.presentationData.dateTimeFormat, withSeconds: true)",
            "image == nil && suggestedPost == nil",
            "timeBackgroundNode.isHidden = !showTime",
            "timeNode?.isHidden = !showTime",
            "backgroundSize.height += timeSize.height",
            "backgroundSize.width = max(backgroundSize.width, timeSize.width)",
            "timeFrame = CGRect",
            "y: contentOuterInsets.top + actionBodySize.height",
        ):
            with self.subTest(token=token):
                self.assertIn(token, action)

        tap = swift_block(action, "override public func tapActionAtPoint(")
        self.assertIn("timeBackgroundNode.frame.contains(point)", tap)
        self.assertIn("return ChatMessageBubbleContentTapAction(content: .openMessage)", tap)

    def test_stock_top_notification_position_and_animation_remain_intact(self) -> None:
        controller = source("submodules/TelegramUI/Sources/NotificationContainerController.swift")
        container = source("submodules/TelegramUI/Sources/NotificationContainerControllerNode.swift")
        item = source("submodules/TelegramUI/Sources/NotificationItemContainerNode.swift")

        self.assertIn("self.statusBar.statusBarStyle = .Ignore", controller)
        self.assertIn("contentInsets.top = statusBarHeight + 6.0", item)
        self.assertIn("contentInsets.top += 34.0", item)
        self.assertIn("func animateIn()", item)
        self.assertIn("y: -self.backgroundView.frame.maxY", item)
        self.assertIn("func animateOut", item)
        self.assertIn("containerNode.animateIn()", container)
        self.assertIn("topItemNode.animateOut", container)


if __name__ == "__main__":
    unittest.main()
