import Foundation
import UIKit
import Display
import SwiftSignalKit
import Postbox
import TelegramCore
import TelegramPresentationData
import TelegramUIPreferences
import ItemListUI
import PresentationDataUtils
import AccountContext
import AyuGramLib

private final class AyuGramChatsArguments {
    let context: AccountContext
    let updateBool: (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void
    let updateString: (WritableKeyPath<AyuGramSettings, String>, String) -> Void
    let updateInt32: (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void
    let updateDouble: (WritableKeyPath<AyuGramSettings, Double>, Double) -> Void

    init(context: AccountContext, updateBool: @escaping (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void, updateString: @escaping (WritableKeyPath<AyuGramSettings, String>, String) -> Void, updateInt32: @escaping (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void, updateDouble: @escaping (WritableKeyPath<AyuGramSettings, Double>, Double) -> Void) {
        self.context = context
        self.updateBool = updateBool
        self.updateString = updateString
        self.updateInt32 = updateInt32
        self.updateDouble = updateDouble
    }
}

private enum AyuGramChatsSection: Int32 {
    case stickers
    case channels
    case messages
    case contextMenu
    case messageField
}

private enum AyuGramChatsEntry: ItemListNodeEntry {
    case stickersHeader(PresentationTheme)
    case onlyAddedStickers(PresentationTheme, Bool)
    case showChannelReactions(PresentationTheme, Bool)
    case showGroupReactions(PresentationTheme, Bool)
    case recentStickersCount(PresentationTheme, String, Int32)
    case channelsHeader(PresentationTheme)
    case quickAdmin(PresentationTheme, Bool)
    case messageShot(PresentationTheme, Bool)
    case channelBottomButton(PresentationTheme, String, Int32)
    case messagesHeader(PresentationTheme)
    case deletedMark(PresentationTheme, String)
    case editedMark(PresentationTheme, String)
    case replaceWithIcons(PresentationTheme, Bool)
    case hideFastShare(PresentationTheme, Bool)
    case disableColoredReplies(PresentationTheme, Bool)
    case messageWidth(PresentationTheme, String, Double)
    case semiTransparentDeleted(PresentationTheme, Bool)
    case contextMenuHeader(PresentationTheme)
    case showReactionsPanel(PresentationTheme, String, Int32)
    case showViewsPanel(PresentationTheme, String, Int32)
    case showHideMessage(PresentationTheme, String, Int32)
    case showUserMessages(PresentationTheme, String, Int32)
    case showMessageDetails(PresentationTheme, String, Int32)
    case showRepeatMessage(PresentationTheme, String, Int32)
    case messageFieldHeader(PresentationTheme)
    case showAttach(PresentationTheme, Bool)
    case showCommands(PresentationTheme, Bool)
    case showTTL(PresentationTheme, Bool)
    case showEmoji(PresentationTheme, Bool)
    case showVoice(PresentationTheme, Bool)
    case showGift(PresentationTheme, Bool)
    case showAiEditor(PresentationTheme, Bool)

    var section: ItemListSectionId {
        switch self {
        case .stickersHeader, .onlyAddedStickers, .showChannelReactions, .showGroupReactions, .recentStickersCount: return AyuGramChatsSection.stickers.rawValue
        case .channelsHeader, .quickAdmin, .messageShot, .channelBottomButton: return AyuGramChatsSection.channels.rawValue
        case .messagesHeader, .deletedMark, .editedMark, .replaceWithIcons, .hideFastShare, .disableColoredReplies, .messageWidth, .semiTransparentDeleted: return AyuGramChatsSection.messages.rawValue
        case .contextMenuHeader, .showReactionsPanel, .showViewsPanel, .showHideMessage, .showUserMessages, .showMessageDetails, .showRepeatMessage: return AyuGramChatsSection.contextMenu.rawValue
        case .messageFieldHeader, .showAttach, .showCommands, .showTTL, .showEmoji, .showVoice, .showGift, .showAiEditor: return AyuGramChatsSection.messageField.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .stickersHeader: return 0
        case .onlyAddedStickers: return 1
        case .showChannelReactions: return 2
        case .showGroupReactions: return 3
        case .recentStickersCount: return 4
        case .channelsHeader: return 5
        case .quickAdmin: return 6
        case .messageShot: return 7
        case .channelBottomButton: return 8
        case .messagesHeader: return 9
        case .deletedMark: return 10
        case .editedMark: return 11
        case .replaceWithIcons: return 12
        case .hideFastShare: return 13
        case .disableColoredReplies: return 14
        case .messageWidth: return 15
        case .semiTransparentDeleted: return 16
        case .contextMenuHeader: return 17
        case .showReactionsPanel: return 18
        case .showViewsPanel: return 19
        case .showHideMessage: return 20
        case .showUserMessages: return 21
        case .showMessageDetails: return 22
        case .showRepeatMessage: return 23
        case .messageFieldHeader: return 24
        case .showAttach: return 25
        case .showCommands: return 26
        case .showTTL: return 27
        case .showEmoji: return 28
        case .showVoice: return 29
        case .showGift: return 30
        case .showAiEditor: return 31
        }
    }

    static func ==(lhs: AyuGramChatsEntry, rhs: AyuGramChatsEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.onlyAddedStickers(_, lv), .onlyAddedStickers(_, rv)): return lv == rv
        case let (.showChannelReactions(_, lv), .showChannelReactions(_, rv)): return lv == rv
        case let (.showGroupReactions(_, lv), .showGroupReactions(_, rv)): return lv == rv
        case let (.recentStickersCount(_, _, lv), .recentStickersCount(_, _, rv)): return lv == rv
        case let (.quickAdmin(_, lv), .quickAdmin(_, rv)): return lv == rv
        case let (.messageShot(_, lv), .messageShot(_, rv)): return lv == rv
        case let (.channelBottomButton(_, _, lv), .channelBottomButton(_, _, rv)): return lv == rv
        case let (.replaceWithIcons(_, lv), .replaceWithIcons(_, rv)): return lv == rv
        case let (.hideFastShare(_, lv), .hideFastShare(_, rv)): return lv == rv
        case let (.disableColoredReplies(_, lv), .disableColoredReplies(_, rv)): return lv == rv
        case let (.messageWidth(_, _, lv), .messageWidth(_, _, rv)): return lv == rv
        case let (.semiTransparentDeleted(_, lv), .semiTransparentDeleted(_, rv)): return lv == rv
        case let (.showReactionsPanel(_, _, lv), .showReactionsPanel(_, _, rv)): return lv == rv
        case let (.showViewsPanel(_, _, lv), .showViewsPanel(_, _, rv)): return lv == rv
        case let (.showHideMessage(_, _, lv), .showHideMessage(_, _, rv)): return lv == rv
        case let (.showUserMessages(_, _, lv), .showUserMessages(_, _, rv)): return lv == rv
        case let (.showMessageDetails(_, _, lv), .showMessageDetails(_, _, rv)): return lv == rv
        case let (.showRepeatMessage(_, _, lv), .showRepeatMessage(_, _, rv)): return lv == rv
        case let (.showAttach(_, lv), .showAttach(_, rv)): return lv == rv
        case let (.showCommands(_, lv), .showCommands(_, rv)): return lv == rv
        case let (.showTTL(_, lv), .showTTL(_, rv)): return lv == rv
        case let (.showEmoji(_, lv), .showEmoji(_, rv)): return lv == rv
        case let (.showVoice(_, lv), .showVoice(_, rv)): return lv == rv
        case let (.showGift(_, lv), .showGift(_, rv)): return lv == rv
        case let (.showAiEditor(_, lv), .showAiEditor(_, rv)): return lv == rv
        case let (.deletedMark(_, lv), .deletedMark(_, rv)): return lv == rv
        case let (.editedMark(_, lv), .editedMark(_, rv)): return lv == rv
        default: return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramChatsEntry, rhs: AyuGramChatsEntry) -> Bool { lhs.stableId < rhs.stableId }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramChatsArguments
        switch self {
        case .stickersHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Stickers & Emoji", sectionId: self.section)
        case let .onlyAddedStickers(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Show Only Added Stickers", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showOnlyAddedStickers, v) })
        case let .showChannelReactions(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Show Channel Reactions", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showChannelReactions, v) })
        case let .showGroupReactions(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Show Group Reactions", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showGroupReactions, v) })
        case let .recentStickersCount(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Recent Stickers Count", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.recentStickersCount, [20, 50, 100, 200][(([20, 50, 100, 200].firstIndex(of: value) ?? -1) + 1) % 4])
            })
        case .channelsHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Groups & Channels", sectionId: self.section)
        case let .quickAdmin(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Quick Admin Shortcuts", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.quickAdminShortcuts, v) })
        case let .messageShot(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Message Shot Feature", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.messageShotFeature, v) })
        case let .channelBottomButton(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Channel Bottom Button", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.channelBottomButton, (value + 1) % 3)
            })
        case .messagesHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Messages", sectionId: self.section)
        case let .deletedMark(_, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Deleted Mark", label: value, sectionId: self.section, style: .blocks, action: {
                let presets = ["\u{1F480}", "\u{1F5D1}", "\u{274C}", "\u{1F6AB}"]
                let idx = presets.firstIndex(of: value) ?? -1
                arguments.updateString(\.deletedMessageMark, presets[(idx + 1) % presets.count])
            })
        case let .editedMark(_, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Edited Mark", label: value, sectionId: self.section, style: .blocks, action: {
                let presets = ["edited", "\u{270F}\u{FE0F}", "(ред.)"]
                let idx = presets.firstIndex(of: value) ?? -1
                arguments.updateString(\.editedMessageMark, presets[(idx + 1) % presets.count])
            })
        case let .replaceWithIcons(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Replace with Icons", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.replaceMarksWithIcons, v) })
        case let .hideFastShare(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Hide Fast Share Button", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideFastShareButton, v) })
        case let .disableColoredReplies(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Disable Colored Replies", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.disableColoredReplies, v) })
        case let .messageWidth(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Message Width", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateDouble(\.messageWidthMultiplier, [1.0, 1.25, 1.5, 2.0][(([1.0, 1.25, 1.5, 2.0].firstIndex(where: { abs($0 - value) < 0.001 }) ?? -1) + 1) % 4])
            })
        case let .semiTransparentDeleted(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Semi-transparent Deleted", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.semiTransparentDeletedMessages, v) })
        case .contextMenuHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Context Menu Elements", sectionId: self.section)
        case let .showReactionsPanel(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Reactions Panel", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showReactionsPanelInContextMenu, (value + 1) % 3)
            })
        case let .showViewsPanel(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Views Panel", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showViewsPanelInContextMenu, (value + 1) % 3)
            })
        case let .showHideMessage(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Hide Message", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showHideMessageInContextMenu, (value + 1) % 3)
            })
        case let .showUserMessages(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "User's Messages", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showUserMessagesInContextMenu, (value + 1) % 3)
            })
        case let .showMessageDetails(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Message Details", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showMessageDetailsInContextMenu, (value + 1) % 3)
            })
        case let .showRepeatMessage(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Repeat Message", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showRepeatMessageInContextMenu, (value + 1) % 3)
            })
        case .messageFieldHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Message Field Elements", sectionId: self.section)
        case let .showAttach(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Attachment", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showAttachButton, v) })
        case let .showCommands(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Commands", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showCommandsButton, v) })
        case let .showTTL(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "TTL", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showTTLButton, v) })
        case let .showEmoji(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Emoji & Stickers", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showEmojiButton, v) })
        case let .showVoice(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Voice Recording", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showVoiceButton, v) })
        case let .showGift(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Gift", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showGiftButton, v) })
        case let .showAiEditor(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "AI Editor", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showAiEditorButton, v) })
        }
    }
}

