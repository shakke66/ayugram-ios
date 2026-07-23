import Foundation
import Postbox
import TelegramCore
import SwiftSignalKit

public enum RenderedTotalUnreadCountType {
    case raw
    case filtered
}

public func renderedTotalUnreadCount(inAppNotificationSettings: InAppNotificationSettings, transaction: Transaction, accountPeerId: PeerId? = nil) -> (Int32, RenderedTotalUnreadCountType) {
    let totalUnreadState = transaction.getTotalUnreadState(groupId: .root)
    return renderedTotalUnreadCount(inAppSettings: inAppNotificationSettings, totalUnreadState: totalUnreadState, accountPeerId: accountPeerId)
}

public func renderedTotalUnreadCount(inAppSettings: InAppNotificationSettings, totalUnreadState: ChatListTotalUnreadState, accountPeerId: PeerId? = nil, groupId: PeerGroupId = .root) -> (Int32, RenderedTotalUnreadCountType) {
    let type: RenderedTotalUnreadCountType
    switch inAppSettings.totalUnreadCountDisplayStyle {
        case .filtered:
            type = .filtered
    }
    let displayState = accountPeerId.flatMap { accountPeerId in
        AyuGramHooks.adjustedTotalUnreadState?(accountPeerId, groupId, totalUnreadState)
    } ?? totalUnreadState
    return (displayState.count(for: inAppSettings.totalUnreadCountDisplayStyle.category, in: inAppSettings.totalUnreadCountDisplayCategory.statsType, with: inAppSettings.totalUnreadCountIncludeTags), type)
}

public func renderedTotalUnreadCount(accountManager: AccountManager<TelegramAccountManagerTypes>, engine: TelegramEngine) -> Signal<(Int32, RenderedTotalUnreadCountType), NoError> {
    return combineLatest(
        accountManager.sharedData(keys: [ApplicationSpecificSharedDataKeys.inAppNotificationSettings]),
        engine.data.subscribe(
            TelegramEngine.EngineData.Item.Messages.TotalReadCounters()
        ),
        AyuGramHooks.filteredUnreadStateUpdates?(engine.account.peerId) ?? .single(0)
    )
    |> map { sharedData, totalReadCounters, _ -> (Int32, RenderedTotalUnreadCountType) in
        let inAppSettings: InAppNotificationSettings
        if let value = sharedData.entries[ApplicationSpecificSharedDataKeys.inAppNotificationSettings]?.get(InAppNotificationSettings.self) {
            inAppSettings = value
        } else {
            inAppSettings = .defaultSettings
        }
        let type: RenderedTotalUnreadCountType
        switch inAppSettings.totalUnreadCountDisplayStyle {
            case .filtered:
                type = .filtered
        }
        let totalUnreadState = AyuGramHooks.adjustedTotalUnreadState?(
            engine.account.peerId,
            .root,
            totalReadCounters._asCounters()
        ) ?? totalReadCounters._asCounters()
        return (totalUnreadState.count(for: inAppSettings.totalUnreadCountDisplayStyle.category, in: inAppSettings.totalUnreadCountDisplayCategory.statsType, with: inAppSettings.totalUnreadCountIncludeTags), type)
    }
    |> distinctUntilChanged(isEqual: { lhs, rhs in
        return lhs == rhs
    })
}
