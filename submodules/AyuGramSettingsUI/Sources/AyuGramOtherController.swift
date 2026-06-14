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

private final class AyuGramOtherArguments {
    let context: AccountContext
    let updateBool: (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void
    let openURL: (String) -> Void
    let copyToClipboard: (String) -> Void
    let resetSettings: () -> Void

    init(context: AccountContext, updateBool: @escaping (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void, openURL: @escaping (String) -> Void, copyToClipboard: @escaping (String) -> Void, resetSettings: @escaping () -> Void) {
        self.context = context
        self.updateBool = updateBool
        self.openURL = openURL
        self.copyToClipboard = copyToClipboard
        self.resetSettings = resetSettings
    }
}

private enum AyuGramOtherSection: Int32 {
    case support
    case other
}

private enum AyuGramOtherEntry: ItemListNodeEntry {
    case supportHeader(PresentationTheme)
    case boosty(PresentationTheme)
    case ton(PresentationTheme)
    case bitcoin(PresentationTheme)
    case ethereum(PresentationTheme)
    case solana(PresentationTheme)
    case tron(PresentationTheme)
    case supportInfo(PresentationTheme)
    case otherHeader(PresentationTheme)
    case crashReporting(PresentationTheme, Bool)
    case crashReportingInfo(PresentationTheme)
    case associateLinks(PresentationTheme, Bool)
    case resetSettings(PresentationTheme)

    var section: ItemListSectionId {
        switch self {
        case .supportHeader, .boosty, .ton, .bitcoin, .ethereum, .solana, .tron, .supportInfo:
            return AyuGramOtherSection.support.rawValue
        case .otherHeader, .crashReporting, .crashReportingInfo, .associateLinks, .resetSettings:
            return AyuGramOtherSection.other.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .supportHeader: return 0
        case .boosty: return 1
        case .ton: return 2
        case .bitcoin: return 3
        case .ethereum: return 4
        case .solana: return 5
        case .tron: return 6
        case .supportInfo: return 7
        case .otherHeader: return 8
        case .crashReporting: return 9
        case .crashReportingInfo: return 10
        case .associateLinks: return 11
        case .resetSettings: return 12
        }
    }

    static func ==(lhs: AyuGramOtherEntry, rhs: AyuGramOtherEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.crashReporting(_, lv), .crashReporting(_, rv)): return lv == rv
        case let (.associateLinks(_, lv), .associateLinks(_, rv)): return lv == rv
        default: return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramOtherEntry, rhs: AyuGramOtherEntry) -> Bool { lhs.stableId < rhs.stableId }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramOtherArguments
        switch self {
        case .supportHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Support", sectionId: self.section)
        case .boosty:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Boosty", label: "", sectionId: self.section, style: .blocks, action: { arguments.openURL("https://boosty.to/ayugram") })
        case .ton:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "TON", label: "", sectionId: self.section, style: .blocks, action: { arguments.copyToClipboard("UQA4i8U8vP3mYUZSV3KqDQEHPwmhninEqCkkKc7BITQ652de") })
        case .bitcoin:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Bitcoin", label: "", sectionId: self.section, style: .blocks, action: { arguments.copyToClipboard("bc1qdk6qq4mzq5yap3fpy0qau3246w3m3uwac9f0xd") })
        case .ethereum:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Ethereum", label: "", sectionId: self.section, style: .blocks, action: { arguments.copyToClipboard("0x405589857C8DFAb45B2027c68ad1e58877FDa347") })
        case .solana:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Solana", label: "", sectionId: self.section, style: .blocks, action: { arguments.copyToClipboard("8ZHQpPxpsdRjsWoBcF1dmvRM5dB6zEhJ3jMBFZjYfyHs") })
        case .tron:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Tron", label: "", sectionId: self.section, style: .blocks, action: { arguments.copyToClipboard("TRpbajq38qU8joThgAfKJLyEPbNjzsdPJ1") })
        case .supportInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Support the developers and get a unique badge!"), sectionId: self.section)
        case .otherHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Other", sectionId: self.section)
        case let .crashReporting(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Crash Reporting", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.crashReportingEnabled, v) })
        case .crashReportingInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain("When enabled, you will be offered to send a crash report after an unexpected app termination."), sectionId: self.section)
        case let .associateLinks(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Associate Links with AyuGram", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.associateLinks, v) })
        case .resetSettings:
            return ItemListActionItem(presentationData: presentationData, title: "Reset Settings", kind: .destructive, alignment: .natural, sectionId: self.section, style: .blocks, action: { arguments.resetSettings() })
        }
    }
}

private func ayuGramOtherEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramOtherEntry] {
    var entries: [AyuGramOtherEntry] = []
    entries.append(.supportHeader(presentationData.theme))
    entries.append(.boosty(presentationData.theme))
    entries.append(.ton(presentationData.theme))
    entries.append(.bitcoin(presentationData.theme))
    entries.append(.ethereum(presentationData.theme))
    entries.append(.solana(presentationData.theme))
    entries.append(.tron(presentationData.theme))
    entries.append(.supportInfo(presentationData.theme))
    entries.append(.otherHeader(presentationData.theme))
    entries.append(.crashReporting(presentationData.theme, settings.crashReportingEnabled))
    entries.append(.crashReportingInfo(presentationData.theme))
    entries.append(.associateLinks(presentationData.theme, settings.associateLinks))
    entries.append(.resetSettings(presentationData.theme))
    return entries
}

public func ayuGramOtherController(context: AccountContext) -> ViewController {
    let arguments = AyuGramOtherArguments(
        context: context,
        updateBool: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        openURL: { url in
            arguments.context.sharedContext.openExternalUrl(context: arguments.context, urlContext: .generic, url: url, forceExternal: true, presentationData: arguments.context.sharedContext.currentPresentationData.with { $0 }, navigationController: nil, dismissInput: {})
        },
        copyToClipboard: { text in
            UIPasteboard.general.string = text
        },
        resetSettings: {
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { _ in
                return .defaultSettings
            }.startStandalone()
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, ayuGramSettings(accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuGramOtherEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Other"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    return ItemListController(context: context, state: signal)
}
