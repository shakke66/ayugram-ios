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
        var disposables: [Disposable] = []
        _ = self.state.modify { state in
            var state = state
            disposables = Array(state.settingsDisposables.values)
            state.settingsDisposables.removeAll()
            state.services.removeAll()
            return state
        }
        for disposable in disposables {
            disposable.dispose()
        }
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
        mediaBox: MediaBox
    ) {
        let canRegister = self.state.with { state -> Bool in
            guard state.prepared else {
                return false
            }
            if let service = state.services[accountPeerId],
               service.isBound(to: accountRecordId, postbox: postbox, mediaBox: mediaBox) {
                return false
            }
            return true
        }
        guard canRegister else {
            return
        }

        self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: false)
        let settingsDisposable = MetaDisposable()
        _ = self.state.modify { state in
            var state = state
            state.settingsDisposables[accountPeerId] = settingsDisposable
            return state
        }
        settingsDisposable.set(grvmSettings(accountId: accountPeerId, accountManager: self.accountManager).start(next: { [weak self] settings in
            guard let self else {
                return
            }
            if let service = self.service(accountPeerId: accountPeerId) {
                service.updateSettings(settings)
                return
            }

            let coordinator = GRVMMessageArchiveCoordinator(
                accountPeerId: accountPeerId,
                accountRecordId: accountRecordId,
                postbox: postbox,
                mediaBox: mediaBox,
                store: self.store,
                mediaStore: self.mediaStore,
                settings: settings
            )
            do {
                try coordinator.prepare()
            } catch {
                return
            }
            var registered = false
            _ = self.state.modify { state in
                var state = state
                guard state.prepared,
                      state.settingsDisposables[accountPeerId] === settingsDisposable,
                      state.services[accountPeerId] == nil else {
                    return state
                }
                state.services[accountPeerId] = coordinator
                registered = true
                return state
            }
            guard registered else {
                return
            }
            coordinator.resumePendingCleanupJobs()
            coordinator.reconcilePersistentMessageState()
        }))
    }

    public func unregister(accountPeerId: PeerId) {
        self.removeRegistration(accountPeerId: accountPeerId, clearPrimary: true)
    }

    private func removeRegistration(accountPeerId: PeerId, clearPrimary: Bool) {
        var disposable: Disposable?
        _ = self.state.modify { state in
            var state = state
            disposable = state.settingsDisposables.removeValue(forKey: accountPeerId)
            state.services.removeValue(forKey: accountPeerId)
            if clearPrimary && state.primaryAccountPeerId == accountPeerId {
                state.primaryAccountPeerId = nil
            }
            return state
        }
        disposable?.dispose()
    }

    public func setPrimaryAccount(_ accountPeerId: PeerId?) {
        _ = self.state.modify { state in
            var state = state
            state.primaryAccountPeerId = accountPeerId
            return state
        }
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
