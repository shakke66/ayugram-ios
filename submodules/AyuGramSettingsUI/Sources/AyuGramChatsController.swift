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
    let pushController: (ViewController) -> Void
    let updateBool: (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void
    let updateString: (WritableKeyPath<AyuGramSettings, String>, String) -> Void
    let updateInt32: (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void
    let updateDouble: (WritableKeyPath<AyuGramSettings, Double>, Double) -> Void

    init(context: AccountContext, pushController: @escaping (ViewController) -> Void, updateBool: @escaping (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void, updateString: @escaping (WritableKeyPath<AyuGramSettings, String>, String) -> Void, updateInt32: @escaping (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void, updateDouble: @escaping (WritableKeyPath<AyuGramSettings, Double>, Double) -> Void) {
        self.context = context
        self.pushController = pushController
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
    case showPrivateReactions(PresentationTheme, Bool)
    case recentStickersCount(PresentationTheme, String, Int32)
    case channelsHeader(PresentationTheme)
    case quickAdmin(PresentationTheme, Bool)
    case channelBottomButton(PresentationTheme, String, Int32)
    case messagesHeader(PresentationTheme)
    case showDeletedMark(PresentationTheme, Bool)
    case showEditedMark(PresentationTheme, Bool)
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
    case showAddFilter(PresentationTheme, String, Int32)
    case messageFieldHeader(PresentationTheme)
    case showAttach(PresentationTheme, Bool)
    case showTTL(PresentationTheme, Bool)
    case showEmoji(PresentationTheme, Bool)
    case showVoice(PresentationTheme, Bool)
    case showGift(PresentationTheme, Bool)
    case showAiEditor(PresentationTheme, Bool)

    var section: ItemListSectionId {
        switch self {
        case .stickersHeader, .onlyAddedStickers, .showChannelReactions, .showGroupReactions, .showPrivateReactions, .recentStickersCount: return AyuGramChatsSection.stickers.rawValue
        case .channelsHeader, .quickAdmin, .channelBottomButton: return AyuGramChatsSection.channels.rawValue
        case .messagesHeader, .showDeletedMark, .showEditedMark, .deletedMark, .editedMark, .replaceWithIcons, .hideFastShare, .disableColoredReplies, .messageWidth, .semiTransparentDeleted: return AyuGramChatsSection.messages.rawValue
        case .contextMenuHeader, .showReactionsPanel, .showViewsPanel, .showHideMessage, .showUserMessages, .showMessageDetails, .showRepeatMessage, .showAddFilter: return AyuGramChatsSection.contextMenu.rawValue
        case .messageFieldHeader, .showAttach, .showTTL, .showEmoji, .showVoice, .showGift, .showAiEditor: return AyuGramChatsSection.messageField.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .stickersHeader: return 0
        case .onlyAddedStickers: return 1
        case .showChannelReactions: return 2
        case .showGroupReactions: return 3
        case .showPrivateReactions: return 4
        case .recentStickersCount: return 5
        case .channelsHeader: return 6
        case .quickAdmin: return 7
        case .channelBottomButton: return 8
        case .messagesHeader: return 9
        case .showDeletedMark: return 10
        case .showEditedMark: return 11
        case .replaceWithIcons: return 12
        case .deletedMark: return 13
        case .editedMark: return 14
        case .hideFastShare: return 15
        case .disableColoredReplies: return 16
        case .messageWidth: return 17
        case .semiTransparentDeleted: return 18
        case .contextMenuHeader: return 19
        case .showReactionsPanel: return 20
        case .showViewsPanel: return 21
        case .showHideMessage: return 22
        case .showUserMessages: return 23
        case .showMessageDetails: return 24
        case .showRepeatMessage: return 25
        case .showAddFilter: return 26
        case .messageFieldHeader: return 27
        case .showAttach: return 28
        case .showTTL: return 29
        case .showEmoji: return 30
        case .showVoice: return 31
        case .showGift: return 32
        case .showAiEditor: return 33
        }
    }

    static func ==(lhs: AyuGramChatsEntry, rhs: AyuGramChatsEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.onlyAddedStickers(_, lv), .onlyAddedStickers(_, rv)): return lv == rv
        case let (.showChannelReactions(_, lv), .showChannelReactions(_, rv)): return lv == rv
        case let (.showGroupReactions(_, lv), .showGroupReactions(_, rv)): return lv == rv
        case let (.showPrivateReactions(_, lv), .showPrivateReactions(_, rv)): return lv == rv
        case let (.recentStickersCount(_, _, lv), .recentStickersCount(_, _, rv)): return lv == rv
        case let (.quickAdmin(_, lv), .quickAdmin(_, rv)): return lv == rv
        case let (.channelBottomButton(_, _, lv), .channelBottomButton(_, _, rv)): return lv == rv
        case let (.showDeletedMark(_, lv), .showDeletedMark(_, rv)): return lv == rv
        case let (.showEditedMark(_, lv), .showEditedMark(_, rv)): return lv == rv
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
        case let (.showAddFilter(_, _, lv), .showAddFilter(_, _, rv)): return lv == rv
        case let (.showAttach(_, lv), .showAttach(_, rv)): return lv == rv
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
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case .stickersHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.stickersHeader], sectionId: self.section)
        case let .onlyAddedStickers(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.stickersOnlyAdded], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showOnlyAddedStickers, v) })
        case let .showChannelReactions(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.stickersChannelReactions], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showChannelReactions, v) })
        case let .showGroupReactions(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.stickersGroupReactions], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showGroupReactions, v) })
        case let .showPrivateReactions(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.stickersPrivateReactions], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showPrivateReactions, v) })
        case let .recentStickersCount(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.stickersRecent], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramRecentStickersCountController(context: arguments.context, currentValue: value, onSelect: {
                    arguments.updateInt32(\.recentStickersCount, $0)
                }))
            })
        case .channelsHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.channelsHeader], sectionId: self.section)
        case let .quickAdmin(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.channelsQuickAdmin], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.quickAdminShortcuts, v) })
        case let .channelBottomButton(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.channelsBottomButton], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramChannelBottomButtonController(context: arguments.context, currentValue: value, onSelect: {
                    arguments.updateInt32(\.channelBottomButton, $0)
                }))
            })
        case .messagesHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.messagesHeader], sectionId: self.section)
        case let .showDeletedMark(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.deletedMarkVisible], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showDeletedMark, v) })
        case let .showEditedMark(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.editedMarkVisible], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showEditedMark, v) })
        case let .replaceWithIcons(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.messagesIcons], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.replaceMarksWithIcons, v) })
        case let .deletedMark(theme, value):
            return ItemListSingleLineInputItem(
                context: arguments.context,
                presentationData: presentationData,
                title: NSAttributedString(string: strings[.deletedMark], textColor: theme.list.itemPrimaryTextColor),
                text: value,
                placeholder: strings[.deletedMarkPrompt],
                type: .regular(capitalization: false, autocorrection: false),
                clearType: .always,
                sectionId: self.section,
                textUpdated: { value in arguments.updateString(\.deletedMessageMark, value) },
                action: {},
                cleared: { arguments.updateString(\.deletedMessageMark, strings[.deletedMarkDefault]) }
            )
        case let .editedMark(theme, value):
            return ItemListSingleLineInputItem(
                context: arguments.context,
                presentationData: presentationData,
                title: NSAttributedString(string: strings[.editedMark], textColor: theme.list.itemPrimaryTextColor),
                text: value.isEmpty ? strings[.editedMarkDefault] : value,
                placeholder: strings[.editedMarkPrompt],
                type: .regular(capitalization: false, autocorrection: false),
                clearType: .always,
                sectionId: self.section,
                textUpdated: { value in arguments.updateString(\.editedMessageMark, value) },
                action: {},
                cleared: { arguments.updateString(\.editedMessageMark, "") }
            )
        case let .hideFastShare(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.messagesFastShare], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideFastShareButton, v) })
        case let .disableColoredReplies(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.messagesColoredReplies], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.disableColoredReplies, v) })
        case let .messageWidth(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.messagesWidth], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.updateDouble(\.messageWidthMultiplier, [1.0, 1.25, 1.5, 2.0][(([1.0, 1.25, 1.5, 2.0].firstIndex(where: { abs($0 - value) < 0.001 }) ?? -1) + 1) % 4])
            })
        case let .semiTransparentDeleted(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.messagesTranslucent], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.semiTransparentDeletedMessages, v) })
        case .contextMenuHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.contextHeader], sectionId: self.section)
        case let .showReactionsPanel(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.contextReactions], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showReactionsPanelInContextMenu, (value + 1) % 3)
            })
        case let .showViewsPanel(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.contextViews], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showViewsPanelInContextMenu, (value + 1) % 3)
            })
        case let .showHideMessage(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.contextHide], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showHideMessageInContextMenu, (value + 1) % 3)
            })
        case let .showUserMessages(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.contextUserMessages], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showUserMessagesInContextMenu, (value + 1) % 3)
            })
        case let .showMessageDetails(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.contextDetails], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showMessageDetailsInContextMenu, (value + 1) % 3)
            })
        case let .showRepeatMessage(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.contextRepeat], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showRepeatMessageInContextMenu, (value + 1) % 3)
            })
        case let .showAddFilter(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.contextAddFilter], label: label, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showAddFilterInContextMenu, (value + 1) % 3)
            })
        case .messageFieldHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.fieldHeader], sectionId: self.section)
        case let .showAttach(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.fieldAttach], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showAttachButton, v) })
        case let .showTTL(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.fieldTtl], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showTTLButton, v) })
        case let .showEmoji(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.fieldEmoji], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showEmojiButton, v) })
        case let .showVoice(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.fieldVoice], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showVoiceButton, v) })
        case let .showGift(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.fieldGift], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showGiftButton, v) })
        case let .showAiEditor(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.fieldAi], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showAiEditorButton, v) })
        }
    }
}

