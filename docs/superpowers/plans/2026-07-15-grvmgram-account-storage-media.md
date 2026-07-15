# GRVMgram Account Storage and Media Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the process-global flat archive with an account-scoped, migration-safe message/revision store, in-memory indexes, and persistent media backup/restore.

**Architecture:** Split database models, SQL storage, media files, and account coordination into focused units. Metadata commits synchronously on one serialized queue; downloaded media copies asynchronously to normalized account/resource paths; UI layout reads immutable in-memory indexes rather than SQLite.

**Tech Stack:** Swift, Foundation, SQLCipher C API, Postbox/MediaBox, SwiftSignalKit, Python 3.12 sqlite3/unittest.

## Global Constraints

- Keep the physical filename `ayugram_messages.db` for migration compatibility.
- Add `account_id`, message namespace, and thread ID to every archive key.
- Quarantine unattributed legacy rows when multiple accounts exist.
- Never read SQLite synchronously from a message-layout function.
- Back up only completed local MediaBox resources; do not initiate downloads.
- Use hard links when possible and streaming file copies otherwise; do not load large video files into Data.
- Persist relative paths only.
- Retain data until explicit cleanup; no automatic size or age limit.
- Do not launch GitHub Actions during this plan.

---

## File Map

### Create

- `submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift` — keys, records, fingerprints, query filters.
- `submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift` — SQLCipher schema v2, migration, CRUD, batch transactions.
- `submodules/AyuGramLib/Sources/GRVMMessageArchiveIndex.swift` — immutable deleted/revision identity snapshots.
- `submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift` — relative paths, atomic link/copy, restore, cleanup.
- `submodules/AyuGramLib/Sources/GRVMMediaResourceCollector.swift` — exhaustive resource enumeration from Telegram media.
- `submodules/AyuGramLib/Sources/GRVMAccountSettings.swift` — account-keyed settings envelope and legacy migration.
- `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift` — binds account, Postbox, MediaBox, store, indexes.
- `submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift` — synchronized active-account and primary-account service map.
- `Tests/GRVMgramContracts/test_archive_schema.py` — executable migration/account/fingerprint SQL tests.

### Replace

- `submodules/AyuGramLib/Sources/AyuDeletedMessagesDB.swift` — replaced with a compatibility facade only after lifecycle/UI consumers migrate in the next plan.

### Modify

- `submodules/AyuGramLib/Sources/AyuGramSettings.swift` — add account envelope accessors and new fields while preserving legacy Codable keys.
- `submodules/TelegramUIPreferences/Sources/PostboxKeys.swift` — add a new shared-data key for account settings.
- `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift` — use synchronized runtime state and account registry.
- `submodules/AyuGramLib/BUILD`
- `submodules/TelegramUI/Sources/AppDelegate.swift:1020-1125` — register active account contexts after SharedAccountContext exists.

### Delete after all consumers migrate

- None. Keep `AyuDeletedMessagesDB` as a thin deprecated facade for one release.

---

### Task 1: Define stable archive identities and content fingerprints

**Files:**
- Create: `submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift`
- Test: `Tests/GRVMgramContracts/test_archive_schema.py`

**Interfaces:**
- Produces: `GRVMMessageKey`, `GRVMArchivedMessage`, `GRVMEditRevisionDraft`, `GRVMEditRevision`, `GRVMArchivedMedia`, `GRVMArchiveQuery`.
- Consumes later: account store, coordinator, archive/history UI.

- [ ] **Step 1: Write failing source-contract tests**

```python
# Tests/GRVMgramContracts/test_archive_schema.py
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"


class ArchiveContractTests(unittest.TestCase):
    def test_message_key_contains_account_namespace_and_thread(self) -> None:
        source = MODELS.read_text(encoding="utf-8")
        for field in ("accountId", "peerId", "namespace", "messageId", "threadId"):
            self.assertIn(f"let {field}:", source)

    def test_store_schema_is_account_scoped(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        for column in ("account_id", "peer_id", "message_namespace", "message_id", "thread_id"):
            self.assertIn(column, source)

    def test_revision_schema_has_both_uniqueness_constraints(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("UNIQUE(account_id, peer_id, message_namespace, message_id, version)", source)
        self.assertIn("UNIQUE(account_id, peer_id, message_namespace, message_id, fingerprint)", source)
```

