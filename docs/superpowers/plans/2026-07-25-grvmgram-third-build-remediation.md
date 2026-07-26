# GRVMgram Third-Build Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every remaining second-build QA defect, remove G09/A06/C15, preserve all confirmed green behavior, and create a targeted third-build device checklist containing only changed or realistically affected behavior.

**Architecture:** Three ultra-reasoning implementation streams work on disjoint file sets while the root coordinator owns integration and shared-file handoffs. Every bug follows root-cause trace → focused RED → minimal GREEN; full contracts/validation and whole-diff review run once after all clusters. GRVM Notify is explicitly outside this plan.

**Tech Stack:** Swift, Telegram-iOS/Postbox/SwiftSignalKit, Bazel source layout, Python `unittest` source contracts, PowerShell on Windows 11.

## Global Constraints

- Runtime/product truth is `docs/grvmgram-second-build-qa-checklist.md`; current ordering/invariants are in `мозги/bdopus.md` section 13.
- Preserve existing user changes in `docs/grvmgram-second-build-qa-checklist.md`, `docs/ui-testing.md`, and `docs/superpowers/plans/2026-07-25-grvm-notify-web-push.md`.
- Do not commit, push, run GitHub Actions, or deploy without a separate user instruction.
- Do not run the complete contracts/validation suites per task. Run focused modules per cluster and one combined local gate after integration.
- Do not edit the same file concurrently. The coordinator must explicitly hand shared files from one stream to the next.
- Preserve the 27 confirmed removals, Ghost `N/4` without a runtime master gate, C04 private reactions, ST03 context-menu behavior, stock Telegram wallpapers/replies/Mini Apps/compose routes, and account-scoped archives/revisions/media/read data.
- Settings become client-wide; account data remains account-scoped.
- GRVM Notify remains an independent PWA/Web Push workstream and is not implemented here.

---

### Task 1: ST22 cancellable and terminal Forward Local Copy preparation

**Owner:** media/stability stream.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_preserved_media_actions_contract.py`
- Modify: `submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift`
- Inspect-only unless the RED proves a gap: `submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift`

**Interfaces:**
- Consumes: `Signal<GRVMPreservedMediaEnqueuePayload, GRVMPreservedMediaEnqueueError>` from `GRVMPreservedMediaEnqueue(context:message:)`.
- Produces: picker-owned, cancellable, bounded preparation that invokes the existing selection callback exactly once on success and returns the picker to an interactive error state on every non-success terminal path.

- [ ] **Step 1: Add the focused RED contracts**

Add `ReplayLocalForwardUIContractTests.test_local_copy_preparation_is_picker_owned_cancellable_and_bounded` and `test_local_copy_empty_completion_cleans_loading_and_shows_error`. They must require a retained disposable, a visible cancel closure, a timeout alternate, a completed handler, cleanup on `next/error/completed/cancel`, and errors presented on the peer selector rather than the hidden source chat.

- [ ] **Step 2: Run the ST22 RED command and verify the expected failures**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m unittest -v Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_local_copy_preparation_is_picker_owned_cancellable_and_bounded Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_local_copy_empty_completion_cleans_loading_and_shows_error
```

Expected: both new tests fail because the current code uses `.loading(cancelled: nil)`, discards the disposable, has no timeout, and has no completion callback.

- [ ] **Step 3: Implement one terminal lifecycle in `forwardMessages`**

Keep the existing pure availability and standalone enqueue payload. In the `localCopy` branch:

```swift
let preparationDisposable = MetaDisposable()
var receivedPayload = false
var terminal = false
```

Use a single main-queue cleanup function that is idempotent, dismisses the progress UI, resets `preparingLocalCopy`, and disposes the retained preparation. Present the loading controller through the picker with a cancel closure calling that cleanup. Add a bounded timeout whose alternate is `.fail(.unavailable)`. In `next`, set `receivedPayload`, store the payload, cleanup, and re-enter the existing selection callback. In `error`, cleanup and show the existing typed error over the picker. In `completed`, if no payload was received, cleanup and show the unavailable error. Never enqueue twice.

