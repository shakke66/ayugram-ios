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

private final class AyuGramShadowBanArguments {
    let context: AccountContext
    let presentIdEditor: (Int?, String) -> Void

    init(context: AccountContext, presentIdEditor: @escaping (Int?, String) -> Void) {
        self.context = context
        self.presentIdEditor = presentIdEditor
    }
}

private enum AyuGramShadowBanSection: Int32 {
    case ids
}

private enum AyuGramShadowBanEntry: ItemListNodeEntry {
    case idsHeader(PresentationTheme)
    case shadowBanId(PresentationTheme, Int32, String)
    case addId(PresentationTheme)

    var section: ItemListSectionId {
        switch self {
        case .idsHeader, .shadowBanId, .addId:
            return AyuGramShadowBanSection.ids.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .idsHeader: return 0
        case let .shadowBanId(_, index, _): return 100 + index
        case .addId: return 9000
        }
    }

    static func ==(lhs: AyuGramShadowBanEntry, rhs: AyuGramShadowBanEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.shadowBanId(_, li, lv), .shadowBanId(_, ri, rv)): return li == ri && lv == rv
        default: return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramShadowBanEntry, rhs: AyuGramShadowBanEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramShadowBanArguments
        switch self {
        case .idsHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Shadow Banned IDs", sectionId: self.section)
        case let .shadowBanId(_, index, id):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: id, label: "", sectionId: self.section, style: .blocks, action: {
                arguments.presentIdEditor(Int(index), id)
            })
        case .addId:
            return ItemListActionItem(presentationData: presentationData, title: "Add ID", kind: .generic, alignment: .natural, sectionId: self.section, style: .blocks, action: {
                arguments.presentIdEditor(nil, "")
            })
        }
    }
}

private func ayuGramShadowBanEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramShadowBanEntry] {
    var entries: [AyuGramShadowBanEntry] = []
    entries.append(.idsHeader(presentationData.theme))
    var index: Int32 = 0
    for id in settings.shadowBanIds {
        entries.append(.shadowBanId(presentationData.theme, index, "\(id)"))
        index += 1
    }
    entries.append(.addId(presentationData.theme))
    return entries
}

public func ayuGramShadowBanController(context: AccountContext) -> ViewController {
    var presentControllerImpl: ((ViewController, ViewControllerPresentationArguments?) -> Void)?

    let arguments = AyuGramShadowBanArguments(
        context: context,
        presentIdEditor: { index, current in
            let editController = promptController(context: context, text: index == nil ? "Add Peer ID" : "Edit Peer ID", value: current, apply: { value in
                guard let value = value else {
                    return
                }
                let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager) { s in
                    var s = s
                    if let index = index {
                        if index >= 0 && index < s.shadowBanIds.count {
                            if trimmed.isEmpty {
                                s.shadowBanIds.remove(at: index)
                            } else if let parsed = Int64(trimmed) {
                                s.shadowBanIds[index] = parsed
                            }
                        }
                    } else if let parsed = Int64(trimmed) {
                        s.shadowBanIds.append(parsed)
                    }
                    return s
                }.startStandalone()
            })
            presentControllerImpl?(editController, nil)
        }
    )

    let signal = combineLatest(context.sharedContext.presentationData, ayuGramSettings(accountManager: context.sharedContext.accountManager))
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuGramShadowBanEntries(settings: settings, presentationData: presentationData)
        return (
            ItemListControllerState(presentationData: ItemListPresentationData(presentationData), title: .text("Shadow Ban"), leftNavigationButton: nil, rightNavigationButton: nil, backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)),
            (ItemListNodeState(presentationData: ItemListPresentationData(presentationData), entries: entries, style: .blocks), arguments)
        )
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] c, p in
        controller?.present(c, in: .window(.root), with: p)
    }
    return controller
}
