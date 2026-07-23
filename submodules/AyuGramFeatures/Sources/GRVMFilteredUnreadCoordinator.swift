import SwiftSignalKit
import Postbox
import TelegramCore

/// Maintains a bounded, account-local snapshot used only by presentation code.
/// The stock Postbox read state is never changed by this coordinator.
public final class GRVMFilteredUnreadCoordinator {
    private struct ThreadSnapshot {
        let rawCount: Int32
        let hiddenCount: Int32
        let markedUnread: Bool
        let isMuted: Bool
        let scanResult: LocalUnreadMessageScanResult

        var adjustedCount: Int32 {
            return max(0, self.rawCount - self.hiddenCount)
        }

        var rawUnread: Bool {
            return self.rawCount > 0 || self.markedUnread
        }

        var adjustedUnread: Bool {
            return self.adjustedCount > 0 || self.markedUnread
        }
    }

    private struct PeerMetadata {
        let tags: PeerSummaryCounterTags
        let isMuted: Bool
        let groupId: PeerGroupId?
    }

    private struct PeerSnapshot {
        let rawState: CombinedPeerReadState?
        let hiddenByNamespace: [MessageId.Namespace: Int32]
        let scanResultsByNamespace: [MessageId.Namespace: LocalUnreadMessageScanResult]
        let hasIncompleteScan: Bool
        let threadSnapshots: [Int64: ThreadSnapshot]
        let hasIncompleteThreadScan: Bool
        let isThreadBased: Bool
        let metadata: PeerMetadata

        var threadAggregateRawCount: Int32 {
            return Int32(clamping: self.threadSnapshots.values.reduce(0) { partial, thread in
                partial + (thread.rawUnread ? 1 : 0)
            })
        }

        var threadAggregateAdjustedCount: Int32 {
            return Int32(clamping: self.threadSnapshots.values.reduce(0) { partial, thread in
                partial + (thread.adjustedUnread ? 1 : 0)
            })
        }

        var threadAggregateRawPresence: Int32 {
            return self.threadSnapshots.values.contains(where: { $0.rawUnread }) ? 1 : 0
        }

        var threadAggregateAdjustedPresence: Int32 {
            return self.threadSnapshots.values.contains(where: { $0.adjustedUnread }) ? 1 : 0
        }

        var threadAggregateRawFilteredPresence: Int32 {
            return self.threadSnapshots.values.contains(where: { $0.rawUnread && !$0.isMuted }) ? 1 : 0
        }

        var threadAggregateAdjustedFilteredPresence: Int32 {
            return self.threadSnapshots.values.contains(where: { $0.adjustedUnread && !$0.isMuted }) ? 1 : 0
        }

        var threadAggregateKnownHiddenMessageCount: Int32 {
            return Int32(clamping: self.threadSnapshots.values.reduce(0) { partial, thread in
                partial + Int(thread.hiddenCount)
            })
        }

        var threadAggregateKnownHiddenChatCount: Int32 {
            return Int32(clamping: self.threadSnapshots.values.reduce(0) { partial, thread in
                guard thread.scanResult.isComplete, !thread.markedUnread, thread.rawUnread, !thread.adjustedUnread else {
                    return partial
                }
                return partial + 1
            })
        }
    }

    private struct Snapshot {
        var enabled = false
        var revision: Int64 = 0
        var peers: [PeerId: PeerSnapshot] = [:]
    }

    private let accountPeerId: PeerId
    private let postbox: Postbox
    private let queue = Queue(name: "GRVMFilteredUnreadCoordinator", qos: .utility)
    private let state = Atomic<Snapshot>(value: Snapshot())
    private let updatesPromise = ValuePromise<Int64>(0, ignoreRepeated: true)
    private let disposables = DisposableSet()

    private var predicate: ((Message) -> Bool)?
    private var generation: Int64 = 0
    private var nextScanToken: Int64 = 0
    private var scanTokens: [PeerId: Int64] = [:]
    private var materializedPeerIds = Set<PeerId>()

    public init(accountPeerId: PeerId, postbox: Postbox) {
        self.accountPeerId = accountPeerId
        self.postbox = postbox
    }

    deinit {
        self.disposables.dispose()
    }

    public func start() {
        self.disposables.add(self.postbox.localUnreadMessagePeerIdsUpdates().start(next: { [weak self] peerIds in
            self?.enqueue(peerIds: peerIds)
        }))
    }

    public func stop() {
        self.disposables.dispose()
        self.queue.async { [weak self] in
            guard let self else {
                return
            }
            self.generation &+= 1
            self.predicate = nil
            self.materializedPeerIds.removeAll()
            _ = self.state.modify { _ in Snapshot() }
            self.publish()
        }
    }