- [ ] **Step 4: Run the focused ST22 GREEN and adjacent forward guards**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_local_copy_preparation_is_picker_owned_cancellable_and_bounded Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_local_copy_empty_completion_cleans_loading_and_shows_error Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_local_copy_availability_is_pure_and_prefers_durable_marker_media Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_local_copy_bridge_is_nullable_chat_owned_and_separate_from_stock_forward Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_local_copy_single_selection_preserves_forum_thread Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_local_copy_reuses_stock_selector_paid_commit_enqueue_and_pending_pipeline
git diff --check -- submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift Tests/GRVMgramContracts/test_preserved_media_actions_contract.py
```

Expected: focused tests pass and the stock selector/forum/paid/enqueue paths remain present.

---

### Task 2: ST20 fail-closed Burn preparation and ST21 dependency verification

**Owner:** media/stability stream. It retains `ChatInterfaceStateContextMenus.swift` until this task is reviewed.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_preserved_media_actions_contract.py`
- Modify: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- Modify: `submodules/GalleryUI/Sources/SecretMediaPreviewController.swift`
- Modify: `submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift`
- Inspect-only first: `submodules/TelegramUI/Sources/ChatController.swift`, `submodules/TelegramUI/Sources/OpenChatMessage.swift`, gallery/open-message parameter files.

**Interfaces:**
- Consumes: `AyuGramHooks.prepareConsumableMedia(accountPeerId,message) -> Signal<Bool, NoError>`.
- Produces: SP01 OFF direct consume; SP01 ON consume only after exact fetch, positive bytes, durable archive, and marker; false or empty completion never consumes.

- [ ] **Step 1: Add focused RED contracts for terminal fetch, dismiss ordering, and first-open gates**

Add:

- `ArchiveHooksSentinelContractTests.test_prepare_fetch_is_terminal_and_fail_closed`;
- `ReplayLocalForwardUIContractTests.test_burn_waits_for_context_menu_dismissal`;
- `ReplayLocalForwardUIContractTests.test_first_open_consumes_only_after_preservation_success`.

The first requires `reportResultStatus: true`. The second requires `grvmBurnMessage` to be called from the context-menu dismiss completion. The third requires preview/playlist consumers to branch on the emitted `Bool` and treat no value as failure.

- [ ] **Step 2: Run the ST20 RED command**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_preserved_media_actions_contract.ArchiveHooksSentinelContractTests.test_prepare_fetch_is_terminal_and_fail_closed Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_burn_waits_for_context_menu_dismissal Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_first_open_consumes_only_after_preservation_success
```

Expected: failures identify the default non-reporting fetch, immediate confirmation presentation, and consumers that ignore `false`/empty completion.

- [ ] **Step 3: Make fetch terminal and fail closed**

In `prepareConsumableMedia`, call:

```swift
fetchedMediaResource(
    mediaBox: self.mediaBox,
    userLocation: .peer(preparation.message.id.peerId),
    userContentType: fetchResource.userContentType,
    reference: fetchResource.reference,
    reportResultStatus: true,
    continueInBackground: true
)
```

Map success to `true`, errors to `.single(false)`, and ensure every preparation branch emits exactly one `Bool`. Do not attach `GRVMPreservedConsumableMediaAttribute` before all required resources have positive completed bytes and durable archive records.

- [ ] **Step 4: Gate Burn, preview, and playlist consumption**

Present the Burn confirmation only inside `c?.dismiss(... completion:)`. Preserve direct consume when SP01 is OFF. When SP01 is ON, use `take(1)` plus a completed fallback so only `prepared == true` calls consume; `false` or completion without value shows the typed error and leaves content unconsumed. Apply the same truth table to first-open preview and playlist paths. Use the exact `AyuGramHooks.shouldPreserveOneTimeMedia` admission hook rather than the broader deleted-message hook. For the playlist, a minimal `TelegramPresentationData` dependency plus native `UIAlertController` presentation is allowed.

- [ ] **Step 5: Run focused ST20 GREEN and ST21 source guards**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_preserved_media_actions_contract.ArchiveHooksSentinelContractTests.test_prepare_fetch_is_terminal_and_fail_closed Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_burn_waits_for_context_menu_dismissal Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_first_open_consumes_only_after_preservation_success Tests.GRVMgramContracts.test_preserved_media_actions_contract.ArchiveHooksSentinelContractTests.test_prepare_reloads_exact_row_and_selects_positive_primary_resources Tests.GRVMgramContracts.test_preserved_media_actions_contract.ArchiveHooksSentinelContractTests.test_prepare_persists_every_terminal_record_before_attaching_marker Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_burn_source_has_irreversible_truth_table_and_one_forced_call Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_replay_fixture_keeps_normal_receipts_and_disables_every_replay_edge Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_replay_flag_propagates_through_gallery_and_playlist Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_replay_voice_playlist_is_scoped_to_the_exact_message Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_replay_receipt_gates_prepare_and_consume_only_on_normal_open Tests.GRVMgramContracts.test_preserved_media_actions_contract.ReplayLocalForwardUIContractTests.test_replay_restore_is_rechecked_and_opens_a_fresh_message
git diff --check -- submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift submodules/GalleryUI/Sources/SecretMediaPreviewController.swift submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift Tests/GRVMgramContracts/test_preserved_media_actions_contract.py
```

