# GRVMgram Message Lifecycle Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Clear Deleted durably strict and close every cross-task lifecycle defect found by the whole-subsystem review.

**Architecture:** Add a schema-v3 cleanup journal before crossing SQLite, filesystem, and Postbox boundaries. Run cleanup as an idempotent staged job, resume unfinished jobs during account registration, and expose typed failure to UI. Keep replay, account-scope, `.copying` recovery, and Call History fixes at their existing authoritative points.

**Tech Stack:** Swift, Postbox, MediaBox, SwiftSignalKit, SQLCipher/SQLite, Foundation FileManager, Bazel, Python 3.12 source-contract tests.

## Global Constraints

- Work only on `codex/grvmgram-full-parity`; do not push or run GitHub Actions.
- `Clear Deleted` emits success only after archive files, Postbox rows, SQLite rows/mappings/blob metadata, the immutable index, and the cleanup job are finalized.
- A failed or interrupted cleanup remains durable and retryable; no failure is represented as a successful empty result.
- Never unlink a blob that has a mapping outside the exact cleanup job.
- Missing archive files are successful idempotent removals; invalid nonempty paths and other filesystem errors fail closed.
- Resolve one-time-media settings through the exact account service; never `primaryService()`.
- Keep internal AyuGram type/module/hook names. Public copy uses GRVMgram and is localized by the final localization plan.
- Preserve the read-state recursion fix and every completed Message Lifecycle invariant.
- Windows source contracts are the per-task gate. The only macOS Swift/Bazel build remains the final CI run.

---

## File Map

### Create

- `Tests/GRVMgramContracts/test_cleanup_journal_contract.py` - schema, journal, staged ordering, resume, and error contracts.

### Modify

- `submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift`
- `submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift`
- `submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift`
- `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- `submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift`
- `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- `submodules/AyuGramFeatures/Sources/AyuGramFeatures.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift`
- `submodules/AyuGramSettingsUI/Sources/GRVMArchiveContextMenuItems.swift`
- `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- `submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift`
- `submodules/TelegramCore/Sources/State/ManagedAutoremoveMessageOperations.swift`
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteMessages.swift`
- `submodules/Postbox/Sources/Postbox.swift`
- `Tests/GRVMgramContracts/test_archive_schema.py`
- `Tests/GRVMgramContracts/test_media_archive_contract.py`
- `Tests/GRVMgramContracts/test_history_ui_contract.py`
- `Tests/GRVMgramContracts/test_edit_routes_contract.py`
- `Tests/GRVMgramContracts/test_delete_routes_contract.py`

---

### Task 1: Add schema-v3 cleanup jobs and atomic journal APIs

**Files:**
- Modify: `submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift`
- Modify: `submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift`
- Create: `Tests/GRVMgramContracts/test_cleanup_journal_contract.py`
- Modify: `Tests/GRVMgramContracts/test_archive_schema.py`

**Interfaces:**
- Produces:

```swift
public enum GRVMCleanupPhase: Int32, Codable {
    case planned = 0
    case filesRemoved = 1
}

public struct GRVMCleanupJob: Codable, Equatable {
    public let id: UUID
    public let accountId: Int64
    public let peerId: Int64?
    public let threadId: Int64?
    public let phase: GRVMCleanupPhase
    public let createdAt: Int32
    public let messageKeys: [GRVMMessageKey]
    public let mediaRecords: [GRVMArchivedMedia]
}

public enum GRVMClearDeletedError: Error, Equatable {
    case archiveUnavailable
    case mediaRemovalFailed(Int)
    case databaseFinalizationFailed
}

public func beginDeletedCleanup(accountId: Int64, peerId: Int64?, threadId: Int64?) throws -> GRVMCleanupJob?
public func pendingCleanupJobs(accountId: Int64) throws -> [GRVMCleanupJob]
public func markCleanupFilesRemoved(id: UUID) throws -> GRVMCleanupJob
public func finalizeDeletedCleanup(id: UUID) throws -> [GRVMMessageKey]
```

