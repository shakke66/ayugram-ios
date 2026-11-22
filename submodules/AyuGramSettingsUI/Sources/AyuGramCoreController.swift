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
    let toggleSuppressTypingAndUploads: (Bool) -> Void
    let setSendWithoutSoundMode: (Int32) -> Void
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
        toggleSuppressTypingAndUploads: @escaping (Bool) -> Void,
        setSendWithoutSoundMode: @escaping (Int32) -> Void,
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
        self.toggleSuppressTypingAndUploads = toggleSuppressTypingAndUploads
        self.setSendWithoutSoundMode = setSendWithoutSoundMode
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
    case ghostComponentTypingAndUploads(PresentationTheme, Bool)
    case suggestGhostForStories(PresentationTheme, Bool)
    case suggestGhostForStoriesInfo(PresentationTheme)
    case sendWithoutSoundMode(PresentationTheme, String, Int32)
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
        case .ghostModeHeader, .ghostModeToggle, .ghostComponentReadReceipts, .ghostComponentStoryReads, .ghostComponentOnlineStatus, .ghostComponentTypingAndUploads, .suggestGhostForStories, .suggestGhostForStoriesInfo:
            return AyuGramCoreSection.ghostMode.rawValue
        case .sendWithoutSoundMode, .sendWithoutSoundInfo:
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
        case .ghostComponentTypingAndUploads: return 5
        case .suggestGhostForStories: return 10
        case .suggestGhostForStoriesInfo: return 11
        case .sendWithoutSoundMode: return 14
        case .sendWithoutSoundInfo: return 15
        case .spyModeHeader: return 16
        case .saveDeletedMessages: return 17
        case .saveEditHistory: return 18
        case .saveForBots: return 19
        case .otherHeader: return 20
        case .localPremium: return 21
        case .disableAds: return 22
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
        case let (.ghostComponentTypingAndUploads(_, lhsValue), .ghostComponentTypingAndUploads(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.suggestGhostForStories(_, lhsValue), .suggestGhostForStories(_, rhsValue)):
            return lhsValue == rhsValue
        case let (.sendWithoutSoundMode(_, lhsLabel, lhsValue), .sendWithoutSoundMode(_, rhsLabel, rhsValue)):
            return lhsLabel == rhsLabel && lhsValue == rhsValue
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
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case .ghostModeHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.ghostHeader], sectionId: self.section)
        case let .ghostModeToggle(_, label, value):
            return ItemListSwitchItem(presentationData: presentationData, title: label, value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleGhostMode(value)
            })
        case let .ghostComponentReadReceipts(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.ghostReadReceipts], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressReadReceipts(value)
            })
        case let .ghostComponentStoryReads(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.ghostStoryViews], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressStoryReads(value)
            })
        case let .ghostComponentOnlineStatus(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.ghostOnline], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressOnlineStatus(value)
            })
        case let .ghostComponentTypingAndUploads(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.ghostTyping], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuppressTypingAndUploads(value)
            })
        case let .suggestGhostForStories(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.ghostStoryPrompt], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSuggestGhostForStories(value)
            })
        case .suggestGhostForStoriesInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain(strings[.ghostStoryPromptInfo]), sectionId: self.section)
        case let .sendWithoutSoundMode(_, label, value):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: strings[.ghostSilent], label: label, sectionId: self.section, style: .blocks, action: {
                arguments.setSendWithoutSoundMode((value + 1) % 3)
            })
        case .sendWithoutSoundInfo:
            return ItemListTextItem(presentationData: presentationData, text: .plain(strings[.ghostSilentInfo]), sectionId: self.section)
        case .spyModeHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.spyHeader], sectionId: self.section)
        case let .saveDeletedMessages(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.spySaveDeleted], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSaveDeletedMessages(value)
            })
        case let .saveEditHistory(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.spySaveEdits], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSaveEditHistory(value)
            })
        case let .saveForBots(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.spySaveBots], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleSaveForBots(value)
            })
        case .otherHeader:
            return ItemListSectionHeaderItem(presentationData: presentationData, text: strings[.coreOtherHeader], sectionId: self.section)
        case let .localPremium(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.coreLocalPremium], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleLocalPremium(value)
            })
        case let .disableAds(_, value):
            return ItemListSwitchItem(presentationData: presentationData, title: strings[.coreDisableAds], value: value, maximumNumberOfLines: 2, adaptiveLayout: true, sectionId: self.section, style: .blocks, updated: { value in
                arguments.toggleDisableAds(value)
            })
        }
    }
}

