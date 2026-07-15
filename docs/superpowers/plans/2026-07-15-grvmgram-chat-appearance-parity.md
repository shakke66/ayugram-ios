# GRVMgram Chat and Appearance Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every applicable Appearance and Chats setting account-scoped and functional on iOS, including the real message actions, compose controls, channel controls, rendering policies, and complete Message Shot workflow defined by the approved GRVMgram parity design.

**Architecture:** A typed account-aware snapshot in TelegramCore replaces process-global zero-argument appearance hooks, while AyuGramFeatures maps each registered account's persisted settings into that snapshot. Existing Telegram UI primitives remain authoritative: chat presentation data owns bubble geometry and fonts, AvatarNode owns clipping, native application bindings own alternate icons, existing navigation/controllers own admin and discussion actions, and a small UIKit renderer owns Message Shot.

**Tech Stack:** Swift, UIKit, AsyncDisplayKit, TelegramCore/Postbox, AyuGramLib, AyuGramFeatures, TelegramPresentationData, ItemListUI, Photos, Python 3.12 `unittest` source-contract tests, Bazel/rules_apple in final macOS CI.

## Global Constraints

- Work only on `codex/grvmgram-full-parity` and preserve the approved base lineage from `b3c83ff590774717fd2905a6cd58272b487ee888`.
- Execute this plan after `2026-07-15-grvmgram-account-storage-media.md`, `2026-07-15-grvmgram-message-lifecycle-history.md`, and `2026-07-15-grvmgram-ghost-filters-general.md`.
- Preserve internal AyuGram module names, type names, hook identifiers, Codable keys, and the legacy database filename for migration compatibility.
- Use `grvmSettings(accountId:accountManager:)` and `updateGRVMSettings(accountId:accountManager:_:)` for every settings read/write; do not reintroduce a process-global settings snapshot.
- An account-dependent consumer must receive `context.account.peerId`, `item.context.account.peerId`, `interfaceState.accountPeerId`, or an equivalent explicit account peer ID.
- Add no third-party library. Reuse UIKit, Photos, Postbox, TelegramCore, the existing controller factories, and existing Bazel targets.
- Windows cannot compile the iOS Bazel graph. Every task therefore starts with an executable Python source-contract test; compilation and signing remain owned by the final localization/branding/CI plan on macOS.
- Do not start an intermediate GitHub Actions build and do not push `master` from this plan.
- The lifecycle plan owns `GRVMDeletedMessageAttribute`, `GRVMEditHistoryMessageAttribute`, per-chat/topic View Deleted, Clear Deleted, per-message History, and the common deleted-message opacity path. This plan consumes and verifies those interfaces without recreating them.
- The localization/branding plan owns every RU/EN value, GRVMgram public copy, localized alternate-icon names, and removal of Desktop Drawer rows. This plan owns functional alternate-icon switching and lists every new key that the localization plan must provide.
- Keep scam, fake, verified, and custom-verification indicators. Hide only the premium star and peer emoji status when `hidePremiumStatuses` is enabled.
- Context-menu modes are exact: `0 = hidden`, `1 = visible`, `2 = visibleWithModifier`. Shift or Control exposes mode 2 directly; touch/no-modifier exposes those actions inside one localized вЂњMore GRVMgram ActionsвЂќ submenu.
- Validate `recentStickersCount` to `1...200` (default `100`), `avatarCorners` to `0...50`, `messageBubbleRadius` to `0...16`, and `messageWidthMultiplier` to `0.5...4.0` rounded to a `0.05` step.
- The default deleted mark is `\u{1F9F9}`. The edited mark accepts arbitrary text; an empty value resolves through the localized edited fallback. Icon mode hides both mark editors without destroying their stored values.
- Message Shot defaults are: background on, date off, reactions off, header on, header decorations on, colorful replies on, spoiler reveal on, and current theme.
- A setting row may remain visible only when this plan names a concrete producer, consumer, and regression contract for it.

---

## Cross-Plan Interfaces

### Account-scoped settings and runtime registry

Consume these exact interfaces from the account/storage plan:

~~~swift
public func grvmSettings(
    accountId: PeerId,
    accountManager: AccountManager<TelegramAccountManagerTypes>
) -> Signal<AyuGramSettings, NoError>

public func updateGRVMSettings(
    accountId: PeerId,
    accountManager: AccountManager<TelegramAccountManagerTypes>,
    _ f: @escaping (AyuGramSettings) -> AyuGramSettings
) -> Signal<Void, NoError>

public final class GRVMAccountFeatureRegistry {
    public func register(
        accountPeerId: PeerId,
        accountRecordId: AccountRecordId,
        postbox: Postbox,
        mediaBox: MediaBox
    )
    public func unregister(accountPeerId: PeerId)
    public func setPrimaryAccount(_ accountPeerId: PeerId?)
    public func service(accountPeerId: PeerId) -> GRVMMessageArchiveCoordinator?
    public func primaryService() -> GRVMMessageArchiveCoordinator?
    public func ownPeerIds() -> Set<PeerId>
}
~~~

### Lifecycle UI and attributes

Consume these exact interfaces from the lifecycle/history plan:

~~~swift
public final class GRVMDeletedMessageAttribute: MessageAttribute, LocalMessageDeletionMarker, Equatable
public final class GRVMEditHistoryMessageAttribute: MessageAttribute, Equatable

public func grvmDeletedMessagesController(
    context: AccountContext,
    peerId: PeerId? = nil,
    threadId: Int64? = nil
) -> ViewController

public func grvmMessageHistoryController(
    context: AccountContext,
    messageId: MessageId
) -> ViewController
~~~

### Filter editor

Consume these exact interfaces from the Ghost/filters/general plan:

~~~swift
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
~~~

`Add Filter` passes the selected message text as `initialExpression` and the current dialog as `initialPeerId`. The editor's constructor supplies enabled, case-insensitive, non-reversed defaults; this plan does not duplicate filter persistence.

### Localization keys owned by the final plan

In addition to keys already listed by the localization plan, its key enum/resources must provide:

~~~swift
case stickersPrivateReactions = "GRVMgram.Chats.Stickers.PrivateReactions"
case deletedMarkVisible = "GRVMgram.Chat.DeletedMark.Visible"
case editedMarkVisible = "GRVMgram.Chat.EditedMark.Visible"
case fieldAttachPopup = "GRVMgram.Chats.Field.AttachPopup"
case fieldEmojiPopup = "GRVMgram.Chats.Field.EmojiPopup"
case contextMoreActions = "GRVMgram.Chats.Context.MoreActions"
case messageDetailsTitle = "GRVMgram.MessageDetails.Title"
case messageDetailsId = "GRVMgram.MessageDetails.Id"
case messageDetailsDate = "GRVMgram.MessageDetails.Date"
case messageDetailsEditDate = "GRVMgram.MessageDetails.EditDate"
case messageDetailsForwardDate = "GRVMgram.MessageDetails.ForwardDate"
case messageDetailsViews = "GRVMgram.MessageDetails.Views"
case messageDetailsForwards = "GRVMgram.MessageDetails.Forwards"
case messageDetailsMedia = "GRVMgram.MessageDetails.Media"
case messageShotBackground = "GRVMgram.MessageShot.Background"
case messageShotReactions = "GRVMgram.MessageShot.Reactions"
case messageShotCurrentTheme = "GRVMgram.MessageShot.Theme.Current"
case messageShotLightTheme = "GRVMgram.MessageShot.Theme.Light"
case messageShotDarkTheme = "GRVMgram.MessageShot.Theme.Dark"
~~~

## File Map

### Create

