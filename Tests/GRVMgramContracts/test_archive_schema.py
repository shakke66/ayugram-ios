import json
import sqlite3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"
COORDINATOR = (
    ROOT / "submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift"
)
EDITABLE_CONTENT = (
    ROOT
    / "submodules/TelegramCore/Sources/SyncCore/GRVMEditableMessageContent.swift"
)
DELETED_ATTRIBUTE = (
    ROOT
    / "submodules/TelegramCore/Sources/SyncCore/GRVMDeletedMessageAttribute.swift"
)


def swift_sql(source: str, name: str) -> str:
    marker = f'static let {name} = """'
    start_index = source.find(marker)
    if start_index < 0:
        raise AssertionError(f"missing Swift SQL constant: {name}")
    start = start_index + len(marker)
    return source[start : source.index('"""', start)]


LEGACY_SCHEMA = """
CREATE TABLE deleted_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    date INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    media_description TEXT NOT NULL DEFAULT '',
    entity_create_date INTEGER NOT NULL,
    peer_title TEXT NOT NULL DEFAULT '',
    sender_name TEXT NOT NULL DEFAULT '',
    media_resources TEXT NOT NULL DEFAULT '',
    UNIQUE(peer_id, message_id, entity_create_date)
);
CREATE TABLE edited_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    date INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    media_description TEXT NOT NULL DEFAULT '',
    edit_date INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    peer_title TEXT NOT NULL DEFAULT '',
    sender_name TEXT NOT NULL DEFAULT '',
    media_resources TEXT NOT NULL DEFAULT '',
    UNIQUE(peer_id, message_id, version)
);
"""

PREVIOUS_LIFECYCLE_SCHEMA_V3 = """
CREATE TABLE archived_messages (
    account_id INTEGER NOT NULL,
    peer_id INTEGER NOT NULL,
    message_namespace INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL DEFAULT 0,
    sender_id INTEGER NOT NULL DEFAULT 0,
    message_timestamp INTEGER NOT NULL,
    deleted_at INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    entities BLOB NOT NULL DEFAULT X'',
    media_summary TEXT NOT NULL DEFAULT '',
    peer_title TEXT NOT NULL DEFAULT '',
    sender_name TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (account_id, peer_id, message_namespace, message_id, thread_id)
);
CREATE TABLE edit_revisions (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    peer_id INTEGER NOT NULL,
    message_namespace INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    saved_at INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    entities BLOB NOT NULL DEFAULT X'',
    media_summary TEXT NOT NULL DEFAULT '',
    resource_ids BLOB NOT NULL DEFAULT X''
);
CREATE TABLE archived_media_blobs (
    account_id INTEGER NOT NULL,
    resource_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    byte_count INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT '',
    copy_state INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, resource_id)
);
PRAGMA user_version = 3;
"""


