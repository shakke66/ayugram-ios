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

private final class AyuGramMainArguments {
    let context: AccountContext
    let pushController: (ViewController) -> Void

    init(context: AccountContext, pushController: @escaping (ViewController) -> Void) {
        self.context = context
        self.pushController = pushController
    }
}

private enum AyuGramMainSection: Int32 {
    case header
    case categories
    case links
}

private enum AyuGramMainEntry: ItemListNodeEntry {
    case header(PresentationTheme, String)
    case categoryAyuGram(PresentationTheme)
    case categoryFilters(PresentationTheme)
    case categoryGeneral(PresentationTheme)
    case categoryAppearance(PresentationTheme)
    case categoryChats(PresentationTheme)
    case categoryOther(PresentationTheme)
    case spyHistory(PresentationTheme)
    case editHistory(PresentationTheme)
    case linkChannel(PresentationTheme)
    case linkChat(PresentationTheme)
    case linkDocs(PresentationTheme)

    var section: ItemListSectionId {
        switch self {
        case .header:
            return AyuGramMainSection.header.rawValue
        case .categoryAyuGram, .categoryFilters, .categoryGeneral, .categoryAppearance, .categoryChats, .categoryOther, .spyHistory, .editHistory:
            return AyuGramMainSection.categories.rawValue
        case .linkChannel, .linkChat, .linkDocs:
            return AyuGramMainSection.links.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .header: return 0
        case .categoryAyuGram: return 1
        case .categoryFilters: return 2
        case .categoryGeneral: return 3
        case .categoryAppearance: return 4
        case .categoryChats: return 5
        case .categoryOther: return 6
        case .spyHistory: return 7
        case .editHistory: return 8
        case .linkChannel: return 9
        case .linkChat: return 10
        case .linkDocs: return 11
        }
    }

    static func ==(lhs: AyuGramMainEntry, rhs: AyuGramMainEntry) -> Bool {
        return lhs.stableId == rhs.stableId
    }

    static func <(lhs: AyuGramMainEntry, rhs: AyuGramMainEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramMainArguments
        switch self {
        case let .header(_, text):
            return ItemListTextItem(presentationData: presentationData, text: .plain(text), sectionId: self.section)
        case .categoryAyuGram:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "AyuGram", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramCoreController(context: arguments.context))
            })
        case .categoryFilters:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Filters", label: "\u{03B2}", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramFiltersController(context: arguments.context))
            })
        case .categoryGeneral:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "General", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramGeneralController(context: arguments.context))
            })
        case .categoryAppearance:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Appearance", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramAppearanceController(context: arguments.context))
            })
        case .categoryChats:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Chats", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramChatsController(context: arguments.context))
            })
        case .categoryOther:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Other", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramOtherController(context: arguments.context))
            })
        case .spyHistory:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Deleted Messages", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramDeletedMessagesController(context: arguments.context))
            })
        case .editHistory:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Edit History", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramEditedMessagesController(context: arguments.context))
            })
        case .linkChannel:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Channel", label: "@ayugram", sectionId: self.section, style: .blocks, action: {
                arguments.context.sharedContext.openExternalUrl(context: arguments.context, urlContext: .generic, url: "https://t.me/ayugram", forceExternal: false, presentationData: arguments.context.sharedContext.currentPresentationData.with { $0 }, navigationController: nil, dismissInput: {})
            })
        case .linkChat:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Chat", label: "@ayugramchat", sectionId: self.section, style: .blocks, action: {
                arguments.context.sharedContext.openExternalUrl(context: arguments.context, urlContext: .generic, url: "https://t.me/ayugramchat", forceExternal: false, presentationData: arguments.context.sharedContext.currentPresentationData.with { $0 }, navigationController: nil, dismissInput: {})
            })
        case .linkDocs:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Documentation", label: "docs.ayugram.one", sectionId: self.section, style: .blocks, action: {
                arguments.context.sharedContext.openExternalUrl(context: arguments.context, urlContext: .generic, url: "https://docs.ayugram.one", forceExternal: true, presentationData: arguments.context.sharedContext.currentPresentationData.with { $0 }, navigationController: nil, dismissInput: {})
            })
        }
    }
}

private func ayuGramMainEntries(presentationData: PresentationData) -> [AyuGramMainEntry] {
    var entries: [AyuGramMainEntry] = []
    entries.append(.header(presentationData.theme, "AyuGram iOS v1.0.0\nFork of Telegram for iOS with extended customization."))
    entries.append(.categoryAyuGram(presentationData.theme))
    entries.append(.categoryFilters(presentationData.theme))
    entries.append(.categoryGeneral(presentationData.theme))
    entries.append(.categoryAppearance(presentationData.theme))
    entries.append(.categoryChats(presentationData.theme))
    entries.append(.categoryOther(presentationData.theme))
    entries.append(.spyHistory(presentationData.theme))
    entries.append(.editHistory(presentationData.theme))
    entries.append(.linkChannel(presentationData.theme))
    entries.append(.linkChat(presentationData.theme))
    entries.append(.linkDocs(presentationData.theme))
    return entries
}

public func ayuGramMainController(context: AccountContext) -> ViewController {
    var pushControllerImpl: ((ViewController) -> Void)?

    let arguments = AyuGramMainArguments(
        context: context,
        pushController: { controller in
            pushControllerImpl?(controller)
        }
    )

    let signal = context.sharedContext.presentationData
    |> map { presentationData -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuGramMainEntries(presentationData: presentationData)
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text("AyuGram Settings"),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: entries,
            style: .blocks
        )
        return (controllerState, (listState, arguments))
    }

    let controller = ItemListController(context: context, state: signal)
    pushControllerImpl = { [weak controller] c in
        controller?.push(c)
    }
    return controller
}
