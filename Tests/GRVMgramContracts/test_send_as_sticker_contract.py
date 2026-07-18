import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PICKER = ROOT / "submodules/MediaPickerUI/Sources/MediaPickerScreen.swift"
ATTACH = ROOT / "submodules/TelegramUI/Sources/ChatControllerOpenAttachmentMenu.swift"
PASTE = ROOT / "submodules/TelegramUI/Sources/Chat/ChatControllerPaste.swift"
PROTOCOLS = ROOT / "submodules/AccountContext/Sources/AccountContext.swift"


class SendAsStickerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.picker = PICKER.read_text(encoding="utf-8")
        cls.attach = ATTACH.read_text(encoding="utf-8")
        cls.paste = PASTE.read_text(encoding="utf-8")

    def test_bridge_is_concrete_and_propagated_to_child_picker(self) -> None:
        self.assertEqual(
            self.picker.count("public var sendAsSticker: ((UIImage) -> Void)?"), 1
        )
        protocol_source = PROTOCOLS.read_text(encoding="utf-8")
        protocol_body = re.search(
            r"public protocol MediaPickerScreen: ViewController \{(?P<body>.*?)\n\}",
            protocol_source,
            re.DOTALL,
        )
        self.assertIsNotNone(protocol_body)
        self.assertNotIn("sendAsSticker", protocol_body.group("body"))
        self.assertIn("mediaPicker.sendAsSticker = strongSelf.sendAsSticker", self.picker)

    def test_action_requires_exactly_one_eligible_static_image(self) -> None:
        for token in (
            "selectedItems.count == 1",
            "sendAsSticker != nil",
            "price == nil",
            "!hasSpoilers",
            "TGMediaAssetPhotoType",
            "TGMediaAssetGifType",
            "TGCameraCapturedVideo",
            "adjustments.sendAsGif",
            "TGMediaAssetSubtypePhotoLive",
            "TGMediaLivePhotoModeOff",
            "image.images == nil",
        ):
            self.assertIn(token, self.picker)
        self.assertIn(
            "editingContext.isForceLivePhotoEnabled()",
            self._static_eligibility_method(),
        )

    def test_extraction_uses_real_legacy_apis_and_guarded_fallbacks(self) -> None:
        for token in (
            "editingContext.imageSignal(for: selectedItem, withUpdates: false)",
            "TGMediaAssetImageSignals.image(for: asset, imageType: TGMediaAssetImageTypeFullSize, size: .zero)",
            "capturedPhoto.existingImage",
            "selectedItem as? UIImage",
            "sendAsStickerRequestDisposable",
            "ActionDisposable",
            "deliver(on: SQueue.main())",
            "image.images == nil",
        ):
            self.assertIn(token, self.picker)

    def test_success_dismisses_before_callback_and_failure_does_not_send(self) -> None:
        self.assertRegex(
            self.picker,
            r"self\.dismiss\(completion: \{\s*sendAsSticker\(image\)",
        )
        self.assertIn("presentSendAsStickerError", self.picker)
        self.assertNotIn("controllerNode.send(asFile: false", self._sticker_methods())

    def test_chat_wires_once_to_existing_sticker_pipeline(self) -> None:
        self.assertEqual(self.attach.count("controller.sendAsSticker ="), 1)
        self.assertEqual(
            self.attach.count("enqueueStickerImage(image, isMemoji: false)"), 1
        )

    def test_reuses_single_existing_webp_pipeline_without_duplication(self) -> None:
        self.assertIn(
            "func enqueueStickerImage(_ image: UIImage, isMemoji: Bool)", self.paste
        )
        self.assertEqual(self.paste.count("convertToWebP(image:"), 1)
        for source in (self.picker, self.attach):
            self.assertNotIn("convertToWebP", source)
            self.assertNotIn("LocalFileMediaResource", source)

    def _sticker_methods(self) -> str:
        start = self.picker.find("private func sendSelectedImageAsSticker")
        end = self.picker.find("fileprivate func defaultTransitionView", start)
        self.assertGreaterEqual(start, 0)
        self.assertGreater(end, start)
        return self.picker[start:end]

    def _static_eligibility_method(self) -> str:
        start = self.picker.find("private func isStaticStickerItem")
        end = self.picker.find("private func sendSelectedImageAsSticker", start)
        self.assertGreaterEqual(start, 0)
        self.assertGreater(end, start)
        return self.picker[start:end]


if __name__ == "__main__":
    unittest.main()
