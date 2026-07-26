# GRVM Notify Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Выпустить production GRVM Notify: один guided setup из GRVMgram, отдельная iOS Home Screen PWA с Telegram Web Push, безопасный same-device auth handoff, точный notification click в IPA и проверенный real-device release path.

**Architecture:** Native GRVMgram хранит install-wide ownership принятой Telegram Web-сессии, строго обрабатывает `grvmgram://` и выполняет account/navigation/revoke. Отдельный pinned fork `morethanwords/tweb@e52b5d9318848ab83316cb53138358cf49d2a27f` хранит Web-сессию на устройстве, регистрирует `token_type = 10`, получает Web Push и передаёт только проверяемый click target в native приложение. Два workstream собираются независимо, а затем проходят один интеграционный release gate.

**Tech Stack:** Swift 5, Telegram-iOS/Bazel, SwiftSignalKit, AccountManager shared data, Python `unittest` source/runtime models, TypeScript, SolidJS, Vite, Vitest, Service Worker Web Push, Cloudflare Pages, GitHub Actions macOS build.

## Global Constraints

- Native repository: `C:\Users\Redmi\Desktop\1\projects\ayugrammIOS\Telegram-iOS-clean`.
- Web repository: `C:\Users\Redmi\Desktop\1\projects\ayugrammIOS\GRVM-Notify`.
- Canonical production origin: `https://grvm-notify.pages.dev`; не менять после первого device enrollment.
- Minimum Web Push OS: iOS/iPadOS 16.4; PWA устанавливается пользователем через Home Screen.
- Happy path не содержит QR, Telegram password, copy/paste и account chooser.
- Ровно один logged-in Telegram Web account на установленную PWA.
- Local passcode OFF: plain full preview только после фактического device proof.
- Local passcode ON: fully closed PWA показывает generic/no-preview fallback; `push_key` не переносится в plaintext Service Worker storage.
- Никакого GRVM backend/session storage; Telegram auth key, push payload и переписка остаются в PWA.
- Native-only GRVM filters, Shadow Ban и foreground dedupe не синхронизируются в v1.
- Stock `tg://login`, `tgfork` и обычное upstream multi-account поведение вне GRVM Notify mode сохраняются.
- Не логировать login token, полный auth URL, subscription keys/endpoints, account IDs, raw/decrypted push или message body.
- Все production изменения начинаются с RED test/model, затем minimal implementation и GREEN.
- Параллельные implementers не выполняют `git add`, `commit`, `push`, workflow dispatch или deploy; эти операции выполняет только root после review.
- Существующие dirty user changes сохраняются; запрещены reset/checkout/delete для их очистки.

## Workstream ownership

- **Native workstream:** Tasks 1–3; production Swift files и native integration.
- **Web workstream:** Tasks 4–6; отдельный `GRVM-Notify` repository.
- **Contract/release workstream:** Task 7; Python contracts, docs, cross-repo checks и release preparation.
- **Root integration:** Task 8; review, commits, public push/deploy, GitHub workflow и failure loop.

Native и Web workstreams можно выполнять параллельно. Task 7 сначала пишет RED contracts в отдельных test/doc files и не редактирует production files Tasks 1–6. Task 8 начинается только после их независимых review.

---

### Task 1: Native state, strict deep-link contract and scheme registration

**Files:**

- Modify: `submodules/TelegramUIPreferences/Sources/PostboxKeys.swift`
- Create: `submodules/AyuGramLib/Sources/GRVMNotifyState.swift`
- Create: `submodules/TelegramUI/Sources/GRVMNotifyDeepLink.swift`
- Modify: `Telegram/Telegram-iOS/Info.plist`
- Modify: `Telegram/Telegram-iOS/InfoBazel.plist`
- Modify: `Telegram/BUILD`
- Test: `Tests/GRVMgramContracts/test_grvm_notify_native_contract.py`

**Interfaces:**

- Produces `ApplicationSpecificSharedDataKeys.grvmNotifyState` at numeric key `25`.
- Produces `GRVMNotifyState`, protocol `GRVMNotifyStateStoring` and concrete `GRVMNotifyStateStore`.
- Produces `GRVMNotifyDeepLink.parse(_:) -> GRVMNotifyDeepLink?` with `.authorize` and `.openMessage` cases.
- Preserves existing `tgfork`; adds `grvmgram` as an additional scheme.

- [ ] **Step 1: Write RED state/parser contracts**

Add executable Python models plus source assertions. The behavioral tests must include these exact cases:

```python
def test_state_requires_pair_and_expires_pending_after_24_hours():
    assert normalize_state({"pairedUserId": 7, "sessionHash": None}) == empty_state()
    assert pending_is_valid(started_at=1_000, now=1_000 + 86_399)
    assert not pending_is_valid(started_at=1_000, now=1_000 + 86_400)

def test_authorize_rejects_duplicates_bad_origin_and_oversized_token():
    assert parse_url("grvmgram://notify-auth?token=AQID&token=BAUG&return_url=https%3A%2F%2Fgrvm-notify.pages.dev%2Fsetup%2F") is None
    assert parse_url("grvmgram://notify-auth?token=AQID&return_url=https%3A%2F%2Fevil.example%2F") is None
    assert parse_url("grvmgram://notify-auth?token=" + "A" * 4097 + "&return_url=https%3A%2F%2Fgrvm-notify.pages.dev%2Fsetup%2F") is None

def test_open_message_requires_one_peer_kind_and_int32_message():
    assert parse_url("grvmgram://notify-open?account_user_id=7&peer_type=user&peer_id=8&message_id=9") is not None
    assert parse_url("grvmgram://notify-open?account_user_id=7&peer_type=user&peer_type=group&peer_id=8&message_id=9") is None
    assert parse_url("grvmgram://notify-open?account_user_id=7&peer_type=user&peer_id=8&message_id=2147483648") is None
```

The source assertions must fail until key `25`, `GRVMNotifyState.swift`, `GRVMNotifyDeepLink.swift` and both plist scheme entries exist.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
python -m unittest Tests.GRVMgramContracts.test_grvm_notify_native_contract -v
```

Expected: failures naming missing key/file/scheme/parser contract; no unrelated suite is run.

- [ ] **Step 3: Add key 25 and the install-wide state store**

Add `case grvmNotifyState = 25` without renumbering keys `0...24`. Implement a Postbox-safe Data envelope and normalize invalid pairs:

```swift
public struct GRVMNotifyState: Codable, Equatable {
    public var pairedUserId: Int64?
    public var sessionHash: Int64?
    public var pendingAccountUserId: Int64?
    public var pendingStartedAt: Int32?

