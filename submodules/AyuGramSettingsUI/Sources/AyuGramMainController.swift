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
    case categories
}

private enum AyuGramMainEntry: ItemListNodeEntry {
    case categoryAyuGram(PresentationTheme)
    case categoryFilters(PresentationTheme)
    case categoryGeneral(PresentationTheme)
    case categoryAppearance(PresentationTheme)
    case categoryChats(PresentationTheme)
    case categoryOther(PresentationTheme)

    var section: ItemListSectionId {
        return AyuGramMainSection.categories.rawValue
    }

    var stableId: Int32 {
        switch self {
        case .categoryAyuGram: return 1
        case .categoryFilters: return 2
        case .categoryGeneral: return 3
        case .categoryAppearance: return 4
        case .categoryChats: return 5
        case .categoryOther: return 6
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
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case .categoryAyuGram:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.mainCore], label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramCoreController(context: arguments.context))
            })
        case .categoryFilters:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.mainFilters], label: "\u{03B2}", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramFiltersController(context: arguments.context))
            })
        case .categoryGeneral:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.mainGeneral], label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramGeneralController(context: arguments.context))
            })
        case .categoryAppearance:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.mainAppearance], label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramAppearanceController(context: arguments.context))
            })
        case .categoryChats:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.mainChats], label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramChatsController(context: arguments.context))
            })
        case .categoryOther:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.mainOther], label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramOtherController(context: arguments.context))
            })
        }
    }
}

private func ayuGramMainEntries(presentationData: PresentationData) -> [AyuGramMainEntry] {
    return [
        .categoryAyuGram(presentationData.theme),
        .categoryFilters(presentationData.theme),
        .categoryGeneral(presentationData.theme),
        .categoryAppearance(presentationData.theme),
        .categoryChats(presentationData.theme),
        .categoryOther(presentationData.theme),
    ]
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
        let strings = GRVMgramStrings(presentationData.strings)
        let entries = ayuGramMainEntries(presentationData: presentationData)
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text(strings[.settingsTitle]),
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
