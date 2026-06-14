import Foundation
import Postbox

public final class AyuGramHooks {
    // MARK: - Spy Mode
    public static var onMessagesDeleted: (([Message]) -> Void)?
    public static var onMessageEdited: ((Message, Message) -> Void)?
    public static var shouldSaveDeletedMessages: (() -> Bool)?
    public static var shouldSaveEditHistory: (() -> Bool)?
    public static var shouldPreserveOneTimeMedia: (() -> Bool)?

    // MARK: - Ghost Mode
    public static var shouldSuppressReadReceipts: (() -> Bool)?
    public static var shouldSuppressPresence: (() -> Bool)?
    public static var shouldSuppressTyping: (() -> Bool)?
    public static var shouldSuppressStoryRead: (() -> Bool)?
    public static var shouldSuppressContentRead: (() -> Bool)?

    // MARK: - Premium & Ads
    public static var isLocalPremiumEnabled: (() -> Bool)?
    public static var shouldDisableAds: (() -> Bool)?

    // MARK: - General
    public static var shouldHideStories: (() -> Bool)?
    public static var shouldDisableSimilarChannels: (() -> Bool)?
    public static var shouldDisableNotificationDelay: (() -> Bool)?
    public static var shouldShowSeconds: (() -> Bool)?
    public static var shouldShowDialogID: (() -> Bool)?
    public static var shouldSpoofWebviewAsAndroid: (() -> Bool)?
    public static var shouldIncreaseWebviewSize: (() -> Bool)?
    public static var shouldConfirmStickers: (() -> Bool)?
    public static var shouldConfirmGIF: (() -> Bool)?
    public static var shouldConfirmVoice: (() -> Bool)?

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
    public static var isMessageDeletedCheck: ((Int64, Int32) -> Bool)?
    public static var hasEditHistoryCheck: ((Int64, Int32) -> Bool)?

    // MARK: - Sending
    public static var shouldUseScheduledMessages: (() -> Bool)?
    public static var shouldSendWithoutSound: (() -> Bool)?

    // MARK: - Reanimation (W0)
    public static var shouldSuppressUploadProgress: (() -> Bool)?
    public static var shouldMarkReadAfterAction: (() -> Bool)?
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
    public static var shouldSuggestGhostForStories: (() -> Bool)?
    public static var shouldFilterZalgo: (() -> Bool)?
    public static var shouldImproveLinkPreviews: (() -> Bool)?
    public static var shouldUseSemiTransparentDeleted: (() -> Bool)?
    public static var shouldHidePremiumStatuses: (() -> Bool)?
    public static var avatarCornerRadius: (() -> Int32)?
    public static var messageBubbleRadius: (() -> Int32)?
    public static var shouldUseSingleCornerRadius: (() -> Bool)?
    public static var peerIdDisplayMode: (() -> Int32)?     // 0 Hidden / 1 TelegramApi / 2 BotApi
    public static var sendWithoutSoundMode: (() -> Int32)?  // 0 Never / 1 InGhost / 2 Always

    // MARK: - Filters / shadow-ban (заполняются в W4)
    public static var isMessageHiddenByFilter: ((Int64, String) -> Bool)?
    public static var isShadowBanned: ((Int64) -> Bool)?
}
