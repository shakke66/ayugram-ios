import Postbox
import SwiftSignalKit
import TelegramCore
import AyuGramLib

private final class GRVMMessageFilterStateUpdates {
    private let queue = Queue(name: "GRVMMessageFilterStateUpdates")
    private let promise: ValuePromise<Int64>
    private var lastRevision: Int64

    init(revision: Int64) {
        self.promise = ValuePromise<Int64>(revision, ignoreRepeated: true)
        self.lastRevision = revision
    }

    func signal() -> Signal<Int64, NoError> {
        return self.promise.get()
    }

    func publish(revision: Int64) {
        self.queue.async { [weak self] in
            guard let self, revision > self.lastRevision else {
                return
            }
            self.lastRevision = revision
            self.promise.set(revision)
        }
    }
}

private struct FilterRuntimeState {
    var engines: [PeerId: GRVMMessageFilterEngine] = [:]
    var blockedPeerIds: [PeerId: Set<PeerId>] = [:]
    var settings: [PeerId: AyuGramSettings] = [:]
    var filterSettingsSubscriptions: [PeerId: MetaDisposable] = [:]
    var revisions: [PeerId: Int64] = [:]
    var revisionUpdates: [PeerId: GRVMMessageFilterStateUpdates] = [:]
}

public final class AyuGramFeatureManager {
    public let registry: GRVMAccountFeatureRegistry

    private let filterRuntimeState = Atomic<FilterRuntimeState>(value: FilterRuntimeState())
    private let filteredMessageVisibility = GRVMFilteredMessageVisibility()
    private let filteredUnreadCoordinators = Atomic<[PeerId: GRVMFilteredUnreadCoordinator]>(value: [:])
    private lazy var blockedPeersRegistry = GRVMBlockedPeersRegistry(updated: { [weak self] accountPeerId, peerIds in
        self?.updateBlockedPeerIds(accountPeerId: accountPeerId, peerIds: peerIds)
    })

    private var currentSettings: AyuGramSettings {
        return self.registry.primaryService()?.settingsSnapshot() ?? .defaultSettings
    }

    private func settings(accountPeerId: PeerId) -> AyuGramSettings? {
        return self.registry.service(accountPeerId: accountPeerId)?.settingsSnapshot()
    }

    private func isGhostActive(_ settings: AyuGramSettings) -> Bool {
        return settings.suppressReadReceipts
            || settings.suppressStoryReads
            || settings.suppressOnlineStatus
            || settings.suppressTypingAndUploads
    }

    public init(registry: GRVMAccountFeatureRegistry) {
        self.registry = registry
    }

    public func updateActiveAccounts(_ accounts: [Account]) {
        assert(Queue.mainQueue().isCurrent())
        let activeAccountPeerIds = Set(accounts.map(\.peerId))
        self.filteredMessageVisibility.retainAccounts(activeAccountPeerIds)
        var removedFilterSubscriptions: [MetaDisposable] = []
        _ = self.filterRuntimeState.modify { state in
            var state = state
            state.engines = state.engines.filter { activeAccountPeerIds.contains($0.key) }
            state.blockedPeerIds = state.blockedPeerIds.filter { activeAccountPeerIds.contains($0.key) }
            state.settings = state.settings.filter { activeAccountPeerIds.contains($0.key) }
            state.revisions = state.revisions.filter { activeAccountPeerIds.contains($0.key) }
            state.revisionUpdates = state.revisionUpdates.filter { activeAccountPeerIds.contains($0.key) }
            for accountPeerId in Array(state.filterSettingsSubscriptions.keys) where !activeAccountPeerIds.contains(accountPeerId) {
                if let disposable = state.filterSettingsSubscriptions.removeValue(forKey: accountPeerId) {
                    removedFilterSubscriptions.append(disposable)
                }
            }
            return state
        }
        for disposable in removedFilterSubscriptions {
            disposable.dispose()
        }
        var removedUnreadCoordinators: [GRVMFilteredUnreadCoordinator] = []
        _ = self.filteredUnreadCoordinators.modify { coordinators in
            var coordinators = coordinators
            for accountPeerId in coordinators.keys where !activeAccountPeerIds.contains(accountPeerId) {
                if let coordinator = coordinators.removeValue(forKey: accountPeerId) {
                    removedUnreadCoordinators.append(coordinator)
                }
            }
            for account in accounts where coordinators[account.peerId] == nil {
                let coordinator = GRVMFilteredUnreadCoordinator(
                    accountPeerId: account.peerId,
                    postbox: account.postbox
                )
                coordinator.start()
                coordinators[account.peerId] = coordinator
            }
            return coordinators
        }
        for coordinator in removedUnreadCoordinators {
            coordinator.stop()
        }
        for accountPeerId in activeAccountPeerIds {
            self.observeMessageFilterSettings(accountPeerId: accountPeerId)
            self.refreshFilteredUnread(accountPeerId: accountPeerId)
        }
        self.blockedPeersRegistry.updateAccounts(accounts)
    }

