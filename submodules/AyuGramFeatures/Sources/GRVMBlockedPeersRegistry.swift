import Postbox
import SwiftSignalKit
import TelegramCore

public final class GRVMBlockedPeersRegistry {
    private final class Entry {
        let account: Account
        let context: BlockedPeersContext
        let disposable = MetaDisposable()

        init(account: Account, context: BlockedPeersContext) {
            self.account = account
            self.context = context
        }
    }

    private var entries: [PeerId: Entry] = [:]
    private let updated: (PeerId, Set<PeerId>) -> Void

    public init(updated: @escaping (PeerId, Set<PeerId>) -> Void) {
        self.updated = updated
    }

    deinit {
        for entry in self.entries.values {
            entry.disposable.dispose()
        }
    }

    public func updateAccounts(_ accounts: [Account]) {
        assert(Queue.mainQueue().isCurrent())
        let activeAccountPeerIds = Set(accounts.map(\.peerId))
        for accountPeerId in Array(self.entries.keys) where !activeAccountPeerIds.contains(accountPeerId) {
            self.unregister(accountPeerId: accountPeerId)
        }
        for account in accounts {
            self.register(account: account)
        }
    }

    private func register(account: Account) {
        let accountPeerId = account.peerId
        if let existing = self.entries[accountPeerId], existing.account === account {
            return
        }
        self.unregister(accountPeerId: accountPeerId)

        let context = BlockedPeersContext(account: account, subject: .blocked)
        let entry = Entry(account: account, context: context)
        self.entries[accountPeerId] = entry
        entry.disposable.set(context.state.start(next: { [weak self, weak context] state in
            guard let self,
                  let context,
                  self.entries[accountPeerId]?.context === context else {
                return
            }
            self.updated(accountPeerId, Set(state.peers.map(\.peerId)))
            if !state.isLoadingMore && state.canLoadMore {
                context.loadMore()
            }
        }))
    }

    private func unregister(accountPeerId: PeerId) {
        guard let entry = self.entries.removeValue(forKey: accountPeerId) else {
            return
        }
        entry.disposable.dispose()
        self.updated(accountPeerId, [])
    }
}
