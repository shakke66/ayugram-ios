# GRVMgram Post-Release Fix Wave Design

**Date:** 2026-07-22

**Goal:** Close every non-green finding in `docs/grvmgram-functional-test-checklist.md`, remove the 27 product-rejected functions, preserve the confirmed working invariants, and produce one final validated iPhone build without repeated full-suite or CI churn.

## Scope and source of truth

- The QA checklist is authoritative for current feature status and exact acceptance criteria.
- `мозги/bdopus.md`, section 12, is the handoff and invariant summary. Historical green contracts are evidence of source shape, not proof of iPhone runtime behavior.
- The removal set is exactly the 27 entries marked `🗑️`: G02, G07, G08, AR01, AR07, N11–N13, A04, A09, A10, A12, C08, CP02, CP03, CP06, MS01–MS10, and ST05.
- The fix set is every entry marked `🟡` or `❌`, with duplicated roll-up rows Q01–Q05 closed by their owning fixes rather than implemented twice.
- Existing `✅` behavior must remain unchanged unless a recorded dependency requires a narrow adjustment.

## Execution architecture

The work is split into three implementation streams and one integration gate:

1. **Removal stream:** remove rejected settings rows, editors, consumers, hooks, localization keys, obsolete tests, and safe legacy-setting reads. It owns the shared settings schema and settings controllers while it runs.
2. **Broken-runtime stream:** repair unreachable, no-op, unsafe, or crashing paths. It begins with independent P0 findings and is divided by runtime ownership so one patch does not span unrelated subsystems.
3. **Partial/UI stream:** finish already-working behavior, public copy, localization, archive/history presentation, and Q04 adaptive settings layout. Layout work starts after the removal stream so deleted rows are not polished and the shared controllers are edited only once.
4. **Integration gate:** one combined contracts/validator gate, one independent whole-diff review, one final macOS build, then targeted device re-QA.

Agents may investigate independent streams in parallel. Production edits that touch `AyuGramSettings.swift`, `AyuGramSettingsUI`, shared hooks, or the same TelegramUI controller are serialized through one owner to avoid merge conflicts.

## Priority order

1. ST03 hard freeze.
2. G01 and ST15–ST17 reachability/read-state coupling.
3. Q01/Q02 client-wide settings and migration correctness.
4. F23/F23A/F27 self-account safety and F26A history completeness.
5. ST21/ST22 preserved-media loss/copy paths.
6. Remaining broken runtime groups.
7. Removal wave and dependent counter/schema cleanup.
8. Partial behavior, localization/copy, archive/history UI, and Q04 layout.

The removal stream may run before lower-priority runtime groups when it eliminates their conflicting settings/UI ownership.

## Q04 adaptive settings layout

- Do not change the global Telegram `ItemListSwitchItem` one-line default.
- Surviving GRVM switch rows use a scoped two-line title policy; their existing item layout supplies dynamic height and vertically centers the switch.
- At accessibility text sizes, rows may grow beyond two lines rather than overlap the trailing control.
- Disclosure rows remain inline when title and value fit. Known long title/value pairs use a stacked detail layout with a multiline title.
- Filters, General, Appearance, Chats, and Core settings are included; rows removed by the product decision are excluded.
- Raw `BlackFilledIcon`, mixed EN/RU copy, and missing spaces are copy/localization findings, not hidden inside the layout fix.

## Verification economy

- Every production bug starts with one focused failing contract that models the recorded runtime transition or source invariant, then receives the minimal fix and focused green run.
- A stream runs its related contract set once after its batch, not after every mechanical row deletion.
- The full `Tests/GRVMgramContracts` suite, `Tests/GRVMgramValidation`, source validator, and `git diff --check` run once after local integration, with one repeat only if integration fixes are needed.
- Review is independent: focused task review for P0/high-risk batches and one whole-diff review before CI.
- No intermediate GitHub Actions build. Run one macOS build only after local green state and review.
- Device re-QA is targeted to the affected routes, plus smoke checks for preserved invariants and RU/EN narrow-screen layout.

## Preserved invariants

- Other users' known deletions remain inline and in the account-scoped archive; current-account deletions do not.
- Edited/deleted marks remain configurable and attached to the correct bubbles.
- Per-message History remains scoped to the selected message.
- Local Premium remains exact-current-account policy while genuine Premium for other peers is preserved.
- Settings are client-wide; archives, revisions, media, and read/action data stay account-scoped.
- Public branding remains GRVMgram; compatible internal AyuGram names and persisted keys stay stable unless a removal task explicitly migrates them.
- Device screenshots and crash logs containing personal data are never committed or published.

## Completion criteria

- No checklist entry remains `🟡`, `❌`, or `🗑️` without an explicit externally blocked reason.
- All removed functions are absent from UI and unreachable at runtime, with safe legacy-value handling.
- All focused and combined local gates pass, independent review has no open Critical/Important findings, and one macOS CI produces a validated IPA.
- Targeted iPhone QA confirms P0 routes, client-wide settings, preserved media, archive/history behavior, and adaptive RU/EN settings layout.
