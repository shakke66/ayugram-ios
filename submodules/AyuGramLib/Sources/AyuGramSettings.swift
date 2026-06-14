import Foundation
import TelegramCore
import SwiftSignalKit

public struct AyuGramSettings: Codable, Equatable {
    // MARK: - Ghost Mode
    public var ghostModeEnabled: Bool
    public var suppressReadReceipts: Bool
    public var suppressStoryReads: Bool
    public var suppressOnlineStatus: Bool
    public var suppressTypingStatus: Bool
    public var suppressUploadProgress: Bool
    public var readOnAction: Bool
    public var useScheduledMessages: Bool
    public var sendWithoutSound: Bool

    // MARK: - Message Saving (Spy Mode)
    public var saveDeletedMessages: Bool
    public var saveEditHistory: Bool
    public var saveForBots: Bool

    // MARK: - Premium / Ads
    public var localTelegramPremium: Bool
    public var disableAds: Bool

    // MARK: - Filters
    public var enableFilters: Bool
    public var enableFiltersInChats: Bool
    public var hideFromBlockedUsers: Bool

    // MARK: - General
    public var translationProvider: Int32
    public var hideStories: Bool
    public var disableSimilarChannels: Bool
    public var disableNotificationDelay: Bool
    public var showSecondsInMessages: Bool
    public var showDialogId: Int32
    public var spoofWebviewAsAndroid: Bool
    public var increaseWebviewSize: Bool
    public var confirmSendSticker: Bool
    public var confirmSendGIF: Bool
    public var confirmSendVoice: Bool

    // MARK: - Appearance
    public var selectedAppIcon: String
    public var hideNotificationBadge: Bool
    public var hideNotificationCounters: Bool
    public var md3StyleSwitches: Bool
    public var removeMessageBubbleTail: Bool
    public var disableCustomBackgrounds: Bool
    public var codeFontName: String
    public var hideFolderCounters: Bool
    public var hideAllChatsFolder: Bool
    public var showGhostToggleInDrawer: Bool
    public var showStreamerToggleInDrawer: Bool

    // MARK: - Chats
    public var showOnlyAddedStickers: Bool
    public var hideReactions: Int32
    public var recentStickersCount: Int32
    public var channelBottomButton: Int32
    public var quickAdminShortcuts: Bool
    public var messageShotFeature: Bool
    public var showDeletedMark: Bool
    public var showEditedMark: Bool
    public var deletedMessageMark: String
    public var editedMessageMark: String
    public var replaceMarksWithIcons: Bool
    public var hideFastShareButton: Bool
    public var disableColoredReplies: Bool
    public var messageWidthMultiplier: Double

    // MARK: - Context Menu
    public var showReactionsPanelInContextMenu: Int32
    public var showViewsPanelInContextMenu: Int32
    public var showHideMessageInContextMenu: Int32
    public var showUserMessagesInContextMenu: Int32
    public var showMessageDetailsInContextMenu: Int32
    public var showRepeatMessageInContextMenu: Int32

    // MARK: - Message Field
    public var showAttachButton: Bool
    public var showCommandsButton: Bool
    public var showTTLButton: Bool
    public var showEmojiButton: Bool
    public var showVoiceButton: Bool

    // MARK: - Drawer / Sidebar
    public var showMyProfileInDrawer: Bool
    public var showBotsInDrawer: Bool
    public var showCreateGroupInDrawer: Bool
    public var showCreateChannelInDrawer: Bool
    public var showContactsInDrawer: Bool
    public var showCallsInDrawer: Bool
    public var showSavedInDrawer: Bool
    public var showLocalReadInDrawer: Bool
    public var showServerReadInDrawer: Bool
    public var showNightModeInDrawer: Bool

    // MARK: - Other
    public var crashReportingEnabled: Bool
    public var associateLinks: Bool

    // MARK: - Reactions / Message field (6.7.8)
    public var showChannelReactions: Bool
    public var showGroupReactions: Bool
    public var showGiftButton: Bool
    public var showAiEditorButton: Bool

    // MARK: - Ghost / Stories (6.7.8)
    public var suggestGhostForStories: Bool

    // MARK: - General (6.7.8)
    public var filterZalgo: Bool
    public var improveLinkPreviews: Bool

    // MARK: - Appearance (6.7.8)
    public var semiTransparentDeletedMessages: Bool
    public var hidePremiumStatuses: Bool
    public var avatarCorners: Int32
    public var singleCornerRadius: Bool
    public var messageBubbleRadius: Int32

    // MARK: - Sending option (6.7.8)
    public var sendWithoutSoundOption: Int32

    // MARK: - Filters (6.7.8)
    public var shadowBanIds: [Int64]
    public var messageFilters: [String]

