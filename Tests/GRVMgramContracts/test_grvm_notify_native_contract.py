import base64
import plistlib
import re
import unittest
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlsplit


ROOT = Path(__file__).resolve().parents[2]
POSTBOX_KEYS_PATH = ROOT / "submodules/TelegramUIPreferences/Sources/PostboxKeys.swift"
STATE_PATH = ROOT / "submodules/AyuGramLib/Sources/GRVMNotifyState.swift"
PARSER_PATH = ROOT / "submodules/TelegramUI/Sources/GRVMNotifyDeepLink.swift"
COORDINATOR_PATH = ROOT / "submodules/TelegramUI/Sources/GRVMNotifyCoordinator.swift"
RECONCILIATION_PATH = ROOT / "submodules/TelegramCore/Sources/TelegramEngine/Privacy/GRVMNotifySessionReconciliation.swift"
APP_DELEGATE_PATH = ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift"
PRIVACY_PATH = ROOT / "submodules/TelegramCore/Sources/TelegramEngine/Privacy/TelegramEnginePrivacy.swift"
INFO_PLIST_PATHS = (
    ROOT / "Telegram/Telegram-iOS/Info.plist",
    ROOT / "Telegram/Telegram-iOS/InfoBazel.plist",
)
BUILD_PATH = ROOT / "Telegram/BUILD"
FORK_CONFIG_PATH = ROOT / "Telegram/Telegram-iOS/Config-Fork.xcconfig"

INT32_MAX = 2_147_483_647
INT64_MAX = 9_223_372_036_854_775_807
PENDING_LIFETIME = 86_400


def empty_state():
    return {
        "pairedUserId": None,
        "sessionHash": None,
        "pendingAccountUserId": None,
        "pendingStartedAt": None,
    }


def _positive_int(value, maximum):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 < value <= maximum
    )


def _nonzero_int64(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and -INT64_MAX - 1 <= value <= INT64_MAX
        and value != 0
    )


def pending_is_valid(started_at, now):
    return (
        _positive_int(started_at, INT32_MAX)
        and isinstance(now, int)
        and not isinstance(now, bool)
        and now < started_at + PENDING_LIFETIME
    )


def normalize_state(state, now=None):
    result = {
        key: state.get(key)
        for key in empty_state()
    }

    if not (
        _positive_int(result["pairedUserId"], INT64_MAX)
        and _nonzero_int64(result["sessionHash"])
    ):
        result["pairedUserId"] = None
        result["sessionHash"] = None

    pending_pair_is_valid = (
        _positive_int(result["pendingAccountUserId"], INT64_MAX)
        and _positive_int(result["pendingStartedAt"], INT32_MAX)
    )
    if now is not None:
        pending_pair_is_valid = pending_pair_is_valid and pending_is_valid(
            result["pendingStartedAt"],
            now,
        )
    if not pending_pair_is_valid:
        result["pendingAccountUserId"] = None
        result["pendingStartedAt"] = None

    return result


def _strict_unquote(value):
    if re.search(r"%(?![0-9A-Fa-f]{2})", value):
        return None
    try:
        return unquote_to_bytes(value).decode("utf-8")
    except UnicodeDecodeError:
        return None


def _query_fields(raw_query):
    if not raw_query:
        return None

    fields = {}
    for part in raw_query.split("&"):
        encoded_name, separator, encoded_value = part.partition("=")
        if not separator:
            return None
        name = _strict_unquote(encoded_name)
        value = _strict_unquote(encoded_value)
        if name is None or value is None:
            return None
        fields.setdefault(name, []).append((value, encoded_value))
    return fields


def _single_fields(fields, required, optional=()):
    allowed = set(required) | set(optional)
    if set(fields) - allowed or set(required) - set(fields):
        return None
    if any(len(values) != 1 for values in fields.values()):
        return None
    return {name: values[0] for name, values in fields.items()}


def _parse_positive_integer(value, maximum):
    if not re.fullmatch(r"[0-9]+", value):
        return None
    parsed = int(value)
    if not 0 < parsed <= maximum:
        return None
    return parsed