Expected: ST20 focused tests and existing ST21 exact-viewer/receipt guards pass. Do not change ST21 production files unless one of these focused guards proves the current exact standalone flow incomplete.

---

### Task 3: Remove G09, A06, and C15 completely

**Owner:** quick/removal stream. It may work in parallel with Tasks 1–2 except for shared-file handoffs noted below.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_removals_contract.py`
- Modify: `Tests/GRVMgramContracts/test_account_settings_contract.py`
- Modify: `Tests/GRVMgramContracts/test_ghost_settings_contract.py`
- Modify: `Tests/GRVMgramContracts/test_ghost_runtime_contract.py`
- Modify: `Tests/GRVMgramContracts/test_ghost_boundary_fix_contract.py`
- Modify: `Tests/GRVMgramContracts/test_runtime_removal_compatibility_contract.py`
- Modify: `Tests/GRVMgramContracts/test_appearance_surfaces_contract.py`
- Modify: `Tests/GRVMgramContracts/test_chat_controls_contract.py`
- Modify: `Tests/GRVMgramContracts/test_grvmgram_localization_resources_contract.py`
- Modify: `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- Delete: `submodules/AyuGramLib/Sources/GRVMGhostSchedule.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift`
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Modify: `submodules/TelegramCore/Sources/GRVMChatAppearance.swift`
- Modify: `submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift`
- Modify: `Telegram/Telegram-iOS/en.lproj/GRVMgram.strings`
- Modify: `Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings`
- Modify after coordinator handoff: `submodules/TelegramUI/Sources/ChatController.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageReplyInfoNode/Sources/ChatMessageReplyInfoNode.swift`

**Interfaces:**
- Produces: no G09/A06/C15 schema, UI, hook, policy, runtime, localization, or positive contract path.
- Preserves: stock scheduled-message pipeline, G10 silent mode, forced/per-chat/global wallpaper priority, and stock name-color replies/navigation.

- [ ] **Step 1: Rewrite removal contracts first and verify RED**