- `submodules/TelegramCore/Sources/GRVMChatAppearance.swift` вЂ” dependency-safe enums and immutable account snapshot used by low-level UI modules.
- `submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift` вЂ” maps account-scoped `AyuGramSettings` into the TelegramCore snapshot and wires the registry-backed hook.
- `submodules/TelegramUI/Sources/GRVMMessageDetailsController.swift` вЂ” deterministic metadata extraction and the Details controller.
- `submodules/TelegramUI/Sources/GRVMMessageShotModel.swift` вЂ” selected-message, reply, reaction, spoiler, media-preview, header, and theme model.
- `submodules/TelegramUI/Sources/GRVMMessageShotRenderer.swift` вЂ” UIKit/Core Graphics image composition.
- `submodules/TelegramUI/Sources/GRVMMessageShotController.swift` вЂ” preview/options UI plus copy/save actions.
- `Tests/GRVMgramContracts/test_chat_appearance_settings_contract.py` вЂ” Codable defaults, validation, account-scope, and settings-controller contracts.
- `Tests/GRVMgramContracts/test_appearance_consumers_contract.py` вЂ” icon/badge/avatar/MD3/background/font/premium/folder contracts.
- `Tests/GRVMgramContracts/test_chat_controls_contract.py` вЂ” sticker/reaction/channel/rendering/compose contracts.
- `Tests/GRVMgramContracts/test_context_menu_semantics_contract.py` вЂ” visibility routing and real action semantics.
- `Tests/GRVMgramContracts/test_message_shot_contract.py` вЂ” complete Message Shot model/renderer/controller/selection contract.

### Modify: settings and hook ownership

- `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift`
- `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- `submodules/AyuGramFeatures/BUILD`
- `submodules/TelegramCore/Sources/AyuGramHooks.swift`

### Modify: appearance consumers

- `submodules/Display/Source/SwitchNode.swift`
- `submodules/TelegramUI/Sources/AppDelegate.swift`
- `submodules/TelegramUI/Sources/TelegramRootController.swift`
- `submodules/TabBarUI/Sources/TabBarController.swift`
- `submodules/TabBarUI/Sources/TabBarContollerNode.swift`
- `submodules/TelegramUI/Components/TabBarComponent/Sources/TabBarComponent.swift`
- `submodules/TelegramUI/Components/ChatList/ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift`
- `submodules/AvatarNode/Sources/AvatarNode.swift`
- `submodules/TelegramPresentationData/Sources/ChatPresentationData.swift`
- `submodules/TelegramPresentationData/Sources/ChatMessageBubbleImages.swift`
- `submodules/TelegramPresentationData/Sources/PresentationThemeEssentialGraphics.swift`
- `submodules/ChatMessageBackground/Sources/ChatMessageBackground.swift`
- `submodules/TelegramUI/Sources/ChatController.swift`
- `submodules/TelegramUI/Sources/ChatHistoryListNode.swift`

### Modify: complete premium-status surfaces

- `submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleComponent.swift`
- `submodules/TelegramUI/Components/ChatTitleView/Sources/ChatTitleView.swift`
- `submodules/ChatListUI/Sources/Node/ChatListItem.swift`
- `submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift`
- `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift`
- `submodules/ItemListPeerItem/Sources/ItemListPeerItem.swift`
- `submodules/ContactsPeerItem/Sources/ContactsPeerItem.swift`
- `submodules/TelegramUI/Components/ChatListHeaderComponent/Sources/ChatListHeaderComponent.swift`

### Modify: chats, context menus, compose, and selection

- `submodules/TelegramUI/Components/ChatEntityKeyboardInputNode/Sources/ChatEntityKeyboardInputNode.swift`
- `submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiPagerContentSignals.swift`
- `submodules/TelegramUI/Components/Chat/ChatChannelSubscriberInputPanelNode/Sources/ChatChannelSubscriberInputPanelNode.swift`
- `submodules/TelegramUI/Components/Chat/ChatMessageReplyInfoNode/Sources/ChatMessageReplyInfoNode.swift`
- `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- `submodules/TelegramUI/Sources/ChatInterfaceInputContexts.swift`
- `submodules/TelegramUI/Components/Chat/ChatTextInputPanelNode/Sources/ChatTextInputPanelNode.swift`
- `submodules/ChatPresentationInterfaceState/Sources/ChatPanelInterfaceInteraction.swift`
- `submodules/TelegramUI/Components/Chat/ChatMessageSelectionInputPanelNode/Sources/ChatMessageSelectionInputPanelNode.swift`
- `submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift`
- `submodules/AyuGramLib/Sources/GRVMMessageArchiveStore.swift`
- `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- `submodules/TelegramUI/BUILD`

All listed Swift targets already glob `Sources/**/*.swift`. The only new dependency is `//submodules/Display:Display` in `submodules/AyuGramFeatures/BUILD` so the active-account subscriber can set `SwitchNode.defaultStyle`. TelegramUI already imports Photos in `StoreDownloadedMedia.swift` and already depends on AyuGramLib/AyuGramFeatures; do not add a duplicate framework or module dependency.

## Canonical Coverage Ledger

| Canonical row | Producer | Consumer and verification | Task |
|---|---|---|---:|
| Public app-icon picker | `selectedAppIcon` | native application bindings, actual available icon list | 2 |
| Notification badge hiding | `hideNotificationBadge` | AppDelegate active account | 2 |
| Notification counters | `hideNotificationCounters` | current TabBarComponent badge input | 2 |
| Avatar corners | `avatarCorners` | AvatarNode account-aware clip path | 3 |
| Single corner radius | `singleCornerRadius` | forum/roundedRect avatar policy | 3 |
| MD3 switches | `md3StyleSwitches` | Display/SwitchNode active-account style | 3 |
| Custom backgrounds | `disableCustomBackgrounds` | ChatController per-account wallpaper choice | 3 |
| Premium status hiding | `hidePremiumStatuses` | all eight premium-star/emoji surfaces | 3 |
| Monospace font | `codeFontName` | injected ChatPresentationData fixed font | 3 |
| Folder counters | `hideFolderCounters` | chat-list filter tab | 2 |
| All Chats | `hideAllChatsFolder` | chat-list filter ordering | 2 |
| Only added stickers/emoji | `showOnlyAddedStickers` | installed-pack filtering in both keyboards/search | 4 |
| Reactions by chat type | three booleans | broadcast/group/private bubble policy | 4 |
| Recent sticker count | `recentStickersCount` | validated `1...200` keyboard limit | 4 |
| Hide/Mute/Discuss | typed channel mode | subscriber panel, discussion fallback | 5 |
| Quick Admin | `quickAdminShortcuts` | Recent Actions and Admins; old ban shortcut removed | 5 |
| Icon/text and arbitrary marks | mark fields/visibility/icon mode | lifecycle attributes and timestamp renderer | 6 |
| Tail/share/colorful replies | three booleans | bubble corners/share/reply nodes | 6 |
| Translucent deleted | `semiTransparentDeletedMessages` | lifecycle common item-node opacity | 6, 10 |
| Bubble radius and width | validated radius/multiplier | chat presentation/layout | 6 |
| Context-menu controls | seven typed visibility values | real actions plus Shift/Control/touch routing | 7 |
| Compose-field controls | nine booleans | input contexts/text panel | 8 |
| Attach/Emoji touch popup | two booleans | long-press equivalents | 8 |
| Full Message Shot | feature flag plus options | selection panel/model/renderer/copy/save | 9 |
| Per-chat/topic View Deleted | lifecycle plan | controller/menu source audit only | 10 |
| Per-message History | lifecycle plan | attribute/action source audit only | 10 |

### Task 1: Define validated account-aware chat and appearance policy