def parse_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "grvmgram"
        or parsed.path
        or parsed.fragment
        or parsed.netloc not in {"notify-auth", "notify-open"}
    ):
        return None

    fields = _query_fields(parsed.query)
    if fields is None:
        return None

    if parsed.netloc == "notify-auth":
        items = _single_fields(fields, required=("token", "return_url"))
        if items is None:
            return None

        token_value, encoded_token = items["token"]
        if not 1 <= len(encoded_token) <= 4_096:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_-]+", token_value) or len(token_value) % 4 == 1:
            return None
        try:
            padded_token = token_value + "=" * ((4 - len(token_value) % 4) % 4)
            token = base64.urlsafe_b64decode(padded_token)
        except (ValueError, base64.binascii.Error):
            return None
        canonical_token = base64.urlsafe_b64encode(token).decode("ascii").rstrip("=")
        if not 1 <= len(token) <= 512 or canonical_token != token_value:
            return None

        return_url = urlsplit(items["return_url"][0])
        if (
            return_url.scheme != "https"
            or return_url.netloc != "grvm-notify.pages.dev"
            or return_url.path != "/setup/"
            or return_url.query
            or return_url.fragment
        ):
            return None
        return ("authorize", token, items["return_url"][0])

    items = _single_fields(
        fields,
        required=("account_user_id", "peer_type", "peer_id", "message_id"),
        optional=("thread_id",),
    )
    if items is None:
        return None

    account_user_id = _parse_positive_integer(items["account_user_id"][0], INT64_MAX)
    peer_id = _parse_positive_integer(items["peer_id"][0], INT64_MAX)
    message_id = _parse_positive_integer(items["message_id"][0], INT32_MAX)
    peer_type = items["peer_type"][0]
    if (
        account_user_id is None
        or peer_id is None
        or message_id is None
        or peer_type not in {"user", "group", "channel"}
    ):
        return None

    thread_id = None
    if "thread_id" in items:
        thread_id = _parse_positive_integer(items["thread_id"][0], INT64_MAX)
        if thread_id is None:
            return None

    return (
        "openMessage",
        account_user_id,
        (peer_type, peer_id),
        message_id,
        thread_id,
    )


def authorize(user_id):
    return ("authorize", user_id)


def open_message(account_user_id, message_id):
    return ("open-message", account_user_id, message_id)


class CoordinatorModel:
    def __init__(self, ready, locked, pending_user_id, paired_user_id=None):
        self.ready = ready
        self.locked = locked
        self.pending_user_id = pending_user_id
        self.paired_user_id = paired_user_id
        self.active_user_ids = list(
            dict.fromkeys(
                user_id
                for user_id in (pending_user_id, paired_user_id)
                if user_id is not None
            )
        )
        self.presented = []
        self.navigated = []
        self.removed_session_hashes = []
        self.error = None
        self._generation = 0
        self._pending = None
        self._approval_in_flight = False
        self._approval_generation = None
        self._accepted_session_hash = None
        self._accepted_session_generation = None
        self._provisional_paired_user_id = None
        self.authorization_finalization_idle = True

    def enqueue(self, request):
        self._generation += 1
        self._pending = (self._generation, request)
        self.drain()

    def logout(self, user_id):
        self.active_user_ids = [
            active_user_id
            for active_user_id in self.active_user_ids
            if active_user_id != user_id
        ]

    def dispatch_approval(self):
        self.authorization_finalization_idle = False
        self._approval_in_flight = True
        self._approval_generation = self._generation

    def accept_session(self, session_hash):
        assert self._approval_in_flight
        self._approval_in_flight = False
        if self._approval_generation != self._generation:
            self.removed_session_hashes.append(session_hash)
            self._approval_generation = None
            self.authorization_finalization_idle = True
            self.drain()
            return
        self._accepted_session_generation = self._approval_generation
        self._approval_generation = None
        self._accepted_session_hash = session_hash

    def publish_provisional_pair(self, user_id):
        assert self._accepted_session_hash is not None
        self.paired_user_id = user_id
        self._provisional_paired_user_id = user_id

    def complete_persistence(self, verified):
        should_remove = (
            self._accepted_session_hash is not None
            and (
                not verified
                or self._accepted_session_generation != self._generation
            )
        )
        if should_remove:
            self.removed_session_hashes.append(self._accepted_session_hash)
            if self.paired_user_id == self._provisional_paired_user_id:
                self.paired_user_id = None
        self._accepted_session_hash = None
        self._accepted_session_generation = None
        self._provisional_paired_user_id = None
        self.authorization_finalization_idle = True
        self.drain()

    def drain(self):
        if self._pending is None or not self.ready or self.locked:
            return

        generation, request = self._pending
        if request[0] == "open-message" and not self.authorization_finalization_idle:
            return
        self._pending = None
        if generation != self._generation:
            return

        if request[0] == "authorize":
            user_id = request[1]
            if self.pending_user_id != user_id or user_id not in self.active_user_ids:
                self.error = "account-unavailable"
                return
            self.presented.append(user_id)
        else:
            account_user_id = request[1]
            if (
                self.paired_user_id != account_user_id
                or account_user_id not in self.active_user_ids
            ):
                return
            self.navigated.append(request[2])