    public static let empty = GRVMNotifyState(
        pairedUserId: nil,
        sessionHash: nil,
        pendingAccountUserId: nil,
        pendingStartedAt: nil
    )

    public func normalized(now: Int32) -> GRVMNotifyState
    public func hasValidPending(now: Int32) -> Bool
}

public protocol GRVMNotifyStateStoring: AnyObject {
    func state() -> Signal<GRVMNotifyState, NoError>
    func update(_ f: @escaping (GRVMNotifyState) -> GRVMNotifyState) -> Signal<GRVMNotifyState, NoError>
    func writeAndVerify(_ state: GRVMNotifyState) -> Signal<Bool, NoError>
}

public final class GRVMNotifyStateStore: GRVMNotifyStateStoring {
    public init(accountManager: AccountManager<TelegramAccountManagerTypes>)
}
```

`pairedUserId/sessionHash` are both nil or both positive/nonzero. Pending expires at `startedAt + 86_400`. `GRVMNotifyStateStore.writeAndVerify` performs an update transaction, then reads the shared entry once and returns whether the normalized stored value equals the requested normalized state.

- [ ] **Step 4: Implement the strict URL parser**

Use explicit query-item cardinality checks; never use “first value wins”. The Swift interface is:

```swift
enum GRVMNotifyPeer: Equatable {
    case user(Int64)
    case group(Int64)
    case channel(Int64)
}

enum GRVMNotifyDeepLink: Equatable {
    case authorize(token: Data, returnURL: URL)
    case openMessage(accountUserId: Int64, peer: GRVMNotifyPeer, messageId: Int32, threadId: Int64?)

    static func parse(_ url: URL) -> GRVMNotifyDeepLink?
}
```

Rules: exact scheme `grvmgram`; exact hosts `notify-auth`/`notify-open`; decoded auth token `1...512` bytes; encoded field at most `4096` characters; exact return scheme/host/port `https://grvm-notify.pages.dev`; return path `/setup/`; positive safe integers; message ID fits `Int32`; optional positive `thread_id`; unknown or duplicate fields reject the whole URL.

- [ ] **Step 5: Register the additional scheme**

Add `grvmgram` to the compatibility scheme arrays in `Info.plist`, `InfoBazel.plist` and the `UrlTypesInfoPlist` fragment in `Telegram/BUILD`. Preserve `$(APP_SPECIFIC_URL_SCHEME)`, `tgfork`, `telegram`, `tg`, `ton` and `tonsite` exactly.

- [ ] **Step 6: Run focused GREEN and source whitespace check**

Run:

```powershell
python -m unittest Tests.GRVMgramContracts.test_grvm_notify_native_contract -v
git diff --check -- submodules/TelegramUIPreferences/Sources/PostboxKeys.swift submodules/AyuGramLib/Sources/GRVMNotifyState.swift submodules/TelegramUI/Sources/GRVMNotifyDeepLink.swift Telegram/Telegram-iOS/Info.plist Telegram/Telegram-iOS/InfoBazel.plist Telegram/BUILD Tests/GRVMgramContracts/test_grvm_notify_native_contract.py
```

Expected: focused tests PASS; diff-check exit `0` apart from repository line-ending warnings.

- [ ] **Step 7: Root review and checkpoint commit**

Root reviews only Task 1 files, checks no credential material was added, then commits:

```powershell
git add -- submodules/TelegramUIPreferences/Sources/PostboxKeys.swift submodules/AyuGramLib/Sources/GRVMNotifyState.swift submodules/TelegramUI/Sources/GRVMNotifyDeepLink.swift Telegram/Telegram-iOS/Info.plist Telegram/Telegram-iOS/InfoBazel.plist Telegram/BUILD Tests/GRVMgramContracts/test_grvm_notify_native_contract.py
git commit -m "feat: add GRVM Notify native state and links"
```

---

### Task 2: Native auth coordinator, readiness gates and exact navigation

**Files:**

- Create: `submodules/TelegramUI/Sources/GRVMNotifyCoordinator.swift`
- Create: `submodules/TelegramCore/Sources/TelegramEngine/Privacy/GRVMNotifySessionReconciliation.swift`
- Modify: `submodules/TelegramUI/Sources/AppDelegate.swift`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Privacy/TelegramEnginePrivacy.swift`
- Test: `Tests/GRVMgramContracts/test_grvm_notify_native_contract.py`

**Interfaces:**

- Consumes `GRVMNotifyState`, `GRVMNotifyDeepLink`, `approveAuthTransferToken`, `SharedAccountContext.activeAccountContexts` and `AppLockContext.isCurrentlyLocked`.
- Produces a single AppDelegate-lifetime `GRVMNotifyCoordinator` with `enqueue(url:) -> Bool`.
- Produces error-preserving `TelegramEngine.Privacy.grvmNotifySessionHashesOnce() -> Signal<Set<Int64>, GRVMNotifySessionFetchError>`.
- Produces an AppDelegate navigation closure that always supplies `alwaysKeepMessageId: true`.

- [ ] **Step 1: Extend RED contracts with lifecycle models**

Add a deterministic Python coordinator model and assertions for:

```python
def test_locked_cold_start_waits_then_revalidates_owner():
    model = CoordinatorModel(ready=False, locked=True, pending_user_id=7)
    model.enqueue(authorize(user_id=7))
    assert model.presented == []
    model.ready = True
    model.locked = False
    model.active_user_ids = []
    model.drain()
    assert model.error == "account-unavailable"

def test_new_request_cancels_old_request_and_logout_does_not_retarget():
    model = CoordinatorModel(ready=False, locked=False, pending_user_id=7)
    model.enqueue(open_message(account_user_id=7, message_id=1))
    model.enqueue(open_message(account_user_id=7, message_id=2))
    model.logout(7)
    model.ready = True
    model.drain()
    assert model.navigated == []
