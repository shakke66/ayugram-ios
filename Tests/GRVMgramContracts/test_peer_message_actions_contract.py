import ast
import re
import struct
import textwrap
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


def _balanced_swift_delimiter_end(
    text: str, opening_index: int, opening: str, closing: str
) -> int:
    if opening_index < 0 or opening_index >= len(text) or text[opening_index] != opening:
        return -1

    depth = 0
    index = opening_index
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
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def swift_call(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        return ""
    opening = text.find("(", start)
    closing = _balanced_swift_delimiter_end(text, opening, "(", ")")
    return "" if closing < 0 else text[start : closing + 1]


def swift_enclosing_call(text: str, anchor: str) -> str:
    anchor_index = text.find(anchor)
    if anchor_index < 0:
        return ""
    opening = text.rfind("(", 0, anchor_index + 1)
    while opening >= 0:
        closing = _balanced_swift_delimiter_end(text, opening, "(", ")")
        if closing >= anchor_index:
            return text[opening : closing + 1]
        opening = text.rfind("(", 0, opening)
    return ""


def swift_named_closure(call: str, label: str) -> str:
    match = re.search(rf"\b{re.escape(label)}\s*:\s*\{{", call)
    return "" if match is None else _balanced_swift_block(call, match.start())


def swift_closure_matching(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return "" if match is None else _balanced_swift_block(text, match.start())


def _swift_control_body_open(text: str, start: int) -> int:
    index = start
    parenthesis_depth = 0
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
        elif char == "(":
            parenthesis_depth += 1
        elif char == ")" and parenthesis_depth:
            parenthesis_depth -= 1
        elif char == "{" and parenthesis_depth == 0:
            return index
        index += 1
    return -1


def swift_control_statement(
    text: str,
    anchor: str,
    keywords: tuple[str, ...] = ("if", "guard", "switch", "for", "while"),
) -> str:
    anchor_index = text.find(anchor)
    if anchor_index < 0:
        return ""
    keyword_pattern = re.compile(rf"\b({'|'.join(map(re.escape, keywords))})\b")
    candidates = list(keyword_pattern.finditer(text, 0, anchor_index + len(anchor)))
    for candidate in reversed(candidates):
        opening = _swift_control_body_open(text, candidate.start())
        if opening < 0:
            continue
        block = _balanced_swift_block(text, opening)
        if not block:
            continue
        end = opening + len(block) - 1
        if candidate.group(1) == "if":
            cursor = end + 1
            while True:
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
                if not text.startswith("else", cursor):
                    break
                else_opening = _swift_control_body_open(text, cursor)
                if else_opening < 0:
                    break
                else_block = _balanced_swift_block(text, else_opening)
                if not else_block:
                    break
                end = else_opening + len(else_block) - 1
                cursor = end + 1
        if candidate.start() <= anchor_index <= end:
            return text[candidate.start() : end + 1]
    return ""


def python_assigned_call(
    text: str, target_name: str, function_name: str
) -> ast.Call | None:
    try:
        tree = ast.parse(textwrap.dedent(text))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == target_name for target in targets):
            continue
        value = node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id == function_name:
                return value
    return None


def swift_enclosing_statement(text: str, anchor: str) -> str:
    anchor_index = text.find(anchor)
    if anchor_index < 0:
        return ""

    stack: list[int] = []
    containing: list[tuple[int, int]] = []
    index = 0
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
            stack.append(index)
        elif char == "}" and stack:
            opening = stack.pop()
            if opening < anchor_index < index:
                containing.append((opening, index))
        index += 1

    if not containing:
        return ""
    opening, closing = max(containing, key=lambda pair: pair[0])
    prefix_start = max(0, opening - 3000)
    prefix = text[prefix_start:opening]
    statements = list(
        re.finditer(
            r"(?m)^[ \t]*(?:if|for|while|switch|func|(?:let|var)\s+[A-Za-z_])\b",
            prefix,
        )
    )
    start = prefix_start + statements[-1].start() if statements else opening
    return text[start : closing + 1]


def python_function(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        return ""
    line_start = text.rfind("\n", 0, start) + 1
    indent = len(text[line_start:start])
    pattern = re.compile(
        rf"(?m)^[ ]{{0,{indent}}}(?:def |class |if __name__)"
    )
    match = pattern.search(text, start + len(signature))
    end = match.start() if match else len(text)
    return text[line_start:end]


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
    switch = swift_control_statement(text, case_token, keywords=("switch",))
    scope = switch or text
    start = scope.find(case_token)
    if start < 0:
        return ""
    ends = [scope.find(token, start + len(case_token)) for token in sibling_tokens]
    ends = [index for index in ends if index >= 0]
    end = min(ends) if ends else len(scope)
    return scope[start:end]


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


def cloud_read_state(max_incoming_read_id: int, marked_unread: bool = False) -> tuple:
    return (
        (
            "cloud",
            (
                "idBased",
                max_incoming_read_id,
                max_incoming_read_id,
                max_incoming_read_id,
                0,
                marked_unread,
            ),
        ),
    )


def cloud_max_incoming_read_id(state: tuple | None) -> int | None:
    if state is None:
        return None
    for namespace, read_state in state:
        if namespace == "cloud":
            return read_state[1]
    return None


class ReadReceiptBypassModel:
    def __init__(self, nonce_candidates: list[tuple[int, int]]) -> None:
        self._nonce_candidates = iter(nonce_candidates)
        self.entries: dict[tuple[int, int], dict[str, Any]] = {}

    def register(
        self,
        account_peer_id: int,
        peer_id: int,
        max_incoming_read_id: int,
        state: tuple,
        now: int,
    ) -> tuple[int, int]:
        self.entries = {
            token_id: entry
            for token_id, entry in self.entries.items()
            if entry["expires_at"] > now
        }
        while True:
            token_id = next(self._nonce_candidates)
            if token_id != (0, 0) and token_id not in self.entries:
                break
        self.entries[token_id] = {
            "account_peer_id": account_peer_id,
            "peer_id": peer_id,
            "max_incoming_read_id": max_incoming_read_id,
            "state": state,
            "expires_at": now + 30,
        }
        return token_id

    def consume_if_matching(
        self,
        token_id: tuple[int, int],
        account_peer_id: int,
        peer_id: int,
        max_incoming_read_id: int | None,
        state: tuple | None,
        now: int,
    ) -> bool:
        self.entries = {
            entry_token_id: entry
            for entry_token_id, entry in self.entries.items()
            if entry["expires_at"] > now
        }
        entry = self.entries.pop(token_id, None)
        return entry is not None and all(
            (
                entry["account_peer_id"] == account_peer_id,
                entry["peer_id"] == peer_id,
                entry["max_incoming_read_id"] == max_incoming_read_id,
                entry["state"] == state,
            )
        )


def push_operation(state: tuple | None, then_sync: bool = True) -> dict[str, Any]:
    return {"kind": "push", "state": state, "then_sync": then_sync}


def force_push_operation(
    state: tuple | None,
    token_id: tuple[int, int],
    then_sync: bool = True,
) -> dict[str, Any]:
    return {
        "kind": "forcePush",
        "state": state,
        "then_sync": then_sync,
        "token_id": token_id,
    }


def process_read_operation(
    operation: dict[str, Any],
    registry: ReadReceiptBypassModel,
    account_peer_id: int,
    peer_id: int,
    live_state: tuple | None,
    ghost_enabled: bool,
    now: int,
) -> tuple[list[tuple[str, tuple | None]], bool]:
    if operation["kind"] == "push":
        if ghost_enabled:
            return [], True
        return [("stock", live_state)], False

    state = operation["state"]
    claimed = registry.consume_if_matching(
        operation["token_id"],
        account_peer_id,
        peer_id,
        cloud_max_incoming_read_id(state),
        state,
        now,
    )
    if claimed and state is not None:
        return [("exact", state)], False
    if ghost_enabled:
        return [], True
    return [("stock", live_state)], False


def encode_synchronize_read_operation(operation: dict[str, Any]) -> bytes:
    if operation["kind"] == "push":
        return bytes((0, int(operation["then_sync"])))
    if operation["kind"] == "validate":
        return bytes((1,))
    high, low = operation["token_id"]
    return struct.pack("<BBqq", 2, int(operation["then_sync"]), high, low)


def decode_synchronize_read_operation(data: bytes, state: tuple | None) -> dict[str, Any]:
    if not data:
        return {"kind": "validate"}
    if data[0] == 0:
        if len(data) != 2:
            return {"kind": "validate"}
        return push_operation(state, data[1] != 0)
    if data[0] == 1:
        return {"kind": "validate"}
    if data[0] == 2:
        if len(data) != 18 or data[1] not in (0, 1):
            return {"kind": "validate"}
        _, then_sync, high, low = struct.unpack("<BBqq", data)
        if high == 0 and low == 0:
            return {"kind": "validate"}
        return force_push_operation(state, (high, low), bool(then_sync))
    return {"kind": "validate"}


def legacy_decode_synchronize_read_operation(
    data: bytes, state: tuple | None
) -> dict[str, Any]:
    if not data:
        return {"kind": "validate"}
    if data[0] == 0 and len(data) >= 2:
        return push_operation(state, data[1] != 0)
    return {"kind": "validate"}


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
    synchronize_path = (
        "submodules/TelegramCore/Sources/State/SynchronizePeerReadState.swift"
    )
    reply_path = (
        "submodules/TelegramCore/Sources/TelegramEngine/Messages/ReplyThreadHistory.swift"
    )
    postbox_path = "submodules/Postbox/Sources/Postbox.swift"
    synchronize_table_path = (
        "submodules/Postbox/Sources/MessageHistorySynchronizeReadStateTable.swift"
    )
    account_protocol_path = "submodules/AccountContext/Sources/AccountContext.swift"
    account_impl_path = "submodules/TelegramUI/Sources/AccountContext.swift"

    def test_exact_read_mode_and_private_account_forwarder(self) -> None:
        read = source(self.read_path)
        mode = swift_block(read, "public enum GRVMReadMode")
        for token in ("case automatic", "case localOnly", "case forceServer"):
            self.assertIn(token, mode)

        engine = source(self.engine_path)
        messages = swift_block(engine, "final class Messages")
        self.assertIn("private let account: Account", messages)
        read_forwarder = swift_block(messages, "public func grvmApplyMaxReadIndex(")
        for token in (
            "_ index: MessageIndex",
            "mode: GRVMReadMode",
            "Signal<Void, NoError>",
            "_internal_grvmApplyMaxReadIndex(",
            "account: self.account",
        ):
            self.assertIn(normalized(token), normalized(read_forwarder))
        self.assertNotIn("extension TelegramEngine.Messages", read)

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
        self.assertIn(
            "(index.id.peerId.namespace",
            normalized(apply),
            "Cloud peer alternatives must be grouped under the Cloud message guard",
        )

    def test_local_read_applies_then_confirms_in_one_non_network_transaction(self) -> None:
        apply = swift_block(source(self.read_path), "func _internal_grvmApplyMaxReadIndex(")
        local = bounded_window(apply, "case .localOnly", before=100, after=2600)
        self.assertIn("account.postbox.transaction", local)
        assert_ordered_tokens(
            self,
            local,
            [
                "transaction.getPeerCachedData(peerId: index.id.peerId)",
                "associatedHistoryMessageId",
                "_internal_applyMaxReadIndexInteractively(",
                "transaction: transaction",
                "stateManager: account.stateManager",
                "index: index",
                "transaction.confirmSynchronizedIncomingReadState(index.id.peerId)",
                "transaction.confirmSynchronizedIncomingReadState(associatedHistoryMessageId.peerId)",
            ],
        )
        self.assertIn("CachedChannelData", local)
        self.assertNotIn("network.request", local)
        self.assertNotIn("synchronizePeerReadState", local)
        self.assertNotIn(".complete()", local)

    def test_force_read_binds_each_peer_to_its_exact_state_and_nonce(self) -> None:
        apply = swift_block(source(self.read_path), "func _internal_grvmApplyMaxReadIndex(")
        force = bounded_window(apply, "case .forceServer", before=100, after=4800)
        loop = swift_control_statement(
            force, "GRVMReadReceiptBypass.shared.register(", keywords=("for",)
        )
        self.assertTrue(loop, "Force registration must stay inside the per-peer loop")
        assert_ordered_tokens(
            self,
            loop,
            [
                "transaction.getCombinedPeerReadState(peerId)",
                "let forceTokenId = GRVMReadReceiptBypass.shared.register(",
                "accountPeerId: account.peerId",
                "peerId: peerId",
                "maxIncomingReadId: maxIncomingReadId",
                "state: combinedPeerReadState",
                "transaction.forceSynchronizeIncomingReadState(",
                "peerId",
                "state: combinedPeerReadState",
                "forceTokenId: forceTokenId",
            ],
        )
        for token in (
            "var forcePeerIds = [index.id.peerId]",
            "associatedHistoryMessageId.peerId",
            "forcePeerIds.append",
            "Namespaces.Message.Cloud",
            "case let .idBased",
            "case let .indexBased",
        ):
            self.assertIn(token, force)
        self.assertEqual(1, loop.count("GRVMReadReceiptBypass.shared.register("))
        self.assertEqual(1, loop.count("transaction.forceSynchronizeIncomingReadState("))
        self.assertNotIn("afterCompleted", force)
        self.assertNotIn("completed:", force)

    def test_force_sync_transaction_api_queues_given_snapshot_and_token(self) -> None:
        postbox = source(self.postbox_path)
        public_api = swift_block(
            postbox, "public func forceSynchronizeIncomingReadState("
        )
        for token in (
            "_ peerId: PeerId",
            "state: CombinedPeerReadState",
            "forceTokenId: PeerReadStateSynchronizationForceTokenId",
            "self.postbox?.forceSynchronizeIncomingReadState(",
            "peerId",
            "state: state",
            "forceTokenId: forceTokenId",
        ):
            self.assertIn(normalized(token), normalized(public_api))

        implementation = swift_block(
            postbox, "fileprivate func forceSynchronizeIncomingReadState("
        )
        assert_ordered_tokens(
            self,
            implementation,
            [
                "self.synchronizeReadStateTable.set(",
                "peerId",
                ".ForcePush(",
                "state: state",
                "thenSync: true",
                "tokenId: forceTokenId",
                "currentUpdatedSynchronizeReadStateOperations",
            ],
        )
        self.assertNotIn("getCombinedState", implementation)

    def test_force_operation_identity_and_persistent_format_are_explicit(self) -> None:
        table = source(self.synchronize_table_path)
        token_type = swift_block(
            table, "public struct PeerReadStateSynchronizationForceTokenId"
        )
        for token in (
            "Equatable",
            "public let high: Int64",
            "public let low: Int64",
            "public init(high: Int64, low: Int64)",
        ):
            self.assertIn(normalized(token), normalized(token_type))

        operation = swift_block(table, "public enum PeerReadStateSynchronizationOperation")
        for token in (
            "case Push(state: CombinedPeerReadState?, thenSync: Bool)",
            "case Validate",
            "case ForcePush(",
            "state: CombinedPeerReadState?",
            "thenSync: Bool",
            "tokenId: PeerReadStateSynchronizationForceTokenId",
        ):
            self.assertIn(normalized(token), normalized(operation))

        decoder = swift_block(table, "func get(")
        self.assertGreaterEqual(decoder.find("value.length"), 0)
        self.assertLess(decoder.find("value.length"), decoder.find("value.read("))
        for token in (
            "case 0",
            ".Push(state: getCombinedPeerReadState(peerId)",
            "case 1",
            "case 2",
            "value.length == 18",
            "syncValue == 0 || syncValue == 1",
            "PeerReadStateSynchronizationForceTokenId(high: high, low: low)",
            ".ForcePush(",
            "default",
            ".Validate",
        ):
            self.assertIn(normalized(token), normalized(decoder))
        self.assertRegex(
            normalized(decoder),
            r"(?:high==0&&low==0|low==0&&high==0)",
        )

        encoder = swift_block(table, "override func beforeCommit()")
        force_encoder = swift_case_clause(
            encoder, "case let .ForcePush", ("case let .Push", "case .Validate")
        )
        for token in (
            "var operationValue: Int8 = 2",
            "var syncValue: Int8 = thenSync ? 1 : 0",
            "var high = tokenId.high",
            "var low = tokenId.low",
        ):
            self.assertIn(normalized(token), normalized(force_encoder))
        self.assertEqual(4, force_encoder.count("buffer.write("))
        self.assertEqual(2, normalized(force_encoder).count("length:8"))

    def test_operation_encoding_round_trips_and_old_decoder_fails_closed(self) -> None:
        state = cloud_read_state(41, marked_unread=True)
        operations = (
            push_operation(state, False),
            push_operation(state, True),
            {"kind": "validate"},
            force_push_operation(state, (7, -9), True),
        )
        self.assertEqual(b"\x00\x00", encode_synchronize_read_operation(operations[0]))
        self.assertEqual(b"\x00\x01", encode_synchronize_read_operation(operations[1]))
        self.assertEqual(b"\x01", encode_synchronize_read_operation(operations[2]))
        for operation in operations:
            with self.subTest(operation=operation["kind"]):
                encoded = encode_synchronize_read_operation(operation)
                self.assertEqual(
                    operation,
                    decode_synchronize_read_operation(encoded, state),
                )

        force_bytes = encode_synchronize_read_operation(operations[-1])
        self.assertEqual(18, len(force_bytes))
        for length in range(18):
            self.assertEqual(
                {"kind": "validate"},
                decode_synchronize_read_operation(force_bytes[:length], state),
            )
        self.assertEqual(
            {"kind": "validate"},
            decode_synchronize_read_operation(force_bytes + b"\x00", state),
        )
        malformed_then_sync = bytearray(force_bytes)
        malformed_then_sync[1] = 2
        self.assertEqual(
            {"kind": "validate"},
            decode_synchronize_read_operation(bytes(malformed_then_sync), state),
        )
        self.assertEqual(
            {"kind": "validate"},
            decode_synchronize_read_operation(
                encode_synchronize_read_operation(
                    force_push_operation(state, (0, 0), True)
                ),
                state,
            ),
        )
        self.assertEqual(
            {"kind": "validate"},
            decode_synchronize_read_operation(b"\x7f", state),
        )
        self.assertEqual(
            {"kind": "validate"},
            legacy_decode_synchronize_read_operation(force_bytes, state),
        )
        self.assertEqual(
            push_operation(state, True),
            legacy_decode_synchronize_read_operation(b"\x00\x01", state),
        )

    def test_bypass_source_uses_random_128_bit_token_first_consumption(self) -> None:
        bypass = source(self.bypass_path)
        entry = swift_block(bypass, "private struct Entry")
        for token in (
            "tokenId: PeerReadStateSynchronizationForceTokenId",
            "accountPeerId: PeerId",
            "peerId: PeerId",
            "maxIncomingReadId: MessageId.Id",
            "state: CombinedPeerReadState",
            "expiresAt: Double",
        ):
            self.assertIn(normalized(token), normalized(entry))
        for forbidden in ("nextTokenId", "Atomic<Int64>", "&+"):
            self.assertNotIn(forbidden, bypass)

        register = swift_block(bypass, "func register(")
        register_modify = swift_closure_matching(
            register, r"(?:self\.)?entries\s*\.modify\s*\{"
        )
        for token in (
            "state: CombinedPeerReadState",
            "PeerReadStateSynchronizationForceTokenId",
            "UInt64.random",
            "entries.contains",
            "entry.tokenId == tokenId",
            "expiresAt",
            "self.queue.after(30.0",
        ):
            self.assertIn(normalized(token), normalized(register))
        self.assertTrue(register_modify)
        self.assertIn("UInt64.random", register_modify)
        self.assertIn("entries.contains", register_modify)
        self.assertRegex(
            normalized(register_modify),
            r"(?:tokenId\.high!=0\|\|tokenId\.low!=0|"
            r"tokenId\.high==0&&tokenId\.low==0)",
        )

        consume = swift_block(bypass, "func consumeIfMatching(")
        for token in (
            "tokenId: PeerReadStateSynchronizationForceTokenId",
            "accountPeerId: PeerId",
            "peerId: PeerId",
            "maxIncomingReadId: MessageId.Id?",
            "state: CombinedPeerReadState?",
            "entries.removeAll",
            "entry.tokenId == tokenId",
            "let entry = entries.remove(at: index)",
            "entry.accountPeerId == accountPeerId",
            "entry.peerId == peerId",
            "entry.maxIncomingReadId == maxIncomingReadId",
            "entry.state == state",
        ):
            self.assertIn(normalized(token), normalized(consume))
        consume_body = normalized(consume)
        self.assertLess(consume_body.find("entries.removeAll"), consume_body.find("firstIndex"))
        self.assertLess(consume_body.find("entries.remove(at:index)"), consume_body.find("entry.accountPeerId==accountPeerId"))
        self.assertEqual(1, consume_body.count("firstIndex"))

    def test_bypass_behavior_is_token_scoped_exact_and_one_shot(self) -> None:
        state = cloud_read_state(30)
        wrong_state = cloud_read_state(30, marked_unread=True)

        missing = ReadReceiptBypassModel([])
        self.assertFalse(missing.consume_if_matching((9, 9), 10, 20, 30, state, 100))

        expired = ReadReceiptBypassModel([(1, 1)])
        expired_token = expired.register(10, 20, 30, state, 100)
        self.assertFalse(
            expired.consume_if_matching(expired_token, 10, 20, 30, state, 130)
        )
        self.assertNotIn(expired_token, expired.entries)

        wrong_token = ReadReceiptBypassModel([(1, 1), (2, 2)])
        correct_token = wrong_token.register(10, 20, 30, state, 100)
        other_token = wrong_token.register(10, 21, 31, cloud_read_state(31), 100)
        self.assertFalse(
            wrong_token.consume_if_matching(other_token, 10, 20, 30, state, 100)
        )
        self.assertNotIn(other_token, wrong_token.entries)
        self.assertIn(correct_token, wrong_token.entries)

        mismatches = (
            (11, 20, 30, state),
            (10, 21, 30, state),
            (10, 20, 31, state),
            (10, 20, 30, wrong_state),
        )
        for index, arguments in enumerate(mismatches, start=10):
            registry = ReadReceiptBypassModel([(index, index)])
            token_id = registry.register(10, 20, 30, state, 100)
            self.assertFalse(
                registry.consume_if_matching(token_id, *arguments, now=100)
            )
            self.assertNotIn(token_id, registry.entries)
            self.assertFalse(
                registry.consume_if_matching(token_id, 10, 20, 30, state, 100)
            )

        exact = ReadReceiptBypassModel([(30, 30)])
        exact_token = exact.register(10, 20, 30, state, 100)
        self.assertTrue(
            exact.consume_if_matching(exact_token, 10, 20, 30, state, 100)
        )
        self.assertFalse(
            exact.consume_if_matching(exact_token, 10, 20, 30, state, 100)
        )

    def test_main_migrated_and_repeated_forces_have_distinct_identity(self) -> None:
        registry = ReadReceiptBypassModel(
            [(0, 0), (1, 2), (1, 2), (3, 4), (5, 6)]
        )
        main_state = cloud_read_state(40)
        migrated_state = cloud_read_state(25)
        main_token = registry.register(10, 20, 40, main_state, 100)
        migrated_token = registry.register(10, 21, 25, migrated_state, 100)
        repeated_token = registry.register(10, 20, 40, main_state, 100)
        self.assertEqual(3, len({main_token, migrated_token, repeated_token}))
        self.assertNotEqual(
            force_push_operation(main_state, main_token),
            force_push_operation(main_state, repeated_token),
        )

    def test_restart_stale_nonce_cannot_claim_new_registration(self) -> None:
        state = cloud_read_state(50)
        before_restart = ReadReceiptBypassModel([(7, 8)])
        stale_token = before_restart.register(10, 20, 50, state, 100)
        stale_operation = force_push_operation(state, stale_token)

        after_restart = ReadReceiptBypassModel([(9, 10)])
        fresh_token = after_restart.register(10, 20, 50, state, 100)
        rpc, confirmed = process_read_operation(
            stale_operation, after_restart, 10, 20, state, True, 100
        )
        self.assertEqual([], rpc)
        self.assertTrue(confirmed)
        self.assertIn(fresh_token, after_restart.entries)

        fresh_rpc, _ = process_read_operation(
            force_push_operation(state, fresh_token),
            after_restart,
            10,
            20,
            state,
            True,
            100,
        )
        self.assertEqual([("exact", state)], fresh_rpc)

    def test_exact_snapshot_remains_rpc_target_after_live_state_advances(self) -> None:
        exact_state = cloud_read_state(60, marked_unread=True)
        live_state = cloud_read_state(61, marked_unread=False)
        registry = ReadReceiptBypassModel([(11, 12)])
        token_id = registry.register(10, 20, 60, exact_state, 100)
        rpc, confirmed = process_read_operation(
            force_push_operation(exact_state, token_id),
            registry,
            10,
            20,
            live_state,
            True,
            100,
        )
        self.assertEqual([("exact", exact_state)], rpc)
        self.assertFalse(confirmed)
        self.assertNotEqual(live_state, rpc[0][1])

    def test_active_stock_push_keeps_force_pending_for_one_exact_rpc(self) -> None:
        state = cloud_read_state(70)
        registry = ReadReceiptBypassModel([(13, 14)])
        token_id = registry.register(10, 20, 70, state, 100)
        active = push_operation(state)
        incoming = force_push_operation(state, token_id)
        self.assertNotEqual(active, incoming)
        pending = incoming if active != incoming else None

        old_rpc, old_confirmed = process_read_operation(
            active, registry, 10, 20, state, True, 100
        )
        self.assertEqual([], old_rpc)
        self.assertTrue(old_confirmed)
        self.assertIn(token_id, registry.entries, "Stock Push must not consume force token")

        self.assertIsNotNone(pending)
        assert pending is not None
        forced_rpc, forced_confirmed = process_read_operation(
            pending, registry, 10, 20, cloud_read_state(71), True, 100
        )
        self.assertEqual([("exact", state)], forced_rpc)
        self.assertFalse(forced_confirmed)
        self.assertNotIn(token_id, registry.entries)

    def test_force_mismatch_falls_back_closed_by_ghost_mode(self) -> None:
        registered_state = cloud_read_state(80)
        mismatched_state = cloud_read_state(80, marked_unread=True)
        live_state = cloud_read_state(81)

        ghost_registry = ReadReceiptBypassModel([(15, 16)])
        ghost_token = ghost_registry.register(10, 20, 80, registered_state, 100)
        ghost_rpc, ghost_confirmed = process_read_operation(
            force_push_operation(mismatched_state, ghost_token),
            ghost_registry,
            10,
            20,
            live_state,
            True,
            100,
        )
        self.assertEqual([], ghost_rpc)
        self.assertTrue(ghost_confirmed)
        self.assertNotIn(ghost_token, ghost_registry.entries)

        normal_registry = ReadReceiptBypassModel([(17, 18)])
        normal_token = normal_registry.register(10, 20, 80, registered_state, 100)
        normal_rpc, normal_confirmed = process_read_operation(
            force_push_operation(mismatched_state, normal_token),
            normal_registry,
            10,
            20,
            live_state,
            False,
            100,
        )
        self.assertEqual([("stock", live_state)], normal_rpc)
        self.assertFalse(normal_confirmed)
        self.assertNotIn(normal_token, normal_registry.entries)

    def test_manager_separates_stock_and_force_paths(self) -> None:
        manager = source(self.manager_path)
        push = swift_case_clause(
            manager, "case let .Push", ("case .Validate", "case let .ForcePush")
        )
        force = swift_case_clause(
            manager, "case let .ForcePush", ("case .Validate", "case let .Push")
        )
        self.assertTrue(push)
        self.assertTrue(force)
        self.assertNotIn("GRVMReadReceiptBypass", push)
        self.assertNotIn("consumeIfMatching", push)
        self.assertNotIn("exactPushState", push)
        for token in (
            "AyuGramHooks.shouldSuppressReadReceipts",
            "transaction.confirmSynchronizedIncomingReadState(peerId)",
            "synchronizePeerReadState(",
            "push: true",
            "validate: thenSync",
        ):
            self.assertIn(token, push)

        for token in (
            "state: pushState",
            "thenSync: thenSync",
            "tokenId: tokenId",
            "Namespaces.Message.Cloud",
            "GRVMReadReceiptBypass.shared.consumeIfMatching(",
            "tokenId: tokenId",
            "accountPeerId: self.stateManager.accountPeerId",
            "peerId: peerId",
            "maxIncomingReadId: maxIncomingReadId",
            "state: pushState",
            "if forceServerRead, let pushState = pushState",
            "exactPushState: pushState",
            "validate: thenSync",
            "else if AyuGramHooks.shouldSuppressReadReceipts",
            "transaction.confirmSynchronizedIncomingReadState(peerId)",
            "else",
            "push: true",
        ):
            self.assertIn(normalized(token), normalized(force))
        self.assertEqual(1, force.count("consumeIfMatching("))
        self.assertEqual(1, force.count("exactPushState:"))

    def test_exact_push_overload_selects_snapshot_before_rpc_and_keeps_full_state(self) -> None:
        synchronize = source(self.synchronize_path)
        exact = enclosing_swift_function(
            synchronize, "exactPushState: CombinedPeerReadState"
        )
        self.assertTrue(exact)
        for token in (
            "exactPushState.states",
            "Namespaces.Message.Cloud",
            "Namespaces.Message.SecretIncoming",
            "pushPeerReadState(",
            "readState: readState",
            "validatePeerReadState(",
        ):
            self.assertIn(token, exact)
        rpc_offset = exact.find("pushPeerReadState(")
        self.assertGreaterEqual(rpc_offset, 0)
        before_rpc = exact[:rpc_offset]
        self.assertNotIn("getPeerReadStates", before_rpc)
        self.assertNotIn("getCombinedPeerReadState", before_rpc)
        self.assertNotIn("postbox.transaction", before_rpc)

        low_level = swift_block(
            synchronize,
            "private func pushPeerReadState(network: Network, postbox: Postbox, stateManager: AccountStateManager, peerId: PeerId, readState: PeerReadState)",
        )
        self.assertIn("markedUnread", low_level)

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

        mode_switch = swift_control_statement(
            reply, "switch mode", keywords=("switch",)
        )
        reply_body = normalized(reply)
        conditional_form = all(
            token in reply_body
            for token in (
                "mode==.localOnly",
                "mode==.automatic",
                "mode==.forceServer",
                "shouldSuppressReadReceipts",
            )
        )
        self.assertTrue(
            mode_switch or conditional_form,
            "Reply-thread network gate must visibly encode the three-mode truth table",
        )
        if mode_switch:
            cases = ("case .automatic", "case .localOnly", "case .forceServer")
            automatic = swift_case_clause(mode_switch, cases[0], cases[1:])
            local = swift_case_clause(mode_switch, cases[1], (cases[0], cases[2]))
            force = swift_case_clause(
                mode_switch, cases[2], cases[:2] + ("default:",)
            )
            self.assertIn("shouldSuppressReadReceipts", automatic)
            automatic_body = normalized(automatic)
            self.assertTrue(
                "return" in automatic_body
                or "false" in automatic_body
                or "!AyuGramHooks.shouldSuppressReadReceipts" in automatic_body
                or "shouldSuppressReadReceipts" in automatic_body
                and any(token in automatic_body for token in ("!=true", "==false")),
                "Automatic reply reads must gate network work on Ghost suppression",
            )
            local_body = normalized(local)
            self.assertNotIn("readSavedHistory", local_body)
            self.assertNotIn("readDiscussion", local_body)
            local_returns = "return" in local_body
            local_assignment = re.search(
                r"([A-Za-z_][A-Za-z0-9_]*)=false", local_body
            )
            self.assertTrue(local_returns or local_assignment)
            self.assertTrue(
                any(
                    token in force
                    for token in ("true", "readSavedHistory", "readDiscussion")
                )
            )
            switch_end = reply.find(mode_switch) + len(mode_switch)
            if "readSavedHistory" not in mode_switch:
                self.assertLess(switch_end, reply.index("readSavedHistory"))
            if "readDiscussion" not in mode_switch:
                self.assertLess(switch_end, reply.index("readDiscussion"))
            if local_assignment is not None:
                gate_name = local_assignment.group(1)
                force_body = normalized(force)
                self.assertRegex(force_body, rf"{re.escape(gate_name)}=true")
                automatic_assignment = re.search(
                    rf"{re.escape(gate_name)}=([^;}}]*shouldSuppressReadReceipts[^;}}]*)",
                    automatic_body,
                )
                self.assertIsNotNone(automatic_assignment)
                assert automatic_assignment is not None
                self.assertTrue(
                    "!" in automatic_assignment.group(1)
                    or "!=true" in automatic_assignment.group(1)
                    or "==false" in automatic_assignment.group(1)
                )
                network_offset = min(
                    reply.index("readSavedHistory"), reply.index("readDiscussion")
                )
                gate_prefix = normalized(reply[switch_end:network_offset])
                self.assertRegex(
                    gate_prefix,
                    rf"(?:guard{re.escape(gate_name)}else\{{return|"
                    rf"if!{re.escape(gate_name)}\{{return|"
                    rf"if{re.escape(gate_name)}\{{)",
                )
        else:
            automatic_gate = swift_control_statement(
                reply, "shouldSuppressReadReceipts", keywords=("if", "guard")
            )
            automatic_body = normalized(automatic_gate)
            self.assertIn("mode==.automatic", automatic_body)
            self.assertIn("return", automatic_body)
            local_gate = swift_control_statement(
                reply, "mode == .localOnly", keywords=("if", "guard")
            )
            force_gate = swift_control_statement(
                reply, "mode == .forceServer", keywords=("if", "guard")
            )
            self.assertTrue(local_gate)
            self.assertNotIn("readSavedHistory", local_gate)
            self.assertNotIn("readDiscussion", local_gate)
            self.assertTrue(force_gate)
            self.assertTrue(
                "true" in force_gate
                or "readSavedHistory" in force_gate
                or "readDiscussion" in force_gate
            )

        public = swift_block(
            reply_source,
            "public func applyMaxReadIndex(messageIndex: MessageIndex, mode: GRVMReadMode = .automatic)",
        )
        self.assertIn("impl.applyMaxReadIndex(messageIndex: messageIndex, mode: mode)", public)

    def test_reply_local_read_confirms_migrated_associated_peer(self) -> None:
        reply_source = source(self.reply_path)
        reply = swift_block(
            reply_source,
            "func applyMaxReadIndex(messageIndex: MessageIndex, mode: GRVMReadMode = .automatic)",
        )
        local = swift_control_statement(reply, "if case .localOnly", keywords=("if",))
        self.assertTrue(local, "Reply localOnly path must be explicit")
        self.assertIn("transaction.getPeerCachedData(peerId: messageIndex.id.peerId)", reply)
        self.assertIn("CachedChannelData", reply)
        self.assertIn("associatedHistoryMessageId", reply)
        self.assertIn(
            "transaction.confirmSynchronizedIncomingReadState(associatedHistoryMessageId.peerId)",
            reply,
        )
        self.assertGreaterEqual(
            reply.count("transaction.confirmSynchronizedIncomingReadState("),
            2,
        )

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
        regression = python_function(
            ghost_contract,
            "def test_reply_threads_keep_local_updates_but_gate_direct_reads(",
        )
        reply_call = python_assigned_call(regression, "reply", "swift_block")
        self.assertIsNotNone(reply_call)
        assert reply_call is not None
        self.assertGreaterEqual(len(reply_call.args), 2)
        signature = reply_call.args[1]
        self.assertIsInstance(signature, ast.Constant)
        self.assertEqual(
            "func applyMaxReadIndex(messageIndex: MessageIndex, "
            "mode: GRVMReadMode = .automatic)",
            signature.value,
        )
        body = normalized(regression)
        self.assertIn("gate=re.search(", body)
        self.assertIn(
            normalized(
                'self.assertLess(reply.index("strongSelf.unreadCountValue = '
                'unreadCountValue"), gate.start())'
            ),
            body,
        )
        self.assertIn(
            normalized('self.assertLess(gate.end(), reply.index("readSavedHistory"))'),
            body,
        )
        self.assertIn(
            normalized('self.assertLess(gate.end(), reply.index("readDiscussion"))'),
            body,
        )


class PeerMessageDeleteEngineContractTests(unittest.TestCase):
    delete_path = (
        "submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteOwnMessages.swift"
    )
    engine_path = (
        "submodules/TelegramCore/Sources/TelegramEngine/Messages/"
        "TelegramEngineMessages.swift"
    )

    def delete_helper(self) -> str:
        messages = swift_block(source(self.engine_path), "final class Messages")
        forwarder = swift_block(messages, "public func grvmDeleteOwnMessages(")
        forwarder_match = re.search(
            r"return\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*account\s*:\s*self\.account",
            forwarder,
        )
        if forwarder_match is None:
            return ""
        return swift_block(
            source(self.delete_path), f"func {forwarder_match.group(1)}("
        )

    def test_exact_delete_result_and_private_account_forwarder(self) -> None:
        delete = source(self.delete_path)
        result = swift_block(delete, "public struct GRVMDeleteOwnMessagesResult")
        for token in (
            "Equatable",
            "public let matchedCount: Int",
            "public let submittedCount: Int",
        ):
            self.assertIn(token, result)

        messages = swift_block(source(self.engine_path), "final class Messages")
        self.assertIn("private let account: Account", messages)
        forwarder = swift_block(messages, "public func grvmDeleteOwnMessages(")
        for token in (
            "peerId: PeerId",
            "threadId: Int64?",
            "Signal<GRVMDeleteOwnMessagesResult, NoError>",
            "account: self.account",
        ):
            self.assertIn(normalized(token), normalized(forwarder))
        self.assertRegex(
            normalized(forwarder),
            r"return_internal_[A-Za-z0-9_]+\(account:self\.account",
        )
        self.assertNotIn("extension TelegramEngine.Messages", delete)

    def test_engine_revalidates_group_channel_and_topic_scope(self) -> None:
        helper = self.delete_helper()
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
        self.assertTrue(
            re.search(r"guardpeerId!=account\.peerIdelse\{return", scope)
            or re.search(r"ifpeerId==account\.peerId\{return", scope),
            "Engine deletion must reject Saved Messages in the account guard",
        )

        channel_scope_raw = swift_control_statement(helper, "channel.info")
        channel_scope = normalized(channel_scope_raw)
        if "switchchannel.info" in channel_scope:
            broadcast = normalized(
                swift_case_clause(channel_scope_raw, "case .broadcast", ("case .group",))
            )
            group = normalized(
                swift_case_clause(channel_scope_raw, "case .group", ("case .broadcast",))
            )
            self.assertIn("return", broadcast)
            self.assertNotIn("returntrue", broadcast)
            self.assertNotIn("isAllowed=true", broadcast)
            self.assertIn("case.group", group)
            self.assertNotIn("returnfalse", group)
            group_guard = True
        else:
            group_guard = bool(
                re.search(r"guardcase\.group=channel\.infoelse\{return", channel_scope)
            )
            if not group_guard and re.search(
                r"(?:if|guard)channel\.info==\.group.*else\{return", channel_scope
            ):
                group_opening = _swift_control_body_open(channel_scope_raw, 0)
                group_body = _balanced_swift_block(channel_scope_raw, group_opening)
                group_tail = channel_scope_raw[group_opening + len(group_body) :]
                group_guard = (
                    "returnfalse" not in normalized(group_body)
                    and "returntrue" not in normalized(group_tail)
                    and "return" in normalized(group_tail)
                )
            if not group_guard:
                group_guard = bool(
                    re.search(r"ifcase\.group=channel\.info.*else\{return", channel_scope)
                )
                if group_guard:
                    group_opening = _swift_control_body_open(channel_scope_raw, 0)
                    group_body = _balanced_swift_block(channel_scope_raw, group_opening)
                    group_tail = channel_scope_raw[group_opening + len(group_body) :]
                    group_guard = (
                        "returnfalse" not in normalized(group_body)
                        and "returntrue" not in normalized(group_tail)
                        and "return" in normalized(group_tail)
                    )
        self.assertTrue(
            group_guard,
            "TelegramChannel deletion must explicitly reject broadcast/non-group info",
        )

        thread_anchor = next(
            (
                anchor
                for anchor in (
                    "if threadId != nil",
                    "if let _ = threadId",
                    "if let threadId",
                    "guard threadId == nil",
                )
                if anchor in helper
            ),
            "",
        )
        self.assertTrue(thread_anchor, "Missing explicit non-nil topic validation")
        thread_guard_raw = swift_control_statement(helper, thread_anchor)
        thread_guard = normalized(thread_guard_raw)
        self.assertIn("TelegramChannel", thread_guard)
        forum_scope = normalized(
            swift_control_statement(thread_guard_raw, "isForumOrMonoForum", keywords=("if", "guard"))
        )
        forum_guard_prefix = forum_scope.split("else", 1)[0]
        negative_forum_guard = bool(
            re.search(
                r"guard[^{}]*(?:![^{}]*isForumOrMonoForum|"
                r"isForumOrMonoForum(?:==false|!=true))",
                forum_guard_prefix,
            )
        )
        self.assertTrue(
            (
                not negative_forum_guard
                and re.search(r"guard.*isForumOrMonoForum.*else\{return", forum_scope)
            )
            or re.search(r"if!.*isForumOrMonoForum.*\{return", forum_scope)
            or re.search(r"if.*isForumOrMonoForum(?:==false|!=true).*\{return", forum_scope)
            or (
                all(token not in forum_scope for token in ("if!", "==false", "!=true"))
                and re.search(r"if.*isForumOrMonoForum.*else\{return", forum_scope)
            ),
            "A non-nil topic must reject non-forum channels on the invalid branch",
        )
        for forbidden in (
            "hasPermission(.deleteAllMessages)",
            "hasPermission(.banMembers)",
            "clearAuthorHistory",
        ):
            self.assertNotIn(forbidden, helper)

    def test_search_location_and_defensive_message_filters_are_exact(self) -> None:
        search = enclosing_swift_function(self.delete_helper(), "searchMessages(")
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
        ):
            self.assertIn(normalized(token), normalized(search))

        self.assertIn("result.messages", search)
        insertion = re.search(
            r"[A-Za-z_][A-Za-z0-9_]*\.(?:insert|updateValue)\s*\(\s*message\.id",
            search,
        )
        self.assertIsNotNone(insertion)
        assert insertion is not None
        collected = swift_control_statement(search, insertion.group(0))
        self.assertRegex(collected.lstrip(), r"^if\b")
        collected_opening = _swift_control_body_open(collected, 0)
        self.assertGreaterEqual(collected_opening, 0)
        collected_condition = normalized(collected[:collected_opening])
        for token in (
            "message.id.namespace == Namespaces.Message.Cloud",
            "message.author?.id == account.peerId",
            "message.threadId == threadId",
        ):
            self.assertIn(normalized(token), collected_condition)
        self.assertNotIn(
            "!message.id.namespace==Namespaces.Message.Cloud", collected_condition
        )
        self.assertNotIn(
            "!message.author?.id==account.peerId", collected_condition
        )
        self.assertNotIn("!message.threadId==threadId", collected_condition)
        cloud_end = collected_condition.find(
            normalized("message.id.namespace == Namespaces.Message.Cloud")
        ) + len(normalized("message.id.namespace == Namespaces.Message.Cloud"))
        author_start = collected_condition.find(
            normalized("message.author?.id == account.peerId")
        )
        thread_start = collected_condition.find(
            normalized("message.threadId == threadId")
        )
        self.assertGreaterEqual(author_start, cloud_end)
        self.assertGreaterEqual(thread_start, author_start)
        self.assertIn("&&", collected_condition[cloud_end:author_start])
        self.assertIn("&&", collected_condition[author_start:thread_start])
        self.assertNotIn("||", collected_condition[:author_start])
        allowed_thread_or = "threadId==nil||message.threadId==threadId"
        self.assertNotIn(
            "||",
            collected_condition.replace(allowed_thread_or, "thread-match"),
        )
        first_body = _balanced_swift_block(collected, collected_opening)
        insertion_offset = collected.find(insertion.group(0))
        self.assertGreaterEqual(insertion_offset, collected_opening)
        self.assertLess(insertion_offset, collected_opening + len(first_body))
        self.assertRegex(
            normalized(collected),
            r"[A-Za-z0-9_]+\.(?:insert|updateValue)\(message\.id",
        )

    def test_cumulative_scan_dedupes_and_fails_closed_on_no_progress(self) -> None:
        scan = enclosing_swift_function(self.delete_helper(), "searchMessages(")
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
        helper = self.delete_helper()
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
        self.assertEqual(1, helper.count("deleteMessagesInteractively("))
        batch_chain = enclosing_swift_function(
            helper, "deleteMessagesInteractively("
        )
        delete_call = swift_call(batch_chain, "deleteMessagesInteractively")
        delete_call_body = normalized(delete_call)
        self.assertIn("type:.forEveryone", delete_call_body)

        message_ids = re.search(
            r"messageIds:([A-Za-z_][A-Za-z0-9_]*)", delete_call_body
        )
        definition = ""
        bounded_batch = False
        if message_ids is not None:
            definition_match = re.search(
                rf"(?m)^[ \t]*(?:let|var)\s+{re.escape(message_ids.group(1))}\b[^\n]*",
                batch_chain,
            )
            definition = "" if definition_match is None else normalized(definition_match.group(0))
            prefix_definition = re.fullmatch(
                rf"(?:let|var){re.escape(message_ids.group(1))}(?::[^=]+)?="
                r"Array\(([A-Za-z_][A-Za-z0-9_]*)\.prefix\(100\)\)",
                definition,
            )
            if prefix_definition is not None:
                source_ids = prefix_definition.group(1)
                bounded_batch = (
                    f"{source_ids}.dropFirst({message_ids.group(1)}.count)"
                    in normalized(batch_chain)
                )
        direct_prefix = re.search(
            r"messageIds:Array\(([A-Za-z_][A-Za-z0-9_]*)\.prefix\(100\)\)"
            r"(?:,|\))",
            delete_call_body,
        )
        bounded_batch = bounded_batch or direct_prefix is not None

        call_offset = batch_chain.find("deleteMessagesInteractively(")
        returns = list(re.finditer(r"\breturn\b", batch_chain[:call_offset]))
        self.assertTrue(returns, "The batch delete signal must be returned")
        batch_expression = batch_chain[returns[-1].start() :]
        expression_call = swift_call(batch_expression, "deleteMessagesInteractively")
        expression_offset = batch_expression.find("deleteMessagesInteractively")
        expression_tail = normalized(
            batch_expression[expression_offset + len(expression_call) :]
        )
        expression_prefix = normalized(batch_expression[:expression_offset])
        direct_return = re.fullmatch(
            r"return\(?[A-Za-z0-9_$.?]*", expression_prefix
        )
        concat_return = re.fullmatch(
            r"return[A-Za-z0-9_$.?]*(?:concat|concatenate)\(\[?"
            r"[A-Za-z0-9_$.?]*",
            expression_prefix,
        )
        self.assertTrue(
            direct_return or concat_return,
            "deleteMessagesInteractively must belong to the returned batch expression",
        )
        for latest_operator in (
            "mapToSignal",
            "switchToLatest",
            "switchMap",
            "flatMapLatest",
        ):
            self.assertNotIn(latest_operator, batch_expression)

        function_name = re.search(r"func\s+([A-Za-z0-9_]+)\s*\(", batch_chain)
        recursive_completion = False
        if function_name is not None:
            recursive_offset = expression_tail.find(f"{function_name.group(1)}(")
            if recursive_offset >= 0:
                recursive_completion = "completed:" in expression_tail[:recursive_offset]
        sequential = (
            "|>then(" in expression_tail
            or concat_return is not None
            or recursive_completion
        )
        self.assertTrue(bounded_batch, "Deletion batches must contain at most 100 IDs")
        self.assertTrue(
            sequential,
            "Deletion batches need a real then/concat/recursive chain; "
            "mapToSignal or switch-latest is not sequencing proof",
        )
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
        self.assertEqual([message(value)["id"] for value in range(100)], batches[0])
        self.assertEqual([message(value)["id"] for value in range(100, 105)], batches[1])

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
        read_message = swift_enclosing_statement(
            context_menu, 'text: "Read Message"'
        )
        self.assertRegex(read_message.lstrip(), r"^if\b")
        self.assertLess(len(read_message), 6000)
        route_opening = _swift_control_body_open(read_message, 0)
        self.assertGreaterEqual(route_opening, 0)
        route_condition = normalized(read_message[:route_opening])
        for predicate in (
            "messages.count==1",
            "message.flags.contains(.Incoming)",
            "message.id.namespace==Namespaces.Message.Cloud",
            "shouldSuppressReadReceipts?(context.account.peerId)==true",
        ):
            self.assertIn(predicate, route_condition)
        self.assertNotIn("!message.flags.contains(.Incoming)", route_condition)
        self.assertNotRegex(
            route_condition,
            r"shouldSuppressReadReceipts\?\([^)]*\)(?:!=true|==false)",
        )
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
            'Chat/Context Menu/Read',
        ):
            self.assertIn(token, read_message)
        read_item = swift_enclosing_call(read_message, 'text: "Read Message"')
        action = swift_named_closure(read_item, "action")
        for token in (
            "interfaceInteraction.chatController() as? ChatControllerImpl",
            "message.index",
            ".localOnly",
        ):
            self.assertIn(token, action)
        read_call = swift_call(action, "grvmApplyMaxReadIndex")
        self.assertIn("grvmApplyMaxReadIndex(", action)
        assert_ordered_tokens(
            self,
            read_call,
            ["grvmApplyMaxReadIndex(", "message.index", ".localOnly"],
        )

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

        helper_name = re.search(r"func\s+([A-Za-z0-9_]+)\s*\(", target)
        self.assertIsNotNone(helper_name)
        assert helper_name is not None
        local_label = "text: strings[.menuReadAllLocal]"
        server_label = "text: strings[.menuReadAllServer]"
        header = enclosing_swift_function(chat, local_label)
        local_item = swift_enclosing_call(header, local_label)
        server_item = swift_enclosing_call(header, server_label)
        local_action = swift_named_closure(local_item, "action")
        server_action = swift_named_closure(server_item, "action")
        for action, mode, wrong_mode in (
            (local_action, ".localOnly", ".forceServer"),
            (server_action, ".forceServer", ".localOnly"),
        ):
            self.assertIn(f"{helper_name.group(1)}(", action)
            self.assertIn(mode, action)
            self.assertNotIn(wrong_mode, action)

    def test_header_builder_has_read_pair_ghost_fallback_and_mode_exclusions(self) -> None:
        local_label = "text: strings[.menuReadAllLocal]"
        server_label = "text: strings[.menuReadAllServer]"
        header = enclosing_swift_function(source(self.chat_path), local_label)
        for token in (
            "chatLocationUnreadCount(",
            "|> take(1)",
            "unreadCount > 0",
            "shouldSuppressReadReceipts?(",
            "context.account.peerId",
            "let strings = GRVMgramStrings(self.presentationData.strings)",
            local_label,
            ".localOnly",
            server_label,
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
        header_body = normalized(header)
        header_no_parens = header_body.replace("(", "").replace(")", "")
        self.assertRegex(
            header_no_parens,
            r"(?:peerId!=(?:self\.)?context\.account\.peerId|"
            r"(?:self\.)?context\.account\.peerId!=peerId)",
        )
        self.assertNotRegex(
            header_no_parens,
            r"(?:peerId==(?:self\.)?context\.account\.peerId|"
            r"(?:self\.)?context\.account\.peerId==peerId)",
        )
        inequality_match = re.search(
            r"peerId\s*!=\s*(?:self\.)?context\.account\.peerId|"
            r"(?:self\.)?context\.account\.peerId\s*!=\s*peerId",
            header,
        )
        self.assertIsNotNone(inequality_match)
        assert inequality_match is not None
        inequality_scope = swift_control_statement(
            header, inequality_match.group(0), keywords=("if", "guard")
        )
        visibility_body = normalized(inequality_scope).replace("(", "").replace(")", "")
        visibility_condition = visibility_body.split("{", 1)[0]
        item_label = local_label
        item_offset = header.find(item_label)
        guard_before_item = normalized(header[:item_offset]).replace("(", "").replace(")", "")
        self.assertTrue(
            (
                visibility_body.startswith("if")
                and re.search(
                    r"(?:peerId!=.*context\.account\.peerId|"
                    r"context\.account\.peerId!=peerId)",
                    visibility_condition,
                )
                and normalized(item_label) in visibility_body
            )
            or re.search(
                r"guard.*(?:peerId!=.*context\.account\.peerId|"
                r"context\.account\.peerId!=peerId).*else\{return",
                guard_before_item,
            ),
            "Saved Messages inequality must guard the visible action route",
        )
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
        delete_label = "text: strings[.menuDeleteOwn]"
        header = enclosing_swift_function(source(self.chat_path), delete_label)
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
            "let strings = GRVMgramStrings(self.presentationData.strings)",
            delete_label,
            "title: strings[.deleteOwnTitle]",
            "text: strings[.deleteOwnText]",
            "title: strings[.deleteOwnAction]",
            'Chat/Context Menu/Delete',
            "textColor: .destructive",
        ):
            self.assertIn(token, header)
        delete_item = swift_enclosing_call(header, delete_label)
        delete_action = swift_named_closure(delete_item, "action")
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
        alert = swift_call(delete_action, "textAlertController")
        destructive_call = swift_call(
            alert, "TextAlertAction(type: .destructiveAction"
        )
        destructive = swift_named_closure(destructive_call, "action")
        engine_call = swift_call(destructive, "engine.messages.grvmDeleteOwnMessages")
        self.assertIn("engine.messages.grvmDeleteOwnMessages(", destructive)
        self.assertIn("threadId: threadId", engine_call)
        self.assertNotIn("threadId: nil", engine_call)
        self.assertNotRegex(
            normalized(destructive), r"(?:let|var)threadId[^=]*=nil"
        )
        self.assertEqual(1, delete_action.count("grvmDeleteOwnMessages("))

        cancel_anchor = next(
            (
                token
                for token in ("Common_Cancel", 'title: "Cancel"')
                if token in delete_action
            ),
            "",
        )
        self.assertTrue(cancel_anchor, "Missing explicit Cancel action")
        cancel_call = swift_enclosing_call(alert, cancel_anchor)
        cancel = swift_named_closure(cancel_call, "action")
        self.assertNotIn("grvmDeleteOwnMessages(", cancel)

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

        avatar = swift_closure_matching(
            chat, r"avatarNode\.contextAction\s*=\s*\{"
        )
        header = enclosing_swift_function(
            chat, "text: strings[.menuReadAllLocal]"
        )
        header_name = re.search(r"func\s+([A-Za-z0-9_]+)\s*\(", header)
        self.assertIsNotNone(header_name)
        assert header_name is not None
        self.assertIn(f"{header_name.group(1)}(", avatar)

        more = swift_closure_matching(
            chat, r"self\.moreBarButton\.contextAction\s*=\s*\{"
        )
        self.assertIn(f"{header_name.group(1)}(", more)
        forum_call = swift_call(more, "ChatListControllerImpl.openMoreMenu")
        bot_call = swift_call(more, "openBotForumMoreMenu")
        passed_names: list[str] = []
        for call in (forum_call, bot_call):
            call_body = normalized(call)
            self.assertNotIn("additionalItems:[]", call_body)
            passed = re.search(
                r"additionalItems:([A-Za-z_][A-Za-z0-9_]*)", call_body
            )
            self.assertIsNotNone(passed)
            assert passed is not None
            passed_names.append(passed.group(1))
        self.assertEqual(passed_names[0], passed_names[1])
        self.assertRegex(
            more,
            rf"(?:next|startStandalone\(next):\s*\{{[\s\S]{{0,240}}?"
            rf"\b{passed_names[0]}\b\s+in",
        )
        producer_call = swift_enclosing_call(
            more, f"{passed_names[0]} in"
        )
        self.assertIn(f"additionalItems:{passed_names[0]}", normalized(producer_call))
        header_call = swift_call(more, f"{header_name.group(1)}(")
        self.assertTrue(header_call)
        header_end = more.find(header_call) + len(header_call)
        producer_opening = more.rfind("(", 0, more.find(f"{passed_names[0]} in") + 1)
        raw_producer_prefix = more[header_end:producer_opening]
        producer_prefix = normalized(more[header_end:producer_opening])
        self.assertRegex(
            raw_producer_prefix,
            r"^\s*(?:(?:\|>\s*[A-Za-z0-9_$.]+(?:\s*\([^;{}]*\))?)|"
            r"\s*\)+)*\s*(?:\|>|\.?)\s*startStandalone\s*$",
        )
        self.assertNotIn("let_=", producer_prefix)
        self.assertNotIn(";", producer_prefix)
        self.assertEqual(1, chat_list.count("additionalItems:"))

        self.assertIn("grvmArchiveContextMenuItems(", avatar)
        self.assertIn("grvmArchiveContextMenuItems(", forum)
        self.assertIn("grvmArchiveContextMenuItems(", bot)

    def test_jump_calls_existing_lower_bound_helper_without_reimplementing_history(self) -> None:
        chat = source(self.chat_path)
        jump_label = "text: strings[.menuJumpBeginning]"
        jump_item = swift_enclosing_statement(chat, jump_label)
        jump_call = swift_enclosing_call(jump_item, jump_label)
        jump_action = swift_named_closure(jump_call, "action")
        self.assertIn("scrollToStartOfHistory()", jump_action)
        self.assertIn('Chat/Context Menu/GoToMessage', jump_item)

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
            "let grvmStrings = GRVMgramStrings(presentationData.strings)",
            "ActionSheetController(presentationData:",
            "title: grvmStrings[.menuCopyCallback]",
            "UIPasteboard.general.string",
            "ActionSheetButtonItem",
            "presentationData.strings.Common_Cancel",
        ):
            self.assertIn(token, callback)
        assert_ordered_tokens(
            self,
            callback,
            ["title: grvmStrings[.menuCopyCallback]", "UIPasteboard.general.string"],
        )
        self.assertEqual(1, callback.count("UIPasteboard.general.string"))
        self.assertNotIn("requestMessageActionCallback", method)
        self.assertNotIn("performMessageButtonAction", method)


if __name__ == "__main__":
    unittest.main()
