import Foundation
import Postbox

public enum GRVMContextMenuVisibility: Int32 {
    case hidden = 0
    case visible = 1
    case visibleWithModifier = 2
}

public enum GRVMChannelBottomButtonMode: Int32 {
    case hidden = 0
    case discuss = 1

    public init(normalizingRawValue value: Int32) {
        self = value == 0 ? .hidden : .discuss
    }
}

public struct GRVMAppearanceSettings: Equatable {
    public let selectedAppIcon: String
    public let hideNotificationBadge: Bool
    public let hideNotificationCounters: Bool
    public let removeMessageBubbleTail: Bool
    public let disableCustomBackgrounds: Bool
    public let codeFontName: String
    public let hideFolderCounters: Bool
    public let hideAllChatsFolder: Bool
    public let hidePremiumStatuses: Bool
    public let avatarCorners: Int32

    public init(
        selectedAppIcon: String,
        hideNotificationBadge: Bool,
        hideNotificationCounters: Bool,
        removeMessageBubbleTail: Bool,
        disableCustomBackgrounds: Bool,
        codeFontName: String,
        hideFolderCounters: Bool,
        hideAllChatsFolder: Bool,
        hidePremiumStatuses: Bool,
        avatarCorners: Int32
    ) {
        self.selectedAppIcon = selectedAppIcon
        self.hideNotificationBadge = hideNotificationBadge
        self.hideNotificationCounters = hideNotificationCounters
        self.removeMessageBubbleTail = removeMessageBubbleTail
        self.disableCustomBackgrounds = disableCustomBackgrounds
        self.codeFontName = codeFontName
        self.hideFolderCounters = hideFolderCounters
        self.hideAllChatsFolder = hideAllChatsFolder
        self.hidePremiumStatuses = hidePremiumStatuses
        self.avatarCorners = avatarCorners
    }
}

public struct GRVMChatSettings: Equatable {
    public let showOnlyAddedStickers: Bool
    public let showChannelReactions: Bool
    public let showGroupReactions: Bool
    public let showPrivateReactions: Bool
    public let recentStickersCount: Int32
    public let channelBottomButton: GRVMChannelBottomButtonMode
    public let quickAdminShortcuts: Bool
    public let showDeletedMark: Bool
    public let showEditedMark: Bool
    public let deletedMessageMark: String
    public let editedMessageMark: String
    public let replaceMarksWithIcons: Bool
    public let hideFastShareButton: Bool
    public let disableColoredReplies: Bool
    public let semiTransparentDeletedMessages: Bool
    public let messageWidthMultiplier: Double

    public init(
        showOnlyAddedStickers: Bool,
        showChannelReactions: Bool,
        showGroupReactions: Bool,
        showPrivateReactions: Bool,
        recentStickersCount: Int32,
        channelBottomButton: GRVMChannelBottomButtonMode,
        quickAdminShortcuts: Bool,
        showDeletedMark: Bool,
        showEditedMark: Bool,
        deletedMessageMark: String,
        editedMessageMark: String,
        replaceMarksWithIcons: Bool,
        hideFastShareButton: Bool,
        disableColoredReplies: Bool,
        semiTransparentDeletedMessages: Bool,
        messageWidthMultiplier: Double
    ) {
        self.showOnlyAddedStickers = showOnlyAddedStickers
        self.showChannelReactions = showChannelReactions
        self.showGroupReactions = showGroupReactions
        self.showPrivateReactions = showPrivateReactions
        self.recentStickersCount = recentStickersCount
        self.channelBottomButton = channelBottomButton
        self.quickAdminShortcuts = quickAdminShortcuts
        self.showDeletedMark = showDeletedMark
        self.showEditedMark = showEditedMark
        self.deletedMessageMark = deletedMessageMark
        self.editedMessageMark = editedMessageMark
        self.replaceMarksWithIcons = replaceMarksWithIcons
        self.hideFastShareButton = hideFastShareButton
        self.disableColoredReplies = disableColoredReplies
        self.semiTransparentDeletedMessages = semiTransparentDeletedMessages
        self.messageWidthMultiplier = messageWidthMultiplier
    }
}

