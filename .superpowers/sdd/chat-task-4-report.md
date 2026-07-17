# Chat / Appearance Task 4 Report

## Implemented

- Replaced Task 4 zero-argument hooks with exact-account `GRVMChatSettings` snapshots.
- Reused live `itemCollectionsView` installed IDs for emoji/sticker base content and search.
- Added namespace-aware `.Sticker` / `.CustomEmoji` pack-ID membership; nil, named, and builtin references remain ineligible only when `showOnlyAddedStickers` is enabled.
- Filtered emoji/sticker recents, peer-specific packs, featured packs, and search results while preserving stock behavior when disabled, Unicode/static/selected emoji, and saved/favorite stickers.
- Applied installed eligibility before `recentStickersCount`, with a separate post-append visible counter.
- Replaced only the GRVM reaction-row visibility policy with broadcast/group/private branches and unknown/missing fallback `true`; the result is the final render-condition AND.

## Files

- `Tests/GRVMgramContracts/test_chat_controls_contract.py`
- `submodules/TelegramUI/Components/ChatEntityKeyboardInputNode/Sources/ChatEntityKeyboardInputNode.swift`
- `submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiPagerContentSignals.swift`
- `submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift`
- `.superpowers/sdd/chat-task-4-report.md`

## TDD Evidence

- RED: `python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v` ran 8 tests with 18 expected source-contract assertion failures and 0 errors; both behavior fixtures already passed.
- GREEN: the same focused command ran 8 tests in 0.092s, all passed.
- Full local GRVM suite, run exactly once: `python -m unittest discover -s Tests/GRVMgramContracts -p 'test_*.py' -v` ran 237 tests in 3.722s, all passed.

## Checks

- `git diff --check`: clean; Windows `autocrlf` emitted informational LF/CRLF warnings only.
- `git diff --cached --check`: clean before staging; repeated after exact staging.
- Branch: `codex/grvmgram-full-parity`; base `7a1da8f18e20843dec21c0d2b496ad2b3555be7d` is an ancestor.
- Migrated Task 4 zero-argument hook search: no consumers remain in the three named Swift files.
- No push or CI run.

## Self-review

- Account: producers use `context.account.peerId`; reaction layout uses exact `item.context.account.peerId`.
- Compile/API: no new signatures, imports, dependencies, or BUILD changes; existing `TelegramMediaFile`, `ItemCollectionId`, `itemCollectionsView`, and SwiftSignalKit APIs are reused.
- Ordering/dedupe: disabled paths retain existing scope/order/dedupe; enabled search filters after stock dedupe and before append.
- Cap: ineligible and premium-disabled recent entries do not consume the visible limit; count increments only after append.
- Reaction scope: stock eligibility, available/send/merge logic, callbacks, and inline reactions are unchanged.

## Concerns and Deviations

- Windows cannot compile the iOS graph; final Swift compilation remains a macOS CI responsibility per Global Constraints. Source contracts and direct API inspection found no compile blocker.
- No implementation deviations from the binding preflight.