```

Source assertions must require: cold launch allowlist contains `grvmgram`; every UIKit URL entry calls the same enqueue helper; readiness/unlock filters exist; public Telegram ID is compared to `context.account.peerId.id._internalGetInt64Value()`; no `AccountRecordId(rawValue: accountUserId)`; navigation sets `alwaysKeepMessageId: true`.

- [ ] **Step 2: Run focused test and confirm the new RED failures**

Run the same focused unittest command from Task 1. Expected: only new coordinator/reconciliation assertions fail.

- [ ] **Step 3: Implement one coordinator and dependency boundary**

Use one `MetaDisposable` per pending auth/navigation operation. The initializer receives concrete closures instead of reaching for a global AppDelegate:

```swift
final class GRVMNotifyCoordinator {
    struct Environment {
        let stateStore: GRVMNotifyStateStoring
        let activeAccounts: Signal<(primary: AccountContext?, accounts: [(AccountRecordId, AccountContext, Int32)], currentAuth: UnauthorizedAccount?), NoError>
        let authorizedContext: () -> Signal<AuthorizedApplicationContext, NoError>
        let isLocked: Signal<Bool, NoError>
        let present: (ViewController) -> Void
        let navigate: (AccountRecordId, PeerId, Int64?, MessageId) -> Void
        let openReturnURL: (URL) -> Void
    }

    init(environment: Environment)
    @discardableResult func enqueue(url: URL) -> Bool
}
```

All `grvmgram` URLs return `true` from `enqueue`, including malformed URLs. Malformed input shows at most one localized error after UI readiness and is never forwarded into stock URL routing.

- [ ] **Step 4: Wire foreground and killed-app URL admission**

In `launchOptions[.url]`, add exact handling for both `URL` and `String` forms with scheme `grvmgram`, calling `enqueueGRVMNotifyURL`. In all four foreground UIKit callbacks, call the same helper before `openUrl(url:)`:

```swift
private func enqueueGRVMNotifyURL(_ url: URL) -> Bool {
    guard url.scheme?.lowercased() == "grvmgram" else { return false }
    _ = self.grvmNotifyCoordinator.enqueue(url: url)
    return true
}
```

Do not send malformed `grvmgram` URLs to `context.openUrl` or `UIApplication.shared.open`.

- [ ] **Step 5: Implement auth readiness, exact account and persistence flow**

For `.authorize`:

1. wait for an authorized root context with `context.isReady.get() == true`;
2. wait for `isCurrentlyLocked == false`;
3. read normalized state and require a non-expired pending user;
4. resolve exactly one active `AccountContext` by public CloudUser ID;
5. present one confirmation naming that account;
6. call `approveAuthTransferToken` with an `ActiveSessionsContext` for the exact account;
7. call `stateStore.writeAndVerify` before displaying success;
8. on false read-back, call exact `remove(hash:)` and keep native state unpaired;
9. attempt the allowlisted HTTPS return; show the Home Screen fallback instruction if automatic return is not observed.

Never log the token, URL or query fields. `.invalid`, `.expired`, `.alreadyAccepted`, `.generic`, account unavailable and expired pending each receive distinct RU/EN localization keys defined in Task 3.

- [ ] **Step 6: Implement exact navigation and bounded missing-peer behavior**

Map `GRVMNotifyPeer` to `Namespaces.Peer.CloudUser`, `.CloudGroup` or `.CloudChannel`, and construct a Cloud `MessageId`. Before navigation, subscribe for at most 5 seconds to local `EngineData.Item.Peer.Peer`; this is a wait for existing synchronization, not a network fetch. On timeout show `Чат ещё не синхронизирован`.

The AppDelegate closure switches to `accountId`, waits the matching `AuthorizedApplicationContext`, root readiness and unlock, rechecks ownership, then calls:

```swift
context.openChatWithPeerId(
    peerId: peerId,
    threadId: verifiedThreadId,
    messageId: messageId,
    storyId: nil,
    alwaysKeepMessageId: true
)
```

Pass `threadId` only from positive `custom.thread_id`; otherwise use parent forum/chat fallback. A new URL, logout, account removal or coordinator deinit disposes the wait.

- [ ] **Step 7: Add error-preserving session reconciliation**

Implement a one-shot wrapper over `account.getAuthorizations()` that does not use `retryRequestIfNotFrozen` and does not convert `nil`/network failure to an empty set:

```swift
public enum GRVMNotifySessionFetchError: Error {
    case network
}

public func grvmNotifySessionHashesOnce() -> Signal<Set<Int64>, GRVMNotifySessionFetchError>
```

Only a real server response maps to hashes. Native ownership can be cleared after exact `terminateAnotherSession(id:)` completion or a successful one-shot response that lacks the hash.

- [ ] **Step 8: Run focused GREEN and scoped diff check**

Run:

```powershell
python -m unittest Tests.GRVMgramContracts.test_grvm_notify_native_contract -v
git diff --check -- submodules/TelegramUI/Sources/GRVMNotifyCoordinator.swift submodules/TelegramCore/Sources/TelegramEngine/Privacy/GRVMNotifySessionReconciliation.swift submodules/TelegramUI/Sources/AppDelegate.swift submodules/TelegramCore/Sources/TelegramEngine/Privacy/TelegramEnginePrivacy.swift Tests/GRVMgramContracts/test_grvm_notify_native_contract.py
```

Expected: focused tests PASS and no whitespace errors.

- [ ] **Step 9: Root review and checkpoint commit**

Review cold/foreground routing, unlock waits, cancellation and account ownership. Root commits Task 2 files with:

```powershell
git commit -m "feat: coordinate GRVM Notify auth and navigation"
```

---

### Task 3: Native settings, one-flow onboarding, revoke and localization

**Files:**

- Create: `submodules/TelegramUI/Sources/GRVMNotifySettingsController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramMainController.swift`
- Modify: `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoScreenSettingsActions.swift`
- Modify: `submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift`
- Modify: `Telegram/Telegram-iOS/en.lproj/GRVMgram.strings`
- Modify: `Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings`
- Test: `Tests/GRVMgramContracts/test_grvm_notify_native_contract.py`

**Interfaces:**

- Adds `ayuGramMainController(context:openGRVMNotify:)` while preserving a default closure for source compatibility.
- Produces `grvmNotifySettingsController(context:) -> ViewController` in `TelegramUI`.
- Uses only the state/store and engine surfaces from Tasks 1–2; `AyuGramSettingsUI` does not import `TelegramUI`.

- [ ] **Step 1: Add RED UI/localization contracts**

Require a stable `Уведомления`/`Notifications` row in GRVMgram main settings and assert that the source contains these states/actions:

```text
unsupportedOS
notConnected
webSessionConnected
connectedToMissingAccount
disconnecting
statusNotVerified
startSetup
continueSetup
openDevices
disconnect
```

The test must assert that native copy says `Web-сессия подключена`, not `Уведомления работают`, because native cannot observe PWA permission/subscription.

- [ ] **Step 2: Run focused test and confirm RED**

Run the Task 1 focused command. Expected: main-row/controller/string assertions fail.

- [ ] **Step 3: Add the callback-driven main row**

Add `.categoryNotifications` with a new stable ID after existing IDs. Extend arguments with `openGRVMNotify: () -> Void`. Keep this signature compatible:

```swift
public func ayuGramMainController(
    context: AccountContext,
    openGRVMNotify: @escaping () -> Void = {}
) -> ViewController
```

In `PeerInfoScreenSettingsActions.swift`, pass a closure that pushes `grvmNotifySettingsController(context: self.context)`. This keeps module dependencies acyclic.

- [ ] **Step 4: Implement the minimal native management screen**

Render state from `GRVMNotifyStateStore(accountManager: context.sharedContext.accountManager).state()` and `activeAccountContexts`:

- iOS below 16.4: explanation only;
- no pair: one `Настроить` action;
- accepted session: `Web-сессия подключена`, owner account and `Продолжить настройку`;
- owner missing: orphaned warning and manual Devices instructions;
- disconnect in flight: non-destructive progress state;
- reconciliation timeout/error: `Статус не проверен`, ownership retained.

`Настроить` stores current public user ID and timestamp before calling a force-external Safari open for `https://grvm-notify.pages.dev/setup/?grvm_notify=1`. Do not show a pre-Safari alert that adds a tap.