    // MARK: - Computed
    public var ghostModeActiveCount: Int {
        var count = 0
        if suppressReadReceipts { count += 1 }
        if suppressStoryReads { count += 1 }
        if suppressOnlineStatus { count += 1 }
        if suppressTypingStatus { count += 1 }
        if suppressUploadProgress { count += 1 }
        return count
    }

    public static var defaultSettings: AyuGramSettings {
        return AyuGramSettings(
            ghostModeEnabled: false,
            suppressReadReceipts: false,
            suppressStoryReads: false,
            suppressOnlineStatus: false,
            suppressTypingStatus: false,
            suppressUploadProgress: false,
            readOnAction: false,
            useScheduledMessages: false,
            sendWithoutSound: false,
            saveDeletedMessages: true,
            saveEditHistory: true,
            saveForBots: false,
            localTelegramPremium: false,
            disableAds: true,
            enableFilters: false,
            enableFiltersInChats: false,
            hideFromBlockedUsers: false,
            translationProvider: 0,
            hideStories: false,
            disableSimilarChannels: true,
            disableNotificationDelay: true,
            showSecondsInMessages: false,
            showDialogId: 0,
            spoofWebviewAsAndroid: false,
            increaseWebviewSize: true,
            confirmSendSticker: false,
            confirmSendGIF: false,
            confirmSendVoice: false,
            selectedAppIcon: "default",
            hideNotificationBadge: false,
            hideNotificationCounters: false,
            md3StyleSwitches: false,
            removeMessageBubbleTail: false,
            disableCustomBackgrounds: false,
            codeFontName: "",
            hideFolderCounters: false,
            hideAllChatsFolder: false,
            showGhostToggleInDrawer: true,
            showStreamerToggleInDrawer: false,
            showOnlyAddedStickers: false,
            hideReactions: 0,
            recentStickersCount: 20,
            channelBottomButton: 1,
            quickAdminShortcuts: true,
            messageShotFeature: true,
            showDeletedMark: true,
            showEditedMark: true,
            deletedMessageMark: "\u{1F480}",
            editedMessageMark: "edited",
            replaceMarksWithIcons: false,
            hideFastShareButton: false,
            disableColoredReplies: false,
            messageWidthMultiplier: 1.0,
            showReactionsPanelInContextMenu: 0,
            showViewsPanelInContextMenu: 0,
            showHideMessageInContextMenu: 1,
            showUserMessagesInContextMenu: 1,
            showMessageDetailsInContextMenu: 1,
            showRepeatMessageInContextMenu: 1,
            showAttachButton: true,
            showCommandsButton: true,
            showTTLButton: true,
            showEmojiButton: true,
            showVoiceButton: true,
            showMyProfileInDrawer: false,
            showBotsInDrawer: false,
            showCreateGroupInDrawer: true,
            showCreateChannelInDrawer: true,
            showContactsInDrawer: true,
            showCallsInDrawer: true,
            showSavedInDrawer: true,
            showLocalReadInDrawer: false,
            showServerReadInDrawer: false,
            showNightModeInDrawer: true,
            crashReportingEnabled: true,
            associateLinks: false,
            showChannelReactions: true,
            showGroupReactions: true,
            showGiftButton: true,
            showAiEditorButton: true,
            suggestGhostForStories: true,
            filterZalgo: false,
            improveLinkPreviews: false,
            semiTransparentDeletedMessages: false,
            hidePremiumStatuses: false,
            avatarCorners: 23,
            singleCornerRadius: false,
            messageBubbleRadius: 16,
            sendWithoutSoundOption: 0,
            shadowBanIds: [],
            messageFilters: []
        )
    }

