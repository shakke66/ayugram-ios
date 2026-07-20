import re
import sqlite3
import unittest
from dataclasses import dataclass, replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    path = ROOT / relative_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def swift_multiline_string(text: str, name: str) -> str:
    anchor = f'static let {name} = """'
    start = text.find(anchor)
    if start < 0:
        return ""
    start += len(anchor)
    end = text.find('"""', start)
    return text[start:end] if end >= 0 else ""


def around(text: str, anchor: str, before: int = 2500, after: int = 2500) -> str:
    start = text.find(anchor)
    if start < 0:
        return ""
    return text[max(0, start - before) : start + len(anchor) + after]


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        return ""
    opening = text.find("{", start)
    if opening < 0:
        return ""
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def swift_calls(text: str, signature: str) -> list[str]:
    """Return balanced call expressions so argument ownership can be checked."""
    calls: list[str] = []
    cursor = 0
    while True:
        start = text.find(signature, cursor)
        if start < 0:
            return calls
        opening = text.find("(", start + len(signature))
        if opening < 0:
            return calls
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
                if depth == 0:
                    calls.append(text[start : index + 1])
                    cursor = index + 1
                    break
        else:
            return calls


def action_block(text: str, label: str) -> str:
    start = text.find(f'text: "{label}"')
    if start < 0:
        return ""
    return swift_block(text[start:], "action: {")