- [ ] **Step 2: Run the tests to verify missing files fail**

```powershell
python -m unittest Tests.GRVMgramContracts.test_archive_schema -v
```

Expected: FAIL with `FileNotFoundError` for `GRVMMessageArchiveModels.swift`.

- [ ] **Step 3: Add the exact public models**

```swift
import Foundation

public struct GRVMMessageKey: Hashable, Codable {
    public let accountId: Int64
    public let peerId: Int64
    public let namespace: Int32
    public let messageId: Int32
    public let threadId: Int64

    public init(accountId: Int64, peerId: Int64, namespace: Int32, messageId: Int32, threadId: Int64 = 0) {
        self.accountId = accountId
        self.peerId = peerId
        self.namespace = namespace
        self.messageId = messageId
        self.threadId = threadId
    }
}

public struct GRVMArchivedMessage: Equatable {
    public let key: GRVMMessageKey
    public let senderId: Int64
    public let timestamp: Int32
    public let deletedAt: Int32
    public let text: String
    public let entitiesData: Data
    public let mediaSummary: String
    public let resourceIds: [String]
    public let peerTitle: String
    public let senderName: String
}

public struct GRVMEditRevision: Equatable {
    public let rowId: Int64
    public let key: GRVMMessageKey
    public let version: Int32
    public let fingerprint: String
    public let savedAt: Int32
    public let text: String
    public let entitiesData: Data
    public let mediaSummary: String
    public let resourceIds: [String]
}

public struct GRVMEditRevisionDraft: Equatable {
    public let key: GRVMMessageKey
    public let fingerprint: String
    public let savedAt: Int32
    public let text: String
    public let entitiesData: Data
    public let mediaSummary: String
    public let resourceIds: [String]
}

public struct GRVMArchivedMedia: Equatable {
    public enum CopyState: Int32 {
        case unavailable = 0
        case copying = 1
        case complete = 2
        case missing = 3
    }

    public let accountId: Int64
    public let resourceId: String
    public let relativePath: String
    public let byteCount: Int64
    public let kind: String
    public let copyState: CopyState
}

public struct GRVMArchiveQuery: Equatable {
    public let accountId: Int64
    public let peerId: Int64?
    public let threadId: Int64?
    public let limit: Int32
}

public func grvmContentFingerprint(
    text: String,
    entitiesData: Data,
    mediaSummary: String,
    resourceIds: [String]
) -> String
```

- [ ] **Step 4: Run the model contract**

```powershell
python -m unittest Tests.GRVMgramContracts.test_archive_schema.ArchiveContractTests.test_message_key_contains_account_namespace_and_thread -v
```

Expected: PASS.

Implement `grvmContentFingerprint` with `JSONSerialization.data(withJSONObject:options: [.sortedKeys])`; encode `entitiesData` as base64 and sort/deduplicate `resourceIds` first. Return the canonical JSON data's base64 string. The exact same content therefore has the same fingerprint across launches without relying on Swift's randomized `Hasher`.

- [ ] **Step 5: Commit the models and red schema test**

```powershell
git add submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift Tests/GRVMgramContracts/test_archive_schema.py
git commit -m "feat: define account-scoped archive models"
```

### Task 2: Implement transactional schema v2 and legacy migration

**Files:**
- Create: `submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift`
- Test: `Tests/GRVMgramContracts/test_archive_schema.py`

**Interfaces:**
- Produces:

