import Postbox
import SwiftSignalKit
import TelegramCore
import AyuGramLib

public final class AyuGramFeatureManager {
    public let registry: GRVMAccountFeatureRegistry

    private var currentSettings: AyuGramSettings {
        return self.registry.primaryService()?.settingsSnapshot() ?? .defaultSettings
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
        AyuGramHooks.isLocalPremiumEnabled = { [weak self] peerId in
            guard let service = self?.registry.primaryService(), service.accountPeerId == peerId else {
                return false
            }
            return service.settingsSnapshot().localTelegramPremium
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

        // MARK: - Sending
        AyuGramHooks.shouldUseScheduledMessages = { [weak self] in
            guard let s = self?.currentSettings else { return false }
            // Send-in-Ghost only applies while a full Ghost Mode is active (desktop parity).
            return s.useScheduledMessages && s.ghostModeEnabled && s.suppressOnlineStatus
        }
        AyuGramHooks.shouldSendWithoutSound = { [weak self] in
            guard let s = self?.currentSettings else { return false }
            // sendWithoutSoundOption: 0 Never / 1 InGhost / 2 Always (6.7.8 mode).
            switch s.sendWithoutSoundOption {
            case 2:
                return true
            case 1:
                return s.ghostModeEnabled
            default:
                // Never (0) — fall back to the legacy standalone toggle.
                return s.sendWithoutSound
            }
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
        AyuGramHooks.avatarCornerRadius = { [weak self] in self?.currentSettings.avatarCorners ?? 50 }
        AyuGramHooks.messageBubbleRadius = { [weak self] in self?.currentSettings.messageBubbleRadius ?? 16 }
        AyuGramHooks.shouldUseSingleCornerRadius = { [weak self] in self?.currentSettings.singleCornerRadius ?? false }
        AyuGramHooks.peerIdDisplayMode = { [weak self] in self?.currentSettings.showDialogId ?? 0 }
        AyuGramHooks.sendWithoutSoundMode = { [weak self] in self?.currentSettings.sendWithoutSoundOption ?? 0 }

        // MARK: - Filters (W4)
        AyuGramHooks.isShadowBanned = { [weak self] peerId in
            return self?.registry.primaryService()?.isShadowBanned(peerId) ?? false
        }
        AyuGramHooks.isMessageHiddenByFilter = { [weak self] peerId, text in
            return self?.registry.primaryService()?.isMessageHiddenByFilter(peerId: peerId, text: text) ?? false
        }
    }
}
