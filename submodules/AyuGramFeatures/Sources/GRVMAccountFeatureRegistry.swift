import Foundation
import SwiftSignalKit
import Postbox
import TelegramCore
import AyuGramLib

public final class GRVMAccountFeatureRegistry {
    private struct RuntimeState {
        var prepared = false
        var primaryAccountPeerId: PeerId?
        var services: [PeerId: GRVMMessageArchiveCoordinator] = [:]
        var settingsDisposables: [PeerId: Disposable] = [:]
    }

    private let lifecycleQueue = Queue(name: "GRVMAccountFeatureRegistry")
    private let state = Atomic<RuntimeState>(value: RuntimeState())
    private let store: GRVMMessageArchiveStore
    private let mediaStore: GRVMArchivedMediaStore
    private let accountManager: AccountManager<TelegramAccountManagerTypes>

    public init(
        databaseURL: URL,
        mediaRootURL: URL,
        accountManager: AccountManager<TelegramAccountManagerTypes>
    ) {
        self.store = GRVMMessageArchiveStore(databaseURL: databaseURL)
        self.mediaStore = GRVMArchivedMediaStore(rootURL: mediaRootURL)
        self.accountManager = accountManager
    }

    deinit {
        var services: [GRVMMessageArchiveCoordinator] = []
        var disposables: [Disposable] = []
        _ = self.state.modify { state in
            var state = state
            services = Array(state.services.values)
            disposables = Array(state.settingsDisposables.values)
            state.settingsDisposables.removeAll()
            state.services.removeAll()
            return state
        }
        var waiters: [Subscriber<[MessageId], GRVMClearDeletedError>] = []
        for service in services {
            waiters.append(contentsOf: service.shutdownForReplacement())
        }
        for disposable in disposables {
            disposable.dispose()
        }
        Self.deliverShutdownErrors(waiters)
    }

    public func prepare(activeAccountRecordIds: [Int64]) throws {
        if self.state.with({ $0.prepared }) {
            return
        }
        try self.store.migrate(activeAccountRecordIds: activeAccountRecordIds)
        _ = self.state.modify { state in
            var state = state
            state.prepared = true
            return state
        }
    }

    public func register(
        accountPeerId: PeerId,
        accountRecordId: AccountRecordId,
        postbox: Postbox,
        mediaBox: MediaBox,
        initialSettings: AyuGramSettings
    ) {
        var shutdownWaiters: [Subscriber<[MessageId], GRVMClearDeletedError>] = []
        self.lifecycleQueue.sync {
            shutdownWaiters = self.registerOnQueue(
                accountPeerId: accountPeerId,
                accountRecordId: accountRecordId,
                postbox: postbox,
                mediaBox: mediaBox,
                initialSettings: initialSettings
            )
        }
        Self.deliverShutdownErrors(shutdownWaiters)
    }

    private func registerOnQueue(
        accountPeerId: PeerId,
        accountRecordId: AccountRecordId,
        postbox: Postbox,
        mediaBox: MediaBox,
        initialSettings: AyuGramSettings
    ) -> [Subscriber<[MessageId], GRVMClearDeletedError>] {
        let existingService = self.state.with { state -> GRVMMessageArchiveCoordinator? in
            guard state.prepared else {
                return nil
            }
            if let service = state.services[accountPeerId],
               service.isBound(to: accountRecordId, postbox: postbox, mediaBox: mediaBox) {
                return service
            }
            return nil
        }
        if let service = existingService {
            service.updateSettings(initialSettings)
            self.publishPrimaryAppearance()
            return []
        }
        guard self.state.with({ $0.prepared }) else {
            return []
        }

        let removal = self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: false)
        guard removal.removed else {
            return removal.waiters
        }

        let coordinator = GRVMMessageArchiveCoordinator(
            accountPeerId: accountPeerId,
            accountRecordId: accountRecordId,
            postbox: postbox,
            mediaBox: mediaBox,
            store: self.store,
            mediaStore: self.mediaStore,
            settings: initialSettings
        )
        do {
            try coordinator.prepare()
        } catch {
            return removal.waiters
        }