    public init(
        ghostModeEnabled: Bool,
        suppressReadReceipts: Bool,
        suppressStoryReads: Bool,
        suppressOnlineStatus: Bool,
        suppressTypingStatus: Bool,
        suppressUploadProgress: Bool,
        readOnAction: Bool,
        useScheduledMessages: Bool,
        sendWithoutSound: Bool,
        saveDeletedMessages: Bool,
        saveEditHistory: Bool,
        saveForBots: Bool,
        localTelegramPremium: Bool,
        disableAds: Bool,
        enableFilters: Bool,
        enableFiltersInChats: Bool,
        hideFromBlockedUsers: Bool,
        translationProvider: Int32,
        hideStories: Bool,
        disableSimilarChannels: Bool,
        disableNotificationDelay: Bool,
        showSecondsInMessages: Bool,
        showDialogId: Int32,
        spoofWebviewAsAndroid: Bool,
        increaseWebviewSize: Bool,
        confirmSendSticker: Bool,
        confirmSendGIF: Bool,
        confirmSendVoice: Bool,
        selectedAppIcon: String,
        hideNotificationBadge: Bool,
        hideNotificationCounters: Bool,
        md3StyleSwitches: Bool,
        removeMessageBubbleTail: Bool,
        disableCustomBackgrounds: Bool,
        codeFontName: String,
        hideFolderCounters: Bool,
        hideAllChatsFolder: Bool,
        showGhostToggleInDrawer: Bool,
        showStreamerToggleInDrawer: Bool,
        showOnlyAddedStickers: Bool,
        hideReactions: Int32,
        recentStickersCount: Int32,
        channelBottomButton: Int32,
        quickAdminShortcuts: Bool,
        messageShotFeature: Bool,
        showDeletedMark: Bool,
        showEditedMark: Bool,
        deletedMessageMark: String,
        editedMessageMark: String,
        replaceMarksWithIcons: Bool,
        hideFastShareButton: Bool,
        disableColoredReplies: Bool,
        messageWidthMultiplier: Double,
        showReactionsPanelInContextMenu: Int32,
        showViewsPanelInContextMenu: Int32,
        showHideMessageInContextMenu: Int32,
        showUserMessagesInContextMenu: Int32,
        showMessageDetailsInContextMenu: Int32,
        showRepeatMessageInContextMenu: Int32,
        showAttachButton: Bool,
        showCommandsButton: Bool,
        showTTLButton: Bool,
        showEmojiButton: Bool,
        showVoiceButton: Bool,
        showMyProfileInDrawer: Bool,
        showBotsInDrawer: Bool,
        showCreateGroupInDrawer: Bool,
        showCreateChannelInDrawer: Bool,
        showContactsInDrawer: Bool,
        showCallsInDrawer: Bool,
        showSavedInDrawer: Bool,
        showLocalReadInDrawer: Bool,
        showServerReadInDrawer: Bool,
        showNightModeInDrawer: Bool,
        crashReportingEnabled: Bool,
        associateLinks: Bool,
        showChannelReactions: Bool,
        showGroupReactions: Bool,
        showGiftButton: Bool,
        showAiEditorButton: Bool,
        suggestGhostForStories: Bool,
        filterZalgo: Bool,
        improveLinkPreviews: Bool,
        semiTransparentDeletedMessages: Bool,
        hidePremiumStatuses: Bool,
        avatarCorners: Int32,
        singleCornerRadius: Bool,
        messageBubbleRadius: Int32,
        sendWithoutSoundOption: Int32,
        shadowBanIds: [Int64],
        messageFilters: [String]
    ) {
        self.ghostModeEnabled = ghostModeEnabled
        self.suppressReadReceipts = suppressReadReceipts
        self.suppressStoryReads = suppressStoryReads
        self.suppressOnlineStatus = suppressOnlineStatus
        self.suppressTypingStatus = suppressTypingStatus
        self.suppressUploadProgress = suppressUploadProgress
        self.readOnAction = readOnAction
        self.useScheduledMessages = useScheduledMessages
        self.sendWithoutSound = sendWithoutSound
        self.saveDeletedMessages = saveDeletedMessages
        self.saveEditHistory = saveEditHistory
        self.saveForBots = saveForBots
        self.localTelegramPremium = localTelegramPremium
        self.disableAds = disableAds
        self.enableFilters = enableFilters
        self.enableFiltersInChats = enableFiltersInChats
        self.hideFromBlockedUsers = hideFromBlockedUsers
        self.translationProvider = translationProvider
        self.hideStories = hideStories
        self.disableSimilarChannels = disableSimilarChannels
        self.disableNotificationDelay = disableNotificationDelay
        self.showSecondsInMessages = showSecondsInMessages
        self.showDialogId = showDialogId
        self.spoofWebviewAsAndroid = spoofWebviewAsAndroid
        self.increaseWebviewSize = increaseWebviewSize
        self.confirmSendSticker = confirmSendSticker
        self.confirmSendGIF = confirmSendGIF
        self.confirmSendVoice = confirmSendVoice
        self.selectedAppIcon = selectedAppIcon
        self.hideNotificationBadge = hideNotificationBadge
        self.hideNotificationCounters = hideNotificationCounters
        self.md3StyleSwitches = md3StyleSwitches
        self.removeMessageBubbleTail = removeMessageBubbleTail
        self.disableCustomBackgrounds = disableCustomBackgrounds
        self.codeFontName = codeFontName
        self.hideFolderCounters = hideFolderCounters
        self.hideAllChatsFolder = hideAllChatsFolder
        self.showGhostToggleInDrawer = showGhostToggleInDrawer
        self.showStreamerToggleInDrawer = showStreamerToggleInDrawer
        self.showOnlyAddedStickers = showOnlyAddedStickers
        self.hideReactions = hideReactions
        self.recentStickersCount = recentStickersCount
        self.channelBottomButton = channelBottomButton
        self.quickAdminShortcuts = quickAdminShortcuts
        self.messageShotFeature = messageShotFeature
        self.showDeletedMark = showDeletedMark
        self.showEditedMark = showEditedMark
        self.deletedMessageMark = deletedMessageMark
        self.editedMessageMark = editedMessageMark
        self.replaceMarksWithIcons = replaceMarksWithIcons
        self.hideFastShareButton = hideFastShareButton
        self.disableColoredReplies = disableColoredReplies
        self.messageWidthMultiplier = messageWidthMultiplier
        self.showReactionsPanelInContextMenu = showReactionsPanelInContextMenu
        self.showViewsPanelInContextMenu = showViewsPanelInContextMenu
        self.showHideMessageInContextMenu = showHideMessageInContextMenu
        self.showUserMessagesInContextMenu = showUserMessagesInContextMenu
        self.showMessageDetailsInContextMenu = showMessageDetailsInContextMenu
        self.showRepeatMessageInContextMenu = showRepeatMessageInContextMenu
        self.showAttachButton = showAttachButton
        self.showCommandsButton = showCommandsButton
        self.showTTLButton = showTTLButton
        self.showEmojiButton = showEmojiButton
        self.showVoiceButton = showVoiceButton
        self.showMyProfileInDrawer = showMyProfileInDrawer
        self.showBotsInDrawer = showBotsInDrawer
        self.showCreateGroupInDrawer = showCreateGroupInDrawer
        self.showCreateChannelInDrawer = showCreateChannelInDrawer
        self.showContactsInDrawer = showContactsInDrawer
        self.showCallsInDrawer = showCallsInDrawer
        self.showSavedInDrawer = showSavedInDrawer
        self.showLocalReadInDrawer = showLocalReadInDrawer
        self.showServerReadInDrawer = showServerReadInDrawer
        self.showNightModeInDrawer = showNightModeInDrawer
        self.crashReportingEnabled = crashReportingEnabled
        self.associateLinks = associateLinks
        self.showChannelReactions = showChannelReactions
        self.showGroupReactions = showGroupReactions
        self.showGiftButton = showGiftButton
        self.showAiEditorButton = showAiEditorButton
        self.suggestGhostForStories = suggestGhostForStories
        self.filterZalgo = filterZalgo
        self.improveLinkPreviews = improveLinkPreviews
        self.semiTransparentDeletedMessages = semiTransparentDeletedMessages
        self.hidePremiumStatuses = hidePremiumStatuses
        self.avatarCorners = avatarCorners
        self.singleCornerRadius = singleCornerRadius
        self.messageBubbleRadius = messageBubbleRadius
        self.sendWithoutSoundOption = sendWithoutSoundOption
        self.shadowBanIds = shadowBanIds
        self.messageFilters = messageFilters
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: StringCodingKey.self)