    public func setFilter(enabled: Bool, predicate: ((Message) -> Bool)?) {
        self.queue.async { [weak self] in
            guard let self else {
                return
            }
            self.generation &+= 1
            self.predicate = predicate
            self.materializedPeerIds.removeAll()
            _ = self.state.modify { state in
                var state = state
                state.enabled = enabled
                state.peers.removeAll()
                return state
            }
            self.publish()
            guard enabled else {
                return
            }
            self.materializeInitialPeers()
        }
    }

    public func rescanMaterializedPeers() {
        self.queue.async { [weak self] in
            guard let self, self.state.with({ $0.enabled }) else {
                return
            }
            self.generation &+= 1
            let peerIds = self.materializedPeerIds
            for peerId in peerIds {
                self.scheduleScan(peerId: peerId)
            }
        }
    }

    public func updates() -> Signal<Int64, NoError> {
        return self.updatesPromise.get()
    }

    public func adjustedPeerReadState(peerId: PeerId, state: CombinedPeerReadState) -> CombinedPeerReadState {
        let snapshot = self.state.with { $0 }
        guard snapshot.enabled, let peer = snapshot.peers[peerId] else {
            return state
        }
        if peer.isThreadBased {
            // Forum/reply peers expose an effective presence count rather than
            // a peer message count. Never apply the regular namespace delta to
            // that synthetic state, especially when the bounded thread scan
            // has holes or omitted topics.
            return Self.adjustedThreadAggregateReadState(state, peer: peer) ?? state
        }
        return Self.adjustedPeerReadState(state, hiddenByNamespace: peer.hiddenByNamespace)
    }

    public func adjustedThreadUnreadCount(peerId: PeerId, threadId: Int64, rawCount: Int32) -> Int32 {
        let snapshot = self.state.with { $0 }
        guard snapshot.enabled,
              let peer = snapshot.peers[peerId],
              let thread = peer.threadSnapshots[threadId] else {
            return rawCount
        }
        return max(0, rawCount - thread.hiddenCount)
    }

    public func adjustedTotalUnreadState(groupId: PeerGroupId, state: ChatListTotalUnreadState) -> ChatListTotalUnreadState {
        let snapshot = self.state.with { $0 }
        guard snapshot.enabled else {
            return state
        }

        var result = state
        for peer in snapshot.peers.values {
            guard peer.metadata.groupId == groupId else {
                continue
            }
            let absoluteMessageDelta: Int32
            let absoluteChatDelta: Int32
            let filteredMessageDelta: Int32
            let filteredChatDelta: Int32
            if peer.isThreadBased {
                guard !peer.hasIncompleteThreadScan, !peer.threadSnapshots.isEmpty else {
                    // Unknown or omitted topics remain visible in aggregate
                    // counters; only a complete snapshot may produce a delta.
                    continue
                }
                // Thread-based Postbox totals represent one presence/message
                // per peer, while the handleThreads view represents topic
                // count. Subtract only locally known hidden topics/messages.
                absoluteMessageDelta = max(0, peer.threadAggregateRawPresence - peer.threadAggregateAdjustedPresence)
                absoluteChatDelta = absoluteMessageDelta
                filteredMessageDelta = max(0, peer.threadAggregateRawFilteredPresence - peer.threadAggregateAdjustedFilteredPresence)
                filteredChatDelta = filteredMessageDelta
            } else if let rawState = peer.rawState {
                let adjustedState = Self.adjustedPeerReadState(rawState, hiddenByNamespace: peer.hiddenByNamespace)
                let rawMessageCount = max(rawState.count, rawState.markedUnread ? 1 : 0)
                let adjustedMessageCount = max(adjustedState.count, adjustedState.markedUnread ? 1 : 0)
                absoluteMessageDelta = max(0, rawMessageCount - adjustedMessageCount)
                absoluteChatDelta = rawState.isUnread && !adjustedState.isUnread ? 1 : 0
                if !peer.metadata.isMuted {
                    filteredMessageDelta = absoluteMessageDelta
                    filteredChatDelta = absoluteChatDelta
                } else {
                    filteredMessageDelta = 0
                    filteredChatDelta = 0
                }
            } else {
                continue
            }
            guard absoluteMessageDelta != 0 || absoluteChatDelta != 0 || filteredMessageDelta != 0 || filteredChatDelta != 0 else {
                continue
            }

            for tag in peer.metadata.tags {
                if var counters = result.absoluteCounters[tag] {
                    counters.messageCount = max(0, counters.messageCount - absoluteMessageDelta)
                    counters.chatCount = max(0, counters.chatCount - absoluteChatDelta)
                    result.absoluteCounters[tag] = counters
                }
                if var counters = result.filteredCounters[tag] {
                    counters.messageCount = max(0, counters.messageCount - filteredMessageDelta)
                    counters.chatCount = max(0, counters.chatCount - filteredChatDelta)
                    result.filteredCounters[tag] = counters
                }
            }
        }
        return result
    }

