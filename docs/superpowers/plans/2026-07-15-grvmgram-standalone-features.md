# GRVMgram Standalone Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the remaining applicable iOS parity features that do not belong to message lifecycle, Ghost/filters/general, or chat/appearance ownership: Send as Sticker, numeric peer lookup and IDs, local profile dates, media controls, precise timestamps, rounded stickers, channel-author badges, capture privacy, adaptive Saved Music color, local crash export/reset, explicit read/delete/navigation actions, and locally preserved consumable-media replay/copy.

**Architecture:** Reuse Telegram's existing conversion, picker, Postbox, engine search/read/delete, gallery, formatting, sticker, notification, enqueue, and media-resource primitives. Pure identity parsing/formatting lives in AyuGramLib. Account-sensitive policy is resolved with an explicit account peer ID. UIKit additions stay narrow; durable media operations extend the account archive coordinator and use stock viewers/uploaders rather than parallel implementations.

**Tech Stack:** Swift, UIKit, Photos/LegacyMediaPickerUI, Postbox, TelegramEngine, TelegramCore, SwiftSignalKit, AsyncDisplayKit, MediaBox, Python 3.12 `unittest` source-contract tests, Bazel/rules_apple in final macOS CI.

## Global Constraints

- Execute after `2026-07-15-grvmgram-account-storage-media.md` and Task 1 of `2026-07-15-grvmgram-ghost-filters-general.md`, which provide account settings, the account registry, and account-aware hook conventions.
- Coordinate with `2026-07-15-grvmgram-chat-appearance-parity.md`: that plan owns context-menu visibility/mode and profile layout policy; this plan owns numeric ID formatting/lookup and the concrete standalone consumers listed here.
- Preserve internal AyuGram symbols and old Codable keys. Public labels are GRVMgram and receive RU/EN values in the localization/branding plan.
- Add no third-party image, palette, WebP, privacy, or search dependency.
- Do not contact resolver bots or external APIs for peer lookup, registration dates, artwork, badges, or verification.
- Do not claim to prevent iOS screenshots. Streamer privacy covers recording, AirPlay, and screen sharing while `UIScreen.main.isCaptured` is true.
- Do not use private APIs or the secure-text-field screenshot hack.
- Rounded stickers affect picker/list presentation only, matching Desktop. They do not round sticker message bubbles.
- Preserve stock Telegram verified/fake/scam indicators, official-session flags, top notification banners, seeking, PiP restrictions for GIFs, and existing send-confirmation behavior.
- Windows cannot compile the iOS graph. Every task starts with a Python source-contract test; final macOS compilation/signing belongs to the localization/branding/CI plan.
- Do not trigger GitHub Actions or push `master` from this plan.

---

## Cross-Plan Interfaces

Consume account settings and runtime state through:

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
    public func settingsSnapshot() -> AyuGramSettings
}

public final class GRVMAccountFeatureRegistry {
    public func service(accountPeerId: PeerId) -> GRVMMessageArchiveCoordinator?
    public func primaryService() -> GRVMMessageArchiveCoordinator?
}
```

This plan adds two account settings:

```swift
public var streamerModeEnabled: Bool       // default false
public var adaptiveCoverColor: Bool        // default true
```

and these exact pure/public interfaces:

```swift
public enum GRVMNumericPeerLookup {
    public static func candidates(for query: String) -> [PeerId]
}

public enum GRVMPeerIdFormat {
    case telegram
    case botAPI
}

public func grvmFormatPeerId(
    _ peerId: PeerId,
    format: GRVMPeerIdFormat
) -> String
```

The General plan provides these exact account-aware display hooks, which this plan consumes:

```swift
public static var shouldShowDialogID: ((PeerId) -> Bool)?
public static var peerIdDisplayMode: ((PeerId) -> Int32)?
public static var shouldShowSeconds: ((PeerId) -> Bool)?
```

```swift
public extension TelegramEngine.Contacts {
    func localPeers(
        ids: [PeerId]
    ) -> Signal<[EngineRenderedPeer], NoError>
}
```

```swift
public final class GRVMScreenCapturePrivacyController {
    public init(
        window: UIWindow,
        enabled: Signal<Bool, NoError>
    )

    public func dispose()
}
```

---

## Ownership Matrix

| Feature | Producer | Authoritative consumer | Verification |
|---|---|---|---|
| Send as Sticker | media picker More menu | existing `enqueueStickerImage` | static-image eligibility and WebP reuse contract |
| Numeric peer lookup | local parser | chat-list search/Postbox | grammar, no network, dedupe contract |
| Copy ID | common formatter | profile/context actions | namespace format matrix |
| Profile dates | existing peer/cached data | profile items | local-data-only contract |
| GIF controls | existing setting/policy | universal video gallery | animated gate regression |
| Voice/round seeking | stock player state | message/gallery scrubbers | source regression only |
| Reaction seconds | message reaction timestamp | reaction list menu | reaction seconds formatter contract |
| Service time | message timestamp | action bubble | account-scoped pill contract |
| Top notifications | stock notification controller | top overlay | regression only |
| Rounded stickers | fixed Desktop radius | picker/list image layers | mode-isolation contract |
| Channel-author badge | message author/channel type | bubble author header | separate-node contract |
| Streamer privacy | account setting + capture state | app window cover | lifecycle/privacy contract |
| Adaptive cover | account setting + local artwork | Saved Music header | cache/stale-result contract |
| Official badges | Telegram server/session flags | stock UI | forbidden custom-source contract |
| Crash export/reset | account setting + local files | Other/AppDelegate | local-only and confirmation contract |
| Delete Own/Read variants | selected account/dialog/topic | chat menus/Postbox/stock read | exact-route contract |
| Callback/Jump | selected button/history bounds | context/chat menus | payload/navigation contract |
| Burn/replay/forward | local cache/archive availability | gallery/enqueue | resource and permission contract |

---

## File Map

### Create

- `submodules/AyuGramLib/Sources/GRVMPeerId.swift` - numeric grammar and Telegram/Bot API formatting.
- `submodules/TelegramCore/Sources/GRVMReadReceiptBypass.swift` - expiring exact-read override tokens.
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/GRVMReadActions.swift` - local/forced peer read policy.
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteOwnMessages.swift` - author/topic-scoped server deletion.
- `submodules/TelegramCore/Sources/SyncCore/GRVMPreservedConsumableMediaAttribute.swift` - durable replay marker.
- `submodules/TelegramUI/Sources/GRVMLocalCrashExport.swift` - bounded app-log staging and session marker.
- `submodules/TelegramUI/Sources/GRVMScreenCapturePrivacyController.swift` - capture observer and opaque cover.
- `submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift` - verified local media to standalone upload.
- `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/GRVMSavedMusicColor.swift` - local artwork extraction, normalization, and cache.
- `Tests/GRVMgramContracts/test_send_as_sticker_contract.py`
- `Tests/GRVMgramContracts/test_peer_identity_contract.py`
- `Tests/GRVMgramContracts/test_media_controls_contract.py`
- `Tests/GRVMgramContracts/test_timestamp_notification_contract.py`
- `Tests/GRVMgramContracts/test_sticker_badge_contract.py`
- `Tests/GRVMgramContracts/test_streamer_privacy_contract.py`
- `Tests/GRVMgramContracts/test_saved_music_contract.py`
- `Tests/GRVMgramContracts/test_crash_reset_contract.py`
- `Tests/GRVMgramContracts/test_peer_message_actions_contract.py`
- `Tests/GRVMgramContracts/test_preserved_media_actions_contract.py`
- `Tests/GRVMgramContracts/test_standalone_release_gate.py`

### Modify

- `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- `submodules/AyuGramLib/BUILD`
- `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- `submodules/TelegramCore/Sources/TelegramEngine/Contacts/TelegramEngineContacts.swift`
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift`
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/ApplyMaxReadIndexInteractively.swift`
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/ReplyThreadHistory.swift`
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift`
- `submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift`
- `submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift`
- `submodules/TelegramCore/Sources/State/SynchronizeConsumeMessageContentsOperation.swift`
- `submodules/TelegramCore/Sources/State/ManagedAutoremoveMessageOperations.swift`
- `submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift`
- `submodules/TelegramCore/Sources/SyncCore/SyncCore_SynchronizeConsumeMessageContentsOperation.swift`
- `submodules/TelegramCore/Sources/Account/AccountManager.swift`
- `submodules/AccountContext/Sources/AccountContext.swift`
- `submodules/MediaPickerUI/Sources/MediaPickerScreen.swift`
- `submodules/TelegramUI/Sources/ChatControllerOpenAttachmentMenu.swift`
- `submodules/TelegramUI/Sources/ChatController.swift`
- `submodules/TelegramUI/Sources/Chat/ChatControllerPaste.swift`
- `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- `submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift`
- `submodules/TelegramUI/Sources/ChatControllerScrollToPointInHistory.swift`
- `submodules/TelegramUI/Sources/OpenChatMessage.swift`
- `submodules/TelegramUI/Sources/AccountContext.swift`
- `submodules/ChatListUI/Sources/ChatListSearchListPaneNode.swift`
- `submodules/ChatListUI/BUILD`
- `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift`
- `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift`
- `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/BUILD`
- `submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift`
- `submodules/TelegramStringFormatting/Sources/DateFormat.swift`
- `submodules/TelegramStringFormatting/Sources/PresenceStrings.swift`
- `submodules/Components/ReactionListContextMenuContent/Sources/ReactionListContextMenuContent.swift`
- `submodules/TelegramUI/Components/Chat/ChatMessageActionBubbleContentNode/Sources/ChatMessageActionBubbleContentNode.swift`
- `submodules/TelegramUI/Components/Chat/ChatMessageItemView/Sources/ChatMessageItemView.swift`
- `submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift`
- `submodules/GalleryData/Sources/GalleryData.swift`
- `submodules/GalleryUI/Sources/SecretMediaPreviewController.swift`
- `submodules/StickerPackPreviewUI/Sources/StickerPackPreviewGridItem.swift`
- `submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiPagerContentComponent.swift`
- `submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiKeyboardItemLayer.swift`
- `submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift`
- `submodules/TelegramUI/Sources/AppDelegate.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift`

