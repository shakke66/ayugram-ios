import re
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    path = ROOT / relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _balanced_swift_block(text: str, start: int) -> str:
    opening_brace = text.find("{", start)
    if opening_brace < 0:
        return ""

    depth = 0
    index = opening_brace
    quote = False
    line_comment = False
    block_comment = 0
    while index < len(text):
        char = text[index]
        pair = text[index : index + 2]
        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if pair == "/*":
                block_comment += 1
                index += 1
            elif pair == "*/":
                block_comment -= 1
                index += 1
        elif quote:
            if char == "\\":
                index += 1
            elif char == '"':
                quote = False
        elif pair == "//":
            line_comment = True
            index += 1
        elif pair == "/*":
            block_comment = 1
            index += 1
        elif char == '"':
            quote = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
        index += 1
    return ""


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    return "" if start < 0 else _balanced_swift_block(text, start)


def enclosing_swift_function(text: str, anchor: str) -> str:
    anchor_index = text.find(anchor)
    if anchor_index < 0:
        return ""
    matches = list(
        re.finditer(
            r"(?m)^[ \t]*(?:(?:public|private|fileprivate|internal|open|static|class)\s+)*func\s+",
            text[:anchor_index],
        )
    )
    return "" if not matches else _balanced_swift_block(text, matches[-1].start())


def bounded_window(text: str, anchor: str, before: int = 2500, after: int = 4000) -> str:
    index = text.find(anchor)
    if index < 0:
        return ""
    return text[max(0, index - before) : min(len(text), index + after)]


def bounded_window_last(
    text: str, anchor: str, before: int = 2500, after: int = 4000
) -> str:
    index = text.rfind(anchor)
    if index < 0:
        return ""
    return text[max(0, index - before) : min(len(text), index + after)]


def swift_case_clause(text: str, case_token: str, sibling_tokens: tuple[str, ...]) -> str:
    start = text.find(case_token)
    if start < 0:
        return ""
    ends = [text.find(token, start + len(case_token)) for token in sibling_tokens]
    ends = [index for index in ends if index >= 0]
    end = min(ends) if ends else min(len(text), start + 1600)
    return text[start:end]


def normalized(text: str) -> str:
    return "".join(text.split())


def assert_ordered_tokens(
    test: unittest.TestCase, text: str, tokens: list[str]
) -> None:
    body = normalized(text)
    offset = 0
    for token in tokens:
        expected = normalized(token)
        index = body.find(expected, offset)
        test.assertNotEqual(index, -1, f"Missing ordered token: {token}")
        offset = index + len(expected)


def callback_copy_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.hex()


def simulate_delete_scan(
    pages: list[dict[str, Any]], account_id: int, thread_id: int | None
) -> tuple[int, int, list[list[tuple[int, int]]]]:
    collected: dict[tuple[int, int], None] = {}
    previous_state: object | None = None
    previous_count = 0

    for page in pages:
        for message in page["messages"]:
            if message["namespace"] != "cloud":
                continue
            if message["author_id"] != account_id:
                continue
            if thread_id is not None and message["thread_id"] != thread_id:
                continue
            collected.setdefault(message["id"], None)

        if page["completed"]:
            ids = list(collected)
            batches = [ids[index : index + 100] for index in range(0, len(ids), 100)]
            return len(ids), len(ids), batches

        if page["state"] == previous_state or len(collected) == previous_count:
            return len(collected), 0, []
        previous_state = page["state"]
        previous_count = len(collected)

    return len(collected), 0, []