**Files:**
- Create: `submodules/TelegramCore/Sources/GRVMChatAppearance.swift`
- Create: `submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift`
- Create: `Tests/GRVMgramContracts/test_chat_appearance_settings_contract.py`
- Modify: `submodules/AyuGramLib/Sources/AyuGramSettings.swift`
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`

**Interfaces:**
- Consumes: exact account settings and registry interfaces in **Cross-Plan Interfaces**.
- Produces:

~~~swift
public enum GRVMContextMenuVisibility: Int32 {
    case hidden = 0
    case visible = 1
    case visibleWithModifier = 2
}

public enum GRVMChannelBottomButtonMode: Int32 {
    case hidden = 0
    case mute = 1
    case discussWithFallback = 2
}

public enum GRVMMessageShotTheme: Int32 {
    case current = 0
    case light = 1
    case dark = 2
}

public struct GRVMChatAppearanceSettings: Equatable {
    public let appearance: GRVMAppearanceSettings
    public let chats: GRVMChatSettings
    public let contextMenu: GRVMContextMenuSettings
    public let compose: GRVMComposeSettings
    public let messageShot: GRVMMessageShotOptions
    public static let `default`: GRVMChatAppearanceSettings
}

public extension AyuGramHooks {
    static var chatAppearanceSettings: ((PeerId) -> GRVMChatAppearanceSettings)?
    static func chatAppearance(accountPeerId: PeerId) -> GRVMChatAppearanceSettings
}

public extension AyuGramSettings {
    var grvmChatAppearanceSettings: GRVMChatAppearanceSettings { get }
}
~~~

- [ ] **Step 1: Write the failing settings and policy contract**

Create the complete test file:

~~~python
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class ChatAppearanceSettingsContractTests(unittest.TestCase):
    def test_new_codable_fields_have_declaration_default_decode_and_encode(self) -> None:
        text = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        fields = {
            "showPrivateReactions": "true",
            "showAddFilterInContextMenu": "1",
            "showAttachPopup": "true",
            "showEmojiPopup": "true",
            "messageShotShowBackground": "true",
            "messageShotShowDate": "false",
            "messageShotShowReactions": "false",
            "messageShotShowHeader": "true",
            "messageShotShowHeaderDecorations": "true",
            "messageShotColorfulReplies": "true",
            "messageShotRevealSpoilers": "true",
            "messageShotTheme": "0",
        }
        for name, default in fields.items():
            with self.subTest(name=name):
                self.assertRegex(text, rf"public var {name}: (?:Bool|Int32)")
                self.assertIn(f"{name}: {default}", text)
                self.assertIn(f'forKey: "{name}") ?? {default}', text)
                self.assertIn(f'encode(self.{name}, forKey: "{name}")', text)

    def test_desktop_defaults_and_validation_are_explicit(self) -> None:
        settings = source("submodules/AyuGramLib/Sources/AyuGramSettings.swift")
        self.assertIn("recentStickersCount: 100", settings)
        self.assertIn(r'deletedMessageMark: "\u{1F9F9}"', settings)
        policy = source("submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift")
        required = [
            "min(200, max(1, self.recentStickersCount))",
            "min(50, max(0, self.avatarCorners))",
            "min(16, max(0, self.messageBubbleRadius))",
            "min(4.0, max(0.5, self.messageWidthMultiplier))",
            "(clampedWidth * 20.0).rounded() / 20.0",
            "GRVMContextMenuVisibility(rawValue:",
            "GRVMChannelBottomButtonMode(rawValue:",
            "GRVMMessageShotTheme(rawValue:",
        ]
        for fragment in required:
            self.assertIn(fragment, policy)

    def test_single_account_aware_hook_replaces_zero_argument_appearance_reads(self) -> None:
        hooks = source("submodules/TelegramCore/Sources/AyuGramHooks.swift")
        self.assertIn(
            "public static var chatAppearanceSettings: ((PeerId) -> GRVMChatAppearanceSettings)?",
            hooks,
        )
        self.assertIn(
            "public static func chatAppearance(accountPeerId: PeerId) -> GRVMChatAppearanceSettings",
            hooks,
        )
        policy = source("submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift")
        self.assertIn("registry.service(accountPeerId: accountPeerId)", policy)
        self.assertIn("service.settingsSnapshot().grvmChatAppearanceSettings", policy)
        self.assertNotIn("primaryService()", policy)

    def test_settings_controllers_use_account_scoped_api(self) -> None:
        for relative_path in [
            "submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift",
            "submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift",
        ]:
            text = source(relative_path)
            self.assertIn(
                "grvmSettings(accountId: context.account.peerId, accountManager:",
                text,
            )
            self.assertIn(
                "updateGRVMSettings(accountId: context.account.peerId, accountManager:",
                text,
            )
            self.assertNotRegex(text, r"(?<!GRVM)ayuGramSettings\\(accountManager:")
            self.assertNotRegex(text, r"(?<!GRVM)updateAyuGramSettings\\(accountManager:")


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run the contract and verify RED**

~~~powershell
python -m unittest Tests.GRVMgramContracts.test_chat_appearance_settings_contract -v
~~~

Expected: FAIL in `test_new_codable_fields_have_declaration_default_decode_and_encode` because `showPrivateReactions` and the Message Shot/popup fields do not exist.

- [ ] **Step 3: Add the missing Codable fields without renaming legacy keys**

Add these declarations to `AyuGramSettings`:

~~~swift
public var showPrivateReactions: Bool
public var showAddFilterInContextMenu: Int32
public var showAttachPopup: Bool
public var showEmojiPopup: Bool
public var messageShotShowBackground: Bool
public var messageShotShowDate: Bool
public var messageShotShowReactions: Bool
public var messageShotShowHeader: Bool
public var messageShotShowHeaderDecorations: Bool
public var messageShotColorfulReplies: Bool
public var messageShotRevealSpoilers: Bool
public var messageShotTheme: Int32
~~~

Use these exact defaults in `defaultSettings` and the public initializer:

~~~swift
showPrivateReactions: true,
showAddFilterInContextMenu: 1,
showAttachPopup: true,
showEmojiPopup: true,
messageShotShowBackground: true,
messageShotShowDate: false,
messageShotShowReactions: false,
messageShotShowHeader: true,
messageShotShowHeaderDecorations: true,
messageShotColorfulReplies: true,
messageShotRevealSpoilers: true,
messageShotTheme: 0,
~~~

Change the two existing Desktop defaults in that same initializer:

~~~swift
recentStickersCount: 100,
deletedMessageMark: "\u{1F9F9}",
~~~

Decode every new field with its exact existing-name key:

~~~swift
self.showPrivateReactions = try container.decodeIfPresent(Bool.self, forKey: "showPrivateReactions") ?? true
self.showAddFilterInContextMenu = try container.decodeIfPresent(Int32.self, forKey: "showAddFilterInContextMenu") ?? 1
self.showAttachPopup = try container.decodeIfPresent(Bool.self, forKey: "showAttachPopup") ?? true
self.showEmojiPopup = try container.decodeIfPresent(Bool.self, forKey: "showEmojiPopup") ?? true
self.messageShotShowBackground = try container.decodeIfPresent(Bool.self, forKey: "messageShotShowBackground") ?? true
self.messageShotShowDate = try container.decodeIfPresent(Bool.self, forKey: "messageShotShowDate") ?? false
self.messageShotShowReactions = try container.decodeIfPresent(Bool.self, forKey: "messageShotShowReactions") ?? false
self.messageShotShowHeader = try container.decodeIfPresent(Bool.self, forKey: "messageShotShowHeader") ?? true
self.messageShotShowHeaderDecorations = try container.decodeIfPresent(Bool.self, forKey: "messageShotShowHeaderDecorations") ?? true
self.messageShotColorfulReplies = try container.decodeIfPresent(Bool.self, forKey: "messageShotColorfulReplies") ?? true
self.messageShotRevealSpoilers = try container.decodeIfPresent(Bool.self, forKey: "messageShotRevealSpoilers") ?? true
self.messageShotTheme = try container.decodeIfPresent(Int32.self, forKey: "messageShotTheme") ?? 0
~~~

Encode them explicitly:

~~~swift
try container.encode(self.showPrivateReactions, forKey: "showPrivateReactions")
try container.encode(self.showAddFilterInContextMenu, forKey: "showAddFilterInContextMenu")
try container.encode(self.showAttachPopup, forKey: "showAttachPopup")
try container.encode(self.showEmojiPopup, forKey: "showEmojiPopup")
try container.encode(self.messageShotShowBackground, forKey: "messageShotShowBackground")
try container.encode(self.messageShotShowDate, forKey: "messageShotShowDate")
try container.encode(self.messageShotShowReactions, forKey: "messageShotShowReactions")
try container.encode(self.messageShotShowHeader, forKey: "messageShotShowHeader")
try container.encode(self.messageShotShowHeaderDecorations, forKey: "messageShotShowHeaderDecorations")
try container.encode(self.messageShotColorfulReplies, forKey: "messageShotColorfulReplies")
try container.encode(self.messageShotRevealSpoilers, forKey: "messageShotRevealSpoilers")
try container.encode(self.messageShotTheme, forKey: "messageShotTheme")
~~~

Retain `hideReactions` and all Drawer fields for decoding compatibility even though the localized UI no longer presents them.

- [ ] **Step 4: Add dependency-safe typed snapshot values**

Create `GRVMChatAppearance.swift` with these public groups. Keep initializers public because AyuGramFeatures constructs the values in another module:

~~~swift
import Foundation
import Postbox

public enum GRVMContextMenuVisibility: Int32 {
    case hidden = 0
    case visible = 1
    case visibleWithModifier = 2
}

public enum GRVMChannelBottomButtonMode: Int32 {
    case hidden = 0
    case mute = 1
    case discussWithFallback = 2
}

public enum GRVMMessageShotTheme: Int32 {
    case current = 0
    case light = 1
    case dark = 2
}

public struct GRVMAppearanceSettings: Equatable {
    public let selectedAppIcon: String
    public let hideNotificationBadge: Bool
    public let hideNotificationCounters: Bool
    public let md3StyleSwitches: Bool
    public let removeMessageBubbleTail: Bool
    public let disableCustomBackgrounds: Bool
    public let codeFontName: String
    public let hideFolderCounters: Bool
    public let hideAllChatsFolder: Bool
    public let hidePremiumStatuses: Bool
    public let avatarCorners: Int32
    public let singleCornerRadius: Bool
    public let messageBubbleRadius: Int32

    public init(
        selectedAppIcon: String,
        hideNotificationBadge: Bool,
        hideNotificationCounters: Bool,
        md3StyleSwitches: Bool,
        removeMessageBubbleTail: Bool,
        disableCustomBackgrounds: Bool,
        codeFontName: String,
        hideFolderCounters: Bool,
        hideAllChatsFolder: Bool,
        hidePremiumStatuses: Bool,
        avatarCorners: Int32,
        singleCornerRadius: Bool,
        messageBubbleRadius: Int32
    ) {
        self.selectedAppIcon = selectedAppIcon
        self.hideNotificationBadge = hideNotificationBadge
        self.hideNotificationCounters = hideNotificationCounters
        self.md3StyleSwitches = md3StyleSwitches
        self.removeMessageBubbleTail = removeMessageBubbleTail
        self.disableCustomBackgrounds = disableCustomBackgrounds
        self.codeFontName = codeFontName
        self.hideFolderCounters = hideFolderCounters
        self.hideAllChatsFolder = hideAllChatsFolder
        self.hidePremiumStatuses = hidePremiumStatuses
        self.avatarCorners = avatarCorners
        self.singleCornerRadius = singleCornerRadius
        self.messageBubbleRadius = messageBubbleRadius
    }
}

public struct GRVMChatSettings: Equatable {
    public let showOnlyAddedStickers: Bool
    public let showChannelReactions: Bool
    public let showGroupReactions: Bool
    public let showPrivateReactions: Bool
    public let recentStickersCount: Int32
    public let channelBottomButton: GRVMChannelBottomButtonMode
    public let quickAdminShortcuts: Bool
    public let messageShotFeature: Bool
    public let showDeletedMark: Bool
    public let showEditedMark: Bool
    public let deletedMessageMark: String
    public let editedMessageMark: String
    public let replaceMarksWithIcons: Bool
    public let hideFastShareButton: Bool
    public let disableColoredReplies: Bool
    public let semiTransparentDeletedMessages: Bool
    public let messageWidthMultiplier: Double

    public init(
        showOnlyAddedStickers: Bool,
        showChannelReactions: Bool,
        showGroupReactions: Bool,
        showPrivateReactions: Bool,
        recentStickersCount: Int32,
        channelBottomButton: GRVMChannelBottomButtonMode,
        quickAdminShortcuts: Bool,
        messageShotFeature: Bool,
        showDeletedMark: Bool,
        showEditedMark: Bool,
        deletedMessageMark: String,
        editedMessageMark: String,
        replaceMarksWithIcons: Bool,
        hideFastShareButton: Bool,
        disableColoredReplies: Bool,
        semiTransparentDeletedMessages: Bool,
        messageWidthMultiplier: Double
    ) {
        self.showOnlyAddedStickers = showOnlyAddedStickers
        self.showChannelReactions = showChannelReactions
        self.showGroupReactions = showGroupReactions
        self.showPrivateReactions = showPrivateReactions
        self.recentStickersCount = recentStickersCount
        self.channelBottomButton = channelBottomButton
        self.quickAdminShortcuts = quickAdminShortcuts
        self.messageShotFeature = messageShotFeature
        self.showDeletedMark = showDeletedMark
        self.showEditedMark = showEditedMark
        self.deletedMessageMark = deletedMessageMark
        self.editedMessageMark = editedMessageMark
        self.replaceMarksWithIcons = replaceMarksWithIcons
        self.hideFastShareButton = hideFastShareButton
        self.disableColoredReplies = disableColoredReplies
        self.semiTransparentDeletedMessages = semiTransparentDeletedMessages
        self.messageWidthMultiplier = messageWidthMultiplier
    }
}

public struct GRVMContextMenuSettings: Equatable {
    public let reactions: GRVMContextMenuVisibility
    public let views: GRVMContextMenuVisibility
    public let hide: GRVMContextMenuVisibility
    public let userMessages: GRVMContextMenuVisibility
    public let details: GRVMContextMenuVisibility
    public let repeatMessage: GRVMContextMenuVisibility
    public let addFilter: GRVMContextMenuVisibility

    public init(
        reactions: GRVMContextMenuVisibility,
        views: GRVMContextMenuVisibility,
        hide: GRVMContextMenuVisibility,
        userMessages: GRVMContextMenuVisibility,
        details: GRVMContextMenuVisibility,
        repeatMessage: GRVMContextMenuVisibility,
        addFilter: GRVMContextMenuVisibility
    ) {
        self.reactions = reactions
        self.views = views
        self.hide = hide
        self.userMessages = userMessages
        self.details = details
        self.repeatMessage = repeatMessage
        self.addFilter = addFilter
    }
}

public struct GRVMComposeSettings: Equatable {
    public let showAttachButton: Bool
    public let showCommandsButton: Bool
    public let showTTLButton: Bool
    public let showEmojiButton: Bool
    public let showVoiceButton: Bool
    public let showGiftButton: Bool
    public let showAiEditorButton: Bool
    public let showAttachPopup: Bool
    public let showEmojiPopup: Bool

    public init(
        showAttachButton: Bool,
        showCommandsButton: Bool,
        showTTLButton: Bool,
        showEmojiButton: Bool,
        showVoiceButton: Bool,
        showGiftButton: Bool,
        showAiEditorButton: Bool,
        showAttachPopup: Bool,
        showEmojiPopup: Bool
    ) {
        self.showAttachButton = showAttachButton
        self.showCommandsButton = showCommandsButton
        self.showTTLButton = showTTLButton
        self.showEmojiButton = showEmojiButton
        self.showVoiceButton = showVoiceButton
        self.showGiftButton = showGiftButton
        self.showAiEditorButton = showAiEditorButton
        self.showAttachPopup = showAttachPopup
        self.showEmojiPopup = showEmojiPopup
    }
}

public struct GRVMMessageShotOptions: Equatable {
    public let showBackground: Bool
    public let showDate: Bool
    public let showReactions: Bool
    public let showHeader: Bool
    public let showHeaderDecorations: Bool
    public let colorfulReplies: Bool
    public let revealSpoilers: Bool
    public let theme: GRVMMessageShotTheme

    public init(
        showBackground: Bool,
        showDate: Bool,
        showReactions: Bool,
        showHeader: Bool,
        showHeaderDecorations: Bool,
        colorfulReplies: Bool,
        revealSpoilers: Bool,
        theme: GRVMMessageShotTheme
    ) {
        self.showBackground = showBackground
        self.showDate = showDate
        self.showReactions = showReactions
        self.showHeader = showHeader
        self.showHeaderDecorations = showHeaderDecorations
        self.colorfulReplies = colorfulReplies
        self.revealSpoilers = revealSpoilers
        self.theme = theme
    }
}

public struct GRVMChatAppearanceSettings: Equatable {
    public let appearance: GRVMAppearanceSettings
    public let chats: GRVMChatSettings
    public let contextMenu: GRVMContextMenuSettings
    public let compose: GRVMComposeSettings
    public let messageShot: GRVMMessageShotOptions

    public init(
        appearance: GRVMAppearanceSettings,
        chats: GRVMChatSettings,
        contextMenu: GRVMContextMenuSettings,
        compose: GRVMComposeSettings,
        messageShot: GRVMMessageShotOptions
    ) {
        self.appearance = appearance
        self.chats = chats
        self.contextMenu = contextMenu
        self.compose = compose
        self.messageShot = messageShot
    }

    public static let `default` = GRVMChatAppearanceSettings(
        appearance: GRVMAppearanceSettings(
            selectedAppIcon: "default",
            hideNotificationBadge: false,
            hideNotificationCounters: false,
            md3StyleSwitches: false,
            removeMessageBubbleTail: false,
            disableCustomBackgrounds: false,
            codeFontName: "",
            hideFolderCounters: false,
            hideAllChatsFolder: false,
            hidePremiumStatuses: false,
            avatarCorners: 50,
            singleCornerRadius: false,
            messageBubbleRadius: 16
        ),
        chats: GRVMChatSettings(
            showOnlyAddedStickers: false,
            showChannelReactions: true,
            showGroupReactions: true,
            showPrivateReactions: true,
            recentStickersCount: 100,
            channelBottomButton: .mute,
            quickAdminShortcuts: true,
            messageShotFeature: true,
            showDeletedMark: true,
            showEditedMark: true,
            deletedMessageMark: "\u{1F9F9}",
            editedMessageMark: "",
            replaceMarksWithIcons: false,
            hideFastShareButton: false,
            disableColoredReplies: false,
            semiTransparentDeletedMessages: false,
            messageWidthMultiplier: 1.0
        ),
        contextMenu: GRVMContextMenuSettings(
            reactions: .hidden,
            views: .hidden,
            hide: .visible,
            userMessages: .visible,
            details: .visible,
            repeatMessage: .visible,
            addFilter: .visible
        ),
        compose: GRVMComposeSettings(
            showAttachButton: true,
            showCommandsButton: true,
            showTTLButton: true,
            showEmojiButton: true,
            showVoiceButton: true,
            showGiftButton: true,
            showAiEditorButton: true,
            showAttachPopup: true,
            showEmojiPopup: true
        ),
        messageShot: GRVMMessageShotOptions(
            showBackground: true,
            showDate: false,
            showReactions: false,
            showHeader: true,
            showHeaderDecorations: true,
            colorfulReplies: true,
            revealSpoilers: true,
            theme: .current
        )
    )
}
~~~

- [ ] **Step 5: Map persisted settings with clamped numeric and enum values**

Create `GRVMChatAppearancePolicy.swift`. The extension must compute validation once and then build the groups:

~~~swift
import Foundation
import Display
import Postbox
import TelegramCore
import TelegramUIPreferences
import AyuGramLib

public extension AyuGramSettings {
    var grvmChatAppearanceSettings: GRVMChatAppearanceSettings {
        let recentStickersCount = min(200, max(1, self.recentStickersCount))
        let avatarCorners = min(50, max(0, self.avatarCorners))
        let messageBubbleRadius = min(16, max(0, self.messageBubbleRadius))
        let clampedWidth = min(4.0, max(0.5, self.messageWidthMultiplier))
        let messageWidthMultiplier = (clampedWidth * 20.0).rounded() / 20.0

        func visibility(
            _ value: Int32,
            fallback: GRVMContextMenuVisibility
        ) -> GRVMContextMenuVisibility {
            return GRVMContextMenuVisibility(rawValue: value) ?? fallback
        }

        return GRVMChatAppearanceSettings(
            appearance: GRVMAppearanceSettings(
                selectedAppIcon: self.selectedAppIcon,
                hideNotificationBadge: self.hideNotificationBadge,
                hideNotificationCounters: self.hideNotificationCounters,
                md3StyleSwitches: self.md3StyleSwitches,
                removeMessageBubbleTail: self.removeMessageBubbleTail,
                disableCustomBackgrounds: self.disableCustomBackgrounds,
                codeFontName: self.codeFontName,
                hideFolderCounters: self.hideFolderCounters,
                hideAllChatsFolder: self.hideAllChatsFolder,
                hidePremiumStatuses: self.hidePremiumStatuses,
                avatarCorners: avatarCorners,
                singleCornerRadius: self.singleCornerRadius,
                messageBubbleRadius: messageBubbleRadius
            ),
            chats: GRVMChatSettings(
                showOnlyAddedStickers: self.showOnlyAddedStickers,
                showChannelReactions: self.showChannelReactions,
                showGroupReactions: self.showGroupReactions,
                showPrivateReactions: self.showPrivateReactions,
                recentStickersCount: recentStickersCount,
                channelBottomButton: GRVMChannelBottomButtonMode(rawValue: self.channelBottomButton) ?? .mute,
                quickAdminShortcuts: self.quickAdminShortcuts,
                messageShotFeature: self.messageShotFeature,
                showDeletedMark: self.showDeletedMark,
                showEditedMark: self.showEditedMark,
                deletedMessageMark: self.deletedMessageMark,
                editedMessageMark: self.editedMessageMark,
                replaceMarksWithIcons: self.replaceMarksWithIcons,
                hideFastShareButton: self.hideFastShareButton,
                disableColoredReplies: self.disableColoredReplies,
                semiTransparentDeletedMessages: self.semiTransparentDeletedMessages,
                messageWidthMultiplier: messageWidthMultiplier
            ),
            contextMenu: GRVMContextMenuSettings(
                reactions: visibility(self.showReactionsPanelInContextMenu, fallback: .hidden),
                views: visibility(self.showViewsPanelInContextMenu, fallback: .hidden),
                hide: visibility(self.showHideMessageInContextMenu, fallback: .visible),
                userMessages: visibility(self.showUserMessagesInContextMenu, fallback: .visible),
                details: visibility(self.showMessageDetailsInContextMenu, fallback: .visible),
                repeatMessage: visibility(self.showRepeatMessageInContextMenu, fallback: .visible),
                addFilter: visibility(self.showAddFilterInContextMenu, fallback: .visible)
            ),
            compose: GRVMComposeSettings(
                showAttachButton: self.showAttachButton,
                showCommandsButton: self.showCommandsButton,
                showTTLButton: self.showTTLButton,
                showEmojiButton: self.showEmojiButton,
                showVoiceButton: self.showVoiceButton,
                showGiftButton: self.showGiftButton,
                showAiEditorButton: self.showAiEditorButton,
                showAttachPopup: self.showAttachPopup,
                showEmojiPopup: self.showEmojiPopup
            ),
            messageShot: GRVMMessageShotOptions(
                showBackground: self.messageShotShowBackground,
                showDate: self.messageShotShowDate,
                showReactions: self.messageShotShowReactions,
                showHeader: self.messageShotShowHeader,
                showHeaderDecorations: self.messageShotShowHeaderDecorations,
                colorfulReplies: self.messageShotColorfulReplies,
                revealSpoilers: self.messageShotRevealSpoilers,
                theme: GRVMMessageShotTheme(rawValue: self.messageShotTheme) ?? .current
            )
        )
    }
}

public func installGRVMChatAppearanceHooks(registry: GRVMAccountFeatureRegistry) {
    AyuGramHooks.chatAppearanceSettings = { [weak registry] accountPeerId in
        guard let service = registry?.service(accountPeerId: accountPeerId) else {
            return .default
        }
        return service.settingsSnapshot().grvmChatAppearanceSettings
    }
}
~~~

Add `//submodules/Display:Display` to `submodules/AyuGramFeatures/BUILD` now; Task 3 uses the imported low-level switch value.

