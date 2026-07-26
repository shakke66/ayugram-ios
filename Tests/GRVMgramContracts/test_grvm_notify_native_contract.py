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
        )
    )
    return tests


if __name__ == "__main__":
    unittest.main()
