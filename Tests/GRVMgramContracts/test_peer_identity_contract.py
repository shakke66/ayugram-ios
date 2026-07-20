import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PEER_ID = ROOT / "submodules/AyuGramLib/Sources/GRVMPeerId.swift"
CONTACTS = (
    ROOT
    / "submodules/TelegramCore/Sources/TelegramEngine/Contacts/TelegramEngineContacts.swift"
)
SEARCH = ROOT / "submodules/ChatListUI/Sources/ChatListSearchListPaneNode.swift"
PROFILE = (
    ROOT
    / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift"
)
PROFILE_BUILD = ROOT / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/BUILD"
CHAT_BUILD = ROOT / "submodules/ChatListUI/BUILD"
AYUGRAM_BUILD = ROOT / "submodules/AyuGramLib/BUILD"

MAX_PEER_ID = 0x00FFFFFFFFFFFFFF


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def swift_block(source: str, signature: str) -> str:
    start = source.find(signature)
    if start == -1:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening_brace = source.index("{", start)
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


def source_region(source: str, start: str, end: str) -> str:
    start_index = source.find(start)
    if start_index == -1:
        raise AssertionError(f"Missing source region start: {start}")
    end_index = source.find(end, start_index + len(start))
    if end_index == -1:
        raise AssertionError(f"Missing source region end: {end}")
    return source[start_index:end_index]


def mirror_candidates(query: str) -> list[tuple[str, int]]:
    value = query.strip()
    explicit = False
    if len(value) >= 2 and value[:2].lower() == "id":
        if len(value) >= 3 and value[2] == ":":
            value = value[3:]
            explicit = True
        elif len(value) >= 3 and value[2] == " ":
            value = value[3:]
            explicit = True
        else:
            return []
        if value.startswith(" ") or value.endswith(" "):
            return []

    negative = value.startswith("-")
    digits = value[1:] if negative else value
    if not digits or any(byte < 0x30 or byte > 0x39 for byte in digits.encode("utf-8")):
        return []

    if explicit and negative:
        return []

    if negative and digits.startswith("100"):
        remainder_digits = digits[3:]
        if not remainder_digits:
            return []
        remainder = 0
        for byte in remainder_digits.encode("ascii"):
            digit = byte - 0x30
            if remainder > (MAX_PEER_ID - digit) // 10:
                return []
            remainder = remainder * 10 + digit
        if remainder == 0:
            return []
        return [("channel", remainder)]

    magnitude = 0
    for byte in digits.encode("ascii"):
        digit = byte - 0x30
        if magnitude > ((2**63 - 1) - digit) // 10:
            return []
        magnitude = magnitude * 10 + digit
    if magnitude == 0:
        return []

    if negative:
        if magnitude > MAX_PEER_ID:
            return []
        return [("group", magnitude)]

    if magnitude > MAX_PEER_ID:
        return []
    if explicit:
        return [("user", magnitude), ("group", magnitude), ("channel", magnitude)]
    if len(digits) >= 5:
        return [("user", magnitude)]
    return []


