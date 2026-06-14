import Foundation
import UIKit
import Display
import SwiftSignalKit
import Postbox
import TelegramCore
import TelegramPresentationData
import TelegramUIPreferences
import ItemListUI
import PresentationDataUtils
import AccountContext
import AyuGramLib

private final class AyuGramCoreArguments {
    let context: AccountContext
    let toggleGhostMode: (Bool) -> Void
    let toggleSuppressReadReceipts: (Bool) -> Void
    let toggleSuppressStoryReads: (Bool) -> Void
    let toggleSuppressOnlineStatus: (Bool) -> Void
    let toggleSuppressTypingStatus: (Bool) -> Void
    let toggleSuppressUploadProgress: (Bool) -> Void
    let toggleReadOnAction: (Bool) -> Void
    let toggleUseScheduledMessages: (Bool) -> Void
    let toggleSendWithoutSound: (Bool) -> Void
    let toggleSaveDeletedMessages: (Bool) -> Void
    let toggleSaveEditHistory: (Bool) -> Void
    let toggleSaveForBots: (Bool) -> Void
    let toggleLocalPremium: (Bool) -> Void
    let toggleDisableAds: (Bool) -> Void
    let toggleSuggestGhostForStories: (Bool) -> Void

    init(
        context: AccountContext,
        toggleGhostMode: @escaping (Bool) -> Void,
        toggleSuppressReadReceipts: @escaping (Bool) -> Void,
        toggleSuppressStoryReads: @escaping (Bool) -> Void,
        toggleSuppressOnlineStatus: @escaping (Bool) -> Void,
        toggleSuppressTypingStatus: @escaping (Bool) -> Void,
        toggleSuppressUploadProgress: @escaping (Bool) -> Void,
        toggleReadOnAction: @escaping (Bool) -> Void,
        toggleUseScheduledMessages: @escaping (Bool) -> Void,
        toggleSendWithoutSound: @escaping (Bool) -> Void,
        toggleSaveDeletedMessages: @escaping (Bool) -> Void,
        toggleSaveEditHistory: @escaping (Bool) -> Void,
        toggleSaveForBots: @escaping (Bool) -> Void,
        toggleLocalPremium: @escaping (Bool) -> Void,
        toggleDisableAds: @escaping (Bool) -> Void,
        toggleSuggestGhostForStories: @escaping (Bool) -> Void
    ) {
        self.context = context
        self.toggleGhostMode = toggleGhostMode
        self.toggleSuppressReadReceipts = toggleSuppressReadReceipts
        self.toggleSuppressStoryReads = toggleSuppressStoryReads
        self.toggleSuppressOnlineStatus = toggleSuppressOnlineStatus
        self.toggleSuppressTypingStatus = toggleSuppressTypingStatus
        self.toggleSuppressUploadProgress = toggleSuppressUploadProgress
        self.toggleReadOnAction = toggleReadOnAction
        self.toggleUseScheduledMessages = toggleUseScheduledMessages
        self.toggleSendWithoutSound = toggleSendWithoutSound
        self.toggleSaveDeletedMessages = toggleSaveDeletedMessages
        self.toggleSaveEditHistory = toggleSaveEditHistory
        self.toggleSaveForBots = toggleSaveForBots
        self.toggleLocalPremium = toggleLocalPremium
        self.toggleDisableAds = toggleDisableAds
        self.toggleSuggestGhostForStories = toggleSuggestGhostForStories
    }
}

private enum AyuGramCoreSection: Int32 {
    case ghostMode
    case ghostComponents
    case sending
    case spyMode
    case other
}

private enum AyuGramCoreEntry: ItemListNodeEntry {
    case ghostModeHeader(PresentationTheme)
    case ghostModeToggle(PresentationTheme, String, Bool)
    case ghostComponentReadReceipts(PresentationTheme, Bool)
    case ghostComponentStoryReads(PresentationTheme, Bool)
    case ghostComponentOnlineStatus(PresentationTheme, Bool)
    case ghostComponentTypingStatus(PresentationTheme, Bool)
    case ghostComponentUploadProgress(PresentationTheme, Bool)
    case readOnAction(PresentationTheme, Bool)
    case readOnActionInfo(PresentationTheme)
    case suggestGhostForStories(PresentationTheme, Bool)
    case suggestGhostForStoriesInfo(PresentationTheme)
    case useScheduledMessages(PresentationTheme, Bool)
    case useScheduledMessagesInfo(PresentationTheme)
    case sendWithoutSound(PresentationTheme, Bool)
    case sendWithoutSoundInfo(PresentationTheme)
    case spyModeHeader(PresentationTheme)
    case saveDeletedMessages(PresentationTheme, Bool)
    case saveEditHistory(PresentationTheme, Bool)
    case saveForBots(PresentationTheme, Bool)
    case otherHeader(PresentationTheme)
    case localPremium(PresentationTheme, Bool)
    case disableAds(PresentationTheme, Bool)