---

### Task 1: Add Send as Sticker to the media picker without a new converter

**Files:**
- Modify: `submodules/MediaPickerUI/Sources/MediaPickerScreen.swift`
- Modify: `submodules/TelegramUI/Sources/ChatControllerOpenAttachmentMenu.swift`
- Modify: `submodules/TelegramUI/Sources/Chat/ChatControllerPaste.swift`
- Test: `Tests/GRVMgramContracts/test_send_as_sticker_contract.py`

**Picker bridge:**

```swift
public var sendAsSticker: ((UIImage) -> Void)?
```

on `MediaPickerScreenImpl`, assigned by the owning `ChatController`.

- [ ] **Step 1: Write the failing source contract**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PICKER = ROOT / "submodules/MediaPickerUI/Sources/MediaPickerScreen.swift"
ATTACH = ROOT / "submodules/TelegramUI/Sources/ChatControllerOpenAttachmentMenu.swift"
PASTE = ROOT / "submodules/TelegramUI/Sources/Chat/ChatControllerPaste.swift"


class SendAsStickerContractTests(unittest.TestCase):
    def test_reuses_existing_sticker_pipeline(self) -> None:
        paste = PASTE.read_text(encoding="utf-8")
        self.assertIn("func enqueueStickerImage(_ image: UIImage, isMemoji: Bool)", paste)
        self.assertIn("convertToWebP", paste)

    def test_picker_only_offers_one_static_image(self) -> None:
        source = PICKER.read_text(encoding="utf-8")
        for token in ("sendAsSticker", "selectedItems.count == 1", "imageSignalForItem", "imageForAsset"):
            self.assertIn(token, source)
        self.assertIn("paidMedia", source)
        self.assertIn("spoiler", source)

    def test_chat_wires_picker_to_enqueue_sticker(self) -> None:
        source = ATTACH.read_text(encoding="utf-8")
        self.assertIn("sendAsSticker", source)
        self.assertIn("enqueueStickerImage", source)
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_send_as_sticker_contract -v
```

Expected: FAIL because the picker has no Send as Sticker bridge/action.

- [ ] **Step 3: Add the narrowly eligible More-menu action**

At the existing More menu around `MediaPickerScreen.swift:3035`, add the action only when all are true:

- exactly one selected item;
- it is a static image, not a video, GIF/live-photo-as-video, or animated result;
- paid media is off;
- spoiler is off;
- `sendAsSticker != nil`.

Do not alter the normal photo/file actions. The action uses the localization key supplied by the final plan.

- [ ] **Step 4: Resolve the edited full-resolution image**

First subscribe once to:

```swift
TGMediaEditingContext.imageSignalForItem(selectedItem, withUpdates: false)
```

If no edited image is produced and the item is `TGMediaAsset`, fall back to:

```swift
TGMediaAssetImageSignals.imageForAsset(
    asset,
    imageType: .fullSize,
    size: CGSize.zero
)
```

Perform image delivery on the main queue, dismiss the picker, and invoke `sendAsSticker(image)`. On extraction failure, keep the picker open and present the standard localized generic error. Never fall back to sending a normal photo.

- [ ] **Step 5: Reuse ChatController's proven WebP path**

In `ChatControllerOpenAttachmentMenu.swift:1333` and every equivalent gallery construction branch, assign the bridge to call:

```swift
self?.enqueueStickerImage(image, isMemoji: false)
```

Do not copy `convertToWebP`, create an extra temporary-file pipeline, or add a WebP package. Preserve existing paid-message confirmation rules that `enqueueStickerImage` already enters.

- [ ] **Step 6: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_send_as_sticker_contract -v
git diff --check
git add submodules/MediaPickerUI/Sources/MediaPickerScreen.swift submodules/TelegramUI/Sources/ChatControllerOpenAttachmentMenu.swift submodules/TelegramUI/Sources/Chat/ChatControllerPaste.swift Tests/GRVMgramContracts/test_send_as_sticker_contract.py
git commit -m "feat: send selected photos as stickers"
```

Expected: PASS and no whitespace errors.

---

### Task 2: Add numeric local lookup, common ID formatting, and locally known profile dates

**Files:**
- Create: `submodules/AyuGramLib/Sources/GRVMPeerId.swift`
- Modify: `submodules/AyuGramLib/BUILD`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Contacts/TelegramEngineContacts.swift`
- Modify: `submodules/ChatListUI/Sources/ChatListSearchListPaneNode.swift`
- Modify: `submodules/ChatListUI/BUILD`
- Modify: `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift`
- Modify: `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/BUILD`
- Test: `Tests/GRVMgramContracts/test_peer_identity_contract.py`

- [ ] **Step 1: Write executable parser truth-table tests and source contracts**

The Python module includes a mirror truth table for the Swift grammar and source assertions for the exact interfaces. Cases:

| Query | Candidates |
|---|---|
| `12345` | user 12345 |
| `id:12345` or `id 12345` | user, legacy group, channel 12345 |
| `-10012345` | channel 12345 |
| `-12345` | legacy group 12345 |
| `1234` | none unless explicitly prefixed |
| `0`, overflow, decimal, sign-only, mixed text | none |

Also assert `TelegramEngine.Contacts.localPeers(ids:)` contains no resolver username, network request, bot ID, or `resolvePeerByName` call; search results dedupe by peer ID; and profile dates reference only `creationDate`/`invitedOn`.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_peer_identity_contract -v
```

Expected: FAIL because the parser/engine API are absent and profile uses a private formatter.

- [ ] **Step 3: Implement overflow-safe namespace grammar**

Trim surrounding whitespace, lowercase only the optional `id` prefix, and parse ASCII decimal digits into `Int64` with overflow rejection. Construct `PeerId` values with Telegram's namespace constants:

- plain positive, at least five digits: `.CloudUser` only;
- explicit positive: `.CloudUser`, `.CloudGroup`, `.CloudChannel` in that order;
- `-100` prefix with a non-zero remainder: `.CloudChannel` only;
- any other negative non-zero number: `.CloudGroup` using the absolute raw ID;
- zero, extra separators/text, and an ID that cannot fit `PeerId.Id`: empty.

Deduplicate candidates while preserving order.

- [ ] **Step 4: Add common Telegram/Bot API formatting**

`grvmFormatPeerId` returns:

| Namespace | `.telegram` | `.botAPI` |
|---|---|---|
| user | raw numeric ID | raw numeric ID |
| legacy group | raw numeric ID | `-<raw>` |
| channel/megagroup | raw numeric ID | `-100<raw>` |

Replace private `ayuFormatPeerId` in `PeerInfoProfileItems.swift:26` and use the common formatter for every Copy ID action. Evaluate `shouldShowDialogID?(context.account.peerId)` and `peerIdDisplayMode?(context.account.peerId)`; target peer identity is never used as the settings account. The account-aware display mode chooses hidden/Telegram/Bot API presentation. A tap copies the displayed format; the row's existing long-press/context action offers both explicit formats regardless of current display mode.

- [ ] **Step 5: Read candidate peers from Postbox only**

Implement `TelegramEngine.Contacts.localPeers(ids:)` as one `postbox.transaction`, retrieving locally stored peers/cached data for each ID and returning renderable peers in input order. Missing peers are omitted. No network fallback is scheduled.

At `ChatListSearchListPaneNode.swift:2195-2364`, parse the current query, request local peers, prepend them to `foundLocalPeers`, and dedupe the combined list by `peerId`. Guard the async result with the current query token so stale numeric results do not enter a newer search. Existing row selection already opens the peer/profile and remains authoritative.

Add `//submodules/AyuGramLib:AyuGramLib` plus `import AyuGramLib` to `ChatListUI` and `PeerInfoScreen`; these are one-way UI -> library dependencies. Do not move the parser into TelegramCore or add a TelegramCore -> AyuGramLib dependency.

- [ ] **Step 6: Add only dates Telegram stores locally**

In profile items:

- `TelegramGroup.creationDate > 0`: show Created;
- `TelegramChannel`/megagroup with `CachedChannelData.invitedOn > 0`: show Joined;
- otherwise a channel with `creationDate > 0`: show Created;
- user/account peers and zero timestamps: no row.

Format through `stringForFullDate` with current presentation data. Do not infer a date from peer ID, message history, membership state, or a bot. Use localized Created/Joined labels supplied by the final plan.

- [ ] **Step 7: Run identity contracts and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_peer_identity_contract -v
git diff --check
git add submodules/AyuGramLib/Sources/GRVMPeerId.swift submodules/AyuGramLib/BUILD submodules/TelegramCore/Sources/TelegramEngine/Contacts/TelegramEngineContacts.swift submodules/ChatListUI/Sources/ChatListSearchListPaneNode.swift submodules/ChatListUI/BUILD submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/BUILD Tests/GRVMgramContracts/test_peer_identity_contract.py
git commit -m "feat: add local peer lookup ids and profile dates"
```

Expected: PASS.

---

### Task 3: Restore GIF controls and protect existing media seeking

**Files:**
- Modify: `submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift`
- Test: `Tests/GRVMgramContracts/test_media_controls_contract.py`

- [ ] **Step 1: Write a failing gate/regression contract**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GALLERY = ROOT / "submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift"


class MediaControlsContractTests(unittest.TestCase):
    def test_gif_controls_are_not_suppressed_by_animation(self) -> None:
        source = GALLERY.read_text(encoding="utf-8")
        self.assertNotIn("if isAnimated || disablePlayerControls", source)
        self.assertGreaterEqual(source.count("if disablePlayerControls"), 2)
        self.assertIn("!isAnimated", source)  # PiP remains unavailable for GIF.

    def test_seek_sources_remain_present(self) -> None:
        paths = {
            "submodules/TelegramUI/Components/Chat/ChatMessageInteractiveFileNode/Sources/ChatMessageInteractiveFileNode.swift": "seek",
            "submodules/TelegramUI/Components/Chat/ChatMessageInteractiveInstantVideoNode/Sources/ChatMessageInteractiveInstantVideoNode.swift": "seek",
            "submodules/TelegramUI/Components/Chat/InstantVideoRadialStatusNode/Sources/InstantVideoRadialStatusNode.swift": "seek",
            "submodules/GalleryUI/Sources/ChatVideoGalleryItemScrubberView.swift": "seek",
        }
        for path, token in paths.items():
            self.assertIn(token, (ROOT / path).read_text(encoding="utf-8").lower())
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_media_controls_contract -v
```

Expected: FAIL on the two `isAnimated || disablePlayerControls` gates around lines 1516 and 1854.

- [ ] **Step 3: Make the minimal gallery correction**

At both gates, test only `disablePlayerControls`. This restores stock play/pause, scrubber, mute, and volume controls for animated/GIF content. Retain the current `!isAnimated` PiP gate around line 1907 and all autoplay/loop semantics.

Do not implement new seeking: the existing voice path near `ChatMessageInteractiveFileNode.swift:1331`, round-video paths near `ChatMessageInteractiveInstantVideoNode.swift:1444/1737`, radial drag path near `InstantVideoRadialStatusNode.swift:267`, and fullscreen scrubber near `ChatVideoGalleryItemScrubberView.swift:108` are the implementation. The contract guards them against accidental removal.

- [ ] **Step 4: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_media_controls_contract -v
git diff --check
git add submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift Tests/GRVMgramContracts/test_media_controls_contract.py
git commit -m "fix: expose playback controls for gifs"
```

Expected: PASS.

---

### Task 4: Show precise reaction and service-message time while preserving top notifications

**Files:**
- Modify: `submodules/TelegramStringFormatting/Sources/DateFormat.swift`
- Modify: `submodules/TelegramStringFormatting/Sources/PresenceStrings.swift`
- Modify: `submodules/Components/ReactionListContextMenuContent/Sources/ReactionListContextMenuContent.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageActionBubbleContentNode/Sources/ChatMessageActionBubbleContentNode.swift`
- Test: `Tests/GRVMgramContracts/test_timestamp_notification_contract.py`

**Backward-compatible formatter signatures:**

```swift
public func stringForMediumDate(
    timestamp: Int32,
    strings: PresentationStrings,
    dateTimeFormat: PresentationDateTimeFormat,
    withTime: Bool = true,
    withSeconds: Bool = false
) -> String

public func humanReadableStringForTimestamp(
    strings: PresentationStrings,
    dateTimeFormat: PresentationDateTimeFormat,
    timestamp: Int32,
    alwaysShowTime: Bool = false,
    allowYesterday: Bool = true,
    format: HumanReadableStringFormat? = nil,
    withSeconds: Bool = false
) -> PresentationStrings.FormattedString
```

- [ ] **Step 1: Write failing seconds/layout and notification regressions**

Assert both new defaulted parameters, `timeinfo.tm_sec` forwarded to existing `stringForShortTimestamp(... seconds:)`, reaction UI opts in with `withSeconds: true`, action bubble owns a distinct time node/pill gated by account-scoped `showSecondsInMessages`, and stock `NotificationContainerController`/node/item files still implement top safe-area positioning and top-edge animate in/out.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_timestamp_notification_contract -v
```

Expected: FAIL because medium/human-readable formatters omit seconds and service bubbles have no distinct time element.

- [ ] **Step 3: Extend shared formatting without changing existing callers**

Append `withSeconds: Bool = false` to both public signatures. Thread optional seconds through the private human-readable helper and call:

```swift
stringForShortTimestamp(
    hours: Int32(timeinfo.tm_hour),
    minutes: Int32(timeinfo.tm_min),
    seconds: withSeconds ? Int32(timeinfo.tm_sec) : nil,
    dateTimeFormat: dateTimeFormat
)
```

