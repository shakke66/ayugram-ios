# GRVMgram Post-Release Fix Wave Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the complete GRVMgram iOS project by removing all 27 rejected functions, fixing every `❌` finding, completing every `🟡` finding including Q04 adaptive UI, and producing one validated final IPA.

**Architecture:** Three isolated Codex tasks run concurrently: removals, partial/UI work, and broken runtime functions. They use strict ownership boundaries and focused RED/GREEN tests. This coordinator integrates their reviewed commits, resolves the few declared shared-file seams, runs one combined local gate and whole-diff review, then triggers one macOS CI and targeted device re-QA.

**Tech Stack:** Swift, UIKit/AsyncDisplayKit, Telegram-iOS/Postbox/MediaBox, Python 3.12 `unittest` source contracts, Bazel/rules_apple on final macOS CI, Git worktrees, Codex `gpt-5.6-sol` with `ultra` reasoning.

## Global Constraints

- Authoritative status and acceptance criteria: `docs/grvmgram-functional-test-checklist.md` in the coordinator checkout.
- Handoff and preserved invariants: `мозги/bdopus.md`, current section 12.
- Base branch: `codex/grvmgram-full-parity`, expected pre-wave HEAD `1688d97f9a85f5ee1cd1227a89ec418a68ebedd8` plus the coordinator's recorded ST03/plan working-tree snapshot.
- Every created implementation task uses `gpt-5.6-sol` and reasoning effort `ultra`.
- Each stream writes a detailed subplan before production edits, follows focused RED → minimal GREEN, then runs one related batch gate and one independent reviewer agent.
- Do not run the full contract suite after every small edit. Do not trigger intermediate GitHub Actions builds.
- The coordinator alone updates the master progress ledger and QA checklist, integrates branches, runs combined gates, pushes, triggers CI, records artifact metadata, and hands off device QA.
- Do not publish screenshots, crash logs, account identifiers, or other personal data.
- Preserve user changes and the untracked QA checklist. Never use destructive Git cleanup/reset commands.
- Preserve internal AyuGram-compatible symbols, persisted keys, and database filenames unless a removal task includes an explicit backward-compatible migration.
- Keep confirmed invariants: other-user deletions inline plus account archive; configurable marks; per-message History; exact-account Local Premium; client-wide settings with account-scoped archives/revisions/media/read data; public GRVMgram branding.

## Shared-file ownership and conflict policy

| Area | Primary owner | Rule |
|---|---|---|
| `AyuGramSettings.swift`, GRVM settings schema/migration | Stream A — removals | Streams B/C must not commit overlapping schema changes before Stream A reports its final commit. |
| `AyuGramSettingsUI` Core/General/Appearance/Chats controllers | Stream A — removals | Stream A removes rejected rows and applies the final multiline switch wiring to surviving rows. |
| `ItemListSwitchItem.swift`, `ItemListDisclosureItem.swift` adaptive infrastructure | Stream B — partial/UI | Defaults remain stock-compatible; new behavior is opt-in for GRVM rows. |
| Archive/history UI, localization/public copy | Stream B — partial/UI | Stream A may only remove explicitly rejected archive entries. |
| Runtime engines, hooks, TelegramUI consumers for `❌` functions | Stream C — broken runtime | Stream C defers changes that require the final removal schema until Stream A reports its commit. |
| QA checklist, master ledger, integration fixes, final CI | Coordinator | Child tasks report evidence; they do not edit coordinator bookkeeping. |

When a stream discovers an unavoidable overlap, it stops only that file, reports the exact hunk/interface to the coordinator, and continues its independent files. It does not duplicate or overwrite another stream's implementation.

---

## Stream A: Remove 27 rejected functions

**Exact product IDs:** G02, G07, G08, AR01, AR07, N11, N12, N13, A04, A09, A10, A12, C08, CP02, CP03, CP06, MS01, MS02, MS03, MS04, MS05, MS06, MS07, MS08, MS09, MS10, ST05.

