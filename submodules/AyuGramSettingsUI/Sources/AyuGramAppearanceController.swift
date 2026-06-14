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

private final class AyuGramAppearanceArguments {
    let context: AccountContext
    let updateBool: (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void
    let updateInt32: (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void
    let updateString: (WritableKeyPath<AyuGramSettings, String>, String) -> Void

    init(context: AccountContext, updateBool: @escaping (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void, updateInt32: @escaping (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void, updateString: @escaping (WritableKeyPath<AyuGramSettings, String>, String) -> Void) {
        self.context = context
        self.updateBool = updateBool
        self.updateInt32 = updateInt32
        self.updateString = updateString
    }
}

private enum AyuGramAppearanceSection: Int32 {
    case appIcon
    case appearance
    case folders
    case drawer
}

private let ayuGramAppIconOptions: [String] = ["default", "Black", "BlackClassic", "BlackFilled", "Blue", "BlueClassic", "BlueFilled", "WhiteFilled", "New1", "New2"]

private enum AyuGramAppearanceEntry: ItemListNodeEntry {
    case appIconHeader(PresentationTheme)
    case appIcon(PresentationTheme, String)
    case hideNotificationBadge(PresentationTheme, Bool)
    case hideNotificationCounters(PresentationTheme, Bool)
    case appearanceHeader(PresentationTheme)
    case md3Switches(PresentationTheme, Bool)
    case removeBubbleTail(PresentationTheme, Bool)
    case disableCustomBg(PresentationTheme, Bool)
    case codeFont(PresentationTheme, String)
    case avatarCorners(PresentationTheme, String, Int32)
    case messageBubbleRadius(PresentationTheme, String, Int32)
    case singleCornerRadius(PresentationTheme, Bool)
    case hidePremiumStatuses(PresentationTheme, Bool)
    case foldersHeader(PresentationTheme)
    case hideFolderCounters(PresentationTheme, Bool)
    case hideAllChats(PresentationTheme, Bool)
    case drawerHeader(PresentationTheme)
    case ghostInDrawer(PresentationTheme, Bool)
    case streamerInDrawer(PresentationTheme, Bool)

    var section: ItemListSectionId {
        switch self {
        case .appIconHeader, .appIcon, .hideNotificationBadge, .hideNotificationCounters: return AyuGramAppearanceSection.appIcon.rawValue
        case .appearanceHeader, .md3Switches, .removeBubbleTail, .disableCustomBg, .codeFont, .avatarCorners, .messageBubbleRadius, .singleCornerRadius, .hidePremiumStatuses: return AyuGramAppearanceSection.appearance.rawValue
        case .foldersHeader, .hideFolderCounters, .hideAllChats: return AyuGramAppearanceSection.folders.rawValue
        case .drawerHeader, .ghostInDrawer, .streamerInDrawer: return AyuGramAppearanceSection.drawer.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .appIconHeader: return 0
        case .appIcon: return 1
        case .hideNotificationBadge: return 2
        case .hideNotificationCounters: return 3
        case .appearanceHeader: return 4
        case .md3Switches: return 5
        case .removeBubbleTail: return 6
        case .disableCustomBg: return 7
        case .codeFont: return 8
        case .avatarCorners: return 9
        case .messageBubbleRadius: return 10
        case .singleCornerRadius: return 11
        case .hidePremiumStatuses: return 12
        case .foldersHeader: return 13
        case .hideFolderCounters: return 14
        case .hideAllChats: return 15
        case .drawerHeader: return 16
        case .ghostInDrawer: return 17
        case .streamerInDrawer: return 18
        }
    }

    static func ==(lhs: AyuGramAppearanceEntry, rhs: AyuGramAppearanceEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.appIcon(_, lv), .appIcon(_, rv)): return lv == rv
        case let (.hideNotificationBadge(_, lv), .hideNotificationBadge(_, rv)): return lv == rv
        case let (.hideNotificationCounters(_, lv), .hideNotificationCounters(_, rv)): return lv == rv
        case let (.md3Switches(_, lv), .md3Switches(_, rv)): return lv == rv
        case let (.removeBubbleTail(_, lv), .removeBubbleTail(_, rv)): return lv == rv
        case let (.disableCustomBg(_, lv), .disableCustomBg(_, rv)): return lv == rv
        case let (.hideFolderCounters(_, lv), .hideFolderCounters(_, rv)): return lv == rv
        case let (.hideAllChats(_, lv), .hideAllChats(_, rv)): return lv == rv
        case let (.ghostInDrawer(_, lv), .ghostInDrawer(_, rv)): return lv == rv
        case let (.streamerInDrawer(_, lv), .streamerInDrawer(_, rv)): return lv == rv
        case let (.codeFont(_, lv), .codeFont(_, rv)): return lv == rv
        case let (.avatarCorners(_, _, lv), .avatarCorners(_, _, rv)): return lv == rv
        case let (.messageBubbleRadius(_, _, lv), .messageBubbleRadius(_, _, rv)): return lv == rv
        case let (.singleCornerRadius(_, lv), .singleCornerRadius(_, rv)): return lv == rv
        case let (.hidePremiumStatuses(_, lv), .hidePremiumStatuses(_, rv)): return lv == rv
        default: return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramAppearanceEntry, rhs: AyuGramAppearanceEntry) -> Bool { lhs.stableId < rhs.stableId }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramAppearanceArguments
        switch self {
        case .appIconHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "App Icon", sectionId: self.section)
        case let .appIcon(_, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "App Icon", label: value == "default" ? "Default" : value, sectionId: self.section, style: .blocks, action: {
                let idx = ayuGramAppIconOptions.firstIndex(of: value) ?? -1
                arguments.updateString(\.selectedAppIcon, ayuGramAppIconOptions[(idx + 1) % ayuGramAppIconOptions.count])
            })
        case let .hideNotificationBadge(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Hide Notification Badge", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideNotificationBadge, v) })
        case let .hideNotificationCounters(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Hide Notification Counters", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideNotificationCounters, v) })
        case .appearanceHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Appearance", sectionId: self.section)
        case let .md3Switches(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "MD3 Style Switches", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.md3StyleSwitches, v) })
        case let .removeBubbleTail(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Remove Message Tail", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.removeMessageBubbleTail, v) })
        case let .disableCustomBg(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Disable Custom Backgrounds", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.disableCustomBackgrounds, v) })
        case let .codeFont(_, value):
            let presets = ["", "Menlo", "Courier", "Courier-Bold"]
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Code Font", label: value.isEmpty ? "Default" : value, sectionId: self.section, style: .blocks, action: {
                let idx = presets.firstIndex(of: value) ?? -1
                arguments.updateString(\.codeFontName, presets[(idx + 1) % presets.count])
            })
        case let .avatarCorners(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Avatar Corners", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.avatarCorners, [0, 23, 50][(([0, 23, 50].firstIndex(of: value) ?? -1) + 1) % 3])
            })
        case let .messageBubbleRadius(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Message Bubble Radius", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.messageBubbleRadius, [0, 8, 16, 24][(([0, 8, 16, 24].firstIndex(of: value) ?? -1) + 1) % 4])
            })
        case let .singleCornerRadius(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Single Corner Radius (forums)", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.singleCornerRadius, v) })
        case let .hidePremiumStatuses(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Hide Premium Statuses", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hidePremiumStatuses, v) })
        case .foldersHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Folders", sectionId: self.section)
        case let .hideFolderCounters(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Hide Folder Counters", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideFolderCounters, v) })
        case let .hideAllChats(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Hide \"All Chats\"", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideAllChatsFolder, v) })
        case .drawerHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Drawer", sectionId: self.section)
        case let .ghostInDrawer(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Ghost Mode Toggle", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showGhostToggleInDrawer, v) })
        case let .streamerInDrawer(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Streamer Mode Toggle", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showStreamerToggleInDrawer, v) })
        }
    }
}

private func ayuGramAppearanceEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramAppearanceEntry] {
    var entries: [AyuGramAppearanceEntry] = []
    entries.append(.appIconHeader(presentationData.theme))
    entries.append(.appIcon(presentationData.theme, settings.selectedAppIcon))
    entries.append(.hideNotificationBadge(presentationData.theme, settings.hideNotificationBadge))
    entries.append(.hideNotificationCounters(presentationData.theme, settings.hideNotificationCounters))
    entries.append(.appearanceHeader(presentationData.theme))
    entries.append(.md3Switches(presentationData.theme, settings.md3StyleSwitches))
    entries.append(.removeBubbleTail(presentationData.theme, settings.removeMessageBubbleTail))
    entries.append(.disableCustomBg(presentationData.theme, settings.disableCustomBackgrounds))
    entries.append(.codeFont(presentationData.theme, settings.codeFontName))
    entries.append(.avatarCorners(presentationData.theme, "\(settings.avatarCorners)", settings.avatarCorners))
    entries.append(.messageBubbleRadius(presentationData.theme, "\(settings.messageBubbleRadius)", settings.messageBubbleRadius))
    entries.append(.singleCornerRadius(presentationData.theme, settings.singleCornerRadius))
    entries.append(.hidePremiumStatuses(presentationData.theme, settings.hidePremiumStatuses))
    entries.append(.foldersHeader(presentationData.theme))
    entries.append(.hideFolderCounters(presentationData.theme, settings.hideFolderCounters))
    entries.append(.hideAllChats(presentationData.theme, settings.hideAllChatsFolder))
    entries.append(.drawerHeader(presentationData.theme))
    entries.append(.ghostInDrawer(presentationData.theme, settings.showGhostToggleInDrawer))
    entries.append(.streamerInDrawer(presentationData.theme, settings.showStreamerToggleInDrawer))
    return entries
}

public func ayuGramAppearanceController(context: AccountContext) -> ViewController {
    let arguments = AyuGramAppearanceArguments(
        context: context,
        updateBool: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateInt32: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateString: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, ayuGramSettings(accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuGramAppearanceEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Appearance"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    return ItemListController(context: context, state: signal)
}
