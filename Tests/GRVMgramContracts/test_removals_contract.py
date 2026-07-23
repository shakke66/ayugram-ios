from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


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


class RemovalSchemaContractTests(unittest.TestCase):
    def test_schema_keeps_only_the_surviving_ghost_interface(self) -> None:
        settings = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        for declaration in (
            "public var suppressReadReceipts: Bool",
            "public var suppressStoryReads: Bool",
            "public var suppressOnlineStatus: Bool",
            "public var suppressTypingAndUploads: Bool",
            "public var useScheduledMessages: Bool",
            "public var sendWithoutSoundMode: Int32",
        ):
            self.assertIn(declaration, settings)

        for removed_declaration in (
            "public var ghostModeEnabled:",
            "public var ghostLockedComponents:",
            "public var suppressTypingStatus:",
            "public var suppressUploadProgress:",
            "public var goOfflineAfterOnline:",
            "public var readOnAction:",
            "public var sendWithoutSound:",
            "public var sendWithoutSoundOption:",
        ):
            self.assertNotIn(removed_declaration, settings)

        count = swift_block(settings, "public var ghostModeActiveCount")
        self.assertEqual(4, count.count("count += 1"))
        self.assertIn("suppressTypingAndUploads", count)
        self.assertNotIn("goOfflineAfterOnline", count)

        bulk_toggle = swift_block(settings, "public mutating func setGhostModeEnabled")
        for property_name in (
            "suppressReadReceipts",
            "suppressStoryReads",
            "suppressOnlineStatus",
            "suppressTypingAndUploads",
        ):
            self.assertIn(f"self.{property_name} = enabled", bulk_toggle)
        self.assertNotIn("ghostLockedComponents", bulk_toggle)

    def test_renamed_ghost_values_decode_legacy_keys_but_encode_only_new_keys(self) -> None:
        settings = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        decoder = swift_block(settings, "public init(from decoder: Decoder)")
        encoder = swift_block(settings, "public func encode(to encoder: Encoder)")

        for key in (
            "suppressTypingAndUploads",
            "suppressTypingStatus",
            "suppressUploadProgress",
            "sendWithoutSoundMode",
            "sendWithoutSoundOption",
            "sendWithoutSound",
        ):
            self.assertIn(f'forKey: "{key}"', decoder)
        for key in ("suppressTypingAndUploads", "sendWithoutSoundMode"):
            self.assertIn(f'encode(self.{key}, forKey: "{key}")', encoder)
        for legacy_key in (
            "suppressTypingStatus",
            "suppressUploadProgress",
            "sendWithoutSoundOption",
            "sendWithoutSound",
        ):
            self.assertNotIn(f'forKey: "{legacy_key}"', encoder)

    def test_all_rejected_schema_fields_and_new_writes_are_absent(self) -> None:
        settings = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        encoder = swift_block(settings, "public func encode(to encoder: Encoder)")
        removed = (
            "ghostLockedComponents",
            "goOfflineAfterOnline",
            "readOnAction",
            "spoofWebviewAsAndroid",
            "increaseWebviewSize",
            "increaseWebviewHeight",
            "increaseWebviewWidth",
            "md3StyleSwitches",
            "messageBubbleRadius",
            "singleCornerRadius",
            "adaptiveCoverColor",
            "messageShotFeature",
            "messageShotShowBackground",
            "messageShotShowDate",
            "messageShotShowReactions",
            "messageShotShowHeader",
            "messageShotShowHeaderDecorations",
            "messageShotColorfulReplies",
            "messageShotRevealSpoilers",
            "messageShotTheme",
            "showAttachPopup",
            "showCommandsButton",
            "showEmojiPopup",
        )
        for name in removed:
            with self.subTest(name=name):
                self.assertNotIn(f"public var {name}:", settings)
                self.assertNotIn(f'forKey: "{name}"', encoder)

        # N01 is owned by Stream B and must remain available to its controller/runtime pass.
        self.assertIn("public var translationProvider: Int32", settings)
        general = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift"
        )
        self.assertIn("case translationProvider", general)
        self.assertIn(r"\.translationProvider", general)


