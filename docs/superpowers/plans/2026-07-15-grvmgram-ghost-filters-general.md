# GRVMgram Ghost, Filters, and General Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Desktop-equivalent Ghost Mode, message filters, translation selection, link handling, and Webview controls while making every affected decision account-scoped and preserving already-working General features.

**Architecture:** Persist typed settings per account, resolve every TelegramCore/TelegramUI hook through the exact registered account service, and keep pure policy in AyuGramLib. Ghost networking remains at the authoritative TelegramCore mutation points. Filtering compiles immutable account snapshots and evaluates complete `Message` objects before history entries are built. General integrations reuse Telegram's existing UI and networking primitives, with small Foundation-only helpers for external translation and URL rewriting.

**Tech Stack:** Swift, Foundation, UIKit, Postbox, TelegramCore, TelegramEngine, SwiftSignalKit, ItemListUI, UniformTypeIdentifiers-compatible document picking, Python 3.12 `unittest` source-contract tests, Bazel/rules_apple in final macOS CI.

## Global Constraints

- Execute after `2026-07-15-grvmgram-account-storage-media.md`; it provides account settings, the registry, and synchronized coordinator snapshots.
- Execute before `2026-07-15-grvmgram-chat-appearance-parity.md`; that plan consumes the filter editor interface defined here.
- Preserve the user's uncommitted `ManagedSynchronizePeerReadStates.swift` fix: suppressed read-state pushes must consume the operation with `confirmSynchronizedIncomingReadState`, never a bare synchronous `.complete()`.
- Keep internal AyuGram module/type/hook names and legacy Codable keys for migration. Public copy is localized as GRVMgram by the final localization plan.
- Never introduce a new account-dependent or message-dependent `() -> Bool` hook. Pass `PeerId` and, for filters, the complete `Message`.
- Resolve settings only through `registry.service(accountPeerId:)?.settingsSnapshot()` or `grvmSettings(accountId:accountManager:)`; never fall back to another or primary account.
- A missing account service fails closed: preserve stock Telegram behavior and do not apply another account's preferences.
- Use the existing Telegram `ItemList` and context-menu design. Do not add external UI dependencies or copied Desktop widgets.
- Read on Interact and scheduled Ghost sending are mutually exclusive in both persisted updates and effective runtime predicates.
- Do not send text to Google or Yandex unless that provider is explicitly selected. Do not use an embedded upstream API key.
- Import files are local JSON only, at most 1 MiB. Export uses the iOS share sheet; no paste service or project endpoint.
- Windows cannot compile the iOS graph. Each task begins with an executable Python source-contract test. The final localization/branding/CI plan owns the only GitHub Actions build.
- Do not push `master` or trigger an intermediate workflow from this plan.

---

## Cross-Plan Interfaces

Consume the account/storage interfaces exactly as declared there:

```swift
public func grvmSettings(
    accountId: PeerId,
    accountManager: AccountManager<TelegramAccountManagerTypes>
) -> Signal<AyuGramSettings, NoError>

public func updateGRVMSettings(
    accountId: PeerId,
    accountManager: AccountManager<TelegramAccountManagerTypes>,
    _ f: @escaping (AyuGramSettings) -> AyuGramSettings
) -> Signal<Void, NoError>

public final class GRVMMessageArchiveCoordinator {
    public let accountPeerId: PeerId
    public func settingsSnapshot() -> AyuGramSettings
    public func updateSettings(_ settings: AyuGramSettings)
}

public final class GRVMAccountFeatureRegistry {
    public func service(accountPeerId: PeerId) -> GRVMMessageArchiveCoordinator?
}
```

Produce this exact filter interface for the chat/appearance plan:

```swift
public struct AyuMessageFilter: Codable, Equatable, Identifiable {
    public var id: UUID
    public var expression: String
    public var isEnabled: Bool
    public var isReversed: Bool
    public var isCaseInsensitive: Bool
    public var peerId: Int64?
    public var excludedPeerIds: Set<Int64>

    public init(
        id: UUID = UUID(),
        expression: String,
        isEnabled: Bool = true,
        isReversed: Bool = false,
        isCaseInsensitive: Bool = true,
        peerId: Int64? = nil,
        excludedPeerIds: Set<Int64> = []
    )
}

public func ayuGramFilterEditorController(
    context: AccountContext,
    filter: AyuMessageFilter? = nil,
    initialExpression: String = "",
    initialPeerId: PeerId? = nil
) -> ViewController
```

## Exact Models and Hook Contracts

```swift
public enum GRVMGhostComponent: String, Codable, CaseIterable {
    case readReceipts
    case storyReads
    case onlineStatus
    case typingAndUploads
    case goOfflineAfterOnline
}

public enum GRVMTranslationProvider: Int32, Codable, CaseIterable {
    case telegram = 0
    case google = 1
    case yandex = 2
}
```

`GRVMGhostComponent` and `AyuMessageFilter` live in AyuGramLib. `GRVMTranslationProvider` lives in TelegramCore (`GRVMTranslationProvider.swift`) so the translation engine can use the typed provider without creating a TelegramCore -> AyuGramLib dependency cycle; `AyuGramSettings.translationProvider` remains the legacy-compatible `Int32` storage field.

`AyuGramHooks` owns these account-aware signatures after Task 1:

