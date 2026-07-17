# Chat / Appearance Task 5 Report

## Implemented

- Added authoritative subscriber actions for hidden panels and linked-discussion navigation.
- Applied the typed exact-account channel bottom mode only to stock mute branches: non-postable broadcasts, non-sendable gigagroups, Replies, and Verification Codes.
- Preserved join, kicked, pinned-message, and Saved Messages behavior; discuss mode falls back to the stock mute action without a real `peerDiscussionId`.
- Made hidden panels store their action, hide the container, return zero layout/minimal height, and restore visibility on nonhidden updates.
- Added exact-account Quick Admin availability for standard/default peer chats with the required state and channel permission matrix.
- Appended stable Recent Actions and Admins bar items after stock navigation items and rechecked availability before opening native controllers.
- Removed the old Ban context-menu shortcut, its redundant message fetch, and the two migrated legacy hook assignments.

## Files

- `Tests/GRVMgramContracts/test_chat_controls_contract.py`
- `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- `submodules/TelegramUI/Components/Chat/ChatChannelSubscriberInputPanelNode/Sources/ChatChannelSubscriberInputPanelNode.swift`
- `submodules/TelegramUI/Sources/ChatController.swift`
- `submodules/TelegramUI/Sources/ChatInterfaceStateNavigationButtons.swift`
- `submodules/TelegramUI/Sources/Chat/UpdateChatPresentationInterfaceState.swift`
- `.superpowers/sdd/chat-task-5-report.md`

## TDD Evidence

- Initial RED: `python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v` ran 12 tests with 4 expected failures and 0 errors. Missing behavior was exactly the typed subscriber actions, hidden zero-height layout, typed Quick Admin policy, and stable native actions.
- Legacy-wiring RED discovered during self-review: the focused suite ran 12 tests with 2 expected failures for the remaining `AyuGramFeatureManager` assignments.
- Focused GREEN: the same focused command ran 12 tests in 0.082s, all passed.
- Full local GRVM suite, run exactly once: `python -m unittest discover -s Tests/GRVMgramContracts -p 'test_*.py' -v` ran 241 tests in 1.964s, all passed.

## Checks

- `git diff --check`: clean; Windows `autocrlf` emitted informational LF/CRLF warnings only.
- Legacy scan: no bottom-mode or Quick Admin zero-argument consumers or wiring remain in the migrated call paths; declarations remain allowed for the final cleanup gate.
- Old Ban scan: no `Conversation_ContextMenuBan`, Quick Admin hook, or redundant message fetch remains in the peer context-menu closure.
- Changed-file scope matches Task 5 plus the required direct legacy-wiring call path and this report.
- Branch: `codex/grvmgram-full-parity`; base `0d5e0b1aed533b7dcfa03a39e08b415ff627867f` is an ancestor.
- No dependency, BUILD, localization, push, or CI changes.

## Self-review

- Account identity: channel mode uses `interfaceState.accountPeerId`; Quick Admin uses `presentationInterfaceState.accountPeerId`.
- Subscriber state: settings are read only inside configured stock mute branches; `peerDiscussionId` is the sole discussion source.
- Permissions: Recent Actions requires admin rights or creator status; Admins is public for group channels and admin-only for broadcasts.
- UI state: selection, non-default presentation, non-peer locations, scheduled, pinned, message-options, and custom-chat states suppress Quick Admin items.
- Navigation: stock primary/secondary items are untouched and remain first; stable GRVM items are appended and native factories are used after a fresh policy check.
- Context behavior: profile, chat, mention, search, gallery, and dismissal behavior remain unchanged after deleting only the obsolete Ban branch.

## Concerns

- Windows cannot compile the iOS Bazel graph. Final Swift compilation remains a macOS CI responsibility under the plan's Global Constraints; source contracts and direct API/signature inspection found no compile blocker.