```swift
public final class GRVMMessageArchiveStore {
    public init(databaseURL: URL)
    public func migrate(activeAccountRecordIds: [Int64]) throws
    public func saveDeleted(_ messages: [GRVMArchivedMessage], media: [GRVMMessageKey: [GRVMArchivedMedia]]) throws
    public func saveRevision(_ draft: GRVMEditRevisionDraft, media: [GRVMArchivedMedia]) throws -> GRVMEditRevision
    public func updateMedia(_ record: GRVMArchivedMedia) throws
    public func deletedMessages(_ query: GRVMArchiveQuery) throws -> [GRVMArchivedMessage]
    public func editHistory(_ key: GRVMMessageKey) throws -> [GRVMEditRevision]
    public func deletedKeys(accountId: Int64) throws -> Set<GRVMMessageKey>
    public func revisedKeys(accountId: Int64) throws -> Set<GRVMMessageKey>
    public func archivedMedia(accountId: Int64, resourceIds: [String]) throws -> [GRVMArchivedMedia]
    public func deletedMessageKeys(accountId: Int64, peerId: Int64?, threadId: Int64?) throws -> [GRVMMessageKey]
    public func removeDeleted(_ keys: [GRVMMessageKey]) throws -> [GRVMArchivedMedia]
}
```

- [ ] **Step 1: Extend the failing tests with executable SQL requirements**

Add a test helper that extracts the triple-quoted `schemaV2` string from Swift, opens `:memory:`, executes it, and asserts:

```python
def test_schema_executes_and_declares_v2_tables(self) -> None:
    source = STORE.read_text(encoding="utf-8")
    start = source.index('static let schemaV2 = """') + len('static let schemaV2 = """')
    end = source.index('"""', start)
    db = sqlite3.connect(":memory:")
    db.executescript(source[start:end])
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    self.assertTrue({"archived_messages", "edit_revisions", "archived_media_blobs", "archived_message_media"} <= names)
```

- [ ] **Step 2: Run the schema tests**

```powershell
python -m unittest Tests.GRVMgramContracts.test_archive_schema -v
```

Expected: model test PASS; schema tests FAIL because the store is missing.

- [ ] **Step 3: Add the complete schema constant**

```sql
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS archived_messages (
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
    PRIMARY KEY (account_id, peer_id, message_namespace, message_id)
);
CREATE INDEX IF NOT EXISTS archived_messages_dialog
ON archived_messages(account_id, peer_id, thread_id, deleted_at DESC);

CREATE TABLE IF NOT EXISTS edit_revisions (
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
    resource_ids BLOB NOT NULL DEFAULT X'',
    UNIQUE(account_id, peer_id, message_namespace, message_id, version),
    UNIQUE(account_id, peer_id, message_namespace, message_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS edit_revisions_message
ON edit_revisions(account_id, peer_id, message_namespace, message_id, version);

CREATE TABLE IF NOT EXISTS archived_media_blobs (
    account_id INTEGER NOT NULL,
    resource_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    byte_count INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT '',
    copy_state INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, resource_id)
);

CREATE TABLE IF NOT EXISTS archived_message_media (
    account_id INTEGER NOT NULL,
    peer_id INTEGER NOT NULL,
    message_namespace INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL DEFAULT 0,
    resource_id TEXT NOT NULL,
    PRIMARY KEY (account_id, peer_id, message_namespace, message_id, revision_id, resource_id),
    FOREIGN KEY (account_id, resource_id)
      REFERENCES archived_media_blobs(account_id, resource_id) ON DELETE CASCADE
);
```

Embed this as `static let schemaV2`, execute it inside `BEGIN IMMEDIATE`, set `PRAGMA user_version = 2` only before COMMIT, and ROLLBACK on every thrown error.

- [ ] **Step 4: Implement deterministic migration**

Migration behavior:

