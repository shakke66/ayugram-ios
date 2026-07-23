import Foundation
import UIKit
import Display
import AsyncDisplayKit
import SwiftSignalKit
import TelegramPresentationData
import ItemListUI

final class GRVMIntegerSliderItem: ListViewItem, ItemListItem {
    let presentationData: ItemListPresentationData
    let title: String
    let value: Int32
    let range: ClosedRange<Int32>
    let previewImage: UIImage?
    let updated: (Int32) -> Void
    let sectionId: ItemListSectionId

    init(
        presentationData: ItemListPresentationData,
        title: String,
        value: Int32,
        range: ClosedRange<Int32>,
        previewImage: UIImage? = nil,
        sectionId: ItemListSectionId,
        updated: @escaping (Int32) -> Void
    ) {
        self.presentationData = presentationData
        self.title = title
        self.value = value
        self.range = range
        self.previewImage = previewImage
        self.sectionId = sectionId
        self.updated = updated
    }

    func nodeConfiguredForParams(
        async: @escaping (@escaping () -> Void) -> Void,
        params: ListViewItemLayoutParams,
        synchronousLoads: Bool,
        previousItem: ListViewItem?,
        nextItem: ListViewItem?,
        completion: @escaping (ListViewItemNode, @escaping () -> (Signal<Void, NoError>?, (ListViewItemApply) -> Void)) -> Void
    ) {
        async {
            let node = GRVMIntegerSliderItemNode()
            let (layout, apply) = node.asyncLayout()(
                self,
                params,
                itemListNeighbors(item: self, topItem: previousItem as? ItemListItem, bottomItem: nextItem as? ItemListItem)
            )
            node.contentSize = layout.contentSize
            node.insets = layout.insets
            Queue.mainQueue().async {
                completion(node, {
                    return (nil, { _ in apply() })
                })
            }
        }
    }

    func updateNode(
        async: @escaping (@escaping () -> Void) -> Void,
        node: @escaping () -> ListViewItemNode,
        params: ListViewItemLayoutParams,
        previousItem: ListViewItem?,
        nextItem: ListViewItem?,
        animation: ListViewItemUpdateAnimation,
        completion: @escaping (ListViewItemNodeLayout, @escaping (ListViewItemApply) -> Void) -> Void
    ) {
        Queue.mainQueue().async {
            guard let nodeValue = node() as? GRVMIntegerSliderItemNode else {
                return
            }
            let makeLayout = nodeValue.asyncLayout()
            async {
                let (layout, apply) = makeLayout(
                    self,
                    params,
                    itemListNeighbors(item: self, topItem: previousItem as? ItemListItem, bottomItem: nextItem as? ItemListItem)
                )
                Queue.mainQueue().async {
                    completion(layout, { _ in apply() })
                }
            }
        }
    }
}

private final class GRVMIntegerSliderItemNode: ListViewItemNode, ItemListItemNode {
    private let backgroundNode: ASDisplayNode
    private let topStripeNode: ASDisplayNode
    private let bottomStripeNode: ASDisplayNode
    private let maskNode: ASImageNode
    private let previewNode: ASImageNode
    private let titleNode: ImmediateTextNode
    private let valueNode: ImmediateTextNode
    private var sliderView: UISlider?
    private var item: GRVMIntegerSliderItem?
    private var lastEmittedValue: Int32?

    var tag: ItemListItemTag? {
        return nil
    }

    init() {
        self.backgroundNode = ASDisplayNode()
        self.backgroundNode.isLayerBacked = true
        self.topStripeNode = ASDisplayNode()
        self.topStripeNode.isLayerBacked = true
        self.bottomStripeNode = ASDisplayNode()
        self.bottomStripeNode.isLayerBacked = true
        self.maskNode = ASImageNode()
        self.maskNode.isUserInteractionEnabled = false
        self.previewNode = ASImageNode()
        self.previewNode.displaysAsynchronously = false
        self.previewNode.displayWithoutProcessing = true
        self.titleNode = ImmediateTextNode()
        self.titleNode.displaysAsynchronously = false
        self.titleNode.maximumNumberOfLines = 2
        self.valueNode = ImmediateTextNode()
        self.valueNode.displaysAsynchronously = false
        self.valueNode.maximumNumberOfLines = 1

        super.init(layerBacked: false)

        self.addSubnode(self.titleNode)
        self.addSubnode(self.valueNode)
        self.addSubnode(self.previewNode)
    }

