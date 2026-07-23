import Foundation
import UIKit
import Display
import SwiftSignalKit
import TelegramPresentationData
import ItemListUI
import AccountContext

private final class AyuGramIntegerValueArguments {
    let updateValue: (Int32) -> Void

    init(updateValue: @escaping (Int32) -> Void) {
        self.updateValue = updateValue
    }
}

private enum AyuGramIntegerValueEntry: ItemListNodeEntry {
    case slider(PresentationTheme, GRVMgramStringKey, Int32, ClosedRange<Int32>, Bool)

    var section: ItemListSectionId {
        return 0
    }

    var stableId: Int32 {
        return 0
    }

    static func ==(lhs: AyuGramIntegerValueEntry, rhs: AyuGramIntegerValueEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.slider(lhsTheme, lhsTitle, lhsValue, lhsRange, lhsPreview), .slider(rhsTheme, rhsTitle, rhsValue, rhsRange, rhsPreview)):
            return lhsTheme === rhsTheme
                && lhsTitle == rhsTitle
                && lhsValue == rhsValue
                && lhsRange == rhsRange
                && lhsPreview == rhsPreview
        }
    }

    static func <(lhs: AyuGramIntegerValueEntry, rhs: AyuGramIntegerValueEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramIntegerValueArguments
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case let .slider(theme, titleKey, value, range, showsAvatarPreview):
            return GRVMIntegerSliderItem(
                presentationData: presentationData,
                title: strings[titleKey],
                value: value,
                range: range,
                previewImage: showsAvatarPreview ? grvmAvatarPreviewImage(theme: theme, value: value) : nil,
                sectionId: self.section,
                updated: arguments.updateValue
            )
        }
    }
}

private func grvmAvatarPreviewImage(theme: PresentationTheme, value: Int32) -> UIImage? {
    let imageSize = CGSize(width: 96.0, height: 96.0)
    let clampedValue = min(50, max(0, value))
    let cornerRadius = imageSize.width * CGFloat(clampedValue) / 100.0
    return generateImage(imageSize, opaque: false, rotatedContext: { size, context in
        let bounds = CGRect(origin: .zero, size: size)
        context.clear(bounds)
        context.saveGState()
        context.addPath(CGPath(
            roundedRect: bounds,
            cornerWidth: cornerRadius,
            cornerHeight: cornerRadius,
            transform: nil
        ))
        context.clip()
        context.setFillColor(theme.list.itemAccentColor.cgColor)
        context.fill(bounds)

        context.setFillColor(UIColor.white.withAlphaComponent(0.92).cgColor)
        context.fillEllipse(in: CGRect(x: 31.0, y: 19.0, width: 34.0, height: 34.0))
        context.fillEllipse(in: CGRect(x: 17.0, y: 56.0, width: 62.0, height: 52.0))
        context.restoreGState()
    })
}

private func ayuGramIntegerValueController(
    context: AccountContext,
    titleKey: GRVMgramStringKey,
    currentValue: Int32,
    range: ClosedRange<Int32>,
    showsAvatarPreview: Bool,
    onSelect: @escaping (Int32) -> Void
) -> ViewController {
    let initialValue = min(range.upperBound, max(range.lowerBound, currentValue))
    let currentValueState = Atomic<Int32>(value: initialValue)
    let currentValuePromise = ValuePromise<Int32>(initialValue, ignoreRepeated: true)
    let arguments = AyuGramIntegerValueArguments(updateValue: { rawValue in
        let value = min(range.upperBound, max(range.lowerBound, rawValue))
        let previousValue = currentValueState.swap(value)
        guard previousValue != value else {
            return
        }
        currentValuePromise.set(value)
        onSelect(value)
    })

    let signal = combineLatest(context.sharedContext.presentationData, currentValuePromise.get())
    |> map { presentationData, value -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let entries: [AyuGramIntegerValueEntry] = [
            .slider(presentationData.theme, titleKey, value, range, showsAvatarPreview)
        ]
        return (
            ItemListControllerState(
                presentationData: ItemListPresentationData(presentationData),
                title: .text(strings[titleKey]),
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

public func ayuGramAvatarCornersController(
    context: AccountContext,
    currentValue: Int32,
    onSelect: @escaping (Int32) -> Void
) -> ViewController {
    return ayuGramIntegerValueController(
        context: context,
        titleKey: .appearanceAvatarCorners,
        currentValue: currentValue,
        range: 0 ... 50,
        showsAvatarPreview: true,
        onSelect: onSelect
    )
}

public func ayuGramRecentStickersCountController(
    context: AccountContext,
    currentValue: Int32,
    onSelect: @escaping (Int32) -> Void
) -> ViewController {
    return ayuGramIntegerValueController(
        context: context,
        titleKey: .stickersRecent,
        currentValue: currentValue,
        range: 1 ... 200,
        showsAvatarPreview: false,
        onSelect: onSelect
    )
}
