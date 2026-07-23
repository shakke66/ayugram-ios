import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GALLERY = ROOT / "submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift"


def setup_item(source: str) -> str:
    start = source.index("    func setupItem(_ item: UniversalVideoGalleryItem) {")
    end = source.index("    private func updateDisplayPlaceholder()", start)
    return source[start:end]


class MediaControlsContractTests(unittest.TestCase):
    def test_animated_media_keeps_gallery_controls_and_excludes_pip(self) -> None:
        setup = setup_item(GALLERY.read_text(encoding="utf-8"))

        self.assertNotIn("if isAnimated || disablePlayerControls", setup)
        self.assertEqual(2, setup.count("if disablePlayerControls {"))
        self.assertIn(
            "if forceEnablePiP || (!isAnimated && !disablePlayerControls && !disablePictureInPicture)",
            setup,
        )
        self.assertIn("actionAtEnd: isAnimated ? .loop : strongSelf.actionAtEnd", setup)

    def test_existing_seek_routes_remain_intact(self) -> None:
        routes = {
            "submodules/TelegramUI/Components/Chat/ChatMessageInteractiveFileNode/Sources/ChatMessageInteractiveFileNode.swift": "playlistControl(.seek(timestamp), type: type)",
            "submodules/TelegramUI/Components/Chat/ChatMessageInteractiveInstantVideoNode/Sources/ChatMessageInteractiveInstantVideoNode.swift": "self.videoNode?.seek(position * duration)",
            "submodules/TelegramUI/Components/Chat/InstantVideoRadialStatusNode/Sources/InstantVideoRadialStatusNode.swift": "self.seekTo?(min(0.99, fraction), true)",
            "submodules/GalleryUI/Sources/ChatVideoGalleryItemScrubberView.swift": "self?.seek(timestamp)",
        }

        for path, token in routes.items():
            self.assertIn(token, (ROOT / path).read_text(encoding="utf-8"))

    def test_muted_gif_pause_state_reaches_the_playback_controls(self) -> None:
        setup = setup_item(GALLERY.read_text(encoding="utf-8"))

        self.assertIn("isAnimated = content.fileReference.media.isAnimated", setup)
        self.assertEqual(2, setup.count("if !content.enableSound && !isAnimated {"))
        self.assertNotIn(
            "if !content.enableSound {\n                                        isPaused = false",
            setup,
        )
        self.assertIn("footerContent = .playback(paused: true, seekable: seekable)", setup)


if __name__ == "__main__":
    unittest.main()