- [ ] **Step 5: Implement exact Devices and disconnect actions**

Resolve the saved owner through active contexts. `Открыть устройства` uses the exact target context and `makeRecentSessionsController`. `Отключить` calls `terminateAnotherSession(id:)`; clear state only on completion. On `.generic`, timeout or missing account keep ownership. On screen entry, run `grvmNotifySessionHashesOnce`; only a successful response without the hash reconciles a manual external revoke.

- [ ] **Step 6: Add complete RU/EN copy**

Add typed `GRVMgramStringKey` entries for title, row, install instructions, session-connected disclaimer, start/continue, confirmation, pending expiry, invalid/expired/already-accepted/generic auth errors, account missing, chat unsynchronized, open PWA fallback, open Devices, disconnect, disconnect failure, orphaned session and status-not-verified. Every key exists once in both `.strings` files; no hardcoded Russian/English remains in Swift.

- [ ] **Step 7: Run focused GREEN and localization validation**

Run:

```powershell
python -m unittest Tests.GRVMgramContracts.test_grvm_notify_native_contract -v
python -m unittest Tests.GRVMgramContracts.test_grvmgram_localization_resources_contract -v
git diff --check -- submodules/TelegramUI/Sources/GRVMNotifySettingsController.swift submodules/AyuGramSettingsUI/Sources/AyuGramMainController.swift submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoScreenSettingsActions.swift submodules/TelegramPresentationData/Sources/GRVMgramStrings.swift Telegram/Telegram-iOS/en.lproj/GRVMgram.strings Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings Tests/GRVMgramContracts/test_grvm_notify_native_contract.py
```

Expected: both focused suites PASS.

- [ ] **Step 8: Root review and checkpoint commit**

Root checks click budget, truthful status, exact owner revoke and module direction, then commits:

```powershell
git commit -m "feat: add GRVM Notify native setup"
```

---

### Task 4: Bootstrap pinned tweb and implement the one-button auth setup

**Files:**

- Create repository: `C:\Users\Redmi\Desktop\1\projects\ayugrammIOS\GRVM-Notify`
- Modify: `.gitattributes`
- Modify: `package.json`
- Modify: `src/scripts/generate_changelog.js`
- Create: `src/lib/grvmNotify/mode.ts`
- Create: `src/lib/grvmNotify/authLink.ts`
- Create: `src/lib/grvmNotify/setupState.ts`
- Create: `src/lib/grvmNotify/*.test.ts`
- Create: `src/components/grvmNotify/GRVMNotifySetup.tsx`
- Modify: `src/pages/bootstrapIm.ts`
- Modify: `src/pages/cards/SignQRCard.tsx`

**Interfaces:**

- Pinned base must remain exactly `e52b5d9318848ab83316cb53138358cf49d2a27f`.
- Produces `isGRVMNotifyMode`, `isStandalonePWA`, `buildAuthorizationDeepLink` and a tested setup state reducer.
- Exposes the current rotating login token to the GRVM setup component without duplicating MTProto/DC migrate logic.

- [ ] **Step 1: Create the pinned LF checkout**

Run from `C:\Users\Redmi\Desktop\1\projects\ayugrammIOS`:

```powershell
git -c core.autocrlf=false clone https://github.com/morethanwords/tweb.git GRVM-Notify
git -C GRVM-Notify checkout e52b5d9318848ab83316cb53138358cf49d2a27f
git -C GRVM-Notify switch -c codex/grvm-notify-production
git -C GRVM-Notify rev-parse HEAD
```

Expected SHA: `e52b5d9318848ab83316cb53138358cf49d2a27f`. If the target directory already exists, verify its resolved path and branch; do not delete it automatically.

- [ ] **Step 2: Pin the Windows-capable toolchain and prove baseline**

Use Node `^22.18 || >=24.11` and `pnpm@11.16.0`. Add LF rules for `*.js`, `*.ts`, `*.tsx`, `*.json`, `*.md`, `*.css`. Change changelog version parsing to `const version = match[1].trim();`.

Run:

```powershell
corepack prepare pnpm@11.16.0 --activate
pnpm install --frozen-lockfile
pnpm run build
```

Expected: the previous `en_0.8.6\r.md` failure is absent. Record baseline build duration; do not copy upstream `public/` as a release artifact.

- [ ] **Step 3: Write RED mode/auth/state tests**

Tests must cover:

```typescript
expect(isGRVMNotifyMode(new URL('https://grvm-notify.pages.dev/setup/?grvm_notify=1'))).toBe(true);
expect(buildAuthorizationDeepLink(new Uint8Array([1, 2, 3]))).toBe(
  'grvmgram://notify-auth?token=AQID&return_url=https%3A%2F%2Fgrvm-notify.pages.dev%2Fsetup%2F'
);
expect(reduceSetup('idle', {type: 'permission-denied'})).toBe('permission-denied');
expect(reduceSetup('authorizing', {type: 'registration-failed'})).toBe('registration-error');
```

Also prove that notification permission is requested only inside the `activate` click handler and that a denied prompt never calls the login-token flow.

- [ ] **Step 4: Run focused Vitest and confirm RED**

Run:

```powershell
pnpm exec vitest run src/lib/grvmNotify
```

Expected: missing module/component failures.

- [ ] **Step 5: Implement mode, deep link and reducer**

`buildAuthorizationDeepLink` base64url-encodes raw bytes without padding and includes only `token` plus the fixed allowlisted return URL. It never includes an account ID because Safari/standalone storage transfer is not trusted.

The reducer states are:

```typescript
export type GRVMNotifySetupState =
  | 'install-required'
  | 'idle'
  | 'requesting-permission'
  | 'permission-denied'
  | 'authorizing'
  | 'registration-pending'
  | 'ready-full-preview'
  | 'ready-private'
  | 'multi-account-blocked'
  | 'registration-error';
```

- [ ] **Step 6: Reuse the existing rotating login-token flow**

Refactor `SignQRCard` only enough to expose a copied `Uint8Array` token callback while preserving existing `auth.exportLoginToken`, DC migrate and `auth.loginTokenSuccess` polling. GRVM mode does not require the user to scan the QR. Automatic custom-scheme navigation is attempted once per token generation; if iOS blocks it, render one `Продолжить в GRVMgram` button using the latest token.

- [ ] **Step 7: Mount the one-button setup surface**

At the end of the existing app bootstrap, mount `GRVMNotifySetup` above normal UI when `isGRVMNotifyMode()` is true. Before installation it shows only Add-to-Home-Screen instructions. In standalone mode it shows one `Активировать` button; that click requests permission, then starts auth. After readiness it becomes a management surface with actual push state, passcode/privacy mode, retry, open GRVMgram and disconnect. Hide account-add controls in GRVM mode.

- [ ] **Step 8: Run focused GREEN, typecheck and build**

Run:

```powershell
pnpm exec vitest run src/lib/grvmNotify
pnpm run build
git diff --check
```

Expected: tests and build PASS; generated Service Worker remains at root.

- [ ] **Step 9: Root review and web checkpoint commit**

Root checks no credential values or auth tokens entered the diff, then commits in `GRVM-Notify`:

```powershell
git add -- .gitattributes package.json src/scripts/generate_changelog.js src/lib/grvmNotify src/components/grvmNotify src/pages
git commit -m "feat: add GRVM Notify setup flow"
```

---

### Task 5: Make Web Push registration race-safe and privacy-safe

**Files:**

- Modify: `src/lib/uiNotificationsManager.ts`
- Modify: `src/lib/appManagers/pushSingleManager.ts`
- Modify: `src/lib/webPushApiManager.ts`
- Modify: `src/lib/serviceWorker/push.ts`
- Create: `src/lib/grvmNotify/pushPolicy.ts`
- Create: `src/lib/grvmNotify/pushPolicy.test.ts`
- Create: `src/lib/grvmNotify/serviceWorkerFallback.test.ts`
- Create: `src/lib/appManagers/pushSingleManager.grvmNotify.test.ts`
- Create: `src/lib/uiNotificationsManager.grvmNotify.test.ts`
- Create: `src/lib/serviceWorker/push.grvmNotify.test.ts`

**Interfaces:**

- Produces `UiNotificationsManager.registerGRVMNotifyPush(): Promise<void>`.
- Produces one serialized GRVM registration policy with account generation tracking.
- Commits `registeredDevice` only after server acknowledgement and final generation revalidation.
- Produces an explicit staged disconnect result; preserves ordinary upstream behavior outside GRVM mode.

- [ ] **Step 1: Write RED registration race/retry tests**

Use fake account managers and deferred promises to prove:

```typescript
it('rejects before settings.push and subscription creation when two accounts exist', async () => {
  const env = fakePushEnvironment({accounts: [account(1), account(2)]});
  await expect(env.registerGRVMNotifyPush()).rejects.toThrow('grvm_notify_requires_exactly_one_web_account');
  expect(env.settingsWrites).toEqual([]);
  expect(env.subscriptionRequests).toBe(0);
});

it('rolls back when account generation changes during registerDevice', async () => {
  const env = fakePushEnvironment({accounts: [account(1)]});
  const pending = env.beginRegistration();
  env.login(account(2));
  env.resolveRegisterAcknowledgement();
  await expect(pending).rejects.toThrow('grvm_notify_account_set_changed');
  expect(env.unregisterCalls).toEqual([1]);
  expect(env.registeredDevice).toBeUndefined();
});

it('retries the same token after a rejected server call', async () => {
  const env = fakePushEnvironment({accounts: [account(1)], failFirstRegister: true});
  await expect(env.register()).rejects.toBeDefined();
  await expect(env.register()).resolves.toBe(true);
  expect(env.registerCalls).toBe(2);
});
```

Add equivalent unregister tests: no local clear before acknowledgement, failed unregister retains retry material, logout is not called after unregister failure.

- [ ] **Step 2: Write RED cold-worker and logging tests**

Mock a cold IndexedDB getter whose cached value is initially unavailable. The push handler must await `get('push_keys_ids_base64')` and call `showNotification` with generic title/body on storage/parse/decrypt failure. Spy on all modified log functions and assert they never receive token data, endpoint, `p256dh`, `auth`, user IDs, raw payload, decrypted body or a full `grvmgram://notify-auth` URL.

- [ ] **Step 3: Run focused Vitest and confirm RED**

Run:

```powershell
pnpm exec vitest run src/lib/grvmNotify/pushPolicy.test.ts src/lib/grvmNotify/serviceWorkerFallback.test.ts
```

Expected: generation, retry, staged unregister, cold fallback and redaction tests fail against pinned upstream.