```swift
public static var shouldSuppressReadReceipts: ((PeerId) -> Bool)?
public static var shouldSuppressPresence: ((PeerId) -> Bool)?
public static var shouldSuppressTyping: ((PeerId) -> Bool)?
public static var shouldSuppressStoryRead: ((PeerId) -> Bool)?
public static var shouldSuppressContentRead: ((PeerId) -> Bool)?
public static var shouldSuppressUploadProgress: ((PeerId) -> Bool)?
public static var shouldForceOfflineAfterOnline: ((PeerId) -> Bool)?
public static var shouldMarkReadAfterAction: ((PeerId) -> Bool)?
public static var shouldUseScheduledMessages: ((PeerId) -> Bool)?
public static var sendWithoutSoundMode: ((PeerId) -> Int32)?
public static var isMessageHiddenByFilter: ((PeerId, Message) -> Bool)?
public static var isShadowBanned: ((PeerId, PeerId) -> Bool)?
public static var matchingMessageFilterIds: ((PeerId, Message) -> [String])?
public static var isShowingFilteredMessages: ((PeerId, PeerId) -> Bool)?
public static var setShowingFilteredMessages: ((PeerId, PeerId, Bool) -> Void)?
public static var shouldDisableExternalLinkWarning: ((PeerId) -> Bool)?
public static var shouldImproveLinkPreviews: ((PeerId) -> Bool)?
public static var translationProvider: ((PeerId) -> GRVMTranslationProvider)?
public static var shouldDisableAds: ((PeerId) -> Bool)?
public static var shouldHideStories: ((PeerId) -> Bool)?
public static var shouldDisableSimilarChannels: ((PeerId) -> Bool)?
public static var shouldDisableNotificationDelay: ((PeerId) -> Bool)?
public static var shouldFilterZalgo: ((PeerId) -> Bool)?
public static var shouldShowSeconds: ((PeerId) -> Bool)?
public static var shouldShowDialogID: ((PeerId) -> Bool)?
public static var peerIdDisplayMode: ((PeerId) -> Int32)?
public static var shouldConfirmStickers: ((PeerId) -> Bool)?
public static var shouldConfirmGIF: ((PeerId) -> Bool)?
public static var shouldConfirmVoice: ((PeerId) -> Bool)?
public static var shouldSpoofWebviewAsAndroid: ((PeerId) -> Bool)?
public static var shouldIncreaseWebviewHeight: ((PeerId) -> Bool)?
public static var shouldIncreaseWebviewWidth: ((PeerId) -> Bool)?
```

The old `shouldIncreaseWebviewSize`, text-only filter closure, zero-argument Ghost closures, and standalone upload switch are compatibility inputs only during migration and have no remaining runtime consumer after this plan.

---

## File Map

### Create

- `submodules/AyuGramLib/Sources/GRVMGhostModels.swift` - component enum and pure master-toggle/effective-policy helpers.
- `submodules/AyuGramLib/Sources/AyuMessageFilter.swift` - stable filter model and versioned backup envelope.
- `submodules/AyuGramLib/Sources/GRVMGhostSchedule.swift` - pure message-kind and delay calculation.
- `submodules/TelegramCore/Sources/GRVMTranslationProvider.swift` - dependency-safe typed provider enum.
- `submodules/AyuGramFeatures/Sources/GRVMMessageFilterEngine.swift` - compiled account snapshot and complete-message matching.
- `submodules/AyuGramFeatures/Sources/GRVMBlockedPeersRegistry.swift` - account-scoped blocked peer subscriptions.
- `submodules/AyuGramFeatures/Sources/GRVMFilteredMessageVisibility.swift` - account/chat runtime overrides.
- `submodules/AyuGramSettingsUI/Sources/AyuGramFilterEditorController.swift` - add/edit/select-chat screen.
- `submodules/TelegramCore/Sources/GRVMExternalTranslation.swift` - Google/Yandex requests and strict decoding.
- `submodules/TelegramUI/Sources/GRVMLinkPreviewRewrite.swift` - pure supported-host rewrite.
- `Tests/GRVMgramContracts/test_ghost_settings_contract.py`
- `Tests/GRVMgramContracts/test_ghost_runtime_contract.py`
- `Tests/GRVMgramContracts/test_filter_contract.py`
- `Tests/GRVMgramContracts/test_filter_ui_contract.py`
- `Tests/GRVMgramContracts/test_general_integrations_contract.py`
- `Tests/GRVMgramContracts/test_general_regressions_contract.py`

### Modify

- `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- `submodules/AyuGramLib/BUILD`
- `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- `submodules/AyuGramFeatures/BUILD`
- `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- `submodules/TelegramCore/Sources/State/AccountTaskManager.swift`
- `submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift`
- `submodules/TelegramCore/Sources/Account/Account.swift`
- `submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift`
- `submodules/TelegramCore/Sources/State/ManagedLocalInputActivities.swift`
- `submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift`
- `submodules/TelegramCore/Sources/State/ManagedSynchronizeViewStoriesOperations.swift`
- `submodules/TelegramCore/Sources/State/MessageReactions.swift`
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/Translate.swift`
- `submodules/TelegramCore/BUILD`
- `submodules/TelegramUI/Sources/ChatController.swift`
- `submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift`
- `submodules/TelegramUI/Sources/ChatHistoryEntriesForView.swift`
- `submodules/TelegramUI/Sources/ChatInterfaceStateContextQueries.swift`
- `submodules/TelegramUI/Sources/AppDelegate.swift`
- `submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/StoryContainerScreen.swift`
- `submodules/WebUI/Sources/WebAppWebView.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramFiltersController.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramShadowBanController.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift`
- `submodules/AyuGramSettingsUI/BUILD`

---

### Task 1: Add migration-safe typed settings and account-aware hook contracts

**Files:**
- Create: `submodules/AyuGramLib/Sources/GRVMGhostModels.swift`
- Create: `submodules/AyuGramLib/Sources/AyuMessageFilter.swift`
- Modify: `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- Modify: `submodules/AyuGramLib/BUILD`
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Create: `submodules/TelegramCore/Sources/GRVMTranslationProvider.swift`
- Test: `Tests/GRVMgramContracts/test_ghost_settings_contract.py`

**Settings added:**

```swift
public var ghostLockedComponents: Set<GRVMGhostComponent>
public var goOfflineAfterOnline: Bool
public var filters: [AyuMessageFilter]
public var disableExternalLinkWarning: Bool
public var increaseWebviewHeight: Bool
public var increaseWebviewWidth: Bool
```

- [ ] **Step 1: Write the failing settings contract**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "submodules/AyuGramLib/Sources/AyuGramSettings.swift"
MODELS = ROOT / "submodules/AyuGramLib/Sources/GRVMGhostModels.swift"
FILTER = ROOT / "submodules/AyuGramLib/Sources/AyuMessageFilter.swift"
HOOKS = ROOT / "submodules/TelegramCore/Sources/AyuGramHooks.swift"
PROVIDER = ROOT / "submodules/TelegramCore/Sources/GRVMTranslationProvider.swift"


class GhostSettingsContractTests(unittest.TestCase):
    def test_five_components_and_new_fields_exist(self) -> None:
        models = MODELS.read_text(encoding="utf-8")
        for case in ("readReceipts", "storyReads", "onlineStatus", "typingAndUploads", "goOfflineAfterOnline"):
            self.assertIn(f"case {case}", models)
        settings = SETTINGS.read_text(encoding="utf-8")
        for field in ("ghostLockedComponents", "goOfflineAfterOnline", "filters", "disableExternalLinkWarning", "increaseWebviewHeight", "increaseWebviewWidth"):
            self.assertIn(f"var {field}:", settings)

    def test_filter_shape_is_stable(self) -> None:
        source = FILTER.read_text(encoding="utf-8")
        for field in ("id", "expression", "isEnabled", "isReversed", "isCaseInsensitive", "peerId", "excludedPeerIds"):
            self.assertIn(f"var {field}:", source)

    def test_identity_sensitive_hooks_are_account_aware(self) -> None:
        source = HOOKS.read_text(encoding="utf-8")
        self.assertNotIn("shouldSuppressReadReceipts: (() -> Bool)", source)
        self.assertIn("shouldSuppressReadReceipts: ((PeerId) -> Bool)", source)
        self.assertIn("isMessageHiddenByFilter: ((PeerId, Message) -> Bool)", source)
        self.assertIn("shouldIncreaseWebviewHeight: ((PeerId) -> Bool)", source)
        self.assertIn("shouldIncreaseWebviewWidth: ((PeerId) -> Bool)", source)

    def test_translation_provider_lives_in_telegram_core(self) -> None:
        source = PROVIDER.read_text(encoding="utf-8")
        self.assertIn("enum GRVMTranslationProvider: Int32", source)
        self.assertIn("case telegram = 0", source)
        self.assertIn("case google = 1", source)
        self.assertIn("case yandex = 2", source)
```