    override func didLoad() {
        super.didLoad()
        let sliderView = UISlider(frame: .zero)
        sliderView.isContinuous = true
        sliderView.addTarget(self, action: #selector(self.sliderValueChanged), for: .valueChanged)
        self.view.addSubview(sliderView)
        self.sliderView = sliderView
    }

    func asyncLayout() -> (_ item: GRVMIntegerSliderItem, _ params: ListViewItemLayoutParams, _ neighbors: ItemListNeighbors) -> (ListViewItemNodeLayout, () -> Void) {
        let currentItem = self.item
        return { item, params, neighbors in
            let sideInset: CGFloat = params.leftInset + 16.0
            let rightInset: CGFloat = params.rightInset + 16.0
            let valueFont = Font.regular(item.presentationData.fontSize.itemListBaseFontSize)
            let titleFont = Font.regular(item.presentationData.fontSize.itemListBaseFontSize)
            let valueText = "\(item.value)"
            let valueWidth: CGFloat = 56.0
            let titleWidth = max(1.0, params.width - sideInset - rightInset - valueWidth - 16.0)
            self.titleNode.attributedText = NSAttributedString(
                string: item.title,
                font: titleFont,
                textColor: item.presentationData.theme.list.itemPrimaryTextColor
            )
            self.valueNode.attributedText = NSAttributedString(
                string: valueText,
                font: valueFont,
                textColor: item.presentationData.theme.list.itemAccentColor
            )
            let titleSize = self.titleNode.updateLayout(CGSize(width: titleWidth, height: CGFloat.greatestFiniteMagnitude))
            let resolvedValueSize = self.valueNode.updateLayout(CGSize(width: valueWidth, height: CGFloat.greatestFiniteMagnitude))
            let labelHeight = max(titleSize.height, resolvedValueSize.height)
            let previewHeight: CGFloat = item.previewImage == nil ? 0.0 : 112.0
            let titleY = previewHeight + 12.0
            let sliderY = titleY + labelHeight + 4.0
            let contentHeight = sliderY + 44.0 + 8.0
            let insets = itemListNeighborsGroupedInsets(neighbors, params)
            let layout = ListViewItemNodeLayout(
                contentSize: CGSize(width: params.width, height: contentHeight),
                insets: insets
            )

            let themeUpdated = currentItem?.presentationData.theme !== item.presentationData.theme
            return (layout, { [weak self] in
                guard let self else {
                    return
                }
                self.item = item
                self.lastEmittedValue = item.value

                if themeUpdated {
                    self.backgroundNode.backgroundColor = item.presentationData.theme.list.itemBlocksBackgroundColor
                    self.topStripeNode.backgroundColor = item.presentationData.theme.list.itemBlocksSeparatorColor
                    self.bottomStripeNode.backgroundColor = item.presentationData.theme.list.itemBlocksSeparatorColor
                }

                if self.backgroundNode.supernode == nil {
                    self.insertSubnode(self.backgroundNode, at: 0)
                    self.insertSubnode(self.topStripeNode, at: 1)
                    self.insertSubnode(self.bottomStripeNode, at: 2)
                    self.insertSubnode(self.maskNode, at: 3)
                }

                let separatorHeight = UIScreenPixel
                let hasCorners = itemListHasRoundedBlockLayout(params)
                var hasTopCorners = false
                var hasBottomCorners = false
                switch neighbors.top {
                case .sameSection(false):
                    self.topStripeNode.isHidden = true
                default:
                    hasTopCorners = true
                    self.topStripeNode.isHidden = hasCorners
                }
                let bottomStripeInset: CGFloat
                switch neighbors.bottom {
                case .sameSection(false):
                    bottomStripeInset = sideInset
                    self.bottomStripeNode.isHidden = false
                default:
                    bottomStripeInset = 0.0
                    hasBottomCorners = true
                    self.bottomStripeNode.isHidden = hasCorners
                }

                self.maskNode.image = hasCorners ? PresentationResourcesItemList.cornersImage(
                    item.presentationData.theme,
                    top: hasTopCorners,
                    bottom: hasBottomCorners
                ) : nil
                self.backgroundNode.frame = CGRect(
                    x: 0.0,
                    y: -min(insets.top, separatorHeight),
                    width: params.width,
                    height: contentHeight + min(insets.top, separatorHeight) + min(insets.bottom, separatorHeight)
                )
                self.maskNode.frame = self.backgroundNode.frame.insetBy(dx: params.leftInset, dy: 0.0)
                self.topStripeNode.frame = CGRect(x: 0.0, y: -min(insets.top, separatorHeight), width: params.width, height: separatorHeight)
                self.bottomStripeNode.frame = CGRect(
                    x: bottomStripeInset,
                    y: contentHeight - separatorHeight,
                    width: params.width - params.rightInset - bottomStripeInset,
                    height: separatorHeight
                )

                self.previewNode.image = item.previewImage
                self.previewNode.isHidden = item.previewImage == nil
                if let previewImage = item.previewImage {
                    self.previewNode.frame = CGRect(
                        x: floor((params.width - previewImage.size.width) / 2.0),
                        y: 12.0,
                        width: previewImage.size.width,
                        height: previewImage.size.height
                    )
                }
                self.titleNode.frame = CGRect(x: sideInset, y: titleY, width: titleSize.width, height: titleSize.height)
                self.valueNode.frame = CGRect(
                    x: params.width - rightInset - resolvedValueSize.width,
                    y: titleY,
                    width: resolvedValueSize.width,
                    height: resolvedValueSize.height
                )

                if let sliderView = self.sliderView {
                    sliderView.minimumValue = Float(item.range.lowerBound)
                    sliderView.maximumValue = Float(item.range.upperBound)
                    sliderView.isContinuous = true
                    sliderView.minimumTrackTintColor = item.presentationData.theme.list.itemAccentColor
                    sliderView.maximumTrackTintColor = item.presentationData.theme.list.itemSwitchColors.frameColor
                    sliderView.tintColor = item.presentationData.theme.list.itemAccentColor
                    sliderView.setValue(Float(item.value), animated: false)
                    sliderView.accessibilityLabel = item.title
                    sliderView.accessibilityValue = valueText
                    sliderView.frame = CGRect(
                        x: sideInset,
                        y: sliderY,
                        width: params.width - sideInset - rightInset,
                        height: 44.0
                    )
                }
            })
        }
    }

    @objc private func sliderValueChanged() {
        guard let sliderView = self.sliderView, let item = self.item else {
            return
        }
        let roundedValue = Int32(sliderView.value.rounded())
        let value = min(item.range.upperBound, max(item.range.lowerBound, roundedValue))
        sliderView.setValue(Float(value), animated: false)
        sliderView.accessibilityValue = "\(value)"
        guard self.lastEmittedValue != value else {
            return
        }
        self.lastEmittedValue = value
        self.item?.updated(value)
    }

    override func animateInsertion(_ currentTimestamp: Double, duration: Double, options: ListViewItemAnimationOptions) {
        self.layer.animateAlpha(from: 0.0, to: 1.0, duration: 0.4)
    }

    override func animateRemoved(_ currentTimestamp: Double, duration: Double) {
        self.layer.animateAlpha(from: 1.0, to: 0.0, duration: 0.15, removeOnCompletion: false)
    }
}
