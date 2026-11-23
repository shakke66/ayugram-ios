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
    case peer(PresentationTheme, Int32, Int64, String)
    case empty(PresentationTheme)
    case add(PresentationTheme)

    var section: ItemListSectionId {
        return 0
    }

    var stableId: Int32 {
        switch self {
        case .header: return 0
        case let .peer(_, index, _, _): return 100 + index
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
        case let (.peer(lt, li, lp, ltitle), .peer(rt, ri, rp, rtitle)):
            return lt === rt && li == ri && lp == rp && ltitle == rtitle
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
        case let .peer(_, _, peerId, title):
            return ItemListCheckboxItem(
                presentationData: presentationData,
                title: title,
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

private func ayuGramShadowBanPeerIds(settings: AyuGramSettings, accountPeerId: PeerId) -> [Int64] {
    return GRVMShadowBanPolicy.normalizedPeerIds(
        settings.shadowBanIds,
        accountPeerId: accountPeerId.toInt64()
    )
}

// The stored value is the internal PeerId; show who it is: the name and the public Telegram ID (as in the
// message menu), or only the ID while the peer is unknown locally. Also used by the filter screens.
func ayuGramPeerTitleWithPublicId(peerId: Int64, peer: EnginePeer?, presentationData: PresentationData) -> String {
    let id = PeerId(peerId)
    let publicId = grvmFormatPeerId(id, format: .botAPI)
    if let peer {
        return "\(peer.displayTitle(strings: presentationData.strings, displayOrder: presentationData.nameDisplayOrder)) (\(publicId))"
    }
    return publicId
}

private func ayuGramShadowBanEntries(
    settings: AyuGramSettings,
    accountPeerId: PeerId,
    peers: [EnginePeer.Id: EnginePeer?],
    presentationData: PresentationData
) -> [AyuGramShadowBanEntry] {
    let theme = presentationData.theme
    let peerIds = ayuGramShadowBanPeerIds(settings: settings, accountPeerId: accountPeerId)
    var entries: [AyuGramShadowBanEntry] = [.header(theme)]
    for (index, peerId) in peerIds.enumerated() {
        let peer = peers[PeerId(peerId)] ?? nil
        entries.append(.peer(theme, Int32(index), peerId, ayuGramPeerTitleWithPublicId(peerId: peerId, peer: peer, presentationData: presentationData)))
    }
    if peerIds.isEmpty {
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
                    filter: [.excludeSavedMessages],
                    hasContactSelector: false,
                    title: strings[.shadowAddPrompt]
                )
            )
            controller.peerSelected = { [weak controller] peer, _ in
                let peerId = peer.id.toInt64()
                let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                    var settings = settings
                    settings.shadowBanIds = GRVMShadowBanPolicy.updatedPeerIds(
                        settings.shadowBanIds,
                        peerId: peerId,
                        isBanned: true,
                        accountPeerId: context.account.peerId.toInt64()
                    )
                    return settings
                }.startStandalone()
                controller?.dismiss()
            }
            pushControllerImpl?(controller)
        },
        removePeer: { peerId in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                var settings = settings
                settings.shadowBanIds = GRVMShadowBanPolicy.updatedPeerIds(
                    settings.shadowBanIds,
                    peerId: peerId,
                    isBanned: false,
                    accountPeerId: context.account.peerId.toInt64()
                )
                return settings
            }.startStandalone()
        }
    )

    let settingsAndPeers = grvmSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager)
    |> mapToSignal { settings -> Signal<(AyuGramSettings, [EnginePeer.Id: EnginePeer?]), NoError> in
        let peerIds = ayuGramShadowBanPeerIds(settings: settings, accountPeerId: context.account.peerId).map { PeerId($0) }
        return context.engine.data.subscribe(EngineDataMap(peerIds.map(TelegramEngine.EngineData.Item.Peer.Peer.init(id:))))
        |> map { peers -> (AyuGramSettings, [EnginePeer.Id: EnginePeer?]) in
            return (settings, peers)
        }
    }

    let signal = combineLatest(
        context.sharedContext.presentationData,
        settingsAndPeers
    )
    |> map { presentationData, settingsAndPeers -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let (settings, peers) = settingsAndPeers
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
                        accountPeerId: context.account.peerId,
                        peers: peers,
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