- [ ] **Step 2: Run the contract and observe the expected failure**

```powershell
python -m unittest Tests.GRVMgramContracts.test_ghost_settings_contract -v
```

Expected: FAIL because the typed model files and account-aware signatures do not exist.

- [ ] **Step 3: Implement exact models, defaults, and decoding migration**

Use the interfaces from this plan verbatim. Defaults are:

```swift
ghostLockedComponents: []
goOfflineAfterOnline: false
filters: []
disableExternalLinkWarning: false
increaseWebviewHeight: true
increaseWebviewWidth: true
```

Manual `Codable` decoding performs these migrations once in memory and encodes both the canonical new values and unchanged legacy keys needed for downgrade safety:

- When `filters` is absent, map every `messageFilters` string to an enabled, non-reversed, case-insensitive global filter and every `reversedFilters` string to the same shape with `isReversed = true`; assign deterministic UUID v5-style values from kind/index/expression so decoding the same legacy payload is stable.
- When `sendWithoutSoundOption` is absent and `sendWithoutSound == true`, set the canonical mode to `2` (Always); otherwise use `0` (Never). Runtime code no longer reads `sendWithoutSound`.
- When either independent Webview key is absent, initialize it from legacy `increaseWebviewSize`; runtime code no longer reads the legacy field.
- Preserve `suppressUploadProgress` on decode/encode, but effective typing/upload state is the conjunction of Ghost master with the combined component enabled when either old typing or upload value was enabled. Future UI updates write both legacy booleans together.
- `ghostModeActiveCount` counts exactly five components; typing/upload contributes one, not two.
- `setGhostModeEnabled(_:)` changes only components absent from `ghostLockedComponents`. It updates both typing legacy fields together and does not clear locks.
- Every settings mutation normalizes `readOnAction && useScheduledMessages` by disabling the other value according to the row the user just enabled.
- Clamp `translationProvider` to `GRVMTranslationProvider.telegram/google/yandex`; legacy value `3` (Native) decodes as Telegram because no common public UIKit consumer exists for the deployment target.

- [ ] **Step 4: Replace hook declarations without wiring consumers yet**

Change only the signatures listed in **Exact Models and Hook Contracts**. Retain unrelated hook declarations for their owning plans. Import `Postbox` already provides `PeerId` and `Message`. Create `GRVMTranslationProvider.swift` in TelegramCore with the exact three cases; do not import AyuGramLib from TelegramCore.

- [ ] **Step 5: Run focused tests**

```powershell
python -m unittest Tests.GRVMgramContracts.test_ghost_settings_contract -v
```

Expected: PASS.

- [ ] **Step 6: Commit the model boundary**

```powershell
git add submodules/AyuGramLib/Sources/GRVMGhostModels.swift submodules/AyuGramLib/Sources/AyuMessageFilter.swift submodules/AyuGramLib/Sources/AyuGramSettings.swift submodules/AyuGramLib/BUILD submodules/TelegramCore/Sources/AyuGramHooks.swift submodules/TelegramCore/Sources/GRVMTranslationProvider.swift Tests/GRVMgramContracts/test_ghost_settings_contract.py
git commit -m "feat: define account scoped ghost and filter settings"
```

---

### Task 2: Wire all five Ghost components at authoritative account-aware points

**Files:**
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/TelegramCore/Sources/State/AccountTaskManager.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift`
- Modify: `submodules/TelegramCore/Sources/Account/Account.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedLocalInputActivities.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedSynchronizeViewStoriesOperations.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift`
- Test: `Tests/GRVMgramContracts/test_ghost_runtime_contract.py`

- [ ] **Step 1: Add failing source contracts for account propagation and the recursion fix**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class GhostRuntimeContractTests(unittest.TestCase):
    def source(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_suppressed_read_operation_is_consumed(self) -> None:
        source = self.source("submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift")
        self.assertIn("confirmSynchronizedIncomingReadState", source)
        self.assertNotIn("shouldSuppressReadReceipts?()", source)

    def test_presence_manager_receives_account_peer_id(self) -> None:
        source = self.source("submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift")
        self.assertIn("accountPeerId: PeerId", source)
        self.assertIn("shouldForceOfflineAfterOnline?(self.accountPeerId)", source)

    def test_typing_and_upload_share_one_effective_component(self) -> None:
        manager = self.source("submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift")
        self.assertIn("suppressTypingStatus || settings.suppressUploadProgress", manager)
        self.assertIn("service(accountPeerId: accountPeerId)", manager)

    def test_locked_components_have_a_native_disclosure_screen(self) -> None:
        ui = self.source("submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift")
        self.assertIn("ghostLockedComponents", ui)
        self.assertIn("Locked Components", ui)
```

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_ghost_runtime_contract -v
```

Expected: FAIL on zero-argument hooks, missing presence account ID, and absent lock UI.

- [ ] **Step 3: Wire effective predicates through the exact account service**

In `AyuGramFeatureManager`, install closures that resolve `registry.service(accountPeerId:)`, read one immutable `settingsSnapshot()`, and return:

```swift
readReceipts = settings.ghostModeEnabled && settings.suppressReadReceipts
storyReads = settings.ghostModeEnabled && settings.suppressStoryReads
presence = settings.ghostModeEnabled && settings.suppressOnlineStatus
typingAndUploads = settings.ghostModeEnabled
    && (settings.suppressTypingStatus || settings.suppressUploadProgress)
