import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"


def swift_sql(source: str, name: str) -> str:
    marker = f'static let {name} = """'
    start = source.index(marker) + len(marker)
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


class ArchiveContractTests(unittest.TestCase):
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

    def test_schema_executes_and_declares_v2_tables(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        db = sqlite3.connect(":memory:")
        db.executescript(swift_sql(source, "schemaV2"))
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
            "PRAGMA user_version = 2",
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

    def test_planned_media_cannot_downgrade_a_complete_blob(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("archived_media_blobs.copy_state = 2", source)
        self.assertIn("excluded.copy_state = 1", source)

    def test_query_iteration_does_not_swallow_sqlite_errors(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("private func readRows", source)
        self.assertIn("case SQLITE_DONE", source)
        self.assertIn("throw self.sqliteError(database)", source)