Require removal of `useScheduledMessages`, `disableCustomBackgrounds`, and `disableColoredReplies`, their UI/routes/hooks/policies/strings, and the `GRVMGhostSchedule.swift` helper. Require preservation of stock scheduled attributes/pickers/enqueue, `forcedWallpaper` before per-chat wallpaper, and unconditional stock `author?.nameColor` handling.

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_removals_contract Tests.GRVMgramContracts.test_account_settings_contract Tests.GRVMgramContracts.test_ghost_settings_contract Tests.GRVMgramContracts.test_ghost_runtime_contract Tests.GRVMgramContracts.test_runtime_removal_compatibility_contract Tests.GRVMgramContracts.test_appearance_surfaces_contract Tests.GRVMgramContracts.test_chat_controls_contract Tests.GRVMgramContracts.test_grvmgram_localization_resources_contract
```

Expected: updated tests fail against the still-present slices.

- [ ] **Step 2: Remove G09 without touching stock scheduling**

Remove the settings field/default/init/codec/mutator, Core settings rows, hook/manager wiring, helper file, custom ChatController delay/proxy/recursive-commit gate, and two localization keys. Leave `shouldDivertMessagesToScheduled`, `OutgoingScheduleInfoMessageAttribute`, scheduled subject/commit flow, transform/enqueue, schedule picker, media `scheduleTime`, G10, and Ghost `N/4` unchanged.

- [ ] **Step 3: Remove A06 while restoring stock wallpaper flow**

Remove the settings field, Appearance row, appearance snapshot/policy property, hook/manager wiring, runtime branch, and string. The surviving branch order must be:

```swift
if let forcedWallpaper = strongSelf.forcedWallpaper {
    // existing forced wallpaper handling
} else if let chatWallpaper {
    // existing per-chat wallpaper handling
}
```

Do not add a tombstone field; legacy JSON keys are ignored by Codable after field removal.

- [ ] **Step 4: Remove C15 while preserving stock replies**

Remove the settings field, Chats row, chat snapshot/policy property, localized string, and positive contracts. In `ChatMessageReplyInfoNode`, remove the GRVM conditional and always execute the existing `switch author?.nameColor` stock behavior. Preserve author, quote text, thumbnail, and exact-source navigation.

- [ ] **Step 5: Run the removal cluster GREEN**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_removals_contract Tests.GRVMgramContracts.test_account_settings_contract Tests.GRVMgramContracts.test_ghost_settings_contract Tests.GRVMgramContracts.test_ghost_runtime_contract Tests.GRVMgramContracts.test_ghost_boundary_fix_contract Tests.GRVMgramContracts.test_runtime_removal_compatibility_contract Tests.GRVMgramContracts.test_appearance_surfaces_contract Tests.GRVMgramContracts.test_chat_controls_contract Tests.GRVMgramContracts.test_grvmgram_localization_resources_contract
```

Expected: removal and stock-survival contracts pass. Do not run the full suite.

---

### Task 4: ST15 read-to-top and Q03 typed History label

**Owner:** quick/removal stream after media stream releases `ChatInterfaceStateContextMenus.swift`.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_peer_message_actions_contract.py`
- Modify: `Tests/GRVMgramContracts/test_history_presentation_contract.py`
- Modify: `submodules/TelegramUI/Sources/ChatController.swift`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`

**Interfaces:**
- Consumes: existing `ChatControllerImpl.grvmApplyTopReadIndex(mode:)` and existing `GRVMgramStrings.menuHistory`.
- Produces: ST15 reads the whole exact chat/topic locally; Russian history action uses `История`.

- [ ] **Step 1: Make focused tests RED**

Update the ST15 contract to require `grvmApplyTopReadIndex(mode: .localOnly)` without `message.index`. Update History presentation to require `grvmStrings[.menuHistory]` and reject hardcoded `text: "History"`.

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_peer_message_actions_contract.PeerMessageUIContractTests.test_read_message_is_one_incoming_cloud_ghost_scoped_local_action Tests.GRVMgramContracts.test_history_presentation_contract.HistoryPresentationContractTests.test_history_action_copy_is_typed_and_exact_in_both_languages
```

- [ ] **Step 2: Reuse the known-good exact read-to-top path**

Change `private func grvmApplyTopReadIndex(mode:)` to module-internal `func`. Replace only the ST15 context action call with:

```swift
chatController.grvmApplyTopReadIndex(mode: .localOnly)
```

Do not alter TelegramCore read APIs, ST16, ST17, or server receipt behavior.

- [ ] **Step 3: Use the typed History string**

Replace only:

```swift
text: "History"
```

with:

```swift
text: grvmStrings[.menuHistory]
```

- [ ] **Step 4: Run focused GREEN and adjacent guards**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_peer_message_actions_contract.PeerMessageUIContractTests.test_read_message_is_one_incoming_cloud_ghost_scoped_local_action Tests.GRVMgramContracts.test_peer_message_actions_contract.PeerMessageUIContractTests.test_read_all_uses_top_cloud_index_at_action_time_for_both_locations Tests.GRVMgramContracts.test_history_presentation_contract.HistoryPresentationContractTests.test_history_action_copy_is_typed_and_exact_in_both_languages Tests.GRVMgramContracts.test_grvmgram_localization_resources_contract
```