- [ ] **Step 6: Expose one account-aware hook and remove targeted zero-argument wiring**

Add to `AyuGramHooks.swift`:

~~~swift
public static var chatAppearanceSettings: ((PeerId) -> GRVMChatAppearanceSettings)?

public static func chatAppearance(accountPeerId: PeerId) -> GRVMChatAppearanceSettings {
    return self.chatAppearanceSettings?(accountPeerId) ?? .default
}
~~~

Call `installGRVMChatAppearanceHooks(registry:)` after the account plan creates the registry. Delete the appearance/chat/context-menu/compose assignments in `AyuGramFeatureManager.wireHooks` that return `self.currentSettings`. Ghost, filters, deletion, Local Premium, and general-feature hooks remain owned by their respective plans.

- [ ] **Step 7: Convert both settings controllers to exact-account reads and writes**

Use this body for every typed update closure:

~~~swift
let _ = updateGRVMSettings(
    accountId: context.account.peerId,
    accountManager: context.sharedContext.accountManager
) { settings in
    var settings = settings
    settings[keyPath: keyPath] = value
    return settings
}.startStandalone()
~~~

Use this signal in both controllers:

~~~swift
let settings = grvmSettings(
    accountId: context.account.peerId,
    accountManager: context.sharedContext.accountManager
)
let signal = combineLatest(context.sharedContext.presentationData, settings)
~~~