class NumericPeerLookupTruthTableTests(unittest.TestCase):
    def test_complete_lookup_grammar(self) -> None:
        cases = {
            "12345": [("user", 12345)],
            " 12345 ": [("user", 12345)],
            "1234": [],
            "00001": [("user", 1)],
            "id:12345": [("user", 12345), ("group", 12345), ("channel", 12345)],
            "ID 12345": [("user", 12345), ("group", 12345), ("channel", 12345)],
            "Id:00001": [("user", 1), ("group", 1), ("channel", 1)],
            "id12345": [],
            "id::12345": [],
            "id: 12345": [],
            "id  12345": [],
            "id:-12345": [],
            "ID -10012345": [],
            "-10012345": [("channel", 12345)],
            "-10000001": [("channel", 1)],
            "-10012345678901234": [("channel", 12345678901234)],
            "-100": [],
            "-1000": [],
            "-10000000": [],
            "-12345": [("group", 12345)],
            "-1": [("group", 1)],
            "0": [],
            "00000": [],
            "-0": [],
            "": [],
            " ": [],
            "+12345": [],
            "--12345": [],
            "-+12345": [],
            "-": [],
            "123.45": [],
            "12_345": [],
            "12345x": [],
            "١٢٣٤٥": [],
            "１２３４５": [],
            str(MAX_PEER_ID): [("user", MAX_PEER_ID)],
            f"id:{MAX_PEER_ID}": [
                ("user", MAX_PEER_ID),
                ("group", MAX_PEER_ID),
                ("channel", MAX_PEER_ID),
            ],
            str(MAX_PEER_ID + 1): [],
            str(2**63 - 1): [],
            str(2**63): [],
            str(-(2**63)): [],
            f"-100{MAX_PEER_ID}": [("channel", MAX_PEER_ID)],
            f"-100{MAX_PEER_ID + 1}": [],
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(mirror_candidates(query), expected)


class PeerIdentitySourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.peer_id = read(PEER_ID)
        cls.contacts = read(CONTACTS)
        cls.search = read(SEARCH)
        cls.profile = read(PROFILE)
        cls.profile_build = read(PROFILE_BUILD)
        cls.chat_build = read(CHAT_BUILD)
        cls.ayugram_build = read(AYUGRAM_BUILD)

    def test_parser_is_ascii_overflow_safe_and_uses_real_peer_payload_bound(self) -> None:
        parser = swift_block(cls_source := self.peer_id, "public static func candidates(for query: String)")
        overflow_parser = swift_block(cls_source, "private static func parseMagnitude(")
        for token in (
            "public enum GRVMNumericPeerLookup",
            "query.trimmingCharacters(in: .whitespacesAndNewlines)",
            "byte >= 0x30 && byte <= 0x39",
            "0x00ffffffffffffff",
            "PeerId.Id._internalFromInt64Value(magnitude)",
            "Namespaces.Peer.CloudUser",
            "Namespaces.Peer.CloudGroup",
            "Namespaces.Peer.CloudChannel",
        ):
            self.assertIn(
                token,
                cls_source if token in ("public enum GRVMNumericPeerLookup", "0x00ffffffffffffff") else parser,
            )
        self.assertIn("query.trimmingCharacters(in: .whitespacesAndNewlines)", parser)
        self.assertIn(".utf8", parser)
        self.assertIn("magnitude > (maximum - digit) / 10", overflow_parser)
        for forbidden in ("Int64(", "abs(", "PeerId.Id.max", ".wholeNumberValue"):
            self.assertNotIn(forbidden, parser)

    def test_channel_form_parses_only_the_peer_payload_remainder(self) -> None:
        parser = swift_block(self.peer_id, "public static func candidates(for query: String)")
        self.assertIn("parseMagnitude(remainderDigits, maximum: maximumPeerId)", parser)
        self.assertNotIn("parseMagnitude(digits, maximum: Int64.max)", parser)

    def test_explicit_prefix_is_limited_to_positive_form(self) -> None:
        parser = swift_block(self.peer_id, "public static func candidates(for query: String)")
        self.assertIn("guard !isExplicit else", parser)

    def test_common_formatter_composes_bot_api_ids_without_arithmetic_negation(self) -> None:
        formatter = swift_block(self.peer_id, "public func grvmFormatPeerId(")
        for token in (
            "public enum GRVMPeerIdFormat",
            "case telegram",
            "case botAPI",
            "peerId.id._internalGetInt64Value()",
            'return "-\\(rawMagnitude)"',
            'return "-100\\(rawMagnitude)"',
            "return rawValue",
        ):
            self.assertIn(
                token,
                self.peer_id if token in ("public enum GRVMPeerIdFormat", "case telegram", "case botAPI") else formatter,
            )
        self.assertNotIn("-rawMagnitude", formatter)

    def test_local_peers_is_one_ordered_postbox_transaction_and_local_only(self) -> None:
        block = swift_block(self.contacts, "public func localPeers(ids:")
        for token in (
            "self.account.postbox.transaction",
            "for id in ids",
            "transaction.getPeer(id)",
            "EnginePeer(peer)",
            "EngineRenderedPeer(peer:",
            "result.append",
        ):
            self.assertIn(token, block)
        self.assertEqual(block.count("postbox.transaction"), 1)
        for forbidden in (
            "network",
            "request(",
            "resolvePeerByName",
            "resolveUsername",
            "botId",
            "getPeerCachedData",
        ):
            self.assertNotIn(forbidden, block)
        self.assertNotIn("import AyuGramLib", self.contacts)

    def test_numeric_search_is_switch_latest_scoped_and_merged_before_recent_and_local(self) -> None:
        branch = swift_block(self.search, "} else if let query = query, (key == .chats || key == .topics) {")
        for token in (
            "import AyuGramLib",
            "GRVMNumericPeerLookup.candidates(for: query)",
            "context.engine.contacts.localPeers(ids:",
            "combineLatest(",
            "numericPeers,",
            "fixedOrRemovedRecentlySearchedPeers,",
            "localPeers",
            "var existingPeerIds = Set<EnginePeer.Id>()",
            "for peer in numericPeers",
            "for peer in recentlySearched",
            "for peer in localPeers",
        ):
            self.assertIn(token, self.search if token == "import AyuGramLib" else branch)
        self.assertLess(branch.index("for peer in numericPeers"), branch.index("for peer in recentlySearched"))
        self.assertLess(branch.index("for peer in recentlySearched"), branch.index("for peer in localPeers"))
        self.assertLess(branch.index("let localPeers ="), branch.index("let numericPeers ="))
        local_pipeline = branch[branch.index("let localPeers =") : branch.index("let numericPeerIds =")]
        numeric_pipeline = branch[branch.index("let numericPeerIds =") : branch.index("foundLocalPeers =")]
        self.assertIn("ChatListIndex", local_pipeline)
        self.assertNotIn("ChatListIndex", numeric_pipeline)

    def test_profile_id_rows_are_account_scoped_and_offer_both_formats(self) -> None:
        function = swift_block(self.profile, "func infoItems(")
        for token in (
            "import AyuGramLib",
            "grvmFormatPeerId(peerId, format:",
            "AyuGramHooks.shouldShowDialogID?(context.account.peerId)",
            "AyuGramHooks.peerIdDisplayMode?(context.account.peerId)",
            "case 2:",
            ".botAPI",
            "default:",
            ".telegram",
            "let grvmStrings = GRVMgramStrings(presentationData.strings)",
            "text: grvmStrings[.peerCopyTelegramId]",
            "text: grvmStrings[.peerCopyBotApiId]",
            "longTapAction:",
            "contextAction:",
        ):
            self.assertIn(token, self.profile if token == "import AyuGramLib" else function)
        self.assertNotIn("ayuFormatPeerId", self.profile)
        self.assertEqual(function.count("peerIdDisplayMode?(context.account.peerId)"), 1)
        self.assertNotIn("shouldShowDialogID?(peerId)", function)
        self.assertNotIn("peerIdDisplayMode?(peerId)", function)

        user_branch = source_region(
            function,
            "if let user = data.peer as? TelegramUser",
            "} else if let channel = data.peer as? TelegramChannel",
        )
        channel_branch = source_region(
            function,
            "} else if let channel = data.peer as? TelegramChannel",
            "} else if let group = data.peer as? TelegramGroup",
        )
        group_branch = source_region(
            function,
            "} else if let group = data.peer as? TelegramGroup",
            "if let peer = data.peer, let members = data.members",
        )
        for branch, target_id in (
            (user_branch, "user.id"),
            (channel_branch, "channel.id"),
            (group_branch, "group.id"),
        ):
            self.assertIn("shouldShowDialogID?(context.account.peerId)", branch)
            self.assertIn(f"makePeerIdItem(ItemDialogId, {target_id})", branch)

        context_menu = swift_block(function, "let openContextMenu:")
        for token in (
            "ContextExtractedContentContainingNode",
            ".extracted(PeerInfoContextExtractedContentSource",
            ".reference(PeerInfoContextReferenceContentSource",
        ):
            self.assertIn(token, context_menu)

    def test_profile_dates_use_only_honest_local_fields(self) -> None:
        function = swift_block(self.profile, "func infoItems(")
        user_branch = source_region(
            function,
            "if let user = data.peer as? TelegramUser",
            "} else if let channel = data.peer as? TelegramChannel",
        )
        channel_branch = source_region(
            function,
            "} else if let channel = data.peer as? TelegramChannel",
            "} else if let group = data.peer as? TelegramGroup",
        )
        group_branch = source_region(
            function,
            "} else if let group = data.peer as? TelegramGroup",
            "if let peer = data.peer, let members = data.members",
        )

        for forbidden in (
            "creationDate",
            "invitedOn",
            "grvmStrings[.peerCreated]",
            "grvmStrings[.peerJoined]",
        ):
            self.assertNotIn(forbidden, user_branch)
        for token in (
            "let invitedOn = cachedData.invitedOn, invitedOn > 0",
            "peerDate = (grvmStrings[.peerJoined], invitedOn)",
            "channel.creationDate > 0",
            "peerDate = (grvmStrings[.peerCreated], channel.creationDate)",
            "stringForFullDate(timestamp: peerDate.timestamp",
            "dateTimeFormat: presentationData.dateTimeFormat",
        ):
            self.assertIn(token, channel_branch)
        self.assertLess(channel_branch.index("invitedOn > 0"), channel_branch.index("channel.creationDate > 0"))
        for token in (
            "group.creationDate > 0",
            "label: grvmStrings[.peerCreated]",
            "stringForFullDate(timestamp: group.creationDate",
            "dateTimeFormat: presentationData.dateTimeFormat",
        ):
            self.assertIn(token, group_branch)
        self.assertNotIn("invitedOn", group_branch)
        for forbidden in ("registration", "messageHistory", "peerId.timestamp"):
            self.assertNotIn(forbidden, function.lower())

    def test_build_dependencies_follow_one_way_ui_to_library_direction(self) -> None:
        self.assertEqual(self.chat_build.count("//submodules/AyuGramLib:AyuGramLib"), 1)
        self.assertEqual(self.profile_build.count("//submodules/AyuGramLib:AyuGramLib"), 1)
        self.assertIn("glob([", self.ayugram_build)
        self.assertIn('"Sources/**/*.swift"', self.ayugram_build)


if __name__ == "__main__":
    unittest.main()