class PeerMessageReadEngineContractTests(unittest.TestCase):
    engine_path = (
        "submodules/TelegramCore/Sources/TelegramEngine/Messages/"
        "TelegramEngineMessages.swift"
    )
    read_path = (
        "submodules/TelegramCore/Sources/TelegramEngine/Messages/GRVMReadActions.swift"
    )
    bypass_path = "submodules/TelegramCore/Sources/GRVMReadReceiptBypass.swift"
    manager_path = (
        "submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift"
    )
    reply_path = (
        "submodules/TelegramCore/Sources/TelegramEngine/Messages/ReplyThreadHistory.swift"
    )
    account_protocol_path = "submodules/AccountContext/Sources/AccountContext.swift"
    account_impl_path = "submodules/TelegramUI/Sources/AccountContext.swift"

    def test_exact_public_types_and_private_account_forwarders(self) -> None:
        read = source(self.read_path)
        delete = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/"
            "DeleteOwnMessages.swift"
        )
        mode = swift_block(read, "public enum GRVMReadMode")
        for token in ("case automatic", "case localOnly", "case forceServer"):
            self.assertIn(token, mode)

        result = swift_block(delete, "public struct GRVMDeleteOwnMessagesResult")
        for token in (
            "Equatable",
            "public let matchedCount: Int",
            "public let submittedCount: Int",
        ):
            self.assertIn(token, result)

        engine = source(self.engine_path)
        messages = swift_block(engine, "final class Messages")
        self.assertIn("private let account: Account", messages)
        read_forwarder = swift_block(messages, "public func grvmApplyMaxReadIndex(")
        delete_forwarder = swift_block(messages, "public func grvmDeleteOwnMessages(")
        for token in (
            "_ index: MessageIndex",
            "mode: GRVMReadMode",
            "Signal<Void, NoError>",
            "_internal_grvmApplyMaxReadIndex(",
            "account: self.account",
        ):
            self.assertIn(normalized(token), normalized(read_forwarder))
        for token in (
            "peerId: PeerId",
            "threadId: Int64?",
            "Signal<GRVMDeleteOwnMessagesResult, NoError>",
            "account: self.account",
        ):
            self.assertIn(normalized(token), normalized(delete_forwarder))
        self.assertRegex(
            normalized(delete_forwarder),
            r"return_internal_[A-Za-z0-9_]+\(account:self\.account",
        )
        self.assertNotIn("extension TelegramEngine.Messages", read + delete)

    def test_explicit_modes_reject_non_cloud_scope_and_automatic_stays_stock(self) -> None:
        read = source(self.read_path)
        apply = swift_block(read, "func _internal_grvmApplyMaxReadIndex(")
        for token in (
            "index.id.namespace",
            "Namespaces.Message.Cloud",
            "index.id.peerId.namespace",
            "Namespaces.Peer.CloudUser",
            "Namespaces.Peer.CloudGroup",
            "Namespaces.Peer.CloudChannel",
            "case .automatic",
            "_internal_applyMaxReadIndexInteractively(",
            "case .localOnly",
            "case .forceServer",
        ):
            self.assertIn(token, apply)

    def test_local_read_applies_then_confirms_in_one_non_network_transaction(self) -> None:
        apply = swift_block(source(self.read_path), "func _internal_grvmApplyMaxReadIndex(")
        local = bounded_window(apply, "case .localOnly", before=100, after=1800)
        self.assertIn("account.postbox.transaction", local)
        assert_ordered_tokens(
            self,
            local,
            [
                "_internal_applyMaxReadIndexInteractively(",
                "transaction: transaction",
                "stateManager: account.stateManager",
                "index: index",
                "transaction.confirmSynchronizedIncomingReadState(index.id.peerId)",
            ],
        )
        self.assertNotIn("network.request", local)
        self.assertNotIn("synchronizePeerReadState", local)
        self.assertNotIn(".complete()", local)

    def test_force_read_is_deferred_and_registers_before_stock_mutation(self) -> None:
        apply = swift_block(source(self.read_path), "func _internal_grvmApplyMaxReadIndex(")
        force = bounded_window(apply, "case .forceServer", before=100, after=1800)
        assert_ordered_tokens(
            self,
            force,
            [
                "deferred {",
                "GRVMReadReceiptBypass",
                "accountPeerId: account.peerId",
                "peerId: index.id.peerId",
                "maxIncomingReadId: index.id.id",
                "_internal_applyMaxReadIndexInteractively(",
            ],
        )
        self.assertNotIn("afterCompleted", force)
        self.assertNotIn("completed:", force)

    def test_bypass_token_is_exact_expiring_and_one_shot(self) -> None:
        bypass = source(self.bypass_path)
        for token in (
            "Atomic",
            "accountPeerId",
            "peerId",
            "maxIncomingReadId",
            "expiresAt",
            "tokenId",
        ):
            self.assertIn(token, bypass)

        register = swift_block(bypass, "func register(")
        self.assertRegex(register, r"30(?:\.0)?")
        self.assertIn("expiresAt", register)
        self.assertIn("after", register)
        self.assertIn("tokenId", register)
        self.assertRegex(
            normalized(register),
            r"(?:remove|invalidate).*tokenId|tokenId.*(?:remove|invalidate)",
        )

        consume = swift_block(bypass, "func consumeIfMatching(")
        for token in (
            "accountPeerId",
            "peerId",
            "maxIncomingReadId",
            "expiresAt",
            "modify",
        ):
            self.assertIn(token, consume)
        self.assertRegex(consume, r"\.remove(?:All|Value|\()")
        self.assertRegex(
            normalized(consume),
            r"expiresAt(?:<=|>)|(?:now|currentTime)>=.*expiresAt",
        )
        self.assertIn("return true", consume)
        self.assertNotIn("primaryService", bypass)

    def test_manager_consumes_cloud_target_before_force_ghost_normal_branches(self) -> None:
        manager = source(self.manager_path)
        push = bounded_window(manager, "case let .Push", before=0, after=3600)
        for token in (
            "Namespaces.Message.Cloud",
            ".idBased",
            ".indexBased",
            "GRVMReadReceiptBypass",
            "consumeIfMatching",
            "self.stateManager.accountPeerId",
            "peerId",
            "maxIncomingReadId",
            "forceServerRead",
        ):
            self.assertIn(token, push)
        self.assertNotIn(".Push(_, thenSync)", push)
        self.assertRegex(
            normalized(push),
            r"consumeIfMatching\(accountPeerId:self\.stateManager\.accountPeerId,"
            r"peerId:peerId,maxIncomingReadId:",
        )
        assert_ordered_tokens(
            self,
            push,
            [
                "if forceServerRead",
                "synchronizePeerReadState(",
                "else if AyuGramHooks.shouldSuppressReadReceipts?(self.stateManager.accountPeerId) == true",
                "self.postbox.transaction",
                "transaction.confirmSynchronizedIncomingReadState(peerId)",
                "else",
                "synchronizePeerReadState(",
            ],
        )
        self.assertNotIn("signal = .complete()", push)
        self.assertEqual(2, push.count("synchronizePeerReadState("))

    def test_reply_thread_modes_preserve_local_updates_before_network_gate(self) -> None:
        reply_source = source(self.reply_path)
        reply = swift_block(
            reply_source,
            "func applyMaxReadIndex(messageIndex: MessageIndex, mode: GRVMReadMode = .automatic)",
        )
        for token in (
            "setMessageHistoryThreadInfo",
            "_internal_applyMaxReadIndexInteractively",
            "strongSelf.unreadCountValue = unreadCountValue",
            "shouldSuppressReadReceipts",
            ".automatic",
            ".localOnly",
            ".forceServer",
            "readSavedHistory",
            "readDiscussion",
        ):
            self.assertIn(token, reply)
        local_end = reply.index("strongSelf.unreadCountValue = unreadCountValue")
        self.assertLess(local_end, reply.index("readSavedHistory"))
        self.assertLess(local_end, reply.index("readDiscussion"))

        switch_form = "switch mode" in reply
        conditional_form = all(
            token in normalized(reply)
            for token in (
                "mode==.localOnly",
                "mode==.automatic",
                "shouldSuppressReadReceipts",
            )
        )
        self.assertTrue(
            switch_form or conditional_form,
            "Reply-thread network gate must visibly encode the three-mode truth table",
        )
        if switch_form:
            cases = ("case .automatic", "case .localOnly", "case .forceServer")
            automatic = swift_case_clause(reply, cases[0], cases[1:])
            local = swift_case_clause(reply, cases[1], (cases[0], cases[2]))
            force = swift_case_clause(reply, cases[2], cases[:2] + ("default:",))
            self.assertIn("shouldSuppressReadReceipts", automatic)
            self.assertTrue("return" in local or "false" in local)
            self.assertTrue(
                any(token in force for token in ("true", "break", "readSavedHistory", "readDiscussion"))
            )

        public = swift_block(
            reply_source,
            "public func applyMaxReadIndex(messageIndex: MessageIndex, mode: GRVMReadMode = .automatic)",
        )
        self.assertIn("impl.applyMaxReadIndex(messageIndex: messageIndex, mode: mode)", public)

    def test_account_context_adds_exact_mode_route_without_removing_stock_route(self) -> None:
        protocol = source(self.account_protocol_path)
        self.assertIn("func applyMaxReadIndex(for location:", protocol)
        requirement = bounded_window(
            protocol, "func grvmApplyMaxReadIndex(", before=0, after=650
        )
        for token in (
            "for location: ChatLocation",
            "contextHolder: Atomic<ChatLocationContextHolder?>",
            "messageIndex: MessageIndex",
            "mode: GRVMReadMode",
        ):
            self.assertIn(normalized(token), normalized(requirement))

        implementation_source = source(self.account_impl_path)
        implementation = swift_block(
            implementation_source, "public func grvmApplyMaxReadIndex("
        )
        assert_ordered_tokens(
            self,
            implementation,
            [
                "case .peer",
                "self.engine.messages.grvmApplyMaxReadIndex(",
                "mode: mode",
                "case let .replyThread",
                "chatLocationContext(",
                "context.applyMaxReadIndex(messageIndex: messageIndex, mode: mode)",
                "case .customChatContents",
            ],
        )
        self.assertIn("public func applyMaxReadIndex(for location:", implementation_source)

    def test_existing_ghost_contract_tracks_new_reply_signature_and_order_checks(self) -> None:
        ghost_contract = source("Tests/GRVMgramContracts/test_ghost_runtime_contract.py")
        self.assertIn(
            "func applyMaxReadIndex(messageIndex: MessageIndex, "
            "mode: GRVMReadMode = .automatic)",
            ghost_contract,
        )
        for token in (
            "setMessageHistoryThreadInfo",
            "_internal_applyMaxReadIndexInteractively",
            "strongSelf.unreadCountValue = unreadCountValue",
            "readSavedHistory",
            "readDiscussion",
            "assertLess",
        ):
            self.assertIn(token, ghost_contract)