- [ ] **Step 8: Run GREEN, refactor, and commit**

~~~powershell
python -m unittest Tests.GRVMgramContracts.test_chat_appearance_settings_contract -v
git diff --check
git add submodules/TelegramCore/Sources/GRVMChatAppearance.swift submodules/TelegramCore/Sources/AyuGramHooks.swift submodules/AyuGramLib/Sources/AyuGramSettings.swift submodules/AyuGramFeatures/Sources/GRVMChatAppearancePolicy.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift submodules/AyuGramFeatures/BUILD submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift Tests/GRVMgramContracts/test_chat_appearance_settings_contract.py
git commit -m "refactor: scope chat appearance policy by account"
~~~

Expected: four tests PASS; `git diff --check` prints no errors. During refactor, keep the snapshot immutable and do not add one closure per setting.

### Task 2: Apply real app icons, badges, folder counters, and All Chats visibility

**Files:**
- Create: `Tests/GRVMgramContracts/test_appearance_consumers_contract.py`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift`
- Modify: `submodules/TelegramUI/Sources/AppDelegate.swift`
- Modify: `submodules/TelegramUI/Sources/TelegramRootController.swift`
- Modify: `submodules/TabBarUI/Sources/TabBarController.swift`
- Modify: `submodules/TabBarUI/Sources/TabBarContollerNode.swift`
- Modify: `submodules/TelegramUI/Components/TabBarComponent/Sources/TabBarComponent.swift`
- Modify: `submodules/TelegramUI/Components/ChatList/ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift`

**Interfaces:**
- Consumes: `GRVMChatAppearanceSettings.appearance` and the account-scoped update function.
- Produces: native icon selection whose persisted value changes only after `requestSetAlternateIconName` succeeds; account-aware badge/folder policies.

- [ ] **Step 1: Write the failing consumer contract**

Create the complete file:

~~~python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class AppearanceConsumerContractTests(unittest.TestCase):
    def test_app_icon_picker_uses_only_native_application_bindings(self) -> None:
        text = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift"
        )
        for fragment in [
            "getAvailableAlternateIcons()",
            "getAlternateIconName()",
            "requestSetAlternateIconName(icon.isDefault ? nil : icon.name",
            "guard success else",
            "updateString(\\.selectedAppIcon, icon.name)",
        ]:
            self.assertIn(fragment, text)
        self.assertNotIn("ayuGramAppIconOptions", text)

    def test_badge_consumers_receive_the_active_account(self) -> None:
        app_delegate = source("submodules/TelegramUI/Sources/AppDelegate.swift")
        self.assertIn("context.context.account.peerId", app_delegate)
        self.assertIn("appearance.hideNotificationBadge", app_delegate)
        root = source("submodules/TelegramUI/Sources/TelegramRootController.swift")
        self.assertIn("accountPeerId: self.context.account.peerId", root)
        node = source("submodules/TabBarUI/Sources/TabBarContollerNode.swift")
        self.assertIn("AyuGramHooks.chatAppearance(accountPeerId: accountPeerId)", node)
        component = source(
            "submodules/TelegramUI/Components/TabBarComponent/Sources/TabBarComponent.swift"
        )
        self.assertIn("hideBadges: Bool", component)
        self.assertIn("component.hideBadges ? nil : tabBarItem.badgeValue", component)

    def test_folder_controls_use_the_node_account_context(self) -> None:
        text = source(
            "submodules/TelegramUI/Components/ChatList/"
            "ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift"
        )
        self.assertIn(
            "AyuGramHooks.chatAppearance(accountPeerId: self.context.account.peerId)",
            text,
        )
        self.assertIn("appearance.hideFolderCounters", text)
        self.assertIn("appearance.hideAllChatsFolder", text)
        self.assertNotIn("shouldHideFolderCounters?()", text)
        self.assertNotIn("shouldHideAllChatsFolder?()", text)


if __name__ == "__main__":
    unittest.main()
~~~

- [ ] **Step 2: Run the contract and verify RED**

~~~powershell
python -m unittest Tests.GRVMgramContracts.test_appearance_consumers_contract -v
~~~

Expected: FAIL because the icon row only cycles a hard-coded string and current badge/folder consumers use zero-argument hooks.

- [ ] **Step 3: Replace the string cycle with a native action-sheet picker**

Remove `ayuGramAppIconOptions`. Build the picker from the exact list returned by the application binding:

~~~swift
private func grvmAppIconPicker(
    context: AccountContext,
    updateString: @escaping (WritableKeyPath<AyuGramSettings, String>, String) -> Void
) -> ViewController {
    let presentationData = context.sharedContext.currentPresentationData.with { $0 }
    let controller = ActionSheetController(presentationData: presentationData)
    let icons = context.sharedContext.applicationBindings.getAvailableAlternateIcons()
    let currentName = context.sharedContext.applicationBindings.getAlternateIconName()
        ?? icons.first(where: \.isDefault)?.name

    let iconItems: [ActionSheetItem] = icons.map { icon in
        let title = grvmLocalizedAppIconTitle(icon.name, strings: GRVMgramStrings(presentationData))
        return ActionSheetButtonItem(
            title: icon.name == currentName ? "вњ“ \(title)" : title,
            color: .accent,
            action: { [weak controller] in
                context.sharedContext.applicationBindings.requestSetAlternateIconName(
                    icon.isDefault ? nil : icon.name
                ) { success in
                    Queue.mainQueue().async {
                        guard success else {
                            return
                        }
                        updateString(\.selectedAppIcon, icon.name)
                        controller?.dismissAnimated()
                    }
                }
            }
        )
    }
    controller.setItemGroups([
        ActionSheetItemGroup(items: iconItems),
        ActionSheetItemGroup(items: [
            ActionSheetButtonItem(
                title: presentationData.strings.Common_Cancel,
                color: .accent,
                action: { [weak controller] in controller?.dismissAnimated() }
            )
        ])
    ])
    return controller
}
~~~

`grvmLocalizedAppIconTitle` is the mapping owned by the localization plan. The item label uses `getAlternateIconName()` as system truth and treats the binding's `isDefault` icon as current when that name is nil. Do not update `selectedAppIcon` on failure.

- [ ] **Step 4: Make OS and tab badges account-aware**

In `AppDelegate.resetBadge`, retain the authorized context together with its count:

~~~swift
self.badgeDisposable.set((
    self.context.get()
    |> mapToSignal { context -> Signal<(AuthorizedApplicationContext?, Int32), NoError> in
        guard let context else {
            return .single((nil, 0))
        }
        return context.applicationBadge
        |> map { (context, $0) }
    }
    |> deliverOnMainQueue
).start(next: { context, count in
    let hideBadge: Bool
    if let context {
        hideBadge = AyuGramHooks.chatAppearance(
            accountPeerId: context.context.account.peerId
        ).appearance.hideNotificationBadge
    } else {
        hideBadge = false
    }
    UIApplication.shared.applicationIconBadgeNumber = hideBadge ? 0 : Int(count)
}))
~~~

Add an optional account to `TabBarControllerImpl` and pass it through `TabBarControllerNode`:

~~~swift
public init(
    theme: PresentationTheme,
    strings: PresentationStrings,
    accountPeerId: PeerId? = nil
)
~~~

Construct it in `TelegramRootController.addRootControllers` with:

~~~swift
let tabBarController = TabBarControllerImpl(
    theme: self.presentationData.theme,
    strings: self.presentationData.strings,
    accountPeerId: self.context.account.peerId
)
~~~

Before creating `TabBarComponent`, derive:

~~~swift
let hideBadges = self.accountPeerId.flatMap {
    AyuGramHooks.chatAppearance(accountPeerId: $0).appearance.hideNotificationCounters
} ?? false
~~~

Add `hideBadges: Bool` to `TabBarComponent` and use:

~~~swift
badgeValue = component.hideBadges ? nil : tabBarItem.badgeValue
~~~

The obsolete `TabBarNode.updateNodeBadge` path may keep its stock assignment, but it must not contain a GRVMgram hook because the current component path is authoritative.

- [ ] **Step 5: Resolve folder counters and All Chats from the node's account**

At the start of both relevant layout methods:

~~~swift
let appearance = AyuGramHooks.chatAppearance(
    accountPeerId: self.context.account.peerId
).appearance
~~~

Use `appearance.hideFolderCounters` in the badge-alpha predicate. Skip the `.all` entry only when `appearance.hideAllChatsFolder` is true and another filter remains. Preserve `.all` as the selected fallback when it is the only entry; never create an empty tab strip.

- [ ] **Step 6: Run GREEN and commit**

~~~powershell
python -m unittest Tests.GRVMgramContracts.test_appearance_consumers_contract -v
git diff --check
git add submodules/AyuGramSettingsUI/Sources/AyuGramAppearanceController.swift submodules/TelegramUI/Sources/AppDelegate.swift submodules/TelegramUI/Sources/TelegramRootController.swift submodules/TabBarUI/Sources/TabBarController.swift submodules/TabBarUI/Sources/TabBarContollerNode.swift submodules/TelegramUI/Components/TabBarComponent/Sources/TabBarComponent.swift submodules/TelegramUI/Components/ChatList/ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift Tests/GRVMgramContracts/test_appearance_consumers_contract.py
git commit -m "feat: apply account appearance to icons and counters"
~~~

Expected: three tests PASS; selecting an icon is represented by a real native request, not a stored-string cycle.

### Task 3: Apply geometry, MD3, backgrounds, fonts, and premium hiding

**Files:**
- Create: `Tests/GRVMgramContracts/test_appearance_surfaces_contract.py`
- Modify: `submodules/Display/Source/SwitchNode.swift`
- Modify: `submodules/AvatarNode/Sources/AvatarNode.swift`
- Modify: `submodules/TelegramPresentationData/Sources/ChatPresentationData.swift`
- Modify: `submodules/TelegramPresentationData/Sources/ChatMessageBubbleImages.swift`
- Modify: `submodules/ChatMessageBackground/Sources/ChatMessageBackground.swift`
- Modify: every premium-status surface listed in the File Map.

**Interfaces:**
- Consumes: `AyuGramHooks.chatAppearance(accountPeerId:)`.
- Produces: primary-account app-wide appearance plus exact-account chat/peer appearance.

- [ ] **Step 1: Write the failing surface inventory contract**

Create a path/anchor test that requires: `SwitchNode.defaultStyle`, clamped avatar and bubble radii, default-wallpaper fallback, selected fixed-width font, and `hidePremiumStatuses` checks at all eight listed surfaces. The test must reject any check that hides scam, fake, verified, or custom-verification badges.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_appearance_surfaces_contract -v
```