forceOffline = settings.ghostModeEnabled
    && settings.goOfflineAfterOnline
```

Assign `typingAndUploads` to both `shouldSuppressTyping` and `shouldSuppressUploadProgress`. Never consult a primary account for these closures.

- [ ] **Step 4: Pass account identity into every TelegramCore consumer**

- `ManagedSynchronizePeerReadStates` uses `stateManager.accountPeerId` and retains the already-proven transaction that calls `confirmSynchronizedIncomingReadState(peerId:)` before completing the operation.
- Story synchronization and content-consumption managers use `stateManager.accountPeerId`. Their existing `withTakenOperation`/operation-log removal remains intact.
- `ManagedLocalInputActivities` already receives `accountPeerId`; pass it into typing and upload hooks.
- `AccountTaskManager` and `AccountStateManager` use their existing `accountPeerId` fields.
- Extend `AccountPresenceManager.init` with `accountPeerId: PeerId`, and pass `self.peerId` from `Account.swift` at its construction site.

Do not suppress the mandatory offline packet sent while leaving the app. Suppress only attempts to advertise online state or active input.

- [ ] **Step 5: Implement automatic offline-after-online exactly once**

At the successful completion of an explicit `account.updateStatus(offline: .boolFalse)` request, when the force-offline predicate is true, cancel the pending online timer and immediately enqueue `account.updateStatus(offline: .boolTrue)`. If the online request was suppressed before transmission, do not send an extra offline packet. Serialize both decisions on `AccountPresenceManager`'s existing queue so a stale completion cannot override a newer state.

- [ ] **Step 6: Replace the six-switch Ghost UI with five components and locks**

Keep a master switch plus five component rows. The fourth row writes both `suppressTypingStatus` and `suppressUploadProgress`. Add an `ItemListDisclosureItem` titled by localization key `GRVMgram.Ghost.LockedComponents` with value `N/5`; it opens a second standard `ItemList` controller containing five lock switches. A master change calls the model helper and leaves locked component values untouched. No Shift-click gesture is introduced on iOS.

- [ ] **Step 7: Run the focused contract and full contract subset**

```powershell
python -m unittest Tests.GRVMgramContracts.test_ghost_settings_contract Tests.GRVMgramContracts.test_ghost_runtime_contract -v
```

Expected: PASS, including the `confirmSynchronizedIncomingReadState` guard.

- [ ] **Step 8: Commit Ghost component wiring**

```powershell
git add submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/TelegramCore/Sources/State/AccountTaskManager.swift submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift submodules/TelegramCore/Sources/Account/Account.swift submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift submodules/TelegramCore/Sources/State/ManagedLocalInputActivities.swift submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift submodules/TelegramCore/Sources/State/ManagedSynchronizeViewStoriesOperations.swift submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift Tests/GRVMgramContracts/test_ghost_runtime_contract.py
git commit -m "fix: complete account scoped ghost mode"
```

---

### Task 3: Correct scheduling, Read on Interact, silent send, and pre-view Story Ghost

**Files:**
- Create: `submodules/AyuGramLib/Sources/GRVMGhostSchedule.swift`
- Modify: `submodules/AyuGramLib/BUILD`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/TelegramUI/Sources/ChatController.swift`
- Modify: `submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift`
- Modify: `submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/StoryContainerScreen.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift`
- Test: `Tests/GRVMgramContracts/test_ghost_runtime_contract.py`

**Pure interface:**

```swift
public func grvmGhostScheduleDelay(
    messages: [EnqueueMessage],
    proxyEnabled: Bool
) -> Int32
```

- [ ] **Step 1: Extend the failing contract**

