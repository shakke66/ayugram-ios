import Foundation
import UIKit
import Display
import AsyncDisplayKit
import SwiftSignalKit
import TelegramPresentationData
import ItemListUI
import PresentationDataUtils
import AccountContext

private final class AyuGramCodeFontArguments {
    let selectFont: (String) -> Void

    init(selectFont: @escaping (String) -> Void) {
        self.selectFont = selectFont
    }
}

private enum AyuGramCodeFontEntry: ItemListNodeEntry {
    case font(PresentationTheme, String, Bool, Int32)

    var section: ItemListSectionId {
        return 0
    }

    var stableId: Int32 {
        switch self {
        case let .font(_, _, _, index):
            return index
        }
    }

    static func ==(lhs: AyuGramCodeFontEntry, rhs: AyuGramCodeFontEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.font(lhsTheme, lhsName, lhsSelected, lhsIndex), .font(rhsTheme, rhsName, rhsSelected, rhsIndex)):
            return lhsTheme === rhsTheme && lhsName == rhsName && lhsSelected == rhsSelected && lhsIndex == rhsIndex
        }
    }

    static func <(lhs: AyuGramCodeFontEntry, rhs: AyuGramCodeFontEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramCodeFontArguments
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case let .font(_, fontName, selected, _):
            return ItemListCheckboxItem(
                presentationData: presentationData,
                title: fontName.isEmpty ? strings[.commonDefault] : fontName,
                style: .right,
                checked: selected,
                zeroSeparatorInsets: false,
                sectionId: self.section,
                action: {
                    arguments.selectFont(fontName)
                }
            )
        }
    }
}

private final class GRVMCodeFontPreviewFooterItem: ItemListControllerFooterItem {
    let theme: PresentationTheme
    let fontName: String
    let previewText: String

    init(theme: PresentationTheme, fontName: String, previewText: String) {
        self.theme = theme
        self.fontName = fontName
        self.previewText = previewText
    }

    func isEqual(to: ItemListControllerFooterItem) -> Bool {
        guard let item = to as? GRVMCodeFontPreviewFooterItem else {
            return false
        }
        return self.theme === item.theme
            && self.fontName == item.fontName
            && self.previewText == item.previewText
    }

    func node(current: ItemListControllerFooterItemNode?) -> ItemListControllerFooterItemNode {
        if let current = current as? GRVMCodeFontPreviewFooterItemNode {
            current.item = self
            return current
        } else {
            return GRVMCodeFontPreviewFooterItemNode(item: self)
        }
    }
}

private final class GRVMCodeFontPreviewFooterItemNode: ItemListControllerFooterItemNode {
    private let backgroundNode: NavigationBackgroundNode
    private let separatorNode: ASDisplayNode
    private let textNode: ImmediateTextNode
    private var validLayout: ContainerViewLayout?

    var item: GRVMCodeFontPreviewFooterItem {
        didSet {
            self.updateItem()
            if let validLayout = self.validLayout {
                let _ = self.updateLayout(layout: validLayout, transition: .immediate)
            }
        }
    }

    init(item: GRVMCodeFontPreviewFooterItem) {
        self.item = item
        self.backgroundNode = NavigationBackgroundNode(color: item.theme.rootController.tabBar.backgroundColor)
        self.separatorNode = ASDisplayNode()
        self.textNode = ImmediateTextNode()
        self.textNode.displaysAsynchronously = false
        self.textNode.maximumNumberOfLines = 2

        super.init()

        self.addSubnode(self.backgroundNode)
        self.addSubnode(self.separatorNode)
        self.addSubnode(self.textNode)
        self.updateItem()
    }

    private func updateItem() {
        self.backgroundNode.updateColor(color: self.item.theme.rootController.tabBar.backgroundColor, transition: .immediate)
        self.separatorNode.backgroundColor = self.item.theme.rootController.tabBar.separatorColor
        let previewFont = UIFont(name: self.item.fontName, size: 16.0) ?? Font.monospace(16.0)
        self.textNode.attributedText = NSAttributedString(
            string: self.item.previewText,
            font: previewFont,
            textColor: self.item.theme.list.itemPrimaryTextColor,
            paragraphAlignment: .left
        )
    }

    override func updateBackgroundAlpha(_ alpha: CGFloat, transition: ContainedViewLayoutTransition) {
        transition.updateAlpha(node: self.backgroundNode, alpha: alpha)
        transition.updateAlpha(node: self.separatorNode, alpha: alpha)
    }

    override func updateLayout(layout: ContainerViewLayout, transition: ContainedViewLayoutTransition) -> CGFloat {
        self.validLayout = layout
        let sideInset: CGFloat = 16.0
        let textSize = self.textNode.updateLayout(CGSize(
            width: layout.size.width - layout.safeInsets.left - layout.safeInsets.right - sideInset * 2.0,
            height: CGFloat.greatestFiniteMagnitude
        ))
        let contentHeight = max(72.0, textSize.height + 24.0)
        let height = contentHeight + layout.intrinsicInsets.bottom
        let panelFrame = CGRect(
            x: 0.0,
            y: layout.size.height - height,
            width: layout.size.width,
            height: height
        )

        transition.updateFrame(node: self.backgroundNode, frame: panelFrame)
        self.backgroundNode.update(size: panelFrame.size, transition: transition)
        transition.updateFrame(
            node: self.separatorNode,
            frame: CGRect(x: 0.0, y: panelFrame.minY, width: panelFrame.width, height: UIScreenPixel)
        )
        transition.updateFrame(
            node: self.textNode,
            frame: CGRect(
                x: layout.safeInsets.left + sideInset,
                y: panelFrame.minY + 12.0,
                width: textSize.width,
                height: textSize.height
            )
        )
        return height
    }

    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        return self.backgroundNode.frame.contains(point)
    }
}

public func ayuGramCodeFontController(
    context: AccountContext,
    currentFontName: String,
    onSelect: @escaping (String) -> Void
) -> ViewController {
    var fontNames: [String] = []
    for familyName in UIFont.familyNames.sorted() {
        fontNames.append(contentsOf: UIFont.fontNames(forFamilyName: familyName))
    }
    let availableFontNames = [""] + Array(Set(fontNames)).sorted()
    let initialFontName = availableFontNames.contains(currentFontName) ? currentFontName : ""
    let currentFontNameValue = Atomic<String>(value: initialFontName)
    let currentFontNamePromise = ValuePromise<String>(initialFontName, ignoreRepeated: true)

    let arguments = AyuGramCodeFontArguments(selectFont: { fontName in
        let previous = currentFontNameValue.swap(fontName)
        guard previous != fontName else {
            return
        }
        currentFontNamePromise.set(fontName)
        onSelect(fontName)
    })

    let signal = combineLatest(
        context.sharedContext.presentationData,
        currentFontNamePromise.get()
    )
    |> map { presentationData, selectedFontName -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let entries: [AyuGramCodeFontEntry] = availableFontNames.enumerated().map { index, fontName in
            return .font(presentationData.theme, fontName, fontName == selectedFontName, Int32(index))
        }
        let previewItem = GRVMCodeFontPreviewFooterItem(
            theme: presentationData.theme,
            fontName: selectedFontName,
            previewText: strings[.appearanceCodeFontPreview]
        )
        return (
            ItemListControllerState(
                presentationData: ItemListPresentationData(presentationData),
                title: .text(strings[.appearanceCodeFont]),
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
                    footerItem: previewItem,
                    animateChanges: true
                ),
                arguments
            )
        )
    }

    return ItemListController(context: context, state: signal)
}