def switch_case(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        return ""
    remainder = text[start + len(signature) :]
    next_case = re.search(r"\n\s*(?:case\b|default:)", remainder)
    end = len(text) if next_case is None else start + len(signature) + next_case.start()
    return text[start:end]


def ordered(text: str, *anchors: str) -> bool:
    positions = [text.find(anchor) for anchor in anchors]
    return all(position >= 0 for position in positions) and positions == sorted(positions)


@dataclass(frozen=True)
class BurnCase:
    count: int = 1
    peer: str = "user"
    namespace: str = "cloud"
    incoming: bool = True
    media: str = "image"
    ttl: bool = True
    has_consumable: bool = True
    consumed: bool = False


def burn_eligible(case: BurnCase) -> bool:
    return (
        case.count == 1
        and case.peer in {"user", "group", "channel"}
        and case.namespace == "cloud"
        and case.incoming
        and case.media in {"image", "file"}
        and case.ttl
        and case.has_consumable
        and not case.consumed
    )


def burn_execution_steps(prepared: bool) -> tuple[str, str]:
    preparation = "prepare:complete" if prepared else "prepare:failed"
    return preparation, "consume:force"


@dataclass(frozen=True)
class ReplayCase:
    count: int = 1
    has_marker: bool = True
    consumed: bool = True
    expired: bool = False
    locally_deleted: bool = False
    restored: bool = True


def replay_eligible(case: ReplayCase) -> bool:
    lifecycle_allows_replay = case.consumed or case.expired or case.locally_deleted
    return case.count == 1 and case.has_marker and lifecycle_allows_replay and case.restored


@dataclass(frozen=True)
class LocalCopyCase:
    count: int = 1
    deleted: bool = False
    ttl: bool = False
    one_play: bool = False
    source_protected: bool = False
    chat_protected: bool = False
    text: str = ""
    media: tuple[str, ...] = ()
    current_size: int = 0
    restored_size: int = 0


def local_copy_outcome(case: LocalCopyCase) -> str:
    special = any(
        (
            case.deleted,
            case.ttl,
            case.one_play,
            case.source_protected,
            case.chat_protected,
        )
    )
    if case.count != 1 or not special:
        return "notCandidate"
    if not case.media:
        return "ready" if case.text else "unsupported"
    if case.media not in {("image",), ("file",)}:
        return "unsupported"
    return "ready" if max(case.current_size, case.restored_size) > 0 else "unavailable"


SAFE_ENTITIES = {
    "Mention",
    "Hashtag",
    "BotCommand",
    "Url",
    "Email",
    "Bold",
    "Italic",
    "Code",
    "Pre",
    "TextUrl",
    "TextMention",
    "PhoneNumber",
    "Strikethrough",
    "BlockQuote",
    "Underline",
    "BankCard",
    "Spoiler",
    "FormattedDate",
}

SAFE_FILE_ATTRIBUTES = {
    "FileName",
    "ImageSize",
    "Sticker",
    "Animated",
    "Video",
    "Audio",
}


def safe_entity(entity: tuple[str, int, int], utf16_length: int) -> bool:
    kind, start, end = entity
    return 0 <= start < end <= utf16_length and kind in SAFE_ENTITIES


def safe_file_attributes(attributes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(attribute for attribute in attributes if attribute in SAFE_FILE_ATTRIBUTES)


def replay_flow(consume_on_open: bool) -> dict[str, bool]:
    return {
        "interaction": consume_on_open,
        "open_chat": consume_on_open,
        "gallery_data": consume_on_open,
        "secret_preview": consume_on_open,
        "playlist": consume_on_open,
        "playback_is_view_once": consume_on_open,
        "prepare": consume_on_open,
        "consume": consume_on_open,
    }


def decode_force(payload: dict[str, int]) -> bool:
    return payload.get("f", 0) != 0


def sends_content_read(*, suppressed: bool, force: bool) -> bool:
    return force or not suppressed


def merged_media(*, marker: bool, incoming: str) -> tuple[bool, str]:
    media = "preserved" if marker and incoming == "expired" else incoming
    return marker, media


def autoremove_outcome(
    *,
    secret: bool,
    is_remove: bool,
    marker: bool,
    legacy: bool = False,
    ghost: bool = False,
) -> str:
    _ = legacy, ghost
    if secret or is_remove:
        return "delete"
    return "retain-clear-timer" if marker else "expire-clear-timer"


def primary_resource_ids(records: list[tuple[str, int]]) -> tuple[str, ...] | None:
    if not records or any(size <= 0 for _, size in records):
        return None
    return tuple(sorted({resource_id for resource_id, _ in records}))


@dataclass(frozen=True)
class ArchivedMediaRecord:
    account: str
    message_key: str
    resource_id: str
    complete: bool = True
    byte_count: int = 1
    restored_size: int = 1


def prepare_terminal_outcome(records: tuple[ArchivedMediaRecord, ...]) -> tuple[bool, tuple[str, ...]]:
    complete = bool(records) and all(record.complete and record.byte_count > 0 for record in records)
    rollback_ids = () if complete else tuple(record.resource_id for record in records)
    return complete, rollback_ids


def rollback_attempt_resources(
    *, inserted_resource_ids: tuple[str, ...], terminal_outcome: str
) -> tuple[str, ...]:
    """Only the current reservation's inserted IDs may be rolled back on failure."""
    if terminal_outcome == "markerAttached":
        return ()
    return tuple(sorted(set(inserted_resource_ids)))


def restore_authorized(
    *,
    account: str,
    message_key: str,
    marker_ids: tuple[str, ...],
    records: tuple[ArchivedMediaRecord, ...],
) -> bool:
    expected = set(marker_ids)
    actual = {record.resource_id for record in records}
    return (
        bool(expected)
        and len(records) == len(actual)
        and actual == expected
        and all(
            record.account == account
            and record.message_key == message_key
            and record.complete
            and record.byte_count > 0
            and record.restored_size > 0
            for record in records
        )
    )


def sqlite_sentinel_fixture() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        swift_multiline_string(
            source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"),
            "schemaV2",
        )
    )
    return connection


class SourceContractTestCase(unittest.TestCase):
    def assertContains(self, text: str, anchor: str) -> None:
        if anchor not in text:
            self.fail(f"Missing source anchor: {anchor!r}")

    def assertContainsAll(self, text: str, *anchors: str) -> None:
        for anchor in anchors:
            self.assertContains(text, anchor)

    def assertNotContains(self, text: str, anchor: str) -> None:
        if anchor in text:
            self.fail(f"Forbidden source anchor present: {anchor!r}")

    def assertAnyContains(self, text: str, *anchors: str) -> None:
        if not any(anchor in text for anchor in anchors):
            self.fail(f"Missing one of source anchors: {anchors!r}")

    def assertMatches(self, text: str, pattern: str) -> None:
        if re.search(pattern, text) is None:
            self.fail(f"Missing source pattern: {pattern!r}")

    def assertOrdered(self, text: str, *anchors: str) -> None:
        self.assertTrue(ordered(text, *anchors), msg=f"Expected ordered anchors: {anchors}")


class ConsumeLifecycleContractTests(SourceContractTestCase):
    def test_preserved_consumable_attribute_codec_equality_and_registration(self) -> None:
        attribute = source(
            "submodules/TelegramCore/Sources/SyncCore/GRVMPreservedConsumableMediaAttribute.swift"
        )
        self.assertContainsAll(
            attribute,
            "public final class GRVMPreservedConsumableMediaAttribute: MessageAttribute, Equatable",
            "public let resourceIds: [String]",
            "public let media: [Media]",
            "public let preparedAt: Int32",
            "public init(resourceIds: [String], media: [Media], preparedAt: Int32)",
            "public required init(decoder: PostboxDecoder)",
            'decodeStringArrayForKey("r")',
            'decodeObjectArrayForKey("m").compactMap { $0 as? Media }',
            'decodeInt32ForKey("t", orElse: 0)',
            'encodeStringArray(self.resourceIds, forKey: "r")',
            'encodeObjectArray(self.media, forKey: "m")',
            'encodeInt32(self.preparedAt, forKey: "t")',
            "areMediaArraysEqual(lhs.media, rhs.media)",
            "self.media = media",
        )
        equality = swift_block(attribute, "public static func ==(")
        self.assertContainsAll(equality, "resourceIds", "preparedAt", "areMediaArraysEqual")
        self.assertMatches(attribute, r"self\.resourceIds\s*=.*\.sorted\(")
        for forbidden in ("relativePath", "absolutePath", "archivePath", "payload", "accountId"):
            self.assertNotContains(attribute, forbidden)

        account_manager = source("submodules/TelegramCore/Sources/Account/AccountManager.swift")
        self.assertContains(
            account_manager,
            "declareEncodable(GRVMPreservedConsumableMediaAttribute.self, f: { GRVMPreservedConsumableMediaAttribute(decoder: $0) })",
        )

    def test_force_operation_defaults_round_trips_and_builder_propagates(self) -> None:
        operation = source(
            "submodules/TelegramCore/Sources/SyncCore/SyncCore_SynchronizeConsumeMessageContentsOperation.swift"
        )
        builder = source(
            "submodules/TelegramCore/Sources/State/SynchronizeConsumeMessageContentsOperation.swift"
        )
        self.assertContainsAll(
            operation,
            "public let force: Bool",
            'self.force = decoder.decodeInt32ForKey("f", orElse: 0) != 0',
            'encoder.encodeInt32(self.force ? 1 : 0, forKey: "f")',
        )
        self.assertMatches(
            operation,
            r"public init\(messageIds: \[MessageId\],\s*force: Bool = false\)",
        )
        self.assertMatches(builder, r"(?s)func addSynchronizeConsumeMessageContentsOperation.*force: Bool = false")
        self.assertContains(builder, "SynchronizeConsumeMessageContentsOperation(messageIds: messageIds, force: force)")

    def test_public_and_internal_force_api_bypass_only_ghost_suppression(self) -> None:
        interactive = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift"
        )
        engine = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift"
        )
        worker = source(
            "submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift"
        )
        internal_method = swift_block(
            interactive,
            "func _internal_markMessageContentAsConsumedInteractively(",
        )
        public_method = swift_block(
            engine,
            "public func markMessageContentAsConsumedInteractively(",
        )
        self.assertContains(internal_method, "force: Bool = false")
        self.assertContains(internal_method, "shouldSuppressContentRead?(accountPeerId) == true && !force")
        self.assertContains(internal_method, "force: force")
        self.assertContains(public_method, "force: Bool = false")
        self.assertContains(public_method, "force: force")
        self.assertContains(worker, "shouldSuppressContentRead?(stateManager.accountPeerId) == true && !operation.force")

    def test_consume_worker_keeps_stock_user_channel_and_pts_routes(self) -> None:
        worker = source(
            "submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift"
        )
        builder = source(
            "submodules/TelegramCore/Sources/State/SynchronizeConsumeMessageContentsOperation.swift"
        )
        self.assertContainsAll(
            worker,
            "Api.functions.messages.readMessageContents",
            "Api.functions.channels.readMessageContents",
            "apiInputChannel(peer)",
            ".updatePts(pts: pts, ptsCount: ptsCount)",
            "operation.messageIds",
        )
        self.assertContains(builder, "operationLogRemoveEntry")

    def test_remote_consume_callers_pass_exact_account_identity(self) -> None:
        remote = source(
            "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift"
        )
        account_state = source(
            "submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift"
        )
        secret_state = source(
            "submodules/TelegramCore/Sources/State/ProcessSecretChatIncomingDecryptedOperations.swift"
        )
        remote_method = swift_block(remote, "func markMessageContentAsConsumedRemotely(")
        self.assertContains(remote_method, "accountPeerId: PeerId")
        pattern = re.compile(
            r"markMessageContentAsConsumedRemotely\(\s*"
            r"accountPeerId:\s*accountPeerId,\s*"
            r"transaction:\s*transaction,",
            re.DOTALL,
        )
        self.assertEqual(2, len(pattern.findall(account_state)))
        self.assertEqual(1, len(pattern.findall(secret_state)))

    def test_remote_consume_updates_lifecycle_but_marker_alone_retains_media(self) -> None:
        remote = swift_block(
            source(
                "submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift"
            ),
            "func markMessageContentAsConsumedRemotely(",
        )
        self.assertContainsAll(
            remote,
            "GRVMPreservedConsumableMediaAttribute",
            "ConsumableContentMessageAttribute(consumed: true)",
            "ConsumablePersonalMentionMessageAttribute(consumed: true, pending: false)",
            "updatedTags.remove(.unseenPersonalMessage)",
            "AutoremoveTimeoutMessageAttribute",
            "AutoclearTimeoutMessageAttribute",
            "TelegramMediaExpiredContent",
        )
        self.assertNotContains(remote, "shouldPreserveOneTimeMedia")
        self.assertNotContains(remote, "shouldSuppressContentRead")
        marker_gate = re.search(
            r"let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"message\.attributes\.contains\(where:\s*\{\s*\$0 is "
            r"GRVMPreservedConsumableMediaAttribute\s*\}\)",
            remote,
        )
        if marker_gate is not None:
            gate_name = marker_gate.group(1)
            self.assertGreaterEqual(remote.count(f"if !{gate_name}"), 2)
            first_expiration_gate = remote.find(f"if !{gate_name}")
            for lifecycle_anchor in (
                "ConsumableContentMessageAttribute(consumed: true)",
                "ConsumablePersonalMentionMessageAttribute(consumed: true, pending: false)",
                "updatedTags.remove(.unseenPersonalMessage)",
            ):
                self.assertLess(remote.find(lifecycle_anchor), first_expiration_gate)
        else:
            self.fail("Remote consume must expose an explicit durable-marker gate")

    def test_autoremove_marker_gate_does_not_bypass_whole_message_deletion(self) -> None:
        autoremove = source(
            "submodules/TelegramCore/Sources/State/ManagedAutoremoveMessageOperations.swift"
        )
        self.assertContainsAll(
            autoremove,
            "message.id.peerId.namespace == Namespaces.Peer.SecretChat || isRemove",
            "_internal_applyMessageDeletion(",
            "mode: .server(.ttl)",
            "GRVMPreservedConsumableMediaAttribute",
            "AutoclearTimeoutMessageAttribute",
            "TelegramMediaExpiredContent",
        )
        self.assertOrdered(
            autoremove,
            "message.id.peerId.namespace == Namespaces.Peer.SecretChat || isRemove",
            "GRVMPreservedConsumableMediaAttribute",
        )
        self.assertNotContains(autoremove, "shouldPreserveOneTimeMedia")
        marker_gate = re.search(
            r"let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"message\.attributes\.contains\(where:\s*\{\s*\$0 is "
            r"GRVMPreservedConsumableMediaAttribute\s*\}\)",
            autoremove,
        )
        if marker_gate is not None:
            marker_branch = swift_block(autoremove, f"else if {marker_gate.group(1)}")
            self.assertContains(marker_branch, "AutoclearTimeoutMessageAttribute")
            self.assertAnyContains(marker_branch, "media: currentMessage.media", ".withUpdatedMedia(")
            self.assertNotContains(marker_branch, "TelegramMediaExpiredContent")
            expired_branch = autoremove[
                autoremove.find(marker_branch) + len(marker_branch) :
            ]
            self.assertContains(expired_branch, "TelegramMediaExpiredContent")
        else:
            self.fail("Autoremove must expose an explicit durable-marker branch")

    def test_bulk_and_edit_merges_retain_marker_but_restore_only_expired_media(self) -> None:
        standalone = source(
            "submodules/TelegramCore/Sources/SyncCore/SyncCore_StandaloneAccountTransaction.swift"
        )
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        account_state = source(
            "submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift"
        )
        bulk = around(account_state, "transaction.addMessages(messages, location: location)", 6500, 200)
        edit = around(account_state, "case let .EditMessage(id, message):", 0, 6500)
        attribute_merge = swift_block(hooks, "func grvmMergedEditStateAttributes(")
        media_merge = swift_block(hooks, "func grvmMergedEditedMessage(")
        self.assertContains(standalone, "mergeMessageAttributes")
        self.assertMatches(
            standalone,
            r"(?s)if let\s+(?P<standaloneMarker>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"previous\.first\(where:.*GRVMPreservedConsumableMediaAttribute.*"
            r"!updated\.contains\(where:.*GRVMPreservedConsumableMediaAttribute.*"
            r"updated\.append\(\s*(?P=standaloneMarker)\s*\)",
        )
        self.assertMatches(
            attribute_merge,
            r"(?s)if let\s+(?P<attributeMarker>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"previous\.first\(where:.*GRVMPreservedConsumableMediaAttribute.*"
            r"result\.removeAll\(where:.*GRVMPreservedConsumableMediaAttribute.*"
            r"result\.append\(\s*(?P=attributeMarker)\s*\)",
        )
        self.assertMatches(
            media_merge,
            r"(?s)if let\s+(?P<marker>[A-Za-z_][A-Za-z0-9_]*)\s*=.*"
            r"GRVMPreservedConsumableMediaAttribute.*"
            r"incoming\.media.*TelegramMediaExpiredContent.*"
            r"updatedMedia\s*=\s*(?P=marker)\.media",
        )
        self.assertContainsAll(
            bulk,
            "transaction.getMessage(",
            "grvmMergedEditedMessage(",
            "transaction.addMessages(messages, location: location)",
        )
        bulk_assignment = re.search(
            r"(?s)(?:messages\[[^\]]+\]\s*=\s*grvmMergedEditedMessage\(|"
            r"messages\s*=\s*messages\.(?:map|compactMap)\s*\{.*?"
            r"grvmMergedEditedMessage\()",
            bulk,
        )
        self.assertIsNotNone(
            bulk_assignment,
            msg="Bulk merge must store the marker-preserving message before addMessages",
        )
        self.assertOrdered(bulk, "grvmMergedEditedMessage(", "transaction.addMessages(messages, location: location)")
        self.assertContains(edit, "grvmMergedEditStateAttributes(")
        if "grvmMergedEditedMessage(" not in edit:
            self.assertMatches(
                edit,
                r"(?s)if let\s+(?P<marker>[A-Za-z_][A-Za-z0-9_]*)\s*=.*"
                r"GRVMPreservedConsumableMediaAttribute.*TelegramMediaExpiredContent.*"
                r"updatedMedia\s*=\s*(?P=marker)\.media",
            )
        self.assertOrdered(edit, "grvmMergedEditStateAttributes(", ".update")

    def test_force_and_marker_behavior_fixtures_cover_fail_closed_edges(self) -> None:
        self.assertEqual([False, False, True], [decode_force(payload) for payload in ({}, {"f": 0}, {"f": 1})])
        self.assertEqual(
            [True, True, False, True],
            [
                sends_content_read(suppressed=suppressed, force=force)
                for suppressed, force in ((False, False), (False, True), (True, False), (True, True))
            ],
        )
        self.assertEqual(
            [
                (False, "expired"),
                (True, "preserved"),
                (False, "updated"),
                (True, "updated"),
            ],
            [
                merged_media(marker=marker, incoming=incoming)
                for marker, incoming in (
                    (False, "expired"),
                    (True, "expired"),
                    (False, "updated"),
                    (True, "updated"),
                )
            ],
        )
        cases = (
            (False, False, False, False, False, "expire-clear-timer"),
            (False, False, False, True, True, "expire-clear-timer"),
            (False, False, True, False, False, "retain-clear-timer"),
            (True, False, True, False, False, "delete"),
            (False, True, True, True, True, "delete"),
        )
        for secret, is_remove, marker, legacy, ghost, expected in cases:
            self.assertEqual(
                expected,
                autoremove_outcome(
                    secret=secret,
                    is_remove=is_remove,
                    marker=marker,
                    legacy=legacy,
                    ghost=ghost,
                ),
            )


class ArchiveHooksSentinelContractTests(SourceContractTestCase):
    def test_primary_resource_fixture_requires_positive_sorted_unique_ids(self) -> None:
        self.assertEqual(
            ("file-a", "photo-z"),
            primary_resource_ids([("photo-z", 20), ("file-a", 30), ("photo-z", 20)]),
        )
        self.assertIsNone(primary_resource_ids([]))
        self.assertIsNone(primary_resource_ids([("photo-z", 20), ("file-a", 0)]))
        complete, rollback = prepare_terminal_outcome(
            (
                ArchivedMediaRecord("account-a", "message-1", "photo-z", byte_count=20),
                ArchivedMediaRecord("account-a", "message-1", "file-a", byte_count=30),
            )
        )
        self.assertTrue(complete)
        self.assertEqual((), rollback)
        complete, rollback = prepare_terminal_outcome(
            (ArchivedMediaRecord("account-a", "message-1", "file-a", byte_count=0),)
        )
        self.assertFalse(complete)
        self.assertEqual(("file-a",), rollback)

        events = ["probe:file-a", "probe:photo-z", "reserve"]
        events += ["archive:file-a", "persist:file-a", "archive:photo-z", "persist:photo-z"]
        events += ["verify-all-complete", "attach-marker"]
        last_persist = max(index for index, event in enumerate(events) if event.startswith("persist:"))
        self.assertLess(last_persist, events.index("attach-marker"))

    def test_sentinel_fixture_is_idempotent_transfers_and_counts_all_revisions(self) -> None:
        database = sqlite_sentinel_fixture()
        key = (7, 100, 0, 42, 0)
        database.execute(
            """
            INSERT INTO archived_media_blobs
                (account_id, resource_id, relative_path, byte_count, kind, copy_state, generation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (7, "primary", "7/blobs/aa/primary", 64, "file", 2, 9),
        )
        reserve = """
            INSERT OR IGNORE INTO archived_message_media
                (account_id, peer_id, message_namespace, message_id,
                 thread_id, revision_id, resource_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        database.execute(reserve, (*key, -1, "primary"))
        database.execute(reserve, (*key, -1, "primary"))
        self.assertEqual(
            1,
            database.execute(
                "SELECT COUNT(*) FROM archived_message_media WHERE revision_id = -1"
            ).fetchone()[0],
        )
        self.assertEqual(
            (2, 9),
            database.execute(
                "SELECT copy_state, generation FROM archived_media_blobs"
            ).fetchone(),
        )

        database.execute(reserve, (*key, 0, "primary"))
        database.execute(
            """
            DELETE FROM archived_message_media
            WHERE account_id = ? AND peer_id = ? AND message_namespace = ?
              AND message_id = ? AND thread_id = ? AND revision_id = -1
              AND resource_id = ?
            """,
            (*key, "primary"),
        )
        self.assertEqual(
            [(0,)],
            database.execute(
                "SELECT revision_id FROM archived_message_media ORDER BY revision_id"
            ).fetchall(),
        )
        self.assertEqual(
            1,
            database.execute(
                "SELECT COUNT(*) FROM archived_message_media WHERE resource_id = ?",
                ("primary",),
            ).fetchone()[0],
        )
        database.close()

    def test_failed_attempt_fixture_removes_only_attempt_owned_sentinels(self) -> None:
        mappings = {
            ("old", -1, "kept"),
            ("attempt", -1, "shared"),
            ("deleted", 0, "shared"),
            ("attempt", -1, "orphan"),
        }
        planned_for_attempt = ("kept", "shared", "orphan")
        inserted_by_attempt = ("shared", "orphan")
        self.assertEqual(
            {"kept"},
            set(planned_for_attempt) - set(inserted_by_attempt),
            msg="A reused sentinel is planned but never owned by this attempt",
        )
        for terminal_outcome in (
            "archiveIncomplete",
            "terminalDatabaseFailure",
            "stalePostboxRow",
            "markerWriteFailure",
        ):
            with self.subTest(terminal_outcome=terminal_outcome):
                rollback_ids = rollback_attempt_resources(
                    inserted_resource_ids=inserted_by_attempt,
                    terminal_outcome=terminal_outcome,
                )
                remaining = {
                    row
                    for row in mappings
                    if not (
                        row[0] == "attempt"
                        and row[1] == -1
                        and row[2] in rollback_ids
                    )
                }
                referenced = {row[2] for row in remaining}
                self.assertEqual(("orphan", "shared"), rollback_ids)
                self.assertIn(("old", -1, "kept"), remaining)
                self.assertNotIn("kept", rollback_ids)
                self.assertIn("shared", referenced)
                self.assertNotIn("orphan", referenced)
        self.assertEqual(
            (),
            rollback_attempt_resources(
                inserted_resource_ids=inserted_by_attempt,
                terminal_outcome="markerAttached",
            ),
        )

    def test_exact_account_hook_fixture_never_falls_back_to_primary(self) -> None:
        calls: list[tuple[str, str]] = []
        services = {"account-a": "owner-a", "account-b": "owner-b"}

        def hook(account_id: str, message_id: str) -> bool:
            owner = services.get(account_id)
            if owner is None:
                return False
            calls.append((owner, message_id))
            return True

        self.assertTrue(hook("account-b", "same-message-id"))
        self.assertFalse(hook("missing", "same-message-id"))
        self.assertEqual([("owner-b", "same-message-id")], calls)

    def test_archive_hooks_are_symmetric_exact_account_and_fail_closed(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        manager = source("submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift")
        self.assertContains(hooks, "import SwiftSignalKit")
        self.assertContainsAll(
            hooks,
            "public static var prepareConsumableMedia: ((PeerId, Message) -> Signal<Bool, NoError>)?",
            "public static var restoreConsumableMedia: ((PeerId, Message) -> Signal<Bool, NoError>)?",
        )
        for hook_name, service_call in (
            ("prepareConsumableMedia", "service.prepareConsumableMedia(message)"),
            ("restoreConsumableMedia", "service.restoreArchivedMedia(for: message)"),
        ):
            block = around(
                manager,
                f"AyuGramHooks.{hook_name} = {{ [weak self] accountPeerId, message in",
                0,
                1000,
            )
            self.assertContainsAll(
                block,
                "guard let service = self?.registry.service(accountPeerId: accountPeerId) else",
                "registry.service(accountPeerId: accountPeerId)",
                ".single(false)",
                service_call,
            )
            self.assertNotContains(block, "primaryService")
            self.assertNotContains(block, "currentSettings")

    def test_prepare_reloads_exact_row_and_selects_positive_primary_resources(self) -> None:
        coordinator = source(
            "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
        )
        prepare = swift_block(coordinator, "public func prepareConsumableMedia(")
        self.assertContainsAll(
            prepare,
            "public func prepareConsumableMedia(_ message: Message) -> Signal<Bool, NoError>",
            "settingsSnapshot().saveDeletedMessages",
            "postbox.transaction",
            "transaction.getMessage(message.id)",
            "self.messageKey(",
            "accountRecordId",
            "stableId",
            "TelegramMediaImage",
            "TelegramMediaFile",
            "largestImageRepresentation(image.representations)",
            "file.resource",
            "grvmMediaResources(",
            "Set(",
            ".filter",
            "id.stringRepresentation",
            ".sorted()",
            "completedResourcePath",
        )
        self.assertMatches(prepare, r"(?s)(fileSize|byteCount|size).*?>\s*0")
        self.assertMatches(
            prepare,
            r"(?s)(?:allSatisfy|\.all\s*\{).*?\.complete.*?(?:byteCount|size)\s*>\s*0",
        )
        self.assertMatches(
            prepare,
            r"(?s)grvmMediaResources\(.*?\).*?\.filter.*?"
            r"(?:[Pp]rimary|[Rr]equired)[A-Za-z]*Ids.*?contains",
        )
        self.assertNotContains(prepare, "message.id.peerId == self.accountPeerId")
        for forbidden in ("network.request", "fetchedResource", "resourceData(", "fetchResource"):
            self.assertNotContains(prepare, forbidden)

    def test_prepare_persists_every_terminal_record_before_attaching_marker(self) -> None:
        prepare = swift_block(
            source("submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"),
            "public func prepareConsumableMedia(",
        )
        self.assertContainsAll(
            prepare,
            "reserveConsumableMedia(",
            "mediaStore.archive(",
            "store.updateMedia(",
            "rollbackConsumableMediaReservation(",
            "insertedResourceIds",
            ".complete",
            "byteCount > 0",
            "GRVMPreservedConsumableMediaAttribute(",
        )
        self.assertGreaterEqual(prepare.count("GRVMPreservedConsumableMediaAttribute"), 2)
        self.assertGreaterEqual(prepare.count("transaction.getMessage(message.id)"), 2)
        self.assertLess(
            prepare.find("settingsSnapshot().saveDeletedMessages"),
            prepare.rfind("GRVMPreservedConsumableMediaAttribute("),
        )
        self.assertLess(prepare.find("completedResourcePath"), prepare.find("reserveConsumableMedia("))
        self.assertLess(prepare.find("reserveConsumableMedia("), prepare.find("mediaStore.archive("))
        self.assertLess(prepare.find("mediaStore.archive("), prepare.find("store.updateMedia("))
        marker_position = prepare.rfind("GRVMPreservedConsumableMediaAttribute(")
        terminal_validation = re.search(
            r"(?s)\b([A-Za-z_][A-Za-z0-9_]*)\.(?:allSatisfy|all)\s*"
            r"(?:\(\s*)?\{.*?\.complete.*?(?:byteCount|size)\s*>\s*0",
            prepare,
        )
        self.assertIsNotNone(
            terminal_validation,
            msg="Marker eligibility must be derived from verified terminal archive records",
        )
        validated_records = terminal_validation.group(1)
        marker_calls = swift_calls(prepare, "GRVMPreservedConsumableMediaAttribute")
        self.assertGreaterEqual(len(marker_calls), 1)
        marker_ids = re.search(
            r"(?s)\bresourceIds\s*:\s*(.*?)\s*,\s*media\s*:",
            marker_calls[-1],
        )
        self.assertIsNotNone(marker_ids, msg="Marker must declare its verified resource IDs")
        derived_ids = re.findall(
            rf"(?s)(?:let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            rf"{re.escape(validated_records)}\.(?:map|compactMap).*?"
            r"resourceId.*?\.sorted\(\)",
            prepare[:marker_position],
        )
        self.assertTrue(
            re.search(rf"\b{re.escape(validated_records)}\b", marker_ids.group(1))
            or any(
                re.search(rf"\b{re.escape(derived_id)}\b", marker_ids.group(1))
                for derived_id in derived_ids
            ),
            msg="Marker resourceIds must come from the complete terminal record set",
        )
        archive_positions = [
            match.start() for match in re.finditer(r"mediaStore\.archive\(", prepare)
        ]
        update_positions = [
            match.start() for match in re.finditer(r"store\.updateMedia\(", prepare)
        ]
        self.assertTrue(archive_positions)
        self.assertTrue(update_positions)
        self.assertLess(max(archive_positions), marker_position)
        self.assertLess(max(update_positions), marker_position)
        self.assertEqual(
            len(update_positions),
            len(re.findall(r"store\.updateMedia\(", prepare[:marker_position])),
        )
        self.assertLess(max(update_positions), prepare.rfind("transaction.getMessage(message.id)"))
        self.assertLess(
            prepare.rfind("transaction.getMessage(message.id)"),
            prepare.rfind("GRVMPreservedConsumableMediaAttribute("),
        )
        reservation_binding = re.search(
            r"(?:let|var|guard\s+let)\s+([A-Za-z_][A-Za-z0-9_]*)"
            r"(?:\s*:\s*[^=\n]+)?\s*=\s*(?:try[?!]?\s+)?"
            r"(?:self\.)?store\.reserveConsumableMedia\(",
            prepare,
        )
        tuple_binding = re.search(
            r"(?:let|var|guard\s+let)\s*\(([^)]+)\)\s*=\s*"
            r"(?:try[?!]?\s+)?(?:self\.)?store\.reserveConsumableMedia\(",
            prepare,
        )
        if reservation_binding is not None:
            reservation_expressions = (
                f"{reservation_binding.group(1)}.insertedResourceIds",
            )
        elif tuple_binding is not None:
            tuple_names = [name.strip() for name in tuple_binding.group(1).split(",")]
            reservation_expressions = tuple(
                name for name in tuple_names if "inserted" in name.lower()
            )
            self.assertTrue(
                reservation_expressions,
                msg="Tuple reservation result must expose its attempt-owned inserted IDs",
            )
        else:
            self.assertContains(prepare, "reserveConsumableMedia(")
            reservation_expressions = ("insertedResourceIds",)
        rollback_calls = swift_calls(prepare, "rollbackConsumableMediaReservation")
        self.assertGreaterEqual(len(rollback_calls), 1)
        for rollback_call in rollback_calls:
            argument = re.search(
                r"\binsertedResourceIds\s*:\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)",
                rollback_call,
            )
            self.assertIsNotNone(argument, msg="Rollback must name its attempt-owned ID set")
            argument_expression = argument.group(1)
            direct_match = any(
                argument_expression == expression for expression in reservation_expressions
            )
            alias_match = any(
                re.search(
                    rf"(?:let|var)\s+{re.escape(argument_expression)}\s*=\s*"
                    rf"{re.escape(expression)}\b",
                    prepare,
                )
                for expression in reservation_expressions
            )
            self.assertTrue(
                direct_match or alias_match,
                msg="Rollback IDs must flow from the reservation's insertedResourceIds",
            )
            self.assertNotContains(rollback_call, "resourceIds: []")
        rollback_position = prepare.find("rollbackConsumableMediaReservation(")
        self.assertGreater(rollback_position, marker_position)
        self.assertLess(prepare.rfind("store.updateMedia("), rollback_position)
        terminal_tail = prepare[marker_position:]
        terminal_gate_patterns = (
            r"(?s)\|>\s*(?:map|mapToSignal)\s*\{.*?"
            r"(?:if\s+!\w+|guard\s+\w+\s+else).*?rollbackConsumableMediaReservation\(",
            r"(?s)defer\s*\{.*?(?:if|guard).*?rollbackConsumableMediaReservation\(",
            r"(?s)(?:catch|else)\s*\{.*?rollbackConsumableMediaReservation\(",
        )
        self.assertTrue(
            any(re.search(pattern, terminal_tail) for pattern in terminal_gate_patterns),
            msg="All terminal failures must pass through a success-gated rollback gate",
        )
        self.assertNotContains(prepare[rollback_position + 1 :], "GRVMPreservedConsumableMediaAttribute(")

    def test_store_reservation_is_sentinel_idempotent_and_fail_closed(self) -> None:
        store = source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift")
        reservation = swift_block(store, "public func reserveConsumableMedia(")
        rollback = swift_block(store, "public func rollbackConsumableMediaReservation(")
        self.assertMatches(store, r"consumableMediaRevisionId\s*:\s*Int64\s*=\s*-1")
        self.assertContainsAll(
            reservation,
            "self.transaction(database)",
            "INSERT OR IGNORE INTO archived_message_media",
            "consumableMediaRevisionId",
            "insertedResourceIds",
            "sqlite3_changes(database)",
            ".complete",
            "byteCount > 0",
            "admitMedia",
        )
        self.assertMatches(
            reservation,
            r"(?s)INSERT OR IGNORE INTO archived_message_media.*?"
            r"account_id.*?peer_id.*?message_namespace.*?message_id.*?thread_id.*?"
            r"revision_id.*?resource_id.*?VALUES.*?"
            r"self\.keyValues\(key\).*?consumableMediaRevisionId.*?resourceId",
        )
        self.assertMatches(
            reservation,
            r"(?s)sqlite3_changes\(database\).*?"
            r"insertedResourceIds\.insert\([^)]*resourceId",
        )
        self.assertNotContains(
            around(reservation, "INSERT OR IGNORE INTO archived_message_media", 0, 1800),
            "revisionId: 0",
        )
        reuse_gate = re.search(
            r"if let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=.*?"
            r"\1\.copyState\s*==\s*\.complete.*?\1\.byteCount\s*>\s*0",
            reservation,
            re.DOTALL,
        )
        self.assertIsNotNone(reuse_gate, msg="Reservation must branch on a valid complete blob")
        reuse_branch = swift_block(reservation, reuse_gate.group(0))
        self.assertNotContains(reuse_branch, "admitMedia")
        self.assertAnyContains(reuse_branch, "continue", "return")
        self.assertOrdered(reservation, reuse_branch, "admitMedia")
        self.assertContainsAll(
            rollback,
            "insertedResourceIds",
            "consumableMediaRevisionId",
            "DELETE FROM archived_message_media",
            "account_id = ?",
            "peer_id = ?",
            "message_namespace = ?",
            "message_id = ?",
            "thread_id = ?",
            "resource_id = ?",
            "SELECT COUNT(*) FROM archived_message_media",
            "references == 0",
            "DELETE FROM archived_media_blobs",
        )
        self.assertNotContains(rollback, "revision_id = 0")

    def test_save_deleted_transfers_sentinel_after_revision_zero_mapping(self) -> None:
        save_deleted = swift_block(
            source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"),
            "public func saveDeleted(",
        )
        self.assertContainsAll(
            save_deleted,
            "self.transaction(database)",
            "insertMapping(database, key: message.key, revisionId: 0",
            "consumableMediaRevisionId",
            "DELETE FROM archived_message_media",
            "account_id = ?",
            "peer_id = ?",
            "message_namespace = ?",
            "message_id = ?",
            "thread_id = ?",
            "resource_id = ?",
        )
        self.assertOrdered(
            save_deleted,
            "insertMapping(database, key: message.key, revisionId: 0",
            "consumableMediaRevisionId",
        )

    def test_cleanup_reference_queries_count_sentinel_and_normal_mappings(self) -> None:
        store = source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift")
        matches = list(
            re.finditer(
                r"SELECT COUNT\(\*\) FROM archived_message_media WHERE account_id = \? AND resource_id = \?",
                store,
            )
        )
        self.assertGreaterEqual(len(matches), 2)
        for match in matches:
            reference_query = store[max(0, match.start() - 200) : match.end() + 200]
            self.assertNotContains(reference_query, "revision_id")
        finalize = swift_block(store, "public func finalizeDeletedCleanup(")
        self.assertContains(finalize, "DELETE FROM archived_message_media")
        self.assertContains(finalize, "revision_id = 0")
        self.assertContains(finalize, "references == 0")
        self.assertContains(store, "if references == 0")

    def test_restore_requires_exact_complete_mapping_and_fresh_postbox_write(self) -> None:
        good_records = (
            ArchivedMediaRecord("account-a", "message-1", "photo-z", restored_size=10),
            ArchivedMediaRecord("account-a", "message-1", "file-a", restored_size=20),
        )
        self.assertTrue(
            restore_authorized(
                account="account-a",
                message_key="message-1",
                marker_ids=("photo-z", "file-a"),
                records=good_records,
            )
        )
        for invalid in (
            (),
            good_records[:1],
            good_records + (ArchivedMediaRecord("account-a", "message-1", "extra"),),
            (ArchivedMediaRecord("account-b", "message-1", "photo-z"), ArchivedMediaRecord("account-a", "message-1", "file-a")),
            (ArchivedMediaRecord("account-a", "other-message", "photo-z"), ArchivedMediaRecord("account-a", "message-1", "file-a")),
            (ArchivedMediaRecord("account-a", "message-1", "photo-z", complete=False), ArchivedMediaRecord("account-a", "message-1", "file-a")),
            (ArchivedMediaRecord("account-a", "message-1", "photo-z", byte_count=0), ArchivedMediaRecord("account-a", "message-1", "file-a")),
            (ArchivedMediaRecord("account-a", "message-1", "photo-z", restored_size=0), ArchivedMediaRecord("account-a", "message-1", "file-a")),
        ):
            self.assertFalse(
                restore_authorized(
                    account="account-a",
                    message_key="message-1",
                    marker_ids=("photo-z", "file-a"),
                    records=invalid,
                )
            )
        restore = swift_block(
            source("submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"),
            "public func restoreArchivedMedia(",
        )
        media_store_restore = swift_block(
            source("submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift"),
            "public func restore(",
        )
        store = source("submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift")
        mapping_lookup = swift_block(store, "public func consumableMedia(")
        self.assertContainsAll(
            mapping_lookup,
            "consumableMediaRevisionId",
            "archived_message_media",
            "archived_media_blobs",
            "account_id = ?",
            "peer_id = ?",
            "message_namespace = ?",
            "message_id = ?",
            "thread_id = ?",
            "revision_id = ?",
            "resource_id",
        )
        self.assertContainsAll(
            restore,
            "public func restoreArchivedMedia(for message: Message) -> Signal<Bool, NoError>",
            "consumableMedia(key:",
            "self.messageKey(",
            "accountRecordId",
            "transaction.getMessage(message.id)",
            "stableId",
            "Set(",
            "attribute.resourceIds",
            "==",
            ".complete",
            "byteCount > 0",
            "mediaStore.restore(",
            "MediaResourceId",
            "completedResourcePath",
            "attribute.media",
            "transaction.updateMessage",
        )
        self.assertContainsAll(
            media_store_restore,
            "MediaResourceId(record.resourceId)",
            "restoreResourceData",
        )
        restore_calls = swift_calls(restore, "mediaStore.restore")
        self.assertGreaterEqual(len(restore_calls), 1)
        restore_loop = re.search(
            r"(?:for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+records|"
            r"records\.(?:map|compactMap)\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s+in)",
            restore,
        )
        if restore_loop is not None:
            record_name = restore_loop.group(1) or restore_loop.group(2)
            for restore_call in restore_calls:
                self.assertContains(restore_call, record_name)
        else:
            self.assertContains(restore, "records.map")
            for restore_call in restore_calls:
                self.assertContains(restore_call, "$0")
        self.assertMatches(
            restore,
            r"(?s)(?:allSatisfy|\.all\s*\{).*?\.complete.*?(?:byteCount|size)\s*>\s*0",
        )
        set_comparison = around(restore, "attribute.resourceIds", 600, 1200)
        self.assertContainsAll(set_comparison, "Set(", "records", "==")
        self.assertGreaterEqual(restore.count("transaction.getMessage(message.id)"), 2)
        self.assertLess(restore.find("mediaStore.restore("), restore.rfind("completedResourcePath"))
        self.assertLess(
            restore.rfind("completedResourcePath"),
            restore.rfind("transaction.getMessage(message.id)"),
        )
        self.assertLess(
            restore.rfind("transaction.getMessage(message.id)"),
            restore.rfind("transaction.updateMessage"),
        )
        path_window = around(restore, "completedResourcePath", 1600, 1600)
        self.assertAnyContains(path_window, "guard", "if")
        self.assertAnyContains(path_window, "return false", ".single(false)", "putNext(false)")
        direct_path_failure = re.search(
            r"(?s)(?:guard|if)(?:(?!transaction\.updateMessage).)*?"
            r"completedResourcePath(?:(?!transaction\.updateMessage).)*?"
            r"(?:else\s*)?\{(?:(?!transaction\.updateMessage).)*?"
            r"(?:return\s+false|\.single\(false\)|putNext\(false\))",
            restore,
        )
        bound_path_failure = re.search(
            r"(?s)(?:let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"(?:(?!transaction\.updateMessage).)*?completedResourcePath.*?"
            r"guard\s+\1\s+else\s*\{.*?"
            r"(?:return\s+false|\.single\(false\)|putNext\(false\))",
            restore,
        )
        self.assertIsNotNone(
            direct_path_failure or bound_path_failure,
            msg="Every restore path must fail before the Postbox marker update",
        )
        self.assertNotContains(
            path_window[: path_window.find("completedResourcePath")],
            "transaction.updateMessage",
        )
        self.assertNotContains(restore, "archivedMedia(accountId:")
        for forbidden in ("network.request", "fetchedResource", "resourceData(", "fetchResource"):
            self.assertNotContains(restore, forbidden)


class ReplayLocalForwardUIContractTests(SourceContractTestCase):
    def test_burn_eligibility_fixture_covers_every_exclusion(self) -> None:
        eligible = BurnCase()
        self.assertTrue(burn_eligible(eligible))
        exclusions = {
            "multi": {"count": 2},
            "outgoing": {"incoming": False},
            "ordinary": {"ttl": False},
            "consumed": {"consumed": True},
            "noAttribute": {"has_consumable": False},
            "local": {"namespace": "local"},
            "scheduled": {"namespace": "scheduled"},
            "secret": {"peer": "secret"},
            "poll": {"media": "poll"},
            "action": {"media": "action"},
        }
        for name, changes in exclusions.items():
            with self.subTest(name=name):
                self.assertFalse(burn_eligible(replace(eligible, **changes)))
        self.assertEqual("consume:force", burn_execution_steps(True)[-1])
        self.assertEqual("consume:force", burn_execution_steps(False)[-1])

    def test_burn_source_has_irreversible_truth_table_and_one_forced_call(self) -> None:
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        eligibility = swift_block(context_menu, "func grvmCanBurnMessage(")
        action = swift_block(context_menu, "func grvmBurnMessage(")
        self.assertContainsAll(
            eligibility,
            "messages.count == 1",
            "Namespaces.Message.Cloud",
            "Namespaces.Peer.CloudUser",
            "Namespaces.Peer.CloudGroup",
            "Namespaces.Peer.CloudChannel",
            ".Incoming",
            "TelegramMediaImage",
            "TelegramMediaFile",
            "ConsumableContentMessageAttribute",
            "!attribute.consumed",
            "minAutoremoveOrClearTimeout",
        )
        self.assertContainsAll(
            action,
            "textAlertController",
            "destructiveAction",
            "prepareConsumableMedia",
            "markMessageContentAsConsumedInteractively",
            "force: true",
        )
        self.assertOrdered(
            action,
            "textAlertController",
            "destructiveAction",
            "prepareConsumableMedia",
            "force: true",
        )
        confirmation = swift_block(action, "destructiveAction")
        self.assertContainsAll(
            confirmation,
            "prepareConsumableMedia",
            "markMessageContentAsConsumedInteractively",
            "force: true",
        )
        prepare_position = confirmation.find("prepareConsumableMedia")
        force_position = confirmation.find("force: true", prepare_position)
        prepare_to_force = confirmation[prepare_position:force_position]
        self.assertAnyContains(
            prepare_to_force,
            "{ _ in",
            "|> ignoreValues",
            "|> then(",
        )
        for forbidden in (
            "guard prepared else",
            "if prepared",
            "if !prepared",
            "prepared == false",
            "prepared else",
        ):
            self.assertNotContains(action, forbidden)
        self.assertNotContains(action, "filter { $0 }")
        self.assertEqual(1, action.count("force: true"))
        force_sites: list[str] = []
        force_pattern = re.compile(
            r"markMessageContentAsConsumedInteractively\(\s*"
            r"messageId:[^)]*?force:\s*true\s*\)",
            re.DOTALL,
        )
        for path in (ROOT / "submodules").rglob("*.swift"):
            text = path.read_text(encoding="utf-8")
            if force_pattern.search(text):
                force_sites.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            ["submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"],
            force_sites,
        )

    def test_replay_fixture_keeps_normal_receipts_and_disables_every_replay_edge(self) -> None:
        self.assertTrue(all(replay_flow(True).values()))
        self.assertFalse(any(replay_flow(False).values()))
        self.assertTrue(replay_eligible(ReplayCase(consumed=True)))
        self.assertTrue(replay_eligible(ReplayCase(consumed=False, expired=True)))
        self.assertTrue(replay_eligible(ReplayCase(consumed=False, locally_deleted=True)))
        for invalid in (
            ReplayCase(count=2),
            ReplayCase(has_marker=False),
            ReplayCase(consumed=False),
            ReplayCase(restored=False),
        ):
            self.assertFalse(replay_eligible(invalid))

    def test_replay_flag_propagates_through_gallery_and_playlist(self) -> None:
        interaction = source(
            "submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift"
        )
        account_open = source("submodules/AccountContext/Sources/OpenChatMessage.swift")
        chat_controller = source("submodules/TelegramUI/Sources/ChatController.swift")
        open_chat = source("submodules/TelegramUI/Sources/OpenChatMessage.swift")
        gallery_data = source("submodules/GalleryData/Sources/GalleryData.swift")
        secret_preview = source(
            "submodules/GalleryUI/Sources/SecretMediaPreviewController.swift"
        )
        playlist = source(
            "submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift"
        )

        open_message_params = swift_block(interaction, "public struct OpenMessageParams")
        self.assertContainsAll(
            open_message_params,
            "consumeOnOpen: Bool",
            "consumeOnOpen: Bool = true",
            "self.consumeOnOpen = consumeOnOpen",
        )
        self.assertContainsAll(
            account_open,
            "public let consumeOnOpen: Bool",
            "consumeOnOpen: Bool = true",
            "self.consumeOnOpen = consumeOnOpen",
        )
        self.assertContains(chat_controller, "consumeOnOpen: params.consumeOnOpen")
        self.assertGreaterEqual(open_chat.count("params.consumeOnOpen"), 2)
        self.assertContains(open_chat, "consumeOnOpen: params.consumeOnOpen")
        self.assertContains(open_chat, "consumeViewOnce: params.consumeOnOpen")
        self.assertContainsAll(
            gallery_data,
            "consumeOnOpen: Bool = true",
            "SecretMediaPreviewController(context: context, messageId: message.id, consumeOnOpen: consumeOnOpen)",
        )
        self.assertContainsAll(
            secret_preview,
            "private let consumeOnOpen: Bool",
            "consumeOnOpen: Bool = true",
            "self.consumeOnOpen = consumeOnOpen",
        )
        self.assertContainsAll(
            playlist,
            "consumeViewOnce: Bool = true",
            "self.consumeViewOnce = consumeViewOnce",
            "consumeViewOnce && self.message.minAutoremoveOrClearTimeout == viewOnceTimeout",
        )

    def test_replay_receipt_gates_prepare_and_consume_only_on_normal_open(self) -> None:
        secret_preview = source(
            "submodules/GalleryUI/Sources/SecretMediaPreviewController.swift"
        )
        playlist = source(
            "submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift"
        )
        apply_view = swift_block(secret_preview, "private func applyMessageView()")
        playback_started = swift_block(playlist, "public func onItemPlaybackStarted(")
        self.assertContainsAll(
            apply_view,
            "if self.consumeOnOpen",
            "prepareConsumableMedia",
            "markMessageContentAsConsumedInteractively",
        )
        self.assertMatches(
            apply_view,
            r"(?s)if\s+self\.consumeOnOpen\s*\{.*?"
            r"prepareConsumableMedia.*?markMessageContentAsConsumedInteractively.*?\}",
        )
        self.assertEqual(1, apply_view.count("markMessageContentAsConsumedInteractively"))
        self.assertOrdered(
            apply_view,
            "if self.consumeOnOpen",
            "prepareConsumableMedia",
            "markMessageContentAsConsumedInteractively",
        )
        self.assertNotContains(apply_view, "force: true")
        self.assertContainsAll(
            playback_started,
            "consumeViewOnce",
            "viewOnceTimeout",
            "markMessageContentAsConsumedInteractively",
        )
        self.assertMatches(
            playback_started,
            r"(?s)(?:if|guard)\s+(?=[^\{]*consumeViewOnce)"
            r"(?=[^\{]*viewOnceTimeout)(?=[^\{]*(?:\|\||return))"
            r"[^\{]*\{?.{0,1200}markMessageContentAsConsumedInteractively",
        )
        receipt_condition = next(
            (
                match.group(1)
                for match in re.finditer(r"(?:if|guard)\s+([^\{]+)", playback_started)
                if "consumeViewOnce" in match.group(1) and "viewOnceTimeout" in match.group(1)
            ),
            "",
        )
        self.assertContainsAll(receipt_condition, "||", "!=")
        self.assertNotContains(playback_started, "force: true")
        self.assertEqual(1, playback_started.count("markMessageContentAsConsumedInteractively"))

    def test_replay_restore_is_rechecked_and_opens_a_fresh_message(self) -> None:
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        eligibility = swift_block(context_menu, "func grvmCanReplayMessage(")
        replay = action_block(context_menu, "Replay")
        replay_row_start = context_menu.find('text: "Replay"')
        replay_row_prefix = context_menu[max(0, replay_row_start - 2500) : replay_row_start]
        self.assertContainsAll(
            eligibility,
            "Signal<Bool, NoError>",
            "messages.count == 1",
            "GRVMPreservedConsumableMediaAttribute",
            "ConsumableContentMessageAttribute",
            "attribute.consumed",
            "TelegramMediaExpiredContent",
            "isLocallyDeletedMessage",
            "restoreConsumableMedia",
            "accountPeerId",
        )
        self.assertNotContains(eligibility, ".single(true)")
        self.assertGreaterEqual(context_menu.count("restoreConsumableMedia"), 2)
        replay_gate = around(context_menu, "grvmCanReplayMessage(", 500, 6000)
        self.assertAnyContains(
            replay_gate,
            "filter { $0 }",
            "guard canReplay else",
            "if canReplay",
        )
        self.assertOrdered(replay_gate, "grvmCanReplayMessage(", 'text: "Replay"')
        self.assertContainsAll(
            replay,
            "GRVMPreservedConsumableMediaAttribute",
            "restoreConsumableMedia",
            "accountPeerId",
            "transaction.getMessage(message.id)",
            "consumeOnOpen: false",
            "controllerInteraction.openMessage",
        )
        restore_position = replay.find("restoreConsumableMedia")
        restore_result = re.search(
            r"(?:let|guard\s+let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=.*?"
            r"restoreConsumableMedia",
            replay,
            re.DOTALL,
        )
        self.assertIsNotNone(restore_result, msg="Replay must bind the restore result")
        restore_guard = re.search(
            r"guard\s+([A-Za-z_][A-Za-z0-9_]*)\s+else",
            replay[restore_position:],
        )
        self.assertIsNotNone(restore_guard, msg="Replay must fail closed after restore verification")
        self.assertEqual(restore_result.group(1), restore_guard.group(1))
        failure_branch = swift_block(replay[restore_position:], f"guard {restore_guard.group(1)} else")
        self.assertAnyContains(failure_branch, "return", "show", "alert", "dismiss")
        self.assertNotContains(failure_branch, "openMessage")
        fresh_row = re.search(
            r"guard\s+let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"transaction\.getMessage\(message\.id\)\s+else",
            replay,
        )
        self.assertIsNotNone(fresh_row, msg="Replay must reload the Postbox row before opening")
        fresh_name = fresh_row.group(1)
        fresh_open_anchor = f"controllerInteraction.openMessage({fresh_name}"
        if fresh_open_anchor not in replay:
            fresh_open_anchor = f"controllerInteraction.openMessage(message: {fresh_name}"
        self.assertContains(replay, fresh_open_anchor)
        self.assertAnyContains(
            replay_row_prefix,
            "if canReplay",
            "guard canReplay else",
            "filter { $0 }",
        )
        self.assertOrdered(
            replay,
            "restoreConsumableMedia",
            "guard " + restore_guard.group(1) + " else",
            "consumeOnOpen: false",
            fresh_open_anchor,
        )

    def test_local_copy_fixture_distinguishes_ready_unavailable_and_unsupported(self) -> None:
        cases = {
            "protectedText": (
                LocalCopyCase(source_protected=True, text="safe text"),
                "ready",
            ),
            "deletedImage": (
                LocalCopyCase(deleted=True, media=("image",), current_size=10),
                "ready",
            ),
            "restoredVoice": (
                LocalCopyCase(one_play=True, media=("file",), restored_size=20),
                "ready",
            ),
            "ordinary": (
                LocalCopyCase(media=("image",), current_size=10),
                "notCandidate",
            ),
            "poll": (
                LocalCopyCase(source_protected=True, media=("poll",)),
                "unsupported",
            ),
            "mixed": (
                LocalCopyCase(source_protected=True, media=("image", "poll"), current_size=10),
                "unsupported",
            ),
            "missingBytes": (
                LocalCopyCase(ttl=True, media=("file",)),
                "unavailable",
            ),
            "emptyText": (
                LocalCopyCase(chat_protected=True),
                "unsupported",
            ),
        }
        for name, (case, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(expected, local_copy_outcome(case))

    def test_safe_entity_fixture_uses_utf16_ranges_and_drops_custom_emoji(self) -> None:
        text = "A\U0001f600B"
        utf16_length = len(text.encode("utf-16-le")) // 2
        self.assertEqual(4, utf16_length)
        self.assertTrue(safe_entity(("Bold", 0, 1), utf16_length))
        self.assertTrue(safe_entity(("Italic", 1, 3), utf16_length))
        self.assertFalse(safe_entity(("CustomEmoji", 1, 3), utf16_length))
        self.assertFalse(safe_entity(("Bold", -1, 1), utf16_length))
        self.assertFalse(safe_entity(("Bold", 1, 1), utf16_length))
        self.assertFalse(safe_entity(("Bold", 3, 5), utf16_length))
        self.assertEqual(
            ("FileName", "ImageSize", "Sticker", "Animated", "Video", "Audio"),
            safe_file_attributes(
                (
                    "FileName",
                    "HasLinkedStickers",
                    "ImageSize",
                    "Sticker",
                    "hintFileIsLarge",
                    "Animated",
                    "NoPremium",
                    "Video",
                    "CustomEmoji",
                    "Audio",
                    "hintIsValidated",
                )
            ),
        )

    def test_local_copy_uses_fresh_positive_standalone_resources_and_safe_metadata(self) -> None:
        enqueue = source("submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift")
        attribute_switch = swift_block(enqueue, "switch attribute")
        entity_switch = swift_block(enqueue, "switch entity.type")
        custom_emoji_case = switch_case(entity_switch, "case .CustomEmoji:")
        self.assertContainsAll(
            enqueue,
            "enum GRVMPreservedMediaEnqueueError: Error",
            "case unsupported",
            "case unavailable",
            "Signal<EnqueueMessage, GRVMPreservedMediaEnqueueError>",
            ".fail(.unsupported)",
            ".fail(.unavailable)",
            "restoreConsumableMedia",
            "completedResourcePath",
            "LocalFileReferenceMediaResource",
            "FileManager.default.temporaryDirectory",
            "linkItem",
            "copyItem",
            "isUniquelyReferencedTemporaryFile: true",
            "Namespaces.Media.LocalImage",
            "Namespaces.Media.LocalFile",
            "Int64.random",
            ".standalone(media:",
            "partialReference: nil",
            "reference: nil",
            "immediateThumbnailData: nil",
            "TextEntitiesMessageAttribute",
            "inlineStickers: [:]",
            "switch attribute",
            "case .FileName",
            "case .ImageSize",
            "case .Sticker",
            "case .Animated",
            "case .Video",
            "case .Audio",
            "case .CustomEmoji",
            "(text as NSString).length",
            "entity.range.lowerBound >= 0",
            "entity.range.upperBound <= (text as NSString).length",
            "replyToMessageId: nil",
            "replyToStoryId: nil",
            "default:",
            "previewRepresentations: []",
            "videoThumbnails: []",
            "videoCover: nil",
            "alternativeRepresentations: []",
        )
        self.assertMatches(enqueue, r"(?s)guard\s+.*(size|byteCount).*?>\s*0")
        self.assertMatches(
            enqueue,
            r"(?s)LocalFileReferenceMediaResource\(.*?"
            r"isUniquelyReferencedTemporaryFile:\s*true.*?size:\s*[A-Za-z_]",
        )
        self.assertContains(attribute_switch, "default:")
        self.assertNotContains(attribute_switch, "attributes.append(attribute)")
        self.assertContains(entity_switch, "switch entity.type")
        self.assertContains(custom_emoji_case, "case .CustomEmoji:")
        self.assertAnyContains(custom_emoji_case, "continue", "return nil", "return false")
        for entity_kind in SAFE_ENTITIES:
            self.assertContains(entity_switch, f".{entity_kind}")
        self.assertContains(entity_switch, "default:")
        self.assertNotContains(enqueue, "removeItem(at:")
        self.assertNotContains(enqueue, "removeItem(atPath:")
        self.assertNotContains(enqueue, "unlink(")
        self.assertAnyContains(enqueue, "message.media.count", "media.count !=")
        for forbidden in (
            ".forward(",
            "enqueueMessages(",
            "pendingMessageManager",
            "network.request",
            "fetchedResource",
            "HasLinkedStickers",
            "hintFileIsLarge",
            "hintIsValidated",
            "NoPremium",
            "copyProtectionEnabled",
            "isCopyProtected",
            "noForwards",
        ):
            self.assertNotContains(enqueue, forbidden)

    def test_local_copy_bridge_is_nullable_chat_owned_and_separate_from_stock_forward(self) -> None:
        interaction = source(
            "submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift"
        )
        chat_controller = source("submodules/TelegramUI/Sources/ChatController.swift")
        context_menu = source(
            "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
        )
        forward = source("submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift")
        local_forward = swift_block(forward, "func forwardLocalCopy(message: Message)")
        eligibility = swift_block(context_menu, "func grvmCanForwardLocalCopy(")
        local_action = around(context_menu, 'text: "Forward Local Copy"', 5000, 5000)
        self.assertContainsAll(
            eligibility,
            "messages.count == 1",
            "isLocallyDeletedMessage",
            "minAutoremoveOrClearTimeout",
            "copyProtectionEnabled",
            "isCopyProtected()",
            "TelegramMediaImage",
            "TelegramMediaFile",
            "completedResourcePath",
            "restoreConsumableMedia",
            "accountPeerId",
        )
        self.assertAnyContains(eligibility, "!message.text.isEmpty", "message.text.isEmpty == false")
        self.assertAnyContains(eligibility, "message.media.count", "message.media.isEmpty")
        self.assertMatches(
            eligibility,
            r"(?s)completedResourcePath.*?(?:fileSize|byteCount|size).*?>\s*0",
        )
        self.assertContains(interaction, "public var grvmForwardLocalCopy: ((Message) -> Void)?")
        self.assertContains(chat_controller, "controllerInteraction.grvmForwardLocalCopy = { [weak self] message in")
        self.assertContainsAll(
            local_action,
            "messages.count == 1",
            "grvmCanForwardLocalCopy",
            "grvmForwardLocalCopy?(message)",
        )
        self.assertContainsAll(
            local_forward,
            "func forwardLocalCopy(message: Message)",
            "GRVMPreservedMediaEnqueue",
            "localCopy: EnqueueMessage?",
            "forwardMessages(messages:",
        )
        self.assertContains(local_forward, "localCopy: localCopy")
        self.assertNotContains(local_forward, ".forward(source:")
        self.assertNotContains(local_forward, "withUpdatedForwardMessageIds")
        self.assertOrdered(local_forward, "GRVMPreservedMediaEnqueue", "forwardMessages(messages:")
        for error_case in ("case .unsupported", "case .unavailable"):
            error_branch = switch_case(local_forward, error_case)
            if error_branch:
                self.assertNotContains(error_branch, "forwardMessages(")
                self.assertAnyContains(error_branch, "return", "present", "alert")
        catch_branch = swift_block(local_forward, "catch")
        if catch_branch:
            self.assertNotContains(catch_branch, "forwardMessages(")
            self.assertAnyContains(catch_branch, "return", "present", "alert")
        self.assertAnyContains(local_forward, "case .unsupported", "catch")
        self.assertAnyContains(local_forward, "case .unavailable", "catch")

    def test_local_copy_reuses_stock_selector_paid_commit_enqueue_and_pending_pipeline(self) -> None:
        forward = source("submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift")
        common_forward = swift_block(forward, "func forwardMessages(messages: [Message]")
        self.assertContainsAll(
            common_forward,
            ".onlyWriteable",
            ".excludeDisabled",
            "selectForumThreads: true",
            "switch mode",
            "case .generic:",
            "case .silent:",
            "case .schedule:",
            "case .whenOnline:",
            "chatMessagePaymentAlertController",
            "OutgoingScheduleInfoMessageAttribute",
            "PaidStarsMessageAttribute",
            "shouldDivertMessagesToScheduled",
            "enqueueMessages(",
            "pendingMessageStatus",
            "if let localCopy",
            "commit(",
        )
        self.assertMatches(
            common_forward,
            r"forwardedMessageIds:\s*(?:"
            r"localCopy\s*==\s*nil\s*\?\s*messages\.map\s*\{\s*\$0\.id\s*\}\s*:\s*nil|"
            r"localCopy\s*!=\s*nil\s*\?\s*nil\s*:\s*messages\.map\s*\{\s*\$0\.id\s*\})",
        )
        self.assertOrdered(common_forward, "if let localCopy", "chatMessagePaymentAlertController")
        self.assertMatches(common_forward, r"(?s)if let localCopy.*result.*localCopy.*commit\(")
        self.assertEqual(1, common_forward.count("let commit: ([EnqueueMessage]) -> Void"))

    def test_stock_forward_remains_server_referenced_and_keeps_both_routes(self) -> None:
        forward = source("submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift")
        self.assertEqual(2, forward.count(".forward(source:"))
        self.assertContainsAll(
            forward,
            "forwardedMessageIds: messages.map { $0.id }",
            "return .forward(source: message.id",
            "return .forward(source: message.id, threadId: nil",
        )


if __name__ == "__main__":
    unittest.main()
