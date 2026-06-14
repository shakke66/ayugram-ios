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

private final class AyuGramGeneralArguments {
    let context: AccountContext
    let updateBool: (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void
    let updateInt32: (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void

    init(context: AccountContext, updateBool: @escaping (WritableKeyPath<AyuGramSettings, Bool>, Bool) -> Void, updateInt32: @escaping (WritableKeyPath<AyuGramSettings, Int32>, Int32) -> Void) {
        self.context = context
        self.updateBool = updateBool
        self.updateInt32 = updateInt32
    }
}

private enum AyuGramGeneralSection: Int32 {
    case translation
    case general
    case webview
    case confirmations
}

private enum AyuGramGeneralEntry: ItemListNodeEntry {
    case translationHeader(PresentationTheme)
    case translationProvider(PresentationTheme, String, Int32)
    case generalHeader(PresentationTheme)
    case hideStories(PresentationTheme, Bool)
    case disableSimilarChannels(PresentationTheme, Bool)
    case disableNotificationDelay(PresentationTheme, Bool)
    case showSeconds(PresentationTheme, Bool)
    case showDialogId(PresentationTheme, String, Int32)
    case filterZalgo(PresentationTheme, Bool)
    case improveLinkPreviews(PresentationTheme, Bool)
    case webviewHeader(PresentationTheme)
    case spoofAndroid(PresentationTheme, Bool)
    case increaseWebview(PresentationTheme, Bool)
    case confirmHeader(PresentationTheme)
    case confirmSticker(PresentationTheme, Bool)
    case confirmGIF(PresentationTheme, Bool)
    case confirmVoice(PresentationTheme, Bool)

    var section: ItemListSectionId {
        switch self {
        case .translationHeader, .translationProvider: return AyuGramGeneralSection.translation.rawValue
        case .generalHeader, .hideStories, .disableSimilarChannels, .disableNotificationDelay, .showSeconds, .showDialogId, .filterZalgo, .improveLinkPreviews: return AyuGramGeneralSection.general.rawValue
        case .webviewHeader, .spoofAndroid, .increaseWebview: return AyuGramGeneralSection.webview.rawValue
        case .confirmHeader, .confirmSticker, .confirmGIF, .confirmVoice: return AyuGramGeneralSection.confirmations.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .translationHeader: return 0
        case .translationProvider: return 1
        case .generalHeader: return 2
        case .hideStories: return 3
        case .disableSimilarChannels: return 4
        case .disableNotificationDelay: return 5
        case .showSeconds: return 6
        case .showDialogId: return 7
        case .filterZalgo: return 8
        case .improveLinkPreviews: return 9
        case .webviewHeader: return 10
        case .spoofAndroid: return 11
        case .increaseWebview: return 12
        case .confirmHeader: return 13
        case .confirmSticker: return 14
        case .confirmGIF: return 15
        case .confirmVoice: return 16
        }
    }

    static func ==(lhs: AyuGramGeneralEntry, rhs: AyuGramGeneralEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.hideStories(_, lv), .hideStories(_, rv)): return lv == rv
        case let (.disableSimilarChannels(_, lv), .disableSimilarChannels(_, rv)): return lv == rv
        case let (.disableNotificationDelay(_, lv), .disableNotificationDelay(_, rv)): return lv == rv
        case let (.showSeconds(_, lv), .showSeconds(_, rv)): return lv == rv
        case let (.spoofAndroid(_, lv), .spoofAndroid(_, rv)): return lv == rv
        case let (.increaseWebview(_, lv), .increaseWebview(_, rv)): return lv == rv
        case let (.confirmSticker(_, lv), .confirmSticker(_, rv)): return lv == rv
        case let (.confirmGIF(_, lv), .confirmGIF(_, rv)): return lv == rv
        case let (.confirmVoice(_, lv), .confirmVoice(_, rv)): return lv == rv
        case let (.translationProvider(_, _, lv), .translationProvider(_, _, rv)): return lv == rv
        case let (.showDialogId(_, _, lv), .showDialogId(_, _, rv)): return lv == rv
        case let (.filterZalgo(_, lv), .filterZalgo(_, rv)): return lv == rv
        case let (.improveLinkPreviews(_, lv), .improveLinkPreviews(_, rv)): return lv == rv
        default: return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramGeneralEntry, rhs: AyuGramGeneralEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramGeneralArguments
        switch self {
        case .translationHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Message Translation", sectionId: self.section)
        case let .translationProvider(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Translation Provider", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.translationProvider, (value + 1) % 4)
            })
        case .generalHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "General", sectionId: self.section)
        case let .hideStories(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Hide Stories", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.hideStories, v) })
        case let .disableSimilarChannels(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Disable Similar Channels", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.disableSimilarChannels, v) })
        case let .disableNotificationDelay(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Disable Notification Delay", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.disableNotificationDelay, v) })
        case let .showSeconds(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Show Seconds in Messages", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.showSecondsInMessages, v) })
        case let .showDialogId(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Show Dialog ID", label: label, sectionId: self.section, style: .blocks, action: {
                arguments.updateInt32(\.showDialogId, (value + 1) % 3)
            })
        case let .filterZalgo(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Zalgo Filter", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.filterZalgo, v) })
        case let .improveLinkPreviews(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Improve Link Previews", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.improveLinkPreviews, v) })
        case .webviewHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Webview", sectionId: self.section)
        case let .spoofAndroid(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Spoof Platform as Android", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.spoofWebviewAsAndroid, v) })
        case let .increaseWebview(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Increase Window Size", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.increaseWebviewSize, v) })
        case .confirmHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Confirmations", sectionId: self.section)
        case let .confirmSticker(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "For Stickers", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.confirmSendSticker, v) })
        case let .confirmGIF(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "For GIFs", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.confirmSendGIF, v) })
        case let .confirmVoice(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "For Voice Messages", value: value, sectionId: self.section, style: .blocks, updated: { v in arguments.updateBool(\.confirmSendVoice, v) })
        }
    }
}

private func ayuGramGeneralEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramGeneralEntry] {
    let providerNames = ["Telegram", "Google", "Yandex", "Native"]
    let providerLabel = settings.translationProvider < Int32(providerNames.count) ? providerNames[Int(settings.translationProvider)] : "Telegram"
    let dialogIdLabels = ["Off", "Telegram API", "Bot API"]
    let dialogIdLabel = settings.showDialogId < Int32(dialogIdLabels.count) ? dialogIdLabels[Int(settings.showDialogId)] : "Off"

    var entries: [AyuGramGeneralEntry] = []
    entries.append(.translationHeader(presentationData.theme))
    entries.append(.translationProvider(presentationData.theme, providerLabel, settings.translationProvider))
    entries.append(.generalHeader(presentationData.theme))
    entries.append(.hideStories(presentationData.theme, settings.hideStories))
    entries.append(.disableSimilarChannels(presentationData.theme, settings.disableSimilarChannels))
    entries.append(.disableNotificationDelay(presentationData.theme, settings.disableNotificationDelay))
    entries.append(.showSeconds(presentationData.theme, settings.showSecondsInMessages))
    entries.append(.showDialogId(presentationData.theme, dialogIdLabel, settings.showDialogId))
    entries.append(.filterZalgo(presentationData.theme, settings.filterZalgo))
    entries.append(.improveLinkPreviews(presentationData.theme, settings.improveLinkPreviews))
    entries.append(.webviewHeader(presentationData.theme))
    entries.append(.spoofAndroid(presentationData.theme, settings.spoofWebviewAsAndroid))
    entries.append(.increaseWebview(presentationData.theme, settings.increaseWebviewSize))
    entries.append(.confirmHeader(presentationData.theme))
    entries.append(.confirmSticker(presentationData.theme, settings.confirmSendSticker))
    entries.append(.confirmGIF(presentationData.theme, settings.confirmSendGIF))
    entries.append(.confirmVoice(presentationData.theme, settings.confirmSendVoice))
    return entries
}

public func ayuGramGeneralController(context: AccountContext) -> ViewController {
    let arguments = AyuGramGeneralArguments(
        context: context,
        updateBool: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        },
        updateInt32: { keyPath, value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s[keyPath: keyPath] = value; return s }.startStandalone()
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, ayuGramSettings(accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuGramGeneralEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("General"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    return ItemListController(context: context, state: signal)
}