    private func filteredUnreadCoordinator(accountPeerId: PeerId) -> GRVMFilteredUnreadCoordinator? {
        return self.filteredUnreadCoordinators.with { $0[accountPeerId] }
    }

    private func refreshFilteredUnread(accountPeerId: PeerId) {
        guard let coordinator = self.filteredUnreadCoordinator(accountPeerId: accountPeerId) else {
            return
        }
        let runtime = self.filterRuntimeState.with { state in
            return (state.settings[accountPeerId], state.engines[accountPeerId])
        }
        let settings = runtime.0 ?? self.settings(accountPeerId: accountPeerId) ?? .defaultSettings
        let engine = runtime.1 ?? self.filterEngine(accountPeerId: accountPeerId)
        coordinator.setFilter(enabled: settings.enableFilters, predicate: { [weak self] message in
            guard let self else {
                return false
            }
            guard !self.filteredMessageVisibility.isShowing(
                accountPeerId: accountPeerId,
                chatPeerId: message.id.peerId
            ) else {
                return false
            }
            return engine?.isMessageHidden(message) ?? false
        })
    }

    private func observeMessageFilterSettings(accountPeerId: PeerId) {
        let disposable = MetaDisposable()
        var didInsert = false
        _ = self.filterRuntimeState.modify { state in
            var state = state
            guard state.filterSettingsSubscriptions[accountPeerId] == nil else {
                return state
            }
            state.filterSettingsSubscriptions[accountPeerId] = disposable
            didInsert = true
            return state
        }
        guard didInsert else {
            return
        }
        disposable.set((self.registry.messageFilterSettings(accountPeerId: accountPeerId)
        |> deliverOnMainQueue).start(next: { [weak self, weak disposable] settings in
            guard let self, let disposable,
                  self.filterRuntimeState.with({ $0.filterSettingsSubscriptions[accountPeerId] === disposable }) else {
                return
            }
            self.updateMessageFilterSettings(accountPeerId: accountPeerId, settings: settings)
        }))
    }

    private func updateMessageFilterSettings(accountPeerId: PeerId, settings: AyuGramSettings) {
        var didReplaceEngine = false
        _ = self.filterRuntimeState.modify { state in
            var state = state
            let blockedPeerIds = state.blockedPeerIds[accountPeerId] ?? []
            state.settings[accountPeerId] = settings
            if let engine = state.engines[accountPeerId],
               engine.settings == settings,
               engine.blockedPeerIds == blockedPeerIds {
                return state
            }
            state.engines[accountPeerId] = GRVMMessageFilterEngine(
                accountPeerId: accountPeerId,
                settings: settings,
                blockedPeerIds: blockedPeerIds
            )
            didReplaceEngine = true
            return state
        }
        if didReplaceEngine {
            self.advanceMessageFilterStateRevision(accountPeerId: accountPeerId)
            self.refreshFilteredUnread(accountPeerId: accountPeerId)
        }
    }