**Deliverable:** Every rejected function is absent from public UI and unreachable at runtime; related settings, counters, consumers, hooks, localization, and tests are removed or migrated safely without deleting stock Telegram subsystems.

- [ ] Inventory each ID from setting field → UI row/editor → hook/consumer → localization → test.
- [ ] Write removal contracts that fail while rejected public UI/runtime routes remain.
- [ ] Remove the full feature slices in coherent groups: Ghost; archive/history; WebView; Appearance; Message Shot; compose popups; Joined.
- [ ] Preserve backward decoding of legacy settings while stopping new writes and public exposure.
- [ ] Update Ghost master semantics to the surviving four components and remove deleted cross-couplings.
- [ ] In the same owned controller pass, set surviving GRVM switch rows to opt-in multiline titles; do not polish rows being deleted.
- [ ] Run focused removal contracts once per coherent group, then one removal-stream batch gate and `git diff --check`.
- [ ] Dispatch one independent reviewer agent; fix all Critical/Important findings and re-run only affected focused tests.
- [ ] Commit reviewed changes in a small number of coherent commits and report commit SHAs, tests, remaining integration interfaces, and concerns to the coordinator.

## Stream B: Complete partial behavior, localization, and UI

**Exact product IDs:** G01; SP01; AR02, AR05A, AR06; F12, F19, F25, F26B; N01, N02, N03; A01, A02, A07, A08, A11; C05, C06; ST06, ST20; Q01, Q02, Q03, Q04, Q05. Roll-up Q rows are closed by their owning fixes rather than implemented twice.

**Deliverable:** Every partial finding meets its checklist acceptance criteria, public EN/RU copy is complete, archives/history are readable, and surviving settings rows are adaptive on narrow Russian layouts and Dynamic Type.

- [ ] Trace each partial finding to its runtime/UI root cause and split the detailed subplan into disjoint batches.
- [ ] Implement ItemList opt-in adaptive infrastructure: keep stock one-line defaults, allow two-line GRVM switch titles with dynamic height, and allow long disclosure title/value rows to stack safely.
- [ ] Cover Core, Filters, General, Appearance, and Chats screenshots while excluding Stream A removal IDs.
- [ ] Finish archive/history presentation, individual permanent delete, filter/avatar presentation, app-icon copy, badge/font/avatar/Premium UI, recent-sticker/channel-button behavior, GIF pause state, and Burn preservation.
- [ ] Replace residual English/raw/internal public labels with typed EN/RU GRVMgram resources; treat `BlackFilledIcon` and malformed spacing as copy defects, not layout workarounds.
- [ ] Defer shared settings-controller/schema hunks to the Stream A interface; provide the coordinator with an exact wiring patch or contract if Stream A must apply it.
- [ ] Run focused contracts for each batch, then one partial/UI batch gate and `git diff --check`.
- [ ] Dispatch one independent reviewer agent; fix all Critical/Important findings and repeat only affected tests.
- [ ] Commit reviewed changes coherently and report SHAs, test counts, integration seams, and device-only checks.

## Stream C: Fix broken runtime functions and P0 defects

**Exact product IDs:** G09, G10; SP04A; F11A, F22, F23, F23A, F26A, F27; A06, A13, A14; C02, C03, C04, C15; CM01, CM07; ST03, ST15, ST16, ST17, ST18, ST21, ST22.

**Deliverable:** Every broken or unreachable function has a real consumer and passes the recorded runtime transition; ST03 no longer freezes; self-account and media-preservation safety boundaries hold.

