# Chat / Appearance Task 7 Report

## Status

Implemented real GRVMgram context-menu actions on `codex/grvmgram-full-parity` from base `edba6737`.

## Implementation

- Captured Shift/Control modifier state in both supported gesture recognizers, reset it with recognizer lifecycle, and forwarded a snapshot into message context-menu construction.
- Replaced legacy integer/zero-argument visibility consumers with typed, account-scoped `chatAppearance(...).contextMenu` placement.
- Added one touch-only `GRVMgram Actions` submenu for `.visibleWithModifier` actions and kept `.visible` actions top-level.
- Implemented Local Hide through a Postbox transaction and `_internal_applyMessageDeletion(..., mode: .server(.localAction))`, without a network deletion route.
- Implemented deduplicated author/forward-author message search with `beginMessageSearch(.member(peer), "")`.
- Added an ItemList-based message Details controller with IDs, dates, author/forward source data, view/forward counts, and image/file metadata.
- Implemented Repeat through a Postbox read plus normal `enqueueMessages`, preserving text/entities, one image/file reference, and thread ID while rejecting missing, empty, secret, service, multi-media, and unsupported content.
- Moved Add Filter into typed placement while preserving the exact `message.text` and `message.id.peerId` seed; retained View Filters, Show Filtered, and Shadow Ban outside that placement.
- Kept stock Delete, Send Now, edit-info, and per-message History independent.

## TDD Evidence

- Initial focused RED before production edits:
  - Command: `python -m unittest Tests.GRVMgramContracts.test_context_menu_semantics_contract -v`
  - Result: `Ran 8 tests`, `FAILED (failures=9)`.
  - The only PASS was the independence contract for stock Delete / Send Now / History.
- Extractor correction evidence:
  - First post-implementation run reached 7/8 PASS.
  - The remaining failure searched for `Show Filtered` only inside `grvmMessageFilterContextMenuItems`, although the preserved action is implemented by its called helper in the same `ChatController.swift` file.
  - The contract was corrected to check file-level preservation while keeping seed assertions brace-local.
- Focused GREEN:
  - Result: `Ran 8 tests`, `OK`.
- Full post-change suite:
  - Command: `python -m unittest discover -s Tests/GRVMgramContracts -p "test_*.py" -v`
  - Result: `Ran 258 tests`, `OK`.

## Files

- `submodules/Display/Source/ContextGesture.swift`
- `submodules/Display/Source/TapLongTapOrDoubleTapGestureRecognizer.swift`
- `submodules/TelegramUI/Sources/Chat/ChatControllerOpenMessageContextMenu.swift`
- `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- `submodules/TelegramUI/Sources/ChatController.swift`
- `submodules/TelegramUI/Sources/GRVMMessageDetailsController.swift`
- `submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift`
- `Tests/GRVMgramContracts/test_context_menu_semantics_contract.py`
- `.superpowers/sdd/chat-task-7-report.md`

## Self-review

- Exact account identity is passed through `context.account.peerId`; typed `GRVMContextMenuSettings` is the only context-menu appearance source.
- Local Hide does not require stock delete permission and does not call a network delete API.
- Repeat does not call `resendMessages` or `sendScheduledMessagesNow`, does not copy schedule/reply/send-as/paid attributes, and cannot enqueue an empty unsupported message.
- Add Filter retains its exact original expression/dialog seed; other filter actions remain available through their existing path.
- No dependency, BUILD, localization, push, or CI changes were made.
- `git diff --check` passed.

## Concerns / Limitations

- The Windows workspace cannot compile or run the iOS target. Swift API consistency was checked against the repository's actual declarations and call-site patterns, and all 258 GRVMgram contract tests passed.

## Reviewer Fix: Independent Stats Placement

- Root cause: Views and Reactions placements were calculated independently, but their shared `ChatReadReportContextItem` was always inserted into the top-level action list and carried unfiltered read/reaction state.
- RED:
  - Added a focused truth-table contract covering hidden/top-level/more combinations, combined routes, and split routes.
  - Command: `python -m unittest Tests.GRVMgramContracts.test_context_menu_semantics_contract -v`
  - Result: `Ran 9 tests`, `FAILED (failures=1)` because `grvmContextStatsRoutes` did not exist.
- Implementation:
  - Added per-placement routes with independent `includeReadReports` and `includeReactions` flags. Matching placements share one item; differing placements produce separate items.
  - Filtered `MessageReadStats` so views-only carries peers/timestamps with zero reactions, while reactions-only carries reaction count with empty peers/timestamps.
  - Views-only items remove `ReactionsMessageAttribute`; reaction calculation, custom-pack resolution, reaction refresh, and reaction action payloads are disabled when reactions are excluded.
  - Reactions-only items do not fetch read stats and receive an immediate local reaction-count state.
- GREEN:
  - Focused contract: `Ran 9 tests`, `OK`.
  - Focused contract plus the affected account-scoped reaction-row regression: `Ran 10 tests`, `OK`.
- Full post-fix suite:
  - The first run exposed the existing account-scoped reaction-state anchor after the implementation used a generic route variable: `Ran 259 tests`, `FAILED (failures=1)`.
  - Root cause was corrected by using the original `message` explicitly for reaction routes and the stripped message only for views-only routes.
  - Final command: `python -m unittest discover -s Tests/GRVMgramContracts -p "test_*.py" -v`
  - Final result: `Ran 259 tests`, `OK`.
- Fix files:
  - `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
  - `Tests/GRVMgramContracts/test_context_menu_semantics_contract.py`
  - `.superpowers/sdd/chat-task-7-report.md`