Existing call sites compile and retain minute precision. Do not duplicate 12/24-hour formatting.

- [ ] **Step 4: Opt reaction history into precise time**

`MessageReactions.swift` already retains exact reaction timestamps around lines 757 and 922. In `ReactionListContextMenuContent.swift:631`, pass `withSeconds: true` to the applicable formatter. Do not synthesize a timestamp from message date or list-load time.

- [ ] **Step 5: Add a separate service-time pill**

In `ChatMessageActionBubbleContentNode`, add a small text/background node aligned to the action bubble's lower trailing edge. It uses the message timestamp, current date/time format, and `withSeconds: true` only when `shouldShowSeconds?(item.context.account.peerId)` is enabled. Include the pill's width/height in async layout and hit-test geometry.

Suppress the extra pill for action cards with `image != nil`, large media-only actions, and suggested-post cards whose own layout already owns a timestamp. Do not append the time to localized service text, because that breaks entity ranges and line wrapping.

- [ ] **Step 6: Preserve stock top notifications**

No production change is needed for top notifications. The current `NotificationContainerController.swift`, `NotificationContainerControllerNode.swift`, and `NotificationItemContainerNode.swift` already position the in-app banner below the top safe area and animate from the top. iOS system notification position is not configurable. Keep the regression assertions; add no toggle.

- [ ] **Step 7: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_timestamp_notification_contract -v
git diff --check
git add submodules/TelegramStringFormatting/Sources/DateFormat.swift submodules/TelegramStringFormatting/Sources/PresenceStrings.swift submodules/Components/ReactionListContextMenuContent/Sources/ReactionListContextMenuContent.swift submodules/TelegramUI/Components/Chat/ChatMessageActionBubbleContentNode/Sources/ChatMessageActionBubbleContentNode.swift Tests/GRVMgramContracts/test_timestamp_notification_contract.py
git commit -m "feat: show precise reaction and service times"
```

Expected: PASS.

---

### Task 5: Round sticker picker artwork and add a separate channel-author badge

**Files:**
- Modify: `submodules/StickerPackPreviewUI/Sources/StickerPackPreviewGridItem.swift`
- Modify: `submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiPagerContentComponent.swift`
- Modify: `submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiKeyboardItemLayer.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift`
- Test: `Tests/GRVMgramContracts/test_sticker_badge_contract.py`

- [ ] **Step 1: Write failing visual-structure contracts**

Assert a named `5.0` sticker radius, an image-sized clipping wrapper in pack preview, `.detailed` gating in EntityKeyboard, explicit reset to radius zero/masks false in non-sticker modes, unchanged chat sticker nodes, and a separate author badge node gated by incoming group/channel-author conditions rather than reused verification state.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_sticker_badge_contract -v
```

Expected: FAIL because picker artwork is square and there is no dedicated channel-author badge.

- [ ] **Step 3: Clip only sticker artwork in pack preview**

In `StickerPackPreviewGridItem`, add an image-frame wrapper/layer with `cornerRadius = 5.0` and `masksToBounds = true`. Move the static image, animation content, and loading artwork/shimmer inside the same wrapper. Size and position it to the existing `imageFrame` on every layout pass.

Do not clip the whole cell: selection effects, context extraction, badges, and touch target must remain outside the rounded artwork.

- [ ] **Step 4: Apply radius only to detailed sticker keyboard items**

When `component.itemLayoutType == .detailed`, apply radius 5 and masking to `itemLayer`, `underlyingContentLayer`, and `tintContentLayer`. On reused layers in emoji/reaction/compact modes, explicitly restore `cornerRadius = 0.0` and `masksToBounds = false`. Keep animated sticker playback and selection transforms unchanged.

- [ ] **Step 5: Add an independent author-header channel badge**

In `ChatMessageBubbleItemNode` near the author header/credibility icon paths around lines 1968-2737 and layout around 4060, allocate a small channel icon node when all are true:

- the message is incoming;
- the containing peer is a group channel/megagroup;
- the effective message author is `TelegramChannel`;
- the item is not admin-log or preview rendering.

Place it immediately after the measured author name, tint it with `authorNameColor`, and include it in header width/layout. Reuse a bundled Telegram channel asset such as `Chat List/Search/Channel`; do not download or create a project badge. Keep verified, fake, scam, emoji-status, and credibility indicators as separate nodes/states.

- [ ] **Step 6: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_sticker_badge_contract -v
git diff --check
git add submodules/StickerPackPreviewUI/Sources/StickerPackPreviewGridItem.swift submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiPagerContentComponent.swift submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiKeyboardItemLayer.swift submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift Tests/GRVMgramContracts/test_sticker_badge_contract.py
git commit -m "feat: refine stickers and channel author labels"
```

Expected: PASS.

---

### Task 6: Implement honest Streamer privacy with a capture-state window cover

**Files:**
- Modify: `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- Create: `submodules/TelegramUI/Sources/GRVMScreenCapturePrivacyController.swift`
- Modify: `submodules/TelegramUI/Sources/AppDelegate.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift`
- Test: `Tests/GRVMgramContracts/test_streamer_privacy_contract.py`