    private static func adjustedPeerReadState(
        _ state: CombinedPeerReadState,
        hiddenByNamespace: [MessageId.Namespace: Int32]
    ) -> CombinedPeerReadState {
        let adjustedStates = state.states.map { namespace, readState -> (MessageId.Namespace, PeerReadState) in
            let hidden = max(0, hiddenByNamespace[namespace] ?? 0)
            let adjustedCount = max(0, readState.count - hidden)
            switch readState {
            case let .idBased(maxIncomingReadId, maxOutgoingReadId, maxKnownId, _, markedUnread):
                return (
                    namespace,
                    .idBased(
                        maxIncomingReadId: maxIncomingReadId,
                        maxOutgoingReadId: maxOutgoingReadId,
                        maxKnownId: maxKnownId,
                        count: adjustedCount,
                        markedUnread: markedUnread
                    )
                )
            case let .indexBased(maxIncomingReadIndex, maxOutgoingReadIndex, _, markedUnread):
                return (
                    namespace,
                    .indexBased(
                        maxIncomingReadIndex: maxIncomingReadIndex,
                        maxOutgoingReadIndex: maxOutgoingReadIndex,
                        count: adjustedCount,
                        markedUnread: markedUnread
                    )
                )
            }
        }
        return CombinedPeerReadState(states: adjustedStates)
    }

    private static func adjustedThreadAggregateReadState(
        _ state: CombinedPeerReadState,
        peer: PeerSnapshot
    ) -> CombinedPeerReadState? {
        guard !peer.hasIncompleteThreadScan else {
            return nil
        }
        guard state.states.count == 1,
              let (namespace, readState) = state.states.first,
              case let .idBased(maxIncomingReadId, maxOutgoingReadId, maxKnownId, count, markedUnread) = readState,
              maxOutgoingReadId <= 1,
              maxIncomingReadId <= 1,
              maxKnownId <= 1 else {
            return nil
        }

        let adjustedCount: Int32
        if count == peer.threadAggregateRawCount {
            adjustedCount = peer.threadAggregateAdjustedCount
        } else if count == peer.threadAggregateRawPresence {
            adjustedCount = peer.threadAggregateAdjustedPresence
        } else {
            return nil
        }
        return CombinedPeerReadState(states: [(
            namespace,
            .idBased(
                maxIncomingReadId: maxIncomingReadId,
                maxOutgoingReadId: maxOutgoingReadId,
                maxKnownId: maxKnownId,
                count: adjustedCount,
                markedUnread: markedUnread
            )
        )])
    }

    private func enqueue(peerIds: Set<PeerId>) {
        self.queue.async { [weak self] in
            guard let self, self.state.with({ $0.enabled }) else {
                return
            }
            for peerId in peerIds {
                self.scheduleScan(peerId: peerId)
            }
        }
    }

    private func materializeInitialPeers() {
        let generation = self.generation
        let _ = self.postbox.transaction { transaction -> Set<PeerId> in
            var peerIds = transaction.getUnreadChatListPeerIds(
                groupId: .root,
                filterPredicate: nil,
                additionalFilter: nil,
                stopOnFirstMatch: false
            )
            peerIds.append(contentsOf: transaction.chatListGetAllPeerIds(groupId: Namespaces.PeerGroup.archive))
            return Set(peerIds.prefix(256))
        }.start(next: { [weak self] peerIds in
            self?.queue.async { [weak self] in
                guard let self, generation == self.generation, self.state.with({ $0.enabled }) else {
                    return
                }
                for peerId in peerIds {
                    self.materializedPeerIds.insert(peerId)
                    self.scheduleScan(peerId: peerId)
                }
            }
        })
    }

