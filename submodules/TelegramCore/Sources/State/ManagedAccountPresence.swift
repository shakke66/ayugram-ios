import Foundation
import TelegramApi
import Postbox
import SwiftSignalKit
import MtProtoKit

private typealias SignalKitTimer = SwiftSignalKit.Timer


private final class AccountPresenceManagerImpl {
    private let queue: Queue
    private let accountPeerId: PeerId
    private let network: Network
    let isPerformingUpdate = ValuePromise<Bool>(false, ignoreRepeated: true)
    
    private var shouldKeepOnlinePresenceDisposable: Disposable?
    private let currentRequestDisposable = MetaDisposable()
    private var onlineTimer: SignalKitTimer?
    private var presenceUpdateId: Int = 0
    
    private var wasOnline: Bool = false
    
    init(queue: Queue, accountPeerId: PeerId, shouldKeepOnlinePresence: Signal<Bool, NoError>, network: Network) {
        self.queue = queue
        self.accountPeerId = accountPeerId
        self.network = network
        
        self.shouldKeepOnlinePresenceDisposable = (shouldKeepOnlinePresence
        |> distinctUntilChanged
        |> deliverOn(self.queue)).start(next: { [weak self] value in
            guard let `self` = self else {
                return
            }
            if self.wasOnline != value {
                self.wasOnline = value
                self.updatePresence(value)
            }
        })
    }
    
    deinit {
        assert(self.queue.isCurrent())
        self.shouldKeepOnlinePresenceDisposable?.dispose()
        self.currentRequestDisposable.dispose()
        self.onlineTimer?.invalidate()
    }
    
    private func updatePresence(_ isOnline: Bool) {
        if isOnline && AyuGramHooks.shouldSuppressPresence?(self.accountPeerId) == true {
            return
        }

        let request: Signal<Api.Bool, MTRpcError>
        if isOnline {
            let timer = SignalKitTimer(timeout: 30.0, repeat: false, completion: { [weak self] in
                guard let strongSelf = self else {
                    return
                }
                strongSelf.updatePresence(true)
            }, queue: self.queue)
            self.onlineTimer = timer
            timer.start()
            request = self.network.request(Api.functions.account.updateStatus(offline: .boolFalse))
        } else {
            self.onlineTimer?.invalidate()
            self.onlineTimer = nil
            request = self.network.request(Api.functions.account.updateStatus(offline: .boolTrue))
        }

        self.presenceUpdateId &+= 1
        let requestId = self.presenceUpdateId
        self.isPerformingUpdate.set(true)
        self.currentRequestDisposable.set((request
        |> ignoreValues
        |> map { _ -> Bool in
        }
        |> then(Signal<Bool, MTRpcError>.single(true))
        |> `catch` { _ -> Signal<Bool, NoError> in
            return .single(false)
        }
        |> deliverOn(self.queue)).start(next: { [weak self] requestSucceeded in
            guard let self = self else {
                return
            }
            guard requestId == self.presenceUpdateId else {
                return
            }
            if isOnline && requestSucceeded && AyuGramHooks.shouldForceOfflineAfterOnline?(self.accountPeerId) == true {
                self.onlineTimer?.invalidate()
                self.onlineTimer = nil
                self.updatePresence(false)
            } else {
                self.isPerformingUpdate.set(false)
            }
        }))
    }
}

final class AccountPresenceManager {
    private let queue = Queue()
    private let impl: QueueLocalObject<AccountPresenceManagerImpl>
    
    init(accountPeerId: PeerId, shouldKeepOnlinePresence: Signal<Bool, NoError>, network: Network) {
        let queue = self.queue
        self.impl = QueueLocalObject(queue: self.queue, generate: {
            return AccountPresenceManagerImpl(queue: queue, accountPeerId: accountPeerId, shouldKeepOnlinePresence: shouldKeepOnlinePresence, network: network)
        })
    }
    
    func isPerformingUpdate() -> Signal<Bool, NoError> {
        return Signal { subscriber in
            let disposable = MetaDisposable()
            self.impl.with { impl in
                disposable.set(impl.isPerformingUpdate.get().start(next: { value in
                    subscriber.putNext(value)
                }))
            }
            return disposable
        }
    }
}
