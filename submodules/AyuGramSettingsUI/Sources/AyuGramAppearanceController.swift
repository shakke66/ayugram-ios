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
    let pushController: (ViewController) -> Void
    let updateBool: (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void
    let updateInt32: (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void
    let updateString: (WritableKeyPath<AyuGramSettings, String>, String) -> Void

    init(context: AccountContext, pushController: @escaping (ViewController) -> Void, updateBool: @escaping (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void, updateInt32: @escaping (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void, updateString: @escaping (WritableKeyPath<AyuGramSettings, String>, String) -> Void) {
        self.context = context
        self.pushController = pushController
        self.updateBool = updateBool
        self.updateInt32 = updateInt32
        self.updateString = updateString
    }
}

private enum AyuGramAppearanceSection: Int32 {
    case appIcon
    case appearance
    case folders
}

private enum AyuGramAppearanceEntry: ItemListNodeEntry {
    case appIconHeader(PresentationTheme)
    case appIcon(PresentationTheme, String)
    case hideNotificationBadge(PresentationTheme, Bool)
    case hideNotificationCounters(PresentationTheme, Bool)
    case appearanceHeader(PresentationTheme)
    case removeBubbleTail(PresentationTheme, Bool)
    case disableCustomBg(PresentationTheme, Bool)
    case codeFont(PresentationTheme, String)
    case avatarCorners(PresentationTheme, Int32)
    case hidePremiumStatuses(PresentationTheme, Bool)
    case foldersHeader(PresentationTheme)
    case hideFolderCounters(PresentationTheme, Bool)
    case hideAllChats(PresentationTheme, Bool)

    var section: ItemListSectionId {
        switch self {
        case .appIconHeader, .appIcon, .hideNotificationBadge, .hideNotificationCounters: return AyuGramAppearanceSection.appIcon.rawValue
        case .appearanceHeader, .removeBubbleTail, .disableCustomBg, .codeFont, .avatarCorners, .hidePremiumStatuses: return AyuGramAppearanceSection.appearance.rawValue
        case .foldersHeader, .hideFolderCounters, .hideAllChats: return AyuGramAppearanceSection.folders.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .appIconHeader: return 0
        case .appIcon: return 1
        case .hideNotificationBadge: return 2
        case .hideNotificationCounters: return 3
        case .appearanceHeader: return 4
        case .removeBubbleTail: return 6
        case .disableCustomBg: return 7
        case .codeFont: return 8
        case .avatarCorners: return 9
        case .hidePremiumStatuses: return 12
        case .foldersHeader: return 14
        case .hideFolderCounters: return 15
        case .hideAllChats: return 16
        }
    }

    static func ==(lhs: AyuGramAppearanceEntry, rhs: AyuGramAppearanceEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.appIcon(_, lv), .appIcon(_, rv)): return lv == rv
        case let (.hideNotificationBadge(_, lv), .hideNotificationBadge(_, rv)): return lv == rv
        case let (.hideNotificationCounters(_, lv), .hideNotificationCounters(_, rv)): return lv == rv
        case let (.removeBubbleTail(_, lv), .removeBubbleTail(_, rv)): return lv == rv
        case let (.disableCustomBg(_, lv), .disableCustomBg(_, rv)): return lv == rv
        case let (.hideFolderCounters(_, lv), .hideFolderCounters(_, rv)): return lv == rv
        case let (.hideAllChats(_, lv), .hideAllChats(_, rv)): return lv == rv
        case let (.codeFont(_, lv), .codeFont(_, rv)): return lv == rv
        case let (.avatarCorners(_, lv), .avatarCorners(_, rv)): return lv == rv
        case let (.hidePremiumStatuses(_, lv), .hidePremiumStatuses(_, rv)): return lv == rv
        default: return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramAppearanceEntry, rhs: AyuGramAppearanceEntry) -> Bool { lhs.stableId < rhs.stableId }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramAppearanceArguments
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case .appIconHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.appIconHeader], sectionId: self.section)
        case let .appIcon(_, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.appIconTitle], label: grvmAppIconDisplayTitle(value, strings: strings), maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.context.sharedContext.mainWindow?.present(
                    ayuGramAppIconPicker(
                        context: arguments.context,
                        onSelect: { rawIdentifier in
                            arguments.updateString(\.selectedAppIcon, rawIdentifier)
                        }
                    ),
                    on: .root
                )
            })
        case let .hideNotificationBadge(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.appearanceHideBadge], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideNotificationBadge, v) })
        case let .hideNotificationCounters(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.appearanceHideCounters], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideNotificationCounters, v) })
        case .appearanceHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.appearanceHeader], sectionId: self.section)
        case let .removeBubbleTail(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.appearanceTail], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.removeMessageBubbleTail, v) })
        case let .disableCustomBg(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.appearanceBackgrounds], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.disableCustomBackgrounds, v) })
        case let .codeFont(_, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.appearanceCodeFont], label: value.isEmpty ? strings[.commonDefault] : value, maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramCodeFontController(context: arguments.context, currentFontName: value, onSelect: {
                    arguments.updateString(\.codeFontName, $0)
                }))
            })
        case let .avatarCorners(_, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.appearanceAvatarCorners], label: "\(min(50, max(0, value)))", maximumTitleNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramAvatarCornersController(context: arguments.context, currentValue: value, onSelect: {
                    arguments.updateInt32(\.avatarCorners, $0)
                }))
            })
        case let .hidePremiumStatuses(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.appearancePremiumStatuses], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hidePremiumStatuses, v) })
        case .foldersHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.appearanceFolders], sectionId: self.section)
        case let .hideFolderCounters(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.appearanceFolderCounters], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideFolderCounters, v) })
        case let .hideAllChats(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.appearanceAllChats], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideAllChatsFolder, v) })
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
    entries.append(.removeBubbleTail(presentationData.theme, settings.removeMessageBubbleTail))
    entries.append(.disableCustomBg(presentationData.theme, settings.disableCustomBackgrounds))
    entries.append(.codeFont(presentationData.theme, settings.codeFontName))
    entries.append(.avatarCorners(presentationData.theme, settings.avatarCorners))
    entries.append(.hidePremiumStatuses(presentationData.theme, settings.hidePremiumStatuses))
    entries.append(.foldersHeader(presentationData.theme))
    entries.append(.hideFolderCounters(presentationData.theme, settings.hideFolderCounters))
    entries.append(.hideAllChats(presentationData.theme, settings.hideAllChatsFolder))
    return entries
}

public func ayuGramAppearanceController(context: AccountContext) -> ViewController {
    var pushControllerImpl: ((ViewController) -> Void)?
    let arguments = AyuGramAppearanceArguments(
        context: context,
        pushController: { controller in
            pushControllerImpl?(controller)
        },
        updateBool: { keyPath, value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateInt32: { keyPath, value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateString: { keyPath, value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, grvmSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let entries = ayuGramAppearanceEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text(strings[.appearanceTitle]), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    let controller = ItemListController(context: context, state: signal)
    pushControllerImpl = { [weak controller] child in
        controller?.push(child)
    }
    return controller
}