- [ ] **Step 1: Write the failing journal contract**

Create `Tests/GRVMgramContracts/test_cleanup_journal_contract.py`:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift"
STORE = ROOT / "submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift"


class CleanupJournalContractTests(unittest.TestCase):
    def test_schema_v3_is_migration_safe(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS cleanup_jobs", source)
        self.assertIn("message_keys BLOB NOT NULL", source)
        self.assertIn("media_records BLOB NOT NULL", source)
        self.assertIn("PRAGMA user_version = 3", source)
        self.assertIn("case 2:", source)
        self.assertIn("case 3:", source)

    def test_cleanup_models_are_codable(self) -> None:
        source = MODELS.read_text(encoding="utf-8")
        self.assertIn("enum GRVMCleanupPhase: Int32, Codable", source)
        self.assertIn("struct GRVMCleanupJob: Codable, Equatable", source)
        self.assertIn("enum GRVMClearDeletedError: Error, Equatable", source)
        self.assertIn("struct GRVMArchivedMedia: Codable, Equatable", source)

    def test_store_has_staged_atomic_boundaries(self) -> None:
        source = STORE.read_text(encoding="utf-8")
        for name in ("beginDeletedCleanup(", "pendingCleanupJobs(", "markCleanupFilesRemoved(", "finalizeDeletedCleanup("):
            self.assertIn(name, source)
        begin = source[source.index("public func beginDeletedCleanup(") :]
        self.assertIn("revisionId: 0", begin[:12000])
        self.assertIn("references == Int64(targetedReferences)", begin[:12000])
        finalize = source[source.index("public func finalizeDeletedCleanup(") :]
        self.assertIn("DELETE FROM archived_messages", finalize[:16000])
        self.assertIn("DELETE FROM cleanup_jobs", finalize[:16000])
        self.assertIn("SELECT COUNT(*) FROM archived_message_media", finalize[:16000])
```

Extend `test_archive_schema.py` so fresh and populated-v2 migrations expect schema 3 while retaining every v2 table/data assertion.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_cleanup_journal_contract -v
python -m unittest Tests.GRVMgramContracts.test_archive_schema -v
```

Expected: the new suite fails because models/table/APIs are absent.

- [ ] **Step 3: Add exact models and schema-v3 migration**

Make `GRVMArchivedMedia.CopyState` and `GRVMArchivedMedia` Codable. Add the public models and memberwise initializers above. Keep the base tables and add:

```swift
static let cleanupSchemaV3 = """
CREATE TABLE IF NOT EXISTS cleanup_jobs (
    job_id TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL,
    scope_peer_id INTEGER NOT NULL DEFAULT 0,
    scope_thread_id INTEGER NOT NULL DEFAULT 0,
    phase INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    message_keys BLOB NOT NULL,
    media_records BLOB NOT NULL,
    UNIQUE(account_id, scope_peer_id, scope_thread_id)
);
CREATE INDEX IF NOT EXISTS cleanup_jobs_account
ON cleanup_jobs(account_id, created_at);
"""
```

Migration cases are exact:

```swift
case 0:
    // Preserve current legacy rename/copy statements.
    try self.execute(database, sql: Self.schemaV2)
    try self.execute(database, sql: Self.cleanupSchemaV3)
    // Preserve current legacy row migration.
    try self.execute(database, sql: "PRAGMA user_version = 3")
case 2:
    try self.execute(database, sql: Self.schemaV2)
    try self.execute(database, sql: Self.cleanupSchemaV3)
    try self.execute(database, sql: "PRAGMA user_version = 3")
case 3:
    try self.execute(database, sql: Self.schemaV2)
    try self.execute(database, sql: Self.cleanupSchemaV3)
default:
    throw GRVMArchiveError.unsupportedSchema(version)
```

- [ ] **Step 4: Implement journal creation**

Use one store-owned `JSONEncoder` and `JSONDecoder`. Encode stable sorted key/media arrays. Store `peerId ?? 0` and `threadId ?? 0`; decode zero to nil.

Within one SQLite transaction, `beginDeletedCleanup`:

1. returns an existing same-scope job;
2. loads exact account/peer/thread keys;
3. returns nil for no keys;
4. counts target revision-0 mappings per account/resource;
5. includes a deduplicated media record only when all mappings are targeted;
6. inserts and returns a `.planned` job.

Use this exact shared-reference gate:

```swift
let references = try self.scalarInt64(
    database,
    sql: "SELECT COUNT(*) FROM archived_message_media WHERE account_id = ? AND resource_id = ?",
    values: [.int64(accountId), .text(resourceId)]
)
guard references == Int64(targetedReferences) else {
    continue
}
```

- [ ] **Step 5: Implement phase update and finalization**

`markCleanupFilesRemoved` changes only `.planned` to `.filesRemoved`; repeated calls return the current `.filesRemoved` job.

`finalizeDeletedCleanup` loads one job and in the same transaction deletes its revision-0 mappings and archived-message rows, then rechecks each candidate:

```swift
let references = try self.scalarInt64(
    database,
    sql: "SELECT COUNT(*) FROM archived_message_media WHERE account_id = ? AND resource_id = ?",
    values: [.int64(record.accountId), .text(record.resourceId)]
)
if references == 0 {
    try self.executePrepared(
        database,
        sql: "DELETE FROM archived_media_blobs WHERE account_id = ? AND resource_id = ?",
        values: [.int64(record.accountId), .text(record.resourceId)]
    )
}
```

Delete the job last and return its keys. Do not alter edit revisions.

- [ ] **Step 6: Verify GREEN and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_cleanup_journal_contract -v
python -m unittest Tests.GRVMgramContracts.test_archive_schema -v
python -m unittest discover -s Tests\GRVMgramContracts -p "test_*.py" -v
git diff --check
git add submodules/AyuGramLib/Sources/GRVMMessageArchiveModels.swift submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift Tests/GRVMgramContracts/test_cleanup_journal_contract.py Tests/GRVMgramContracts/test_archive_schema.py
git commit -m "feat: journal deleted archive cleanup"
```

---

### Task 2: Return filesystem outcomes and recover interrupted media copies

**Files:**
- Modify: `submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift`
- Modify: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Modify: `Tests/GRVMgramContracts/test_media_archive_contract.py`
- Modify: `Tests/GRVMgramContracts/test_cleanup_journal_contract.py`

**Interfaces:**
- Produces:

```swift
public struct GRVMMediaRemovalResult: Equatable {
    public let removed: [GRVMArchivedMedia]
    public let failed: [GRVMArchivedMedia]
}

public func removeArchivedFiles(_ records: [GRVMArchivedMedia]) -> GRVMMediaRemovalResult
```

- [ ] **Step 1: Add failing media contracts**

Require:

```python
self.assertIn("struct GRVMMediaRemovalResult: Equatable", source)
self.assertIn("func removeArchivedFiles(", source)
self.assertIn("NSFileNoSuchFileError", source)
self.assertNotIn("try? self.fileManager.removeItem", remove_section)
self.assertIn('appendingPathExtension("tmp")', remove_section)
self.assertIn("case .copying", reconcile_section)
self.assertIn("mediaBox.completedResourcePath", reconcile_section)
self.assertIn("copyState: .complete", reconcile_section)
self.assertIn("copyState: .unavailable", reconcile_section)
```

Run `python -m unittest Tests.GRVMgramContracts.test_media_archive_contract -v`; expect failure.

- [ ] **Step 2: Implement explicit idempotent removal**

Deduplicate records by account/resource on the media queue. Remove final and `.tmp`. Use:

```swift
do {
    try self.fileManager.removeItem(at: url)
    return true
} catch {
    let nsError = error as NSError
    return nsError.domain == NSCocoaErrorDomain && nsError.code == NSFileNoSuchFileError
}
```

Empty legacy path is success. Invalid nonempty path is failure. A record is removed only when both paths are absent. Put the do/catch rule in one private `removeIfPresent` helper and reuse it for final files, `.tmp` files, and reconciliation orphan cleanup; no `FileManager.removeItem` call remains under `try?`. Keep the old callback wrapper until Task 3, but implement it through the explicit result.

- [ ] **Step 3: Share synchronous archive-copy logic**

Extract the current copy body into:

```swift
private func archiveRecord(
    _ record: GRVMArchivedMedia,
    resource: GRVMMediaResourceReference,
    mediaBox: MediaBox
) -> GRVMArchivedMedia
```

The public signal schedules the helper and emits its terminal record; atomic `.tmp` replacement remains unchanged.

- [ ] **Step 4: Recover `.copying` during reconciliation**

Change reconciliation to:

```swift
public func reconcile(
    accountId: Int64,
    records: [GRVMArchivedMedia],
    mediaBox: MediaBox
) -> Signal<[GRVMArchivedMedia], NoError>
```

For `.copying`, reconstruct `GRVMMediaResourceReference(id: MediaResourceId(record.resourceId), kind: record.kind)` and call `archiveRecord`. Existing final blob promotes to `.complete`; otherwise MediaBox is retried; absent source becomes `.unavailable` after `.tmp` removal. Vanished `.complete` still becomes `.missing`.

Persist every returned update before restoring remaining `.complete` records.

- [ ] **Step 5: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_media_archive_contract -v
python -m unittest Tests.GRVMgramContracts.test_cleanup_journal_contract -v
python -m unittest discover -s Tests\GRVMgramContracts -p "test_*.py" -v
git diff --check
git add submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift Tests/GRVMgramContracts/test_media_archive_contract.py Tests/GRVMgramContracts/test_cleanup_journal_contract.py
git commit -m "fix: recover archived media operations"
```

---

### Task 3: Execute strict jobs and surface typed UI failure

**Files:**
- Modify: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Modify: `submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatures.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/GRVMArchiveContextMenuItems.swift`
- Modify: `submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift`
- Modify: `submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift`
- Modify: `Tests/GRVMgramContracts/test_cleanup_journal_contract.py`
- Modify: `Tests/GRVMgramContracts/test_history_ui_contract.py`

**Interfaces:**

```swift
public func clearDeleted(peerId: PeerId?, threadId: Int64?) -> Signal<[MessageId], GRVMClearDeletedError>
public func resumePendingCleanupJobs()
```

- [ ] **Step 1: Write strict ordering/UI contracts and verify RED**

The cleanup test must prove the public begin-before-run handoff and the runner's destructive order:

```python
clear = coordinator[coordinator.index("public func clearDeleted(") :]
self.assertLess(clear.index("beginDeletedCleanup("), clear.index("runCleanupJob("))
runner = coordinator[coordinator.index("private func runCleanupJob(") :]
anchors = [
    "removeArchivedFiles(",
    "markCleanupFilesRemoved(",
    "self.postbox.transaction",
    "finalizeDeletedCleanup(",
    "self.index.removeDeleted",
    "subscriber.putNext(ids)",
]
positions = [runner.index(anchor) for anchor in anchors]
self.assertEqual(positions, sorted(positions))
self.assertIn("Signal<[MessageId], GRVMClearDeletedError>", coordinator)
self.assertIn("pendingCleanupJobs(accountId:", coordinator)
self.assertIn("resumePendingCleanupJobs()", registry)
self.assertNotIn("self.store.removeDeleted(keys)", coordinator)
```

UI tests require `start(next:error:)`, refresh only in `next`, and a visible error controller. Run cleanup/history suites and observe failure.

- [ ] **Step 2: Serialize preservation and file planning**

Move current preservation bodies into private on-queue helpers. Public methods synchronously capture results:

```swift
var result: [MessageId: [String]] = [:]
self.queue.sync {
    result = self.preserveDeletedMessagesOnQueue(messages, source: source)
}
return result
```

Use the same pattern for Bool revision results. This prevents a mapping from appearing between candidate selection and unlink.

- [ ] **Step 3: Implement one idempotent job runner**

The private runner performs:

```swift
if job.phase == .planned {
    let removal = self.mediaStore.removeArchivedFiles(job.mediaRecords)
    guard removal.failed.isEmpty else {
        failure(.mediaRemovalFailed(removal.failed.count))
        return
    }
    job = try self.store.markCleanupFilesRemoved(id: job.id)
}

let ids = job.messageKeys.map {
    MessageId(peerId: PeerId($0.peerId), namespace: $0.namespace, id: $0.messageId)
}
disposable.set(self.postbox.transaction { transaction -> [MessageId] in
    _internal_applyMessageDeletion(
        accountPeerId: self.accountPeerId,
        transaction: transaction,
        mediaBox: self.mediaBox,
        ids: ids,
        mode: .forceCleanup
    )
    return ids
}.start(next: { ids in
    self.queue.async {
        do {
            let keys = try self.store.finalizeDeletedCleanup(id: job.id)
            self.index.removeDeleted(Set(keys))
            success(ids)
        } catch {
            failure(.databaseFinalizationFailed)
        }
    }
}))
```

No failure calls `putNext`.

- [ ] **Step 4: Resume before ordinary reconciliation**

After registry publication, call `resumePendingCleanupJobs()`. Run oldest jobs sequentially. Start normal `.copying`/missing reconciliation only after jobs finish or the first job remains retryable. Never delete a failed job. Postbox force cleanup is intentionally repeatable.

- [ ] **Step 5: Change bridge/UI error handling**

Update the feature bridge and manager to `Signal<[MessageId], GRVMClearDeletedError>`; missing service is `.fail(.archiveUnavailable)`. Both UI actions use:

```swift
let _ = cleanup.start(next: { _ in
    refreshToken.set(refreshCounter.modify { $0 + 1 })
}, error: { error in
    controller?.present(
        grvmClearDeletedErrorController(error, presentationData: presentationData),
        in: .window(.root)
    )
})
```

The context-menu action uses the same error helper without refresh. Keep temporary English error text in that one helper.

- [ ] **Step 6: Remove obsolete best-effort APIs**

After consumer grep, delete `GRVMMessageArchiveStore.removeDeleted` and callback-only `GRVMArchivedMediaStore.remove`. Reject `try? self.fileManager.removeItem` and success before finalization in tests.

- [ ] **Step 7: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_cleanup_journal_contract -v
python -m unittest Tests.GRVMgramContracts.test_history_ui_contract -v
python -m unittest discover -s Tests\GRVMgramContracts -p "test_*.py" -v
rg -n "removeDeleted\(|mediaStore\.remove\(" submodules -g "*.swift"
git diff --check
git add submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/AyuGramFeatures/Sources/AyuGramFeatures.swift submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift submodules/AyuGramSettingsUI/Sources/GRVMArchiveContextMenuItems.swift submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift submodules/AyuGramLib/Sources/GRVMArchivedMediaStore.swift Tests/GRVMgramContracts/test_cleanup_journal_contract.py Tests/GRVMgramContracts/test_history_ui_contract.py
git commit -m "fix: make deleted cleanup durable"
```

---

### Task 4: Close replay, account, and Call History routes

**Files:**
- Modify: `submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift`
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedAutoremoveMessageOperations.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/Postbox/Sources/Postbox.swift`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteMessages.swift`
- Modify: `Tests/GRVMgramContracts/test_edit_routes_contract.py`
- Modify: `Tests/GRVMgramContracts/test_delete_routes_contract.py`

**Interfaces:**

```swift
public static var shouldPreserveOneTimeMedia: ((PeerId) -> Bool)?
public func messageIdsWithGlobalTag(_ tag: GlobalMessageTags) -> [MessageId]
```

- [ ] **Step 1: Add exact failing route contracts**

```python
helper = window(request_edit, "private func grvmApplyEditedMessage(", 5000)
self.assertIn("!grvmMessageEditContentMatches(previous: previous, incoming: message)", helper)
self.assertLess(helper.index("grvmMessageEditContentMatches"), helper.index("preserveEditRevision"))

self.assertIn("shouldPreserveOneTimeMedia: ((PeerId) -> Bool)?", hooks)
self.assertIn("shouldPreserveOneTimeMedia?(accountPeerId)", autoremove)
self.assertIn("registry.service(accountPeerId: accountPeerId)", manager)
self.assertIn("messageIdsWithGlobalTag(GlobalMessageTags.Calls)", delete_messages)
call_section = window(delete_messages, "func _internal_clearCallHistory(", 7000)
self.assertIn("_internal_applyMessageDeletion(", call_section)
self.assertNotIn("removeAllMessagesWithGlobalTag", call_section)
```

Run edit/delete route suites and observe both fail.

- [ ] **Step 2: Guard outgoing replay**

```swift
if let previous = transaction.getMessage(id),
   !grvmMessageEditContentMatches(previous: previous, incoming: message) {
    shouldMarkHistory = AyuGramHooks.preserveEditRevision?(accountPeerId, previous) == true
}
```

All outgoing response cases already share this helper.

- [ ] **Step 3: Scope one-time media by account**

Change the hook to `((PeerId) -> Bool)?`, pass `accountPeerId`, and wire:

```swift
AyuGramHooks.shouldPreserveOneTimeMedia = { [weak self] accountPeerId in
    return self?.registry.service(accountPeerId: accountPeerId)?.settingsSnapshot().saveDeletedMessages ?? false
}
```

- [ ] **Step 4: Expose exact global-tag IDs**

Map `MessageHistoryTable.allIndicesWithGlobalTag` `.message(index)` entries to IDs and ignore holes. Forward through PostboxImpl and Transaction:

```swift
public func messageIdsWithGlobalTag(_ tag: GlobalMessageTags) -> [MessageId] {
    assert(!self.disposed)
    return self.postbox?.messageIdsWithGlobalTag(tag: tag) ?? []
}
```

- [ ] **Step 5: Route Clear Call History through preservation**

Replace the successful direct removal:

```swift
let ids = transaction.messageIdsWithGlobalTag(GlobalMessageTags.Calls)
_internal_applyMessageDeletion(
    accountPeerId: account.peerId,
    transaction: transaction,
    mediaBox: account.mediaBox,
    ids: ids,
    mode: .server(.localAction)
)
```

- [ ] **Step 6: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_edit_routes_contract -v
python -m unittest Tests.GRVMgramContracts.test_delete_routes_contract -v
python -m unittest discover -s Tests\GRVMgramContracts -p "test_*.py" -v
rg -n "shouldPreserveOneTimeMedia\?\(\)" submodules -g "*.swift"
git diff --check
git add submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift submodules/TelegramCore/Sources/AyuGramHooks.swift submodules/TelegramCore/Sources/State/ManagedAutoremoveMessageOperations.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/Postbox/Sources/Postbox.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteMessages.swift Tests/GRVMgramContracts/test_edit_routes_contract.py Tests/GRVMgramContracts/test_delete_routes_contract.py
git commit -m "fix: close lifecycle integration gaps"
```

---

### Task 5: Re-run the lifecycle gate and whole-subsystem review

**Files:**
- Modify only files required by concrete reviewer findings.

- [ ] **Step 1: Run fresh local evidence**

```powershell
python -m unittest discover -s Tests\GRVMgramContracts -p "test_*.py" -v
python tools/grvmgram/validate_read_state.py submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift
rg -n "try\? self\.fileManager\.removeItem|shouldPreserveOneTimeMedia\?\(\)|removeAllMessagesWithGlobalTag\(tag: GlobalMessageTags\.Calls\)" submodules -g "*.swift"
git diff --check
git status --short
```

Expected: all tests and validator pass; forbidden grep is empty; worktree is clean.

- [ ] **Step 2: Request package-based whole-subsystem review**

Generate a review package from `2f3b8c61` to remediation HEAD. Review cleanup crash phases, shared media references, replay, account scope, Call History, and all existing lifecycle invariants. Resolve every Critical and Important finding before Ghost Task 1.

- [ ] **Step 3: Record the clean gate**

Append remediation commit range and final test count to `.superpowers/sdd/progress.md`. Do not create a bookkeeping-only commit.
