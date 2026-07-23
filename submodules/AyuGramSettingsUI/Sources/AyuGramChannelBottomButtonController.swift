import Foundation
import Display
import SwiftSignalKit
import TelegramPresentationData
import ItemListUI
import AccountContext

public func grvmNormalizedChannelBottomButtonValue(_ value: Int32) -> Int32 {
    return value == 0 ? 0 : 1
}

private final class AyuGramChannelBottomButtonArguments {
    let selectValue: (Int32) -> Void

    init(selectValue: @escaping (Int32) -> Void) {
        self.selectValue = selectValue
    }
}

private enum AyuGramChannelBottomButtonEntry: ItemListNodeEntry {
    case option(PresentationTheme, GRVMgramStringKey, value: Int32, selected: Bool, index: Int32)

    var section: ItemListSectionId {
        return 0
    }

    var stableId: Int32 {
        switch self {
        case let .option(_, _, _, _, index):
            return index
        }
    }

    static func ==(lhs: AyuGramChannelBottomButtonEntry, rhs: AyuGramChannelBottomButtonEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.option(lhsTheme, lhsTitle, lhsValue, lhsSelected, lhsIndex), .option(rhsTheme, rhsTitle, rhsValue, rhsSelected, rhsIndex)):
            return lhsTheme === rhsTheme
                && lhsTitle == rhsTitle
                && lhsValue == rhsValue
                && lhsSelected == rhsSelected
                && lhsIndex == rhsIndex
        }
    }

    static func <(lhs: AyuGramChannelBottomButtonEntry, rhs: AyuGramChannelBottomButtonEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramChannelBottomButtonArguments
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case let .option(_, titleKey, value, selected, _):
            return ItemListCheckboxItem(
                presentationData: presentationData,
                title: strings[titleKey],
                style: .right,
                checked: selected,
                zeroSeparatorInsets: false,
                sectionId: self.section,
                action: {
                    arguments.selectValue(value)
                }
            )
        }
    }
}

private func grvmChannelBottomButtonEntries(
    theme: PresentationTheme,
    selectedValue: Int32
) -> [AyuGramChannelBottomButtonEntry] {
    return [
        .option(theme, .channelsBottomDiscuss, value: 1, selected: selectedValue == 1, index: 0),
        .option(theme, .channelsBottomHide, value: 0, selected: selectedValue == 0, index: 1),
    ]
}

public func ayuGramChannelBottomButtonController(
    context: AccountContext,
    currentValue: Int32,
    onSelect: @escaping (Int32) -> Void
) -> ViewController {
    let initialValue = grvmNormalizedChannelBottomButtonValue(currentValue)
    let selectedValueState = Atomic<Int32>(value: initialValue)
    let selectedValuePromise = ValuePromise<Int32>(initialValue, ignoreRepeated: true)
    let arguments = AyuGramChannelBottomButtonArguments(selectValue: { rawValue in
        let value = grvmNormalizedChannelBottomButtonValue(rawValue)
        let previousValue = selectedValueState.swap(value)
        guard previousValue != value else {
            return
        }
        selectedValuePromise.set(value)
        onSelect(value)
    })

    let signal = combineLatest(context.sharedContext.presentationData, selectedValuePromise.get())
    |> map { presentationData, selectedValue -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let entries = grvmChannelBottomButtonEntries(
            theme: presentationData.theme,
            selectedValue: selectedValue
        )
        return (
            ItemListControllerState(
                presentationData: ItemListPresentationData(presentationData),
                title: .text(strings[.channelsBottomButton]),
                leftNavigationButton: nil,
                rightNavigationButton: nil,
                backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back),
                animateChanges: true
            ),
            (
                ItemListNodeState(
                    presentationData: ItemListPresentationData(presentationData),
                    entries: entries,
                    style: .blocks,
                    animateChanges: true
                ),
                arguments
            )
        )
    }
    return ItemListController(context: context, state: signal)
}