private func ayuGramCoreEntries(settings: AyuGramSettings, presentationData: PresentationData) -> [AyuGramCoreEntry] {
    let strings = GRVMgramStrings(presentationData.strings)
    var entries: [AyuGramCoreEntry] = []

    entries.append(.ghostModeHeader(presentationData.theme))
    let ghostLabel = strings.format(.ghostActiveCount, Int32(settings.ghostModeActiveCount))
    entries.append(.ghostModeToggle(presentationData.theme, ghostLabel, settings.ghostModeActiveCount == 4))
    entries.append(.ghostComponentReadReceipts(presentationData.theme, settings.suppressReadReceipts))
    entries.append(.ghostComponentStoryReads(presentationData.theme, settings.suppressStoryReads))
    entries.append(.ghostComponentOnlineStatus(presentationData.theme, settings.suppressOnlineStatus))
    entries.append(.ghostComponentTypingAndUploads(presentationData.theme, settings.suppressTypingAndUploads))
    entries.append(.suggestGhostForStories(presentationData.theme, settings.suggestGhostForStories))
    entries.append(.suggestGhostForStoriesInfo(presentationData.theme))

    let sendWithoutSoundLabels = [
        strings[.commonNever],
        strings[.commonInGhost],
        strings[.commonAlways],
    ]
    let sendWithoutSoundMode = (0 ... 2).contains(settings.sendWithoutSoundMode) ? settings.sendWithoutSoundMode : 0
    entries.append(.sendWithoutSoundMode(presentationData.theme, sendWithoutSoundLabels[Int(sendWithoutSoundMode)], sendWithoutSoundMode))
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
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.setGhostModeEnabled(value)
                return settings
            }).startStandalone()
        },
        toggleSuppressReadReceipts: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressReadReceipts = value
                return settings
            }).startStandalone()
        },
        toggleSuppressStoryReads: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressStoryReads = value
                return settings
            }).startStandalone()
        },
        toggleSuppressOnlineStatus: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressOnlineStatus = value
                return settings
            }).startStandalone()
        },
        toggleSuppressTypingAndUploads: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suppressTypingAndUploads = value
                return settings
            }).startStandalone()
        },
        setSendWithoutSoundMode: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.sendWithoutSoundMode = value
                return settings
            }).startStandalone()
        },
        toggleSaveDeletedMessages: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.saveDeletedMessages = value
                return settings
            }).startStandalone()
        },
        toggleSaveEditHistory: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.saveEditHistory = value
                return settings
            }).startStandalone()
        },
        toggleSaveForBots: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.saveForBots = value
                return settings
            }).startStandalone()
        },
        toggleLocalPremium: { value in
            let settingsUpdate = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.localTelegramPremium = value
                return settings
            })
            let cleanup: Signal<Never, NoError>
            if value {
                cleanup = .complete()
            } else {
                cleanup = grvmClearLocalPremiumSelfState(
                    postbox: context.account.postbox,
                    accountPeerId: context.account.peerId
                )
            }
            let _ = (settingsUpdate |> ignoreValues |> then(cleanup)).startStandalone()
        },
        toggleDisableAds: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.disableAds = value
                return settings
            }).startStandalone()
        },
        toggleSuggestGhostForStories: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager, { settings in
                var settings = settings
                settings.suggestGhostForStories = value
                return settings
            }).startStandalone()
        }
    )

    let signal = combineLatest(
        context.sharedContext.presentationData,
        grvmSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager)
    )
    |> map { presentationData, settings -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let entries = ayuGramCoreEntries(settings: settings, presentationData: presentationData)
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text(strings[.coreTitle]),
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

    return ItemListController(context: context, state: signal)
}