---

### Task 5: Q01 single client-wide settings snapshot

**Owner:** settings/state stream. It must not edit `AyuGramSettings.swift` or settings controllers during Task 3.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_account_settings_contract.py`
- Modify: `Tests/GRVMgramContracts/test_account_registry_contract.py`
- Modify if typed pipeline requires it: `Tests/GRVMgramContracts/test_telegramui_compile_contract.py`
- Modify: `submodules/AyuGramLib/Sources/GRVMAccountSettings.swift`
- Modify: `submodules/TelegramUI/Sources/AppDelegate.swift`

**Interfaces:**
- Preserve public signatures `grvmSettings(accountId:accountManager:)` and `updateGRVMSettings(accountId:accountManager:_:)`; `accountId` remains for call-site compatibility but no longer selects a settings snapshot.
- Archives, revisions, preserved media, filters/action data, unread/read state, and Telegram account data remain account-scoped.

- [ ] **Step 1: Replace account-scoped contracts with client-wide RED contracts**

Require all account IDs to read/write one snapshot, a Postbox-safe JSON `Data` envelope, deterministic migration, and no fallback to another account after the new-format value exists. Keep startup order tests proving migration precedes service registration.

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_account_settings_contract Tests.GRVMgramContracts.test_account_registry_contract Tests.GRVMgramContracts.test_telegramui_compile_contract
```

Expected: account-scoped expectations fail until the envelope implementation changes.

- [ ] **Step 2: Implement one shared envelope value**

Keep the envelope Postbox-safe. Store one `AyuGramSettings` value under a stable client-wide key instead of indexing `values[accountKey]`. Keep backward decode of the existing `[Int64: AyuGramSettings]` payload only for migration.

Migration precedence is deterministic:

1. already stored new client-wide snapshot;
2. primary active account entry from the old map;
3. smallest stable active account ID present in the old map;
4. legacy shared-data key `ApplicationSpecificSharedDataKeys.ayuGramSettings`;
5. `AyuGramSettings.defaultSettings`.

After writing the new format, never re-import an old per-account value.

- [ ] **Step 3: Pass the deterministic primary account during startup migration**

In `makeGRVMActiveAccountsSnapshotSignal(...)`, preserve migration-before-snapshot ordering and supply the primary account identity required by the migration rule. Do not change per-account archive-service registration.

- [ ] **Step 4: Run focused Q01 GREEN**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_account_settings_contract Tests.GRVMgramContracts.test_account_registry_contract Tests.GRVMgramContracts.test_telegramui_compile_contract
git diff --check -- submodules/AyuGramLib/Sources/GRVMAccountSettings.swift submodules/TelegramUI/Sources/AppDelegate.swift Tests/GRVMgramContracts/test_account_settings_contract.py Tests/GRVMgramContracts/test_account_registry_contract.py Tests/GRVMgramContracts/test_telegramui_compile_contract.py
```

---

### Task 6: A13/A14/Q02 one folder visibility and ordering policy

**Owner:** settings/state stream.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_appearance_consumers_contract.py`
- Modify: `submodules/ChatListUI/Sources/ChatListController.swift`
- Modify: `submodules/ChatListUI/Sources/ChatListControllerNode.swift`
- Modify: `submodules/TelegramUI/Components/PeerSelectionController/Sources/PeerSelectionController.swift`
- Modify: `submodules/TelegramUI/Components/ChatList/ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift`
- Modify only if required for AyuGramLib import: `submodules/TelegramUI/Components/PeerSelectionController/BUILD`

**Interfaces:**
- Consumes: client-wide `grvmSettings` snapshot.
- Produces: identical visible filter set, selected filter, content filter, and badge layout in main chat list and peer selection.

- [ ] **Step 1: Add RED contracts for the shared visible set and persistence**

Require both surfaces to combine the GRVM settings signal, hide badges with zero alpha and zero width/spacing, hide `.all` only when another tab exists, keep `.all` when it is the only tab, and remap hidden selected `.all` to the first visible filter. Reject every conditional `insert(.all, at: 0)` normalization that overrides a stored order.