class RemovalControllerContractTests(unittest.TestCase):
    controller_paths = (
        "submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift",
        "submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift",
        "submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift",
        "submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift",
    )

    def test_rejected_rows_are_absent_and_required_rows_are_public(self) -> None:
        core, general, appearance, chats = (source(path) for path in self.controller_paths)
        for token in (
            "ghostLockedComponents",
            "ghostComponentGoOfflineAfterOnline",
            "readOnAction",
            "ayuGramGhostLockedComponentsController",
        ):
            self.assertNotIn(token, core)
        self.assertIn("settings.ghostModeActiveCount == 4", core)

        for token in (
            "webviewHeader",
            "spoofAndroid",
            "increaseWebviewHeight",
            "increaseWebviewWidth",
        ):
            self.assertNotIn(token, general)

        for token in (
            "md3Switches",
            "messageBubbleRadius",
            "singleCornerRadius",
            "adaptiveCoverColor",
        ):
            self.assertNotIn(token, appearance)

        for token in (
            "messageShot",
            "showAttachPopup",
            "showCommands",
            "showEmojiPopup",
        ):
            self.assertNotIn(token, chats)

        for token in (
            "case showPrivateReactions(PresentationTheme, Bool)",
            "strings[.stickersPrivateReactions]",
            r"arguments.updateBool(\.showPrivateReactions, v)",
            ".showPrivateReactions(presentationData.theme, settings.showPrivateReactions)",
            "case showAddFilter(PresentationTheme, String, Int32)",
            "strings[.contextAddFilter]",
            r"arguments.updateInt32(\.showAddFilterInContextMenu, (value + 1) % 3)",
            ".showAddFilter(presentationData.theme, addFilterLabel, settings.showAddFilterInContextMenu)",
        ):
            self.assertIn(token, chats)

    def test_every_surviving_owned_switch_opts_into_multiline_layout(self) -> None:
        for path in self.controller_paths:
            with self.subTest(path=path):
                controller = source(path)
                switch_rows = [
                    line
                    for line in controller.splitlines()
                    if "ItemListSwitchItem(" in line
                ]
                self.assertGreater(len(switch_rows), 0)
                for row in switch_rows:
                    self.assertIn("maximumNumberOfLines: 2", row)
                    self.assertIn("adaptiveLayout: true", row)

    def test_context_menu_labels_hide_negative_and_out_of_range_legacy_values(self) -> None:
        chats = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift"
        )
        fields = (
            "showReactionsPanelInContextMenu",
            "showViewsPanelInContextMenu",
            "showHideMessageInContextMenu",
            "showUserMessagesInContextMenu",
            "showMessageDetailsInContextMenu",
            "showRepeatMessageInContextMenu",
            "showAddFilterInContextMenu",
        )
        for field in fields:
            with self.subTest(field=field):
                self.assertIn(
                    f"settings.{field} >= 0 && settings.{field} < Int32(contextMenuLabels.count)",
                    chats,
                )
                self.assertIn(
                    f"contextMenuLabels[Int(settings.{field})] : strings[.commonHidden]",
                    chats,
                )

        for key_path in (
            "showReactionsPanelInContextMenu",
            "showViewsPanelInContextMenu",
            "showHideMessageInContextMenu",
            "showUserMessagesInContextMenu",
            "showMessageDetailsInContextMenu",
            "showRepeatMessageInContextMenu",
            "showAddFilterInContextMenu",
        ):
            self.assertIn(
                rf"arguments.updateInt32(\.{key_path}, (value + 1) % 3)",
                chats,
            )

    def test_global_archive_and_history_routes_are_removed_but_scoped_routes_survive(self) -> None:
        main = source("submodules/AyuGramSettingsUI/Sources/AyuGramMainController.swift")
        self.assertNotIn("spyHistory", main)
        self.assertNotIn("editHistory", main)
        self.assertFalse(
            (ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramEditedMessagesController.swift").exists()
        )

        deleted = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift"
        )
        signature = deleted[
            deleted.index("public func grvmDeletedMessagesController(") :
            deleted.index(") -> ViewController", deleted.index("public func grvmDeletedMessagesController("))
        ]
        self.assertIn("peerId: PeerId", signature)
        self.assertIn("threadId: Int64?", signature)
        self.assertNotIn("PeerId?", signature)
        self.assertNotIn("= nil", signature)
        self.assertNotIn("ayuGramDeletedMessagesController", deleted)

        archive_menu = source(
            "submodules/AyuGramSettingsUI/Sources/GRVMArchiveContextMenuItems.swift"
        )
        self.assertIn("grvmDeletedMessagesController(", archive_menu)
        self.assertIn("peerId: PeerId", archive_menu)
        self.assertIn("peerId: peerId", archive_menu)
        history = source(
            "submodules/AyuGramSettingsUI/Sources/GRVMMessageHistoryController.swift"
        )
        self.assertIn("messageId: MessageId", history)