        self.ghostModeEnabled = try container.decodeIfPresent(Bool.self, forKey: "ghostModeEnabled") ?? false
        self.suppressReadReceipts = try container.decodeIfPresent(Bool.self, forKey: "suppressReadReceipts") ?? false
        self.suppressStoryReads = try container.decodeIfPresent(Bool.self, forKey: "suppressStoryReads") ?? false
        self.suppressOnlineStatus = try container.decodeIfPresent(Bool.self, forKey: "suppressOnlineStatus") ?? false
        self.suppressTypingStatus = try container.decodeIfPresent(Bool.self, forKey: "suppressTypingStatus") ?? false
        self.suppressUploadProgress = try container.decodeIfPresent(Bool.self, forKey: "suppressUploadProgress") ?? false
        self.readOnAction = try container.decodeIfPresent(Bool.self, forKey: "readOnAction") ?? false
        self.useScheduledMessages = try container.decodeIfPresent(Bool.self, forKey: "useScheduledMessages") ?? false
        self.sendWithoutSound = try container.decodeIfPresent(Bool.self, forKey: "sendWithoutSound") ?? false

        self.saveDeletedMessages = try container.decodeIfPresent(Bool.self, forKey: "saveDeletedMessages") ?? true
        self.saveEditHistory = try container.decodeIfPresent(Bool.self, forKey: "saveEditHistory") ?? true
        self.saveForBots = try container.decodeIfPresent(Bool.self, forKey: "saveForBots") ?? false

