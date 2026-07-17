import Foundation
import SwiftSignalKit
import TelegramCore
import AyuGramLib
import Display

public extension AyuGramSettings {
    var grvmChatAppearanceSettings: GRVMChatAppearanceSettings {
        let recentStickersCount = min(200, max(1, self.recentStickersCount))
        let avatarCorners = min(50, max(0, self.avatarCorners))
        let messageBubbleRadius = min(16, max(0, self.messageBubbleRadius))
        let clampedWidth = min(4.0, max(0.5, self.messageWidthMultiplier))
        let messageWidthMultiplier = (clampedWidth * 20.0).rounded() / 20.0

        func visibility(
            _ value: Int32,
            fallback: GRVMContextMenuVisibility
        ) -> GRVMContextMenuVisibility {
            return GRVMContextMenuVisibility(rawValue: value) ?? fallback
        }

        return GRVMChatAppearanceSettings(
            appearance: GRVMAppearanceSettings(
                selectedAppIcon: self.selectedAppIcon,
                hideNotificationBadge: self.hideNotificationBadge,
                hideNotificationCounters: self.hideNotificationCounters,
                md3StyleSwitches: self.md3StyleSwitches,
                removeMessageBubbleTail: self.removeMessageBubbleTail,
                disableCustomBackgrounds: self.disableCustomBackgrounds,
                codeFontName: self.codeFontName,
                hideFolderCounters: self.hideFolderCounters,
                hideAllChatsFolder: self.hideAllChatsFolder,
                hidePremiumStatuses: self.hidePremiumStatuses,
                avatarCorners: avatarCorners,
                singleCornerRadius: self.singleCornerRadius,
                messageBubbleRadius: messageBubbleRadius
            ),
            chats: GRVMChatSettings(
                showOnlyAddedStickers: self.showOnlyAddedStickers,
                showChannelReactions: self.showChannelReactions,
                showGroupReactions: self.showGroupReactions,
                showPrivateReactions: self.showPrivateReactions,
                recentStickersCount: recentStickersCount,
                channelBottomButton: GRVMChannelBottomButtonMode(rawValue: self.channelBottomButton) ?? .mute,
                quickAdminShortcuts: self.quickAdminShortcuts,
                messageShotFeature: self.messageShotFeature,
                showDeletedMark: self.showDeletedMark,
                showEditedMark: self.showEditedMark,
                deletedMessageMark: self.deletedMessageMark,
                editedMessageMark: self.editedMessageMark,
                replaceMarksWithIcons: self.replaceMarksWithIcons,
                hideFastShareButton: self.hideFastShareButton,
                disableColoredReplies: self.disableColoredReplies,
                semiTransparentDeletedMessages: self.semiTransparentDeletedMessages,
                messageWidthMultiplier: messageWidthMultiplier
            ),
            contextMenu: GRVMContextMenuSettings(
                reactions: visibility(self.showReactionsPanelInContextMenu, fallback: .hidden),
                views: visibility(self.showViewsPanelInContextMenu, fallback: .hidden),
                hide: visibility(self.showHideMessageInContextMenu, fallback: .visible),
                userMessages: visibility(self.showUserMessagesInContextMenu, fallback: .visible),
                details: visibility(self.showMessageDetailsInContextMenu, fallback: .visible),
                repeatMessage: visibility(self.showRepeatMessageInContextMenu, fallback: .visible),
                addFilter: visibility(self.showAddFilterInContextMenu, fallback: .visible)
            ),
            compose: GRVMComposeSettings(
                showAttachButton: self.showAttachButton,
                showCommandsButton: self.showCommandsButton,
                showTTLButton: self.showTTLButton,
                showEmojiButton: self.showEmojiButton,
                showVoiceButton: self.showVoiceButton,
                showGiftButton: self.showGiftButton,
                showAiEditorButton: self.showAiEditorButton,
                showAttachPopup: self.showAttachPopup,
                showEmojiPopup: self.showEmojiPopup
            ),
            messageShot: GRVMMessageShotOptions(
                showBackground: self.messageShotShowBackground,
                showDate: self.messageShotShowDate,
                showReactions: self.messageShotShowReactions,
                showHeader: self.messageShotShowHeader,
                showHeaderDecorations: self.messageShotShowHeaderDecorations,
                colorfulReplies: self.messageShotColorfulReplies,
                revealSpoilers: self.messageShotRevealSpoilers,
                theme: GRVMMessageShotTheme(rawValue: self.messageShotTheme) ?? .current
            )
        )
    }
}

public func installGRVMChatAppearanceHooks(registry: GRVMAccountFeatureRegistry) {
    AyuGramHooks.chatAppearanceSettings = { [weak registry] accountPeerId in
        guard let registry = registry,
              let service = registry.service(accountPeerId: accountPeerId) else {
            return .default
        }
        return service.settingsSnapshot().grvmChatAppearanceSettings
    }
}

func publishGRVMPrimaryChatAppearance(_ appearance: GRVMChatAppearanceSettings) {
    Queue.mainQueue().async {
        AyuGramHooks.updatePrimaryChatAppearance(appearance)
        SwitchNode.defaultStyle = appearance.appearance.md3StyleSwitches ? .md3 : .standard
    }
}
