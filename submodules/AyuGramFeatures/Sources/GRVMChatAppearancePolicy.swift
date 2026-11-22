import Foundation
import SwiftSignalKit
import TelegramCore
import AyuGramLib

public extension AyuGramSettings {
    var grvmChatAppearanceSettings: GRVMChatAppearanceSettings {
        let recentStickersCount = min(200, max(1, self.recentStickersCount))
        let avatarCorners = min(50, max(0, self.avatarCorners))
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
                removeMessageBubbleTail: self.removeMessageBubbleTail,
                codeFontName: self.codeFontName,
                hideFolderCounters: self.hideFolderCounters,
                hideAllChatsFolder: self.hideAllChatsFolder,
                hidePremiumStatuses: self.hidePremiumStatuses,
                avatarCorners: avatarCorners
            ),
            chats: GRVMChatSettings(
                showOnlyAddedStickers: self.showOnlyAddedStickers,
                showChannelReactions: self.showChannelReactions,
                showGroupReactions: self.showGroupReactions,
                showPrivateReactions: self.showPrivateReactions,
                recentStickersCount: recentStickersCount,
                channelBottomButton: GRVMChannelBottomButtonMode(normalizingRawValue: self.channelBottomButton),
                quickAdminShortcuts: self.quickAdminShortcuts,
                showDeletedMark: self.showDeletedMark,
                showEditedMark: self.showEditedMark,
                deletedMessageMark: self.deletedMessageMark,
                editedMessageMark: self.editedMessageMark,
                replaceMarksWithIcons: self.replaceMarksWithIcons,
                hideFastShareButton: self.hideFastShareButton,
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
                showTTLButton: self.showTTLButton,
                showEmojiButton: self.showEmojiButton,
                showVoiceButton: self.showVoiceButton,
                showGiftButton: self.showGiftButton,
                showAiEditorButton: self.showAiEditorButton
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
    }
}