private func ayuGramChatsEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramChatsEntry] {
    let strings = GRVMgramStrings(presentationData.strings)
    let recentStickersLabel = "\(min(200, max(1, settings.recentStickersCount)))"
    let normalizedChannelBottomButton = grvmNormalizedChannelBottomButtonValue(settings.channelBottomButton)
    let channelBottomLabel = normalizedChannelBottomButton == 1 ? strings[.channelsBottomDiscuss] : strings[.channelsBottomHide]
    let messageWidthLabel = String(format: "%.2f", settings.messageWidthMultiplier)
    let contextMenuLabels = [strings[.commonHidden], strings[.commonShown], strings[.commonWithModifier]]
    let reactionsPanelLabel = settings.showReactionsPanelInContextMenu >= 0 && settings.showReactionsPanelInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showReactionsPanelInContextMenu)] : strings[.commonHidden]
    let viewsPanelLabel = settings.showViewsPanelInContextMenu >= 0 && settings.showViewsPanelInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showViewsPanelInContextMenu)] : strings[.commonHidden]
    let hideMessageLabel = settings.showHideMessageInContextMenu >= 0 && settings.showHideMessageInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showHideMessageInContextMenu)] : strings[.commonHidden]
    let userMessagesLabel = settings.showUserMessagesInContextMenu >= 0 && settings.showUserMessagesInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showUserMessagesInContextMenu)] : strings[.commonHidden]
    let messageDetailsLabel = settings.showMessageDetailsInContextMenu >= 0 && settings.showMessageDetailsInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showMessageDetailsInContextMenu)] : strings[.commonHidden]
    let repeatMessageLabel = settings.showRepeatMessageInContextMenu >= 0 && settings.showRepeatMessageInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showRepeatMessageInContextMenu)] : strings[.commonHidden]
    let addFilterLabel = settings.showAddFilterInContextMenu >= 0 && settings.showAddFilterInContextMenu < Int32(contextMenuLabels.count) ? contextMenuLabels[Int(settings.showAddFilterInContextMenu)] : strings[.commonHidden]

    var entries: [AyuGramChatsEntry] = []
    entries.append(.stickersHeader(presentationData.theme))
    entries.append(.onlyAddedStickers(presentationData.theme, settings.showOnlyAddedStickers))
    entries.append(.showChannelReactions(presentationData.theme, settings.showChannelReactions))
    entries.append(.showGroupReactions(presentationData.theme, settings.showGroupReactions))
    entries.append(.showPrivateReactions(presentationData.theme, settings.showPrivateReactions))
    entries.append(.recentStickersCount(presentationData.theme, recentStickersLabel, settings.recentStickersCount))
    entries.append(.channelsHeader(presentationData.theme))
    entries.append(.quickAdmin(presentationData.theme, settings.quickAdminShortcuts))
    entries.append(.channelBottomButton(presentationData.theme, channelBottomLabel, normalizedChannelBottomButton))
    entries.append(.messagesHeader(presentationData.theme))
    entries.append(.showDeletedMark(presentationData.theme, settings.showDeletedMark))
    entries.append(.showEditedMark(presentationData.theme, settings.showEditedMark))
    entries.append(.replaceWithIcons(presentationData.theme, settings.replaceMarksWithIcons))
    if !settings.replaceMarksWithIcons {
        entries.append(.deletedMark(presentationData.theme, settings.deletedMessageMark))
        entries.append(.editedMark(presentationData.theme, settings.editedMessageMark))
    }
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
    entries.append(.showAddFilter(presentationData.theme, addFilterLabel, settings.showAddFilterInContextMenu))
    entries.append(.messageFieldHeader(presentationData.theme))
    entries.append(.showAttach(presentationData.theme, settings.showAttachButton))
    entries.append(.showTTL(presentationData.theme, settings.showTTLButton))
    entries.append(.showEmoji(presentationData.theme, settings.showEmojiButton))
    entries.append(.showVoice(presentationData.theme, settings.showVoiceButton))
    entries.append(.showGift(presentationData.theme, settings.showGiftButton))
    entries.append(.showAiEditor(presentationData.theme, settings.showAiEditorButton))
    return entries
}

public func ayuGramChatsController(context: AccountContext) -> ViewController {
    var pushControllerImpl: ((ViewController) -> Void)?
    let arguments = AyuGramChatsArguments(
        context: context,
        pushController: { controller in
            pushControllerImpl?(controller)
        },
        updateBool: { keyPath, value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateString: { keyPath, value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateInt32: { keyPath, value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateDouble: { keyPath, value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, grvmSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let entries = ayuGramChatsEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text(strings[.chatsTitle]), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    let controller = ItemListController(context: context, state: signal)
    pushControllerImpl = { [weak controller] child in
        controller?.push(child)
    }
    return controller
}
