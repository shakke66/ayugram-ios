import Foundation
import Postbox
import SwiftSignalKit

public enum GRVMDeletedMessagesPreservationResult {
    case disabled
    case preserved([MessageId: [String]])
    case unavailable
}

public final class AyuGramHooks {
    // MARK: - Spy Mode
    public static var onMessagesDeleted: (([Message]) -> Void)?
    public static var shouldSaveDeletedMessages: ((PeerId) -> Bool)?
    public static var preserveDeletedMessages: ((PeerId, [Message], GRVMDeletionSource) -> GRVMDeletedMessagesPreservationResult)?
    public static var preserveEditRevision: ((PeerId, Message, GRVMEditableMessageContent) -> Bool)?
    public static var hasEditHistory: ((PeerId, MessageId) -> Bool)?
    public static var shouldPreserveOneTimeMedia: ((PeerId) -> Bool)?
    public static var prepareConsumableMedia: ((PeerId, Message) -> Signal<Bool, NoError>)?
    public static var restoreConsumableMedia: ((PeerId, Message) -> Signal<Bool, NoError>)?

    // MARK: - Ghost Mode
    public static var shouldSuppressReadReceipts: ((PeerId) -> Bool)?
    public static var shouldSuppressPresence: ((PeerId) -> Bool)?
    public static var shouldSuppressTyping: ((PeerId) -> Bool)?
    public static var shouldSuppressStoryRead: ((PeerId) -> Bool)?
    public static var shouldSuppressContentRead: ((PeerId) -> Bool)?

    // MARK: - Premium & Ads
    public static var isLocalPremiumEnabled: ((PeerId) -> Bool)?
    public static var shouldDisableAds: ((PeerId) -> Bool)?

    // MARK: - General
    public static var shouldHideStories: ((PeerId) -> Bool)?
    public static var shouldDisableSimilarChannels: ((PeerId) -> Bool)?
    public static var similarChannelsDisabled: ((PeerId) -> Signal<Bool, NoError>)?
    public static var shouldDisableNotificationDelay: ((PeerId) -> Bool)?
    public static var shouldShowSeconds: ((PeerId) -> Bool)?
    public static var shouldShowDialogID: ((PeerId) -> Bool)?
    public static var shouldDisableExternalLinkWarning: ((PeerId) -> Bool)?
    public static var shouldConfirmStickers: ((PeerId) -> Bool)?
    public static var shouldConfirmGIF: ((PeerId) -> Bool)?
    public static var shouldConfirmVoice: ((PeerId) -> Bool)?
    public static var translationProvider: ((PeerId) -> GRVMTranslationProvider)?

    // MARK: - Appearance
    public static var chatAppearanceSettings: ((PeerId) -> GRVMChatAppearanceSettings)?
    public static private(set) var primaryChatAppearance = GRVMChatAppearanceSettings.default

    public static func chatAppearance(accountPeerId: PeerId) -> GRVMChatAppearanceSettings {
        return self.chatAppearanceSettings?(accountPeerId) ?? .default
    }

    public static func updatePrimaryChatAppearance(_ appearance: GRVMChatAppearanceSettings) {
        assert(Thread.isMainThread)
        self.primaryChatAppearance = appearance
    }

    public static var shouldHideNotificationBadge: (() -> Bool)?
    public static var shouldHideNotificationCounters: (() -> Bool)?
    public static var shouldHideFolderCounters: (() -> Bool)?
    public static var shouldHideAllChatsFolder: (() -> Bool)?

    // MARK: - Chats
    public static var shouldShowOnlyAddedStickers: (() -> Bool)?

    // MARK: - Reanimation (W0)
    public static var shouldSuppressUploadProgress: ((PeerId) -> Bool)?
    public static var shouldSaveForBots: (() -> Bool)?
    public static var codeFontName: (() -> String)?
    public static var shouldUseQuickAdminShortcuts: (() -> Bool)?
    public static var shouldShowChannelReactions: (() -> Bool)?
    public static var shouldShowGroupReactions: (() -> Bool)?
    public static var recentStickersLimit: (() -> Int32)?
    public static var channelBottomButtonMode: (() -> Int32)?

    // MARK: - Context menu visibility (W0) — 0 Hidden / 1 Visible / 2 WithModifier
    public static var contextMenuReactionsPanel: (() -> Int32)?
    public static var contextMenuViewsPanel: (() -> Int32)?
    public static var contextMenuHide: (() -> Int32)?
    public static var contextMenuUserMessages: (() -> Int32)?
    public static var contextMenuDetails: (() -> Int32)?
    public static var contextMenuRepeat: (() -> Int32)?

    // MARK: - 6.7.8 features (W0)
    public static var shouldSuggestGhostForStories: ((PeerId) -> Bool)?
    public static var shouldFilterZalgo: ((PeerId) -> Bool)?
    public static var shouldImproveLinkPreviews: ((PeerId) -> Bool)?
    public static var shouldHidePremiumStatuses: (() -> Bool)?
    public static var avatarCornerRadius: (() -> Int32)?
    public static var peerIdDisplayMode: ((PeerId) -> Int32)?     // 0 Hidden / 1 TelegramApi / 2 BotApi
    public static var sendWithoutSoundMode: ((PeerId) -> Int32)?  // 0 Never / 1 InGhost / 2 Always