- [ ] **Step 2: Verify RED**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_appearance_consumers_contract.AppearanceConsumersContractTests.test_hide_badges_propagates_through_all_component_paths Tests.GRVMgramContracts.test_appearance_consumers_contract.AppearanceConsumersContractTests.test_folder_layout_uses_one_account_snapshot_and_one_visible_filter_set
```

- [ ] **Step 3: Remove order normalization from reload paths**

In both `ChatListController.reloadFilters` and `PeerSelectionController.reloadFilters`, preserve server/persisted order for Premium and non-Premium accounts. Do not insert `.all` at index zero merely because the account lacks server Premium.

- [ ] **Step 4: Apply one live presentation policy**

Main `HorizontalTabsComponent` and legacy tab nodes must derive the same visible filters and selection fallback. A hidden badge contributes neither opacity nor measured width. Toggling settings must update already visible tabs without mutating unread counts or folder data.

- [ ] **Step 5: Run focused GREEN**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_appearance_consumers_contract
git diff --check -- submodules/ChatListUI/Sources/ChatListController.swift submodules/ChatListUI/Sources/ChatListControllerNode.swift submodules/TelegramUI/Components/PeerSelectionController/Sources/PeerSelectionController.swift submodules/TelegramUI/Components/ChatList/ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift Tests/GRVMgramContracts/test_appearance_consumers_contract.py
```

---

### Task 7: A08/C05/Q04 shared slider lifecycle, avatar geometry, and recent-sticker runtime limit

**Owner:** reassigned ultra UI stream after first-wave review.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_partial_ui_controllers_contract.py`
- Modify: `Tests/GRVMgramContracts/test_appearance_surfaces_contract.py`
- Modify: `Tests/GRVMgramContracts/test_chat_controls_contract.py`
- Modify: `submodules/AyuGramSettingsUI/Sources/GRVMIntegerSliderItem.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramIntegerValueControllers.swift`
- Modify: `submodules/AvatarNode/Sources/AvatarNode.swift`
- Modify: `submodules/TelegramUI/Components/Stories/AvatarStoryIndicatorComponent/Sources/AvatarStoryIndicatorComponent.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatAvatarNavigationNode/Sources/ChatAvatarNavigationNode.swift`
- Modify narrowly for A08 live invalidation: `submodules/TelegramUI/Sources/ChatHistoryListNode.swift`
- Modify: `submodules/TelegramCore/Sources/State/ApplyUpdateMessage.swift`
- Modify: `submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift`
- Modify: `submodules/TelegramCore/Sources/State/SynchronizeRecentlyUsedMediaOperations.swift`
- Modify: `submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiPagerContentSignals.swift`

- [ ] **Step 1: Add RED contracts for post-load slider configuration and real runtime limits**

Require `GRVMIntegerSliderItemNode.didLoad` to configure the slider from the latest item/layout state even if the first layout occurred before view creation. Require A08 preview to receive the current account peer/avatar, live settings revision to invalidate visible avatars, and all overlay/ring paths to use a normalized radius derived from actual bounds. Require every recent-sticker write path and open keyboard data source to honor `1...200`, not hardcoded `20`.

- [ ] **Step 2: Run focused RED**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_partial_ui_controllers_contract Tests.GRVMgramContracts.test_appearance_surfaces_contract Tests.GRVMgramContracts.test_chat_controls_contract
```

- [ ] **Step 3: Fix the shared slider lifecycle once**

Persist the last item/layout values on the node and invoke the same configuration helper from both layout apply and `didLoad`. Clamp and display integer values without waiting for background/foreground.

- [ ] **Step 4: Normalize avatar shape and live invalidation**

Compute radius from current bounds, pass the normalized shape/radius to the image mask, Story ring, chat-header avatar, and overlays, and react to the client-wide appearance revision. Use the current account photo in preview and placeholder only when no image exists. Remove any transform/geometry path capable of rotating a rounded rectangle into a diamond.

- [ ] **Step 5: Honor recent-sticker count end to end**

Replace all four `removeTailIfCountExceeds: 20` writes with the exact client setting or a shared clamped helper and make the open keyboard react to setting changes. Preserve item order.

