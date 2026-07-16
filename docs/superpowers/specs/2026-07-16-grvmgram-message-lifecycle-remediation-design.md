# GRVMgram Message Lifecycle Remediation Design

**Date:** 2026-07-16

**Status:** Approved working design for the resumed full-parity goal

## Purpose

Close the cross-task defects found by the whole-subsystem review before any Ghost/General work continues:

1. `Clear Deleted` must never report success while archived files, Postbox rows, database rows, or index entries remain.
2. Replayed outgoing edit updates must not add the current content as a historical revision.
3. One-time-media preservation must read the settings of the account performing TTL processing.
4. Archived media left in `.copying` by a crash must reach a terminal state on the next registration.
5. Clear Call History must use the same preservation path as every other user-visible deletion.

The existing minor gap for semi-transparent standalone media is owned by Chat/Appearance Task 6 and is not part of this remediation.

## Cleanup Alternatives

### A. Durable strict cleanup journal (selected)

Persist a cleanup job before any destructive operation. Remove the exact unshared archive files, then idempotently remove Postbox rows, then finalize SQL rows, blob metadata, the in-memory index, and the job. Resume unfinished jobs at account registration. Return a typed error and keep the archive screen unchanged on any incomplete phase.

This is the only approach that matches the user-facing word “Permanently” and prevents a successful result while private files remain.

### B. Optimistic UI with background retry (rejected)

Hide the archive immediately, retain a background deletion tombstone, and retry until files disappear. This makes the UI feel faster but temporarily conceals retained private data and cannot honestly report completion.

### C. Best-effort reconciliation (rejected)

Keep the current order and rely on startup orphan cleanup. It is the smallest diff, but `try? removeItem` can leave an untracked blob indefinitely and the current `NoError` signal cannot distinguish failure from an empty archive.

## Durable Cleanup Model

### Schema

Upgrade the archive database from schema v2 to v3 and add one table:

```sql
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
```

`0` represents a missing peer or thread scope; Telegram peer IDs are nonzero, and thread `0` is equivalent to the non-topic scope. `message_keys` and `media_records` are JSON-encoded Codable arrays. The single-row payload keeps this journal small and avoids three new relational tables.

Add these public models to AyuGramLib:

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
```

`GRVMArchivedMedia.CopyState` and `GRVMArchivedMedia` become Codable without changing stored values.

### Store boundary

`GRVMMessageArchiveStore` owns all journal mutations:

```swift
public func beginDeletedCleanup(
    accountId: Int64,
    peerId: Int64?,
    threadId: Int64?
) throws -> GRVMCleanupJob?

public func pendingCleanupJobs(accountId: Int64) throws -> [GRVMCleanupJob]
public func markCleanupFilesRemoved(id: UUID) throws -> GRVMCleanupJob
public func finalizeDeletedCleanup(id: UUID) throws -> [GRVMMessageKey]
```

`beginDeletedCleanup` runs in one SQLite transaction. It reuses an existing job for the same account/scope, selects exact archived-message keys, collects only revision-0 mappings for those keys, and includes a blob only when every current mapping for that account/resource belongs to the target keys. Edit revisions and messages outside the requested scope therefore keep shared blobs.

Candidate media is deduplicated by `(accountId, resourceId)`. Both synchronous preservation entry points execute their metadata save and archive-copy enqueue on the same coordinator queue used by job planning and the filesystem phase. A new mapping therefore cannot appear between candidate selection and unlink. A mapping created after the filesystem phase queues its archive copy after unlink; finalization rechecks references and retains its blob metadata.

No archived message, mapping, or blob metadata is deleted during `beginDeletedCleanup`.

`finalizeDeletedCleanup` removes the target mappings and archived-message rows, rechecks every candidate’s remaining reference count, deletes blob metadata only at zero references, deletes the job, and returns its keys in one transaction. A new reference that appears after planning wins: its metadata remains.

### Filesystem boundary

Replace the callback-only `GRVMArchivedMediaStore.remove` API with an explicit result:

```swift
public struct GRVMMediaRemovalResult: Equatable {
    public let removed: [GRVMArchivedMedia]
    public let failed: [GRVMArchivedMedia]
}