- [ ] **Step 4: Centralize push-condition application**

Refactor `UiNotificationsManager.onPushConditionsChange` into one awaited implementation:

```typescript
private async applyPushConditions(options: {grvmSingleAccount: boolean}): Promise<void>

public async registerGRVMNotifyPush(): Promise<void> {
  await this.applyPushConditions({grvmSingleAccount: true});
}
```

The Solid effect wrapper catches only a sanitized error category. In GRVM mode the effect also passes `grvmSingleAccount: true`; it cannot race an unguarded automatic route after `settings.push = true`.

- [ ] **Step 5: Add mutex, account generation and final revalidation**

All GRVM registration, `registerAgain`, `account_logged_in`, logout/account-set notifications and unregister operations execute through one promise mutex. Each account-set mutation increments `accountsGeneration`. A registration captures `{generation, accountNumber, userId}`, revalidates before the RPC and after acknowledgement, and rolls back the captured account registration if either revalidation fails.

The preflight occurs before mutating `settings.push`, requesting a subscription or assigning `registeredDevice`. `other_uids` is always an array:

```typescript
const userIds = loggedInAccounts.map(account => account.userId);
const tokenData = {
  token_type: 10,
  token: tokenValue,
  app_sandbox: false,
  secret,
  other_uids: userIds
};
```

- [ ] **Step 6: Fix acknowledged state and retry semantics**

For register, keep a local candidate until every `account.registerDevice` succeeds and generation still matches; only then assign `registeredDevice`. On failure, leave the old committed state unchanged. For unregister, keep token/account material until every server unregister succeeds; on failure expose `unregister-failed` and allow the same operation to retry.

Implement disconnect stages exactly:

```typescript
type DisconnectStage =
  | 'ready'
  | 'unregistering'
  | 'server-unregistered'
  | 'logging-out'
  | 'disconnected'
  | 'unregister-failed'
  | 'logout-failed';
```

Never call logout/local cleanup from `unregister-failed`.

- [ ] **Step 7: Fix the cold encrypted fallback**

Replace synchronous `getCached` use in the encrypted push path with awaited storage loading. Catch storage, base64, JSON and decrypt failures and route all of them to one generic object that produces `GRVM Notify` / `Новое сообщение` (localized browser notification text where supported) without sender/body/IDs. Do not store the decryption key in unencrypted SW data.

- [ ] **Step 8: Redact all touched push/auth logs**

Keep only non-sensitive metadata such as `{tokenType, accountCount, override, outcomeCategory}`. Remove raw payload and notification-body logs from both page and Service Worker paths. Do not interpolate full Error objects when they can contain request data; map them to fixed categories.

- [ ] **Step 9: Run GREEN tests, complete Web tests and build**

Run:

```powershell
pnpm exec vitest run src/lib/grvmNotify
pnpm run build
git diff --check
```

Expected: all GRVM tests and production build PASS.

- [ ] **Step 10: Root review and web checkpoint commit**

Root reviews entry-point coverage and generation rollback, then commits in `GRVM-Notify`:

```powershell
git commit -m "fix: harden GRVM Notify Web Push"
```

---

### Task 6: Exact click bridge, production packaging, branding and Cloudflare artifact

**Files:**

- Create: `src/lib/grvmNotify/notificationTarget.ts`
- Create: `src/lib/grvmNotify/notificationTarget.test.ts`
- Create: `src/components/grvmNotify/GRVMNotifyLanding.tsx`
- Modify: `src/lib/serviceWorker/push.ts`
- Modify: `public/site.webmanifest`
- Modify: `public/site_apple.webmanifest`
- Modify: `src/config/notifications.ts`
- Create: `public/icons/grvm-notify-192.png`
- Create: `public/icons/grvm-notify-512.png`
- Create: `public/icons/grvm-notify-badge.png`
- Modify: `vite.config.ts`
- Modify: `package.json`
- Create: `scripts/build-grvm-notify.mjs`
- Create: `scripts/build-grvm-notify.test.ts`
- Create: `public/_headers`
- Create: `public/_redirects`
- Create/Modify: `README.md`, `LICENSE`, `NOTICE.md`

**Interfaces:**

- Produces `targetFromPush(data, accounts) -> NotificationTarget | undefined`.
- Produces fragment-only `buildLandingURL(target)` and strict custom-scheme `buildNativeOpenURL(target)`.
- Produces clean `release/` suitable for direct Cloudflare Pages upload.

- [ ] **Step 1: Write RED target and fragment tests**

Cover user/group/channel, mapping fallback and disagreement:

```typescript
const accounts = {1: 10};
expect(targetFromPush({accountNumber: 1, custom: {from_id: '20', msg_id: '30'}}, accounts)).toEqual({
  accountUserId: 10, peerType: 'user', peerId: 20, messageId: 30
});
expect(targetFromPush({user_id: 99, accountNumber: 1, custom: {from_id: '20', msg_id: '30'}}, accounts)).toBeUndefined();
expect(buildLandingURL({accountUserId: 10, peerType: 'user', peerId: 20, messageId: 30}).search).toBe('');
expect(buildLandingURL({accountUserId: 10, peerType: 'user', peerId: 20, messageId: 30}).hash).toContain('account_user_id=10');
```

Reject missing/non-positive/unsafe IDs, multiple peer kinds and message IDs outside `Int32`. Accept optional positive `custom.thread_id`; do not infer topic metadata from other fields.

- [ ] **Step 2: Write RED release-artifact tests**

The build test must fail if `release/` contains `.map`, stale root bundles, test/raw source files, a non-root Service Worker, missing manifest/icons, missing `_headers`/`_redirects`, or an HTML-referenced asset not present in the allowlisted staging tree.

- [ ] **Step 3: Run focused RED tests**

Run:

```powershell
pnpm exec vitest run src/lib/grvmNotify/notificationTarget.test.ts scripts/build-grvm-notify.test.ts
```

- [ ] **Step 4: Implement exact notification click routing**

Resolve account ID from positive payload `user_id` or `push_accounts[accountNumber]`; reject disagreement. Service Worker opens `/open/#<URLSearchParams>` so account/chat/message IDs never enter hosting request logs or referrer. The landing page parses only the fragment, attempts `grvmgram://notify-open`, and always renders a visible `Открыть в GRVMgram` fallback button. Generic/passcode-closed notifications without IDs open PWA root.