public struct GRVMContextMenuSettings: Equatable {
    public let reactions: GRVMContextMenuVisibility
    public let views: GRVMContextMenuVisibility
    public let hide: GRVMContextMenuVisibility
    public let userMessages: GRVMContextMenuVisibility
    public let details: GRVMContextMenuVisibility
    public let repeatMessage: GRVMContextMenuVisibility
    public let addFilter: GRVMContextMenuVisibility

    public init(
        reactions: GRVMContextMenuVisibility,
        views: GRVMContextMenuVisibility,
        hide: GRVMContextMenuVisibility,
        userMessages: GRVMContextMenuVisibility,
        details: GRVMContextMenuVisibility,
        repeatMessage: GRVMContextMenuVisibility,
        addFilter: GRVMContextMenuVisibility
    ) {
        self.reactions = reactions
        self.views = views
        self.hide = hide
        self.userMessages = userMessages
        self.details = details
        self.repeatMessage = repeatMessage
        self.addFilter = addFilter
    }
}

public struct GRVMComposeSettings: Equatable {
    public let showAttachButton: Bool
    public let showTTLButton: Bool
    public let showEmojiButton: Bool
    public let showVoiceButton: Bool
    public let showGiftButton: Bool
    public let showAiEditorButton: Bool

    public init(
        showAttachButton: Bool,
        showTTLButton: Bool,
        showEmojiButton: Bool,
        showVoiceButton: Bool,
        showGiftButton: Bool,
        showAiEditorButton: Bool
    ) {
        self.showAttachButton = showAttachButton
        self.showTTLButton = showTTLButton
        self.showEmojiButton = showEmojiButton
        self.showVoiceButton = showVoiceButton
        self.showGiftButton = showGiftButton
        self.showAiEditorButton = showAiEditorButton
    }
}

public struct GRVMChatAppearanceSettings: Equatable {
    public let appearance: GRVMAppearanceSettings
    public let chats: GRVMChatSettings
    public let contextMenu: GRVMContextMenuSettings
    public let compose: GRVMComposeSettings

    public init(
        appearance: GRVMAppearanceSettings,
        chats: GRVMChatSettings,
        contextMenu: GRVMContextMenuSettings,
        compose: GRVMComposeSettings
    ) {
        self.appearance = appearance
        self.chats = chats
        self.contextMenu = contextMenu
        self.compose = compose
    }

    public static let `default` = GRVMChatAppearanceSettings(
        appearance: GRVMAppearanceSettings(
            selectedAppIcon: "default",
            hideNotificationBadge: false,
            hideNotificationCounters: false,
            removeMessageBubbleTail: false,
            disableCustomBackgrounds: false,
            codeFontName: "",
            hideFolderCounters: false,
            hideAllChatsFolder: false,
            hidePremiumStatuses: false,
            avatarCorners: 50
        ),
        chats: GRVMChatSettings(
            showOnlyAddedStickers: false,
            showChannelReactions: true,
            showGroupReactions: true,
            showPrivateReactions: true,
            recentStickersCount: 100,
            channelBottomButton: .discuss,
            quickAdminShortcuts: true,
            showDeletedMark: true,
            showEditedMark: true,
            deletedMessageMark: "\u{1F9F9}",
            editedMessageMark: "",
            replaceMarksWithIcons: false,
            hideFastShareButton: false,
            disableColoredReplies: false,
            semiTransparentDeletedMessages: false,
            messageWidthMultiplier: 1.0
        ),
        contextMenu: GRVMContextMenuSettings(
            reactions: .hidden,
            views: .hidden,
            hide: .visible,
            userMessages: .visible,
            details: .visible,
            repeatMessage: .visible,
            addFilter: .visible
        ),
        compose: GRVMComposeSettings(
            showAttachButton: true,
            showTTLButton: true,
            showEmojiButton: true,
            showVoiceButton: true,
            showGiftButton: true,
            showAiEditorButton: true
        )
    )
}