    private func updateBlockedPeerIds(accountPeerId: PeerId, peerIds: Set<PeerId>) {
        guard let service = self.registry.service(accountPeerId: accountPeerId) else {
            _ = self.filterRuntimeState.modify { state in
                var state = state
                state.engines.removeValue(forKey: accountPeerId)
                state.blockedPeerIds.removeValue(forKey: accountPeerId)
                return state
            }
            return
        }
        let fallbackSettings = service.settingsSnapshot()
        var didReplaceEngine = false
        _ = self.filterRuntimeState.modify { state in
            var state = state
            let settings = state.settings[accountPeerId] ?? fallbackSettings
            if state.blockedPeerIds[accountPeerId] == peerIds,
               let engine = state.engines[accountPeerId],
               engine.settings == settings {
                return state
            }
            state.blockedPeerIds[accountPeerId] = peerIds
            state.engines[accountPeerId] = GRVMMessageFilterEngine(
                accountPeerId: accountPeerId,
                settings: settings,
                blockedPeerIds: peerIds
            )
            didReplaceEngine = true
            return state
        }
        if didReplaceEngine {
            self.advanceMessageFilterStateRevision(accountPeerId: accountPeerId)
            self.refreshFilteredUnread(accountPeerId: accountPeerId)
        }
    }

    private func filterEngine(accountPeerId: PeerId) -> GRVMMessageFilterEngine? {
        guard let service = self.registry.service(accountPeerId: accountPeerId) else {
            _ = self.filterRuntimeState.modify { state in
                var state = state
                state.engines.removeValue(forKey: accountPeerId)
                state.blockedPeerIds.removeValue(forKey: accountPeerId)
                return state
            }
            return nil
        }
        let fallbackSettings = service.settingsSnapshot()
        var didReplaceEngine = false
        let state = self.filterRuntimeState.modify { state in
            var state = state
            let settings = state.settings[accountPeerId] ?? fallbackSettings
            let blockedPeerIds = state.blockedPeerIds[accountPeerId] ?? []
            if let engine = state.engines[accountPeerId],
               engine.settings == settings,
               engine.blockedPeerIds == blockedPeerIds {
                return state
            }
            state.engines[accountPeerId] = GRVMMessageFilterEngine(
                accountPeerId: accountPeerId,
                settings: settings,
                blockedPeerIds: blockedPeerIds
            )
            didReplaceEngine = true
            return state
        }
        if didReplaceEngine {
            self.advanceMessageFilterStateRevision(accountPeerId: accountPeerId)
            self.refreshFilteredUnread(accountPeerId: accountPeerId)
        }
        return state.engines[accountPeerId]
    }

    private func messageFilterStateUpdates(accountPeerId: PeerId) -> Signal<Int64, NoError> {
        // Materialize the account's immutable filter snapshot before exposing
        // the initial revision. This keeps the first consumer refresh tied to
        // an actual engine build instead of a synthetic zero revision.
        _ = self.filterEngine(accountPeerId: accountPeerId)
        let state = self.filterRuntimeState.modify { state in
            var state = state
            if state.revisionUpdates[accountPeerId] == nil {
                state.revisionUpdates[accountPeerId] = GRVMMessageFilterStateUpdates(
                    revision: state.revisions[accountPeerId] ?? 0
                )
            }
            return state
        }
        return state.revisionUpdates[accountPeerId]?.signal() ?? .single(0)
    }

    private func advanceMessageFilterStateRevision(accountPeerId: PeerId) {
        let state = self.filterRuntimeState.modify { state in
            var state = state
            let revision = (state.revisions[accountPeerId] ?? 0) + 1
            state.revisions[accountPeerId] = revision
            if state.revisionUpdates[accountPeerId] == nil {
                state.revisionUpdates[accountPeerId] = GRVMMessageFilterStateUpdates(revision: revision)
            }
            return state
        }
        guard let revision = state.revisions[accountPeerId],
              let updates = state.revisionUpdates[accountPeerId] else {
            return
        }
        updates.publish(revision: revision)
    }