class NavigationGateModel:
    def __init__(self, target_user_id, message_id):
        self.target_user_id = target_user_id
        self.message_id = message_id
        self.current_user_id = target_user_id
        self.current_context_id = 1
        self.target_ready = False
        self.locked = True
        self.owns_target = True
        self.opened = []
        self._gated_context_id = None

    def capture_gate(self):
        if (
            not self.opened
            and self.current_user_id == self.target_user_id
            and self.target_ready
            and not self.locked
            and self.owns_target
        ):
            self._gated_context_id = self.current_context_id

    def complete_navigation(self):
        if (
            self._gated_context_id == self.current_context_id
            and self.current_user_id == self.target_user_id
            and self.target_ready
            and not self.locked
            and self.owns_target
        ):
            self.opened.append(self.message_id)
        self._gated_context_id = None

    def drain(self):
        self.capture_gate()
        self.complete_navigation()


def test_state_requires_pair_and_expires_pending_after_24_hours():
    assert normalize_state({"pairedUserId": 7, "sessionHash": None}) == empty_state()
    assert normalize_state({"pairedUserId": 7, "sessionHash": -42})["sessionHash"] == -42
    assert normalize_state({"pairedUserId": 7, "sessionHash": 0}) == empty_state()
    assert pending_is_valid(started_at=1_000, now=1_000 + 86_399)
    assert not pending_is_valid(started_at=1_000, now=1_000 + 86_400)


def test_authorize_rejects_duplicates_bad_origin_and_oversized_token():
    assert parse_url("grvmgram://notify-auth?token=AQID&token=BAUG&return_url=https%3A%2F%2Fgrvm-notify.pages.dev%2Fsetup%2F") is None
    assert parse_url("grvmgram://notify-auth?token=AQID&return_url=https%3A%2F%2Fevil.example%2F") is None
    assert parse_url("grvmgram://notify-auth?token=" + "A" * 4097 + "&return_url=https%3A%2F%2Fgrvm-notify.pages.dev%2Fsetup%2F") is None


def test_authorize_accepts_canonical_unpadded_base64url_only():
    return_url = "return_url=https%3A%2F%2Fgrvm-notify.pages.dev%2Fsetup%2F"
    parsed = parse_url(f"grvmgram://notify-auth?token=-_8&{return_url}")
    assert parsed is not None
    assert parsed[1] == bytes([251, 255])
    assert parse_url(f"grvmgram://notify-auth?token=%2B%2F8%3D&{return_url}") is None


def test_open_message_requires_one_peer_kind_and_int32_message():
    assert parse_url("grvmgram://notify-open?account_user_id=7&peer_type=user&peer_id=8&message_id=9") is not None
    assert parse_url("grvmgram://notify-open?account_user_id=7&peer_type=user&peer_type=group&peer_id=8&message_id=9") is None
    assert parse_url("grvmgram://notify-open?account_user_id=7&peer_type=user&peer_id=8&message_id=2147483648") is None


def test_locked_cold_start_waits_then_revalidates_owner():
    model = CoordinatorModel(ready=False, locked=True, pending_user_id=7)
    model.enqueue(authorize(user_id=7))
    assert model.presented == []
    model.ready = True
    model.locked = False
    model.active_user_ids = []
    model.drain()
    assert model.error == "account-unavailable"