Expected: FAIL for single-corner, MD3, bubble-radius, and incomplete premium consumers.

- [ ] **Step 3: Implement app-wide primary-account values**

When `GRVMAccountFeatureRegistry.setPrimaryAccount` changes, publish the primary snapshot's MD3 style and default avatar shape on the main queue. `SwitchNode` and context-free avatar callers use only this published immutable value; account-aware chat/peer callers pass their explicit account peer ID.

- [ ] **Step 4: Implement exact-account chat values**

Use the chat account ID to select wallpaper, fixed-width font, bubble radius, and forum single-corner policy. Clamp before rendering and keep Telegram defaults when the setting is disabled.

- [ ] **Step 5: Complete premium hiding and run GREEN**

```powershell
python -m unittest Tests.GRVMgramContracts.test_appearance_surfaces_contract -v
git diff --check
git add submodules/Display submodules/AvatarNode submodules/TelegramPresentationData submodules/ChatMessageBackground submodules/TelegramUI submodules/ChatListUI submodules/ItemListPeerItem submodules/ContactsPeerItem Tests/GRVMgramContracts/test_appearance_surfaces_contract.py
git commit -m "feat: apply complete GRVMgram appearance policy"
```

Expected: all surface anchors pass and no non-premium trust badge is gated.

### Task 4: Filter sticker suggestions and reactions by chat type