class RemovalRuntimeContractTests(unittest.TestCase):
    def test_custom_webview_overrides_are_removed_but_stock_webview_survives(self) -> None:
        webview = source("submodules/WebUI/Sources/WebAppWebView.swift")
        for token in (
            "shouldSpoofWebviewAsAndroid",
            "shouldIncreaseWebviewHeight",
            "shouldIncreaseWebviewWidth",
            "webviewViewportScale",
            "Android 13; Mobile",
        ):
            self.assertNotIn(token, webview)
        self.assertIn("WKWebView", webview)
        self.assertIn("func updateMetrics(", webview)

    def test_rejected_appearance_runtime_is_removed_but_stock_surfaces_survive(self) -> None:
        policy = source("submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift")
        model = source("submodules/TelegramCore/Sources/GRVMChatAppearance.swift")
        for token in (
            "md3StyleSwitches",
            "messageBubbleRadius",
            "singleCornerRadius",
            "messageShotFeature",
            "GRVMMessageShot",
            "showCommandsButton",
            "showAttachPopup",
            "showEmojiPopup",
        ):
            self.assertNotIn(token, policy)
            self.assertNotIn(token, model)

        switch = source("submodules/Display/Source/SwitchNode.swift")
        self.assertNotIn("case md3", switch)
        self.assertNotIn("defaultStyle", switch)

        presentation = source(
            "submodules/TelegramPresentationData/Sources/ChatPresentationData.swift"
        )
        self.assertNotIn("messageBubbleRadius", presentation)
        self.assertIn("mainRadius: chatBubbleCorners.mainRadius", presentation)
        self.assertIn("hasTails: chatBubbleCorners.hasTails && !appearance.removeMessageBubbleTail", presentation)

        peer_header = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift"
        )
        self.assertNotIn("GRVMSavedMusicColor", peer_header)
        self.assertNotIn("shouldUseAdaptiveSavedMusicCover", peer_header)
        self.assertIn("displaySavedMusic", peer_header)
        self.assertFalse(
            (
                ROOT
                / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/GRVMSavedMusicColor.swift"
            ).exists()
        )

    def test_message_shot_is_deleted_without_removing_stock_selection_actions(self) -> None:
        for name in (
            "GRVMMessageShotModel.swift",
            "GRVMMessageShotRenderer.swift",
            "GRVMMessageShotController.swift",
        ):
            self.assertFalse((ROOT / "submodules/TelegramUI/Sources" / name).exists())

        panels = source("submodules/TelegramUI/Sources/ChatInterfaceStateInputPanels.swift")
        selection = source(
            "submodules/TelegramUI/Components/Chat/ChatMessageSelectionInputPanelNode/"
            "Sources/ChatMessageSelectionInputPanelNode.swift"
        )
        self.assertNotIn("grvmMessageShotRequested", panels)
        self.assertNotIn("messageShotRequested", selection)
        self.assertNotIn("messageShotButton", selection)
        for stock_token in (
            "shareSelectedMessages()",
            "deleteSelectedMessages()",
            "reportSelectedMessages()",
            "forwardSelectedMessages()",
            "@objc private func tagButtonPressed()",
            "tagMessageReactions(",
        ):
            self.assertIn(stock_token, selection)

        telegram_ui_build = source("submodules/TelegramUI/BUILD")
        self.assertNotIn('"//submodules/TinyThumbnail:TinyThumbnail"', telegram_ui_build)

    def test_compose_popups_and_command_override_are_removed_but_stock_actions_survive(self) -> None:
        input_contexts = source("submodules/TelegramUI/Sources/ChatInterfaceInputContexts.swift")
        panel = source(
            "submodules/TelegramUI/Components/Chat/ChatTextInputPanelNode/"
            "Sources/ChatTextInputPanelNode.swift"
        )
        self.assertNotIn("showCommandsButton", input_contexts)
        self.assertIn("accessoryItems.append(.commands)", input_contexts)
        for token in (
            "attachmentButtonContextGesture",
            "emojiButtonContextGesture",
            "updateEmojiButtonContextGesture",
            "showAttachPopup",
            "showEmojiPopup",
            "compose.showCommandsButton",
        ):
            self.assertNotIn(token, panel)
        self.assertIn(
            "let showMenuButton = hasMenuButton && interfaceState.interfaceState.mediaDraftState == nil",
            panel,
        )
        self.assertIn(
            "self.menuButton.isUserInteractionEnabled = showMenuButton",
            panel,
        )
        self.assertIn(
            "self.attachmentButton.addTarget(self, action: #selector(self.attachmentButtonPressed)",
            panel,
        )
        self.assertIn("@objc func accessoryItemButtonPressed", panel)

    def test_joined_profile_row_is_removed_but_stock_joined_data_and_events_survive(self) -> None:
        profile = source(
            "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift"
        )
        self.assertNotIn("cachedData.invitedOn", profile)
        self.assertNotIn("grvmStrings[.peerJoined]", profile)
        self.assertIn("channel.creationDate", profile)
        self.assertIn("grvmStrings[.peerCreated]", profile)

        cached = source(
            "submodules/TelegramCore/Sources/SyncCore/SyncCore_CachedChannelData.swift"
        )
        self.assertIn("public let invitedOn: Int32?", cached)
        history = source("submodules/TelegramUI/Sources/ChatHistoryListNode.swift")
        self.assertIn(".joinedChannel", history)
        self.assertIn(".peerJoined", history)

    def test_stream_c_runtime_seam_contains_no_removed_symbols(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        manager = source("submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift")
        removed_hooks = (
            "shouldForceOfflineAfterOnline",
            "shouldMarkReadAfterAction",
            "shouldSpoofWebviewAsAndroid",
            "shouldIncreaseWebviewHeight",
            "shouldIncreaseWebviewWidth",
            "shouldUseAdaptiveSavedMusicCover",
            "shouldUseMD3Switches",
            "messageBubbleRadius",
            "shouldUseSingleCornerRadius",
            "shouldShowMessageShot",
        )
        for name in removed_hooks:
            self.assertNotIn(name, hooks)
            self.assertNotIn(f"AyuGramHooks.{name} =", manager)

        for path in (
            "submodules/TelegramUI/Sources/ChatController.swift",
            "submodules/TelegramUI/Sources/Chat/ChatControllerOpenMessageContextMenu.swift",
            "submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift",
        ):
            self.assertNotIn("grvmMarkCurrentChatReadAfterAction", source(path))
        self.assertNotIn(
            "messageBubbleRadius",
            source("submodules/TelegramUI/Sources/ChatHistoryListNode.swift"),
        )


if __name__ == "__main__":
    unittest.main()