class PeerMessageDeleteEngineContractTests(unittest.TestCase):
    delete_path = (
        "submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteOwnMessages.swift"
    )

    def test_engine_revalidates_group_channel_and_topic_scope(self) -> None:
        delete = source(self.delete_path)
        helper = enclosing_swift_function(delete, "transaction.getPeer(peerId)")
        for token in (
            "account.postbox.transaction",
            "transaction.getPeer(peerId)",
            "TelegramGroup",
            "TelegramChannel",
            "channel.info",
            ".group",
            "threadId",
            "isForumOrMonoForum",
            "account.peerId",
        ):
            self.assertIn(token, helper)
        scope = normalized(helper)
        self.assertRegex(
            scope,
            r"peerId==account\.peerId.*return|guardpeerId!=account\.peerIdelse\{return",
        )
        self.assertRegex(
            scope,
            r"threadId!=nil.*!channel\.isForumOrMonoForum|"
            r"guardthreadId==nil\|\|channel\.isForumOrMonoForum",
        )
        for forbidden in (
            "hasPermission(.deleteAllMessages)",
            "hasPermission(.banMembers)",
            "clearAuthorHistory",
        ):
            self.assertNotIn(forbidden, helper)

    def test_search_location_and_defensive_message_filters_are_exact(self) -> None:
        delete = source(self.delete_path)
        search = enclosing_swift_function(delete, "searchMessages(")
        for token in (
            ".peer(",
            "peerId: peerId",
            "fromId: account.peerId",
            "tags: nil",
            "reactions: nil",
            "threadId: threadId",
            "minDate: nil",
            "maxDate: nil",
            'query: ""',
            "centerId: nil",
            "limit: 100",
            "message.id.namespace == Namespaces.Message.Cloud",
            "message.author?.id == account.peerId",
            "message.threadId == threadId",
        ):
            self.assertIn(normalized(token), normalized(search))

    def test_cumulative_scan_dedupes_and_fails_closed_on_no_progress(self) -> None:
        delete = source(self.delete_path)
        scan = enclosing_swift_function(delete, "searchMessages(")
        for token in (
            "SearchMessagesState",
            "result.messages",
            "result.completed",
            "submittedCount: 0",
        ):
            self.assertIn(normalized(token), normalized(scan))
        self.assertTrue(
            "Set<MessageId>" in scan or re.search(r"\[MessageId\s*:", scan),
            "The cumulative scan must visibly deduplicate MessageId values",
        )

        no_progress = bounded_window_last(
            scan, "submittedCount: 0", before=1800, after=500
        )
        self.assertIn("state", no_progress.lower())
        self.assertIn("count", no_progress.lower())
        self.assertNotIn("deleteMessagesInteractively", no_progress)

    def test_delete_starts_only_after_complete_scan_and_uses_sequential_batches(self) -> None:
        delete = source(self.delete_path)
        helper = enclosing_swift_function(delete, "deleteMessagesInteractively(")
        assert_ordered_tokens(
            self,
            helper,
            [
                "result.completed",
                "deleteMessagesInteractively(",
                "type: .forEveryone",
                "submittedCount:",
            ],
        )
        body = normalized(helper)
        bounded_batch = (
            ("stride(from:" in helper and "by: 100" in helper)
            or ("prefix(100)" in body and "dropFirst" in helper)
            or ("min(" in helper and "100" in helper)
        )
        sequential = any(
            token in body
            for token in ("|>then(", "mapToSignal", "deleteNextBatch(", "deleteBatches(")
        )
        self.assertTrue(bounded_batch, "Deletion batches must contain at most 100 IDs")
        self.assertTrue(sequential, "Deletion batches must be sequenced, not combined")
        self.assertNotIn("removeAllMessagesWithAuthor", delete)
        self.assertNotIn("deleteAllMessages", delete)

    def test_behavior_fixture_dedupes_cumulative_pages_and_batches_in_order(self) -> None:
        account_id = 7
        topic_id = 42

        def message(value: int) -> dict[str, Any]:
            return {
                "id": (1000 + value // 100, value),
                "namespace": "cloud",
                "author_id": account_id,
                "thread_id": topic_id,
            }

        first = [message(value) for value in range(100)]
        second = first + [message(value) for value in range(100, 105)]
        second.extend(
            [
                {**message(200), "namespace": "local"},
                {**message(201), "author_id": 99},
                {**message(202), "thread_id": 77},
            ]
        )
        matched, submitted, batches = simulate_delete_scan(
            [
                {"state": "page-1", "messages": first, "completed": False},
                {"state": "page-2", "messages": second, "completed": True},
            ],
            account_id=account_id,
            thread_id=topic_id,
        )
        self.assertEqual(105, matched)
        self.assertEqual(105, submitted)
        self.assertEqual([100, 5], [len(batch) for batch in batches])
        self.assertEqual([message(value)["id"] for value in range(105)], sum(batches, []))

    def test_behavior_fixture_never_submits_an_incomplete_stalled_scan(self) -> None:
        messages = [
            {
                "id": (100, value),
                "namespace": "cloud",
                "author_id": 7,
                "thread_id": None,
            }
            for value in (1, 2)
        ]
        new_message = {
            "id": (100, 3),
            "namespace": "cloud",
            "author_id": 7,
            "thread_id": None,
        }
        cases = (
            (
                [
                    {"state": "same", "messages": messages, "completed": False},
                    {
                        "state": "same",
                        "messages": messages + [new_message],
                        "completed": False,
                    },
                ],
                3,
            ),
            (
                [
                    {"state": "page-1", "messages": messages, "completed": False},
                    {"state": "page-2", "messages": messages, "completed": False},
                ],
                2,
            ),
        )
        for pages, expected_matched in cases:
            with self.subTest(expected_matched=expected_matched):
                matched, submitted, batches = simulate_delete_scan(
                    pages, account_id=7, thread_id=None
                )
                self.assertEqual(expected_matched, matched)
                self.assertEqual(0, submitted)
                self.assertEqual([], batches)


class PeerMessageUIContractTests(unittest.TestCase):
    context_menu_path = "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
    chat_path = "submodules/TelegramUI/Sources/ChatController.swift"
    chat_list_path = "submodules/ChatListUI/Sources/ChatListController.swift"
    bot_forum_path = "submodules/TelegramUI/Sources/Chat/ChatControllerOpenPeer.swift"
    scroll_path = (
        "submodules/TelegramUI/Sources/ChatControllerScrollToPointInHistory.swift"
    )

    def test_read_message_is_one_incoming_cloud_ghost_scoped_local_action(self) -> None:
        context_menu = source(self.context_menu_path)
        read_message = bounded_window(context_menu, 'text: "Read Message"', 4200, 2200)
        for token in (
            "messages.count == 1",
            "message.flags.contains(.Incoming)",
            "message.id.namespace == Namespaces.Message.Cloud",
            "shouldSuppressReadReceipts?(context.account.peerId) == true",
            ".peer",
            ".replyThread",
            ".scheduledMessages",
            ".customChatContents",
            "Namespaces.Peer.SecretChat",
            "interfaceInteraction.chatController() as? ChatControllerImpl",
            "message.index",
            ".localOnly",
            'Chat/Context Menu/Read',
        ):
            self.assertIn(token, read_message)

    def test_read_all_uses_top_cloud_index_at_action_time_for_both_locations(self) -> None:
        chat = source(self.chat_path)
        target = enclosing_swift_function(
            chat,
            "getTopPeerMessageIndex(peerId: peerId, namespace: Namespaces.Message.Cloud)",
        )
        for token in (
            "self.context.account.postbox.transaction",
            "getTopPeerMessageIndex(peerId: peerId, namespace: Namespaces.Message.Cloud)",
            "getMessageHistoryThreadTopMessage(",
            "self.context.grvmApplyMaxReadIndex(",
            "mode: mode",
        ):
            self.assertIn(normalized(token), normalized(target))
        self.assertTrue(
            normalized("namespaces: [Namespaces.Message.Cloud]") in normalized(target)
            or normalized("namespaces: Set([Namespaces.Message.Cloud])")
            in normalized(target)
        )
        self.assertNotIn("latestMessageInCurrentHistoryView", target)

    def test_header_builder_has_read_pair_ghost_fallback_and_mode_exclusions(self) -> None:
        header = enclosing_swift_function(
            source(self.chat_path), 'text: "Read All Locally"'
        )
        for token in (
            "chatLocationUnreadCount(",
            "|> take(1)",
            "unreadCount > 0",
            "shouldSuppressReadReceipts?(",
            "context.account.peerId",
            'text: "Read All Locally"',
            ".localOnly",
            'text: "Read All on Server"',
            ".forceServer",
            'Chat/Context Menu/Read',
            ".selectionState",
            ".scheduledMessages",
            ".pinnedMessages",
            ".messageOptions",
            ".previewing",
            ".customChatContents",
            ".peer",
            ".replyThread",
            "Namespaces.Peer.SecretChat",
        ):
            self.assertIn(token, header)
        self.assertNotIn("primaryService", header)
        self.assertNotIn(".separator", header)
        self.assertRegex(
            normalized(header),
            r"peerId(?:!=|==)(?:self\.)?context\.account\.peerId",
        )
        header_body = normalized(header)
        self.assertTrue(
            re.search(
                r"unreadCount>0\|\|.*shouldSuppressReadReceipts\?\(", header_body
            )
            or re.search(
                r"shouldSuppressReadReceipts\?\(.*\|\|.*unreadCount>0", header_body
            ),
            "Read All must remain visible for unread local state or effective Ghost suppression",
        )

    def test_delete_own_action_is_group_scoped_and_searches_only_after_confirmation(self) -> None:
        header = enclosing_swift_function(
            source(self.chat_path), 'text: "Delete Own Messages"'
        )
        for token in (
            "TelegramGroup",
            "TelegramChannel",
            "channel.info",
            ".group",
            "isForumOrMonoForum",
            ".scheduledMessages",
            ".customChatContents",
            "textAlertController(",
            "TextAlertAction(type: .destructiveAction",
            "engine.messages.grvmDeleteOwnMessages(",
            'Chat/Context Menu/Delete',
            "textColor: .destructive",
        ):
            self.assertIn(token, header)
        delete_action = bounded_window(
            header, 'text: "Delete Own Messages"', before=200, after=5000
        )
        alert_offset = delete_action.find("textAlertController(")
        self.assertGreaterEqual(alert_offset, 0)
        self.assertNotIn("grvmDeleteOwnMessages(", delete_action[:alert_offset])
        self.assertTrue(
            any(
                token in delete_action[:alert_offset]
                for token in ("dismissWithResult(.default)", "f(.default)", "dismiss(.default)")
            ),
            "The context menu must dismiss before presenting confirmation",
        )
        assert_ordered_tokens(
            self,
            header,
            [
                "textAlertController(",
                "TextAlertAction(type: .destructiveAction",
                "engine.messages.grvmDeleteOwnMessages(",
            ],
        )

    def test_header_actions_reach_avatar_forum_and_bot_forum_stock_menus(self) -> None:
        chat = source(self.chat_path)
        chat_list = source(self.chat_list_path)
        bot_forum = source(self.bot_forum_path)

        forum = swift_block(chat_list, "public static func openMoreMenu(")
        bot = swift_block(bot_forum, "func openBotForumMoreMenu(")
        for owner in (forum, bot):
            self.assertIn(
                normalized("additionalItems: [ContextMenuItem] = []"),
                normalized(owner),
            )
            self.assertIn(
                normalized("if !items.isEmpty && !additionalItems.isEmpty"),
                normalized(owner),
            )
            assert_ordered_tokens(
                self,
                owner,
                [
                    "if !items.isEmpty && !additionalItems.isEmpty",
                    "items.append(.separator)",
                    "items.append(contentsOf: additionalItems)",
                ],
            )

        avatar = bounded_window(chat, "avatarNode.contextAction", 100, 17000)
        self.assertRegex(
            avatar,
            r"items\.append\(contentsOf:\s*(?:strongSelf\.)?"
            r"grvm(?!Archive)[A-Za-z0-9_]+\(",
        )

        more = bounded_window(chat, "self.moreBarButton.contextAction", 100, 4000)
        self.assertIn("additionalItems:", more)
        self.assertIn("ChatListControllerImpl.openMoreMenu", more)
        self.assertIn("openBotForumMoreMenu", more)
        self.assertEqual(1, chat_list.count("additionalItems:"))

        self.assertIn("grvmArchiveContextMenuItems(", avatar)
        self.assertIn("grvmArchiveContextMenuItems(", forum)
        self.assertIn("grvmArchiveContextMenuItems(", bot)

    def test_jump_calls_existing_lower_bound_helper_without_reimplementing_history(self) -> None:
        chat = source(self.chat_path)
        jump = bounded_window(chat, 'text: "Jump to Beginning"', 1500, 1800)
        self.assertIn("scrollToStartOfHistory()", jump)
        self.assertIn('Chat/Context Menu/GoToMessage', jump)

        scroll = swift_block(source(self.scroll_path), "func scrollToStartOfHistory()")
        self.assertEqual(1, scroll.count("ChatHistoryLocationInput("))
        self.assertIn("subject: MessageHistoryScrollToSubject(index: .lowerBound", scroll)
        self.assertIn("anchorIndex: .lowerBound", scroll)
        self.assertIn("sourceIndex: .upperBound", scroll)
        self.assertNotIn("searchMessages", scroll)
        self.assertNotIn("enumerate", scroll)


class PeerMessageCallbackCopyContractTests(unittest.TestCase):
    button_path = (
        "submodules/TelegramUI/Components/Chat/ChatMessageItemView/Sources/"
        "ChatMessageItemView.swift"
    )

    def test_behavior_fixture_prefers_utf8_then_lowercase_two_digit_hex(self) -> None:
        self.assertEqual("callback payload", callback_copy_text(b"callback payload"))
        self.assertEqual("000fff80", callback_copy_text(bytes([0x00, 0x0F, 0xFF, 0x80])))

    def test_long_press_preserves_url_and_adds_callback_conversion(self) -> None:
        method = swift_block(
            source(self.button_path), "open func presentMessageButtonContextMenu("
        )
        self.assertIn("case let .url(url)", method)
        self.assertIn("item.controllerInteraction.longTap(.url(url)", method)

        callback = bounded_window(method, "case let .callback(_, data)", 100, 2600)
        for token in (
            "let bytes = data.makeData()",
            "String(data: bytes, encoding: .utf8)",
            'String(format: "%02x"',
            ".joined()",
        ):
            self.assertIn(token, callback)

    def test_callback_sheet_copies_only_on_copy_action_and_never_executes_callback(self) -> None:
        method = swift_block(
            source(self.button_path), "open func presentMessageButtonContextMenu("
        )
        callback = bounded_window(method, "case let .callback(_, data)", 100, 4000)
        for token in (
            "item.context.sharedContext.currentPresentationData",
            "ActionSheetController(presentationData:",
            'title: "Copy Callback Data"',
            "UIPasteboard.general.string",
            "ActionSheetButtonItem",
            "Cancel",
        ):
            self.assertIn(token, callback)
        assert_ordered_tokens(
            self,
            callback,
            ['title: "Copy Callback Data"', "UIPasteboard.general.string"],
        )
        self.assertEqual(1, callback.count("UIPasteboard.general.string"))
        self.assertNotIn("requestMessageActionCallback", method)
        self.assertNotIn("performMessageButtonAction", method)


if __name__ == "__main__":
    unittest.main()