- [ ] **Step 5: Apply GRVM branding without changing message privacy**

Use existing GRVMgram-owned app icon artwork from the native repository as the source; copy/export only required PWA sizes and record the source path in `NOTICE.md`. Set PWA name/short name to `GRVM Notify`, fixed `start_url` to `/setup/?grvm_notify=1`, standalone display and GRVM notification icon/badge. Do not synthesize sender/title/body when Telegram privacy settings removed them.

- [ ] **Step 6: Build a clean release staging script**

Set production `sourcemap: false` and add pinned dev dependency `wrangler@4.26.0`. `scripts/build-grvm-notify.mjs` resolves `repoRoot = path.resolve(import.meta.dirname, '..')` and `releaseRoot = path.join(repoRoot, 'release')`, verifies `path.dirname(releaseRoot) === repoRoot`, then removes only `releaseRoot` and copies:

- `index.html`;
- the current root `sw-*.js`;
- assets referenced by current HTML/build manifest plus their runtime dependencies;
- manifest, icons and required runtime locales/fonts;
- `_headers`, `_redirects`, `LICENSE`, `NOTICE.md` and README/source link.

Never copy all 4,000+ upstream `public/` files. Reject any `.map` or previous hashed root bundle not referenced by the current build.

- [ ] **Step 7: Add exact Cloudflare routing and baseline headers**

`_redirects` contains:

```text
/setup/* /index.html 200
/open/* /index.html 200
```

`_headers` contains `nosniff`, `no-referrer`, `DENY`, a restricted Permissions Policy and the tested CSP baseline:

```text
default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; media-src 'self' blob: https:; font-src 'self' data: https:; connect-src 'self' https: wss:; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; object-src 'none'
```

If a required pinned-tweb runtime request is blocked, add only its evidenced directive/source and extend the artifact test; do not disable CSP wholesale.

- [ ] **Step 8: Add GPL source handoff**

`README.md` documents upstream commit, build commands, one-account rule, passcode behavior, setup clicks, disconnect and source URL `https://github.com/shakke66/GRVM-Notify`. Keep GPL-3.0-only license and add modified-source notices. The release artifact links to the full repository and build scripts.

- [ ] **Step 9: Run full Web gate and inspect the artifact**

Run:

```powershell
pnpm exec vitest run src/lib/grvmNotify scripts/build-grvm-notify.test.ts
pnpm run build
node scripts/build-grvm-notify.mjs
Get-ChildItem -Recurse -File release | Where-Object { $_.Extension -eq '.map' }
git diff --check
```

Expected: tests/build PASS; final PowerShell command prints nothing; `release/index.html`, one current root Service Worker, `_headers` and `_redirects` exist.

- [ ] **Step 10: Root review and web checkpoint commit**

Root visually inspects the setup/landing pages locally, verifies source handoff and commits:

```powershell
git commit -m "feat: package GRVM Notify production PWA"
```

---

### Task 7: Cross-workstream contracts and targeted QA documents

**Files:**

- Create: `Tests/GRVMgramContracts/test_grvm_notify_release_contract.py`
- Create: `docs/grvm-notify-device-qa.md`
- Modify: `docs/grvmgram-third-build-qa-checklist.md`
- Modify: `docs/ui-testing.md`

**Interfaces:**

- Does not edit production files from Tasks 1–6.
- Verifies the native/web URL schema, privacy claims, build workflow and targeted QA scope.
- Produces the exact manual device journal used after IPA/PWA deployment.

- [ ] **Step 1: Write cross-workstream RED contracts**

The Python test reads native Swift and, when the sibling Web checkout exists, Web TypeScript. It asserts exact shared literals and rejects unsafe alternatives:

```python
for token in ["grvmgram", "notify-auth", "notify-open", "account_user_id", "peer_type", "peer_id", "message_id"]:
    self.assertIn(token, native_sources)
    self.assertIn(token, web_sources)
self.assertNotIn("AccountRecordId(rawValue: accountUserId)", native_sources)
self.assertNotIn("getCached('push_keys_ids_base64')", web_sources)
self.assertIn("other_uids: userIds", web_sources)
```

When the sibling checkout is absent in native-only CI, Web assertions skip with one explicit reason; native assertions always run.

- [ ] **Step 2: Add release-workflow source assertions**

Require `.github/workflows/build.yml` to remain manually dispatchable, upload `GRVMgram-ipa`, run `ValidateGRVMgram.py ipa`, and upload `build-log` on failure. Do not add Web secrets or Cloudflare tokens to the native repository.

- [ ] **Step 3: Create the notification device journal**

`docs/grvm-notify-device-qa.md` contains blank Status/Observation fields for exactly these rows:

1. Add to Home Screen and click count.
2. Permission denied/recovery.
3. Same-device auth and session in Devices.
4. Single-account block under login churn.
5. Passcode OFF closed plain preview.
6. Passcode ON closed generic fallback.
7. Live unlocked decrypt.
8. Foreground/background/killed-IPA click.
9. Exact user/group/channel/message and forum fallback.
10. Missing peer/malformed payload safety.
11. Register/unregister network retry.
12. PWA/native/Devices revoke.
13. Removed native account/orphaned ownership.
14. Relaunch/account switch/seven-day Sideloadly re-sign.

Do not pre-fill device results.

- [ ] **Step 4: Extend only the affected third-build checklist**

Add native regression cards only for: `grvmgram` cold/foreground routing, locked readiness, settings row/localization, exact account/message navigation, session revoke/orphaned state. Do not duplicate unrelated existing 23 cards or the 14-row notification journal.

- [ ] **Step 5: Run focused release contracts**

Run:

```powershell
python -m unittest Tests.GRVMgramContracts.test_grvm_notify_native_contract Tests.GRVMgramContracts.test_grvm_notify_release_contract -v
git diff --check -- Tests/GRVMgramContracts/test_grvm_notify_release_contract.py docs/grvm-notify-device-qa.md docs/grvmgram-third-build-qa-checklist.md docs/ui-testing.md
```

- [ ] **Step 6: Root review and checkpoint commit**

Root confirms no fake PASS status and commits:

```powershell
git commit -m "test: add GRVM Notify release contracts"
```

---

### Task 8: Integrate, publish, build, monitor and repair until green

**Files:**

