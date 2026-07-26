import Foundation
import UIKit
import Display
import SwiftSignalKit
import TelegramPresentationData
import ItemListUI
import AccountContext
import Postbox
import TelegramCore

private final class AyuGramIntegerValueArguments {
    let updateValue: (Int32) -> Void

    init(updateValue: @escaping (Int32) -> Void) {
        self.updateValue = updateValue
    }
}

private enum AyuGramIntegerValueEntry: ItemListNodeEntry {
    case slider(PresentationTheme, GRVMgramStringKey, Int32, ClosedRange<Int32>, UIImage?)

    var section: ItemListSectionId {
        return 0
    }

    var stableId: Int32 {
        return 0
    }

    static func ==(lhs: AyuGramIntegerValueEntry, rhs: AyuGramIntegerValueEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.slider(lhsTheme, lhsTitle, lhsValue, lhsRange, lhsPreviewImage), .slider(rhsTheme, rhsTitle, rhsValue, rhsRange, rhsPreviewImage)):
            return lhsTheme === rhsTheme
                && lhsTitle == rhsTitle
                && lhsValue == rhsValue
                && lhsRange == rhsRange
                && lhsPreviewImage === rhsPreviewImage
        }
    }

    static func <(lhs: AyuGramIntegerValueEntry, rhs: AyuGramIntegerValueEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramIntegerValueArguments
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case let .slider(_, titleKey, value, range, previewImage):
            return GRVMIntegerSliderItem(
                presentationData: presentationData,
                title: strings[titleKey],
                value: value,
                range: range,
                previewImage: previewImage,
                sectionId: self.section,
                updated: arguments.updateValue
            )
        }
    }
}

private func grvmAccountAvatarImage(context: AccountContext) -> Signal<UIImage?, NoError> {
    return context.account.postbox.peerView(id: context.account.peerId)
    |> mapToSignal { peerView -> Signal<UIImage?, NoError> in
        guard let peer = peerView.peers[peerView.peerId], let representation = peer.smallProfileImage else {
            return .single(nil)
        }

        let resourceData = context.account.postbox.mediaBox.resourceData(
            representation.resource,
            attemptSynchronously: true
        )
        return Signal { subscriber in
            subscriber.putNext(nil)
            var emittedResult = false
            let resourceDisposable = resourceData.start(next: { data in
                guard data.complete, !emittedResult else {
                    return
                }
                emittedResult = true
                subscriber.putNext(UIImage(contentsOfFile: data.path))
                subscriber.putCompletion()
            }, completed: {
                if !emittedResult {
                    emittedResult = true
                    subscriber.putCompletion()
                }
            })

            let fetchDisposable: Disposable
            if let peerReference = PeerReference(peer) {
                fetchDisposable = fetchedMediaResource(
                    mediaBox: context.account.postbox.mediaBox,
                    userLocation: .peer(peer.id),
                    userContentType: .avatar,
                    reference: MediaResourceReference.avatar(
                        peer: peerReference,
                        resource: representation.resource
                    )
                ).start()
            } else {
                fetchDisposable = fetchedMediaResource(
                    mediaBox: context.account.postbox.mediaBox,
                    userLocation: .other,
                    userContentType: .avatar,
                    reference: .standalone(resource: representation.resource)
                ).start()
            }

            return ActionDisposable {
                resourceDisposable.dispose()
                fetchDisposable.dispose()
            }
        }
    }
}

private func grvmAvatarPreviewImage(theme: PresentationTheme, value: Int32, avatarImage: UIImage?) -> UIImage? {
    let imageSize = CGSize(width: 96.0, height: 96.0)
    let clampedValue = min(50, max(0, value))
    let cornerRadius = imageSize.width * CGFloat(clampedValue) / 100.0
    return generateImage(imageSize, contextGenerator: { size, context in
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
        if let avatarImage, let cgImage = avatarImage.cgImage {
            let sourceSize = CGSize(width: CGFloat(cgImage.width), height: CGFloat(cgImage.height))
            let scale = max(size.width / sourceSize.width, size.height / sourceSize.height)
            let scaledSize = CGSize(width: sourceSize.width * scale, height: sourceSize.height * scale)
            let imageFrame = CGRect(
                x: floor((size.width - scaledSize.width) / 2.0),
                y: floor((size.height - scaledSize.height) / 2.0),
                width: scaledSize.width,
                height: scaledSize.height
            )
            context.draw(cgImage, in: imageFrame)
        } else {
            context.setFillColor(theme.list.itemAccentColor.cgColor)
            context.fill(bounds)

            context.setFillColor(UIColor.white.withAlphaComponent(0.92).cgColor)
            context.fillEllipse(in: CGRect(x: 31.0, y: 19.0, width: 34.0, height: 34.0))
            context.fillEllipse(in: CGRect(x: 17.0, y: 56.0, width: 62.0, height: 52.0))
        }
        context.restoreGState()
    })
}

private func ayuGramIntegerValueController(
    context: AccountContext,
    titleKey: GRVMgramStringKey,
    currentValue: Int32,
    range: ClosedRange<Int32>,
    showsAvatarPreview: Bool,
    avatarImage: Signal<UIImage?, NoError>? = nil,
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

    let signal = combineLatest(
        context.sharedContext.presentationData,
        currentValuePromise.get(),
        avatarImage ?? .single(nil)
    )
    |> map { presentationData, value, avatarImage -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let entries: [AyuGramIntegerValueEntry] = [
            .slider(
                presentationData.theme,
                titleKey,
                value,
                range,
                showsAvatarPreview ? grvmAvatarPreviewImage(
                    theme: presentationData.theme,
                    value: value,
                    avatarImage: avatarImage
                ) : nil
            )
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
        avatarImage: grvmAccountAvatarImage(context: context),
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
