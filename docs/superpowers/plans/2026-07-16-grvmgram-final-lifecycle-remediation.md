# GRVMgram Final Lifecycle Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the final replacement deadlock and prevent every stale coordinator callback from mutating media metadata or restoring files.

**Architecture:** Make coordinator shutdown return detached cleanup waiters after closing admission and disposing all work under its serial queue. Registry lifecycle operations remove verified identities under their own queue, then asynchronously deliver typed errors only after leaving both queues. Every queued mutation callback checks the same coordinator admission bit immediately before touching the store, Postbox reconciliation, or restore path.

**Tech Stack:** Swift, SwiftSignalKit, Postbox, MediaBox, Python 3.12 source-contract tests.

## Global Constraints

- Work on `codex/grvmgram-full-parity` from `23d484e95596780fdd5c6f71c238611282bfc013`.
- Add both independent contracts and observe both targeted RED failures before editing production Swift.
- Do not amend, push, run Actions, or dispatch nested reviewers.
- Preserve durable journal phases, exact-once waiters, same-bound registration no-op, and new-generation resume ordering.
- Windows source contracts are the local gate; Swift/Xcode/Bazel compilation remains a macOS follow-up.

---

### Task 1: Prove both final lifecycle defects

**Files:**
- Modify: `Tests/GRVMgramContracts/test_account_registry_contract.py`
- Modify: `Tests/GRVMgramContracts/test_cleanup_journal_contract.py`

**Interfaces:**
- Consumes: current `shutdownForReplacement()`, registry lifecycle methods, and coordinator queued callbacks.
- Produces: two independent source contracts for two-phase delivery and stale-callback quiescence.

- [ ] **Step 1: Add the two-phase delivery contract**

Assert that shutdown returns detached waiters, contains no `subscriber.putError`, registry register/unregister invoke delivery after their `lifecycleQueue.sync` blocks, and the delivery helper dispatches asynchronously.

- [ ] **Step 2: Add the stale-callback contract**

Assert that shutdown disposes both `cleanupRunnerDisposable` and `disposables`, then require an `isAcceptingOperations` guard before mutation in the did-remove-resource callback, ordinary reconciliation callback, persistent-state queued block, and both archive-copy callbacks.

- [ ] **Step 3: Verify both RED failures separately**

Run:
`python -m unittest Tests.GRVMgramContracts.test_account_registry_contract.AccountRegistryContractTests.test_registry_delivers_shutdown_errors_after_lifecycle_sync -v`

Expected: `Ran 1 test`, `FAILED (failures=1)` because shutdown still calls subscribers inside its queue sync.

Run:
`python -m unittest Tests.GRVMgramContracts.test_cleanup_journal_contract.CleanupJournalContractTests.test_shutdown_disposes_all_work_and_guards_stale_mutation_callbacks -v`

Expected: `Ran 1 test`, `FAILED (failures=1)` because general subscriptions and mutation callbacks are not quiesced.

---

### Task 2: Move waiter delivery outside both lifecycle locks

**Files:**
- Modify: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Modify: `submodules/AyuGramFeatures/Sources/GRVMAccountFeatureRegistry.swift`
- Test: `Tests/GRVMgramContracts/test_account_registry_contract.py`

**Interfaces:**
- Consumes: `takeAllCleanupWaiters()` and registry identity verification.
- Produces: `shutdownForReplacement() -> [Subscriber<[MessageId], GRVMClearDeletedError>]` plus registry-owned asynchronous terminal delivery.

- [ ] **Step 1: Detach waiters under coordinator synchronization**

Set admission false, dispose cleanup and general work, clear the executor flag, take all waiters, and return them without invoking subscribers.

- [ ] **Step 2: Propagate detached waiters through registry removal**

Return `(removed: Bool, waiters: [...])` from `removeRegistration`, return the waiter array from `registerOnQueue`, and capture it in public register/unregister calls.

- [ ] **Step 3: Deliver after lifecycle synchronization**

After each public lifecycle `sync` returns, call a private helper that uses `Queue.concurrentDefaultQueue().async` and emits `.archiveUnavailable` once per detached subscriber.

- [ ] **Step 4: Verify targeted GREEN**

Run the Task 1 two-phase command. Expected: `Ran 1 test`, `OK`.

---

### Task 3: Quiesce all stale mutation callbacks

**Files:**
- Modify: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Test: `Tests/GRVMgramContracts/test_cleanup_journal_contract.py`

**Interfaces:**
- Consumes: queue-confined `isAcceptingOperations` and permanent `DisposableSet.dispose()`.
- Produces: no stale-generation store update, persistent-state transaction start, or restore invocation after shutdown closes admission.

- [ ] **Step 1: Dispose all coordinator work during shutdown**

Call `self.disposables.dispose()` after closing admission and cancelling the dedicated cleanup runner.

- [ ] **Step 2: Guard every named queued mutation callback**

Insert `guard self.isAcceptingOperations else { return }` inside did-remove-resource, ordinary reconcile, persistent-state, deleted archive-copy, and revision archive-copy queue blocks before their first store access or restore/transaction start. Guard `restore` itself as the shared last boundary.

- [ ] **Step 3: Verify targeted GREEN**

Run the Task 1 stale-callback command. Expected: `Ran 1 test`, `OK`.

---

### Task 4: Complete and commit the remediation

**Files:**
- Modify: `.superpowers/sdd/task-3-report.md`
- Verify: all changed production and contract files.

**Interfaces:**
- Consumes: both GREEN fixes.
- Produces: fresh verification evidence, updated report, and one new commit.

- [ ] **Step 1: Run focused and full verification**

Run registry, cleanup, history, and full `Tests/GRVMgramContracts` suites; run obsolete API/unsafe unlink greps and `git diff --check`.

- [ ] **Step 2: Self-review concurrency**

Verify lock order, reentrant callbacks, identity removal before delivery, queued versus running cancellation, exact-once waiter removal, no blob-metadata resurrection, and new-generation resume.

- [ ] **Step 3: Append evidence to the SDD report**

Record both RED/GREEN results, implementation ordering, test counts, static checks, commit SHA, and the Windows-only compilation concern.

- [ ] **Step 4: Stage exact files and create a new commit**

Run `git diff --cached --check`, then commit with `fix: finish coordinator replacement quiescence`.