        self.localTelegramPremium = try container.decodeIfPresent(Bool.self, forKey: "localTelegramPremium") ?? false
        self.disableAds = try container.decodeIfPresent(Bool.self, forKey: "disableAds") ?? true

        self.enableFilters = try container.decodeIfPresent(Bool.self, forKey: "enableFilters") ?? false
        self.enableFiltersInChats = try container.decodeIfPresent(Bool.self, forKey: "enableFiltersInChats") ?? false
        self.hideFromBlockedUsers = try container.decodeIfPresent(Bool.self, forKey: "hideFromBlockedUsers") ?? false

        self.translationProvider = try container.decodeIfPresent(Int32.self, forKey: "translationProvider") ?? 0
        self.hideStories = try container.decodeIfPresent(Bool.self, forKey: "hideStories") ?? false
        self.disableSimilarChannels = try container.decodeIfPresent(Bool.self, forKey: "disableSimilarChannels") ?? true
        self.disableNotificationDelay = try container.decodeIfPresent(Bool.self, forKey: "disableNotificationDelay") ?? true
        self.showSecondsInMessages = try container.decodeIfPresent(Bool.self, forKey: "showSecondsInMessages") ?? false
        self.showDialogId = try container.decodeIfPresent(Int32.self, forKey: "showDialogId") ?? 0
        self.spoofWebviewAsAndroid = try container.decodeIfPresent(Bool.self, forKey: "spoofWebviewAsAndroid") ?? false
        self.increaseWebviewSize = try container.decodeIfPresent(Bool.self, forKey: "increaseWebviewSize") ?? true
        self.confirmSendSticker = try container.decodeIfPresent(Bool.self, forKey: "confirmSendSticker") ?? false
        self.confirmSendGIF = try container.decodeIfPresent(Bool.self, forKey: "confirmSendGIF") ?? false
        self.confirmSendVoice = try container.decodeIfPresent(Bool.self, forKey: "confirmSendVoice") ?? false

        self.selectedAppIcon = try container.decodeIfPresent(String.self, forKey: "selectedAppIcon") ?? "default"
        self.hideNotificationBadge = try container.decodeIfPresent(Bool.self, forKey: "hideNotificationBadge") ?? false
        self.hideNotificationCounters = try container.decodeIfPresent(Bool.self, forKey: "hideNotificationCounters") ?? false
        self.md3StyleSwitches = try container.decodeIfPresent(Bool.self, forKey: "md3StyleSwitches") ?? false
        self.removeMessageBubbleTail = try container.decodeIfPresent(Bool.self, forKey: "removeMessageBubbleTail") ?? false
        self.disableCustomBackgrounds = try container.decodeIfPresent(Bool.self, forKey: "disableCustomBackgrounds") ?? false
        self.codeFontName = try container.decodeIfPresent(String.self, forKey: "codeFontName") ?? ""
        self.hideFolderCounters = try container.decodeIfPresent(Bool.self, forKey: "hideFolderCounters") ?? false
        self.hideAllChatsFolder = try container.decodeIfPresent(Bool.self, forKey: "hideAllChatsFolder") ?? false
        self.showGhostToggleInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showGhostToggleInDrawer") ?? true
        self.showStreamerToggleInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showStreamerToggleInDrawer") ?? false

        self.showOnlyAddedStickers = try container.decodeIfPresent(Bool.self, forKey: "showOnlyAddedStickers") ?? false
        self.hideReactions = try container.decodeIfPresent(Int32.self, forKey: "hideReactions") ?? 0
        self.recentStickersCount = try container.decodeIfPresent(Int32.self, forKey: "recentStickersCount") ?? 20
        self.channelBottomButton = try container.decodeIfPresent(Int32.self, forKey: "channelBottomButton") ?? 1
        self.quickAdminShortcuts = try container.decodeIfPresent(Bool.self, forKey: "quickAdminShortcuts") ?? true
        self.messageShotFeature = try container.decodeIfPresent(Bool.self, forKey: "messageShotFeature") ?? true
        self.showDeletedMark = try container.decodeIfPresent(Bool.self, forKey: "showDeletedMark") ?? true
        self.showEditedMark = try container.decodeIfPresent(Bool.self, forKey: "showEditedMark") ?? true
        self.deletedMessageMark = try container.decodeIfPresent(String.self, forKey: "deletedMessageMark") ?? "\u{1F480}"
        self.editedMessageMark = try container.decodeIfPresent(String.self, forKey: "editedMessageMark") ?? "edited"
        self.replaceMarksWithIcons = try container.decodeIfPresent(Bool.self, forKey: "replaceMarksWithIcons") ?? false
        self.hideFastShareButton = try container.decodeIfPresent(Bool.self, forKey: "hideFastShareButton") ?? false
        self.disableColoredReplies = try container.decodeIfPresent(Bool.self, forKey: "disableColoredReplies") ?? false
        self.messageWidthMultiplier = try container.decodeIfPresent(Double.self, forKey: "messageWidthMultiplier") ?? 1.0