```swift
let hasLegacyTables = tableExists("deleted_messages") || tableExists("edited_messages")
switch (userVersion, hasLegacyTables, activeAccountRecordIds.count) {
case (0, false, _):
    // Fresh database: create v2 without attempting ALTER TABLE.
case (0, true, 1):
    // Rename v1 tables, create v2, copy legacy rows to the sole account record.
case (0, true, _):
    // Rename v1 tables, create v2, retain *_legacy_v1 quarantine without copying.
case (2, _, _):
    break
default:
    throw GRVMArchiveError.unsupportedSchema(userVersion)
}
```

Use prepared statements for every value; never interpolate text into SQL. Version allocation executes `SELECT COALESCE(MAX(version), -1) + 1` and INSERT inside the same `BEGIN IMMEDIATE` transaction. On a fingerprint uniqueness conflict, query and return the existing `GRVMEditRevision` as a successful deduplicated write.

`saveDeleted` inserts message rows, `.copying` media-blob rows, and `revision_id = 0` mappings atomically. `saveRevision` allocates the version/row ID and creates mappings with that row ID in the same transaction. `updateMedia` changes the copy state/size only after the filesystem operation finishes.

`deletedMessageKeys` is read-only. `removeDeleted` runs after Postbox force-deletion, removes only `revision_id = 0` mappings plus matching `archived_messages` rows in one transaction, and removes an `archived_media_blobs` row only when no deletion or revision mapping for that `(account_id, resource_id)` remains. It returns only the now-unreferenced media records for filesystem cleanup.

- [ ] **Step 5: Verify legacy detection without breaking current consumers**

Add executable fixtures for a fresh empty database, the exact existing `deleted_messages`/`edited_messages` schema, one-account adoption, and multi-account quarantine. Keep `AyuDeletedMessagesDB.swift` unchanged in this task so existing hooks and settings screens continue to compile; the lifecycle plan replaces it only after every caller has moved to the coordinator.

- [ ] **Step 6: Run tests and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_archive_schema -v
git diff --check
git add submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift Tests/GRVMgramContracts/test_archive_schema.py
git commit -m "feat: add account-scoped archive schema"
```

Expected: all schema tests PASS.

### Task 3: Add immutable in-memory deleted/revision indexes

**Files:**
- Create: `submodules/AyuGramLib/Sources/GRVMMessageArchiveIndex.swift`
- Test: `Tests/GRVMgramContracts/test_archive_index_contract.py`

**Interfaces:**
- Produces:

```swift
public struct GRVMMessageArchiveSnapshot {
    public let deleted: Set<GRVMMessageKey>
    public let revised: Set<GRVMMessageKey>
}

public final class GRVMMessageArchiveIndex {
    public func snapshot() -> GRVMMessageArchiveSnapshot
    public func replace(_ snapshot: GRVMMessageArchiveSnapshot)
    public func insertDeleted(_ keys: Set<GRVMMessageKey>)
    public func insertRevised(_ key: GRVMMessageKey)
    public func removeDeleted(_ keys: Set<GRVMMessageKey>)
}

```

- [ ] **Step 1: Write a failing synchronization contract**

The Python test reads the source and asserts one `Atomic<GRVMMessageArchiveSnapshot>` owner, no `DispatchQueue.main.sync`, and no direct mutable `Set` property.

- [ ] **Step 2: Run the contract**

```powershell
python -m unittest Tests.GRVMgramContracts.test_archive_index_contract -v
```

Expected: FAIL because the index file is absent.

- [ ] **Step 3: Implement snapshot updates through Atomic**

```swift
import Postbox

public final class GRVMMessageArchiveIndex {
    private let state = Atomic(value: GRVMMessageArchiveSnapshot(deleted: [], revised: []))

    public func snapshot() -> GRVMMessageArchiveSnapshot {
        return self.state.with { $0 }
    }

    public func replace(_ snapshot: GRVMMessageArchiveSnapshot) {
        _ = self.state.swap(snapshot)
    }

    public func insertDeleted(_ keys: Set<GRVMMessageKey>) {
        self.state.modify { current in
            var deleted = current.deleted
            deleted.formUnion(keys)
            return GRVMMessageArchiveSnapshot(deleted: deleted, revised: current.revised)
        }
    }