        let settingsDisposable = MetaDisposable()
        _ = self.state.modify { state in
            var state = state
            guard state.prepared,
                  state.services[accountPeerId] == nil,
                  state.settingsDisposables[accountPeerId] == nil else {
                return state
            }
            state.services[accountPeerId] = coordinator
            state.settingsDisposables[accountPeerId] = settingsDisposable
            return state
        }
        guard self.state.with({ state in
            state.settingsDisposables[accountPeerId] === settingsDisposable
                && state.services[accountPeerId] === coordinator
        }) else {
            return removal.waiters
        }
        coordinator.resumePendingCleanupJobs()
        coordinator.reconcilePersistentMessageState()
        self.publishPrimaryAppearance()

        settingsDisposable.set(grvmSettings(accountId: accountPeerId, accountManager: self.accountManager).start(next: { [weak self] settings in
            guard let self else {
                return
            }
            self.lifecycleQueue.async { [weak self] in
                guard let self else {
                    return
                }
                guard self.state.with({ state in
                    state.settingsDisposables[accountPeerId] === settingsDisposable
                        && state.services[accountPeerId] === coordinator
                }) else {
                    return
                }
                coordinator.updateSettings(settings)
                self.publishPrimaryAppearance()
            }
        }))
        return removal.waiters
    }

    public func unregister(accountPeerId: PeerId) {
        var shutdownWaiters: [Subscriber<[MessageId], GRVMClearDeletedError>] = []
        self.lifecycleQueue.sync {
            shutdownWaiters = self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: true).waiters
        }
        Self.deliverShutdownErrors(shutdownWaiters)
    }

    private func removeRegistration(
        accountPeerId: PeerId,
        clearPrimary: Bool
    ) -> (removed: Bool, waiters: [Subscriber<[MessageId], GRVMClearDeletedError>]) {
        let service = self.state.with { state in
            state.services[accountPeerId]
        }
        let settingsDisposable = self.state.with { state in
            state.settingsDisposables[accountPeerId]
        }
        let waiters = service?.shutdownForReplacement() ?? []

        var disposable: Disposable?
        var removed = false
        _ = self.state.modify { state in
            var state = state
            let serviceMatches: Bool
            if let service {
                serviceMatches = state.services[accountPeerId] === service
            } else {
                serviceMatches = state.services[accountPeerId] == nil
            }
            let disposableMatches: Bool
            if let settingsDisposable {
                disposableMatches = state.settingsDisposables[accountPeerId] === settingsDisposable
            } else {
                disposableMatches = state.settingsDisposables[accountPeerId] == nil
            }
            guard serviceMatches, disposableMatches else {
                return state
            }
            disposable = state.settingsDisposables.removeValue(forKey: accountPeerId)
            state.services.removeValue(forKey: accountPeerId)
            if clearPrimary && state.primaryAccountPeerId == accountPeerId {
                state.primaryAccountPeerId = nil
            }
            removed = true
            return state
        }
        disposable?.dispose()
        return (removed, waiters)
    }

    private static func deliverShutdownErrors(
        _ waiters: [Subscriber<[MessageId], GRVMClearDeletedError>]
    ) {
        guard !waiters.isEmpty else {
            return
        }
        Queue.concurrentDefaultQueue().async {
            for subscriber in waiters {
                subscriber.putError(.archiveUnavailable)
            }
        }
    }

    public func setPrimaryAccount(_ accountPeerId: PeerId?) {
        _ = self.state.modify { state in
            var state = state
            state.primaryAccountPeerId = accountPeerId
            return state
        }
        self.publishPrimaryAppearance()
    }

    private func publishPrimaryAppearance() {
        publishGRVMPrimaryChatAppearance(
            self.primaryService()?.settingsSnapshot().grvmChatAppearanceSettings ?? .default
        )
    }

    public func service(accountPeerId: PeerId) -> GRVMMessageArchiveCoordinator? {
        return self.state.with { state in
            state.services[accountPeerId]
        }
    }

    public func primaryService() -> GRVMMessageArchiveCoordinator? {
        return self.state.with { state in
            guard let accountPeerId = state.primaryAccountPeerId else {
                return nil
            }
            return state.services[accountPeerId]
        }
    }

    public func ownPeerIds() -> Set<PeerId> {
        return self.state.with { state in
            Set(state.services.keys).union(state.settingsDisposables.keys)
        }
    }
}