        self.showReactionsPanelInContextMenu = try container.decodeIfPresent(Int32.self, forKey: "showReactionsPanelInContextMenu") ?? 0
        self.showViewsPanelInContextMenu = try container.decodeIfPresent(Int32.self, forKey: "showViewsPanelInContextMenu") ?? 0
        self.showHideMessageInContextMenu = try container.decodeIfPresent(Int32.self, forKey: "showHideMessageInContextMenu") ?? 1
        self.showUserMessagesInContextMenu = try container.decodeIfPresent(Int32.self, forKey: "showUserMessagesInContextMenu") ?? 1
        self.showMessageDetailsInContextMenu = try container.decodeIfPresent(Int32.self, forKey: "showMessageDetailsInContextMenu") ?? 1
        self.showRepeatMessageInContextMenu = try container.decodeIfPresent(Int32.self, forKey: "showRepeatMessageInContextMenu") ?? 1

        self.showAttachButton = try container.decodeIfPresent(Bool.self, forKey: "showAttachButton") ?? true
        self.showCommandsButton = try container.decodeIfPresent(Bool.self, forKey: "showCommandsButton") ?? true
        self.showTTLButton = try container.decodeIfPresent(Bool.self, forKey: "showTTLButton") ?? true
        self.showEmojiButton = try container.decodeIfPresent(Bool.self, forKey: "showEmojiButton") ?? true
        self.showVoiceButton = try container.decodeIfPresent(Bool.self, forKey: "showVoiceButton") ?? true

        self.showMyProfileInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showMyProfileInDrawer") ?? false
        self.showBotsInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showBotsInDrawer") ?? false
        self.showCreateGroupInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showCreateGroupInDrawer") ?? true
        self.showCreateChannelInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showCreateChannelInDrawer") ?? true
        self.showContactsInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showContactsInDrawer") ?? true
        self.showCallsInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showCallsInDrawer") ?? true
        self.showSavedInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showSavedInDrawer") ?? true
        self.showLocalReadInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showLocalReadInDrawer") ?? false
        self.showServerReadInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showServerReadInDrawer") ?? false
        self.showNightModeInDrawer = try container.decodeIfPresent(Bool.self, forKey: "showNightModeInDrawer") ?? true

        self.crashReportingEnabled = try container.decodeIfPresent(Bool.self, forKey: "crashReportingEnabled") ?? true
        self.associateLinks = try container.decodeIfPresent(Bool.self, forKey: "associateLinks") ?? false