Add assertions that the schedule helper distinguishes `LocalFileMediaResource`, voice/instant-video, and existing media; applies `ceil(delay * 1.2)` for proxy; `ChatController` has one common read-after-action helper called from send, reaction, and poll paths; silent mode reads only `sendWithoutSoundOption`; and the story gate appears before `markAsSeen(id:)` without the old late `UndoOverlay`.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_ghost_runtime_contract -v
```

Expected: FAIL because the current send path uses a fixed/incorrect schedule and the story suggestion is shown after the view operation.

- [ ] **Step 3: Implement Desktop 6.7.8 timing as pure policy**

Classify the whole enqueue batch by its longest required delay:

- text, forward, `.message`, `.savedGif`, `.savedSticker`, and other server-existing media: `12` seconds;
- voice or instant-video message: `17` seconds;
- a newly attached `.standalone` `TelegramMediaFile` backed by `LocalFileMediaResource`: `max(19, 13 + max(6, ceil(sizeMiB * 0.7)))` seconds;
- when `proxyEnabled`, return `Int32(ceil(Double(base) * 1.2))`.

Use overflow-safe conversion of resource size and a 12-second fallback for missing metadata. Read proxy state in `ChatController` from:

```swift
accountManager.sharedData(keys: [SharedDataKeys.proxySettings])
```

with `ProxySettings.effectiveActiveServer != nil`. Replace the current scheduling branch near `ChatController.swift:8586`; do not delay non-Ghost sends.

- [ ] **Step 4: Make Read on Interact complete and mutually exclusive**

Add one private `ChatController` helper, `grvmMarkCurrentChatReadAfterAction()`, that checks `shouldMarkReadAfterAction?(context.account.peerId)`, marks the current peer/thread through the stock interactive read API, and no-ops when no peer is open. Invoke it only after:

- the enqueue operation has been accepted;
- a reaction update signal completes successfully (`ChatController.swift` reaction block around 1666/2130);
- a poll vote signal returns success (poll block around 3669/3702).

The effective predicate is:

```swift
settings.ghostModeEnabled && settings.readOnAction && !settings.useScheduledMessages
```

The schedule predicate is:

```swift
settings.ghostModeEnabled && settings.useScheduledMessages && !settings.readOnAction
```

When either settings row is enabled, update the other to false in the same `updateGRVMSettings` transform.

- [ ] **Step 5: Use the three-mode silent selector only**

At `ChatController.swift:8319`, compute `sendWithoutSound` from the account-aware `sendWithoutSoundMode`:

- `0`: Never;
- `1`: only while that account's Ghost master is enabled;
- `2`: Always.

Remove the old boolean switch from `AyuGramCoreController`; render a selector/disclosure with these three values. Legacy `sendWithoutSound` remains Codable migration data and has no consumer.

- [ ] **Step 6: Gate story viewing before the first read mutation**

Move the suggestion to the first path that would call `component.content.markAsSeen(id:)` around `StoryContainerScreen.swift:1704`. For one story-screen instance:

- if suggestion is disabled or Story Ghost is already effective, continue immediately;
- otherwise suspend the first mark operation and present `textAlertController` with `Enable Ghost Mode` and `View Normally`;
- `Enable Ghost Mode` writes the exact account setting, waits until the coordinator snapshot has received the updated value, then continues through the now-suppressed mark path;
- `View Normally` performs the original mark once;
- subsequent items on that screen do not prompt again.

Remove the late overlay around `StoryContainerScreen.swift:1082`. No read operation may occur before the choice.

- [ ] **Step 7: Verify task behavior contracts**

```powershell
python -m unittest Tests.GRVMgramContracts.test_ghost_runtime_contract -v
git diff --check
```

Expected: PASS and no whitespace errors.

- [ ] **Step 8: Commit interaction parity**

```powershell
git add submodules/AyuGramLib/Sources/GRVMGhostSchedule.swift submodules/AyuGramLib/BUILD submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/TelegramUI/Sources/ChatController.swift submodules/TelegramUI/Components/ChatControllerInteraction/Sources/ChatControllerInteraction.swift submodules/TelegramUI/Components/Stories/StoryContainerScreen/Sources/StoryContainerScreen.swift submodules/AyuGramSettingsUI/Sources/AyuGramCoreController.swift Tests/GRVMgramContracts/test_ghost_runtime_contract.py
git commit -m "feat: finish ghost send and story behavior"
```

---

### Task 4: Implement the complete message filter engine and blocked/shadow consumers

**Files:**
- Create: `submodules/AyuGramFeatures/Sources/GRVMMessageFilterEngine.swift`
- Create: `submodules/AyuGramFeatures/Sources/GRVMBlockedPeersRegistry.swift`
- Create: `submodules/AyuGramFeatures/Sources/GRVMFilteredMessageVisibility.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/AyuGramFeatures/BUILD`
- Modify: `submodules/TelegramUI/Sources/AppDelegate.swift`
- Modify: `submodules/TelegramUI/Sources/ChatHistoryEntriesForView.swift`
- Modify: `submodules/TelegramCore/Sources/Account/Account.swift`
- Modify: `submodules/TelegramCore/Sources/State/MessageReactions.swift`
- Test: `Tests/GRVMgramContracts/test_filter_contract.py`

- [ ] **Step 1: Write failing contracts for full-message input and semantics**

The Python test reads the filter engine and integration files and asserts:

- `GRVMMessageFilterEngine` compiles `NSRegularExpression` with per-filter case options;
- candidates include text, URL/TextUrl entities, reply-button title/payload, `<button>...</button>`, and `<type>N</type>` tokens;
- invalid regex compilation is skipped without `try!` or `fatalError`;
- normal and reversed policies are separate;
- `ChatHistoryEntriesForView` passes `context.account.peerId` and `message`, not only text;
- author and forwarded-author IDs are both checked;
- blocked peer state is stored by account and drains all pages;
- incoming activities and reaction lists call the account-aware shadow predicate.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_filter_contract -v
```

Expected: FAIL because the existing manager compiles only two global string arrays and the history hook receives `(Int64, String)`.

- [ ] **Step 3: Build immutable compiled snapshots**

`GRVMMessageFilterEngine` accepts one `AyuGramSettings` snapshot and the blocked ID set for the same account. Compile every enabled filter independently. `.caseInsensitive` is set only when `isCaseInsensitive`; a failed expression is retained for UI diagnostics but never matches. Rebuild the engine only when settings or blocked IDs change, then atomically replace the account engine in `AyuGramFeatureManager`.

Filter applicability is exact:

- `peerId` limits the filter to that dialog;
- `excludedPeerIds` suppresses that filter in listed dialogs;
- a global filter always applies to channel dialogs;
- it applies to private/group dialogs only when `enableFiltersInChats` is true;
- disabled filters are skipped;
- any applicable normal match hides the message;
- when one or more reversed filters are applicable, a message is visible only if at least one reversed filter matches;
- `hideFromBlockedUsers` hides messages authored or forwarded by an ID in that account's complete blocked set;
- `shadowBanIds` applies to `message.author?.id` and `message.forwardInfo?.author?.id`.

`isShowingFilteredMessages(account, chat)` bypasses the final hide decision for that chat but does not mutate filters or blocked/shadow state. `matchingMessageFilterIds` still returns matches while the override is on.

- [ ] **Step 4: Build the exact regex candidate**

Concatenate newline-delimited, non-empty values from:

- `message.text`;
- substring covered by `.Url` entities;
- URL value from `.TextUrl(url:)` entities;
- each reply markup button title;
- callback, URL, copy, switch-inline, and Webview payloads;
- synthetic `<button>title payload</button>` per button;
- one synthetic `<type>N</type>` token from the exhaustive mapping below.

Media/service type mapping:

| Message kind | N |
|---|---:|
| text, sponsored, game, invoice, webpage | 0 |
| photo | 1 |
| voice | 2 |
| video | 3 |
| location | 4 |
| instant video | 5 |
| GIF | 8 |
| file | 9 |
| generic service/date | 10 |
| action photo | 11 |
| contact | 12 |
| sticker | 13 |
| music | 14 |
| animated sticker or dice | 15 |
| call | 16 |
| poll or todo | 17 |
| premium gift | 18 |
| emoji-only | 19 |
| suggested photo | 21 |
| wallpaper action | 22 |
| story | 23 |
| story mention | 24 |
| premium gift to channel | 25 |
| giveaway | 26 |
| giveaway results | 28 |
| paid media | 29 |
| Stars or TON gift | 30 |

