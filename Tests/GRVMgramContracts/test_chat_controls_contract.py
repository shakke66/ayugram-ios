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


def normalized(text: str) -> str:
    return "".join(text.split())


def assert_ordered_tokens(
    test: unittest.TestCase, text: str, tokens: list[str]
) -> None:
    body = normalized(text)
    offset = 0
    for token in tokens:
        normalized_token = normalized(token)
        index = body.find(normalized_token, offset)
        test.assertNotEqual(
            index,
            -1,
            f"Missing ordered token after offset {offset}: {normalized_token}",
        )
        offset = index + len(normalized_token)


def apply_installed_policy(
    candidates: list[tuple[str, int | None]],
    installed_ids: set[int],
    enabled: bool,
) -> list[tuple[str, int | None]]:
    preserved = {"unicode", "static", "selected", "saved"}
    return [
        candidate
        for candidate in candidates
        if not enabled
        or candidate[0] in preserved
        or candidate[1] in installed_ids
    ]


def visible_recent_ids(
    pack_ids: list[int | None], installed_ids: set[int], cap: int
) -> list[int]:
    result: list[int] = []
    for pack_id in pack_ids:
        if pack_id not in installed_ids:
            continue
        if len(result) >= cap:
            break
        result.append(pack_id)
    return result


def reactions_visible(peer_kind: str, settings: dict[str, bool]) -> bool:
    if peer_kind == "broadcast":
        return settings["channel"]
    if peer_kind in {"groupChannel", "group"}:
        return settings["group"]
    if peer_kind in {"user", "secretChat"}:
        return settings["private"]
    return True


