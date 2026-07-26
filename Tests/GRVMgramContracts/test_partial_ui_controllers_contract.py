from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.exists():
        raise AssertionError(f"Missing production source: {relative_path}")
    return path.read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start == -1:
        raise AssertionError(f"Missing Swift block: {signature}")
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


class PartialUIControllerContractTests(unittest.TestCase):
    def test_app_icon_picker_localizes_real_ids_and_saves_after_native_success(self) -> None:
        text = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramAppIconPicker.swift"
        )
        for identifier, key in {
            "BlackFilledIcon": "appIconBlackFilled",
            "BlueFilledIcon": "appIconBlueFilled",
            "WhiteFilledIcon": "appIconWhiteFilled",
            "BlackIcon": "appIconBlack",
            "BlueIcon": "appIconBlue",
            "BlackClassicIcon": "appIconBlackClassic",
            "BlueClassicIcon": "appIconBlueClassic",
            "New1": "appIconNew1",
            "New2": "appIconNew2",
            "Premium": "appIconPremium",
            "PremiumBlack": "appIconPremiumBlack",
            "PremiumTurbo": "appIconPremiumTurbo",
        }.items():
            with self.subTest(identifier=identifier):
                self.assertIn(f'"{identifier}": .{key}', text)

        display_title = swift_block(
            text, "public func grvmAppIconDisplayTitle("
        )
        self.assertIn("grvmAppIconTitleKeys[identifier]", display_title)
        self.assertNotIn("?? identifier", display_title)

        picker = swift_block(text, "public func ayuGramAppIconPicker(")
        for token in (
            "getAvailableAlternateIcons()",
            "getAlternateIconName()",
            "requestSetAlternateIconName(icon.isDefault ? nil : icon.name)",
            'let storedIdentifier = icon.isDefault ? "default" : icon.name',
            "guard success else",
            "onSelect(storedIdentifier)",
        ):
            self.assertIn(token, picker)
        self.assertLess(
            picker.index("guard success else"),
            picker.index("onSelect(storedIdentifier)"),
        )

    def test_code_font_controller_lists_every_font_and_keeps_live_footer_preview(self) -> None:
        text = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramCodeFontController.swift"
        )
        strings = source(
            "submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift"
        )
        self.assertIn(
            'case appearanceCodeFontPreview = "GRVMgram.Appearance.CodeFont.Preview"',
            strings,
        )
        controller = swift_block(text, "public func ayuGramCodeFontController(")
        for token in (
            "currentFontName: String",
            "onSelect: @escaping (String) -> Void",
            "UIFont.familyNames.sorted()",
            "UIFont.fontNames(forFamilyName: familyName)",
            "Set(fontNames)",
            'let availableFontNames = [""] +',
            "GRVMCodeFontPreviewFooterItem(",
            "previewText: strings[.appearanceCodeFontPreview]",
            "footerItem: previewItem",
        ):
            self.assertIn(token, controller)

        preview = swift_block(text, "private func updateItem()")
        self.assertIn("UIFont(name: self.item.fontName", preview)
        self.assertIn("?? Font.monospace", preview)
        self.assertIn("self.textNode.attributedText", preview)
        self.assertIn("self.item.previewText", preview)

    def test_integer_sliders_use_exact_ranges_step_and_live_preview(self) -> None:
        build = source("submodules/AyuGramSettingsUI/BUILD")
        self.assertIn('"//submodules/AsyncDisplayKit:AsyncDisplayKit"', build)
        slider = source(
            "submodules/AyuGramSettingsUI/Sources/GRVMIntegerSliderItem.swift"
        )
        for token in (
            "private var sliderView: UISlider?",
            "sliderView.minimumValue = Float(item.range.lowerBound)",
            "sliderView.maximumValue = Float(item.range.upperBound)",
            "sliderView.isContinuous = true",
            "sliderView.value.rounded()",
            "item.range.lowerBound",
            "item.range.upperBound",
            "self.item?.updated(value)",
            "previewImage: UIImage?",
            "valueNode.attributedText",
        ):
            self.assertIn(token, slider)

        controllers = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramIntegerValueControllers.swift"
        )
        avatar = swift_block(
            controllers, "public func ayuGramAvatarCornersController("
        )
        for token in (
            "currentValue: Int32",
            "onSelect: @escaping (Int32) -> Void",
            "range: 0 ... 50",
            "showsAvatarPreview: true",
        ):
            self.assertIn(token, avatar)
        self.assertIn("private func grvmAvatarPreviewImage(", controllers)

        recent = swift_block(
            controllers, "public func ayuGramRecentStickersCountController("
        )
        for token in (
            "currentValue: Int32",
            "onSelect: @escaping (Int32) -> Void",
            "range: 1 ... 200",
        ):
            self.assertIn(token, recent)

    def test_integer_slider_replays_latest_configuration_after_view_load(self) -> None:
        slider = source(
            "submodules/AyuGramSettingsUI/Sources/GRVMIntegerSliderItem.swift"
        )
        self.assertIn("private var sliderFrame: CGRect?", slider)

        did_load = swift_block(slider, "override func didLoad()")
        self.assertIn("self.updateSliderConfiguration()", did_load)

        layout = swift_block(slider, "func asyncLayout()")
        self.assertIn("self.sliderFrame = CGRect(", layout)
        self.assertIn("self.updateSliderConfiguration()", layout)
        self.assertNotIn("if let sliderView = self.sliderView", layout)

        configuration = swift_block(
            slider, "private func updateSliderConfiguration()"
        )
        for token in (
            "guard let sliderView = self.sliderView",
            "let item = self.item",
            "let sliderFrame = self.sliderFrame",
            "let value = min(item.range.upperBound, max(item.range.lowerBound, item.value))",
            "sliderView.minimumValue = Float(item.range.lowerBound)",
            "sliderView.maximumValue = Float(item.range.upperBound)",
            "sliderView.setValue(Float(value), animated: false)",
            'sliderView.accessibilityValue = "\\(value)"',
            "sliderView.frame = sliderFrame",
        ):
            with self.subTest(token=token):
                self.assertIn(token, configuration)

    def test_channel_bottom_selector_is_discuss_then_hidden_and_normalizes_legacy(self) -> None:
        text = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramChannelBottomButtonController.swift"
        )
        normalizer = swift_block(
            text, "public func grvmNormalizedChannelBottomButtonValue("
        )
        self.assertIn("return value == 0 ? 0 : 1", normalizer)

        entries = swift_block(text, "private func grvmChannelBottomButtonEntries(")
        self.assertIn(".channelsBottomDiscuss", entries)
        self.assertIn(".channelsBottomHide", entries)
        self.assertLess(
            entries.index(".channelsBottomDiscuss"),
            entries.index(".channelsBottomHide"),
        )
        self.assertRegex(entries, re.compile(r"value:\s*1.*value:\s*0", re.DOTALL))

        controller = swift_block(
            text, "public func ayuGramChannelBottomButtonController("
        )
        self.assertIn("currentValue: Int32", controller)
        self.assertIn("onSelect: @escaping (Int32) -> Void", controller)
        self.assertNotIn("channelsBottomMute", text)


if __name__ == "__main__":
    unittest.main()