Prefer explicit media/action cases over text fallback. Author names are not appended to the regex candidate: author suppression is ID-based and cannot be spoofed by message text.

- [ ] **Step 5: Load the complete blocked set per active account**

For every registered active account, own a `BlockedPeersContext(account:subject: .blocked)`, subscribe to its state, and call `loadMore()` until `canLoadMore == false`. Store `Set<PeerId>` under the exact account ID, rebuild only that account's filter engine, and dispose/remove it on account unregister. AppDelegate passes lifecycle events through the existing registry ownership established by the account plan.

- [ ] **Step 6: Apply filtering to all required consumers**

- In `ChatHistoryEntriesForView.swift:151`, skip a normal history entry only when `isMessageHiddenByFilter?(context.account.peerId, message) == true` and the per-chat override is false.
- In `Account.peerInputActivities` and `allPeerInputActivities`, remove activities from shadow-banned peers using `self.peerId` as account identity.
- In `MessageReactions.swift`, pass `account.peerId` into initial and network reaction-list states and omit shadow-banned peers without changing counts on the message itself.
- Do not filter the current user's own activity or reaction row unless that exact ID was explicitly added to Shadow Ban.

- [ ] **Step 7: Run filter contracts**

```powershell
python -m unittest Tests.GRVMgramContracts.test_filter_contract -v
```

Expected: PASS.

- [ ] **Step 8: Commit the engine**

```powershell
git add submodules/AyuGramFeatures/Sources/GRVMMessageFilterEngine.swift submodules/AyuGramFeatures/Sources/GRVMBlockedPeersRegistry.swift submodules/AyuGramFeatures/Sources/GRVMFilteredMessageVisibility.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/AyuGramFeatures/BUILD submodules/TelegramUI/Sources/AppDelegate.swift submodules/TelegramUI/Sources/ChatHistoryEntriesForView.swift submodules/TelegramCore/Sources/Account/Account.swift submodules/TelegramCore/Sources/State/MessageReactions.swift Tests/GRVMgramContracts/test_filter_contract.py
git commit -m "feat: implement complete account scoped filters"
```

---

### Task 5: Finish filter management, context actions, import/export, and Show Filtered

**Files:**
- Create: `submodules/AyuGramSettingsUI/Sources/AyuGramFilterEditorController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramFiltersController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramShadowBanController.swift`
- Modify: `submodules/AyuGramSettingsUI/BUILD`
- Modify: `submodules/TelegramUI/Sources/ChatController.swift`
- Test: `Tests/GRVMgramContracts/test_filter_ui_contract.py`

- [ ] **Step 1: Write failing UI and data-flow contracts**

Assert the exact public editor factory, account-scoped settings calls, peer selection controller, 1 MiB import bound, versioned JSON envelope, `UIDocumentPickerViewController`, `UIActivityViewController`, confirmation before clear/import replacement, and context-menu calls for View Filters/Add Filter/Show Filtered/Shadow Ban.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_filter_ui_contract -v
```

Expected: FAIL because only simple string entry and global shadow-ID screens exist.

- [ ] **Step 3: Render a complete account-scoped filters screen**

`AyuGramFiltersController` reads/writes with the current `context.account.peerId`. Sections are:

1. master `enableFilters` and `enableFiltersInChats`;
2. ordered filter rows with enabled state, reversed indicator, dialog scope, and edit/delete actions;
3. Shadow Ban navigation and `hideFromBlockedUsers`;
4. Add Filter, Import, Export, and Clear.

Tapping a row opens the exact editor factory. Swipe delete removes only that UUID. Reordering persists the new array order. Empty-state copy is localized later; no hard-coded AyuGram text is added.

- [ ] **Step 4: Implement add/edit and Select Chat**

The editor owns a local draft and commits only on Done. It validates non-empty regex with `NSRegularExpression`; invalid input keeps the screen open and shows a standard alert. Rows edit expression, enabled, reversed, case insensitive, optional chat, and excluded chats. Select Chat uses:

```swift
context.sharedContext.makePeerSelectionController(
    PeerSelectionControllerParams(...)
)
```

Store only `PeerId.toInt64()` in the Codable model. Clearing the selected chat returns the filter to global scope. The public constructor uses `initialExpression` and `initialPeerId` only when `filter == nil`, with enabled/case-insensitive/non-reversed defaults.

- [ ] **Step 5: Implement versioned local import/export**

```swift
public struct AyuMessageFilterBackup: Codable, Equatable {
    public let version: Int
    public let filters: [AyuMessageFilter]
}
```

- Export version `2` to a temporary `.json` file using sorted/pretty JSON and present `UIActivityViewController`.
- Import through `UIDocumentPickerViewController(documentTypes: ["public.json"], in: .import)` with security-scoped access where required.
- Reject files larger than 1 MiB before decoding, versions other than `2`, duplicate UUIDs, empty expressions, and invalid regexes.
- Show a confirmation summary with total, enabled, reversed, and chat-scoped counts before replacing the current array.
- Clear requires a destructive confirmation and removes only `filters`, not master/shadow settings.
- Always delete the temporary export file after the share controller completes.

- [ ] **Step 6: Add message/chat context actions**

- `View Filters` appears for a selected message when `matchingMessageFilterIds` returns non-empty; it opens a standard list of only those filters.
- `Add Filter` opens the editor with selected message text and current dialog ID; saving appends the new filter.
- `Show Filtered`/`Hide Filtered` toggles the runtime account+chat override and forces a history refresh without persistence.
- `Shadow Ban`/`Unshadow Ban` edits the selected message author's ID for the current account; forwarded-author ID is offered as a distinct choice when different.
- The chat/appearance plan owns visibility mode and submenu placement for these actions; this plan owns their real behavior.

- [ ] **Step 7: Verify UI contracts**

```powershell
python -m unittest Tests.GRVMgramContracts.test_filter_contract Tests.GRVMgramContracts.test_filter_ui_contract -v
```

Expected: PASS.

- [ ] **Step 8: Commit filter UI and actions**

```powershell
git add submodules/AyuGramSettingsUI/Sources/AyuGramFilterEditorController.swift submodules/AyuGramSettingsUI/Sources/AyuGramFiltersController.swift submodules/AyuGramSettingsUI/Sources/AyuGramShadowBanController.swift submodules/AyuGramSettingsUI/BUILD submodules/TelegramUI/Sources/ChatController.swift Tests/GRVMgramContracts/test_filter_ui_contract.py
git commit -m "feat: complete filter management and chat controls"
```

---

### Task 6: Implement Telegram, Google, and Yandex translation providers

**Files:**
- Create: `submodules/TelegramCore/Sources/GRVMExternalTranslation.swift`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Messages/Translate.swift`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift`
- Modify: `submodules/TelegramCore/BUILD`
- Modify: `submodules/TranslateUI/Sources/ChatTranslation.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift`
- Test: `Tests/GRVMgramContracts/test_general_integrations_contract.py`

- [ ] **Step 1: Write failing provider contracts**

Assert exactly three enum cases, stock MTProto usage for Telegram, `URLSession` with a 15-second timeout for Google/Yandex, approved endpoint hosts, no embedded API-key literal, strict response-count validation, and no Native row in General UI.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_general_integrations_contract.GeneralTranslationContractTests -v
```