**Files:**
- Create: `Tests/GRVMgramContracts/test_chat_controls_contract.py`
- Modify: `submodules/TelegramUI/Components/ChatEntityKeyboardInputNode/Sources/ChatEntityKeyboardInputNode.swift`
- Modify: `submodules/TelegramUI/Components/EntityKeyboard/Sources/EmojiPagerContentSignals.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift`

**Interfaces:**
- Consumes: `GRVMChatSettings.showOnlyAddedStickers`, three reaction booleans, and `recentStickersCount`.
- Produces: installed-pack-only sticker/emoji results and peer-kind reaction policy.

- [ ] **Step 1: Add failing predicate and route tests**

The contract requires installed pack-ID membership for suggested stickers, custom emoji, search, and recent items; it also requires distinct broadcast-channel, group/supergroup, and private-chat reaction branches.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v
```

- [ ] **Step 3: Reuse installed-pack signals**

Intersect candidate file pack references with the existing installed sticker/emoji pack ID sets. Preserve Telegram ordering and cap recents with the validated `1...200` value; do not hide already-selected compose content.

- [ ] **Step 4: Apply the reaction predicate and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v
git diff --check
git add submodules/TelegramUI/Components/ChatEntityKeyboardInputNode submodules/TelegramUI/Components/EntityKeyboard submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode Tests/GRVMgramContracts/test_chat_controls_contract.py
git commit -m "feat: complete sticker and reaction controls"
```

### Task 5: Implement channel modes and real Quick Admin actions

**Files:**
- Modify: `Tests/GRVMgramContracts/test_chat_controls_contract.py`
- Modify: `submodules/TelegramUI/Components/Chat/ChatChannelSubscriberInputPanelNode/Sources/ChatChannelSubscriberInputPanelNode.swift`
- Modify: `submodules/TelegramUI/Sources/ChatController.swift`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateNavigationButtons.swift`

**Interfaces:**
- Consumes: `GRVMChannelBottomButtonMode` and `quickAdminShortcuts`.
- Produces: hidden/mute/discuss behavior plus Recent Actions/Admins shortcuts.

- [ ] **Step 1: Extend the contract and verify RED**

Require three exhaustive channel-mode cases, linked-discussion navigation, mute fallback when no linked discussion exists, and two admin shortcuts. Reject the old unrelated Ban shortcut as Quick Admin parity.

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v
```

- [ ] **Step 2: Implement typed channel behavior**

`.hidden` removes the panel, `.mute` preserves the stock mute action, and `.discussWithFallback` opens the linked discussion peer/thread when available or invokes the stock mute action otherwise.

- [ ] **Step 3: Wire native admin controllers and commit**

Reuse Telegram's existing recent-actions and administrators controller factories, retaining normal permission checks.

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v
git diff --check
git add submodules/TelegramUI/Components/Chat/ChatChannelSubscriberInputPanelNode submodules/TelegramUI/Sources/ChatController.swift submodules/TelegramUI/Sources/ChatInterfaceStateNavigationButtons.swift Tests/GRVMgramContracts/test_chat_controls_contract.py
git commit -m "feat: add channel and quick-admin parity"
```

### Task 6: Finish message marks, bubbles, width, share, and replies

**Files:**
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/StringForMessageTimestampStatus.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageReplyInfoNode/Sources/ChatMessageReplyInfoNode.swift`
- Modify: `submodules/TelegramPresentationData/Sources/ChatMessageBubbleImages.swift`
- Modify: `Tests/GRVMgramContracts/test_chat_controls_contract.py`