    public func insertRevised(_ key: GRVMMessageKey) {
        self.state.modify { current in
            var revised = current.revised
            revised.insert(key)
            return GRVMMessageArchiveSnapshot(deleted: current.deleted, revised: revised)
        }
    }

    public func removeDeleted(_ keys: Set<GRVMMessageKey>) {
        self.state.modify { current in
            return GRVMMessageArchiveSnapshot(
                deleted: current.deleted.subtracting(keys),
                revised: current.revised
            )
        }
    }
}
```

- [ ] **Step 4: Define the future coordinator load contract**

Extend the source contract to require Task 6's coordinator to load `deletedKeys(accountId:)` and `revisedKeys(accountId:)`, then call `index.replace`. Every successful write must mutate the store first and the index second before publishing completion.

- [ ] **Step 5: Run and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_archive_index_contract -v
git diff --check
git add submodules/AyuGramLib/Sources/GRVMMessageArchiveIndex.swift Tests/GRVMgramContracts/test_archive_index_contract.py
git commit -m "perf: index archived message state in memory"
```

### Task 4: Make settings account-scoped with a legacy fallback

**Files:**
- Create: `submodules/AyuGramLib/Sources/GRVMAccountSettings.swift`
- Modify: `submodules/TelegramUIPreferences/Sources/PostboxKeys.swift:55-82`
- Modify: `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- Modify: all `submodules/AyuGramSettingsUI/Sources/AyuGram*Controller.swift` update calls
- Test: `Tests/GRVMgramContracts/test_account_settings_contract.py`

**Interfaces:**
- Produces:

```swift
public struct GRVMAccountSettings: Codable, Equatable {
    public var values: [Int64: AyuGramSettings]
}

public func grvmSettings(accountId: PeerId, accountManager: AccountManager<TelegramAccountManagerTypes>) -> Signal<AyuGramSettings, NoError>
public func updateGRVMSettings(accountId: PeerId, accountManager: AccountManager<TelegramAccountManagerTypes>, _ f: @escaping (AyuGramSettings) -> AyuGramSettings) -> Signal<Void, NoError>
public func migrateGRVMSettings(accountIds: [PeerId], accountManager: AccountManager<TelegramAccountManagerTypes>) -> Signal<Void, NoError>
```

- [ ] **Step 1: Write failing account-isolation contracts**

Assert:

- a new `ApplicationSpecificSharedDataKeyValues.grvmAccountSettings = 24`;
- every settings controller calls `updateGRVMSettings(accountId: context.account.peerId, ...)`;
- `migrateGRVMSettings` fills every missing authorized account without overwriting an existing account-specific value;
- the old `ayuGramSettings` key remains declared for decoding.

- [ ] **Step 2: Run the contract**

```powershell
python -m unittest Tests.GRVMgramContracts.test_account_settings_contract -v
```

Expected: FAIL with missing `grvmAccountSettings`.

- [ ] **Step 3: Implement the account envelope**

On first read of the new key:

```swift
if let accountSettings = newEntry?.get(GRVMAccountSettings.self) {
    return accountSettings.values[accountId.toInt64()] ?? .defaultSettings
}
if let legacy = legacyEntry?.get(AyuGramSettings.self) {
    return legacy
}
return .defaultSettings
```

`migrateGRVMSettings` performs one account-manager transaction, resolves the legacy/default value once, and fills only missing entries for every currently authorized account ID. The first account-specific update also writes the resolved legacy/default value under the current account when startup migration has not run yet. Do not erase the old shared key in this release.

- [ ] **Step 4: Enforce Ghost setting invariants in one mutation layer**

In `AyuGramSettings`, centralize:

```swift
public mutating func setReadOnAction(_ enabled: Bool) {
    self.readOnAction = enabled
    if enabled {
        self.useScheduledMessages = false
    }
}