def test_new_request_cancels_old_request_and_logout_does_not_retarget():
    model = CoordinatorModel(
        ready=False,
        locked=False,
        pending_user_id=None,
        paired_user_id=7,
    )
    model.enqueue(open_message(account_user_id=7, message_id=1))
    model.enqueue(open_message(account_user_id=7, message_id=2))
    model.logout(7)
    model.ready = True
    model.drain()
    assert model.navigated == []


def test_post_accept_cleanup_survives_new_request_cancellation():
    model = CoordinatorModel(ready=True, locked=False, pending_user_id=7)
    model.dispatch_approval()
    model.enqueue(open_message(account_user_id=7, message_id=2))
    model.accept_session(session_hash=91)
    assert model.removed_session_hashes == [91]

    model = CoordinatorModel(ready=True, locked=False, pending_user_id=7)
    model.dispatch_approval()
    model.accept_session(session_hash=92)
    model.enqueue(open_message(account_user_id=7, message_id=2))
    model.complete_persistence(verified=True)
    assert model.removed_session_hashes == [92]


def test_navigation_waits_for_finalization_before_reading_provisional_pair():
    model = CoordinatorModel(ready=True, locked=False, pending_user_id=7)
    model.dispatch_approval()
    model.accept_session(session_hash=93)
    model.publish_provisional_pair(user_id=7)

    model.enqueue(open_message(account_user_id=7, message_id=42))
    assert model.navigated == []

    model.complete_persistence(verified=True)
    assert model.removed_session_hashes == [93]
    assert model.paired_user_id is None
    assert model.navigated == []


def test_navigation_final_gate_tracks_current_context_and_unlock():
    model = NavigationGateModel(target_user_id=7, message_id=42)
    model.current_user_id = 8
    model.target_ready = True
    model.locked = False
    model.drain()
    assert model.opened == []

    model.current_user_id = 7
    model.locked = True
    model.drain()
    assert model.opened == []

    model.locked = False
    model.drain()
    assert model.opened == [42]


def test_navigation_rejects_replaced_context_after_gate_capture():
    model = NavigationGateModel(target_user_id=7, message_id=42)
    model.target_ready = True
    model.locked = False
    model.capture_gate()

    model.current_context_id = 2
    model.complete_navigation()
    assert model.opened == []


def _starlark_plist_fragment(source, name):
    pattern = re.compile(r"(?ms)^plist_fragment\(\n.*?^\)")
    for match in pattern.finditer(source):
        block = match.group(0)
        if re.search(rf'(?m)^\s+name = "{re.escape(name)}",$', block):
            return block
    raise AssertionError(f"Missing plist_fragment {name}")


def _compatibility_schemes(plist_path):
    with plist_path.open("rb") as file:
        plist = plistlib.load(file)
    for url_type in plist["CFBundleURLTypes"]:
        if url_type["CFBundleURLName"].endswith(".compatibility"):
            return url_type["CFBundleURLSchemes"]
    raise AssertionError(f"Missing compatibility URL type in {plist_path}")


def _all_plist_schemes(plist_path):
    with plist_path.open("rb") as file:
        plist = plistlib.load(file)
    return [
        scheme
        for url_type in plist["CFBundleURLTypes"]
        for scheme in url_type["CFBundleURLSchemes"]
    ]