    private func scheduleScan(peerId: PeerId) {
        guard self.state.with({ $0.enabled }) else {
            return
        }
        self.nextScanToken &+= 1
        let token = self.nextScanToken
        self.scanTokens[peerId] = token
        let generation = self.generation
        let predicate = self.predicate
        let postbox = self.postbox
        let accountPeerId = self.accountPeerId

        let _ = postbox.transaction { transaction -> PeerSnapshot? in
            guard let peer = transaction.getPeer(peerId) else {
                return nil
            }

            let rawState = transaction.getCombinedPeerReadState(peerId)

            let isContact = transaction.isPeerContact(peerId: peerId)
            let notificationPeerId: PeerId
            if let associatedPeerId = peer.associatedPeerId, peer.associatedPeerOverridesIdentity {
                notificationPeerId = associatedPeerId
            } else {
                notificationPeerId = peerId
            }
            let metadata = PeerMetadata(
                tags: postbox.seedConfiguration.peerSummaryCounterTags(peer, isContact),
                isMuted: resolvedIsRemovedFromTotalUnreadCount(
                    globalSettings: transaction.getGlobalNotificationSettings(),
                    peer: peer,
                    peerSettings: transaction.getPeerNotificationSettings(id: notificationPeerId)
                ),
                groupId: transaction.getPeerChatListInclusion(peerId).groupId
            )
            let isThreadBased = postbox.seedConfiguration.peerSummaryIsThreadBased(
                peer,
                peer.associatedPeerId.flatMap { transaction.getPeer($0) }
            ).value

            var hiddenByNamespace: [MessageId.Namespace: Int32] = [:]
            var scanResultsByNamespace: [MessageId.Namespace: LocalUnreadMessageScanResult] = [:]
            if let rawState {
                for (namespace, readState) in rawState.states {
                    var hidden: Int32 = 0
                    let result = transaction.scanLocalUnreadMessages(peerId: peerId, namespace: namespace, state: readState) { message in
                        guard message.effectivelyIncoming(accountPeerId), predicate?(message) == true else {
                            return
                        }
                        hidden = hidden == Int32.max ? hidden : hidden + 1
                    }
                    scanResultsByNamespace[namespace] = result
                    if hidden != 0 {
                        hiddenByNamespace[namespace] = hidden
                    }
                }
            }

            var threadSnapshots: [Int64: ThreadSnapshot] = [:]
            var hasIncompleteThreadScan = false
            let threadEntries = transaction.getMessageHistoryThreadIndex(peerId: peerId, limit: 257)
            if threadEntries.count > 256 {
                hasIncompleteThreadScan = true
            }
            for entry in threadEntries.prefix(256) {
                guard let data = entry.info.data.get(MessageHistoryThreadData.self) else {
                    hasIncompleteThreadScan = true
                    continue
                }
                let rawCount = max(0, data.incomingUnreadCount)
                var hidden: Int32 = 0
                let result = transaction.scanLocalUnreadThreadMessages(
                    peerId: peerId,
                    threadId: entry.threadId,
                    namespace: Namespaces.Message.Cloud,
                    maxIncomingReadId: data.maxIncomingReadId,
                    maxKnownMessageId: data.maxKnownMessageId,
                    expectedUnreadCount: rawCount
                ) { message in
                    guard message.effectivelyIncoming(accountPeerId), predicate?(message) == true else {
                        return
                    }
                    hidden = hidden == Int32.max ? hidden : hidden + 1
                }
                let isMuted: Bool
                switch data.notificationSettings.muteState {
                case .muted:
                    isMuted = true
                case .unmuted:
                    isMuted = false
                case .default:
                    isMuted = metadata.isMuted
                }
                if result.hasHoles || !result.isComplete {
                    hasIncompleteThreadScan = true
                }
                if rawCount != 0 || data.isMarkedUnread || hidden != 0 {
                    threadSnapshots[entry.threadId] = ThreadSnapshot(
                        rawCount: rawCount,
                        hiddenCount: hidden,
                        markedUnread: data.isMarkedUnread,
                        isMuted: isMuted,
                        scanResult: result
                    )
                }
            }
            // A hole or a count mismatch leaves the unknown portion untouched;
            // only locally enumerated hidden messages enter hiddenByNamespace.
            let hasIncompleteScan = scanResultsByNamespace.values.contains { result in
                result.hasHoles || !result.isComplete
            }
            return PeerSnapshot(
                rawState: rawState,
                hiddenByNamespace: hiddenByNamespace,
                scanResultsByNamespace: scanResultsByNamespace,
                hasIncompleteScan: hasIncompleteScan,
                threadSnapshots: threadSnapshots,
                hasIncompleteThreadScan: hasIncompleteThreadScan,
                isThreadBased: isThreadBased,
                metadata: metadata
            )
        }.start(next: { [weak self] peerSnapshot in
            self?.queue.async { [weak self] in
                guard let self,
                      generation == self.generation,
                      token == self.scanTokens[peerId],
                      self.state.with({ $0.enabled }) else {
                    return
                }
                self.materializedPeerIds.insert(peerId)
                _ = self.state.modify { state in
                    var state = state
                    if let peerSnapshot {
                        state.peers[peerId] = peerSnapshot
                    } else {
                        state.peers.removeValue(forKey: peerId)
                    }
                    return state
                }
                self.publish()
            }
        })
    }

    private func publish() {
        let revision = self.state.modify { state -> Snapshot in
            var state = state
            state.revision &+= 1
            return state
        }.revision
        self.updatesPromise.set(revision)
    }
}
