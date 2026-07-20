import AccountContext
import Display
import ItemListUI
import SwiftSignalKit
import TelegramPresentationData
import TelegramUIPreferences

private enum AyuEditedSection: Int32 {
    case information
}

private enum AyuEditedEntry: ItemListNodeEntry {
    case information(PresentationTheme)

    var section: ItemListSectionId {
        return AyuEditedSection.information.rawValue
    }

    var stableId: Int32 {
        return 0
    }

    static func ==(lhs: AyuEditedEntry, rhs: AyuEditedEntry) -> Bool {
        return true
    }

    static func <(lhs: AyuEditedEntry, rhs: AyuEditedEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let strings = GRVMgramStrings(presentationData.strings)
        return ItemListTextItem(
            presentationData: presentationData,
            text: .plain(strings[.historyInfo]),
            sectionId: self.section
        )
    }
}

/// Explains where the per-message GRVMgram History action is available.
public func ayuGramEditedMessagesController(context: AccountContext) -> ViewController {
    let signal = context.sharedContext.presentationData
    |> map { presentationData -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text(strings[.historyTitle]),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: [AyuEditedEntry.information(presentationData.theme)],
            style: .blocks
        )
        return (controllerState, (listState, ()))
    }
    return ItemListController(context: context, state: signal)
}