- [ ] **Step 1: Write failing lifecycle and safety contracts**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class StreamerPrivacyContractTests(unittest.TestCase):
    def test_public_capture_api_and_cover_are_used(self) -> None:
        source = (ROOT / "submodules/TelegramUI/Sources/GRVMScreenCapturePrivacyController.swift").read_text(encoding="utf-8")
        self.assertIn("UIScreen.capturedDidChangeNotification", source)
        self.assertIn("UIScreen.main.isCaptured", source)
        self.assertIn("window.addSubview", source)
        self.assertIn("accessibilityViewIsModal", source)
        self.assertNotIn("UITextField", source)

    def test_setting_is_real_and_drawer_flag_is_not_a_consumer(self) -> None:
        settings = (ROOT / "submodules/AyuGramLib/Sources/AyuGramSettings.swift").read_text(encoding="utf-8")
        self.assertIn("var streamerModeEnabled: Bool", settings)
        other = (ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift").read_text(encoding="utf-8")
        self.assertIn("streamerModeEnabled", other)
        self.assertNotIn("showStreamerToggleInDrawer", other)

    def test_app_delegate_owns_and_disposes_controller(self) -> None:
        source = (ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift").read_text(encoding="utf-8")
        self.assertIn("GRVMScreenCapturePrivacyController", source)
        self.assertIn("dispose", source)
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_streamer_privacy_contract -v
```

Expected: FAIL because the setting is currently only a dead drawer visibility field and no controller exists.

- [ ] **Step 3: Add migration-safe setting and real Other row**

Add `streamerModeEnabled`, decode default false, and encode it. Keep `showStreamerToggleInDrawer` decode/encode for migration only, but remove every visible/runtime consumer. Add a standard `ItemListSwitchItem` under Other with a concise note that it hides content during recording/AirPlay/screen sharing, not still screenshots. Update through the current account's `updateGRVMSettings` call.

- [ ] **Step 4: Implement the public capture-state controller**

The controller:

- retains a weak window reference and a `MetaDisposable` for `enabled`;
- observes `UIScreen.capturedDidChangeNotification` on main queue;
- stores the latest enabled value;
- shows its cover only when `enabled && UIScreen.main.isCaptured`;
- creates one opaque autoresizing UIView covering `window.bounds`, above Telegram content;
- uses black/system background plus a centered neutral localized GRVMgram privacy label with no account name, avatar, peer, or message data;
- sets `isAccessibilityElement`/`accessibilityViewIsModal` so VoiceOver cannot traverse hidden content;
- removes observer, disposes signal, and removes cover in `dispose`/`deinit`.

No private notification, screen-capture prevention claim, secure text entry, or extra UIWindow is allowed.

- [ ] **Step 5: Own lifecycle from AppDelegate**

After the main window assignment around `AppDelegate.swift:399-417`, create one controller. Feed it a distinct-until-changed signal for the active primary account's `streamerModeEnabled`; when no account is active, emit false. Rebind when primary account changes, using the account plan's registry/settings signal. Dispose the controller before window replacement or AppDelegate teardown.

- [ ] **Step 6: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_streamer_privacy_contract -v
git diff --check
git add submodules/AyuGramLib/Sources/AyuGramSettings.swift submodules/TelegramUI/Sources/GRVMScreenCapturePrivacyController.swift submodules/TelegramUI/Sources/AppDelegate.swift submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift Tests/GRVMgramContracts/test_streamer_privacy_contract.py
git commit -m "feat: add screen capture privacy cover"
```

Expected: PASS.

---

### Task 7: Add adaptive Saved Music color from local artwork

**Files:**
- Modify: `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Create: `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/GRVMSavedMusicColor.swift`
- Modify: `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift`
- Modify: `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/BUILD`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift`
- Test: `Tests/GRVMgramContracts/test_saved_music_contract.py`

**Account-aware policy hook:**

```swift
public static var shouldUseAdaptiveSavedMusicCover: ((PeerId) -> Bool)?
```

- [ ] **Step 1: Write failing local-only/cache contracts**

Assert setting/default true, account-aware hook, largest preview selection, `mediaBox.resourceData`, `data.complete`, `UIImage(contentsOfFile:)`, existing `averageColor(from:)`, HSB clamping bounds, resource-ID cache, `MetaDisposable`, stale-resource equality check, and absence of URLSession/iTunes/artwork network fallback.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_saved_music_contract -v
```

Expected: FAIL because the header always uses stock theme colors and no local artwork policy exists.

- [ ] **Step 3: Add setting and Appearance row**

Add `adaptiveCoverColor` with decode/default true and encode support. Wire the account-aware hook through the exact coordinator snapshot. Add a standard Appearance switch; disabling it immediately restores stock colors without discarding cache.

- [ ] **Step 4: Build deterministic muted color extraction**

`GRVMSavedMusicColor` receives `MediaBox`, a file, and completion. Choose the preview representation with largest pixel area. Subscribe to `mediaBox.resourceData(resource)` but accept only `data.complete == true`; never call fetch. Load `UIImage(contentsOfFile: data.path)`, call existing `averageColor(from:)`, convert to HSB, and clamp:

```swift
saturation = min(0.65, max(0.28, saturation))
brightness = min(0.42, max(0.18, brightness))
```

Preserve hue and full opacity. Cache result by stable media resource ID in a small synchronized in-memory dictionary. A missing representation, incomplete resource, decode failure, or extraction failure returns nil.

- [ ] **Step 5: Integrate with Saved Music header safely**

At `PeerInfoHeaderNode.swift:2584-2705`, retain one `MetaDisposable` and current requested resource ID. When track/account/setting changes, dispose the old request. Apply a completion only if its resource ID still equals the current track's largest representation.

With a color, use it as the Saved Music card background; title is white, subtitle is white with secondary alpha, and icon/arrow are white. Without a color or when disabled, restore the exact stock theme colors. Do not recolor the surrounding profile header.

- [ ] **Step 6: Verify and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_saved_music_contract -v
git diff --check
git add submodules/AyuGramLib/Sources/AyuGramSettings.swift submodules/TelegramCore/Sources/AyuGramHooks.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/GRVMSavedMusicColor.swift submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/BUILD submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift Tests/GRVMgramContracts/test_saved_music_contract.py
git commit -m "feat: adapt saved music color from local artwork"
```

Expected: PASS.

---

### Task 8: Add local crash export and confirmed account reset

**Files:**
- Create: `submodules/TelegramUI/Sources/GRVMLocalCrashExport.swift`
- Create: `Tests/GRVMgramContracts/test_crash_reset_contract.py`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift`
- Modify: `submodules/TelegramUI/Sources/AppDelegate.swift`

**Exact local-only interface:**

```swift
public struct GRVMLocalCrashExportBundle {
    public let urls: [URL]
    public let fileCount: Int
    public let totalBytes: Int64
}

public final class GRVMLocalCrashExport {
    public init(rootPath: String)
    public func beginForegroundSession(accountPeerId: PeerId)
    public func markSessionClean()
    public func previousSessionEndedUnexpectedly(accountPeerId: PeerId) -> Bool
    public func stageExport() -> Signal<GRVMLocalCrashExportBundle?, NoError>
    public func cleanup(_ bundle: GRVMLocalCrashExportBundle)
}
```

- [ ] **Step 1: Write the failing local-only contract**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / "submodules/TelegramUI/Sources/GRVMLocalCrashExport.swift"
APP = ROOT / "submodules/TelegramUI/Sources/AppDelegate.swift"
OTHER = ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift"


class CrashResetContractTests(unittest.TestCase):
    def test_export_is_bounded_and_local(self) -> None:
        source = EXPORT.read_text(encoding="utf-8")
        for token in ("collectLogs", "collectShortLogFiles", "resolvingSymlinksInPath", "isRegularFile", "16 * 1024 * 1024", "cleanup"):
            self.assertIn(token, source)
        for forbidden in ("urlsession", "appcenter", "github.com", "ayugram"):
            self.assertNotIn(forbidden, source.lower())

    def test_app_does_not_start_remote_crash_upload(self) -> None:
        source = APP.read_text(encoding="utf-8")
        self.assertNotIn("AppCenter.start", source)
        self.assertIn("previousSessionEndedUnexpectedly", source)

    def test_reset_is_confirmed_and_account_scoped(self) -> None:
        source = OTHER.read_text(encoding="utf-8")
        self.assertIn("textAlertController", source)
        self.assertIn("updateGRVMSettings", source)
        self.assertIn("context.account.peerId", source)
        self.assertNotIn("updateAyuGramSettings(accountManager:", source)
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_crash_reset_contract -v
```

Expected: FAIL because the switch has no consumer, reset writes the legacy global settings value without confirmation, and AppCenter upload starts independently of the preference.

- [ ] **Step 3: Implement a foreground-session marker without claiming access to iOS `.ips` files**

Store one small atomic JSON marker under `<rootPath>/grvm-local-crash/`, containing account peer ID, foreground start timestamp, and `active`. On `applicationDidBecomeActive`, inspect the previous marker for the primary account and then atomically write `active = true`. On `applicationDidEnterBackground` and `applicationWillTerminate`, write `active = false`. A true marker on the next launch means only "the foreground session ended unexpectedly"; the UI must not call it a symbolicated iOS crash report.

iOS does not expose system Analytics `.ips` files to a sandboxed application. Export only Telegram's own app logs from `Logger.shared.collectLogs()` and `collectShortLogFiles()`. Do not scan outside the app container and do not install a signal/exception handler.

- [ ] **Step 4: Stage a bounded immutable export**

Call `Logger.shared.sync()`, combine normal and critical logs, sort newest first, and accept at most eight regular files with an aggregate maximum of 16 MiB. Resolve the app root and each candidate with `resolvingSymlinksInPath`; reject a candidate unless it remains below the canonical root, has `.isRegularFile == true`, and is not a symlink. Copy accepted files to a unique temporary directory before sharing so the logger cannot mutate them during export.

`stageExport()` returns nil when no safe file exists. Present `UIActivityViewController` with the staged file URLs, include file count/total bytes in the confirmation, and call `cleanup` from both completion and cancellation paths. No network request or automatic recipient is configured.

- [ ] **Step 5: Wire opt-in and remove remote crash startup**

Remove the `AppCenter.start(... Crashes.self ...)` block from `AppDelegate`; keeping an SDK import/build dependency temporarily is harmless, but no crash service may start or upload. After the primary account settings signal is available:

- keep the marker only while `crashReportingEnabled` is true;
- if the prior primary-account marker was active and safe logs exist, offer `Export Local Logs` or `Not Now` once;
- never present an offer for a different account's marker;
- add a manual `Export Local Logs` row in Other while the preference is enabled.

The preference controls local prompting/export only. Turning it off marks the current session clean and removes its marker.

- [ ] **Step 6: Confirm reset and reset only settings**

The destructive row presents `textAlertController`; cancellation performs no write. Confirmation calls:

```swift
updateGRVMSettings(
    accountId: context.account.peerId,
    accountManager: context.sharedContext.accountManager
) { _ in
    AyuGramSettings.defaultSettings
}
```

It does not clear archived messages, backed-up media, another account's settings, Telegram preferences, or authorization. The coordinator receives the new snapshot through the account plan's existing subscription.

- [ ] **Step 7: Run GREEN and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_crash_reset_contract -v
git diff --check
git add submodules/TelegramUI/Sources/GRVMLocalCrashExport.swift submodules/TelegramUI/Sources/AppDelegate.swift submodules/AyuGramSettingsUI/Sources/AyuGramOtherController.swift Tests/GRVMgramContracts/test_crash_reset_contract.py
git commit -m "feat: add local crash export and safe reset"
```

Expected: PASS and no remote crash-service startup remains.

---

### Task 9: Add own-message deletion, read variants, callback copy, and jump to beginning

**Files:**
- Create: `submodules/TelegramCore/Sources/GRVMReadReceiptBypass.swift`
- Create: `submodules/TelegramCore/Sources/TelegramEngine/Messages/GRVMReadActions.swift`
- Create: `submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteOwnMessages.swift`
- Create: `Tests/GRVMgramContracts/test_peer_message_actions_contract.py`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Messages/ApplyMaxReadIndexInteractively.swift`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Messages/ReplyThreadHistory.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift`
- Modify: `submodules/AccountContext/Sources/AccountContext.swift`
- Modify: `submodules/TelegramUI/Sources/AccountContext.swift`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageItemView/Sources/ChatMessageItemView.swift`
- Modify: `submodules/TelegramUI/Sources/ChatController.swift`
- Modify: `submodules/TelegramUI/Sources/ChatControllerScrollToPointInHistory.swift`

**Exact engine interfaces:**

```swift
public enum GRVMReadMode {
    case automatic
    case localOnly
    case forceServer
}

public struct GRVMDeleteOwnMessagesResult: Equatable {
    public let matchedCount: Int
    public let submittedCount: Int
}

public extension TelegramEngine.Messages {
    func grvmApplyMaxReadIndex(
        _ index: MessageIndex,
        mode: GRVMReadMode
    ) -> Signal<Void, NoError>

    func grvmDeleteOwnMessages(
        peerId: PeerId,
        threadId: Int64?
    ) -> Signal<GRVMDeleteOwnMessagesResult, NoError>
}
```

- [ ] **Step 1: Write exact action-route tests**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PeerMessageActionsContractTests(unittest.TestCase):
    def source(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_own_delete_search_is_author_and_topic_scoped(self) -> None:
        source = self.source("submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteOwnMessages.swift")
        self.assertIn("fromId: account.peerId", source)
        self.assertIn("threadId: threadId", source)
        self.assertIn("message.author?.id == account.peerId", source)
        self.assertIn("type: .forEveryone", source)

    def test_local_read_consumes_sync_operation(self) -> None:
        source = self.source("submodules/TelegramCore/Sources/TelegramEngine/Messages/GRVMReadActions.swift")
        self.assertIn("case .localOnly", source)
        self.assertIn("confirmSynchronizedIncomingReadState", source)

    def test_forced_server_read_is_narrow_and_expiring(self) -> None:
        source = self.source("submodules/TelegramCore/Sources/GRVMReadReceiptBypass.swift")
        for token in ("accountPeerId", "peerId", "maxIncomingReadId", "expiresAt"):
            self.assertIn(token, source)
        managed = self.source("submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift")
        self.assertIn("consumeIfMatching", managed)

    def test_button_copy_and_history_jump_use_existing_routes(self) -> None:
        button = self.source("submodules/TelegramUI/Components/Chat/ChatMessageItemView/Sources/ChatMessageItemView.swift")
        self.assertIn("case let .callback(_, data)", button)
        self.assertIn("UIPasteboard.general", button)
        scroll = self.source("submodules/TelegramUI/Sources/ChatControllerScrollToPointInHistory.swift")
        self.assertIn("scrollToStartOfHistory", scroll)
        self.assertIn(".lowerBound", scroll)
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_peer_message_actions_contract -v
```

Expected: FAIL because the actions and forced/local read modes are absent.

- [ ] **Step 3: Implement complete own-message deletion**

Show `Delete Own Messages` only in cloud legacy groups and group channels/megagroups, including the current forum topic; hide it in users, broadcast channels, secret chats, scheduled messages, and custom chat contents. Require a destructive confirmation before search.

The engine repeatedly calls existing `searchMessages` with:

```swift
.peer(
    peerId: peerId,
    fromId: account.peerId,
    tags: nil,
    reactions: nil,
    threadId: threadId,
    minDate: nil,
    maxDate: nil
)
```

using an empty query, limit 100, and returned `SearchMessagesState` until `result.completed`. Deduplicate IDs and defensively retain only cloud messages whose `author?.id == account.peerId` and whose `threadId` equals the requested topic when non-nil. After the complete scan, submit batches of at most 100 through `deleteMessagesInteractively(... type: .forEveryone)`. Do not use `removeAllMessagesWithAuthor`, which is local-only and would leave server history intact. Cancellation before confirmation/search submits nothing.

- [ ] **Step 4: Add local and explicitly forced read modes**

For a peer chat, `localOnly` runs the same Postbox/state-manager mutation as `_internal_applyMaxReadIndexInteractively` and calls `transaction.confirmSynchronizedIncomingReadState(index.id.peerId)` in the same transaction, leaving no Push/Validate operation. It never sends a network request. Hide local read actions for secret chats because starting secret-media timers is not a local-only operation.

`forceServer` registers a 30-second `GRVMReadReceiptBypass` keyed by exact account ID, dialog peer ID, and target max incoming ID, then invokes the stock interactive read mutation. `ManagedSynchronizePeerReadStates` consumes a token only when all three values match the Push state; unmatched/expired tokens never bypass Ghost. Remove a token on completion/failure/timeout. This is an ephemeral action token, not a settings fallback.

Refactor `ReplyThreadHistory.applyMaxReadIndex` to accept `mode: GRVMReadMode = .automatic`:

- all modes update only that thread's local counters/summary;
- `.automatic` sends `readDiscussion`/`readSavedHistory` only when Ghost read suppression is false;
- `.localOnly` never sends either request;
- `.forceServer` sends the existing direct request regardless of Ghost.

Extend the `AccountContext` protocol/implementation with a GRVM method that routes peer chats to the engine and reply threads to `ReplyThreadHistory`, preserving topic scope.

- [ ] **Step 5: Wire exact menu behavior**

- `Read Message` appears on one incoming cloud message while Ghost read suppression is effective and calls `.localOnly` for that selected `MessageIndex`.
- Chat/peer More menu exposes `Read All Locally` and `Read All on Server` when the current cloud chat/topic has unread incoming messages. Use the latest loaded/top `MessageIndex`; local and forced-server modes remain distinct.
- `Jump to Beginning` calls the existing `scrollToStartOfHistory()` implementation, whose `ChatHistoryLocationInput` uses `.lowerBound`; do not enumerate or pre-load all messages.
- Long-pressing an inline reply-markup button extends `ChatMessageItemView.presentMessageButtonContextMenu`. For `.callback(_, data)`, let `bytes = data.makeData()`, then copy `String(data: bytes, encoding: .utf8)` when valid or lowercase hexadecimal otherwise. Keep the existing URL-button long-press path and do not execute the callback.

- [ ] **Step 6: Run GREEN and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_peer_message_actions_contract -v
git diff --check
git add submodules/TelegramCore/Sources/GRVMReadReceiptBypass.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/GRVMReadActions.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/DeleteOwnMessages.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/ApplyMaxReadIndexInteractively.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/ReplyThreadHistory.swift submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift submodules/AccountContext/Sources/AccountContext.swift submodules/TelegramUI/Sources/AccountContext.swift submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift submodules/TelegramUI/Components/Chat/ChatMessageItemView/Sources/ChatMessageItemView.swift submodules/TelegramUI/Sources/ChatController.swift submodules/TelegramUI/Sources/ChatControllerScrollToPointInHistory.swift Tests/GRVMgramContracts/test_peer_message_actions_contract.py
git commit -m "feat: add GRVMgram peer message actions"
```

Expected: PASS; local mode produces no synchronization operation and forced mode cannot bypass another account/dialog/read ID.

---

### Task 10: Add Burn, local one-view replay, and forwarding overrides

**Files:**
- Create: `submodules/TelegramCore/Sources/SyncCore/GRVMPreservedConsumableMediaAttribute.swift`
- Create: `submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift`
- Create: `Tests/GRVMgramContracts/test_preserved_media_actions_contract.py`
- Modify: `submodules/TelegramCore/Sources/Account/AccountManager.swift`
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Modify: `submodules/TelegramCore/Sources/SyncCore/SyncCore_SynchronizeConsumeMessageContentsOperation.swift`
- Modify: `submodules/TelegramCore/Sources/State/SynchronizeConsumeMessageContentsOperation.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift`
- Modify: `submodules/TelegramCore/Sources/State/ManagedAutoremoveMessageOperations.swift`
- Modify: `submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift`
- Modify: `submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift`
- Modify: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Modify: `submodules/GalleryData/Sources/GalleryData.swift`
- Modify: `submodules/GalleryUI/Sources/SecretMediaPreviewController.swift`
- Modify: `submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift`
- Modify: `submodules/TelegramUI/Sources/OpenChatMessage.swift`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- Modify: `submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift`

**Exact preservation interfaces:**

```swift
public final class GRVMPreservedConsumableMediaAttribute: MessageAttribute, Equatable {
    public let resourceIds: [String]
    public let media: [Media]
    public let preparedAt: Int32
}

public extension GRVMMessageArchiveCoordinator {
    func prepareConsumableMedia(_ message: Message) -> Signal<Bool, NoError>
    func restoreArchivedMedia(for message: Message) -> Signal<Bool, NoError>
}

public static var prepareConsumableMedia: ((PeerId, Message) -> Signal<Bool, NoError>)?
```

Extend the stock API compatibly:

```swift
public func markMessageContentAsConsumedInteractively(
    messageId: MessageId,
    force: Bool = false
) -> Signal<Void, NoError>
```

- [ ] **Step 1: Write availability and safety tests**

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PreservedMediaActionsContractTests(unittest.TestCase):
    def source(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_force_consume_is_persisted_in_operation(self) -> None:
        operation = self.source("submodules/TelegramCore/Sources/SyncCore/SyncCore_SynchronizeConsumeMessageContentsOperation.swift")
        self.assertIn("let force: Bool", operation)
        self.assertIn('decodeInt32ForKey("f"', operation)
        managed = self.source("submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift")
        self.assertIn("!operation.force", managed)

    def test_consumed_media_has_a_persistent_marker(self) -> None:
        attribute = self.source("submodules/TelegramCore/Sources/SyncCore/GRVMPreservedConsumableMediaAttribute.swift")
        self.assertIn("resourceIds", attribute)
        self.assertIn("media", attribute)
        self.assertIn("encodeObjectArray", attribute)
        self.assertIn("preparedAt", attribute)
        account = self.source("submodules/TelegramCore/Sources/Account/AccountManager.swift")
        self.assertIn("GRVMPreservedConsumableMediaAttribute", account)

    def test_local_copy_uses_standalone_upload_and_reports_unavailable(self) -> None:
        source = self.source("submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift")
        self.assertIn("LocalFileReferenceMediaResource", source)
        self.assertIn(".standalone", source)
        self.assertIn("case unavailable", source)
        for forbidden in ("copyProtectionEnabled = false", "isCopyProtected = false", "noForwards = false"):
            self.assertNotIn(forbidden, source)

    def test_replay_does_not_consume_again(self) -> None:
        gallery = self.source("submodules/GalleryUI/Sources/SecretMediaPreviewController.swift")
        self.assertIn("consumeOnOpen", gallery)
        playlist = self.source("submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift")
        self.assertIn("consumeViewOnce", playlist)
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_preserved_media_actions_contract -v
```

Expected: FAIL because forced content consumption, durable consumable metadata, replay mode, and standalone local-copy enqueue do not exist.

- [ ] **Step 3: Preserve a consumable resource before first consumption**

`prepareConsumableMedia` is account-scoped and succeeds only when the coordinator belongs to `message.id`'s active account and at least the primary photo/file resource is complete in MediaBox. Reuse `GRVMMediaResourceCollector` and `GRVMArchivedMediaStore.archive`; do not fetch. After all selected complete resources reach durable archive state, attach `GRVMPreservedConsumableMediaAttribute` to the same Postbox message in one transaction. Store sorted stable resource-ID strings, original image/file descriptors through Postbox `encodeObjectArray`, and `preparedAt`; media objects contain metadata/resource references, not payload bytes or absolute archive paths.

Wire `AyuGramHooks.prepareConsumableMedia(accountPeerId,message)` through the exact account registry. Before normal first opening in `GalleryData`/`SecretMediaPreviewController`, and before one-play voice/instant-video is marked consumed in `PeerMessagesMediaPlaylist`, await this signal when `saveDeletedMessages` is enabled. Failure does not fabricate an archive marker; stock viewing may continue, but replay will honestly be unavailable.

- [ ] **Step 4: Keep prepared media metadata while Telegram marks it consumed**

Register `GRVMPreservedConsumableMediaAttribute` in `AccountManager`'s Postbox decoder table. Pass `accountPeerId` into `markMessageContentAsConsumedRemotely` from `AccountStateManagementUtils`. When the message has the preserved attribute, update consumed/countdown attributes and tags normally but do not replace its original `TelegramMediaImage`/`TelegramMediaFile` with `TelegramMediaExpiredContent`. Apply the same guard in `ManagedAutoremoveMessageOperations` and server-message merge branches that would replace prepared media with expired content; retain the local attribute and descriptor array. The lifecycle plan still decides when a whole TTL message becomes locally deleted.

Do not retain original media merely because Ghost is enabled. The durable marker is required, preventing a UI row that points at bytes that were never backed up.

- [ ] **Step 5: Make Burn an explicit server content-read operation**

Desktop Burn means `messages.readMessageContents`/`channels.readMessageContents`, not a local file deletion. Show Burn for one incoming, unconsumed TTL/view-once message with media. Confirm because it is irreversible on Telegram. Try `prepareConsumableMedia` first when the main resource is local, then call `markMessageContentAsConsumedInteractively(messageId:force:true)`.

Add `force` to `SynchronizeConsumeMessageContentsOperation`, encoded as key `"f"` with decode default false. The operation builder preserves it. Both the interactive producer and `ManagedSynchronizeConsumeMessageContentsOperations` ignore Ghost content-read suppression only when `operation.force == true`; all automatic consumption remains suppressed. Direct channel/user/group requests and PTS handling stay stock.

- [ ] **Step 6: Add replay without a second receipt**

`Replay` appears only when the preserved attribute exists and `restoreArchivedMedia(for:)` verifies/restores every primary resource under its original `MediaResourceId`. If a later server merge already replaced the visible media, restore the attribute's descriptor array into the local Postbox message only after resource verification. On failure, show a localized unavailable alert and do not open an empty viewer.

- Add `consumeOnOpen: Bool = true` to `SecretMediaPreviewController`; Replay passes false, normal opening passes true.
- Add `consumeViewOnce: Bool = true` to `PeerMessagesMediaPlaylist`; Replay passes false and builds playback data with `isViewOnce = false`, while normal playlists retain current one-play behavior.
- Reuse `OpenChatMessage`/stock gallery and media manager after restoration. Do not clone a custom player.

- [ ] **Step 7: Implement local-copy forwarding as a new upload**

Stock Forward remains unchanged for ordinary messages. For a deleted, TTL/one-view/one-play, or copy-protected message, show `Forward Local Copy` only when current MediaBox data or an archived blob can provide the complete primary resource. This action never sends a server forward reference.

`GRVMPreservedMediaEnqueue`:

- restores/verifies resources first;
- creates a unique temporary hard link/copy and a `LocalFileReferenceMediaResource`;
- clones only representable image/file dimensions, MIME type, filename, duration, audio/video/sticker attributes, caption, and `TextEntitiesMessageAttribute`;
- assigns a new local media ID and `.standalone(media:)` reference;
- strips source forward info, reply markup callbacks, autoremove/one-view attributes, and copy-protection metadata;
- sends through the normal enqueue/upload path so stock progress, cancellation, retry, paid-message checks, and error handling remain active.

Text-only protected content becomes a normal new text message with safe entities. Unsupported media kinds or missing bytes return a typed `.unsupported`/`.unavailable` error and enqueue nothing. This creates a user-authorized new message; it does not mutate the source message, server permissions, or Telegram's protection flags.

- [ ] **Step 8: Run GREEN and commit exact files only**

```powershell
python -m unittest Tests.GRVMgramContracts.test_preserved_media_actions_contract -v
git diff --check
git add submodules/TelegramCore/Sources/SyncCore/GRVMPreservedConsumableMediaAttribute.swift submodules/TelegramCore/Sources/Account/AccountManager.swift submodules/TelegramCore/Sources/AyuGramHooks.swift submodules/TelegramCore/Sources/SyncCore/SyncCore_SynchronizeConsumeMessageContentsOperation.swift submodules/TelegramCore/Sources/State/SynchronizeConsumeMessageContentsOperation.swift submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift submodules/TelegramCore/Sources/State/ManagedAutoremoveMessageOperations.swift submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/MarkMessageContentAsConsumedInteractively.swift submodules/TelegramCore/Sources/TelegramEngine/Messages/TelegramEngineMessages.swift submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/GalleryData/Sources/GalleryData.swift submodules/GalleryUI/Sources/SecretMediaPreviewController.swift submodules/TelegramUI/Components/MediaManager/PeerMessagesMediaPlaylist/Sources/PeerMessagesMediaPlaylist.swift submodules/TelegramUI/Sources/GRVMPreservedMediaEnqueue.swift submodules/TelegramUI/Sources/OpenChatMessage.swift submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift submodules/TelegramUI/Sources/ChatControllerForwardMessages.swift Tests/GRVMgramContracts/test_preserved_media_actions_contract.py
git commit -m "feat: add preserved media replay and forwarding"
```

Expected: PASS; no directory-wide `git add` is used, preserving the user's unrelated Ghost change.

---

### Task 11: Enforce official-resource boundaries and run the standalone release gate

**Files:**
- Create: `Tests/GRVMgramContracts/test_standalone_release_gate.py`
- Modify production files only if this gate finds a real violation introduced or retained in the standalone scope.

- [ ] **Step 1: Write the failing/guarding release-gate module**

The module enumerates every file owned by this plan and asserts:

- no `ayugrambot`, Extera ID/URL, AyuGram supporter/developer popup, donation URL, resolver bot, dpaste endpoint, or `Official app` advertising string exists;
- no custom GRVMgram trusted/verified badge registry is added;
- Telegram verified/fake/scam rendering remains present;
- `RecentAccountSession.flags.contains(.isOfficial)` remains stock;
- numeric lookup is Postbox-only;
- profile dates are local-data-only;
- Saved Music artwork is local-data-only;
- Streamer privacy uses public capture-state API;
- GIF PiP stays gated while controls are visible;
- notification top-overlay implementation remains present;
- AppCenter crash upload is not started and local export stays inside the canonical app root;
- local read leaves no synchronization operation, while force-server bypass tokens match account/dialog/max ID and expire;
- Burn is the explicit forced content-read route, replay requires a durable marker, and local forwarding uses a new standalone upload;
- no task commit command stages an entire `submodules/TelegramCore`, `submodules/TelegramUI`, or `submodules/AyuGramFeatures` directory;
- no new settings field named for an unimplemented standalone row is introduced.

The final localization/branding plan owns repository-wide public AyuGram name/link removal. This gate prevents this plan from adding or depending on those sources.

- [ ] **Step 2: Run the gate before cleanup**

```powershell
python -m unittest Tests.GRVMgramContracts.test_standalone_release_gate -v
```

Expected: PASS if earlier tasks obeyed boundaries; otherwise FAIL with the exact file/token that must be removed without replacing stock Telegram trust indicators.

- [ ] **Step 3: Correct only concrete gate violations**

For a forbidden custom official/developer/supporter row, remove the row and action. Do not rename it to GRVMgram because there is no backend-maintained registry. Preserve Telegram's own verified/fake/scam and official-session indicators. For a network dependency in lookup/date/artwork, remove that fallback and retain honest empty/stock behavior.

- [ ] **Step 4: Run every standalone contract with fresh output**

```powershell
python -m unittest `
  Tests.GRVMgramContracts.test_send_as_sticker_contract `
  Tests.GRVMgramContracts.test_peer_identity_contract `
  Tests.GRVMgramContracts.test_media_controls_contract `
  Tests.GRVMgramContracts.test_timestamp_notification_contract `
  Tests.GRVMgramContracts.test_sticker_badge_contract `
  Tests.GRVMgramContracts.test_streamer_privacy_contract `
  Tests.GRVMgramContracts.test_saved_music_contract `
  Tests.GRVMgramContracts.test_crash_reset_contract `
  Tests.GRVMgramContracts.test_peer_message_actions_contract `
  Tests.GRVMgramContracts.test_preserved_media_actions_contract `
  Tests.GRVMgramContracts.test_standalone_release_gate -v
git diff --check
```

Expected: all tests PASS and `git diff --check` prints nothing.

- [ ] **Step 5: Commit the release gate**

```powershell
git add Tests/GRVMgramContracts/test_standalone_release_gate.py
git commit -m "test: guard standalone parity boundaries"
```

If Step 3 changed production files, include only those exact fixes in this commit and name the concrete boundary in the commit message.

---

## Localization Handoff

The final localization/branding plan adds Russian and English values for:

- Send as Sticker and image-conversion failure;
- Copy Telegram API ID, Copy Bot API ID, Created, Joined;
- Streamer Mode plus the honest recording/AirPlay description and neutral cover label;
- Adaptive Saved Music Cover;
- service-time accessibility text and channel-author badge accessibility label where exposed.
- local crash export/reset confirmation, Delete Own Messages, Read Message, both Read All variants, Copy Callback Data, Jump to Beginning, Burn, replay, and local forwarding errors.

No public AyuGram, upstream GitHub, donation, supporter, resolver-bot, or official-project copy is introduced by this plan.

## Final Verification for This Plan

- [ ] Run all eleven modules from Task 11 with fresh output.
- [ ] Run `git diff --check`.
- [ ] Run `rg -n "ayugrambot|extera|dpaste|resolvePeerByName|itunes\.apple|secureTextEntry|UITextField"` over files changed by this plan and inspect every match; expected relevant implementation matches are none.
- [ ] Run `rg -n "isAnimated \|\| disablePlayerControls" submodules/GalleryUI/Sources/Items/UniversalVideoGalleryItem.swift`; expected no output.
- [ ] Run `rg -n "showStreamerToggleInDrawer" submodules -g '*.swift'`; only legacy Codable migration declarations/encode/decode may remain.
- [ ] Verify `git status --short` and stage only task-owned files. Preserve the user's Ghost fix and other agents' plan/spec changes.
- [ ] Do not run GitHub Actions. Hand the verified work to the localization/branding/CI plan for the single final macOS build and IPA validation.
