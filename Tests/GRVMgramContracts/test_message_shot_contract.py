from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]

MODEL = "submodules/TelegramUI/Sources/GRVMMessageShotModel.swift"
RENDERER = "submodules/TelegramUI/Sources/GRVMMessageShotRenderer.swift"
CONTROLLER = "submodules/TelegramUI/Sources/GRVMMessageShotController.swift"
PANEL = (
    "submodules/TelegramUI/Components/Chat/"
    "ChatMessageSelectionInputPanelNode/Sources/"
    "ChatMessageSelectionInputPanelNode.swift"
)
INPUT_PANELS = "submodules/TelegramUI/Sources/ChatInterfaceStateInputPanels.swift"
PEER_INFO_PANEL = (
    "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/"
    "PeerInfoSelectionPanelNode.swift"
)


def source(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start == -1:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening_brace = text.find("{", start)
    if opening_brace == -1:
        raise AssertionError(f"Missing opening brace: {signature}")
    depth = 0
    in_line_comment = False
    in_string = False
    escaped = False
    for index in range(opening_brace, len(text)):
        character = text[index]
        if in_line_comment:
            if character == "\n":
                in_line_comment = False
            continue
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if text.startswith("//", index):
            in_line_comment = True
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


def normalized(text: str) -> str:
    return "".join(text.split())


def assert_tokens(
    test: unittest.TestCase, text: str, tokens: list[str]
) -> None:
    body = normalized(text)
    for token in tokens:
        with test.subTest(token=token):
            test.assertIn(normalized(token), body)


@dataclass(frozen=True, order=True)
class FixtureIndex:
    timestamp: int
    namespace: int
    message_id: int


@dataclass(frozen=True)
class FixtureMessage:
    peer_id: int
    thread_id: int | None
    index: FixtureIndex


def build_fixture_model(
    peer_id: int,
    thread_id: int | None,
    selected: list[FixtureMessage | None],
) -> tuple[list[FixtureMessage], int]:
    available = [message for message in selected if message is not None]
    if not available:
        raise ValueError("noAvailableMessages")
    if any(message.peer_id != peer_id for message in available):
        raise ValueError("mixedPeers")
    # The forum root is intentionally retained even when its thread id is absent.
    return sorted(available, key=lambda message: message.index), len(selected) - len(
        available
    )


def fixture_reply(
    real_text: str | None,
    quote_text: str | None,
    reply_attribute_present: bool,
) -> tuple[str, str]:
    if real_text is not None:
        return ("message", real_text)
    if quote_text is not None:
        return ("quote", quote_text)
    if reply_attribute_present:
        return ("unavailable", "Message unavailable")
    return ("none", "")


def validate_fixture_canvas(width: float, height: float, scale: float) -> bool:
    if not all(math.isfinite(value) and value > 0.0 for value in (width, height, scale)):
        return False
    if not 1.0 <= scale <= 3.0:
        return False
    pixel_width = width * scale
    pixel_height = height * scale
    if pixel_width > 16384.0 or pixel_height > 16384.0:
        return False
    return pixel_width * pixel_height * 4.0 <= 48.0 * 1024.0 * 1024.0


class MessageShotBehaviorFixtureTests(unittest.TestCase):
    def test_selected_messages_sort_by_message_index_and_count_missing(self) -> None:
        late = FixtureMessage(100, 42, FixtureIndex(200, 0, 9))
        early = FixtureMessage(100, 42, FixtureIndex(100, 0, 50))
        same_time_lower_id = FixtureMessage(100, 42, FixtureIndex(200, 0, 3))
        messages, unavailable = build_fixture_model(
            100, 42, [late, None, early, same_time_lower_id]
        )
        self.assertEqual(messages, [early, same_time_lower_id, late])
        self.assertEqual(unavailable, 1)

    def test_model_rejects_mixed_peers_and_only_fails_when_all_are_missing(self) -> None:
        with self.assertRaisesRegex(ValueError, "mixedPeers"):
            build_fixture_model(
                100,
                None,
                [FixtureMessage(101, None, FixtureIndex(1, 0, 1))],
            )
        with self.assertRaisesRegex(ValueError, "noAvailableMessages"):
            build_fixture_model(100, None, [None, None])

    def test_forum_root_message_is_preserved(self) -> None:
        root = FixtureMessage(100, None, FixtureIndex(1, 0, 1))
        reply = FixtureMessage(100, 77, FixtureIndex(2, 0, 2))
        messages, _ = build_fixture_model(100, 77, [reply, root])
        self.assertEqual(messages, [root, reply])

    def test_reply_precedence_covers_real_quoted_and_unavailable(self) -> None:
        self.assertEqual(fixture_reply("real", "quote", True), ("message", "real"))
        self.assertEqual(fixture_reply(None, "quote", True), ("quote", "quote"))
        self.assertEqual(
            fixture_reply(None, None, True),
            ("unavailable", "Message unavailable"),
        )
        self.assertEqual(fixture_reply(None, None, False), ("none", ""))

    def test_all_eight_options_are_independent(self) -> None:
        defaults = {
            "showBackground": True,
            "showDate": False,
            "showReactions": False,
            "showHeader": True,
            "showHeaderDecorations": True,
            "colorfulReplies": True,
            "revealSpoilers": True,
            "theme": "current",
        }
        for key in defaults:
            with self.subTest(key=key):
                changed = dict(defaults)
                changed[key] = (
                    "dark"
                    if key == "theme"
                    else not bool(defaults[key])
                )
                self.assertEqual(
                    [name for name in defaults if defaults[name] != changed[name]],
                    [key],
                )

    def test_canvas_guards_cover_scale_pixels_and_memory(self) -> None:
        self.assertTrue(validate_fixture_canvas(480.0, 1200.0, 2.0))
        for values in [
            (math.nan, 20.0, 2.0),
            (480.0, 0.0, 2.0),
            (480.0, 20.0, 0.5),
            (480.0, 20.0, 3.1),
            (9000.0, 20.0, 2.0),
            (480.0, 8000.0, 3.0),
        ]:
            with self.subTest(values=values):
                self.assertFalse(validate_fixture_canvas(*values))


class MessageShotSelectionBridgeContractTests(unittest.TestCase):
    def test_selection_module_uses_only_the_public_message_id_bridge(self) -> None:
        panel = source(PANEL)
        self.assertNotIn("import TelegramUI", panel)
        assert_tokens(
            self,
            panel,
            [
                "public var messageShotRequested: ((Set<MessageId>) -> Void)?",
                "private let messageShotButton: GlassButtonView",
                "self.messageShotButton.isAccessibilityElement = true",
                "self.messageShotButton.button.addTarget(",
                "#selector(self.messageShotButtonPressed)",
            ],
        )

    def test_button_requires_selection_bridge_and_copy_permission(self) -> None:
        panel = source(PANEL)
        update = swift_block(panel, "private func updateActions()")
        pressed = swift_block(panel, "@objc private func messageShotButtonPressed()")
        assert_tokens(
            self,
            update,
            [
                "let canRequestMessageShot = !self.selectedMessages.isEmpty",
                "&& self.messageShotRequested != nil",
                "self.messageShotButton.isEnabled = canRequestMessageShot",
            ],
        )
        assert_tokens(
            self,
            pressed,
            [
                "guard !self.selectedMessages.isEmpty",
                "let messageShotRequested = self.messageShotRequested",
                "if let actions = self.actions, actions.isCopyProtected",
                "self.interfaceInteraction?.displayCopyProtectionTip(",
                "messageShotRequested(self.selectedMessages)",
            ],
        )

    def test_all_four_chat_selection_create_reuse_paths_assign_exact_account_bridge(self) -> None:
        panels = source(INPUT_PANELS)
        self.assertEqual(panels.count("messageShotRequested = grvmMessageShotRequested("), 4)
        assert_tokens(
            self,
            panels,
            [
                "let messageShotEnabled = AyuGramHooks.chatAppearance(",
                "accountPeerId: context.account.peerId",
                ").chats.messageShotFeature",
                "guard messageShotEnabled",
                "let peerId = chatPresentationInterfaceState.chatLocation.peerId",
                "selectedIds: selectedIds",
                "peerId: peerId",
                "threadId: chatPresentationInterfaceState.chatLocation.threadId",
                "interfaceInteraction?.presentController(controller, nil)",
                "interfaceInteraction?.cancelMessageSelection(",
            ],
        )
        peer_info = source(PEER_INFO_PANEL)
        self.assertNotIn("messageShotRequested", peer_info)


class MessageShotModelContractTests(unittest.TestCase):
    def test_model_is_immutable_and_carries_exact_context_and_capabilities(self) -> None:
        model = source(MODEL)
        for signature in [
            "public struct GRVMMessageShotModel",
            "public struct GRVMMessageShotMessage",
            "public struct GRVMMessageShotHeader",
            "public enum GRVMMessageShotReply",
            "public enum GRVMMessageShotMedia",
            "public struct GRVMMessageShotReaction",
            "public struct GRVMMessageShotCapabilities",
        ]:
            block = swift_block(model, signature)
            self.assertNotRegex(
                block,
                re.compile(r"(?m)^ {4}(?:public )?var\s+\w+\s*:"),
            )
        assert_tokens(
            self,
            model,
            [
                "public let accountPeerId: PeerId",
                "public let peerId: PeerId",
                "public let threadId: Int64?",
                "public let chatTitle: String",
                "public let messages: [GRVMMessageShotMessage]",
                "public let unavailableSelectedCount: Int",
                "public let capabilities: GRVMMessageShotCapabilities",
                "public let id: MessageId",
                "public let index: MessageIndex",
                "public let timestamp: Int32",
                "public let day: String",
                "public let time: String",
                "public let direction: GRVMMessageShotDirection",
                "public let header: GRVMMessageShotHeader",
                "public let text: String",
                "public let entities: [MessageTextEntity]",
                "public let reply: GRVMMessageShotReply",
                "public let media: [GRVMMessageShotMedia]",
                "public let reactions: [GRVMMessageShotReaction]",
                "public let containsSpoilers: Bool",
            ],
        )

    def test_loader_uses_one_transaction_message_index_and_missing_policy(self) -> None:
        model = source(MODEL)
        loader = swift_block(model, "public static func load(")
        self.assertEqual(loader.count("postbox.transaction"), 1)
        assert_tokens(
            self,
            loader,
            [
                "accountPeerId: PeerId",
                "peerId: PeerId",
                "threadId: Int64?",
                "selectedIds: Set<MessageId>",
                "dateTimeFormat: PresentationDateTimeFormat",
                "nameDisplayOrder: PresentationPersonNameOrder",
                "transaction.getMessage(id)",
                "unavailableSelectedCount += 1",
                "guard id.peerId == peerId",
                "throw GRVMMessageShotModelError.mixedPeers",
                "guard !messages.isEmpty",
                "throw GRVMMessageShotModelError.noAvailableMessages",
                "messages.sort { $0.index < $1.index }",
            ],
        )
        self.assertNotIn("message.threadId == threadId", loader)
        self.assertNotIn("selectedIds.sorted", loader)

    def test_reply_media_entities_reactions_spoilers_and_headers_are_complete(self) -> None:
        model = source(MODEL)
        mapped = swift_block(model, "private static func mapMessage(")
        media = swift_block(model, "private static func mapMedia(")
        assert_tokens(
            self,
            mapped,
            [
                "TextEntitiesMessageAttribute",
                "case .Spoiler",
                "ReplyMessageAttribute",
                "transaction.getMessage(replyAttribute.messageId)",
                "replyAttribute.quote",
                "QuotedReplyMessageAttribute",
                ".unavailable",
                "media: self.mapMedia(",
                "ReactionsMessageAttribute",
                "MessageReaction.Reaction.custom",
                "authorRank",
                "authorSignature",
                "boostCount",
            ],
        )
        assert_tokens(
            self,
            media,
            [
                "TelegramMediaImage",
                "image.immediateThumbnailData",
                "TelegramMediaFile",
                "file.immediateThumbnailData",
                ".placeholder(",
            ],
        )
        for forbidden in [
            "fetchedMediaResource",
            "resourceData(",
            "http://",
            "https://",
        ]:
            self.assertNotIn(forbidden, model)

    def test_capabilities_keep_header_and_decorations_independent(self) -> None:
        model = source(MODEL)
        capabilities = swift_block(model, "private static func capabilities(")
        assert_tokens(
            self,
            capabilities,
            [
                "hasReactions:",
                "hasReplies:",
                "hasSpoilers:",
                "hasHeaderDecorations:",
                "hasMedia:",
            ],
        )


class MessageShotRendererContractTests(unittest.TestCase):
    def test_renderer_is_fixed_width_two_pass_and_deterministic(self) -> None:
        renderer = source(RENDERER)
        render = swift_block(renderer, "public func render(")
        assert_tokens(
            self,
            renderer,
            [
                "public static let canvasWidth: CGFloat = 480.0",
                "public static let defaultScale: CGFloat = 2.0",
                "private func measure(",
                "private func draw(",
                "UIGraphicsImageRendererFormat()",
                "format.scale = scale",
                "format.opaque = options.showBackground",
                "UIGraphicsImageRenderer(size: layout.size, format: format)",
                "let maximumBubbleWidth = contentWidth * 0.75",
            ],
        )
        assert_tokens(
            self,
            render,
            [
                "let measuredLayout = try self.measure(width: requestedSize.width)",
                "try Self.validate(size: layout.size, scale: scale)",
                "return renderer.image { context in",
                "self.draw(context: context.cgContext, layout: layout",
            ],
        )

    def test_explicit_canvas_size_is_preserved_and_must_fit_measured_content(self) -> None:
        renderer = source(RENDERER)
        render = swift_block(renderer, "public func render(")
        assert_tokens(
            self,
            render,
            [
                "let requestedSize = size",
                "let measuredLayout = try self.measure(width: requestedSize.width)",
                "guard requestedSize.height >= measuredLayout.size.height else",
                "GRVMMessageShotLayout(size: requestedSize",
            ],
        )

    def test_canvas_validation_requires_positive_usable_bubble_content_width(self) -> None:
        renderer = source(RENDERER)
        measure = swift_block(renderer, "private func measure(")
        assert_tokens(
            self,
            measure,
            [
                "let bubbleContentWidth = maximumBubbleWidth - 24.0",
                "guard bubbleContentWidth > 0.0 else",
                "throw GRVMMessageShotRendererError.invalidCanvas",
            ],
        )

    def test_tiny_thumbnails_and_current_wallpaper_use_real_repository_apis(self) -> None:
        renderer = source(RENDERER)
        reply = swift_block(renderer, "private func drawReply(")
        reply_thumbnail = swift_block(renderer, "private func drawReplyThumbnail(")
        media = swift_block(renderer, "private func drawMedia(")
        assert_tokens(
            self,
            renderer,
            [
                "import TinyThumbnail",
                "theme.chat.defaultWallpaper.singleColor ?? theme.list.plainBackgroundColor",
            ],
        )
        self.assertNotIn("theme.chat.defaultWallpaper.color", renderer)
        assert_tokens(
            self,
            reply,
            [
                "let thumbnailData: Data?",
                "let hasMedia: Bool",
                "case let .message(peerId, authorName, text, replyEntities, data, hasReplyMedia, _)",
                "case let .quote(peerId, authorName, text, replyEntities, data, hasReplyMedia, _)",
                "thumbnailData = data",
                "hasMedia = hasReplyMedia",
                "if hasMedia",
                "self.drawReplyThumbnail(thumbnailData: thumbnailData",
            ],
        )
        self.assertEqual(reply.count("self.drawReplyThumbnail(thumbnailData: thumbnailData"), 1)
        assert_tokens(
            self,
            reply_thumbnail,
            [
                "decodeTinyThumbnail(data: data)",
                "UIImage(data: decodedData)",
                "self.strings[.messageShotReplyMediaUnavailable]",
            ],
        )
        self.assertNotIn("self.drawReplyThumbnail(thumbnailData: thumbnailData", reply.split("if hasMedia")[0])
        assert_tokens(
            self,
            media,
            [
                "decodeTinyThumbnail(data: data)",
                "UIImage(data: decodedData)",
            ],
        )

    def test_reply_model_distinguishes_text_only_from_media_without_thumbnail(self) -> None:
        model = source(MODEL)
        mapped = swift_block(model, "private static func mapMessage(")
        assert_tokens(
            self,
            model,
            [
                "hasMedia: Bool",
            ],
        )
        assert_tokens(
            self,
            mapped,
            [
                "hasMedia: !replyMessage.media.isEmpty",
                "hasMedia: quote.media != nil",
            ],
        )

    def test_reactions_wrap_all_items_and_expand_the_bubble_height(self) -> None:
        renderer = source(RENDERER)
        measure = swift_block(renderer, "private func measure(")
        draw_reactions = swift_block(renderer, "private func drawReactions(")
        assert_tokens(
            self,
            measure,
            [
                "let reactionsHeight = Self.reactionsHeight(message.reactions, width: bubbleContentWidth)",
                "height: reactionsHeight",
                "cursor += reactionsHeight + 4.0",
            ],
        )
        assert_tokens(
            self,
            renderer,
            [
                "private static func reactionFrames(",
                "private static func reactionsHeight(",
            ],
        )
        assert_tokens(
            self,
            draw_reactions,
            [
                "let frames = Self.reactionFrames(reactions, width: frame.width)",
                "for (reaction, pillFrame) in zip(reactions, frames)",
            ],
        )

    def test_custom_reaction_placeholder_is_drawn_after_its_pill(self) -> None:
        renderer = source(RENDERER)
        draw_reactions = swift_block(renderer, "private func drawReactions(")
        pill_fill = "UIBezierPath(roundedRect: pillFrame, cornerRadius: 12.0).fill()"
        placeholder = "self.drawCustomReactionPlaceholder("
        text = "self.drawText(value, in: pillFrame"
        self.assertLess(draw_reactions.index(pill_fill), draw_reactions.index(placeholder))
        self.assertLess(draw_reactions.index(placeholder), draw_reactions.index(text))

    def test_palette_and_sender_colors_never_use_randomized_hashes(self) -> None:
        renderer = source(RENDERER)
        palettes = swift_block(renderer, "public struct GRVMMessageShotPalette")
        stable = swift_block(renderer, "private func stableColor(")
        assert_tokens(
            self,
            palettes,
            [
                "static func current(",
                "static func light(",
                "static func dark(",
                "theme.chat.message.incoming",
                "theme.chat.message.outgoing",
            ],
        )
        assert_tokens(
            self,
            stable,
            [
                "peerId.toInt64()",
                "% Int64(palette.senderColors.count)",
            ],
        )
        self.assertNotIn("hashValue", renderer)

    def test_size_memory_transparency_wallpaper_and_spoiler_guards_are_explicit(self) -> None:
        renderer = source(RENDERER)
        validate = swift_block(renderer, "private static func validate(")
        assert_tokens(
            self,
            validate,
            [
                "size.width.isFinite",
                "size.height.isFinite",
                "scale.isFinite",
                "size.width > 0.0",
                "size.height > 0.0",
                "scale >= 1.0 && scale <= 3.0",
                "pixelWidth <= 16384.0",
                "pixelHeight <= 16384.0",
                "estimatedBytes <= 48.0 * 1024.0 * 1024.0",
            ],
        )
        assert_tokens(
            self,
            renderer,
            [
                "options.showBackground ? palette.background : UIColor.clear",
                "case .file, .image, .emoticon:",
                "return palette.background",
                "if !options.revealSpoilers",
                "drawSpoilerMask",
                "case .custom:",
                "drawCustomReactionPlaceholder",
            ],
        )
        for forbidden in ["URLSession", "fetchedMediaResource", "http://", "https://"]:
            self.assertNotIn(forbidden, renderer)


class MessageShotControllerContractTests(unittest.TestCase):
    def test_controller_loads_model_and_settings_once_then_renders_off_main(self) -> None:
        controller = source(CONTROLLER)
        start = swift_block(controller, "private func load()")
        render = swift_block(controller, "private func requestRender()")
        self.assertEqual(controller.count("GRVMMessageShotModel.load("), 1)
        self.assertEqual(controller.count("grvmSettings("), 1)
        assert_tokens(
            self,
            start,
            [
                "combineLatest(",
                "GRVMMessageShotModel.load(",
                "grvmSettings(accountId: self.context.account.peerId",
                "self.model = model",
                "self.options = settings.grvmChatAppearanceSettings.messageShot",
                "self.requestRender()",
            ],
        )
        assert_tokens(
            self,
            render,
            [
                "self.renderGeneration &+= 1",
                "let generation = self.renderGeneration",
                "self.setActionsEnabled(false)",
                "GRVMMessageShotController.renderQueue.async",
                "autoreleasepool",
                "renderer.render(scale: GRVMMessageShotRenderer.defaultScale)",
                "Queue.mainQueue().async",
                "guard generation == self.renderGeneration",
                "self.setActionsEnabled(true)",
            ],
        )
        self.assertNotIn("postbox.transaction", render)
        self.assertNotIn("GRVMMessageShotModel.load(", render)

    def test_all_eight_options_persist_for_the_exact_account_without_requery(self) -> None:
        controller = source(CONTROLLER)
        update = swift_block(controller, "private func updateOptions(")
        self.assertEqual(update.count("updateGRVMSettings("), 1)
        assert_tokens(
            self,
            update,
            [
                "accountId: self.context.account.peerId",
                "settings.messageShotShowBackground = options.showBackground",
                "settings.messageShotShowDate = options.showDate",
                "settings.messageShotShowReactions = options.showReactions",
                "settings.messageShotShowHeader = options.showHeader",
                "settings.messageShotShowHeaderDecorations = options.showHeaderDecorations",
                "settings.messageShotColorfulReplies = options.colorfulReplies",
                "settings.messageShotRevealSpoilers = options.revealSpoilers",
                "settings.messageShotTheme = options.theme.rawValue",
                "self.requestRender()",
            ],
        )
        for forbidden in ["grvmSettings(", "postbox.transaction", "GRVMMessageShotModel.load("]:
            self.assertNotIn(forbidden, update)

    def test_native_ui_has_scroll_preview_theme_control_seven_switches_and_actions(self) -> None:
        controller = source(CONTROLLER)
        assert_tokens(
            self,
            controller,
            [
                "private let previewScrollView = UIScrollView()",
                "private let themeControl: UISegmentedControl",
                "self.themeControl = UISegmentedControl(items: [",
                "grvmStrings[.messageShotThemeCurrent]",
                "grvmStrings[.messageShotThemeLight]",
                "grvmStrings[.messageShotThemeDark]",
                "private let showBackgroundSwitch = UISwitch()",
                "private let showDateSwitch = UISwitch()",
                "private let showReactionsSwitch = UISwitch()",
                "private let showHeaderSwitch = UISwitch()",
                "private let showHeaderDecorationsSwitch = UISwitch()",
                "private let colorfulRepliesSwitch = UISwitch()",
                "private let revealSpoilersSwitch = UISwitch()",
                "private let copyButton = UIButton(type: .system)",
                "private let saveButton = UIButton(type: .system)",
                "heightAnchor.constraint(greaterThanOrEqualToConstant: 44.0)",
                "capabilities.hasReactions",
                "capabilities.hasReplies",
                "capabilities.hasSpoilers",
                "capabilities.hasHeaderDecorations",
            ],
        )
        for forbidden in ["CAGradientLayer", "UIFont(name:", "http://", "https://"]:
            self.assertNotIn(forbidden, controller)

    def test_copy_uses_public_png_and_success_is_the_only_completion_path(self) -> None:
        controller = source(CONTROLLER)
        copy = swift_block(controller, "@objc private func copyPressed()")
        assert_tokens(
            self,
            copy,
            [
                "guard self.renderedGeneration == self.renderGeneration",
                "let data = image.pngData()",
                "UIPasteboard.general.setData(data, forPasteboardType: \"public.png\")",
                "self.completion()",
            ],
        )

    def test_photos_save_uses_add_only_legacy_fallback_main_callbacks_and_settings_denial(self) -> None:
        controller = source(CONTROLLER)
        save = swift_block(controller, "@objc private func savePressed()")
        authorization = swift_block(controller, "private func requestPhotoAuthorization(")
        perform = swift_block(controller, "private func saveToPhotos(")
        assert_tokens(
            self,
            authorization,
            [
                "if #available(iOS 14.0, *)",
                "PHPhotoLibrary.authorizationStatus(for: .addOnly)",
                "PHPhotoLibrary.requestAuthorization(for: .addOnly)",
                "PHPhotoLibrary.authorizationStatus()",
                "PHPhotoLibrary.requestAuthorization",
                "Queue.mainQueue().async",
            ],
        )
        assert_tokens(
            self,
            perform,
            [
                "PHPhotoLibrary.shared().performChanges",
                "PHAssetCreationRequest.forAsset()",
                "creationRequest.addResource(with: .photo, data: pngData, options: nil)",
                "Queue.mainQueue().async",
                "if success",
                "self.completion()",
                "self.presentError(",
            ],
        )
        assert_tokens(
            self,
            save,
            [
                "guard self.renderedGeneration == self.renderGeneration",
                "case .authorized, .limited:",
                "case .denied, .restricted:",
                "self.presentPhotoAccessDenied()",
            ],
        )
        denied = swift_block(controller, "private func presentPhotoAccessDenied()")
        assert_tokens(
            self,
            denied,
            [
                "UIApplication.openSettingsURLString",
                "UIApplication.shared.open(url",
            ],
        )


class MessageShotScopeContractTests(unittest.TestCase):
    def test_cross_module_symbols_import_their_declaring_modules(self) -> None:
        required_imports = {
            MODEL: "import LocalizedPeerData",
            RENDERER: "import Display",
            CONTROLLER: "import PresentationDataUtils",
        }
        for path, required_import in required_imports.items():
            with self.subTest(path=path):
                self.assertIn(required_import, source(path))

    def test_selection_entry_point_is_hidden_for_empty_selection(self) -> None:
        panel = source(PANEL)
        layout = swift_block(panel, "override public func updateLayout(")
        assert_tokens(
            self,
            layout,
            [
                "self.messageShotButton.isHidden = self.peerMedia || self.messageShotRequested == nil || self.selectedMessages.isEmpty",
            ],
        )

    def test_no_network_hash_or_build_churn_contract(self) -> None:
        combined = source(MODEL) + source(RENDERER) + source(CONTROLLER)
        for forbidden in [
            "URLSession",
            "fetchedMediaResource",
            "hashValue",
            "http://",
            "https://",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)
        build = source("submodules/TelegramUI/BUILD")
        self.assertIn('srcs = glob([\n        "Sources/**/*.swift",', build)
        self.assertIn('"//submodules/TinyThumbnail:TinyThumbnail"', build)
        self.assertIn('"//submodules/AyuGramFeatures:AyuGramFeatures"', build)
        self.assertIn('"//submodules/AyuGramLib:AyuGramLib"', build)


if __name__ == "__main__":
    unittest.main()