    public func wireHooks() {
        installGRVMChatAppearanceHooks(registry: self.registry)

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
        AyuGramHooks.prepareConsumableMedia = { [weak self] accountPeerId, message in
            guard let service = self?.registry.service(accountPeerId: accountPeerId) else {
                return .single(false)
            }
            return service.prepareConsumableMedia(message)
        }
        AyuGramHooks.restoreConsumableMedia = { [weak self] accountPeerId, message in
            guard let service = self?.registry.service(accountPeerId: accountPeerId) else {
                return .single(false)
            }
            return service.restoreArchivedMedia(for: message)
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
        AyuGramFeatures.removeDeletedMessage = { [weak self] accountPeerId, key in
            guard let service = self?.registry.service(accountPeerId: accountPeerId) else {
                return .fail(.archiveUnavailable)
            }
            return service.removeDeletedMessage(key)
        }
        AyuGramFeatures.purgeDeletedMessage = { [weak self] accountPeerId, message in
            guard let service = self?.registry.service(accountPeerId: accountPeerId) else {
                return .fail(.archiveUnavailable)
            }
            return service.purgeDeletedMessage(message)
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
            return settings.suppressReadReceipts
        }
        AyuGramHooks.shouldSuppressPresence = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.suppressOnlineStatus
        }
        let shouldSuppressTypingAndUploads: (PeerId) -> Bool = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.suppressTypingAndUploads
        }
        AyuGramHooks.shouldSuppressTyping = shouldSuppressTypingAndUploads
        AyuGramHooks.shouldSuppressUploadProgress = shouldSuppressTypingAndUploads
        AyuGramHooks.shouldSuppressStoryRead = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.suppressStoryReads
        }
        AyuGramHooks.shouldSuppressContentRead = { [weak self] accountPeerId in
            guard let settings = self?.settings(accountPeerId: accountPeerId) else { return false }
            return settings.suppressReadReceipts
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
        AyuGramHooks.translationProvider = { [weak self] accountPeerId in
            guard let rawValue = self?.settings(accountPeerId: accountPeerId)?.translationProvider,
                  let provider = GRVMTranslationProvider(rawValue: rawValue) else {
                return .telegram
            }
            return provider
        }
        AyuGramHooks.shouldHideStories = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.hideStories ?? false
        }
        AyuGramHooks.shouldDisableSimilarChannels = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.disableSimilarChannels ?? false
        }
        AyuGramHooks.similarChannelsDisabled = { [weak self] accountPeerId in
            guard let self else {
                return .single(false)
            }
            return self.registry.similarChannelsDisabled(accountPeerId: accountPeerId)
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
        AyuGramHooks.shouldDisableExternalLinkWarning = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.disableExternalLinkWarning ?? false
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

        // MARK: - W0 Reanimation & 6.7.8
        AyuGramHooks.shouldSaveForBots = { [weak self] in self?.currentSettings.saveForBots ?? false }
        AyuGramHooks.codeFontName = { [weak self] in self?.currentSettings.codeFontName ?? "" }
        AyuGramHooks.shouldShowChannelReactions = { [weak self] in self?.currentSettings.showChannelReactions ?? true }
        AyuGramHooks.shouldShowGroupReactions = { [weak self] in self?.currentSettings.showGroupReactions ?? true }
        AyuGramHooks.recentStickersLimit = { [weak self] in self?.currentSettings.recentStickersCount ?? 20 }

        AyuGramHooks.shouldSuggestGhostForStories = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.suggestGhostForStories ?? false
        }
        AyuGramHooks.shouldFilterZalgo = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.filterZalgo ?? false
        }
        AyuGramHooks.shouldImproveLinkPreviews = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.improveLinkPreviews ?? false
        }
        AyuGramHooks.shouldHidePremiumStatuses = { [weak self] in self?.currentSettings.hidePremiumStatuses ?? false }
        AyuGramHooks.peerIdDisplayMode = { [weak self] accountPeerId in
            return self?.settings(accountPeerId: accountPeerId)?.showDialogId ?? 0
        }
        AyuGramHooks.sendWithoutSoundMode = { [weak self] accountPeerId in
            guard let self, let settings = self.settings(accountPeerId: accountPeerId) else { return 0 }
            switch settings.sendWithoutSoundMode {
            case 2:
                return 2
            case 1:
                return self.isGhostActive(settings) ? 1 : 0
            default:
                return 0
            }
        }

        // MARK: - Filters (W4)
        AyuGramHooks.isShadowBanned = { [weak self] accountPeerId, peerId in
            return self?.filterEngine(accountPeerId: accountPeerId)?.isShadowBanned(peerId) ?? false
        }
        AyuGramHooks.isMessageHiddenByFilter = { [weak self] accountPeerId, message in
            guard let self,
                  let engine = self.filterEngine(accountPeerId: accountPeerId),
                  !self.filteredMessageVisibility.isShowing(
                    accountPeerId: accountPeerId,
                    chatPeerId: message.id.peerId
                  ) else {
                return false
            }
            return engine.isMessageHidden(message)
        }
        AyuGramHooks.matchingMessageFilterIds = { [weak self] accountPeerId, message in
            return self?.filterEngine(accountPeerId: accountPeerId)?.matchingFilterIds(for: message) ?? []
        }
        AyuGramHooks.isShowingFilteredMessages = { [weak self] accountPeerId, chatPeerId in
            guard let self,
                  self.registry.service(accountPeerId: accountPeerId) != nil else {
                return false
            }
            return self.filteredMessageVisibility.isShowing(
                accountPeerId: accountPeerId,
                chatPeerId: chatPeerId
            )
        }
        AyuGramHooks.setShowingFilteredMessages = { [weak self] accountPeerId, chatPeerId, value in
            guard let self,
                  self.registry.service(accountPeerId: accountPeerId) != nil else {
                return
            }
            let previousValue = self.filteredMessageVisibility.isShowing(
                accountPeerId: accountPeerId,
                chatPeerId: chatPeerId
            )
            self.filteredMessageVisibility.setShowing(
                accountPeerId: accountPeerId,
                chatPeerId: chatPeerId,
                value: value
            )
            if previousValue != value {
                self.advanceMessageFilterStateRevision(accountPeerId: accountPeerId)
                self.refreshFilteredUnread(accountPeerId: accountPeerId)
            }
        }
        AyuGramHooks.messageFilterStateUpdates = { [weak self] accountPeerId in
            guard let self else {
                return .single(0)
            }
            return self.messageFilterStateUpdates(accountPeerId: accountPeerId)
        }
        AyuGramHooks.adjustedUnreadPeerReadState = { [weak self] accountPeerId, peerId, state in
            return self?.filteredUnreadCoordinator(accountPeerId: accountPeerId)?.adjustedPeerReadState(
                peerId: peerId,
                state: state
            ) ?? state
        }
        AyuGramHooks.adjustedUnreadThreadCount = { [weak self] accountPeerId, peerId, threadId, rawCount in
            return self?.filteredUnreadCoordinator(accountPeerId: accountPeerId)?.adjustedThreadUnreadCount(
                peerId: peerId,
                threadId: threadId,
                rawCount: rawCount
            ) ?? rawCount
        }
        AyuGramHooks.adjustedTotalUnreadState = { [weak self] accountPeerId, groupId, state in
            return self?.filteredUnreadCoordinator(accountPeerId: accountPeerId)?.adjustedTotalUnreadState(
                groupId: groupId,
                state: state
            ) ?? state
        }
        AyuGramHooks.filteredUnreadStateUpdates = { [weak self] accountPeerId in
            return self?.filteredUnreadCoordinator(accountPeerId: accountPeerId)?.updates() ?? .single(0)
        }
    }
}
