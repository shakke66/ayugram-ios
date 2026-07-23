import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENGINE = "submodules/AyuGramFeatures/Sources/GRVMMessageFilterEngine.swift"
BLOCKED = "submodules/AyuGramFeatures/Sources/GRVMBlockedPeersRegistry.swift"
VISIBILITY = "submodules/AyuGramFeatures/Sources/GRVMFilteredMessageVisibility.swift"
SHADOW_POLICY = "submodules/AyuGramLib/Sources/GRVMShadowBanPolicy.swift"


def source(path: str) -> str:
    file_path = ROOT / path
    if not file_path.exists():
        raise AssertionError(f"Missing Task 4 source: {path}")
    return file_path.read_text(encoding="utf-8")


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


class FilterContractTests(unittest.TestCase):
    def test_engine_compiles_immutable_account_snapshots_safely(self) -> None:
        engine = source(ENGINE)
        self.assertIn("public final class GRVMMessageFilterEngine", engine)
        for token in (
            "public let accountPeerId: PeerId",
            "let settings: AyuGramSettings",
            "let blockedPeerIds: Set<PeerId>",
            "private struct CompiledFilter",
            "let regularExpression: NSRegularExpression?",
            "guard filter.isEnabled else",
            "var options: NSRegularExpression.Options = [.anchorsMatchLines]",
            "if filter.isCaseInsensitive",
            "options.insert(.caseInsensitive)",
            "try? NSRegularExpression(pattern: filter.expression, options: options)",
        ):
            self.assertIn(token, engine)
        self.assertNotIn("try!", engine)
        self.assertNotIn("fatalError", engine)
        self.assertNotIn("preconditionFailure", engine)

    def test_engine_keeps_scope_normal_reversed_and_id_policies_separate(self) -> None:
        engine = source(ENGINE)
        applicability = swift_block(engine, "private func isApplicable(")
        for token in (
            "filter.excludedPeerIds.contains(chatPeerId.toInt64())",
            "if let peerId = filter.peerId",
            "peerId == chatPeerId.toInt64()",
            "chatPeerId.namespace == Namespaces.Peer.CloudChannel",
            "self.settings.enableFiltersInChats",
        ):
            self.assertIn(token, applicability)

        matching = swift_block(engine, "public func matchingFilterIds(for message:")
        self.assertIn("guard self.settings.enableFilters,", matching)
        self.assertIn("self.candidate(for: message)", matching)
        self.assertIn("filter.filter.id.uuidString", matching)

        hidden = swift_block(
            engine,
            "private func isMessageHidden(_ message: Message, visitedMessageIds:",
        )
        for token in (
            "message.author?.id",
            "message.forwardInfo?.author?.id",
            "self.shadowBanPeerIds",
            "self.settings.hideFromBlockedUsers",
            "self.blockedPeerIds",
            "$0.regularExpression != nil",
            "applicableNormalFilters",
            "applicableReversedFilters",
            "applicableNormalFilters.contains",
            "!applicableReversedFilters.contains",
        ):
            self.assertIn(token, hidden)
        self.assertLess(
            hidden.index("applicableNormalFilters.contains"),
            hidden.index("!applicableReversedFilters.contains"),
        )

    def test_outgoing_messages_bypass_every_filter_path(self) -> None:
        engine = source(ENGINE)
        matching = swift_block(engine, "public func matchingFilterIds(for message:")
        hidden = swift_block(
            engine,
            "private func isMessageHidden(_ message: Message, visitedMessageIds:",
        )
        for block in (matching, hidden):
            self.assertIn("message.effectivelyIncoming(self.accountPeerId)", block)
            self.assertLess(
                block.index("message.effectivelyIncoming(self.accountPeerId)"),
                block.index("self.candidate(for: message)"),
            )

    def test_hidden_reply_chain_and_forward_origin_are_recursive_and_bounded(self) -> None:
        engine = source(ENGINE)
        public_entry = swift_block(engine, "public func isMessageHidden(_ message:")
        hidden = swift_block(
            engine,
            "private func isMessageHidden(_ message: Message, visitedMessageIds:",
        )
        self.assertIn("var visitedMessageIds = Set<MessageId>()", public_entry)
        self.assertIn("visitedMessageIds: &visitedMessageIds", public_entry)
        for token in (
            "guard visitedMessageIds.insert(message.id).inserted else",
            "message.sourceAuthorInfo?.originalAuthor",
            "attribute as? ReplyMessageAttribute",
            "message.associatedMessages[replyAttribute.messageId]",
            "self.isMessageHidden(replyMessage, visitedMessageIds: &visitedMessageIds)",
        ):
            self.assertIn(token, hidden)

    def test_shadow_policy_excludes_self_and_deduplicates_at_mutation_boundary(self) -> None:
        policy = source(SHADOW_POLICY)
        normalized = swift_block(policy, "public static func normalizedPeerIds(")
        updated = swift_block(policy, "public static func updatedPeerIds(")
        for token in (
            "peerId != accountPeerId",
            "seen.insert(peerId).inserted",
        ):
            self.assertIn(token, normalized)
        for token in (
            "normalizedPeerIds(peerIds, accountPeerId: accountPeerId)",
            "guard peerId != accountPeerId else",
            "if isBanned",
            "result.append(peerId)",
            "result.removeAll(where: { $0 == peerId })",
        ):
            self.assertIn(token, updated)

        engine = source(ENGINE)
        self.assertIn("GRVMShadowBanPolicy.normalizedPeerIds(", engine)
        shadow = swift_block(engine, "public func isShadowBanned(")
        self.assertIn("peerId != self.accountPeerId", shadow)

    def test_candidate_is_newline_delimited_and_covers_entities_and_buttons(self) -> None:
        engine = source(ENGINE)
        candidate = swift_block(engine, "private func candidate(for message:")
        for token in (
            "append(message.text)",
            "TextEntitiesMessageAttribute",
            "case .Url",
            "case let .TextUrl(url)",
            "message.text as NSString",
            "location: entity.range.lowerBound",
            "substring(with: range)",
            "ReplyMarkupMessageAttribute",
            "for row in replyMarkup.rows",
            "for button in row.buttons",
            "append(button.title)",
            "case let .url(url)",
            "case let .urlAuth(url, _)",
            "case let .callback(_, data)",
            "data.makeData()",
            "case let .switchInline(_, query, _)",
            "case let .openWebView(url, _)",
            "case let .copyText(payload)",
            '"<button>\\(buttonContent)</button>"',
            '"<type>\\(self.messageType(for: message))</type>"',
            'values.joined(separator: "\\n")',
        ):
            self.assertIn(token, candidate)
        self.assertNotIn("displayTitle", candidate)
        self.assertNotIn("compactDisplayTitle", candidate)

    def test_media_and_service_type_map_is_exhaustive_and_prioritized(self) -> None:
        engine = source(ENGINE)
        message_type = swift_block(engine, "private func messageType(for message:")
        action_type = swift_block(engine, "private func actionType(")

        for token in (
            "AdMessageAttribute",
            "TelegramMediaPaidContent",
            "TelegramMediaGiveaway",
            "TelegramMediaGiveawayResults",
            "TelegramMediaDice",
            "TelegramMediaImage",
            "TelegramMediaMap",
            "TelegramMediaContact",
            "TelegramMediaPoll",
            "TelegramMediaTodo",
            "TelegramMediaStory",
            "story.isMention ? 24 : 23",
            "TelegramMediaFile",
            "file.isAnimatedSticker || file.isVideoSticker",
            "file.isSticker",
            "file.isInstantVideo",
            "file.isVoice",
            "file.isMusic",
            "file.isAnimated",
            "file.isVideo",
            "TelegramMediaGame",
            "TelegramMediaInvoice",
            "TelegramMediaWebpage",
            "TelegramMediaExpiredContent",
            "message.text.filter { !$0.isWhitespace }",
            ".containsOnlyEmoji",
        ):
            self.assertIn(token, message_type)

        for token in (
            "case let .photoUpdated(image)",
            "case .suggestedProfilePhoto",
            "case .setChatWallpaper, .setSameChatWallpaper",
            "case .phoneCall, .groupPhoneCall, .conferenceCall",
            "case .giftPremium",
            "case let .giftCode(_, _, _, boostPeerId",
            "boostPeerId == nil ? 18 : 25",
            "case .giftStars, .prizeStars, .starGift, .starGiftUnique, .giftTon",
            "case .giveawayLaunched",
            "case .giveawayResults",
        ):
            self.assertIn(token, action_type)

        expected_types = {
            0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
            18, 19, 21, 22, 23, 24, 25, 26, 28, 29, 30,
        }
        actual_types = {
            int(value)
            for value in re.findall(r"\breturn\s+(\d+)\b", message_type + action_type)
        }
        for left, right in re.findall(
            r"\?\s*(\d+)\s*:\s*(\d+)", message_type + action_type
        ):
            actual_types.update((int(left), int(right)))
        self.assertEqual(expected_types, actual_types)

    def test_blocked_registry_drains_every_page_and_tracks_active_accounts(self) -> None:
        blocked = source(BLOCKED)
        self.assertIn("import Postbox", blocked)
        for token in (
            "public final class GRVMBlockedPeersRegistry",
            "let account: Account",
            "let context: BlockedPeersContext",
            "let disposable = MetaDisposable()",
            "assert(Queue.mainQueue().isCurrent())",
            "BlockedPeersContext(account: account, subject: .blocked)",
            "existing.account === account",
            "[weak self, weak context] state in",
            "Set(state.peers.map(\\.peerId))",
            "!state.isLoadingMore && state.canLoadMore",
            "context.loadMore()",
            "entry.disposable.dispose()",
            "entries.removeValue(forKey: accountPeerId)",
        ):
            self.assertIn(token, blocked)

        update = swift_block(blocked, "public func updateAccounts(")
        self.assertIn("Set(accounts.map(\\.peerId))", update)
        self.assertIn("self.unregister(accountPeerId:", update)
        self.assertIn("self.register(account:", update)

        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        self.assertIn(
            "self.ayuGramFeatureManager?.updateActiveAccounts(accounts.map { $0.1.account })",
            app_delegate,
        )

    def test_manager_atomically_wires_exact_account_engines_and_visibility(self) -> None:
        manager = source(
            "submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift"
        )
        visibility = source(VISIBILITY)
        for token in (
            "Atomic<FilterRuntimeState>",
            "GRVMMessageFilterEngine(",
            "accountPeerId: accountPeerId",
            "registry.service(accountPeerId: accountPeerId)",
            "settingsSnapshot()",
            "AyuGramHooks.isShadowBanned =",
            "AyuGramHooks.isMessageHiddenByFilter =",
            "AyuGramHooks.matchingMessageFilterIds =",
            "AyuGramHooks.isShowingFilteredMessages =",
            "AyuGramHooks.setShowingFilteredMessages =",
            "engine.isMessageHidden(message)",
            "matchingFilterIds(for: message)",
            "self.filteredMessageVisibility.isShowing(",
            "state.blockedPeerIds[accountPeerId] == peerIds",
        ):
            self.assertIn(token, manager)
        self.assertNotIn("primaryService()", manager[manager.index("// MARK: - Filters (W4)") :])
        self.assertNotIn("text: message.text", manager)

        for token in (
            "public final class GRVMFilteredMessageVisibility",
            "Atomic<Set<Key>>",
            "accountPeerId: PeerId",
            "chatPeerId: PeerId",
            "public func isShowing(",
            "public func setShowing(",
            "public func retainAccounts(",
        ):
            self.assertIn(token, visibility)

        coordinator = source(
            "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
        )
        self.assertNotIn("let filters: [NSRegularExpression]", coordinator)
        self.assertNotIn("let reversedFilters: [NSRegularExpression]", coordinator)
        self.assertNotIn("isMessageHiddenByFilter(peerId: Int64, text: String)", coordinator)

    def test_history_passes_full_message_and_honors_per_chat_override(self) -> None:
        history = source(
            "submodules/TelegramUI/Sources/ChatHistoryEntriesForView.swift"
        )
        loop = history[history.index("loop: for entry in view.entries") :]
        self.assertIn(
            "AyuGramHooks.isShowingFilteredMessages?(context.account.peerId, message.id.peerId) != true",
            loop,
        )
        self.assertIn(
            "AyuGramHooks.isMessageHiddenByFilter?(context.account.peerId, message) == true",
            loop,
        )
        self.assertNotIn("message.text)", loop[: loop.index("if case let .replyThread")])

    def test_activity_consumers_use_account_aware_shadow_predicate(self) -> None:
        account = source("submodules/TelegramCore/Sources/Account/Account.swift")
        direct = swift_block(account, "public func peerInputActivities(")
        all_activities = swift_block(account, "public func allPeerInputActivities(")
        for block in (direct, all_activities):
            self.assertIn("AyuGramHooks.isShadowBanned?(self.peerId, peerId)", block)
            self.assertIn("compactMap", block)
            self.assertIn("return nil", block)
        self.assertIn("result[chatPeerId]", all_activities)
        self.assertNotIn("peerId == self.peerId", direct + all_activities)

    def test_reaction_rows_are_account_scoped_without_rewriting_counts(self) -> None:
        reactions = source(
            "submodules/TelegramCore/Sources/State/MessageReactions.swift"
        )
        initial = swift_block(
            reactions,
            "init(accountPeerId: PeerId, message: EngineMessage",
        )
        self.assertIn("if items.count != totalCount", initial)
        self.assertIn("let canLoadMore = items.count != totalCount", initial)
        self.assertIn(
            "items.removeAll(where: { AyuGramHooks.isShadowBanned?(accountPeerId, $0.peer.id) == true })",
            initial,
        )
        self.assertLess(
            initial.index("let canLoadMore = items.count != totalCount"),
            initial.index("items.removeAll(where:"),
        )
        self.assertIn("canLoadMore: canLoadMore", initial)

        impl = swift_block(reactions, "private final class Impl")
        self.assertIn("accountPeerId: account.peerId", impl)
        self.assertIn(
            "AyuGramHooks.isShadowBanned?(accountPeerId, peer.id) != true",
            impl,
        )
        self.assertIn(
            "strongSelf.state.totalCount = max(strongSelf.state.totalCount, state.totalCount)",
            impl,
        )
        self.assertNotIn("totalCount = strongSelf.state.items.count", impl)

        component = source(
            "submodules/Components/ReactionListContextMenuContent/Sources/ReactionListContextMenuContent.swift"
        )
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        self.assertIn(
            "State(accountPeerId: context.account.peerId, message: message",
            component,
        )
        self.assertIn(
            "State(accountPeerId: context.account.peerId, message: EngineMessage(message)",
            context_menu,
        )

        build = source("submodules/AyuGramFeatures/BUILD")
        engine = source(ENGINE)
        self.assertIn("import Emoji", engine)
        self.assertIn('"//submodules/Emoji:Emoji"', build)


if __name__ == "__main__":
    unittest.main()