    var section: ItemListSectionId {
        switch self {
        case .ghostModeHeader, .ghostModeToggle, .ghostComponentReadReceipts, .ghostComponentStoryReads, .ghostComponentOnlineStatus, .ghostComponentTypingStatus, .ghostComponentUploadProgress, .readOnAction, .readOnActionInfo, .suggestGhostForStories, .suggestGhostForStoriesInfo:
            return AyuGramCoreSection.ghostMode.rawValue
        case .useScheduledMessages, .useScheduledMessagesInfo, .sendWithoutSound, .sendWithoutSoundInfo:
            return AyuGramCoreSection.sending.rawValue
        case .spyModeHeader, .saveDeletedMessages, .saveEditHistory, .saveForBots:
            return AyuGramCoreSection.spyMode.rawValue
        case .otherHeader, .localPremium, .disableAds:
            return AyuGramCoreSection.other.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .ghostModeHeader: return 0
        case .ghostModeToggle: return 1
        case .ghostComponentReadReceipts: return 2
        case .ghostComponentStoryReads: return 3
        case .ghostComponentOnlineStatus: return 4
        case .ghostComponentTypingStatus: return 5
        case .ghostComponentUploadProgress: return 6
        case .readOnAction: return 7
        case .readOnActionInfo: return 8
        case .suggestGhostForStories: return 9
        case .suggestGhostForStoriesInfo: return 10
        case .useScheduledMessages: return 11
        case .useScheduledMessagesInfo: return 12
        case .sendWithoutSound: return 13
        case .sendWithoutSoundInfo: return 14
        case .spyModeHeader: return 15
        case .saveDeletedMessages: return 16
        case .saveEditHistory: return 17
        case .saveForBots: return 18
        case .otherHeader: return 19
        case .localPremium: return 20
        case .disableAds: return 21
        }
    }

    static func ==(lhs: AyuGramCoreEntry, rhs: AyuGramCoreEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.ghostModeToggle(_, lhsLabel, lhsValue), .ghostModeToggle(_, rhsLabel, rhsValue)):
            return lhsLabel == rhsLabel && lhsValue == rhsValue
        case let (.ghostComponentReadReceipts(_, lhsValue), .ghostComponentReadReceipts(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.ghostComponentStoryReads(_, lhsValue), .ghostComponentStoryReads(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.ghostComponentOnlineStatus(_, lhsValue), .ghostComponentOnlineStatus(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.ghostComponentTypingStatus(_, lhsValue), .ghostComponentTypingStatus(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.ghostComponentUploadProgress(_, lhsValue), .ghostComponentUploadProgress(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.suggestGhostForStories(_, lhsValue), .suggestGhostForStories(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.readOnAction(_, lhsValue), .readOnAction(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.useScheduledMessages(_, lhsValue), .useScheduledMessages(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.sendWithoutSound(_, lhsValue), .sendWithoutSound(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.saveDeletedMessages(_, lhsValue), .saveDeletedMessages(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.saveEditHistory(_, lhsValue), .saveEditHistory(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.saveForBots(_, lhsValue), .saveForBots(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.localPremium(_, lhsValue), .localPremium(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.disableAds(_, lhsValue), .disableAds(_, rhsValue)):
            return lhsValue == rhsValue
        default:
            return lhs.stableId == rhs.stableId
        }
    }

    static func <(lhs: AyuGramCoreEntry, rhs: AyuGramCoreEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramCoreArguments
        switch self {
        case .ghostModeHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Ghost Mode", sectionId: self.section)
        case let .ghostModeToggle(_, label, value):
            return ItemListSwitchItem(presentationData: presentationData, title: label, value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleGhostMode(value)
            })
        case let .ghostComponentReadReceipts(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Don't Send Read Receipts", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressReadReceipts(value)
            })
        case let .ghostComponentStoryReads(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Don't Send Story Views", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressStoryReads(value)
            })
        case let .ghostComponentOnlineStatus(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Don't Send Online Status", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressOnlineStatus(value)
            })
        case let .ghostComponentTypingStatus(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Don't Send Typing Status", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressTypingStatus(value)
            })
        case let .ghostComponentUploadProgress(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Don't Send Upload Progress", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressUploadProgress(value)
            })
        case let .readOnAction(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Mark Read on Action", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleReadOnAction(value)
            })
        case .readOnActionInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Automatically marks messages as read when you send a new message or react."), sectionId: self.section)
        case let .suggestGhostForStories(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Suggest Ghost Mode for Stories", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuggestGhostForStories(value)
            })
        case .suggestGhostForStoriesInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Shows a prompt before opening stories, offering to enable Ghost Mode."), sectionId: self.section)
        case let .useScheduledMessages(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Use Scheduled Messages", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleUseScheduledMessages(value)
            })
        case .useScheduledMessagesInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Automatically schedules messages with ~12 second delay. You won't appear online. Not recommended on slow internet."), sectionId: self.section)
        case let .sendWithoutSound(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Send Without Sound", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSendWithoutSound(value)
            })
        case .sendWithoutSoundInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain("Sends messages silently by default."), sectionId: self.section)
        case .spyModeHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Spy Mode", sectionId: self.section)
        case let .saveDeletedMessages(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Save Deleted Messages", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSaveDeletedMessages(value)
            })
        case let .saveEditHistory(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Save Edit History", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSaveEditHistory(value)
            })
        case let .saveForBots(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Save in Bot Chats", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSaveForBots(value)
            })
        case .otherHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: "Other", sectionId: self.section)
        case let .localPremium(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Local Telegram Premium", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleLocalPremium(value)
            })
        case let .disableAds(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: "Disable Ads", value: value, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleDisableAds(value)
            })
        }
    }
}