- [ ] **Step 1: Add failing rendering/settings contracts**

Require arbitrary text-entry editors with reset actions for both marks, icon/text exclusivity, lifecycle attributes instead of SQLite, opacity exclusion for admin-log/archive subjects, radius/tail/width consumers, fast-share hiding, and colorful-reply disabling.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v
```

- [ ] **Step 3: Implement editors and rendering policy**

Use Telegram's text-input alert/editor, store arbitrary Unicode unchanged, reset deleted to `\u{1F9F9}`, and reset edited to an empty value that renders the localized fallback. Apply opacity once at the common bubble node.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v
git diff --check
git add submodules/AyuGramSettingsUI/Sources/AyuGramChatsController.swift submodules/TelegramUI/Components/Chat submodules/TelegramPresentationData/Sources/ChatMessageBubbleImages.swift Tests/GRVMgramContracts/test_chat_controls_contract.py
git commit -m "feat: finish GRVMgram message rendering controls"
```

### Task 7: Give every context-menu setting its real action

**Files:**
- Create: `submodules/TelegramUI/Sources/GRVMMessageDetailsController.swift`
- Create: `Tests/GRVMgramContracts/test_context_menu_semantics_contract.py`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift`
- Modify: `submodules/TelegramUI/Sources/ChatController.swift`
- Modify: `submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift`

**Interfaces:**
- Consumes: `GRVMContextMenuSettings` and the filter editor interface.
- Produces: local hide, author search, details, repeat, add-filter, and modifier/touch routing.

- [ ] **Step 1: Write failing action-identity tests**

Require these exact action anchors: local Postbox hide (no server delete), chat search constrained to the selected author/forward author, GRVM details controller, repeat through Telegram's enqueue/resend path, and filter editor seeded with text/dialog. Reject mappings to stock Delete, edit-info, or Send Scheduled Now.

- [ ] **Step 2: Add failing visibility routing tests**

Require `.hidden` omission, `.visible` top-level insertion, hardware Shift/Control exposure for `.visibleWithModifier`, and a single touch-only `contextMoreActions` submenu for mode-2 actions.

- [ ] **Step 3: Verify RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_context_menu_semantics_contract -v
```

- [ ] **Step 4: Implement actions with existing Telegram primitives**

Local Hide updates only local Postbox presentation state and never calls a network delete. Repeat reuses the selected message's locally available text/media enqueue path and reports unavailable media instead of silently sending an empty message. Details renders ID, dates, author/forward data, views/forwards, and media metadata.

- [ ] **Step 5: Run GREEN and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_context_menu_semantics_contract -v
git diff --check
git add submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift submodules/TelegramUI/Sources/ChatController.swift submodules/TelegramUI/Sources/GRVMMessageDetailsController.swift submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift Tests/GRVMgramContracts/test_context_menu_semantics_contract.py
git commit -m "feat: implement GRVMgram context actions"
```

### Task 8: Complete compose controls and touch popup equivalents

**Files:**
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceInputContexts.swift`
- Modify: `submodules/TelegramUI/Components/Chat/ChatTextInputPanelNode/Sources/ChatTextInputPanelNode.swift`
- Modify: `submodules/ChatPresentationInterfaceState/Sources/ChatPanelInterfaceInteraction.swift`
- Modify: `Tests/GRVMgramContracts/test_chat_controls_contract.py`

- [ ] **Step 1: Add failing producer/consumer tests**

Require consumers for Attach, Commands, TTL, Emoji, Voice, Gift, AI, long-press Attach popup, and long-press Emoji/Sticker popup. Each consumer must resolve the exact account snapshot.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v
```

- [ ] **Step 3: Reuse native long-press/context menus**

Expose Telegram's existing attachment categories from the attach-button long press and emoji/sticker/GIF modes from the emoji-button long press. Do not implement Desktop hover behavior on touch hardware.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_controls_contract -v
git diff --check
git add submodules/TelegramUI/Sources/ChatInterfaceInputContexts.swift submodules/TelegramUI/Components/Chat/ChatTextInputPanelNode submodules/ChatPresentationInterfaceState Tests/GRVMgramContracts/test_chat_controls_contract.py
git commit -m "feat: complete compose and popup controls"
```

### Task 9: Build the complete Message Shot workflow

**Files:**
- Create: `submodules/TelegramUI/Sources/GRVMMessageShotModel.swift`
- Create: `submodules/TelegramUI/Sources/GRVMMessageShotRenderer.swift`
- Create: `submodules/TelegramUI/Sources/GRVMMessageShotController.swift`
- Create: `Tests/GRVMgramContracts/test_message_shot_contract.py`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageSelectionInputPanelNode/Sources/ChatMessageSelectionInputPanelNode.swift`
- Modify: `submodules/TelegramUI/BUILD`

**Interfaces:**
- Produces: `GRVMMessageShotOptions`, deterministic model building, `render(size:scale:) -> UIImage`, copy, and Photos save.

- [ ] **Step 1: Write failing model/renderer/controller contracts**

Require chronological selected messages; sender/header/date; text/entities; reply previews and colorful-reply toggle; media placeholders; reactions toggle; spoiler reveal/conceal; background/theme; header decorations; deterministic canvas bounds; copy; Photos authorization/save; and user-visible errors.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest Tests.GRVMgramContracts.test_message_shot_contract -v
```

- [ ] **Step 3: Build the immutable model**

Read selected messages from Postbox once, sort by `MessageIndex`, resolve reply messages in the same transaction, and represent unavailable media explicitly. The model contains no view nodes and is independently renderable.

- [ ] **Step 4: Render and expose preview options**

Use `UIGraphicsImageRenderer`/Core Graphics with bounded width, theme colors, text layout, reply/media/reaction rows, and spoiler policy. The controller updates preview when options change without requerying Postbox.

- [ ] **Step 5: Add copy/save and selection entry point**

Copy the rendered PNG/image to `UIPasteboard`; request add-only Photos permission before saving and surface denial/failure. Show the action only for non-empty selection when the account flag is enabled.

- [ ] **Step 6: Run GREEN and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_message_shot_contract -v
git diff --check
git add submodules/TelegramUI/Sources/GRVMMessageShotModel.swift submodules/TelegramUI/Sources/GRVMMessageShotRenderer.swift submodules/TelegramUI/Sources/GRVMMessageShotController.swift submodules/TelegramUI/Components/Chat/ChatMessageSelectionInputPanelNode submodules/TelegramUI/BUILD Tests/GRVMgramContracts/test_message_shot_contract.py
git commit -m "feat: add complete Message Shot workflow"
```

### Task 10: Run the complete Chat/Appearance parity gate

**Files:**
- Verify all files in this plan.

- [ ] **Step 1: Run every focused contract together**

```powershell
python -m unittest Tests.GRVMgramContracts.test_chat_appearance_settings_contract Tests.GRVMgramContracts.test_appearance_consumers_contract Tests.GRVMgramContracts.test_appearance_surfaces_contract Tests.GRVMgramContracts.test_chat_controls_contract Tests.GRVMgramContracts.test_context_menu_semantics_contract Tests.GRVMgramContracts.test_message_shot_contract -v
```

- [ ] **Step 2: Verify lifecycle and localization ownership boundaries**

```powershell
rg -n "GRVMDeletedMessageAttribute|GRVMEditHistoryMessageAttribute|grvmDeletedMessagesController|grvmMessageHistoryController" submodules/TelegramUI submodules/AyuGramSettingsUI
rg -n "AyuGramHooks\.(shouldUseMD3Switches|avatarCornerRadius|messageBubbleRadius|contextMenu|shouldShowAttachButton)" submodules -g "*.swift"
git diff --check
```

Expected: lifecycle interfaces have consumers; targeted legacy zero-argument appearance/chat hooks have no consumers; diff check passes.

- [ ] **Step 3: Request subsystem review and commit only fixes**

Review against the Canonical Coverage Ledger. Any fix gets its own focused test and commit; do not trigger CI from this plan.
