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
import PromptUI

private final class AyuGramFiltersArguments {
    let context: AccountContext
    let toggleFilters: (Bool) -> Void
    let toggleFiltersInChats: (Bool) -> Void
    let toggleHideFromBlocked: (Bool) -> Void
    let presentFilterEditor: (Int?, String) -> Void
    let pushController: (ViewController) -> Void

    init(context: AccountContext, toggleFilters: @escaping (Bool) -> Void, toggleFiltersInChats: @escaping (Bool) -> Void, toggleHideFromBlocked: @escaping (Bool) -> Void, presentFilterEditor: @escaping (Int?, String) -> Void, pushController: @escaping (ViewController) -> Void) {
        self.context = context
        self.toggleFilters = toggleFilters
        self.toggleFiltersInChats = toggleFiltersInChats
        self.toggleHideFromBlocked = toggleHideFromBlocked
        self.presentFilterEditor = presentFilterEditor
        self.pushController = pushController
    }
}

private enum AyuGramFiltersSection: Int32 {
    case messageFilters
    case patterns
    case globalFilters
}

private enum AyuGramFiltersEntry: ItemListNodeEntry {
    case filtersHeader(PresentationTheme)
    case enableFilters(PresentationTheme, Bool)
    case enableFiltersInChats(PresentationTheme, Bool)
    case hideFromBlocked(PresentationTheme, Bool)
    case patternsHeader(PresentationTheme)
    case filterPattern(PresentationTheme, Int32, String)
    case addFilter(PresentationTheme)
    case globalFiltersHeader(PresentationTheme)
    case shadowBan(PresentationTheme)

    var section: ItemListSectionId {
        switch self {
        case .filtersHeader, .enableFilters, .enableFiltersInChats, .hideFromBlocked:
            return AyuGramFiltersSection.messageFilters.rawValue
        case .patternsHeader, .filterPattern, .addFilter:
            return AyuGramFiltersSection.patterns.rawValue
        case .globalFiltersHeader, .shadowBan:
            return AyuGramFiltersSection.globalFilters.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .filtersHeader: return 0
        case .enableFilters: return 1
        case .enableFiltersInChats: return 2
        case .hideFromBlocked: return 3
        case .patternsHeader: return 4
        case let .filterPattern(_, index, _): return 100 + index
        case .addFilter: return 9000
        case .globalFiltersHeader: return 9001
        case .shadowBan: return 9002
        }
    }

    static func ==(lhs: AyuGramFiltersEntry, rhs: AyuGramFiltersEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.enableFilters(_, lv), .enableFilters(_, rv)): return lv == rv
        case let (.enableFiltersInChats(_, lv), .enableFiltersInChats(_, rv)): return lv == rv
        case let (.hideFromBlocked(_, lv), .hideFromBlocked(_, rv)): return lv == rv
        case let (.filterPattern(_, li, lp), .filterPattern(_, ri, rp)): return li == ri && lp == rp
        default: return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramFiltersEntry, rhs: AyuGramFiltersEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramFiltersArguments
        switch self {
        case .filtersHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Message Filters", sectionId: self.section)
        case let .enableFilters(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Enable Filters", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleFilters(value)
            })
        case let .enableFiltersInChats(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Enable Filters in Chats", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleFiltersInChats(value)
            })
        case let .hideFromBlocked(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Hide from Blocked Users", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleHideFromBlocked(value)
            })
        case .patternsHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Filter Patterns (Regex)", sectionId: self.section)
        case let .filterPattern(_, index, pattern):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: pattern, label: "", sectionId: self.section, style: .blocks, action: {
                arguments.presentFilterEditor(Int(index), pattern)
            })
        case .addFilter:
            return ItemListActionItem(presentationData: presentationData, title: "Add Filter", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.presentFilterEditor(nil, "")
            })
        case .globalFiltersHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Global Filters", sectionId: self.section)
        case .shadowBan:
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: "Shadow Ban", label: "", sectionId: self.section, style: .blocks, action: {
                arguments.pushController(ayuGramShadowBanController(context: arguments.context))
            })
        }
    }
}

private func ayuGramFiltersEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramFiltersEntry] {
    var entries: [AyuGramFiltersEntry] = []
    entries.append(.filtersHeader(presentationData.theme))
    entries.append(.enableFilters(presentationData.theme, settings.enableFilters))
    entries.append(.enableFiltersInChats(presentationData.theme, settings.enableFiltersInChats))
    entries.append(.hideFromBlocked(presentationData.theme, settings.hideFromBlockedUsers))
    entries.append(.patternsHeader(presentationData.theme))
    var index: Int32 = 0
    for pattern in settings.messageFilters {
        entries.append(.filterPattern(presentationData.theme, index, pattern))
        index += 1
    }
    entries.append(.addFilter(presentationData.theme))
    entries.append(.globalFiltersHeader(presentationData.theme))
    entries.append(.shadowBan(presentationData.theme))
    return entries
}

public func ayuGramFiltersController(context: AccountContext) -> ViewController {
    var presentControllerImpl: ((ViewController, ViewControllerPresentationArguments?) -> Void)?
    var pushControllerImpl: ((ViewController) -> Void)?

    let arguments = AyuGramFiltersArguments(
        context: context,
        toggleFilters: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s.enableFilters = value; return s }.startStandalone()
        },
        toggleFiltersInChats: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s.enableFiltersInChats = value; return s }.startStandalone()
        },
        toggleHideFromBlocked: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in var s = s; s.hideFromBlockedUsers = value; return s }.startStandalone()
        },
        presentFilterEditor: { index, current in
            let editController = promptController(context: context, text: index == nil ? "Add Filter Pattern (Regex)" : "Edit Filter Pattern (Regex)", value: current, apply: { value in
                guard let value = value else {
                    return
                }
                let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in
                    var s = s
                    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                    if let index = index {
                        if index >= 0 && index < s.messageFilters.count {
                            if trimmed.isEmpty {
                                s.messageFilters.remove(at: index)
                            } else {
                                s.messageFilters[index] = trimmed
                            }
                        }
                    } else if !trimmed.isEmpty {
                        s.messageFilters.append(trimmed)
                    }
                    return s
                }.startStandalone()
            })
            presentControllerImpl?(editController, nil)
        },
        pushController: { controller in
            pushControllerImpl?(controller)
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, ayuGramSettings(accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuGramFiltersEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Filters"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] c, p in
        controller?.present(c, in: .window(.root), with: p)
    }
    pushControllerImpl = { [weak controller] c in
        controller?.push(c)
    }
    return controller
}