class GRVMNotifyNativeSourceContractTests(unittest.TestCase):
    def test_shared_data_key_25_is_registered_without_renumbering(self):
        source = POSTBOX_KEYS_PATH.read_text(encoding="utf-8")
        enum_match = re.search(
            r"private enum ApplicationSpecificSharedDataKeyValues: Int32 \{(.*?)\n\}",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(enum_match, "Missing shared-data key enum")
        cases = re.findall(r"case \w+ = (\d+)", enum_match.group(1))
        self.assertEqual(list(range(26)), [int(value) for value in cases])
        self.assertIn("case grvmNotifyState = 25", enum_match.group(1))
        self.assertIn(
            "public static let grvmNotifyState = applicationSpecificSharedDataKey(ApplicationSpecificSharedDataKeyValues.grvmNotifyState.rawValue)",
            source,
        )

    def test_install_wide_state_store_contract_exists(self):
        self.assertTrue(STATE_PATH.exists(), f"Missing native state file: {STATE_PATH}")
        source = STATE_PATH.read_text(encoding="utf-8")
        required_contract = (
            "public struct GRVMNotifyState: Codable, Equatable",
            "public static let empty = GRVMNotifyState(",
            "public func normalized(now: Int32) -> GRVMNotifyState",
            "result.sessionHash.map { $0 != 0 }",
            "public func hasValidPending(now: Int32) -> Bool",
            "public protocol GRVMNotifyStateStoring: AnyObject",
            "func state() -> Signal<GRVMNotifyState, NoError>",
            "func update(_ f: @escaping (GRVMNotifyState) -> GRVMNotifyState) -> Signal<GRVMNotifyState, NoError>",
            "func writeAndVerify(_ state: GRVMNotifyState) -> Signal<Bool, NoError>",
            "public final class GRVMNotifyStateStore: GRVMNotifyStateStoring",
            "public init(accountManager: AccountManager<TelegramAccountManagerTypes>)",
            "container.decode(Data.self",
            "JSONDecoder().decode(GRVMNotifyState.self",
            "JSONEncoder().encode(self.state)",
            "transaction.updateSharedData(ApplicationSpecificSharedDataKeys.grvmNotifyState",
            "accountManager.sharedData(keys: [ApplicationSpecificSharedDataKeys.grvmNotifyState])",
            "|> take(1)",
        )
        for contract in required_contract:
            with self.subTest(contract=contract):
                self.assertIn(contract, source)

    def test_strict_deep_link_parser_contract_exists(self):
        self.assertTrue(PARSER_PATH.exists(), f"Missing strict parser file: {PARSER_PATH}")
        source = PARSER_PATH.read_text(encoding="utf-8")
        required_contract = (
            "enum GRVMNotifyPeer: Equatable",
            "case user(Int64)",
            "case group(Int64)",
            "case channel(Int64)",
            "enum GRVMNotifyDeepLink: Equatable",
            "case authorize(token: Data, returnURL: URL)",
            "case openMessage(accountUserId: Int64, peer: GRVMNotifyPeer, messageId: Int32, threadId: Int64?)",
            "static func parse(_ url: URL) -> GRVMNotifyDeepLink?",
            'components.scheme == "grvmgram"',
            'components.host == "notify-auth"',
            'components.host == "notify-open"',
            'replacingOccurrences(of: "-", with: "+")',
            'replacingOccurrences(of: "_", with: "/")',
            "return canonical == value ? data : nil",
            "encodedToken.count <= 4_096",
            "token.count <= 512",
            "items.values.allSatisfy { $0.count == 1 }",
            "Int32(exactly: messageId)",
        )
        for contract in required_contract:
            with self.subTest(contract=contract):
                self.assertIn(contract, source)

    def test_coordinator_enforces_readiness_single_flight_and_exact_ownership(self):
        self.assertTrue(COORDINATOR_PATH.exists(), f"Missing coordinator: {COORDINATOR_PATH}")
        source = COORDINATOR_PATH.read_text(encoding="utf-8")
        required_contract = (
            "import PresentationDataUtils",
            "final class GRVMNotifyCoordinator",
            "struct Environment",
            "let stateStore: GRVMNotifyStateStoring",
            "let activeAccounts: Signal<(primary: AccountContext?, accounts: [(AccountRecordId, AccountContext, Int32)], currentAuth: UnauthorizedAccount?), NoError>",
            "let authorizedContext: () -> Signal<AuthorizedApplicationContext, NoError>",
            "let isLocked: Signal<Bool, NoError>",
            "let present: (ViewController) -> Void",
            "let navigate: (AccountRecordId, PeerId, Int64?, MessageId) -> Void",
            "let openReturnURL: (URL) -> Void",
            "private let authDisposable = MetaDisposable()",
            "private let navigationDisposable = MetaDisposable()",
            "private let authorizationCommitDisposables = DisposableSet()",
            "private let authorizationFinalizationIdle = ValuePromise<Bool>(true, ignoreRepeated: true)",
            "authorizationFinalizationIdle.get()",
            "state.normalized(now:",
            "context.isReady.get()",
            "filter { $0 }",
            "filter { !$0 }",
            "context.account.peerId.id._internalGetInt64Value()",
            "approveAuthTransferToken(",
            "stateStore.writeAndVerify(",
            ".remove(hash:",
            "Namespaces.Peer.CloudUser",
            "Namespaces.Peer.CloudGroup",
            "Namespaces.Peer.CloudChannel",
            "Namespaces.Message.Cloud",
            "TelegramEngine.EngineData.Item.Peer.Peer(id: peerId)",
            "timeout(5.0, queue: .mainQueue(), alternate: .single(nil))",
        )
        for contract in required_contract:
            with self.subTest(contract=contract):
                self.assertIn(contract, source)
        finalization = source[
            source.index("    private func approve("):
            source.index("    private func showAuthorizationSuccess(")
        ]
        self.assertNotIn("authDisposable", finalization)
        self.assertLess(
            finalization.index("authorizationFinalizationIdle.set(false)"),
            finalization.index("approveAuthTransferToken("),
        )
        self.assertIn("resolveAuthorizationTarget(", finalization)
        self.assertLess(
            finalization.index("resolveAuthorizationTarget("),
            finalization.index("stateStore.writeAndVerify("),
        )
        navigation = source[
            source.index("    private func enqueueNavigation("):
            source.index("    private func resolveNavigationTarget(")
        ]
        self.assertIn("waitForAuthorizationFinalization()", navigation)
        self.assertLess(
            navigation.index("waitForAuthorizationFinalization()"),
            navigation.index("resolveNavigationTarget("),
        )
        self.assertNotIn("AccountRecordId(rawValue: accountUserId)", source)
        self.assertNotRegex(source, r"\b(?:Logger|print)\s*\(")

    def test_app_delegate_admits_all_grvmgram_urls_through_one_helper(self):
        source = APP_DELEGATE_PATH.read_text(encoding="utf-8")
        self.assertIn("private lazy var grvmNotifyCoordinator", source)
        self.assertIn("private func enqueueGRVMNotifyURL(_ url: URL) -> Bool", source)
        self.assertIn('url.scheme?.lowercased() == "grvmgram"', source)
        self.assertIn("launchOptions?[.url] as? URL", source)
        self.assertIn("launchOptions?[.url] as? String", source)
        self.assertGreaterEqual(source.count("self.enqueueGRVMNotifyURL(url)"), 6)
        self.assertIn("self.grvmNotifyNavigationDisposable.set(nil)", source)
        self.assertIn("sharedApplicationContext.sharedContext.switchToAccount(id: accountId)", source)
        self.assertIn("context.isReady.get()", source)
        self.assertIn("appLockContext.isCurrentlyLocked", source)
        self.assertIn("stateStore.state()", source)
        navigation = source[
            source.index("    private func navigateGRVMNotify("):
            source.index("    private func openChatWhenReady(")
        ]
        self.assertGreaterEqual(
            navigation.count("switchToAccount(id: accountId)"),
            2,
        )
        self.assertIn("private func finalGRVMNotifyNavigationContext(", navigation)
        final_gate = navigation[
            navigation.index("    private func finalGRVMNotifyNavigationContext("):
        ]
        self.assertIn("self.context.get()", final_gate)
        self.assertIn("context.isReady.get()", final_gate)
        self.assertIn("appLockContext.isCurrentlyLocked", final_gate)
        self.assertIn("sharedContext.activeAccountContexts", final_gate)
        self.assertIn("stateStore.state()", final_gate)
        first_disposable = navigation.index("        navigationDisposables.add")
        open_callback = navigation[
            navigation.index("        navigationDisposables.add", first_disposable + 1):
            navigation.index("    private func finalGRVMNotifyNavigationContext(")
        ]
        self.assertIn("navigationDisposables.add(signal.start", open_callback)
        self.assertIn("let currentContext = self.contextValue", open_callback)
        self.assertIn("currentContext === context", open_callback)
        self.assertIn("currentContext.openChatWithPeerId(", open_callback)
        self.assertNotIn("\n            context.openChatWithPeerId(", open_callback)
        callback_blocks = re.findall(
            r"(?ms)^    func application\([^\n]*(?:open|handleOpen) url: URL[^\n]*\) -> Bool \{.*?^    \}\n",
            source,
        )
        self.assertEqual(4, len(callback_blocks))
        for callback in callback_blocks:
            with self.subTest(callback=callback.splitlines()[0].strip()):
                self.assertIn("if self.enqueueGRVMNotifyURL(url)", callback)
                self.assertIn("self.openUrl(url: url)", callback)
                self.assertLess(
                    callback.index("if self.enqueueGRVMNotifyURL(url)"),
                    callback.index("self.openUrl(url: url)"),
                )
        self.assertNotIn("AccountRecordId(rawValue: accountUserId)", source)
        self.assertIn("alwaysKeepMessageId: true", source)

    def test_session_reconciliation_preserves_transport_errors(self):
        self.assertTrue(RECONCILIATION_PATH.exists(), f"Missing reconciliation: {RECONCILIATION_PATH}")
        source = RECONCILIATION_PATH.read_text(encoding="utf-8")
        required_contract = (
            "public enum GRVMNotifySessionFetchError: Error",
            "case network",
            "func _internal_grvmNotifySessionHashesOnce(account: Account) -> Signal<Set<Int64>, GRVMNotifySessionFetchError>",
            "account.network.request(Api.functions.account.getAuthorizations())",
            "RecentAccountSession(apiAuthorization: authorization).hash",
            "|> mapError {",
            "return .network",
            "|> map { result -> Set<Int64> in",
        )
        for contract in required_contract:
            with self.subTest(contract=contract):
                self.assertIn(contract, source)
        self.assertNotIn("retryRequestIfNotFrozen", source)
        self.assertNotIn("guard let result", source)
        self.assertNotRegex(source, r"\|>\s*catch\b")
        self.assertNotRegex(source, r"\.single\s*\(\s*Set(?:<Int64>)?\(\)\s*\)")

        privacy = PRIVACY_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "public func grvmNotifySessionHashesOnce() -> Signal<Set<Int64>, GRVMNotifySessionFetchError>",
            privacy,
        )
        self.assertIn("_internal_grvmNotifySessionHashesOnce(account: self.account)", privacy)

    def test_grvmgram_scheme_is_added_without_replacing_compatibility_schemes(self):
        for plist_path in INFO_PLIST_PATHS:
            with self.subTest(path=plist_path):
                self.assertEqual(
                    ["tg", "$(APP_SPECIFIC_URL_SCHEME)", "grvmgram"],
                    _compatibility_schemes(plist_path),
                )
                self.assertEqual(
                    ["telegram", "tg", "$(APP_SPECIFIC_URL_SCHEME)", "grvmgram", "ton"],
                    _all_plist_schemes(plist_path),
                )

        build = BUILD_PATH.read_text(encoding="utf-8")
        fragment = _starlark_plist_fragment(build, "UrlTypesInfoPlist")
        scheme_arrays = re.findall(
            r"<key>CFBundleURLSchemes</key>\s*<array>(.*?)</array>",
            fragment,
            re.DOTALL,
        )
        schemes = [
            re.findall(r"<string>([^<]+)</string>", array)
            for array in scheme_arrays
        ]
        self.assertEqual([["telegram"], ["tg", "tonsite", "grvmgram"]], schemes)

        fork_config = FORK_CONFIG_PATH.read_text(encoding="utf-8").splitlines()
        self.assertIn("APP_SPECIFIC_URL_SCHEME=tgfork", fork_config)


def load_tests(loader, tests, pattern):
    del loader, pattern
    tests.addTests(
        unittest.FunctionTestCase(function)
        for function in (
            test_state_requires_pair_and_expires_pending_after_24_hours,
            test_authorize_rejects_duplicates_bad_origin_and_oversized_token,
            test_authorize_accepts_canonical_unpadded_base64url_only,
            test_open_message_requires_one_peer_kind_and_int32_message,
            test_locked_cold_start_waits_then_revalidates_owner,
            test_new_request_cancels_old_request_and_logout_does_not_retarget,
            test_post_accept_cleanup_survives_new_request_cancellation,
            test_navigation_waits_for_finalization_before_reading_provisional_pair,
            test_navigation_final_gate_tracks_current_context_and_unlock,
            test_navigation_rejects_replaced_context_after_gate_capture,
        )
    )
    return tests


if __name__ == "__main__":
    unittest.main()
