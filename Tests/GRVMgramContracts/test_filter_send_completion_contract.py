import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOAD_DISPLAY = (
    "submodules/TelegramUI/Sources/Chat/ChatControllerLoadDisplayNode.swift"
)
CONTROLLER = "submodules/TelegramUI/Sources/ChatController.swift"
CONTROLLER_NODE = "submodules/TelegramUI/Sources/ChatControllerNode.swift"


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


def function_window(text: str, signature: str, size: int = 30_000) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"Missing Swift function: {signature}")
    return text[start : start + size]


class FilterSendCompletionContractTests(unittest.TestCase):
    def test_send_action_is_shared_one_shot_with_stock_transition(self) -> None:
        load_display = source(LOAD_DISPLAY)
        setup = swift_block(
            load_display, "self.chatDisplayNode.setupSendActionOnViewUpdate ="
        )
        for token in (
            "var pendingAction: (() -> Void)? = f",
            "let sendActionOnViewUpdate: () -> Void = {",
            "let action = pendingAction",
            "pendingAction = nil",
            "action?()",
            "self.layoutActionOnViewTransitionAction = sendActionOnViewUpdate",
            "sendActionOnViewUpdate()",
        ):
            self.assertIn(token, setup)
        for stock_transition_token in (
            "strongSelf.chatDisplayNode.containerLayoutUpdated(",
            "mappedTransition = (ChatHistoryListViewTransition(",
            "return mappedTransition",
        ):
            self.assertIn(stock_transition_token, setup)

        consume = swift_block(load_display, "func consumeSendActionOnViewUpdate()")
        self.assertIn(
            "guard let action = self.layoutActionOnViewTransitionAction else",
            consume,
        )
        self.assertLess(
            consume.index("self.layoutActionOnViewTransitionAction = nil"),
            consume.index("action()"),
        )
        self.assertNotIn("historyNode.layoutActionOnViewTransition = nil", consume)

    def test_each_enqueue_route_consumes_only_after_a_real_message_id(self) -> None:
        load_display = source(LOAD_DISPLAY)
        signal_start = load_display.index("let _ = (signal")
        signal_end = load_display.index("donateSendMessageIntent", signal_start)
        composer_enqueue = load_display[signal_start:signal_end]
        self.assertIn("startStandalone(next: { messageIds in", composer_enqueue)
        self.assertIn(
            "messageIds.contains(where: { $0 != nil })", composer_enqueue
        )
        self.assertIn(
            "strongSelf.consumeSendActionOnViewUpdate()", composer_enqueue
        )

        controller = source(CONTROLLER)
        general_enqueue = swift_block(controller, "func sendMessages(_ messages:")
        self.assertIn("startStandalone(next: { [weak self] messageIds in", general_enqueue)
        self.assertIn(
            "messageIds.contains(where: { $0 != nil })", general_enqueue
        )
        self.assertIn(
            "strongSelf.consumeSendActionOnViewUpdate()", general_enqueue
        )

    def test_text_and_media_caption_paths_register_the_same_completion_action(self) -> None:
        node = source(CONTROLLER_NODE)
        text_send = function_window(node, "func sendCurrentMessage(")
        self.assertIn("self.setupSendActionOnViewUpdate(", text_send)
        self.assertIn("self.sendMessages(messages,", text_send)

        controller = source(CONTROLLER)
        media_send = function_window(controller, "func enqueueMediaMessages(")
        self.assertIn(
            "strongSelf.chatDisplayNode.setupSendActionOnViewUpdate(", media_send
        )
        self.assertIn(
            "strongSelf.sendMessages(messages.map", media_send
        )


if __name__ == "__main__":
    unittest.main()