Expected: FAIL because the UI cycles four providers and the Telegram engine ignores or incompletely handles external selection.

- [ ] **Step 3: Add one provider selector to every translation path**

Extend the public engine entry point without breaking stock callers:

```swift
public func translateMessages(
    messageIds: [EngineMessage.Id],
    fromLang: String?,
    toLang: String,
    enableLocalIfPossible: Bool,
    provider: GRVMTranslationProvider = .telegram,
    tone: TranslationTone = .neutral
) -> Signal<Never, TranslationError>
```

Thread `provider` through `_internal_translateMessages` and `_internal_translateMessagesByPeerId`. At `TelegramCore/Sources/TelegramEngine/Messages/Translate.swift:158-290`, route message text, poll text/options, and audio transcription translations through that same value. Keep Telegram as the existing MTProto request, including returned entities. Google/Yandex return plain translated text with an empty entity list.

External requests:

- Google GET: `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=<target>&dt=t&q=<text>` using `URLComponents` query items.
- Yandex POST: `https://translate.yandex.net/api/v1/tr.json/translate?srv=android&id=<uuid>-0-0`, form body `lang=<target>&text=<text>` with percent encoding.

Set `URLRequest.timeoutInterval = 15.0`, require HTTP 2xx, validate JSON types and one output per input, and map timeout/HTTP/malformed/count mismatch to the existing `.generic` translation error. Never silently return the source text as a successful translation.

- [ ] **Step 4: Make provider choice account-scoped in UI and engine calls**

`AyuGramGeneralController` offers Telegram, Google, and Yandex only. It writes `translationProvider` through `updateGRVMSettings` for `context.account.peerId`. `AyuGramFeatureManager` implements `translationProvider(accountPeerId)` from the exact coordinator snapshot. In `TranslateUI/Sources/ChatTranslation.swift`, resolve it with `context.account.peerId` and pass the typed value into `context.engine.messages.translateMessages`. The network helper receives the provider as an argument and never reads mutable global state.

- [ ] **Step 5: Run translation contracts**

```powershell
python -m unittest Tests.GRVMgramContracts.test_general_integrations_contract.GeneralTranslationContractTests -v
```

Expected: PASS.

- [ ] **Step 6: Commit provider support**

```powershell
git add submodules/TelegramCore/Sources/GRVMExternalTranslation.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/Translate.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift submodules/TelegramCore/BUILD submodules/TranslateUI/Sources/ChatTranslation.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift Tests/GRVMgramContracts/test_general_integrations_contract.py
git commit -m "feat: add working translation providers"
```

---

### Task 7: Correct external-link warning and supported-domain preview rewriting

**Files:**
- Create: `submodules/TelegramUI/Sources/GRVMLinkPreviewRewrite.swift`
- Modify: `submodules/TelegramUI/Sources/ChatController.swift`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextQueries.swift`
- Modify: `submodules/TelegramUI/BUILD`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift`
- Test: `Tests/GRVMgramContracts/test_general_integrations_contract.py`

- [ ] **Step 1: Extend contracts for exact warning and host behavior**

The test asserts the warning setting default is false, concealed-link decision includes the exact account ID, only HTTP(S) URLs are rewritten, all supported host mappings exist, and original detected URLs remain in `UrlPreviewState` while only the preview request uses rewritten URLs.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_general_integrations_contract.GeneralLinkContractTests -v
```

Expected: FAIL because no warning consumer exists and current preview handling does not preserve a separate original URL list.

- [ ] **Step 3: Implement the concealed-link warning switch at the real gate**

At `ChatController.swift:9412`, use:

```swift
let effectiveSkipConcealedAlert = skipConcealedAlert
    || (AyuGramHooks.shouldDisableExternalLinkWarning?(
        context.account.peerId
    ) == true)
```

Use this only for Telegram's concealed/external-link confirmation; do not bypass unsafe-scheme rejection, login confirmation, or in-app permission prompts. Add one General switch backed by `disableExternalLinkWarning`.

- [ ] **Step 4: Add a pure URLComponents host rewrite**

Mappings are case-insensitive and preserve scheme, port, path, query, and fragment:

| Original host | Preview host |
|---|---|
| `twitter.com`, `www.twitter.com`, `x.com`, `www.x.com` | `fixupx.com` |
| `tiktok.com`, `www.tiktok.com` | `kktiktok.com` |
| any other `*.tiktok.com` | same subdomain under `kktiktok.com` |
| `reddit.com`, `www.reddit.com` | `vxreddit.com` |
| `instagram.com`, `www.instagram.com` | `kkclip.com` |
| `pixiv.net`, `www.pixiv.net` | `phixiv.net` |

Return the original string for a non-HTTP(S) scheme, parse failure, unsupported host, deceptive suffix such as `x.com.example.org`, or missing host.

- [ ] **Step 5: Rewrite only the webpage-preview request**

At `ChatInterfaceStateContextQueries.swift:559`, retain original detected URLs in `UrlPreviewState` for edit detection and UI. Build a separate rewritten array only when `shouldImproveLinkPreviews?(context.account.peerId)` is true, and pass it to `webpagePreview`. This prevents an edit loop where the composer text and remembered preview URL disagree.

- [ ] **Step 6: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_general_integrations_contract.GeneralLinkContractTests -v
git diff --check
git add submodules/TelegramUI/Sources/GRVMLinkPreviewRewrite.swift submodules/TelegramUI/Sources/ChatController.swift submodules/TelegramUI/Sources/ChatInterfaceStateContextQueries.swift submodules/TelegramUI/BUILD submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift Tests/GRVMgramContracts/test_general_integrations_contract.py
git commit -m "feat: finish link warning and preview controls"
```

