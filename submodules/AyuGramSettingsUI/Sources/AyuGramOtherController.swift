import Foundation
import Display
import SwiftSignalKit
import Postbox
import TelegramCore
import TelegramPresentationData
import TelegramUIPreferences
import ItemListUI
import PresentationDataUtils
import AccountContext
import AlertUI
import AyuGramFeatures
import AyuGramLib

private final class AyuGramOtherArguments {
    let context: AccountContext
    let updateBool: (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void
    let resetSettings: () -> Void

    init(context: AccountContext, updateBool: @escaping (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void, resetSettings: @escaping () -> Void) {
        self.context = context
        self.updateBool = updateBool
        self.resetSettings = resetSettings
    }
}

private enum AyuGramOtherSection: Int32 {
    case other
}

private enum AyuGramOtherEntry: ItemListNodeEntry {
    case otherHeader(PresentationTheme)
    case streamerMode(PresentationTheme, Bool)
    case streamerModeInfo(PresentationTheme)
    case crashReporting(PresentationTheme, Bool)
    case crashReportingInfo(PresentationTheme)
    case exportLocalLogs(PresentationTheme)
    case resetSettings(PresentationTheme)

    var section: ItemListSectionId {
        return AyuGramOtherSection.other.rawValue
    }

    var stableId: Int32 {
        switch self {
        case .otherHeader: return 0
        case .streamerMode: return 1
        case .streamerModeInfo: return 2
        case .crashReporting: return 3
        case .crashReportingInfo: return 4
        case .exportLocalLogs: return 5
        case .resetSettings: return 6
        }
    }

    static func ==(lhs: AyuGramOtherEntry, rhs: AyuGramOtherEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.streamerMode(_, lv), .streamerMode(_, rv)): return lv == rv
        case let (.crashReporting(_, lv), .crashReporting(_, rv)): return lv == rv
        default: return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramOtherEntry, rhs: AyuGramOtherEntry) -> Bool { lhs.stableId < rhs.stableId }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramOtherArguments
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case .otherHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.otherHeader], sectionId: self.section)
        case let .streamerMode(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.streamerTitle], value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.streamerModeEnabled, v) })
        case .streamerModeInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain(strings[.streamerInfo]), sectionId: self.section)
        case let .crashReporting(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.crashTitle], value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.crashReportingEnabled, v) })
        case .crashReportingInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain(strings[.crashInfo]), sectionId: self.section)
        case .exportLocalLogs:
            return ItemListActionItem(presentationData: presentationData, title: strings[.crashExport], kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                AyuGramFeatures.exportLocalLogs?(arguments.context.account.peerId)
            })
        case .resetSettings:
            return ItemListActionItem(presentationData: presentationData, title: strings[.resetTitle], kind: .destructive, alignment: .natural, sectionId: self.section, style: .blocks, action: { arguments.resetSettings() })
        }
    }
}

private func ayuGramOtherEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramOtherEntry] {
    var entries: [AyuGramOtherEntry] = [
        .otherHeader(presentationData.theme),
        .streamerMode(presentationData.theme, settings.streamerModeEnabled),
        .streamerModeInfo(presentationData.theme),
        .crashReporting(presentationData.theme, settings.crashReportingEnabled),
        .crashReportingInfo(presentationData.theme),
    ]
    if settings.crashReportingEnabled {
        entries.append(.exportLocalLogs(presentationData.theme))
    }
    entries.append(.resetSettings(presentationData.theme))
    return entries
}

public func ayuGramOtherController(context: AccountContext) -> ViewController {
    var presentControllerImpl: ((ViewController, ViewControllerPresentationArguments?) -> Void)?
    let arguments = AyuGramOtherArguments(
        context: context,
        updateBool: { keyPath, value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        resetSettings: {
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            let strings = GRVMgramStrings(presentationData.strings)
            presentControllerImpl?(textAlertController(
                context: context,
                title: strings[.resetTitle],
                text: strings[.resetText],
                actions: [
                    TextAlertAction(
                        type: .genericAction,
                        title: presentationData.strings.Common_Cancel,
                        action: {}
                    ),
                    TextAlertAction(
                        type: .destructiveAction,
                        title: strings[.resetAction],
                        action: {
                            let _ = updateGRVMSettings(
                                accountId: context.account.peerId,
                                accountManager: context.sharedContext.accountManager
                            ) { _ in
                                return AyuGramSettings.defaultSettings
                            }.startStandalone()
                        }
                    )
                ]
            ), nil)
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, grvmSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let entries = ayuGramOtherEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text(strings[.otherTitle]), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] child, arguments in
        controller?.present(child, in: .window(.root), with: arguments)
    }
    return controller
}