public mutating func setScheduledMessages(_ enabled: Bool) {
    self.useScheduledMessages = enabled
    if enabled {
        self.readOnAction = false
    }
}
```

Do not let UI controllers write these fields directly.

- [ ] **Step 5: Update every controller and run contracts**

```powershell
python -m unittest Tests.GRVMgramContracts.test_account_settings_contract -v
rg -n "updateAyuGramSettings\(" submodules/AyuGramSettingsUI/Sources
```

Expected: tests PASS; the grep returns no settings-controller call.

- [ ] **Step 6: Commit**

```powershell
git add submodules/AyuGramLib/Sources/GRVMAccountSettings.swift submodules/AyuGramLib/Sources/AyuGramSettings.swift submodules/TelegramUIPreferences/Sources/PostboxKeys.swift submodules/AyuGramSettingsUI/Sources Tests/GRVMgramContracts/test_account_settings_contract.py
git commit -m "feat: scope GRVMgram settings by account"
```

### Task 5: Collect and persist every locally completed media resource

**Files:**
- Create: `submodules/AyuGramLib/Sources/GRVMMediaResourceCollector.swift`
- Create: `submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift`
- Modify: `submodules/Postbox/Sources/MediaBox.swift:308-380`
- Modify: `submodules/AyuGramLib/BUILD`
- Test: `Tests/GRVMgramContracts/test_media_archive_contract.py`

**Interfaces:**
- Produces:

```swift
public struct GRVMMediaResourceReference {
    public let id: MediaResourceId
    public let kind: String
}

public func grvmMediaResources(_ media: [Media]) -> [GRVMMediaResourceReference]

public final class GRVMArchivedMediaStore {
    public init(rootURL: URL, fileManager: FileManager = .default)
    public func plannedRecord(accountId: Int64, resource: GRVMMediaResourceReference) -> GRVMArchivedMedia
    public func archive(_ record: GRVMArchivedMedia, resource: GRVMMediaResourceReference, mediaBox: MediaBox) -> Signal<GRVMArchivedMedia, NoError>
    public func restore(_ record: GRVMArchivedMedia, to mediaBox: MediaBox) -> Signal<Bool, NoError>
    public func remove(_ records: [GRVMArchivedMedia])
}

public extension MediaBox {
    var didRemoveResourceIds: Signal<[MediaResourceId], NoError> { get }
    func restoreResourceData(_ id: MediaResourceId, fromPath path: String) -> Signal<Bool, NoError>
}
```

- [ ] **Step 1: Write the failing collector/path contracts**

The contract asserts source handling for:

```text
image.representations
image.videoRepresentations
image.video
file.resource
file.previewRepresentations
file.videoThumbnails
file.videoCover
file.alternativeRepresentations
TelegramMediaWebpage
TelegramMediaGame
TelegramMediaPaidContent
```

It also rejects absolute persisted paths and `Data(contentsOf:)` in the archive store.
The contract requires both cache-removal methods to publish only IDs whose files were actually unlinked.

- [ ] **Step 2: Run the media contract**

```powershell
python -m unittest Tests.GRVMgramContracts.test_media_archive_contract -v
```

Expected: FAIL because both source files are absent.

- [ ] **Step 3: Implement deduplicated resource collection**

Use a `Set<MediaResourceId>` while preserving first-seen order. Recursively visit nested media, skip duplicate resource IDs, and attach a stable kind string.

- [ ] **Step 4: Implement atomic archive writes**

`plannedRecord` deterministically returns a `.copying` row and relative path without touching the source file. The coordinator commits those rows with message/revision metadata, then starts `archive` on the media store's serial utility queue. For each completed resource, `archive`:

1. derive `<account>/blobs/<resource-hash-prefix>/<resource-hash>` and return `.complete` immediately when an existing final file has the expected byte count;
2. create the parent directory with `FileProtectionType.completeUntilFirstUserAuthentication` and set `URLResourceValues.isExcludedFromBackup = true`;
3. link to `*.tmp` when possible;
4. on cross-device/link failure, use `FileManager.copyItem`;
5. compare source/destination file sizes;
6. atomically move `*.tmp` to the final path;
7. emit a `.complete` record only after the final path exists, or `.unavailable` when the MediaBox resource was not complete.

The coordinator calls `GRVMMessageArchiveStore.updateMedia` for the emitted terminal record. It never waits for file bytes while holding the Postbox transaction or database transaction.

Import the existing `CryptoUtils` module, add `//submodules/CryptoUtils:CryptoUtils` to AyuGramLib's BUILD deps, and hash resource IDs with:

```swift
private func grvmResourceFilename(_ id: MediaResourceId) -> String {
    let data = Data(id.stringRepresentation.utf8)
    let digest: Data = data.withUnsafeBytes { bytes in
        CryptoSHA256(bytes.baseAddress!, Int32(data.count))
    }
    return digest.map { String(format: "%02x", $0) }.joined()
}
```

Do not persist raw resource strings as path segments.

- [ ] **Step 5: Add an error-reporting MediaBox restore API**

```swift
public func restoreResourceData(_ id: MediaResourceId, fromPath path: String) -> Signal<Bool, NoError> {
    return Signal { subscriber in
        let success = self.copyResourceDataFromArchive(id, path: path)
        if success {
            self.resourceDataSubscribers.updated(id)
        }
        subscriber.putNext(success)
        subscriber.putCompletion()
        return EmptyDisposable
    }
}
```

Implement with MediaBox's existing serial file queue and status contexts; do not call the current silent `copyResourceData(_:fromTempPath:)` wrapper.

Alongside the existing `didRemoveResources: Signal<Void, NoError>`, add `didRemoveResourceIds: Signal<[MediaResourceId], NoError>`. Accumulate IDs only after the complete/partial/meta unlink path runs (exclude resources skipped because a file/keep context is active), and emit that exact array from both cache-removal methods.

- [ ] **Step 6: Run contracts and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_media_archive_contract -v
git diff --check
git add submodules/AyuGramLib/Sources/GRVMMediaResourceCollector.swift submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift submodules/AyuGramLib/BUILD submodules/Postbox/Sources/MediaBox.swift Tests/GRVMgramContracts/test_media_archive_contract.py
git commit -m "feat: preserve downloaded deleted media"
```

### Task 6: Bind stores and services to active accounts

**Files:**
- Create: `submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift`
- Create: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/TelegramUI/Sources/AppDelegate.swift:1026-1125`
- Test: `Tests/GRVMgramContracts/test_account_registry_contract.py`

**Interfaces:**
- Produces:

```swift
public final class GRVMMessageArchiveCoordinator {
    public let accountPeerId: PeerId
    public let accountRecordId: AccountRecordId

    public init(
        accountPeerId: PeerId,
        accountRecordId: AccountRecordId,
        postbox: Postbox,
        mediaBox: MediaBox,
        store: GRVMMessageArchiveStore,
        mediaStore: GRVMArchivedMediaStore,
        settings: AyuGramSettings
    )

    public func settingsSnapshot() -> AyuGramSettings
    public func updateSettings(_ settings: AyuGramSettings)
    public func messageKey(_ message: Message) -> GRVMMessageKey
    public func hasEditHistory(_ id: MessageId) -> Bool
    public func deletedMessages(peerId: PeerId?, threadId: Int64?, query: String?) -> Signal<[GRVMArchivedMessage], NoError>
    public func editHistory(_ id: MessageId) -> Signal<[GRVMEditRevision], NoError>
}

public final class GRVMAccountFeatureRegistry {
    public func register(accountPeerId: PeerId, accountRecordId: AccountRecordId, postbox: Postbox, mediaBox: MediaBox)
    public func unregister(accountPeerId: PeerId)
    public func setPrimaryAccount(_ accountPeerId: PeerId?)
    public func service(accountPeerId: PeerId) -> GRVMMessageArchiveCoordinator?
    public func primaryService() -> GRVMMessageArchiveCoordinator?
    public func ownPeerIds() -> Set<PeerId>
}
```