private func ayuGramCoreEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramCoreEntry] {
    var entries: [AyuGramCoreEntry] = []

    entries.append(.ghostModeHeader(presentationData.theme))
    let ghostLabel = "Ghost Mode \(settings.ghostModeActiveCount)/5"
    entries.append(.ghostModeToggle(presentationData.theme, ghostLabel, settings.ghostModeEnabled))
    entries.append(.ghostComponentReadReceipts(presentationData.theme, settings.suppressReadReceipts))
    entries.append(.ghostComponentStoryReads(presentationData.theme, settings.suppressStoryReads))
    entries.append(.ghostComponentOnlineStatus(presentationData.theme, settings.suppressOnlineStatus))
    entries.append(.ghostComponentTypingStatus(presentationData.theme, settings.suppressTypingStatus))
    entries.append(.ghostComponentUploadProgress(presentationData.theme, settings.suppressUploadProgress))
    entries.append(.readOnAction(presentationData.theme, settings.readOnAction))
    entries.append(.readOnActionInfo(presentationData.theme))
    entries.append(.suggestGhostForStories(presentationData.theme, settings.suggestGhostForStories))
    entries.append(.suggestGhostForStoriesInfo(presentationData.theme))

    entries.append(.useScheduledMessages(presentationData.theme, settings.useScheduledMessages))
    entries.append(.useScheduledMessagesInfo(presentationData.theme))
    entries.append(.sendWithoutSound(presentationData.theme, settings.sendWithoutSound))
    entries.append(.sendWithoutSoundInfo(presentationData.theme))

    entries.append(.spyModeHeader(presentationData.theme))
    entries.append(.saveDeletedMessages(presentationData.theme, settings.saveDeletedMessages))
    entries.append(.saveEditHistory(presentationData.theme, settings.saveEditHistory))
    entries.append(.saveForBots(presentationData.theme, settings.saveForBots))

    entries.append(.otherHeader(presentationData.theme))
    entries.append(.localPremium(presentationData.theme, settings.localTelegramPremium))
    entries.append(.disableAds(presentationData.theme, settings.disableAds))

    return entries
}

public func ayuGramCoreController(context: AccountContext) -> ViewController {
    let arguments = AyuGramCoreArguments(
        context: context,
        toggleGhostMode: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.setGhostMode(value)
                return settings
            }).startStandalone()
        },
        toggleSuppressReadReceipts: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressReadReceipts = value
                return settings
            }).startStandalone()
        },
        toggleSuppressStoryReads: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressStoryReads = value
                return settings
            }).startStandalone()
        },
        toggleSuppressOnlineStatus: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressOnlineStatus = value
                return settings
            }).startStandalone()
        },
        toggleSuppressTypingStatus: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressTypingStatus = value
                return settings
            }).startStandalone()
        },
        toggleSuppressUploadProgress: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressUploadProgress = value
                return settings
            }).startStandalone()
        },
        toggleReadOnAction: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.readOnAction = value
                return settings
            }).startStandalone()
        },
        toggleUseScheduledMessages: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.useScheduledMessages = value
                return settings
            }).startStandalone()
        },
        toggleSendWithoutSound: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.sendWithoutSound = value
                return settings
            }).startStandalone()
        },
        toggleSaveDeletedMessages: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.saveDeletedMessages = value
                return settings
            }).startStandalone()
        },
        toggleSaveEditHistory: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.saveEditHistory = value
                return settings
            }).startStandalone()
        },
        toggleSaveForBots: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.saveForBots = value
                return settings
            }).startStandalone()
        },
        toggleLocalPremium: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.localTelegramPremium = value
                return settings
            }).startStandalone()
        },
        toggleDisableAds: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.disableAds = value
                return settings
            }).startStandalone()
        },
        toggleSuggestGhostForStories: { value in
            let _ = updateAyuGramSettings(accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suggestGhostForStories = value
                return settings
            }).startStandalone()
        }
    )

    let signal = combineLatest(
        context.sharedContext.presentationData,
        ayuGramSettings(accountManager: context.sharedContext.accountManager)
    )
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuGramCoreEntries(settings: settings, presentationData: presentationData)
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text("AyuGram"),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: entries,
            style: .blocks
        )
        return (controllerState, (listState, arguments))
    }

    let controller = ItemListController(context: context, state: signal)
    return controller
}