private func ayuGramChatsEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramChatsEntry] {
    let recentStickersLabel = "\(settings.recentStickersCount)"
    let channelBottomLabels = ["Hidden", "Mute/Unmute", "Discuss"]
    let channelBottomLabel = settings.channelBottomButton < Int32(channelBottomLabels.count) ? channelBottomLabels[Int(settings.channelBottomButton)] : "Hidden"
    let messageWidthLabel = String(format: "%.2f", settings.messageWidthMultiplier)
    let contextMenuLabels = ["Hidden", "Shown", "With Modifier"]
    let reactionsPanelLabel = settings.showReactionsPanelInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showReactionsPanelInContextMenu)] : "Hidden"
    let viewsPanelLabel = settings.showViewsPanelInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showViewsPanelInContextMenu)] : "Hidden"
    let hideMessageLabel = settings.showHideMessageInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showHideMessageInContextMenu)] : "Hidden"
    let userMessagesLabel = settings.showUserMessagesInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showUserMessagesInContextMenu)] : "Hidden"
    let messageDetailsLabel = settings.showMessageDetailsInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showMessageDetailsInContextMenu)] : "Hidden"
    let repeatMessageLabel = settings.showRepeatMessageInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showRepeatMessageInContextMenu)] : "Hidden"

    var entries: [AyuGramChatsEntry] = []
    entries.append(.stickersHeader(presentationData.theme))
    entries.append(.onlyAddedStickers(presentationData.theme, settings.showOnlyAddedStickers))
    entries.append(.showChannelReactions(presentationData.theme, settings.showChannelReactions))
    entries.append(.showGroupReactions(presentationData.theme, settings.showGroupReactions))
    entries.append(.recentStickersCount(presentationData.theme, recentStickersLabel, settings.recentStickersCount))
    entries.append(.channelsHeader(presentationData.theme))
    entries.append(.quickAdmin(presentationData.theme, settings.quickAdminShortcuts))
    entries.append(.messageShot(presentationData.theme, settings.messageShotFeature))
    entries.append(.channelBottomButton(presentationData.theme, channelBottomLabel, settings.channelBottomButton))
    entries.append(.messagesHeader(presentationData.theme))
    entries.append(.deletedMark(presentationData.theme, settings.deletedMessageMark))
    entries.append(.editedMark(presentationData.theme, settings.editedMessageMark))
    entries.append(.replaceWithIcons(presentationData.theme, settings.replaceMarksWithIcons))
    entries.append(.hideFastShare(presentationData.theme, settings.hideFastShareButton))
    entries.append(.disableColoredReplies(presentationData.theme, settings.disableColoredReplies))
    entries.append(.messageWidth(presentationData.theme, messageWidthLabel, settings.messageWidthMultiplier))
    entries.append(.semiTransparentDeleted(presentationData.theme, settings.semiTransparentDeletedMessages))
    entries.append(.contextMenuHeader(presentationData.theme))
    entries.append(.showReactionsPanel(presentationData.theme, reactionsPanelLabel, settings.showReactionsPanelInContextMenu))
    entries.append(.showViewsPanel(presentationData.theme, viewsPanelLabel, settings.showViewsPanelInContextMenu))
    entries.append(.showHideMessage(presentationData.theme, hideMessageLabel, settings.showHideMessageInContextMenu))
    entries.append(.showUserMessages(presentationData.theme, userMessagesLabel, settings.showUserMessagesInContextMenu))
    entries.append(.showMessageDetails(presentationData.theme, messageDetailsLabel, settings.showMessageDetailsInContextMenu))
    entries.append(.showRepeatMessage(presentationData.theme, repeatMessageLabel, settings.showRepeatMessageInContextMenu))
    entries.append(.messageFieldHeader(presentationData.theme))
    entries.append(.showAttach(presentationData.theme, settings.showAttachButton))
    entries.append(.showCommands(presentationData.theme, settings.showCommandsButton))
    entries.append(.showTTL(presentationData.theme, settings.showTTLButton))
    entries.append(.showEmoji(presentationData.theme, settings.showEmojiButton))
    entries.append(.showVoice(presentationData.theme, settings.showVoiceButton))
    entries.append(.showGift(presentationData.theme, settings.showGiftButton))
    entries.append(.showAiEditor(presentationData.theme, settings.showAiEditorButton))
    return entries
}

public func ayuGramChatsController(context: AccountContext) -> ViewController {
    let arguments = AyuGramChatsArguments(
        context: context,
        updateBool: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateString: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateInt32: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateDouble: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, ayuGramSettings(accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuGramChatsEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Chats"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    return ItemListController(context: context, state: signal)
}