- [ ] **Step 6: Run focused GREEN**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_partial_ui_controllers_contract Tests.GRVMgramContracts.test_appearance_surfaces_contract Tests.GRVMgramContracts.test_chat_controls_contract Tests.GRVMgramContracts.test_itemlist_adaptive_contract
```

---

### Task 8: C02/C03/CM01 complete reaction display and real picker-panel policy

**Owner:** reassigned ultra reactions stream.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_chat_controls_contract.py`
- Modify: `Tests/GRVMgramContracts/test_context_menu_semantics_contract.py`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift`
- Modify every renderer path identified by the RED trace for text/caption/footer/sticker/animated-sticker/instant-video reactions.
- Modify: `submodules/TelegramUI/Sources/Chat/ChatControllerOpenMessageContextMenu.swift`
- Modify if policy extraction requires it: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`

- [ ] **Step 1: Trace all reaction renderers and add RED behavior contracts**

Tests must fail if channel/group policy is applied only in `ChatMessageBubbleItemNode`, if an open chat lacks live invalidation, or if `showReactionsPanelInContextMenu` controls `ChatReadReportContextItem` rather than `actions.reactionItems`.

- [ ] **Step 2: Apply one display-only policy to every renderer**

Hide already placed reactions locally for broadcast channels or groups/supergroups according to their independent settings. Do not disable the picker, sending/removing reactions, server state, or C04 private behavior. Trigger a live rebuild when settings change.

- [ ] **Step 3: Connect CM01 to the real reaction picker panel**

`Hidden` omits `actions.reactionItems`; `Shown` keeps it in the main context menu; `With Modifier` routes it through the existing GRVM extended/submenu placement. Do not repurpose read-report statistics.

- [ ] **Step 4: Run focused GREEN**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_chat_controls_contract Tests.GRVMgramContracts.test_context_menu_semantics_contract
```

---

### Task 9: AR05A persistent exact local purge without respawn

**Owner:** reassigned ultra archive stream.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_archive_delete_sp01_contract.py`
- Modify: `Tests/GRVMgramContracts/test_local_deletion_contract.py`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- Modify archive/coordinator/store files identified by `removeDeletedMessage` trace.

- [ ] **Step 1: Add RED contracts for chat-context local purge and tombstone behavior**

Require `Удалить локально` for an already saved deletion regardless of admin rights, exact `account + dialog + topic + message ID` cleanup, no neighboring/shared-resource damage, and a persistent tombstone/cleanup rule preventing the server-delete path from re-admitting the same row.

- [ ] **Step 2: Implement one exact purge bridge**

Expose the existing typed removal result to the chat context menu. For live messages with server delete permission, perform confirmed server deletion first and then exact local purge. For already deleted rows, perform only local purge. Persist the suppression boundary so replayed delete updates cannot respawn the row.

- [ ] **Step 3: Run focused GREEN**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_archive_delete_sp01_contract Tests.GRVMgramContracts.test_local_deletion_contract Tests.GRVMgramContracts.test_media_archive_contract
```

---

### Task 10: F22 resolved forwarded-origin identity and unambiguous targets

**Owner:** reassigned ultra filter stream.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_filter_ui_contract.py`
- Modify: `Tests/GRVMgramContracts/test_filter_contract.py`
- Modify Shadow Ban controller/context-menu files discovered by the existing `sourceAuthorInfo.originalAuthor` and `PeerId.toInt64()` trace.

- [ ] **Step 1: Add RED contracts for public identity display and distinct target labels**

Require separate entries for wrapper forward author and original source author, resolved display name, public Telegram/Bot-compatible ID rather than raw namespaced `PeerId.toInt64()`, exact mutation peer identity, self-ban rejection, and live unhide after removal.

- [ ] **Step 2: Store identity, format presentation separately**

Keep the internal `PeerId` required for exact mutation. Resolve the peer for UI and format its public ID using the existing peer-ID helper; never use the displayed string as the mutation key. Give the two source kinds distinct localized labels.