public func removeArchivedFiles(_ records: [GRVMArchivedMedia]) -> GRVMMediaRemovalResult
```

The media-store queue serializes removal with archive copies. It removes both the final path and its `.tmp` sibling. A missing file is success; an empty legacy path has no private archive copy and is success; a nonempty invalid path or any other filesystem error is failure. No critical removal uses `try?`.

### Coordinator state machine

Change the coordinator and UI bridge to:

```swift
public func clearDeleted(
    peerId: PeerId?,
    threadId: Int64?
) -> Signal<[MessageId], GRVMClearDeletedError>
```

The coordinator executes one job as follows:

1. On its serial queue, create or load the durable job.
2. If phase is `.planned`, synchronously remove all candidate archive files.
3. If any removal fails, emit `.mediaRemovalFailed(count)`. Do not mutate Postbox, archived messages, mappings, the index, or the job phase. A retry treats already removed files as success.
4. Persist `.filesRemoved`.
5. Run the existing idempotent Postbox `.forceCleanup` transaction for the job’s exact message IDs.
6. On the coordinator queue, call `finalizeDeletedCleanup`.
7. Only after SQLite commit succeeds, remove the exact keys from the immutable index and emit the message IDs.
8. If SQLite finalize fails, emit `.databaseFinalizationFailed`; the job and archive rows remain, and retrying repeats the already-safe Postbox deletion.

The archive controller refreshes only from `next`. Both archive-screen and context-menu Clear actions show a normal error alert from the typed error. A missing account service fails with `.archiveUnavailable`; an empty scope emits `[]` successfully.

At registration, publish the account coordinator, then call `resumePendingCleanupJobs()`. Jobs are processed oldest first with the same state machine. Only after pending jobs finish or remain retryable does normal media reconciliation restore the remaining records. Re-running any phase is safe after a crash:

- crash during file deletion: `.planned` retries and missing files count as removed;
- crash after files but before phase update: the same retry succeeds;
- crash after `.filesRemoved`: Postbox removal repeats idempotently;
- crash after Postbox commit: SQL finalize repeats;
- crash after SQL commit: the job is absent and no work repeats.

## Archived `.copying` Recovery

Extract the synchronous copy logic used by `archive` so reconciliation can reuse it. During account preparation:

1. A `.copying` record with an existing final blob is promoted to `.complete` using the actual positive file size. The final file is trustworthy because the archive writer publishes it only with an atomic temporary-file replacement.
2. If no final blob exists but MediaBox still has the completed resource, retry the same atomic copy using `record.resourceId` and `record.kind`.
3. If neither source exists, remove any `.tmp` file and mark the record `.unavailable`.
4. Persist every terminal update before restoring complete blobs to MediaBox.

Reconciliation continues to mark vanished `.complete` blobs as `.missing`. Cleanup-job blob rows remain referenced in the database until job finalization, so ordinary orphan reconciliation cannot delete their retry state.

## Edit Replay Guard

The outgoing response helper already receives both the current `Message` and incoming `StoreMessage`. It must call the existing `grvmMessageEditContentMatches` before `preserveEditRevision`:

```swift
if let previous = transaction.getMessage(id),
   !grvmMessageEditContentMatches(previous: previous, incoming: message) {
    shouldMarkHistory = AyuGramHooks.preserveEditRevision?(accountPeerId, previous) == true
}
```

The incoming state-manager route already follows this rule. The shared matcher remains the single definition of text, entity, and media equality.

## Account-Scoped One-Time Media

Change the hook and its sole consumer to:

```swift
public static var shouldPreserveOneTimeMedia: ((PeerId) -> Bool)?
```

`ManagedAutoremoveMessageOperations` passes its `accountPeerId`. `AyuGramFeatureManager` reads only `registry.service(accountPeerId:)?.settingsSnapshot().saveDeletedMessages`; a missing service returns false and preserves stock Telegram behavior.

## Clear Call History Route

Expose one neutral Postbox transaction helper:

```swift
public func messageIdsWithGlobalTag(_ tag: GlobalMessageTags) -> [MessageId]
```

It maps `.message` entries from `MessageHistoryTable.allIndicesWithGlobalTag` and ignores holes. After Telegram confirms call-history deletion, `_internal_clearCallHistory` collects `GlobalMessageTags.Calls` IDs and sends them through `_internal_applyMessageDeletion` with the exact account peer, account MediaBox, and `.server(.localAction)`. The common helper preserves eligible call service messages when Save Deleted is enabled and physically removes them otherwise. The direct `removeAllMessagesWithGlobalTag` call is removed from this user-visible route.

## Error Handling and Observability

- Filesystem, SQLite-journal, and SQLite-finalize failures are distinct typed outcomes.
- Failure never emits successful message IDs.
- UI never refreshes from completion alone.
- No filenames, message text, peer IDs, or database errors are logged.
- Startup resume is silent on success; a failed durable job remains for the next retry and is not discarded.
- Internal errors may be counted later, but telemetry is outside this remediation.

## Test Strategy

All production changes follow RED–GREEN–REFACTOR.

### Executable schema/model contracts

- migrate a fresh database to v3;
- migrate a populated v2 database without changing archive data;
- encode/decode cleanup jobs and archived media;
- reuse the same account/scope job;
- select only unshared candidate blobs;
- finalize keys, mappings, zero-reference blobs, and job atomically;
- retain blob metadata when another edit revision references it.

### Cleanup state-machine contracts

- permission failure produces no success emission, leaves `.planned`, and performs no Postbox deletion;
- retry after partial removal succeeds because missing files are success;
- DB finalize failure leaves `.filesRemoved` and archive rows for retry;
- restart resumes `.planned` and `.filesRemoved` jobs;
- success emission occurs after SQL finalize and index removal;
- empty scope succeeds with `[]`;
- invalid nonempty paths fail closed.

### Regression contracts

- outgoing helper uses `grvmMessageEditContentMatches` before preservation;
- one-time-media hook accepts and consumes the exact account `PeerId`;
- `.copying` final blob becomes `.complete`, missing source becomes `.unavailable`, and temporary files are removed;
- Clear Call History collects exact global-tag IDs and uses `_internal_applyMessageDeletion`;
- the route inventory rejects a remaining direct call-history removal.

Run the complete `Tests/GRVMgramContracts` suite after each focused gate. The final macOS GitHub build remains deferred until every subsystem and localization plan is complete.

## Non-Goals

- No raw archived-media viewer or edit-history media schema expansion.
- No redesign of Telegram’s Postbox transaction engine.
- No telemetry service.
- No intermediate GitHub Actions run.
- No localization work; the final localization plan owns the temporary English error copy.