- All reviewed native dirty files intentionally belonging to the GRVMgram full-parity worktree
- All reviewed Web repository files from Tasks 4–6
- GitHub Actions run and downloaded artifacts under a local non-repository artifact directory

**Interfaces:**

- Consumes green Tasks 1–7 and independent reviews.
- Produces pushed native branch, public GPL Web source, deployed fixed-origin PWA, successful GitHub macOS IPA run and validated IPA artifact.

- [ ] **Step 1: Run independent two-stage reviews**

For each workstream, first review spec compliance, then code quality/race/privacy behavior. Any finding returns to its implementer; rerun only the affected focused tests. Do not start the full gate until Critical/Important findings are zero.

- [ ] **Step 2: Run one native full local gate**

Run exactly once after all native changes integrate:

```powershell
python -m unittest discover -s Tests/GRVMgramContracts -p "test_*.py" -v
python -m unittest discover -s Tests/GRVMgramValidation -p "test_*.py" -v
python build-system/Make/ValidateGRVMgram.py source
git diff --check
```

If it fails, use systematic debugging: isolate the first root cause, add/adjust the focused reproducer, fix, rerun the focused test, then rerun the full gate once after the batch is green.

- [ ] **Step 3: Run one Web full local gate and local HTTP smoke**

Run:

```powershell
pnpm exec vitest run
pnpm run build
node scripts/build-grvm-notify.mjs
pnpm exec vite preview --host 127.0.0.1 --port 4173
```

Smoke `/setup/?grvm_notify=1`, `/open/#account_user_id=10&peer_type=user&peer_id=20&message_id=30`, manifest and root Service Worker in the in-app browser; verify no console CSP errors on the setup path and capture one screenshot for the release review.

- [ ] **Step 4: Audit both publish trees for secrets and unintended files**

Inspect every status path and staged diff. Search tracked/staged text for private keys, bearer tokens, cookies, `.env.local`, provisioning profiles, P12 and real API hash values. Report only file/type if found; never print secret values. Exclude build output, node_modules, device logs and personal screenshots containing PII.

- [ ] **Step 5: Commit the complete native worktree intentionally**

After reviewing the full `git status --short`, stage only the intended full-parity/native notification/docs changes. Existing user-authored docs named in the worktree are preserved and included only if their diff belongs to the requested release. Commit logical remaining groups, then confirm a clean intended index. Do not squash away the design commit `bec20e72`.

- [ ] **Step 6: Publish the Web source and deploy the fixed origin**

Verify `gh auth status`, create/push `https://github.com/shakke66/GRVM-Notify` as public GPL source if absent, and push the reviewed branch. Deploy the clean `release/` directory:

```powershell
pnpm exec wrangler pages project create grvm-notify --production-branch main
pnpm exec wrangler pages deploy release --project-name grvm-notify --branch main
```

If the project already exists, skip only the create command. Verify `https://grvm-notify.pages.dev/setup/?grvm_notify=1`, manifest, Service Worker response and headers. If the canonical project name is unavailable, stop before any device enrollment and request a new fixed origin rather than silently changing it.

- [ ] **Step 7: Push native branch and dispatch the macOS IPA workflow**

Run:

```powershell
git push -u origin codex/grvmgram-full-parity
gh workflow run build.yml --ref codex/grvmgram-full-parity
gh run list --workflow build.yml --branch codex/grvmgram-full-parity --event workflow_dispatch --limit 1 --json databaseId,status,headSha,url
```

Record run ID and head SHA. They must match the pushed notification/full-parity commit.

- [ ] **Step 8: Monitor the run continuously**

Create concrete variables and start the watcher:

```powershell
$runId = [int](gh run list --workflow build.yml --branch codex/grvmgram-full-parity --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch $runId --exit-status
```

Keep user updates under 60 seconds while the watcher runs. On success, inspect job summary and artifact list; do not infer success from a queued/completed status without conclusion `success`.

- [ ] **Step 9: Failure repair loop**

For every failed run:

```powershell
$artifactDir = 'C:\Users\Redmi\Desktop\1\projects\ayugrammIOS\artifacts\grvm-notify'
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
gh run view $runId --log-failed
gh run download $runId -n build-log -D $artifactDir
```

Identify the first causal compile/validation/package error, reproduce with the narrowest available local contract/source check, add a regression assertion, fix minimally, rerun the affected focused suite and required source validation, commit, push, dispatch a new run and watch it. Continue until a run for the latest head SHA concludes `success`. Do not rerun an unchanged failure without a reason.

- [ ] **Step 10: Download and validate the successful IPA**

Download outside the repository:

```powershell
$successfulRunId = $runId
$artifactDir = 'C:\Users\Redmi\Desktop\1\projects\ayugrammIOS\artifacts\grvm-notify'
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
gh run download $successfulRunId -n GRVMgram-ipa -D $artifactDir
python build-system/Make/ValidateGRVMgram.py ipa "$artifactDir\GRVMgram.ipa"
```

Record SHA-256, file size, workflow URL, run ID and source commit. The CI artifact is compile/package proof; install it through Sideloadly for physical-device QA because committed fake signing is not Apple-trusted Ad Hoc signing.

- [ ] **Step 11: Execute targeted physical-device QA**

With the user’s connected iPhone/iPad, install the downloaded IPA via Sideloadly, install `GRVM Notify` from the fixed origin and fill only `docs/grvm-notify-device-qa.md` plus the affected third-build cards. If device access is unavailable in-session, deliver the validated IPA and exact blank journal without inventing results.

- [ ] **Step 12: Final verification and handoff**

Before declaring completion, verify latest GitHub conclusion, artifact validation, deployed origin headers/source link, clean intended git state and honest device statuses. Report remaining platform constraints: separate Home Screen icon, required iOS Add/Allow taps, generic passcode-closed fallback and local GRVM filters not synchronized.

## Execution sequence

1. Start Native Tasks 1–3, Web Tasks 4–6 and Contract Task 7 in three parallel ultra workstreams.
2. Native Tasks are sequential within their workstream; Web Tasks are sequential within theirs.
3. Root reviews each completed task before the next task consumes its interface.
4. Task 8 begins after both repositories pass focused gates and independent review.
5. GitHub failure loops continue until the latest pushed SHA has a successful IPA run or an external credential/platform condition makes progress impossible.
