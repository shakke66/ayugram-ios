import Foundation
import SwiftSignalKit
import Postbox
import TelegramCore
import TelegramUIPreferences
import AccountContext
import AyuGramLib

public final class AyuGramFeatureManager {
    private var settingsDisposable: Disposable?
    private var currentSettings: AyuGramSettings = .defaultSettings
    private var compiledFilters: [NSRegularExpression] = []

    public init() {}

    private func recompileFilters() {
        guard self.currentSettings.enableFilters else {
            self.compiledFilters = []
            return
        }
        self.compiledFilters = self.currentSettings.messageFilters.compactMap { pattern in
            return try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive])
        }
    }

    public func wireHooks(accountManager: AccountManager<TelegramAccountManagerTypes>) {
        // MARK: - Spy Mode
        AyuGramHooks.onMessagesDeleted = { messages in
            AyuDeletedMessagesDB.shared.saveDeletedMessages(messages)
        }
        AyuGramHooks.onMessageEdited = { oldMessage, _ in
            AyuDeletedMessagesDB.shared.saveEditedMessage(oldMessage: oldMessage)
        }
        AyuGramHooks.shouldSaveDeletedMessages = { [weak self] in
            return self?.currentSettings.saveDeletedMessages ?? false
        }
        AyuGramHooks.shouldSaveEditHistory = { [weak self] in
            return self?.currentSettings.saveEditHistory ?? false
        }
        AyuGramHooks.shouldPreserveOneTimeMedia = { [weak self] in
            return self?.currentSettings.saveDeletedMessages ?? false
        }

        // MARK: - Ghost Mode
        AyuGramHooks.shouldSuppressReadReceipts = { [weak self] in
            guard let s = self?.currentSettings else { return false }
            return s.ghostModeEnabled && s.suppressReadReceipts
        }
        AyuGramHooks.shouldSuppressPresence = { [weak self] in
            guard let s = self?.currentSettings else { return false }
            return s.ghostModeEnabled && s.suppressOnlineStatus
        }
        AyuGramHooks.shouldSuppressTyping = { [weak self] in
            guard let s = self?.currentSettings else { return false }
            return s.ghostModeEnabled && s.suppressTypingStatus
        }
        AyuGramHooks.shouldSuppressStoryRead = { [weak self] in
            guard let s = self?.currentSettings else { return false }
            return s.ghostModeEnabled && s.suppressStoryReads
        }
        AyuGramHooks.shouldSuppressContentRead = { [weak self] in
            guard let s = self?.currentSettings else { return false }
            return s.ghostModeEnabled && s.suppressReadReceipts
        }

        // MARK: - Premium & Ads
        AyuGramHooks.isLocalPremiumEnabled = { [weak self] in
            return self?.currentSettings.localTelegramPremium ?? false
        }
        AyuGramHooks.shouldDisableAds = { [weak self] in
            return self?.currentSettings.disableAds ?? true
        }

        // MARK: - General
        AyuGramHooks.shouldHideStories = { [weak self] in
            return self?.currentSettings.hideStories ?? false
        }
        AyuGramHooks.shouldDisableSimilarChannels = { [weak self] in
            return self?.currentSettings.disableSimilarChannels ?? false
        }
        AyuGramHooks.shouldDisableNotificationDelay = { [weak self] in
            return self?.currentSettings.disableNotificationDelay ?? false
        }
        AyuGramHooks.shouldShowSeconds = { [weak self] in
            return self?.currentSettings.showSecondsInMessages ?? false
        }
        AyuGramHooks.shouldShowDialogID = { [weak self] in
            return (self?.currentSettings.showDialogId ?? 0) != 0
        }
        AyuGramHooks.shouldSpoofWebviewAsAndroid = { [weak self] in
            return self?.currentSettings.spoofWebviewAsAndroid ?? false
        }
        AyuGramHooks.shouldIncreaseWebviewSize = { [weak self] in
            return self?.currentSettings.increaseWebviewSize ?? false
        }
        AyuGramHooks.shouldConfirmStickers = { [weak self] in
            return self?.currentSettings.confirmSendSticker ?? false
        }
        AyuGramHooks.shouldConfirmGIF = { [weak self] in
            return self?.currentSettings.confirmSendGIF ?? false
        }
        AyuGramHooks.shouldConfirmVoice = { [weak self] in
            return self?.currentSettings.confirmSendVoice ?? false
        }

        // MARK: - Appearance
        AyuGramHooks.shouldHideNotificationBadge = { [weak self] in
            return self?.currentSettings.hideNotificationBadge ?? false
        }
        AyuGramHooks.shouldHideNotificationCounters = { [weak self] in
            return self?.currentSettings.hideNotificationCounters ?? false
        }
        AyuGramHooks.shouldRemoveBubbleTail = { [weak self] in
            return self?.currentSettings.removeMessageBubbleTail ?? false
        }
        AyuGramHooks.shouldHideFolderCounters = { [weak self] in
            return self?.currentSettings.hideFolderCounters ?? false
        }
        AyuGramHooks.shouldHideAllChatsFolder = { [weak self] in
            return self?.currentSettings.hideAllChatsFolder ?? false
        }

        // MARK: - Chats
        AyuGramHooks.shouldShowOnlyAddedStickers = { [weak self] in
            return self?.currentSettings.showOnlyAddedStickers ?? false
        }
        AyuGramHooks.shouldHideFastShareButton = { [weak self] in
            return self?.currentSettings.hideFastShareButton ?? false
        }
        AyuGramHooks.shouldDisableColoredReplies = { [weak self] in
            return self?.currentSettings.disableColoredReplies ?? false
        }
        AyuGramHooks.shouldShowAttachButton = { [weak self] in
            return self?.currentSettings.showAttachButton ?? true
        }
        AyuGramHooks.shouldShowCommandsButton = { [weak self] in
            return self?.currentSettings.showCommandsButton ?? true
        }
        AyuGramHooks.shouldShowTTLButton = { [weak self] in
            return self?.currentSettings.showTTLButton ?? true
        }
        AyuGramHooks.shouldShowEmojiButton = { [weak self] in
            return self?.currentSettings.showEmojiButton ?? true
        }
        AyuGramHooks.shouldShowVoiceButton = { [weak self] in
            return self?.currentSettings.showVoiceButton ?? true
        }

        // MARK: - Message Width
        AyuGramHooks.messageWidthMultiplier = { [weak self] in
            return self?.currentSettings.messageWidthMultiplier ?? 1.0
        }

        // MARK: - Message Marks
        AyuGramHooks.shouldShowDeletedMark = { [weak self] in
            return self?.currentSettings.showDeletedMark ?? true
        }
        AyuGramHooks.shouldShowEditedMark = { [weak self] in
            return self?.currentSettings.showEditedMark ?? true
        }
        AyuGramHooks.deletedMessageMark = { [weak self] in
            return self?.currentSettings.deletedMessageMark ?? "🗑"
        }
        AyuGramHooks.editedMessageMark = { [weak self] in
            return self?.currentSettings.editedMessageMark ?? "✏️"
        }
        AyuGramHooks.isMessageDeletedCheck = { peerId, messageId in
            return AyuDeletedMessagesDB.shared.isMessageDeleted(peerId: peerId, messageId: messageId)
        }
        AyuGramHooks.hasEditHistoryCheck = { peerId, messageId in
            return AyuDeletedMessagesDB.shared.hasEditHistory(peerId: peerId, messageId: messageId)
        }

        // MARK: - Sending
        AyuGramHooks.shouldUseScheduledMessages = { [weak self] in
            return self?.currentSettings.useScheduledMessages ?? false
        }
        AyuGramHooks.shouldSendWithoutSound = { [weak self] in
            return self?.currentSettings.sendWithoutSound ?? false
        }

        // MARK: - W0 Reanimation & 6.7.8
        AyuGramHooks.shouldSuppressUploadProgress = { [weak self] in
            guard let s = self?.currentSettings else { return false }
            return s.ghostModeEnabled && s.suppressUploadProgress
        }
        AyuGramHooks.shouldMarkReadAfterAction = { [weak self] in self?.currentSettings.readOnAction ?? false }
        AyuGramHooks.shouldSaveForBots = { [weak self] in self?.currentSettings.saveForBots ?? false }
        AyuGramHooks.shouldUseMD3Switches = { [weak self] in self?.currentSettings.md3StyleSwitches ?? false }
        AyuGramHooks.shouldDisableCustomBackgrounds = { [weak self] in self?.currentSettings.disableCustomBackgrounds ?? false }
        AyuGramHooks.codeFontName = { [weak self] in self?.currentSettings.codeFontName ?? "" }
        AyuGramHooks.shouldUseQuickAdminShortcuts = { [weak self] in self?.currentSettings.quickAdminShortcuts ?? false }
        AyuGramHooks.shouldShowMessageShot = { [weak self] in self?.currentSettings.messageShotFeature ?? false }
        AyuGramHooks.shouldReplaceMarksWithIcons = { [weak self] in self?.currentSettings.replaceMarksWithIcons ?? false }
        AyuGramHooks.shouldShowChannelReactions = { [weak self] in self?.currentSettings.showChannelReactions ?? true }
        AyuGramHooks.shouldShowGroupReactions = { [weak self] in self?.currentSettings.showGroupReactions ?? true }
        AyuGramHooks.recentStickersLimit = { [weak self] in self?.currentSettings.recentStickersCount ?? 20 }
        AyuGramHooks.channelBottomButtonMode = { [weak self] in self?.currentSettings.channelBottomButton ?? 1 }

        AyuGramHooks.contextMenuReactionsPanel = { [weak self] in self?.currentSettings.showReactionsPanelInContextMenu ?? 0 }
        AyuGramHooks.contextMenuViewsPanel = { [weak self] in self?.currentSettings.showViewsPanelInContextMenu ?? 0 }
        AyuGramHooks.contextMenuHide = { [weak self] in self?.currentSettings.showHideMessageInContextMenu ?? 1 }
        AyuGramHooks.contextMenuUserMessages = { [weak self] in self?.currentSettings.showUserMessagesInContextMenu ?? 1 }
        AyuGramHooks.contextMenuDetails = { [weak self] in self?.currentSettings.showMessageDetailsInContextMenu ?? 1 }
        AyuGramHooks.contextMenuRepeat = { [weak self] in self?.currentSettings.showRepeatMessageInContextMenu ?? 1 }

        AyuGramHooks.shouldShowGiftButton = { [weak self] in self?.currentSettings.showGiftButton ?? true }
        AyuGramHooks.shouldShowAiEditorButton = { [weak self] in self?.currentSettings.showAiEditorButton ?? true }
        AyuGramHooks.shouldSuggestGhostForStories = { [weak self] in self?.currentSettings.suggestGhostForStories ?? true }
        AyuGramHooks.shouldFilterZalgo = { [weak self] in self?.currentSettings.filterZalgo ?? false }
        AyuGramHooks.shouldImproveLinkPreviews = { [weak self] in self?.currentSettings.improveLinkPreviews ?? false }
        AyuGramHooks.shouldUseSemiTransparentDeleted = { [weak self] in self?.currentSettings.semiTransparentDeletedMessages ?? false }
        AyuGramHooks.shouldHidePremiumStatuses = { [weak self] in self?.currentSettings.hidePremiumStatuses ?? false }
        AyuGramHooks.avatarCornerRadius = { [weak self] in self?.currentSettings.avatarCorners ?? 23 }
        AyuGramHooks.messageBubbleRadius = { [weak self] in self?.currentSettings.messageBubbleRadius ?? 16 }
        AyuGramHooks.shouldUseSingleCornerRadius = { [weak self] in self?.currentSettings.singleCornerRadius ?? false }
        AyuGramHooks.peerIdDisplayMode = { [weak self] in self?.currentSettings.showDialogId ?? 0 }
        AyuGramHooks.sendWithoutSoundMode = { [weak self] in self?.currentSettings.sendWithoutSoundOption ?? 0 }

        // MARK: - Filters (W4)
        AyuGramHooks.isShadowBanned = { [weak self] peerId in
            guard let s = self?.currentSettings, s.enableFilters else { return false }
            return s.shadowBanIds.contains(peerId)
        }
        AyuGramHooks.isMessageHiddenByFilter = { [weak self] peerId, text in
            guard let self = self, self.currentSettings.enableFilters else { return false }
            if self.currentSettings.shadowBanIds.contains(peerId) { return true }
            if text.isEmpty { return false }
            let range = NSRange(text.startIndex..., in: text)
            for regex in self.compiledFilters {
                if regex.firstMatch(in: text, options: [], range: range) != nil {
                    return true
                }
            }
            return false
        }

        self.settingsDisposable = ayuGramSettings(accountManager: accountManager).start(next: { [weak self] settings in
            self?.currentSettings = settings
            self?.recompileFilters()
        })
    }

    deinit {
        self.settingsDisposable?.dispose()
    }
}
