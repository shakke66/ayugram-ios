import Foundation
import UIKit
import Display
import SwiftSignalKit
import Postbox
import TelegramCore
import TelegramPresentationData
import ItemListUI
import AccountContext
import AyuGramLib

private final class AyuGramShadowBanArguments {
    let addPeer: () -> Void
    let removePeer: (Int64) -> Void

    init(addPeer: @escaping () -> Void, removePeer: @escaping (Int64) -> Void) {
        self.addPeer = addPeer
        self.removePeer = removePeer
    }
}

private enum AyuGramShadowBanEntry: ItemListNodeEntry {
    case header(PresentationTheme)
    case peer(PresentationTheme, Int32, Int64)
    case empty(PresentationTheme)
    case add(PresentationTheme)

    var section: ItemListSectionId {
        return 0
    }

    var stableId: Int32 {
        switch self {
        case .header: return 0
        case let .peer(_, index, _): return 100 + index
        case .empty: return 9000
        case .add: return 9001
        }
    }

    static func ==(lhs: AyuGramShadowBanEntry, rhs: AyuGramShadowBanEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.header(lt), .header(rt)),
             let (.empty(lt), .empty(rt)),
             let (.add(lt), .add(rt)):
            return lt === rt
        case let (.peer(lt, li, lp), .peer(rt, ri, rp)):
            return lt === rt && li == ri && lp == rp
        default:
            return false
        }
    }

    static func <(lhs: AyuGramShadowBanEntry, rhs: AyuGramShadowBanEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramShadowBanArguments
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case .header:
            return ItemListSectionHeaderItem(
                presentationData: presentationData,
                text: strings[.shadowTitle],
                sectionId: self.section
            )
        case let .peer(_, _, peerId):
            return ItemListCheckboxItem(
                presentationData: presentationData,
                title: "\(peerId)",
                style: .right,
                checked: true,
                zeroSeparatorInsets: false,
                sectionId: self.section,
                action: {},
                deleteAction: {
                    arguments.removePeer(peerId)
                }
            )
        case .empty:
            return ItemListTextItem(
                presentationData: presentationData,
                text: .plain(strings[.shadowEmpty]),
                sectionId: self.section
            )
        case .add:
            return ItemListActionItem(
                presentationData: presentationData,
                title: strings[.shadowAdd],
                kind: .generic,
                alignment: .natural,
                sectionId: self.section,
                style: .blocks,
                action: arguments.addPeer
            )
        }
    }
}

private func ayuGramShadowBanEntries(
    settings: AyuGramSettings,
    presentationData: PresentationData
) -> [AyuGramShadowBanEntry] {
    let theme = presentationData.theme
    var entries: [AyuGramShadowBanEntry] = [.header(theme)]
    for (index, peerId) in settings.shadowBanIds.enumerated() {
        entries.append(.peer(theme, Int32(index), peerId))
    }
    if settings.shadowBanIds.isEmpty {
        entries.append(.empty(theme))
    }
    entries.append(.add(theme))
    return entries
}

public func ayuGramShadowBanController(context: AccountContext) -> ViewController {
    var pushControllerImpl: ((ViewController) -> Void)?

    let arguments = AyuGramShadowBanArguments(
        addPeer: {
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            let strings = GRVMgramStrings(presentationData.strings)
            let controller = context.sharedContext.makePeerSelectionController(
                PeerSelectionControllerParams(
                    context: context,
                    filter: [],
                    hasContactSelector: false,
                    title: strings[.shadowAddPrompt]
                )
            )
            controller.peerSelected = { [weak controller] peer, _ in
                let peerId = peer.id.toInt64()
                let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                    var settings = settings
                    if !settings.shadowBanIds.contains(peerId) {
                        settings.shadowBanIds.append(peerId)
                    }
                    return settings
                }.startStandalone()
                controller?.dismiss()
            }
            pushControllerImpl?(controller)
        },
        removePeer: { peerId in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                var settings = settings
                settings.shadowBanIds.removeAll { $0 == peerId }
                return settings
            }.startStandalone()
        }
    )

    let signal = combineLatest(
        context.sharedContext.presentationData,
        grvmSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager)
    )
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        return (
            ItemListControllerState(
                presentationData: ItemListPresentationData(presentationData),
                title: .text(strings[.shadowTitle]),
                leftNavigationButton: nil,
                rightNavigationButton: nil,
                backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
            ),
            (
                ItemListNodeState(
                    presentationData: ItemListPresentationData(presentationData),
                    entries: ayuGramShadowBanEntries(
                        settings: settings,
                        presentationData: presentationData
                    ),
                    style: .blocks
                ),
                arguments
            )
        )
    }

    let controller = ItemListController(context: context, state: signal)
    pushControllerImpl = { [weak controller] child in
        controller?.push(child)
    }
    return controller
}