Expected: tests PASS and commit succeeds.

---

### Task 8: Split Webview height/width and lock down General regressions

**Files:**
- Modify: `submodules/WebUI/Sources/WebAppWebView.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift`
- Test: `Tests/GRVMgramContracts/test_general_integrations_contract.py`
- Test: `Tests/GRVMgramContracts/test_general_regressions_contract.py`

- [ ] **Step 1: Add failing independent-dimension and inventory tests**

The Webview contract asserts separate account-aware height and width checks, width-only viewport scale, height-only `viewport_changed` logical metrics, and absence of a shared runtime `shouldIncreaseWebviewSize` gate. The regression inventory asserts concrete consumers remain for hide stories, disable ads, disable similar channels, notification delay, Zalgo filtering, message seconds, dialog IDs, sticker/GIF/voice confirmations, and Android Webview spoofing.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_general_integrations_contract Tests.GRVMgramContracts.test_general_regressions_contract -v
```

Expected: FAIL because `WebAppWebView.swift:165` currently uses one size gate and several General hooks remain process-global.

- [ ] **Step 3: Split Webview dimensions without changing the real scroll frame**

- Width enabled: keep the existing viewport-meta behavior with `initial-scale=0.85`; width disabled: preserve Telegram's stock meta/scale.
- Height enabled: retain the actual UIKit/WKWebView frame and scrolling dimensions, but report `height / 0.85` as the logical stable/expanded height through the existing `viewport_changed` event around `WebAppWebView.swift:240`.
- Height disabled: report stock metrics exactly.
- Evaluate both hooks with `account.peerId` at the WebApp construction/update boundary and retain the values in the component state; do not call mutable global settings from injected JavaScript.
- Android spoof remains an independent account-aware toggle and must not imply either dimension.

Use one named `0.85` scale constant for both dimensions, reject non-finite/non-positive input by falling back to the stock height, and leave safe-area values unchanged. Do not fake height with CSS `min-height`, which breaks nested scrolling.

- [ ] **Step 4: Convert General regression consumers to exact-account lookups where identity is available**

Keep behavior unchanged while passing account IDs at these real boundaries:

- sponsored messages: `TelegramCore/Sources/TelegramEngine/Messages/AdMessages.swift` uses `self.account.peerId`;
- hide stories and similar channels: their account/context owners pass the account peer ID;
- notification polling uses `account.peerId`; AppDelegate-only background work reads the registered primary snapshot directly because no message account is present;
- Zalgo rendering nodes use `item.context.account.peerId`;
- seconds formatter call sites use existing `accountPeerId`/chat context;
- peer ID/profile rows use `context.account.peerId`;
- sticker, GIF, and voice confirmation branches use `ChatController.context.account.peerId`;
- Webview Android spoof uses the WebApp account ID.

Do not redesign these already-working features. The test names their producer, consumer, and account source so later changes cannot leave a visible switch without behavior.

- [ ] **Step 5: Ensure General UI has only implemented rows**

The final General screen contains working rows for Translation Provider, Hide Stories, Disable External Link Warning, Disable Similar Channels, Disable Notification Delay, Filter Zalgo, Improve Link Previews, Show Message Seconds, Dialog ID mode, Spoof Webview as Android, Increase Webview Height, Increase Webview Width, and the three send confirmations. Remove the old combined size row and Native translation choice. All mutations use `updateGRVMSettings` with `context.account.peerId`.

- [ ] **Step 6: Run the complete plan-local suite**

```powershell
python -m unittest `
  Tests.GRVMgramContracts.test_ghost_settings_contract `
  Tests.GRVMgramContracts.test_ghost_runtime_contract `
  Tests.GRVMgramContracts.test_filter_contract `
  Tests.GRVMgramContracts.test_filter_ui_contract `
  Tests.GRVMgramContracts.test_general_integrations_contract `
  Tests.GRVMgramContracts.test_general_regressions_contract -v
git diff --check
```

Expected: all tests PASS; `git diff --check` has no output.

- [ ] **Step 7: Commit independent Webview controls and regression guards**

```powershell
git add submodules/WebUI/Sources/WebAppWebView.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/AyuGramSettingsUI/Sources/AyuGramGeneralController.swift Tests/GRVMgramContracts/test_general_integrations_contract.py Tests/GRVMgramContracts/test_general_regressions_contract.py
git commit -m "feat: finish general settings parity"
```

---

## Localization Handoff

The localization/branding plan supplies Russian and English values for every new row/action. This plan must reference keys, never hard-code public AyuGram copy. Required semantic keys include:

- Ghost five components, lock screen/title/count, Read on Interact, Schedule Messages, silent modes, and story prompt/actions;
- Filters list/editor fields, Select Chat, exclusions, case sensitivity, reversed mode, import/export summaries/errors, Clear, View Filters, Show/Hide Filtered, and Shadow Ban actions;
- Translation providers and external-provider privacy description;
- Disable External Link Warning, Improve Link Previews, Increase Webview Height, and Increase Webview Width.

Internal factory names such as `ayuGramFilterEditorController` stay unchanged for compatibility.

## Final Verification for This Plan

- [ ] Run all six Python modules from Task 8 with fresh output.
- [ ] Run `git diff --check`.
- [ ] Run `rg -n "shouldSuppress(ReadReceipts|Presence|Typing|StoryRead|ContentRead|UploadProgress): \(\(\) -> Bool\)|isMessageHiddenByFilter: \(\(Int64, String\)|shouldIncreaseWebviewSize" submodules -g '*.swift'` and confirm no runtime declarations/consumers remain.
- [ ] Run `rg -n "translate\.googleapis\.com|translate\.yandex\.net|api[_-]?key|AIza" submodules/TelegramCore/Sources/GRVMExternalTranslation.swift` and confirm only the two approved hosts are present and no key is embedded.
- [ ] Run `rg -n "ayugrambot|extera|dpaste|AyuGramDocs|github\.com/AyuGram"` across files changed by this plan and confirm no public endpoint/reference was introduced.
- [ ] Inspect `git status --short` and stage only files owned by completed tasks; preserve unrelated user/agent changes.
- [ ] Do not run GitHub Actions here. Hand the verified branch to the chat/appearance, standalone, and localization/CI plans.