- [ ] **Step 3: Run focused GREEN**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_filter_ui_contract Tests.GRVMgramContracts.test_filter_contract
```

---

### Task 11: SP04A complete the supported cross-client Local Premium state

**Owner:** dedicated ultra protocol stream after other overlapping send/entity work is stable.

**Files:**
- Modify: `Tests/GRVMgramContracts/test_local_premium_sync_contract.py`
- Inspect and modify only after trace: `submodules/TelegramCore/Sources/ApiUtils/TextEntitiesMessageAttribute.swift`, `submodules/TelegramCore/Sources/State/PendingMessageManager.swift`, `submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift`, `submodules/TelegramCore/Sources/State/ApplyUpdateMessage.swift`, `submodules/TelegramCore/Sources/ApiUtils/StoreMessage_Telegram.swift`, and Local Premium peer-state storage/presentation consumers.

- [ ] **Step 1: Reconcile the QA requirement with actual transport capabilities**

Trace the full outgoing custom-emoji entity shim, short ACK, incoming decode, peer presentation, status selection reset, and persistence. Record which state can be represented through Telegram-compatible entities without a backend. Do not claim server Premium or invent a network service.

- [ ] **Step 2: Add RED contracts for every supported state transition**

At minimum cover ordinary send, media caption, reply quote, edit, short ACK, exact single-emoji validation, status persistence after relaunch, peer-scoped badge/status update on the second GRVMgram client after receiving the compatibility payload, OFF cleanup, and preservation of genuine server Premium/self/channel-pack behavior.

- [ ] **Step 3: Implement the minimal backwards-compatible transport and peer cache**

Use Telegram-valid message entities/payloads already accepted by stock clients. Persist the decoded GRVM compatibility state account+peer scoped, expire or replace it deterministically, and render it only in GRVMgram. Never grant server-side Premium capabilities. If profile/sticker state cannot be transported through an existing Telegram-valid boundary, document that exact technical limitation in the third checklist rather than fabricating a backend.

- [ ] **Step 4: Run focused GREEN**

```powershell
python -B -m unittest -v Tests.GRVMgramContracts.test_local_premium_sync_contract
```

---

### Task 12: Integration gate, independent review, and targeted third-build checklist

**Owner:** root coordinator plus one fresh ultra reviewer.

**Files:**
- Create: `docs/grvmgram-third-build-qa-checklist.md`
- Modify only if necessary for accurate handoff: `мозги/bdopus.md` outside the checkout.
- Inspect: complete working-tree diff and all focused test reports.

- [ ] **Step 1: Run the single combined local gate**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m unittest discover -s Tests/GRVMgramContracts -p 'test_*.py'
python -B -m unittest discover -s Tests/GRVMgramValidation -p 'test_*.py'
python -B build-system/Make/ValidateGRVMgram.py source --root .
git diff --check
```

Expected: all contracts and validation pass. Re-run only modules affected by any integration fix; do not repeat the full gate unless the integration fix changes shared schemas or validators.

- [ ] **Step 2: Perform one independent whole-diff review**

The reviewer checks spec compliance, shared-file handoffs, async terminal paths, migration safety, stock-survival guards, and test quality. Fix Critical/Important findings in one consolidated fix wave, then run one scoped re-review.

- [ ] **Step 3: Derive the third checklist from the actual diff**

Include every changed second-build ID plus only adjacent guards whose production files or shared components changed. Deduplicate shared transitions:

- one slider/layout preparation covers A08/C05/Q04 setup, followed by short per-feature assertions;
- one folder setup covers A13/A14/Q02;
- one reaction setup covers C02/C03/C04/CM01, with C04 only as a regression guard;
- one consumable-media setup covers ST20/ST21/ST22/Q05;
- one client-settings setup covers Q01 and account-isolation guards;
- removals G09/A06/C15 each prove absence plus surviving stock behavior.

Each card contains: ID, why it is included, exact RU UI path, prerequisites, concise steps, expected result, blank status, and blank observation. Add build provenance placeholders but no false IPA values.

- [ ] **Step 4: Verify checklist scope mechanically and manually**

Compare the final `git diff --name-only` and changed production symbols against checklist IDs. Confirm no unchanged feature is included merely because it appeared in the second checklist, and no touched shared consumer lacks a regression guard.

- [ ] **Step 5: Stop before external release actions**

Report local implementation and verification results. Do not commit, push, start GitHub Actions, or claim device PASS. A single macOS build and targeted device run require the user's separate instruction.