- [ ] **Step 1: Write failing registry contracts**

Assert:

- registry state is held in `Atomic<RuntimeState>`;
- lookups require an explicit account ID;
- no default/current/global account fallback exists;
- AppDelegate registers contexts only after `SharedAccountContextImpl` creation;
- `AyuGramFeatureManager` no longer owns an unsynchronized process-global `currentSettings` value;
- Local Premium checks the tested peer against the primary service's own peer ID.

- [ ] **Step 2: Run the contract**

```powershell
python -m unittest Tests.GRVMgramContracts.test_account_registry_contract -v
```

Expected: FAIL because the registry is absent and manager still exposes global mutable settings.

- [ ] **Step 3: Implement synchronized runtime state**

```swift
private struct RuntimeState {
    var primaryAccountPeerId: PeerId?
    var services: [PeerId: GRVMMessageArchiveCoordinator] = [:]
}

private let state = Atomic(value: RuntimeState())
```

An event without a registered exact-account service fails closed and leaves Telegram's stock mutation path in control; it is never written into another account. Unregistering removes only that account's service. `primaryService()` reads `primaryAccountPeerId` and never falls back to an arbitrary service.

Replace `AyuGramFeatureManager.currentSettings` reads with `registry.primaryService()?.settingsSnapshot()` only for compatibility hooks whose consumer has no account context. Any hook whose consumer has an `Account`, `AccountContext`, or account peer ID changes signature to accept that ID and resolves `registry.service(accountPeerId:)`; the later parity plans list and convert those consumers. Never read mutable settings or compiled filters outside an `Atomic` snapshot.

- [ ] **Step 4: Subscribe to active account contexts**

After `SharedAccountContextImpl` exists, subscribe to its active-account-context signal, first call `migrateGRVMSettings(accountIds:accountManager:)` for that exact authorized-account list, then call `setPrimaryAccount(primary?.account.peerId)`, register new accounts with record ID/Postbox/MediaBox, and unregister removed accounts. For each registered account, retain a `grvmSettings(accountId:accountManager:)` subscription that calls that coordinator's `updateSettings`; dispose it on unregister. Retain the active-context subscription in AppDelegate or AyuGramFeatureManager.

- [ ] **Step 5: Reconcile startup state**

Before creating any coordinator, call `store.migrate(activeAccountRecordIds:)` once with the complete authorized account-record list from the same `activeAccountContexts` emission. Never migrate once per account, because that could misclassify a multi-account legacy database as single-account.

Then, for each account:

1. load deleted/revised keys into the in-memory index;
2. scan locally deleted Postbox attributes in bounded transactions;
3. attach a history marker to locally present messages whose migrated revision key exists but whose marker is absent;
4. insert missing archive metadata rows;
5. restore each complete archived blob whose MediaBox resource is missing;
6. mark a row `.missing` only when its persistent archive file is absent.

At startup, remove stale `*.tmp` files left by interrupted copies. Then compare final blob paths with the account's `archived_media_blobs` rows and retry deletion of unreferenced files left by a previous failed cleanup; never delete a path still referenced by the database.

Retain a subscription to `mediaBox.didRemoveResourceIds`. Intersect each emitted batch with the coordinator's account-scoped archived-resource index and immediately call `restoreResourceData` for verified complete backups. This keeps deleted media playable after normal Telegram cache cleanup without a synchronous layout query.

- [ ] **Step 6: Run contracts and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_account_registry_contract -v
python -m unittest discover -s Tests/GRVMgramContracts -p "test_*.py" -v
git diff --check
git add submodules/AyuGramFeatures/Sources submodules/AyuGramLib/Sources submodules/TelegramUI/Sources/AppDelegate.swift Tests/GRVMgramContracts/test_account_registry_contract.py
git commit -m "feat: bind GRVMgram archives to accounts"
```

Expected: all archive contracts PASS; no process-global account fallback remains.