    // MARK: - Filters / shadow-ban (заполняются в W4)
    public static var isMessageHiddenByFilter: ((PeerId, Message) -> Bool)?
    public static var isShadowBanned: ((PeerId, PeerId) -> Bool)?
    public static var matchingMessageFilterIds: ((PeerId, Message) -> [String])?
    public static var isShowingFilteredMessages: ((PeerId, PeerId) -> Bool)?
    public static var setShowingFilteredMessages: ((PeerId, PeerId, Bool) -> Void)?
    public static var messageFilterStateUpdates: ((PeerId) -> Signal<Int64, NoError>)?
    // Display-only unread corrections. These hooks never write read state back to Postbox.
    public static var adjustedUnreadPeerReadState: ((PeerId, PeerId, CombinedPeerReadState) -> CombinedPeerReadState)?
    public static var adjustedUnreadThreadCount: ((PeerId, PeerId, Int64, Int32) -> Int32)?
    public static var adjustedTotalUnreadState: ((PeerId, PeerGroupId, ChatListTotalUnreadState) -> ChatListTotalUnreadState)?
    public static var filteredUnreadStateUpdates: ((PeerId) -> Signal<Int64, NoError>)?
}

func grvmMergedEditStateAttributes(
    previous: [MessageAttribute],
    incoming: [MessageAttribute],
    markHistory: Bool
) -> [MessageAttribute] {
    var result = incoming
    if let deleted = previous.first(where: { $0 is GRVMDeletedMessageAttribute }) {
        result.removeAll(where: { $0 is GRVMDeletedMessageAttribute })
        result.append(deleted)
    }
    if let preservedConsumable = previous.first(where: { $0 is GRVMPreservedConsumableMediaAttribute }) {
        result.removeAll(where: { $0 is GRVMPreservedConsumableMediaAttribute })
        result.append(preservedConsumable)
    }

    let previousHistory = previous.first(where: { $0 is GRVMEditHistoryMessageAttribute })
    result.removeAll(where: { $0 is GRVMEditHistoryMessageAttribute })
    if markHistory {
        result.append(GRVMEditHistoryMessageAttribute(
            latestRevisionAt: Int32(Date().timeIntervalSince1970)
        ))
    } else if let previousHistory {
        result.append(previousHistory)
    }
    return result
}

func grvmPreserveEditRevisionIfNeeded(
    accountPeerId: PeerId,
    transaction: Transaction,
    id: MessageId,
    incoming: StoreMessage
) -> Bool {
    guard let previous = transaction.getMessage(id) else {
        return false
    }
    let previousContent = GRVMEditableMessageContent(message: previous)
    let incomingContent = GRVMEditableMessageContent(message: grvmMergedEditedMessage(
        previous: previous,
        incoming: incoming,
        markHistory: false
    ))
    guard previousContent != incomingContent else {
        return false
    }
    return AyuGramHooks.preserveEditRevision?(accountPeerId, previous, previousContent) == true
}

func grvmMergedEditedMessage(
    previous: Message,
    incoming: StoreMessage,
    markHistory: Bool
) -> StoreMessage {
    var updatedFlags = incoming.flags
    var updatedLocalTags = incoming.localTags
    if previous.localTags.contains(.OutgoingLiveLocation) {
        updatedLocalTags.insert(.OutgoingLiveLocation)
    }
    if previous.flags.contains(.Incoming) {
        updatedFlags.insert(.Incoming)
    } else {
        updatedFlags.remove(.Incoming)
    }

    var updatedMedia = incoming.media
    if let preservedConsumable = previous.attributes.first(where: { $0 is GRVMPreservedConsumableMediaAttribute }) as? GRVMPreservedConsumableMediaAttribute {
        let incomingMediaContainsTelegramMediaExpiredContent = incoming.media.contains(where: { $0 is TelegramMediaExpiredContent })
        if incoming.media.count > 0 && incomingMediaContainsTelegramMediaExpiredContent {
            updatedMedia = preservedConsumable.media
        }
    }
    if let previousPaidContent = previous.media.first(where: { $0 is TelegramMediaPaidContent })
        as? TelegramMediaPaidContent,
       case .full = previousPaidContent.extendedMedia.first {
        updatedMedia = previous.media
    }

    return incoming
        .withUpdatedLocalTags(updatedLocalTags)
        .withUpdatedFlags(updatedFlags)
        .withUpdatedAttributes(grvmMergedEditStateAttributes(
            previous: previous.attributes,
            incoming: incoming.attributes,
            markHistory: markHistory
        ))
        .withUpdatedMedia(updatedMedia)
}

func grvmApplyEditedMessage(
    accountPeerId: PeerId,
    transaction: Transaction,
    id: MessageId,
    message: StoreMessage
) {
    let shouldMarkHistory = grvmPreserveEditRevisionIfNeeded(
        accountPeerId: accountPeerId,
        transaction: transaction,
        id: id,
        incoming: message
    )
    transaction.updateMessage(id, update: { previous in
        return .update(grvmMergedEditedMessage(
            previous: previous,
            incoming: message,
            markHistory: shouldMarkHistory
        ))
    })
}