class ChatControlsContractTests(unittest.TestCase):
    subscriber_path = (
        "submodules/TelegramUI/Components/Chat/"
        "ChatChannelSubscriberInputPanelNode/Sources/"
        "ChatChannelSubscriberInputPanelNode.swift"
    )
    controller_path = "submodules/TelegramUI/Sources/ChatController.swift"
    feature_manager_path = (
        "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
    )
    navigation_buttons_path = (
        "submodules/TelegramUI/Sources/ChatInterfaceStateNavigationButtons.swift"
    )
    update_state_path = (
        "submodules/TelegramUI/Sources/Chat/"
        "UpdateChatPresentationInterfaceState.swift"
    )
    keyboard_path = (
        "submodules/TelegramUI/Components/ChatEntityKeyboardInputNode/Sources/"
        "ChatEntityKeyboardInputNode.swift"
    )
    pager_path = (
        "submodules/TelegramUI/Components/EntityKeyboard/Sources/"
        "EmojiPagerContentSignals.swift"
    )
    bubble_path = (
        "submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/"
        "ChatMessageBubbleItemNode.swift"
    )

    def test_exact_account_snapshots_replace_migrated_hooks(self) -> None:
        keyboard = source(self.keyboard_path)
        pager = source(self.pager_path)
        bubble = source(self.bubble_path)

        input_data = swift_block(keyboard, "public static func inputData(")
        emoji_data = swift_block(pager, "static func emojiInputData(")
        sticker_data = swift_block(pager, "static func stickerInputData(")
        begin_layout = swift_block(bubble, "private static func beginLayout(")

        exact_account = (
            "let chats = AyuGramHooks.chatAppearance("
            "accountPeerId: context.account.peerId).chats"
        )
        self.assertIn(normalized(exact_account), normalized(input_data))
        self.assertIn(normalized(exact_account), normalized(emoji_data))
        self.assertIn(normalized(exact_account), normalized(sticker_data))
        self.assertIn(
            normalized(
                "let chats = AyuGramHooks.chatAppearance("
                "accountPeerId: item.context.account.peerId).chats"
            ),
            normalized(begin_layout),
        )

        for legacy in [
            "shouldShowOnlyAddedStickers?()",
            "recentStickersLimit?()",
            "shouldShowChannelReactions?()",
            "shouldShowGroupReactions?()",
        ]:
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, keyboard + pager + bubble)

    def test_membership_helpers_require_real_pack_ids_in_both_namespaces(self) -> None:
        for path in [self.keyboard_path, self.pager_path]:
            with self.subTest(path=path):
                text = source(path)
                helper = swift_block(
                    text, "private func grvmIsMediaInstalled("
                )
                for token in [
                    ".Sticker(_, packReference, _)",
                    ".CustomEmoji(_, _, _, packReference)",
                    "case let .id(id, _) = packReference",
                    "ItemCollectionId(namespace: namespace, id: id)",
                    "installedCollectionIds.contains",
                ]:
                    self.assertIn(normalized(token), normalized(helper))

        combined = source(self.keyboard_path) + source(self.pager_path)
        self.assertIn("Namespaces.ItemCollection.CloudEmojiPacks", combined)
        self.assertIn("Namespaces.ItemCollection.CloudStickerPacks", combined)

    def test_emoji_recents_peer_pack_featured_and_selection_policy(self) -> None:
        pager = source(self.pager_path)
        emoji_data = swift_block(pager, "static func emojiInputData(")
        body = normalized(emoji_data)

        for token in [
            "Set(view.collectionInfos.map { $0.0 })",
            "case let .file(file) = item.content",
            "grvmIsMediaInstalled(file, namespace: Namespaces.ItemCollection.CloudEmojiPacks",
            "installedCollectionIds.contains(peerSpecificPack.info.id)",
            "if !isStandalone && !chats.showOnlyAddedStickers",
            "case let .text(text)",
            "selectedItems: selectedItems",
        ]:
            with self.subTest(token=token):
                self.assertIn(normalized(token), body)

    def test_sticker_recents_filter_before_cap_and_preserve_saved(self) -> None:
        pager = source(self.pager_path)
        sticker_data = swift_block(pager, "static func stickerInputData(")
        saved = swift_block(sticker_data, "if let savedStickers = savedStickers")
        self.assertNotIn("grvmIsMediaInstalled", saved)

        recent = swift_block(sticker_data, "if let recentStickers = recentStickers")
        assert_ordered_tokens(
            self,
            recent,
            [
                "guard let item = item.contents.get(RecentMediaItem.self)",
                "if chats.showOnlyAddedStickers && !grvmIsMediaInstalled(",
                "if visibleRecentCount >= recentLimit",
                "itemGroups[groupIndex].items.append(resultItem)",
                "visibleRecentCount += 1",
            ],
        )
        for token in [
            "let recentLimit = Int(chats.recentStickersCount)",
            "var visibleRecentCount = 0",
            "installedCollectionIds.contains(peerSpecificPack.info.id)",
            "hasTrending && !chats.showOnlyAddedStickers",
        ]:
            self.assertIn(normalized(token), normalized(sticker_data))

    def test_search_uses_live_installed_sets_without_changing_stock_order(self) -> None:
        keyboard = source(self.keyboard_path)
        keyboard_init = swift_block(
            keyboard,
            "public init(context: AccountContext, currentInputData: InputData",
        )
        for token in [
            "let chats = AyuGramHooks.chatAppearance(accountPeerId: context.account.peerId).chats",
            "itemCollectionsView(",
            "namespaces: [Namespaces.ItemCollection.CloudEmojiPacks]",
            "Set(view.collectionInfos.map { $0.0 })",
            "combineLatest(remoteSignal, remotePacksSignal, installedEmojiCollectionIds)",
            "grvmIsMediaInstalled(itemFile, namespace: Namespaces.ItemCollection.CloudEmojiPacks",
            "installedEmojiCollectionIds.contains(collectionId)",
            "combineLatest(context.engine.stickers.searchEmoji(category: value), installedEmojiCollectionIds)",
            "scope: chats.showOnlyAddedStickers ? [.installed] : [.installed, .remote]",
            "grvmIsMediaInstalled(itemFile, namespace: Namespaces.ItemCollection.CloudStickerPacks",
        ]:
            with self.subTest(token=token):
                self.assertIn(normalized(token), normalized(keyboard_init))

        assert_ordered_tokens(
            self,
            keyboard_init,
            [
                "existingIds.contains(itemFile.fileId)",
                "grvmIsMediaInstalled(itemFile, namespace: Namespaces.ItemCollection.CloudStickerPacks",
            ],
        )

    def test_reaction_row_policy_is_final_and_complete(self) -> None:
        bubble = source(self.bubble_path)
        begin_layout = swift_block(bubble, "private static func beginLayout(")
        for token in [
            "as? TelegramChannel",
            "case .broadcast",
            "chats.showChannelReactions",
            "case .group",
            "chats.showGroupReactions",
            "is TelegramGroup",
            "is TelegramUser",
            "is TelegramSecretChat",
            "chats.showPrivateReactions",
        ]:
            self.assertIn(normalized(token), normalized(begin_layout))

        render_condition = normalized(
            "if !bubbleReactions.reactions.isEmpty "
            "&& !item.presentationData.isPreview "
            "&& grvmShouldShowReactions"
        )
        self.assertIn(render_condition, normalized(begin_layout))

    def test_channel_bottom_mode_is_typed_and_routes_real_discussion(self) -> None:
        subscriber = source(self.subscriber_path)
        action_enum = swift_block(subscriber, "private enum SubscriberAction")
        action_for_peer = swift_block(subscriber, "private func actionForPeer(")
        button_pressed = swift_block(subscriber, "@objc private func buttonPressed(")

        for token in ["case hidden", "case openDiscussion(PeerId)"]:
            self.assertIn(normalized(token), normalized(action_enum))

        for token in [
            "let bottomButtonMode = AyuGramHooks.chatAppearance("
            "accountPeerId: interfaceState.accountPeerId).chats.channelBottomButton",
            "case .hidden:",
            "case .mute:",
            "case .discussWithFallback:",
            "case .broadcast = channel.info",
            "let peerDiscussionId = interfaceState.peerDiscussionId",
            "return .openDiscussion(peerDiscussionId)",
            "return muteAction",
            "!channel.hasPermission(.sendSomething)",
            "channel.flags.contains(.isGigagroup)",
            "peer.id.isRepliesOrVerificationCodes",
        ]:
            with self.subTest(token=token):
                self.assertIn(normalized(token), normalized(action_for_peer))

        assert_ordered_tokens(
            self,
            action_for_peer,
            [
                "case .discussWithFallback:",
                "let peerDiscussionId = interfaceState.peerDiscussionId",
                "return .openDiscussion(peerDiscussionId)",
                "return muteAction",
            ],
        )

        self.assertNotIn("AyuGramHooks.channelBottomButtonMode", subscriber)
        self.assertNotIn(
            "AyuGramHooks.channelBottomButtonMode =",
            source(self.feature_manager_path),
        )
        for token in [
            "case let .openDiscussion(peerId)",
            "self.interfaceInteraction?.navigateToChat(peerId)",
        ]:
            self.assertIn(normalized(token), normalized(button_pressed))

    def test_hidden_channel_bottom_panel_resets_visibility_and_height(self) -> None:
        subscriber = source(self.subscriber_path)
        update_layout = swift_block(
            subscriber,
            "private func updateLayout(width: CGFloat",
        )
        minimal_height = swift_block(
            subscriber,
            "override public func minimalHeight(",
        )

        assert_ordered_tokens(
            self,
            update_layout,
            [
                "action = actionForPeer(",
                "self.action = action",
                "if action == .hidden",
                "self.panelContainer.isHidden = true",
                "return 0.0",
                "self.panelContainer.isHidden = false",
            ],
        )
        for token in [
            "actionForPeer(",
            "== .hidden",
            "return 0.0",
            "return defaultHeight(metrics: metrics)",
        ]:
            self.assertIn(normalized(token), normalized(minimal_height))

    def test_quick_admin_availability_is_typed_account_exact_and_permissioned(
        self,
    ) -> None:
        navigation = source(self.navigation_buttons_path)
        availability = swift_block(
            navigation,
            "struct GRVMQuickAdminNavigationAvailability",
        )
        policy = swift_block(
            navigation,
            "func grvmQuickAdminNavigationAvailability(",
        )

        for token in ["let recentActions: Bool", "let admins: Bool"]:
            self.assertIn(normalized(token), normalized(availability))
        for token in [
            "AyuGramHooks.chatAppearance("
            "accountPeerId: presentationInterfaceState.accountPeerId)"
            ".chats.quickAdminShortcuts",
            "presentationInterfaceState.interfaceState.selectionState == nil",
            "case .standard(.default) = presentationInterfaceState.mode",
            "case .peer = presentationInterfaceState.chatLocation",
            "case .scheduledMessages, .pinnedMessages, .messageOptions, "
            ".customChatContents:",
            "channel.adminRights != nil || channel.flags.contains(.isCreator)",
            "case .group:",
            "recentActions: isAdmin, admins: true",
            "case .broadcast:",
            "recentActions: isAdmin, admins: isAdmin",
        ]:
            with self.subTest(token=token):
                self.assertIn(normalized(token), normalized(policy))

    def test_quick_admin_items_append_after_stock_and_open_native_controllers(
        self,
    ) -> None:
        controller = source(self.controller_path)
        update_state = source(self.update_state_path)
        recent_item = swift_block(
            controller,
            "lazy var grvmRecentActionsButtonItem",
        )
        admins_item = swift_block(controller, "lazy var grvmAdminsButtonItem")
        recent_action = swift_block(
            controller,
            "@objc func grvmRecentActionsButtonPressed(",
        )
        admins_action = swift_block(
            controller,
            "@objc func grvmAdminsButtonPressed(",
        )
        peer_context_menu = swift_block(controller, "openPeerContextMenu:")
        update = swift_block(update_state, "func updateChatPresentationInterfaceStateImpl(")

        for block, tokens in [
            (
                recent_item,
                [
                    'UIImage(bundleImageName: "Item List/Icons/View")',
                    ".withRenderingMode(.alwaysTemplate)",
                    "#selector(self.grvmRecentActionsButtonPressed)",
                    "self.presentationData.strings.Group_Info_AdminLog",
                ],
            ),
            (
                admins_item,
                [
                    'UIImage(bundleImageName: "Item List/Icons/Admin")',
                    ".withRenderingMode(.alwaysTemplate)",
                    "#selector(self.grvmAdminsButtonPressed)",
                    "self.presentationData.strings.GroupInfo_Administrators",
                ],
            ),
            (
                recent_action,
                [
                    "grvmQuickAdminNavigationAvailability("
                    "self.presentationInterfaceState)",
                    "availability.recentActions",
                    "makeChatRecentActionsController(",
                    "adminPeerId: nil",
                    "starsState: nil",
                    "self.push(controller)",
                ],
            ),
            (
                admins_action,
                [
                    "grvmQuickAdminNavigationAvailability("
                    "self.presentationInterfaceState)",
                    "availability.admins",
                    "channelAdminsController(",
                    "peerId: channel.id",
                    "self.push(controller)",
                ],
            ),
        ]:
            for token in tokens:
                with self.subTest(token=token):
                    self.assertIn(normalized(token), normalized(block))

        assert_ordered_tokens(
            self,
            update,
            [
                "rightBarButtons.append(rightNavigationButton.buttonItem)",
                "rightBarButtons.append(secondaryRightNavigationButton.buttonItem)",
                "let quickAdminAvailability = "
                "grvmQuickAdminNavigationAvailability("
                "updatedChatPresentationInterfaceState)",
                "rightBarButtons.append("
                "selfController.grvmRecentActionsButtonItem)",
                "rightBarButtons.append(selfController.grvmAdminsButtonItem)",
            ],
        )

        self.assertNotIn("AyuGramHooks.shouldUseQuickAdminShortcuts", controller)
        self.assertNotIn(
            "AyuGramHooks.shouldUseQuickAdminShortcuts =",
            source(self.feature_manager_path),
        )
        self.assertNotIn("Conversation_ContextMenuBan", peer_context_menu)
        self.assertNotIn("chatAvailableMessageActions", peer_context_menu)
        self.assertNotIn("EngineData.Item.Messages.Message", peer_context_menu)

    def test_behavior_fixture_preserves_stock_and_filters_before_cap(self) -> None:
        candidates = [
            ("unicode", None),
            ("static", None),
            ("file", 1),
            ("file", 9),
            ("file", None),
            ("selected", None),
            ("saved", None),
        ]
        self.assertEqual(
            apply_installed_policy(candidates, {1}, enabled=False), candidates
        )
        self.assertEqual(
            apply_installed_policy(candidates, {1}, enabled=True),
            [
                ("unicode", None),
                ("static", None),
                ("file", 1),
                ("selected", None),
                ("saved", None),
            ],
        )
        self.assertEqual(visible_recent_ids([9, 1, 8, 2, 3], {1, 2, 3}, 2), [1, 2])

    def test_behavior_fixture_covers_complete_peer_matrix(self) -> None:
        settings = {"channel": False, "group": True, "private": False}
        expected = {
            "broadcast": False,
            "groupChannel": True,
            "group": True,
            "user": False,
            "secretChat": False,
            "missing": True,
            "unknown": True,
        }
        self.assertEqual(
            {kind: reactions_visible(kind, settings) for kind in expected}, expected
        )


if __name__ == "__main__":
    unittest.main()