- [ ] Adopt the coordinator's existing ST03 RED/GREEN work, independently review it, and keep only one native profile-ID context-menu recognizer route.
- [ ] Group remaining bugs by shared root cause: Ghost/read/silent/schedule; filters/shadow/self-safety/history loading; appearance/folders/reactions/context menus; callback/read actions; preserved media/replay/local forward.
- [ ] For each group, trace the full call path and write focused failing contracts that model the observed runtime transition rather than merely checking symbol presence.
- [ ] Fix P0 order: ST03; G01-dependent ST15–ST17 reachability; self-account shadow/filter safety; filter-aware pagination; preserved one-view media and local forward copy.
- [ ] Do not independently rewrite settings schema/controllers owned by Stream A. Report the exact required post-removal interface for G01/G09/G10 and continue disjoint runtime consumers.
- [ ] Preserve stock Telegram reactions, read state, media, folders, and context menus outside GRVM opt-in policy.
- [ ] Run focused tests per root-cause group, then one broken-runtime batch gate and `git diff --check`.
- [ ] Dispatch one independent reviewer agent; fix all Critical/Important findings and repeat only affected tests.
- [ ] Commit reviewed changes coherently and report SHAs, test counts, integration seams, and device-only checks.

---

## Coordinator integration and final gate

### Coordinator status snapshot (2026-07-23)

- [x] Stream A removals integrated and focused/reviewer gates green.
- [x] Stream B partial/UI work integrated; F19 Phase 2 lower unread consumers are now coordinator-owned and verified.
- [x] Stream C runtime work integrated with its narrowed gate and read-only review green.
- [x] Combined local gate: GRVMgramContracts **537/537**, GRVMgramValidation **150/150**, source validator passed, `git diff --check` exit 0 (Windows line-ending warnings only).
- [x] One read-only whole-diff review dispatched in `gpt-5.6-sol`/`ultra`; verdict is recorded below when returned.
- [ ] macOS Swift/Bazel build, IPA validation, and targeted device re-QA remain pending; no commit/push has been performed.

- [ ] Monitor all three tasks; answer only real blockers and prevent overlapping ownership.
- [ ] Integrate Stream A first, then rebase/cherry-pick Stream B and Stream C reviewed commits around the declared interfaces.
- [ ] Resolve shared seams once: final settings schema/master count, surviving UI rows, client-wide migration, and GRVM adaptive disclosure wiring.
- [ ] Run focused integration regressions for any resolved conflict.
- [ ] Run one combined local gate:

```powershell
python -m unittest discover -s Tests\GRVMgramContracts -p "test_*.py" -v
python -m unittest discover -s Tests\GRVMgramValidation -p "test_*.py" -v
python build-system\Make\ValidateGRVMgram.py source
git diff --check
```

- [ ] Dispatch one `gpt-5.6-sol`/`ultra` whole-diff reviewer; fix all Critical/Important findings in one batch and re-run affected plus combined gates once.
- [ ] Update the QA checklist and `.superpowers/sdd/progress.md` with exact commits and evidence.
- [ ] Push once, trigger one macOS workflow, monitor through Swift/Bazel build, IPA validation, and artifact upload.
- [ ] Record run ID, commit, app version/build, artifact name, validator metadata, and IPA SHA-256.
- [ ] Give the user one targeted RU/EN iPhone re-QA checklist covering affected routes and preserved invariants.

### Final local verification addendum (2026-07-23)

- [x] F19 thread-aware unread boundary: bounded thread scan, hole metadata, account-scoped thread hook, conservative incomplete-scan guards, and async unread-snapshot revision invalidation.
- [x] Focused F19/runtime batch: **20/20**; Python contract suite: **537/537**; validation suite: **150/150**; source validator: passed.
- [x] `git diff --check`: exit 0 (only expected Windows LF→CRLF warnings).
- [ ] macOS Swift/Bazel build and device re-QA remain external release steps; no commit or push was performed.

### Final F19 display invalidation pass (2026-07-23)

- [x] Navigation badge paths use account-scoped `adjustedUnreadPeerReadState` and `filteredUnreadStateUpdates`; initial chat data carries the exact read-state snapshot needed for display-only subtraction.
- [x] `ApplicationContext` keeps raw notification events as the sole enqueue/sound path and removes an already-visible `ChatMessageNotificationItem` when a filter revision hides one of its full `Message` values.
- [x] Affected F19/runtime focused modules: **20/20** (notification/badge slice **4/4**); full contracts: **537/537**; validation: **150/150**; source validator passed.
