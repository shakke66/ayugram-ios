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


MEDIA = "submodules/TelegramUI/Sources/Chat/ChatControllerMediaRecording.swift"
STORY = (
    "submodules/TelegramUI/Components/Stories/StoryContainerScreen/"
    "Sources/StoryContainerScreen.swift"
)


class GhostGeneralFinalReviewContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.media = source(MEDIA)
        cls.story = source(STORY)

    def test_saved_audio_routes_through_shared_send_policy(self) -> None:
        confirmed = swift_block(self.media, "private func sendMediaRecordingConfirmed(")
        audio = confirmed[
            confirmed.index("case let .audio(audio):") : confirmed.index("case .video:")
        ]
        self.assertIn("self.sendMessages(transformedMessages)", audio)
        self.assertNotIn("enqueueMessages(account:", audio)
        self.assertNotIn("donateSendMessageIntent(", audio)

    def test_voice_confirmation_is_after_audio_kind_detection_and_excludes_video(self) -> None:
        send = swift_block(self.media, "func sendMediaRecording(")
        self.assertIn("switch recordedMediaPreview", send)
        kind_switch = send.index("switch recordedMediaPreview")
        voice_gate = send.index("AyuGramHooks.shouldConfirmVoice?")
        self.assertGreater(voice_gate, kind_switch)
        audio_case = send[send.index("case .audio:") : send.index("case .video:")]
        self.assertIn("AyuGramHooks.shouldConfirmVoice?", audio_case)
        video_case = send[send.index("case .video:") :]
        self.assertNotIn("AyuGramHooks.shouldConfirmVoice?", video_case)

    def test_immediate_audio_release_preserves_draft_and_view_once(self) -> None:
        dismiss = swift_block(self.media, "func dismissMediaRecorder(")
        audio = swift_block(dismiss, "if let audioRecorderValue = self.audioRecorderValue {")
        self.assertRegex(
            audio,
            r"if case let \.send\(viewOnce\) = updatedAction[\s\S]+?updatedAction = \.preview",
        )
        self.assertIn("withUpdatedMediaDraftState(.audio(", audio)
        self.assertIn(
            "sendRecordedMedia(false, sendImmediatelyViewOnce)", audio
        )
        self.assertNotIn("strongSelf.sendMessages([.message", audio)

    def test_story_ghost_wait_is_bounded_and_finishes_on_timeout(self) -> None:
        wait = swift_block(self.story, "private func grvmWaitForStoryGhostSnapshot(id:")
        self.assertRegex(wait, r"var remaining(?:Checks|Attempts)\s*=\s*\d+")
        self.assertRegex(wait, r"remaining(?:Checks|Attempts)\s*-=?\s*1")
        self.assertRegex(wait, r"remaining(?:Checks|Attempts)\s*<=?\s*0")
        self.assertIn("AyuGramHooks.shouldSuppressStoryRead?(accountPeerId)", wait)
        self.assertIn("grvmFinishStoryGhostChoice(id: id)", wait)
        self.assertNotRegex(
            wait,
            r"guard\s+AyuGramHooks\.shouldSuppressStoryRead\?\(accountPeerId\)\s*==\s*true\s*else\s*\{\s*return\s*\}",
        )


if __name__ == "__main__":
    unittest.main()
