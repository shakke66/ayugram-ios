# GRVMgram Third-Build Remediation Design

**Date:** 2026-07-25

**Goal:** close every remaining non-green item from the second-build QA with the smallest safe set of production changes, remove `G09`, `A06`, and `C15`, preserve all confirmed green behavior, and produce a third-build checklist containing only changed or realistically affected behavior.

## Sources of truth

- Runtime and product requirements: `docs/grvmgram-second-build-qa-checklist.md`.
- Current handoff and ordering: `мозги/bdopus.md`, section 13.
- Git and CI prove source/build provenance; they do not replace device QA.
- The existing user/document changes in `docs/grvmgram-second-build-qa-checklist.md`, `docs/ui-testing.md`, and `docs/superpowers/plans/2026-07-25-grvm-notify-web-push.md` must be preserved.

## Product decisions

- Remove `G09 Schedule Messages` completely instead of implementing a custom enqueue-delay.
- Complete the already required removals `A06 Disable Custom Backgrounds` and `C15 Simple Replies` while preserving stock Telegram wallpapers and replies.
- `GRVM Notify` remains a separate workstream. No notification/PWA/native implementation is part of this remediation wave.

## Parallel execution architecture

Use three `gpt-5.6-sol` agents at `ultra` reasoning plus the root coordinator.

1. **Media/stability stream:** `ST22`, `ST20`, then runtime verification or repair of `ST21`.
2. **Quick/removal stream:** `G09`, `A06`, `C15`, `ST15`, and `Q03`.
3. **Settings/state stream:** `Q01`, followed by the related folder state cluster `A13`, `A14`, and `Q02` when ownership permits.
4. **Coordinator:** assigns file ownership before edits, resolves shared seams, reviews every diff, integrates tests, and redistributes agents for the remaining clusters.

After the first wave, agents are reassigned to:

- `A08 + C05 + Q04` shared slider/avatar/layout work;
- `C02 + C03 + CM01` reactions display/menu work;
- `SP04A`, `AR05A`, and `F22` as separate bounded fixes.

Agents may exchange source/interface findings, but they must not edit the same file concurrently. The coordinator is the only integration authority.

## Implementation principles

- Establish the recorded root cause before changing behavior.
- Add or adjust one focused regression test per real runtime transition; do not create speculative abstractions.
- Reuse known-good paths where available, such as ST16's exact read-to-top local path for ST15.
- Treat `Q04` and `Q05` as roll-up gates, not duplicate production features.
- Do not alter green behavior merely to simplify implementation.
- Do not commit, push, run GitHub Actions, or deploy GRVM Notify without a separate user instruction.

## Verification economy

- During a cluster: run only the focused test module(s) that cover its changed behavior plus `git diff --check` for the owned diff.
- Do not run the full contracts/validation suites after each card or mechanical removal.
- After all local integration: run one full GRVM contracts gate, one validation/source-validator gate, and one whole-tree `git diff --check`.
- Perform one independent whole-diff review; repeat only tests affected by review fixes.
- Build one macOS IPA only after local green state and explicit permission.
- Device QA for the third build covers only changed IDs, shared components touched by the fixes, and short critical smoke guards. It does not repeat the full first or second checklist.

## Third-build checklist design

Create `docs/grvmgram-third-build-qa-checklist.md` after implementation stabilizes.

Include:

- every ID whose production behavior, persistence schema, UI route, renderer, localization, or deletion path changed;
- roll-up cards `Q01`–`Q05` only where their owning fixes affect the third build;
- adjacent green guards only when the same edited code could regress them;
- exact RU path, prerequisites, short steps, expected result, and a blank result/status field;
- build provenance placeholders for the eventual third IPA.

Exclude:

- unchanged green features whose files and runtime seams were not touched;
- all 27 previously confirmed removals unless a shared cleanup edits their surviving stock seam;
- `GRVM Notify`, which receives its own PoC and release checklist later;
- duplicate tests that prove the same shared component transition.

## Preserved invariants

- Ghost remains four independent components with a derived `N/4` master and no runtime master gate.
- The 27 confirmed removals stay removed; stock Mini Apps, compose controls, Message actions, wallpapers, replies, and profile behavior survive.
- Deleted-message archive and revisions remain account/chat/topic scoped even though settings become client-wide.
- Own outgoing messages remain outside filtering and deleted-message preservation.
- `C04` private-reaction behavior and fixed `ST03` context menu behavior remain green.
- Preserved media is never consumed before durable preparation succeeds.
- Public branding remains GRVMgram and device evidence containing PII is not published.

## Completion criteria

- Every currently open card is either fixed locally or documented as requiring device evidence after a technically complete implementation.
- `G09`, `A06`, and `C15` have no active UI/runtime/schema/localization paths, with safe legacy decoding where necessary.
- Focused tests and the single combined local gate pass.
- Independent review has no unresolved Critical or Important findings.
- The targeted third-build QA checklist accurately reflects the final diff and contains no redundant full-product retest.
