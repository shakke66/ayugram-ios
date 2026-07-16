import Foundation
import Postbox

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

    // MARK: - Ghost Mode
    public static var shouldSuppressReadReceipts: ((PeerId) -> Bool)?
    public static var shouldSuppressPresence: ((PeerId) -> Bool)?
    public static var shouldSuppressTyping: ((PeerId) -> Bool)?
    public static var shouldSuppressStoryRead: ((PeerId) -> Bool)?
    public static var shouldSuppressContentRead: ((PeerId) -> Bool)?
    public static var shouldForceOfflineAfterOnline: ((PeerId) -> Bool)?

    // MARK: - Premium & Ads
    public static var isLocalPremiumEnabled: ((PeerId) -> Bool)?
    public static var shouldDisableAds: ((PeerId) -> Bool)?

    // MARK: - General
    public static var shouldHideStories: ((PeerId) -> Bool)?
    public static var shouldDisableSimilarChannels: ((PeerId) -> Bool)?
    public static var shouldDisableNotificationDelay: ((PeerId) -> Bool)?
    public static var shouldShowSeconds: ((PeerId) -> Bool)?
    public static var shouldShowDialogID: ((PeerId) -> Bool)?
    public static var shouldSpoofWebviewAsAndroid: ((PeerId) -> Bool)?
    public static var shouldIncreaseWebviewHeight: ((PeerId) -> Bool)?
    public static var shouldIncreaseWebviewWidth: ((PeerId) -> Bool)?
    public static var shouldDisableExternalLinkWarning: ((PeerId) -> Bool)?
    public static var shouldConfirmStickers: ((PeerId) -> Bool)?
    public static var shouldConfirmGIF: ((PeerId) -> Bool)?
    public static var shouldConfirmVoice: ((PeerId) -> Bool)?
    public static var translationProvider: ((PeerId) -> GRVMTranslationProvider)?

    // MARK: - Appearance
    public static var shouldHideNotificationBadge: (() -> Bool)?
    public static var shouldHideNotificationCounters: (() -> Bool)?
    public static var shouldRemoveBubbleTail: (() -> Bool)?
    public static var shouldHideFolderCounters: (() -> Bool)?
    public static var shouldHideAllChatsFolder: (() -> Bool)?

    // MARK: - Chats
    public static var shouldShowOnlyAddedStickers: (() -> Bool)?
    public static var shouldHideFastShareButton: (() -> Bool)?
    public static var shouldDisableColoredReplies: (() -> Bool)?
    public static var shouldShowAttachButton: (() -> Bool)?
    public static var shouldShowCommandsButton: (() -> Bool)?
    public static var shouldShowTTLButton: (() -> Bool)?
    public static var shouldShowEmojiButton: (() -> Bool)?
    public static var shouldShowVoiceButton: (() -> Bool)?

    // MARK: - Message Width
    public static var messageWidthMultiplier: (() -> Double)?

    // MARK: - Message Marks
    public static var shouldShowDeletedMark: (() -> Bool)?
    public static var shouldShowEditedMark: (() -> Bool)?
    public static var deletedMessageMark: (() -> String)?
    public static var editedMessageMark: (() -> String)?

    // MARK: - Sending
    public static var shouldUseScheduledMessages: ((PeerId) -> Bool)?
    public static var shouldSendWithoutSound: (() -> Bool)?

    // MARK: - Reanimation (W0)
    public static var shouldSuppressUploadProgress: ((PeerId) -> Bool)?
    public static var shouldMarkReadAfterAction: ((PeerId) -> Bool)?
    public static var shouldSaveForBots: (() -> Bool)?
    public static var shouldUseMD3Switches: (() -> Bool)?
    public static var shouldDisableCustomBackgrounds: (() -> Bool)?
    public static var codeFontName: (() -> String)?
    public static var shouldUseQuickAdminShortcuts: (() -> Bool)?
    public static var shouldShowMessageShot: (() -> Bool)?
    public static var shouldReplaceMarksWithIcons: (() -> Bool)?
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
    public static var shouldShowGiftButton: (() -> Bool)?
    public static var shouldShowAiEditorButton: (() -> Bool)?
    public static var shouldSuggestGhostForStories: ((PeerId) -> Bool)?
    public static var shouldFilterZalgo: ((PeerId) -> Bool)?
    public static var shouldImproveLinkPreviews: ((PeerId) -> Bool)?
    public static var shouldUseSemiTransparentDeleted: (() -> Bool)?
    public static var shouldHidePremiumStatuses: (() -> Bool)?
    public static var avatarCornerRadius: (() -> Int32)?
    public static var messageBubbleRadius: (() -> Int32)?
    public static var shouldUseSingleCornerRadius: (() -> Bool)?
    public static var peerIdDisplayMode: ((PeerId) -> Int32)?     // 0 Hidden / 1 TelegramApi / 2 BotApi
    public static var sendWithoutSoundMode: ((PeerId) -> Int32)?  // 0 Never / 1 InGhost / 2 Always

    // MARK: - Filters / shadow-ban (заполняются в W4)
    public static var isMessageHiddenByFilter: ((PeerId, Message) -> Bool)?
    public static var isShadowBanned: ((PeerId, PeerId) -> Bool)?
    public static var matchingMessageFilterIds: ((PeerId, Message) -> [String])?
    public static var isShowingFilteredMessages: ((PeerId, PeerId) -> Bool)?
    public static var setShowingFilteredMessages: ((PeerId, PeerId, Bool) -> Void)?
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