        self.showChannelReactions = try container.decodeIfPresent(Bool.self, forKey: "showChannelReactions") ?? true
        self.showGroupReactions = try container.decodeIfPresent(Bool.self, forKey: "showGroupReactions") ?? true
        self.showGiftButton = try container.decodeIfPresent(Bool.self, forKey: "showGiftButton") ?? true
        self.showAiEditorButton = try container.decodeIfPresent(Bool.self, forKey: "showAiEditorButton") ?? true
        self.suggestGhostForStories = try container.decodeIfPresent(Bool.self, forKey: "suggestGhostForStories") ?? true
        self.filterZalgo = try container.decodeIfPresent(Bool.self, forKey: "filterZalgo") ?? false
        self.improveLinkPreviews = try container.decodeIfPresent(Bool.self, forKey: "improveLinkPreviews") ?? false
        self.semiTransparentDeletedMessages = try container.decodeIfPresent(Bool.self, forKey: "semiTransparentDeletedMessages") ?? false
        self.hidePremiumStatuses = try container.decodeIfPresent(Bool.self, forKey: "hidePremiumStatuses") ?? false
        self.avatarCorners = try container.decodeIfPresent(Int32.self, forKey: "avatarCorners") ?? 23
        self.singleCornerRadius = try container.decodeIfPresent(Bool.self, forKey: "singleCornerRadius") ?? false
        self.messageBubbleRadius = try container.decodeIfPresent(Int32.self, forKey: "messageBubbleRadius") ?? 16
        self.sendWithoutSoundOption = try container.decodeIfPresent(Int32.self, forKey: "sendWithoutSoundOption") ?? 0
        self.shadowBanIds = try container.decodeIfPresent([Int64].self, forKey: "shadowBanIds") ?? []
        self.messageFilters = try container.decodeIfPresent([String].self, forKey: "messageFilters") ?? []
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: StringCodingKey.self)

        try container.encode(self.ghostModeEnabled, forKey: "ghostModeEnabled")
        try container.encode(self.suppressReadReceipts, forKey: "suppressReadReceipts")
        try container.encode(self.suppressStoryReads, forKey: "suppressStoryReads")
        try container.encode(self.suppressOnlineStatus, forKey: "suppressOnlineStatus")
        try container.encode(self.suppressTypingStatus, forKey: "suppressTypingStatus")
        try container.encode(self.suppressUploadProgress, forKey: "suppressUploadProgress")
        try container.encode(self.readOnAction, forKey: "readOnAction")
        try container.encode(self.useScheduledMessages, forKey: "useScheduledMessages")
        try container.encode(self.sendWithoutSound, forKey: "sendWithoutSound")

        try container.encode(self.saveDeletedMessages, forKey: "saveDeletedMessages")
        try container.encode(self.saveEditHistory, forKey: "saveEditHistory")
        try container.encode(self.saveForBots, forKey: "saveForBots")

        try container.encode(self.localTelegramPremium, forKey: "localTelegramPremium")
        try container.encode(self.disableAds, forKey: "disableAds")

        try container.encode(self.enableFilters, forKey: "enableFilters")
        try container.encode(self.enableFiltersInChats, forKey: "enableFiltersInChats")
        try container.encode(self.hideFromBlockedUsers, forKey: "hideFromBlockedUsers")

        try container.encode(self.translationProvider, forKey: "translationProvider")
        try container.encode(self.hideStories, forKey: "hideStories")
        try container.encode(self.disableSimilarChannels, forKey: "disableSimilarChannels")
        try container.encode(self.disableNotificationDelay, forKey: "disableNotificationDelay")
        try container.encode(self.showSecondsInMessages, forKey: "showSecondsInMessages")
        try container.encode(self.showDialogId, forKey: "showDialogId")
        try container.encode(self.spoofWebviewAsAndroid, forKey: "spoofWebviewAsAndroid")
        try container.encode(self.increaseWebviewSize, forKey: "increaseWebviewSize")
        try container.encode(self.confirmSendSticker, forKey: "confirmSendSticker")
        try container.encode(self.confirmSendGIF, forKey: "confirmSendGIF")
        try container.encode(self.confirmSendVoice, forKey: "confirmSendVoice")

        try container.encode(self.selectedAppIcon, forKey: "selectedAppIcon")
        try container.encode(self.hideNotificationBadge, forKey: "hideNotificationBadge")
        try container.encode(self.hideNotificationCounters, forKey: "hideNotificationCounters")
        try container.encode(self.md3StyleSwitches, forKey: "md3StyleSwitches")
        try container.encode(self.removeMessageBubbleTail, forKey: "removeMessageBubbleTail")
        try container.encode(self.disableCustomBackgrounds, forKey: "disableCustomBackgrounds")
        try container.encode(self.codeFontName, forKey: "codeFontName")
        try container.encode(self.hideFolderCounters, forKey: "hideFolderCounters")
        try container.encode(self.hideAllChatsFolder, forKey: "hideAllChatsFolder")
        try container.encode(self.showGhostToggleInDrawer, forKey: "showGhostToggleInDrawer")
        try container.encode(self.showStreamerToggleInDrawer, forKey: "showStreamerToggleInDrawer")

        try container.encode(self.showOnlyAddedStickers, forKey: "showOnlyAddedStickers")
        try container.encode(self.hideReactions, forKey: "hideReactions")
        try container.encode(self.recentStickersCount, forKey: "recentStickersCount")
        try container.encode(self.channelBottomButton, forKey: "channelBottomButton")
        try container.encode(self.quickAdminShortcuts, forKey: "quickAdminShortcuts")
        try container.encode(self.messageShotFeature, forKey: "messageShotFeature")
        try container.encode(self.showDeletedMark, forKey: "showDeletedMark")
        try container.encode(self.showEditedMark, forKey: "showEditedMark")
        try container.encode(self.deletedMessageMark, forKey: "deletedMessageMark")
        try container.encode(self.editedMessageMark, forKey: "editedMessageMark")
        try container.encode(self.replaceMarksWithIcons, forKey: "replaceMarksWithIcons")
        try container.encode(self.hideFastShareButton, forKey: "hideFastShareButton")
        try container.encode(self.disableColoredReplies, forKey: "disableColoredReplies")
        try container.encode(self.messageWidthMultiplier, forKey: "messageWidthMultiplier")

        try container.encode(self.showReactionsPanelInContextMenu, forKey: "showReactionsPanelInContextMenu")
        try container.encode(self.showViewsPanelInContextMenu, forKey: "showViewsPanelInContextMenu")
        try container.encode(self.showHideMessageInContextMenu, forKey: "showHideMessageInContextMenu")
        try container.encode(self.showUserMessagesInContextMenu, forKey: "showUserMessagesInContextMenu")
        try container.encode(self.showMessageDetailsInContextMenu, forKey: "showMessageDetailsInContextMenu")
        try container.encode(self.showRepeatMessageInContextMenu, forKey: "showRepeatMessageInContextMenu")

        try container.encode(self.showAttachButton, forKey: "showAttachButton")
        try container.encode(self.showCommandsButton, forKey: "showCommandsButton")
        try container.encode(self.showTTLButton, forKey: "showTTLButton")
        try container.encode(self.showEmojiButton, forKey: "showEmojiButton")
        try container.encode(self.showVoiceButton, forKey: "showVoiceButton")

        try container.encode(self.showMyProfileInDrawer, forKey: "showMyProfileInDrawer")
        try container.encode(self.showBotsInDrawer, forKey: "showBotsInDrawer")
        try container.encode(self.showCreateGroupInDrawer, forKey: "showCreateGroupInDrawer")
        try container.encode(self.showCreateChannelInDrawer, forKey: "showCreateChannelInDrawer")
        try container.encode(self.showContactsInDrawer, forKey: "showContactsInDrawer")
        try container.encode(self.showCallsInDrawer, forKey: "showCallsInDrawer")
        try container.encode(self.showSavedInDrawer, forKey: "showSavedInDrawer")
        try container.encode(self.showLocalReadInDrawer, forKey: "showLocalReadInDrawer")
        try container.encode(self.showServerReadInDrawer, forKey: "showServerReadInDrawer")
        try container.encode(self.showNightModeInDrawer, forKey: "showNightModeInDrawer")

        try container.encode(self.crashReportingEnabled, forKey: "crashReportingEnabled")
        try container.encode(self.associateLinks, forKey: "associateLinks")

        try container.encode(self.showChannelReactions, forKey: "showChannelReactions")
        try container.encode(self.showGroupReactions, forKey: "showGroupReactions")
        try container.encode(self.showGiftButton, forKey: "showGiftButton")
        try container.encode(self.showAiEditorButton, forKey: "showAiEditorButton")
        try container.encode(self.suggestGhostForStories, forKey: "suggestGhostForStories")
        try container.encode(self.filterZalgo, forKey: "filterZalgo")
        try container.encode(self.improveLinkPreviews, forKey: "improveLinkPreviews")
        try container.encode(self.semiTransparentDeletedMessages, forKey: "semiTransparentDeletedMessages")
        try container.encode(self.hidePremiumStatuses, forKey: "hidePremiumStatuses")
        try container.encode(self.avatarCorners, forKey: "avatarCorners")
        try container.encode(self.singleCornerRadius, forKey: "singleCornerRadius")
        try container.encode(self.messageBubbleRadius, forKey: "messageBubbleRadius")
        try container.encode(self.sendWithoutSoundOption, forKey: "sendWithoutSoundOption")
        try container.encode(self.shadowBanIds, forKey: "shadowBanIds")
        try container.encode(self.messageFilters, forKey: "messageFilters")
    }

    public mutating func setGhostMode(_ enabled: Bool) {
        self.ghostModeEnabled = enabled
        self.suppressReadReceipts = enabled
        self.suppressStoryReads = enabled
        self.suppressOnlineStatus = enabled
        self.suppressTypingStatus = enabled
        self.suppressUploadProgress = enabled
    }
}

public func updateAyuGramSettings(
    accountManager: AccountManager<TelegramAccountManagerTypes>,
    _ f: @escaping (AyuGramSettings) -> AyuGramSettings
) -> Signal<Void, NoError> {
    return accountManager.transaction { transaction -> Void in
        transaction.updateSharedData(ApplicationSpecificSharedDataKeys.ayuGramSettings, { entry in
            let currentSettings: AyuGramSettings
            if let entry = entry?.get(AyuGramSettings.self) {
                currentSettings = entry
            } else {
                currentSettings = .defaultSettings
            }
            return SharedPreferencesEntry(f(currentSettings))
        })
    }
}

public func ayuGramSettings(
    accountManager: AccountManager<TelegramAccountManagerTypes>
) -> Signal<AyuGramSettings, NoError> {
    return accountManager.sharedData(keys: [ApplicationSpecificSharedDataKeys.ayuGramSettings])
    |> map { sharedData in
        return sharedData.entries[ApplicationSpecificSharedDataKeys.ayuGramSettings]?.get(AyuGramSettings.self) ?? .defaultSettings
    }
}
