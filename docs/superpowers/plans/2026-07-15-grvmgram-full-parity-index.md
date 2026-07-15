# GRVMgram Full iOS Parity Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the approved GRVMgram design as reviewable subsystems and finish with one monitored GitHub Actions build that yields a validated IPA.

**Architecture:** Seven subsystem plans form a dependency graph: crash foundation → account storage/media → message lifecycle/history → core parity → chat/appearance parity → standalone features → localization/branding/final CI. Each subsystem ends with local tests, contract checks, a focused commit, and a reviewer gate.

**Tech Stack:** Swift, Telegram-iOS/Postbox/MediaBox, SQLCipher, UIKit/AsyncDisplayKit, Bazel/rules_apple, Python 3.12, GitHub Actions, gh CLI.

## Global Constraints

- Work only on `codex/grvmgram-full-parity` until all local verification gates pass.
- Preserve internal AyuGram type/module/hook/Codable names unless a plan explicitly changes an interface.
- Public UI and metadata use GRVMgram only.
- Persist deleted messages and downloaded media until explicit cleanup.
- Store edit revisions for incoming and outgoing messages.
- Scope data, settings, and Local Premium by account.
- Do not run intermediate GitHub Actions builds.
- Do not push `master` until every local plan gate passes.
- Diagnose and fix final CI failures until a validated `GRVMgram.ipa` exists.

---

## Plan Set and Dependency Graph

```text
01 crash foundation
        |
02 account storage + media
        |
03 message lifecycle + history + Local Premium
        |
04 Ghost + filters + general settings
        |
05 chat + appearance parity
        |
06 standalone iOS features
        |
07 localization + branding + final CI
```

| Order | Plan | Required output |
|---:|---|---|
| 1 | `2026-07-15-grvmgram-crash-foundation.md` | Proven read-state recursion fix and local contract |
| 2 | `2026-07-15-grvmgram-account-storage-media.md` | Account-scoped SQL store, settings, indexes, media backup |
| 3 | `2026-07-15-grvmgram-message-lifecycle-history.md` | Persistent inline deletes, all edit paths, archive/history UI, Local Premium |
| 4 | `2026-07-15-grvmgram-ghost-filters-general.md` | Complete Ghost, filters, translation/link/Webview/general parity |
| 5 | `2026-07-15-grvmgram-chat-appearance-parity.md` | Correct context menus, marks, rendering, channel controls, Message Shot |
| 6 | `2026-07-15-grvmgram-standalone-features.md` | Remaining applicable Desktop features and removal of unimplemented toggles |
| 7 | `2026-07-15-grvmgram-localization-branding-ci.md` | RU/EN resources, GRVMgram branding, hard-fail artifact validation, green IPA |

## Cross-Plan Interfaces

The following names are canonical across plans:

```swift
public struct GRVMMessageKey: Hashable, Codable {
    public let accountId: Int64
    public let peerId: Int64
    public let namespace: Int32
    public let messageId: Int32
    public let threadId: Int64
}

public enum GRVMDeletionSource: Int32 {
    case server = 0
    case localAction = 1
    case ttl = 2
    case secretRecall = 3
    case validation = 4
    case minimumAvailable = 5
}

public final class GRVMDeletedMessageAttribute: MessageAttribute, LocalMessageDeletionMarker, Equatable {
    public let deletedAt: Int32
    public let source: GRVMDeletionSource
    public let topicId: Int64?
    public let resourceIds: [String]
}

public final class GRVMEditHistoryMessageAttribute: MessageAttribute, Equatable {
    public let latestRevisionAt: Int32
}

public final class GRVMMessageArchiveCoordinator {
    public let accountPeerId: PeerId
    public let accountRecordId: AccountRecordId
    public func settingsSnapshot() -> AyuGramSettings
    public func updateSettings(_ settings: AyuGramSettings)
    public func messageKey(_ message: Message) -> GRVMMessageKey
    public func preserveDeletedMessages(_ messages: [Message], source: GRVMDeletionSource) -> [MessageId: [String]]
    public func preserveEditRevision(_ message: Message) -> Bool
    public func clearDeleted(peerId: PeerId?, threadId: Int64?) -> Signal<[MessageId], NoError>
    public func hasEditHistory(_ id: MessageId) -> Bool
    public func deletedMessages(peerId: PeerId?, threadId: Int64?, query: String?) -> Signal<[GRVMArchivedMessage], NoError>
    public func editHistory(_ id: MessageId) -> Signal<[GRVMEditRevision], NoError>
}

public final class GRVMAccountFeatureRegistry {
    public init(databaseURL: URL, mediaRootURL: URL, accountManager: AccountManager<TelegramAccountManagerTypes>)
    public func prepare(activeAccountRecordIds: [Int64]) throws
    public func register(accountPeerId: PeerId, accountRecordId: AccountRecordId, postbox: Postbox, mediaBox: MediaBox)
    public func unregister(accountPeerId: PeerId)
    public func setPrimaryAccount(_ accountPeerId: PeerId?)
    public func service(accountPeerId: PeerId) -> GRVMMessageArchiveCoordinator?
    public func primaryService() -> GRVMMessageArchiveCoordinator?
    public func ownPeerIds() -> Set<PeerId>
}
```

`GRVMMessageKey.accountId` is always `AccountRecordId.int64`; settings and runtime service lookup use the account's own `PeerId`. TelegramCore persistence hooks return success synchronously, so a failed metadata write falls back to the stock delete/edit path instead of claiming that data was saved.

If implementation discovers an existing Telegram type that makes one signature impossible, update this index and every dependent plan in the same documentation commit before changing production code.

## Per-Task Review Gate

After every implementation task:

1. run the task's focused tests;
2. run `git diff --check`;
3. inspect `git status --short`;
4. request specification and code-quality review;
5. resolve Critical and Important findings before starting the next task;
6. create the exact focused commit named in the task.

## Full Local Gate Before Final CI

Run from the repository root:

```powershell
python -m unittest discover -s Tests -p "test_*.py" -v
python tools/grvmgram/validate_read_state.py submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift
python build-system/Make/ValidateGRVMgram.py source
python -m py_compile build-system/Make/ValidateGRVMgram.py
git diff --check
git status --short
```

Expected:

- every Python test passes;
- both validators exit 0;
- no whitespace errors;
- only intentionally uncommitted plan ledger files, if any, appear in status.

## Branch and Final Build Gate

- [ ] **Step 1: Confirm all seven plan files have every task checked and committed**

Run:

```powershell
rg -n "^- \[ \]" docs/superpowers/plans/2026-07-15-grvmgram-*.md
```

Expected: no unchecked implementation task outside this index.

- [ ] **Step 2: Push the implementation branch as backup**

```powershell
git push -u origin codex/grvmgram-full-parity
```

Expected: branch push succeeds without starting the master-only push workflow.

- [ ] **Step 3: Fast-forward master locally**

```powershell
git switch master
git merge --ff-only codex/grvmgram-full-parity
```

Expected: fast-forward succeeds; no merge commit.

- [ ] **Step 4: Re-run the full local gate on master**

Run the commands in **Full Local Gate Before Final CI**.

Expected: all checks pass on the exact commit that will be pushed.

- [ ] **Step 5: Push master once**

```powershell
git push origin master
```

Expected: one push-triggered CI run for the new HEAD.

- [ ] **Step 6: Execute the monitor/fix/download loop**

Follow the exact commands and failure policy in `2026-07-15-grvmgram-localization-branding-ci.md`.

Expected: GitHub Actions conclusion `success`, downloaded `GRVMgram.ipa`, successful source/IPA validation, and recorded SHA-256.
