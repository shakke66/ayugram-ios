import Postbox
import SwiftSignalKit
import TelegramCore
import AyuGramLib

public final class AyuGramFeatureManager {
    public let registry: GRVMAccountFeatureRegistry

    private var currentSettings: AyuGramSettings {
        return self.registry.primaryService()?.settingsSnapshot() ?? .defaultSettings
    }

    private func settings(accountPeerId: PeerId) -> AyuGramSettings? {
        return self.registry.service(accountPeerId: accountPeerId)?.settingsSnapshot()
    }

    public init(registry: GRVMAccountFeatureRegistry) {
        self.registry = registry
    }

    public func wireHooks() {
        // MARK: - Spy Mode
        AyuGramHooks.shouldSaveDeletedMessages = { [weak self] accountPeerId in
            guard let service = self?.registry.service(accountPeerId: accountPeerId) else {
                return true
            }
            return service.settingsSnapshot().saveDeletedMessages
        }
        AyuGramHooks.preserveDeletedMessages = { [weak self] accountPeerId, messages, source in
            guard let service = self?.registry.service(accountPeerId: accountPeerId) else {
                return .unavailable
            }
            return service.preserveDeletedMessages(messages, source: source)
        }
        AyuGramHooks.preserveEditRevision = { [weak self] accountPeerId, message, content in
            return self?.registry.service(accountPeerId: accountPeerId)?.preserveEditRevision(
                message,
                content: content
            ) ?? false
        }
        AyuGramHooks.hasEditHistory = { [weak self] accountPeerId, messageId in
            return self?.registry.service(accountPeerId: accountPeerId)?.hasEditHistory(messageId) ?? false
        }
        AyuGramFeatures.deletedMessages = { [weak self] accountPeerId, peerId, threadId, query in
            return self?.registry.service(accountPeerId: accountPeerId)?.deletedMessages(
                peerId: peerId,
                threadId: threadId,
                query: query
            ) ?? .single([])
        }
        AyuGramFeatures.clearDeleted = { [weak self] accountPeerId, peerId, threadId in
            return self?.registry.service(accountPeerId: accountPeerId)?.clearDeleted(
                peerId: peerId,
                threadId: threadId
            ) ?? .fail(.archiveUnavailable)
        }
        AyuGramFeatures.editHistory = { [weak self] accountPeerId, messageId in
            return self?.registry.service(accountPeerId: accountPeerId)?.editHistory(messageId) ?? .single([])
        }
        AyuGramHooks.shouldPreserveOneTimeMedia = { [weak self] accountPeerId in
            guard let service = self?.registry.service(accountPeerId: accountPeerId) else {
                return true
            }
            return service.settingsSnapshot().saveDeletedMessages
        }

        // MARK: - Ghost Mode
        AyuGramHooks.shouldSuppressReadReceipts = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.ghostModeEnabled && settings.suppressReadReceipts
        }
        AyuGramHooks.shouldSuppressPresence = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.ghostModeEnabled && settings.suppressOnlineStatus
        }
        let shouldSuppressTypingAndUploads: (PeerId) -> Bool = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.ghostModeEnabled
                && (settings.suppressTypingStatus || settings.suppressUploadProgress)
        }
        AyuGramHooks.shouldSuppressTyping = shouldSuppressTypingAndUploads
        AyuGramHooks.shouldSuppressUploadProgress = shouldSuppressTypingAndUploads
        AyuGramHooks.shouldSuppressStoryRead = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.ghostModeEnabled && settings.suppressStoryReads
        }
        AyuGramHooks.shouldSuppressContentRead = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.ghostModeEnabled && settings.suppressReadReceipts
        }
        AyuGramHooks.shouldForceOfflineAfterOnline = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.ghostModeEnabled && settings.goOfflineAfterOnline
        }

        // MARK: - Premium & Ads
        AyuGramHooks.isLocalPremiumEnabled = { [weak self] peerId in
            guard let service = self?.registry.primaryService(), service.accountPeerId == peerId else {
                return false
            }
            return service.settingsSnapshot().localTelegramPremium
        }
        AyuGramHooks.shouldDisableAds = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.disableAds ?? false
        }

        // MARK: - General
        AyuGramHooks.shouldHideStories = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.hideStories ?? false
        }
        AyuGramHooks.shouldDisableSimilarChannels = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.disableSimilarChannels ?? false
        }
        AyuGramHooks.shouldDisableNotificationDelay = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.disableNotificationDelay ?? false
        }
        AyuGramHooks.shouldShowSeconds = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.showSecondsInMessages ?? false
        }
        AyuGramHooks.shouldShowDialogID = { [weak self] accountPeerId in
            return (self?.settings(accountPeerId: accountPeerId)?.showDialogId ?? 0) != 0
        }
        AyuGramHooks.shouldSpoofWebviewAsAndroid = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.spoofWebviewAsAndroid ?? false
        }
        AyuGramHooks.shouldIncreaseWebviewHeight = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.increaseWebviewHeight ?? false
        }
        AyuGramHooks.shouldIncreaseWebviewWidth = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.increaseWebviewWidth ?? false
        }
        AyuGramHooks.shouldConfirmStickers = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.confirmSendSticker ?? false
        }
        AyuGramHooks.shouldConfirmGIF = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.confirmSendGIF ?? false
        }
        AyuGramHooks.shouldConfirmVoice = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.confirmSendVoice ?? false
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

        // MARK: - Sending
        AyuGramHooks.shouldUseScheduledMessages = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.ghostModeEnabled
                && settings.useScheduledMessages
                && !settings.readOnAction
        }

        // MARK: - W0 Reanimation & 6.7.8
        AyuGramHooks.shouldMarkReadAfterAction = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.ghostModeEnabled
                && settings.readOnAction
                && !settings.useScheduledMessages
        }
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
        AyuGramHooks.shouldSuggestGhostForStories = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.suggestGhostForStories ?? false
        }
        AyuGramHooks.shouldFilterZalgo = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.filterZalgo ?? false
        }
        AyuGramHooks.shouldImproveLinkPreviews = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.improveLinkPreviews ?? false
        }
        AyuGramHooks.shouldUseSemiTransparentDeleted = { [weak self] in self?.currentSettings.semiTransparentDeletedMessages ?? false }
        AyuGramHooks.shouldHidePremiumStatuses = { [weak self] in self?.currentSettings.hidePremiumStatuses ?? false }
        AyuGramHooks.avatarCornerRadius = { [weak self] in self?.currentSettings.avatarCorners ?? 50 }
        AyuGramHooks.messageBubbleRadius = { [weak self] in self?.currentSettings.messageBubbleRadius ?? 16 }
        AyuGramHooks.shouldUseSingleCornerRadius = { [weak self] in self?.currentSettings.singleCornerRadius ?? false }
        AyuGramHooks.peerIdDisplayMode = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.showDialogId ?? 0
        }
        AyuGramHooks.sendWithoutSoundMode = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return 0 }
            switch settings.sendWithoutSoundOption {
            case 2:
                return 2
            case 1:
                return settings.ghostModeEnabled ? 1 : 0
            default:
                return 0
            }
        }

        // MARK: - Filters (W4)
        AyuGramHooks.isShadowBanned = { [weak self] accountPeerId, peerId in
            return self?.registry.service(accountPeerId: accountPeerId)?.isShadowBanned(
                peerId.toInt64()
            ) ?? false
        }
        AyuGramHooks.isMessageHiddenByFilter = { [weak self] accountPeerId, message in
            return self?.registry.service(accountPeerId: accountPeerId)?.isMessageHiddenByFilter(
                peerId: message.id.peerId.toInt64(),
                text: message.text
            ) ?? false
        }
    }
}