class ArchiveContractTests(unittest.TestCase):
    def test_editable_payload_uses_explicit_stable_projections(self) -> None:
        self.assertTrue(EDITABLE_CONTENT.exists())
        source = EDITABLE_CONTENT.read_text(encoding="utf-8")
        for token in (
            "public struct GRVMEditableMessageContent: Codable, Equatable",
            "public enum GRVMEditableMediaContent: Codable, Equatable",
            "TextEntitiesMessageAttribute",
            "ReplyMarkupMessageAttribute",
            "MediaSpoilerMessageAttribute",
            "WebpagePreviewMessageAttribute",
            "InvertMediaMessageAttribute",
            "OutgoingScheduleInfoMessageAttribute",
            "ScheduledRepeatAttribute",
            "case todo",
            "case poll",
            "case webpage",
            "case file",
            "case image",
            "Namespaces.Message.allScheduled.contains",
            "outputFormatting = [.sortedKeys]",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

        media_projection = source[source.index("private static func projectMedia(") :]
        self.assertNotIn("PostboxEncoder", media_projection)
        self.assertNotIn("encodeRootObject(media", source)
        for transient in (
            "completions",
            "pollHash",
            "immediateThumbnailData",
            "PartialMediaReference",
            "fileReference",
        ):
            with self.subTest(transient=transient):
                self.assertNotIn(transient, media_projection)

    def test_projection_fixture_ignores_runtime_state_and_tracks_editable_state(self) -> None:
        def project(media: dict) -> tuple:
            kind = media["kind"]
            if kind == "todo":
                return kind, media["flags"], media["text"], tuple(media["entities"]), tuple(media["items"])
            if kind == "poll":
                return (
                    kind,
                    media["id"],
                    media["publicity"],
                    media["poll_kind"],
                    media["text"],
                    tuple(media["entities"]),
                    tuple(media["options"]),
                    tuple(media["correct_answers"]),
                    media["closed"],
                    media["deadline"],
                )
            if kind == "webpage":
                return kind, media["url"], media["preview"]
            if kind == "file":
                return kind, media["id"], media["resource_id"], media["mime"], media["size"], tuple(media["display"])
            if kind == "image":
                return kind, media["id"], tuple(media["representations"]), tuple(media["flags"])
            raise AssertionError(kind)

        todo = {"kind": "todo", "flags": 1, "text": "T", "entities": (), "items": ((1, "A"),), "completions": ()}
        self.assertEqual(project(todo), project({**todo, "completions": ((1, 99),)}))
        self.assertNotEqual(project(todo), project({**todo, "items": ((1, "B"),)}))

        poll = {
            "kind": "poll", "id": 7, "publicity": "public", "poll_kind": "quiz",
            "text": "Q", "entities": (), "options": (("A", b"a"),),
            "correct_answers": (b"a",), "closed": False, "deadline": 10,
            "results": (), "voters": (), "poll_hash": 1,
        }
        self.assertEqual(project(poll), project({**poll, "results": ("runtime",), "voters": (9,), "poll_hash": 2}))
        self.assertNotEqual(project(poll), project({**poll, "options": (("B", b"b"),)}))

        pending = {"kind": "webpage", "url": "https://example.test", "preview": "large", "state": "pending"}
        loaded = {**pending, "state": "loaded", "title": "hydrated", "instant_page": b"runtime"}
        self.assertEqual(project(pending), project(loaded))

        file_media = {"kind": "file", "id": 3, "resource_id": "r", "mime": "a/b", "size": 4, "display": ("name.txt",), "file_reference": b"one", "immediate_thumbnail": b"a"}
        self.assertEqual(project(file_media), project({**file_media, "file_reference": b"two", "immediate_thumbnail": b"b"}))
        self.assertNotEqual(project(file_media), project({**file_media, "display": ("renamed.txt",)}))

        image = {"kind": "image", "id": 5, "representations": (("r", 10, 20),), "flags": (), "file_reference": b"one", "immediate_thumbnail": b"a"}
        self.assertEqual(project(image), project({**image, "file_reference": b"two", "immediate_thumbnail": b"b"}))
        self.assertNotEqual(project(image), project({**image, "representations": (("r", 20, 20),)}))

    def test_attribute_fixture_excludes_counters_and_reactions(self) -> None:
        editable = {
            "TextEntitiesMessageAttribute",
            "ReplyMarkupMessageAttribute",
            "MediaSpoilerMessageAttribute",
            "WebpagePreviewMessageAttribute",
            "InvertMediaMessageAttribute",
            "OutgoingScheduleInfoMessageAttribute",
            "ScheduledRepeatAttribute",
        }

        def project(attributes: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
            return tuple(attribute for attribute in attributes if attribute[0] in editable)

        base = [("TextEntitiesMessageAttribute", "bold")]
        runtime = base + [
            ("ViewCountMessageAttribute", "99"),
            ("ForwardCountMessageAttribute", "42"),
            ("ReactionsMessageAttribute", "updated"),
        ]
        self.assertEqual(project(base), project(runtime))
        self.assertNotEqual(
            project(base),
            project(base + [("ReplyMarkupMessageAttribute", "button")]),
        )

    def test_identical_canonical_replay_returns_existing_revision(self) -> None:
        db = sqlite3.connect(":memory:")
        db.execute(
            """CREATE TABLE revisions (
                   row_id INTEGER PRIMARY KEY,
                   fingerprint TEXT NOT NULL UNIQUE,
                   payload BLOB NOT NULL
               )"""
        )

        def save(payload: dict) -> int:
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            fingerprint = encoded.hex()
            existing = db.execute(
                "SELECT row_id FROM revisions WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if existing:
                return existing[0]
            cursor = db.execute(
                "INSERT INTO revisions (fingerprint, payload) VALUES (?, ?)",
                (fingerprint, encoded),
            )
            return cursor.lastrowid

        content = {"text": "same", "attributes": [], "media": [{"fileName": "a.txt"}]}
        self.assertEqual(save(content), save(dict(content)))
        self.assertEqual(1, db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0])
        self.assertNotEqual(
            save(content),
            save({**content, "media": [{"fileName": "b.txt"}]}),
        )

    def test_canonical_payload_round_trips_and_drives_fingerprint(self) -> None:
        models = MODELS.read_text(encoding="utf-8")
        store = STORE.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        self.assertGreaterEqual(models.count("editableContent: GRVMEditableMessageContent"), 2)
        self.assertIn("public func grvmContentFingerprint(_ content: GRVMEditableMessageContent)", models)
        self.assertIn("editable_content", store)
        self.assertIn(".data(try self.encodeEditableContent(draft.editableContent))", store)
        self.assertGreaterEqual(store.count("editable_content"), 5)
        self.assertIn("decodeEditableContent(", store)
        self.assertIn("GRVMEditableMessageContent.legacy(", store)
        self.assertIn("grvmContentFingerprint(content)", coordinator)
        self.assertNotIn("grvmContentFingerprint(\n            text:", coordinator)

    def test_canonical_encoding_failures_propagate_without_forced_crash(self) -> None:
        models = MODELS.read_text(encoding="utf-8")
        store = STORE.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")
        self.assertNotIn("try!", models)
        self.assertNotIn("try!", store)
        self.assertIn(
            "public func grvmContentFingerprint(_ content: GRVMEditableMessageContent) throws -> String",
            models,
        )
        self.assertIn("let fingerprint = try grvmContentFingerprint(content)", coordinator)
        self.assertIn(".data(try self.encodeEditableContent(draft.editableContent))", store)
        self.assertIn(
            "private func encodeEditableContent(_ content: GRVMEditableMessageContent) throws -> Data",
            store,
        )

    def test_message_key_contains_account_namespace_and_thread(self) -> None:
        source = MODELS.read_text(encoding="utf-8")
        for field in ("accountId", "peerId", "namespace", "messageId", "threadId"):
            self.assertIn(f"let {field}:", source)

    def test_cross_module_records_have_public_initializers(self) -> None:
        source = MODELS.read_text(encoding="utf-8")
        names = (
            "GRVMMessageKey",
            "GRVMArchivedMessage",
            "GRVMEditRevision",
            "GRVMEditRevisionDraft",
            "GRVMArchivedMedia",
            "GRVMArchiveQuery",
        )
        starts = [source.index(f"public struct {name}") for name in names]
        starts.append(source.index("public func grvmContentFingerprint"))
        for name, start, end in zip(names, starts, starts[1:]):
            self.assertIn("public init(", source[start:end], name)

    def test_store_schema_is_account_scoped(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        for column in (
            "account_id",
            "peer_id",
            "message_namespace",
            "message_id",
            "thread_id",
        ):
            self.assertIn(column, source)

    def test_revision_schema_has_thread_aware_uniqueness(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn(
            "UNIQUE(account_id, peer_id, message_namespace, message_id, thread_id, version)",
            source,
        )
        self.assertIn(
            "UNIQUE(account_id, peer_id, message_namespace, message_id, thread_id, fingerprint)",
            source,
        )

    def test_fresh_schema_executes_and_declares_v5_tables(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        db = sqlite3.connect(":memory:")
        db.executescript(swift_sql(source, "schemaV2"))
        db.executescript(swift_sql(source, "cleanupSchemaV3"))
        db.executescript(swift_sql(source, "deletionSuppressionSchemaV5"))
        db.execute("PRAGMA user_version = 5")
        names = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(
            {
                "archived_messages",
                "edit_revisions",
                "archived_media_blobs",
                "archived_message_media",
                "cleanup_jobs",
                "deleted_message_suppressions",
            }
            <= names
        )
        message_pk = [
            row[1]
            for row in db.execute("PRAGMA table_info(archived_messages)")
            if row[5]
        ]
        self.assertEqual(
            ["account_id", "peer_id", "message_namespace", "message_id", "thread_id"],
            message_pk,
        )
        self.assertEqual(5, db.execute("PRAGMA user_version").fetchone()[0])
        self.assertIn(
            "deletion_source",
            {row[1] for row in db.execute("PRAGMA table_info(archived_messages)")},
        )
        self.assertIn(
            "editable_content",
            {row[1] for row in db.execute("PRAGMA table_info(edit_revisions)")},
        )
        self.assertIn(
            "generation",
            {row[1] for row in db.execute("PRAGMA table_info(archived_media_blobs)")},
        )

    def test_populated_v2_schema_upgrades_to_v5_without_data_loss(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        db = sqlite3.connect(":memory:")
        db.executescript(swift_sql(source, "schemaV2"))
        db.execute(
            """INSERT INTO archived_messages (
                   account_id, peer_id, message_namespace, message_id, thread_id,
                   sender_id, message_timestamp, deleted_at, text
               ) VALUES (7, 11, 0, 22, 0, 33, 44, 55, 'kept')"""
        )
        db.execute("PRAGMA user_version = 2")

        db.executescript(swift_sql(source, "schemaV2"))
        db.executescript(swift_sql(source, "cleanupSchemaV3"))
        db.executescript(swift_sql(source, "deletionSuppressionSchemaV5"))
        db.execute("PRAGMA user_version = 5")

        self.assertEqual(
            (7, 11, 0, 22, 0, "kept"),
            db.execute(
                """SELECT account_id, peer_id, message_namespace, message_id,
                          thread_id, text FROM archived_messages"""
            ).fetchone(),
        )
        self.assertEqual(5, db.execute("PRAGMA user_version").fetchone()[0])
        self.assertIsNotNone(
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cleanup_jobs'"
            ).fetchone()
        )

    def test_populated_v3_schema_upgrades_to_v5_with_safe_defaults(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn('static let lifecycleSchemaV4Migration = """', source)
        db = sqlite3.connect(":memory:")
        db.executescript(PREVIOUS_LIFECYCLE_SCHEMA_V3)
        db.execute(
            """INSERT INTO archived_messages (
                   account_id, peer_id, message_namespace, message_id, thread_id,
                   sender_id, message_timestamp, deleted_at, text
               ) VALUES (7, 11, 0, 22, 0, 33, 44, 55, 'deleted')"""
        )
        db.execute(
            """INSERT INTO edit_revisions (
                   account_id, peer_id, message_namespace, message_id, thread_id,
                   version, fingerprint, saved_at, text
               ) VALUES (7, 11, 0, 22, 0, 0, 'legacy', 66, 'old')"""
        )
        db.execute(
            """INSERT INTO archived_media_blobs (
                   account_id, resource_id, relative_path, byte_count, kind, copy_state
               ) VALUES (7, 'resource', '7/blobs/aa/resource', 10, 'file', 2)"""
        )

        db.executescript(swift_sql(source, "lifecycleSchemaV4Migration"))
        db.executescript(swift_sql(source, "deletionSuppressionSchemaV5"))
        db.execute("PRAGMA user_version = 5")

        self.assertEqual(
            ("deleted", 0),
            db.execute(
                "SELECT text, deletion_source FROM archived_messages"
            ).fetchone(),
        )
        self.assertEqual(
            ("old", b""),
            db.execute(
                "SELECT text, editable_content FROM edit_revisions"
            ).fetchone(),
        )
        self.assertEqual(
            ("resource", 0),
            db.execute(
                "SELECT resource_id, generation FROM archived_media_blobs"
            ).fetchone(),
        )
        self.assertEqual(5, db.execute("PRAGMA user_version").fetchone()[0])
        self.assertIsNotNone(
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'deleted_message_suppressions'"
            ).fetchone()
        )

    def test_v5_suppression_primary_key_is_exact_and_collision_free(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        db = sqlite3.connect(":memory:")
        db.executescript(swift_sql(source, "deletionSuppressionSchemaV5"))

        rows = (
            (1, 2, 3, 4, 5),
            (9, 2, 3, 4, 5),
            (1, 9, 3, 4, 5),
            (1, 2, 9, 4, 5),
            (1, 2, 3, 9, 5),
            (1, 2, 3, 4, 9),
        )
        db.executemany(
            """INSERT INTO deleted_message_suppressions (
                   account_id, peer_id, message_namespace, message_id, thread_id
               ) VALUES (?, ?, ?, ?, ?)""",
            rows,
        )
        db.execute(
            """INSERT OR IGNORE INTO deleted_message_suppressions (
                   account_id, peer_id, message_namespace, message_id, thread_id
               ) VALUES (1, 2, 3, 4, 5)"""
        )

        self.assertEqual(
            list(rows),
            db.execute(
                """SELECT account_id, peer_id, message_namespace, message_id, thread_id
                   FROM deleted_message_suppressions ORDER BY rowid"""
            ).fetchall(),
        )

    def test_all_deletion_sources_round_trip_through_archive_column(self) -> None:
        attribute = DELETED_ATTRIBUTE.read_text(encoding="utf-8")
        cases = re.findall(r"case\s+(\w+)\s*=\s*(\d+)", attribute)
        self.assertEqual(
            [
                ("server", "0"),
                ("localAction", "1"),
                ("ttl", "2"),
                ("secretRecall", "3"),
                ("validation", "4"),
                ("minimumAvailable", "5"),
            ],
            cases,
        )

        source = STORE.read_text(encoding="utf-8")
        self.assertIn("deletion_source INTEGER NOT NULL DEFAULT 0", swift_sql(source, "schemaV2"))
        db = sqlite3.connect(":memory:")
        db.executescript(swift_sql(source, "schemaV2"))
        for message_id, (_, raw_value) in enumerate(cases, start=1):
            db.execute(
                """INSERT INTO archived_messages (
                       account_id, peer_id, message_namespace, message_id, thread_id,
                       sender_id, message_timestamp, deleted_at, deletion_source, text
                   ) VALUES (7, 11, 0, ?, 0, 33, 44, 55, ?, 'deleted')""",
                (message_id, int(raw_value)),
            )
        self.assertEqual(
            list(range(6)),
            [
                row[0]
                for row in db.execute(
                    "SELECT deletion_source FROM archived_messages ORDER BY message_id"
                )
            ],
        )

    def test_deletion_source_raw_value_is_persisted_and_reconciled(self) -> None:
        models = MODELS.read_text(encoding="utf-8")
        store = STORE.read_text(encoding="utf-8")
        coordinator = COORDINATOR.read_text(encoding="utf-8")

        self.assertIn("public let deletionSource: Int32", models)
        preservation = coordinator[
            coordinator.index("private func preserveDeletedMessagesOnQueue(") :
            coordinator.index("public func preserveEditRevision(")
        ]
        self.assertIn("deletionSource: source.rawValue", preservation)
        reconciliation = coordinator[
            coordinator.index("public func reconcilePersistentMessageState()") :
            coordinator.index("public func settingsSnapshot()")
        ]
        self.assertIn(
            "GRVMDeletionSource(rawValue: record.deletionSource) ?? .server",
            reconciliation,
        )
        self.assertGreaterEqual(store.count("deletion_source"), 6)

    def test_one_account_legacy_copy_sql_attributes_every_row(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        db = sqlite3.connect(":memory:")
        db.executescript(LEGACY_SCHEMA)
        db.execute(
            """INSERT INTO deleted_messages
               (peer_id, message_id, sender_id, date, text, media_description,
                entity_create_date, peer_title, sender_name, media_resources)
               VALUES (11, 22, 33, 44, 'deleted', 'photo', 55, 'peer', 'sender', 'r1')"""
        )
        db.execute(
            """INSERT INTO edited_messages
               (peer_id, message_id, sender_id, date, text, media_description,
                edit_date, version, peer_title, sender_name, media_resources)
               VALUES (11, 22, 33, 44, 'old', 'photo', 66, 0, 'peer', 'sender', 'r1')"""
        )
        db.execute("ALTER TABLE deleted_messages RENAME TO deleted_messages_legacy_v1")
        db.execute("ALTER TABLE edited_messages RENAME TO edited_messages_legacy_v1")
        db.executescript(swift_sql(source, "schemaV2"))
        db.execute(swift_sql(source, "migrateDeletedV1"), (777,))
        db.execute(swift_sql(source, "migrateEditedV1"), (777,))
        self.assertEqual(
            (777, 11, 0, 22, 0, "deleted"),
            db.execute(
                """SELECT account_id, peer_id, message_namespace, message_id,
                          thread_id, text FROM archived_messages"""
            ).fetchone(),
        )
        self.assertEqual(
            (777, 11, 0, 22, 0, 0, "old"),
            db.execute(
                """SELECT account_id, peer_id, message_namespace, message_id,
                          thread_id, version, text FROM edit_revisions"""
            ).fetchone(),
        )

    def test_one_account_legacy_media_relationships_are_adopted(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        migration_names = (
            "migrateDeletedMediaBlobsV1",
            "migrateDeletedMediaMappingsV1",
            "migrateEditedMediaBlobsV1",
            "migrateEditedMediaMappingsV1",
        )
        for name in migration_names:
            self.assertIn(f'static let {name} = """', source)

        db = sqlite3.connect(":memory:")
        db.executescript(LEGACY_SCHEMA)
        db.execute(
            """INSERT INTO deleted_messages
               (peer_id, message_id, sender_id, date, text, media_description,
                entity_create_date, peer_title, sender_name, media_resources)
               VALUES (11, 22, 33, 44, 'deleted', 'photo', 55, 'peer', 'sender',
                       'r1,r2,r1')"""
        )
        db.execute(
            """INSERT INTO edited_messages
               (peer_id, message_id, sender_id, date, text, media_description,
                edit_date, version, peer_title, sender_name, media_resources)
               VALUES (11, 22, 33, 44, 'old', 'photo', 66, 0, 'peer', 'sender',
                       'r2,r3')"""
        )
        db.execute("ALTER TABLE deleted_messages RENAME TO deleted_messages_legacy_v1")
        db.execute("ALTER TABLE edited_messages RENAME TO edited_messages_legacy_v1")
        db.executescript(swift_sql(source, "schemaV2"))
        db.execute(swift_sql(source, "migrateDeletedV1"), (777,))
        db.execute(swift_sql(source, "migrateEditedV1"), (777,))
        for name in migration_names:
            db.execute(swift_sql(source, name), (777,))

        self.assertEqual(
            [(777, "r1", 0), (777, "r2", 0), (777, "r3", 0)],
            db.execute(
                """SELECT account_id, resource_id, copy_state
                   FROM archived_media_blobs ORDER BY resource_id"""
            ).fetchall(),
        )
        revision_id = db.execute("SELECT row_id FROM edit_revisions").fetchone()[0]
        self.assertEqual(
            [(0, "r1"), (0, "r2"), (revision_id, "r2"), (revision_id, "r3")],
            db.execute(
                """SELECT revision_id, resource_id FROM archived_message_media
                   ORDER BY revision_id, resource_id"""
            ).fetchall(),
        )

    def test_migration_contract_quarantines_ambiguous_legacy_rows(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        for token in (
            "BEGIN IMMEDIATE",
            "ROLLBACK",
            "PRAGMA user_version = 5",
            "case 2:",
            "case 3:",
            "case 4:",
            "case 5:",
            "activeAccountRecordIds.count == 1",
            "deleted_messages_legacy_v1",
            "edited_messages_legacy_v1",
            "sqlite3_bind_int64",
        ):
            self.assertIn(token, source)

    def test_store_owns_its_sqlite_destructor_and_returns_array_resources(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("private let grvmSQLiteTransient", source)
        self.assertNotIn(", SQLITE_TRANSIENT)", source)
        self.assertIn(
            "resourceIds: try self.mappedResourceIds(database, key: key, revisionId: 0).sorted()",
            source,
        )

    def test_empty_data_is_bound_as_a_zero_length_blob(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("if value.isEmpty", source)
        self.assertIn("sqlite3_bind_zeroblob(statement, index, 0)", source)

    def test_media_admission_enters_new_copying_generation(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn('static let mediaAdmissionSQL = """', source)
        admission = swift_sql(source, "mediaAdmissionSQL")
        self.assertIn("generation = excluded.generation", admission)
        self.assertIn("copy_state = excluded.copy_state", admission)
        self.assertNotIn("archived_media_blobs.copy_state = 2", admission)

    def test_media_generation_cas_blocks_stale_completion_and_resurrection(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn('static let mediaAdmissionSQL = """', source)
        self.assertIn('static let mediaTerminalUpdateSQL = """', source)
        admission = swift_sql(source, "mediaAdmissionSQL")
        terminal = swift_sql(source, "mediaTerminalUpdateSQL")
        self.assertIn("generation = ?", terminal)
        self.assertIn("sql: Self.mediaAdmissionSQL", source)
        self.assertIn("sql: Self.mediaTerminalUpdateSQL", source)

        db = sqlite3.connect(":memory:")
        db.executescript(swift_sql(source, "schemaV2"))
        db.execute(
            admission,
            (7, "resource", "7/blobs/aa/resource", 0, "file", 1, 1),
        )
        db.execute(
            admission,
            (7, "resource", "7/blobs/aa/resource", 0, "file", 1, 2),
        )
        stale = db.execute(
            terminal,
            ("7/blobs/aa/resource", 10, "file", 2, 7, "resource", 1),
        )
        self.assertEqual(0, stale.rowcount)
        self.assertEqual(
            (1, 2),
            db.execute(
                "SELECT copy_state, generation FROM archived_media_blobs"
            ).fetchone(),
        )

        db.execute(
            "DELETE FROM archived_media_blobs WHERE account_id = 7 AND resource_id = 'resource'"
        )
        resurrect = db.execute(
            terminal,
            ("7/blobs/aa/resource", 10, "file", 2, 7, "resource", 2),
        )
        self.assertEqual(0, resurrect.rowcount)
        self.assertEqual(
            0,
            db.execute("SELECT COUNT(*) FROM archived_media_blobs").fetchone()[0],
        )

    def test_cleanup_claim_invalidates_inflight_terminal_callback_before_unlink(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn('static let mediaCleanupClaimSQL = """', source)
        admission = swift_sql(source, "mediaAdmissionSQL")
        claim = swift_sql(source, "mediaCleanupClaimSQL")
        terminal = swift_sql(source, "mediaTerminalUpdateSQL")

        db = sqlite3.connect(":memory:")
        db.executescript(swift_sql(source, "schemaV2"))
        db.execute(
            admission,
            (7, "resource", "7/blobs/aa/resource", 0, "file", 1, 1),
        )
        claimed = db.execute(
            claim,
            (0, 7, "resource", "7/blobs/aa/resource", 1),
        )
        self.assertEqual(1, claimed.rowcount)

        stale = db.execute(
            terminal,
            ("7/blobs/aa/resource", 10, "file", 2, 7, "resource", 1),
        )
        self.assertEqual(0, stale.rowcount)
        self.assertEqual(
            (0, 2),
            db.execute(
                "SELECT copy_state, generation FROM archived_media_blobs"
            ).fetchone(),
        )
        self.assertIn("sql: Self.mediaCleanupClaimSQL", source)

    def test_media_lookup_batches_large_cache_removal_events(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("sqliteVariableBatchSize", source)
        self.assertIn("stride(from: 0, to: uniqueResourceIds.count", source)

    def test_query_iteration_does_not_swallow_sqlite_errors(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("private func readRows", source)
        self.assertIn("case SQLITE_DONE", source)
        self.assertIn("throw self.sqliteError(database)", source)
