import Foundation
import SwiftSignalKit
import Postbox
import TelegramCore
import AyuGramLib

private struct GRVMCoordinatorSettingsState {
    let settings: AyuGramSettings
    let filters: [NSRegularExpression]
    let reversedFilters: [NSRegularExpression]

    init(settings: AyuGramSettings) {
        self.settings = settings
        if settings.enableFilters {
            self.filters = settings.messageFilters.compactMap {
                try? NSRegularExpression(pattern: $0, options: [.caseInsensitive])
            }
            self.reversedFilters = settings.reversedFilters.compactMap {
                try? NSRegularExpression(pattern: $0, options: [.caseInsensitive])
            }
        } else {
            self.filters = []
            self.reversedFilters = []
        }
    }
}

private func grvmEntitiesData(_ message: Message) -> Data {
    guard let attribute = message.attributes.first(where: { $0 is TextEntitiesMessageAttribute }) else {
        return Data()
    }
    let encoder = PostboxEncoder()
    encoder.encodeRootObject(attribute)
    return encoder.makeData()
}

private func grvmMediaSummary(_ media: [Media]) -> String {
    return media.compactMap { item -> String? in
        if item is TelegramMediaImage {
            return "photo"
        } else if let file = item as? TelegramMediaFile {
            if file.isInstantVideo {
                return "video_message"
            } else if file.isVideo {
                return "video"
            } else if file.isVoice {
                return "voice"
            } else if file.isSticker {
                return file.isAnimatedSticker ? "animated_sticker" : "sticker"
            } else if file.isMusic {
                return "audio"
            } else {
                return "document:\(file.fileName ?? "unknown")"
            }
        } else if item is TelegramMediaContact {
            return "contact"
        } else if item is TelegramMediaMap {
            return "location"
        } else if item is TelegramMediaPoll {
            return "poll"
        } else {
            return nil
        }
    }.joined(separator: ",")
}

public final class GRVMMessageArchiveCoordinator {
    public let accountPeerId: PeerId
    public let accountRecordId: AccountRecordId

    private let postbox: Postbox
    private let mediaBox: MediaBox
    private let store: GRVMMessageArchiveStore
    private let mediaStore: GRVMArchivedMediaStore
    private let index = GRVMMessageArchiveIndex()
    private let queue = Queue(name: "GRVMMessageArchiveCoordinator", qos: .utility)
    private let disposables = DisposableSet()
    private let cleanupRunnerDisposable = MetaDisposable()
    private let settingsState: Atomic<GRVMCoordinatorSettingsState>
    private var isAcceptingOperations = true
    private var isCleanupExecutorRunning = false
    private var cleanupWaiters: [UUID: [UUID: Subscriber<[MessageId], GRVMClearDeletedError>]] = [:]
    private var cleanupWaiterJobs: [UUID: UUID] = [:]
    private var didStartArchivedMediaReconciliation = false

    public init(
        accountPeerId: PeerId,
        accountRecordId: AccountRecordId,
        postbox: Postbox,
        mediaBox: MediaBox,
        store: GRVMMessageArchiveStore,
        mediaStore: GRVMArchivedMediaStore,
        settings: AyuGramSettings
    ) {
        self.accountPeerId = accountPeerId
        self.accountRecordId = accountRecordId
        self.postbox = postbox
        self.mediaBox = mediaBox
        self.store = store
        self.mediaStore = mediaStore
        self.settingsState = Atomic(value: GRVMCoordinatorSettingsState(settings: settings))
    }

    deinit {
        self.cleanupRunnerDisposable.dispose()
        self.disposables.dispose()
    }

    func prepare() throws {
        let deleted = try store.deletedKeys(accountId: accountRecordId.int64)
        let revised = try store.revisedKeys(accountId: accountRecordId.int64)
        self.index.replace(GRVMMessageArchiveSnapshot(deleted: deleted, revised: revised))

        self.disposables.add(self.mediaBox.didRemoveResourceIds.start(next: { [weak self] ids in
            guard let self, !ids.isEmpty else {
                return
            }
            self.queue.async {
                let resourceIds = ids.map(\.stringRepresentation)
                guard let records = try? self.store.archivedMedia(
                    accountId: self.accountRecordId.int64,
                    resourceIds: resourceIds
                ) else {
                    return
                }
                self.restore(records.filter { $0.copyState == .complete })
            }
        }))
    }

    func shutdownForReplacement() {
        self.queue.sync {
            guard self.isAcceptingOperations else {
                return
            }
            self.isAcceptingOperations = false
            self.cleanupRunnerDisposable.dispose()
            self.isCleanupExecutorRunning = false
            let waiters = self.takeAllCleanupWaiters()
            for subscriber in waiters {
                subscriber.putError(.archiveUnavailable)
            }
        }
    }

    public func resumePendingCleanupJobs() {
        self.queue.async { [weak self] in
            guard let self else {
                return
            }
            guard self.isAcceptingOperations else {
                return
            }
            self.startCleanupExecutorIfNeeded()
        }
    }

    private func addCleanupWaiter(
        jobId: UUID,
        waiterId: UUID,
        subscriber: Subscriber<[MessageId], GRVMClearDeletedError>
    ) {
        self.cleanupWaiters[jobId, default: [:]][waiterId] = subscriber
        self.cleanupWaiterJobs[waiterId] = jobId
    }

    private func removeCleanupWaiter(_ waiterId: UUID) {
        guard let jobId = self.cleanupWaiterJobs.removeValue(forKey: waiterId) else {
            return
        }
        self.cleanupWaiters[jobId]?.removeValue(forKey: waiterId)
        if self.cleanupWaiters[jobId]?.isEmpty == true {
            self.cleanupWaiters.removeValue(forKey: jobId)
        }
    }

    private func takeCleanupWaiters(jobId: UUID) -> [Subscriber<[MessageId], GRVMClearDeletedError>] {
        guard let waiters = self.cleanupWaiters.removeValue(forKey: jobId) else {
            return []
        }
        for waiterId in waiters.keys {
            self.cleanupWaiterJobs.removeValue(forKey: waiterId)
        }
        return Array(waiters.values)
    }

    private func takeAllCleanupWaiters() -> [Subscriber<[MessageId], GRVMClearDeletedError>] {
        let waiters = self.cleanupWaiters.values.flatMap { $0.values }
        self.cleanupWaiters.removeAll()
        self.cleanupWaiterJobs.removeAll()
        return waiters
    }

    private func startCleanupExecutorIfNeeded() {
        guard self.isAcceptingOperations, !self.isCleanupExecutorRunning else {
            return
        }
        self.isCleanupExecutorRunning = true
        self.drainNextCleanupJob()
    }

    private func drainNextCleanupJob() {
        guard self.isAcceptingOperations else {
            self.isCleanupExecutorRunning = false
            return
        }
        let job: GRVMCleanupJob?
        do {
            job = try self.store.pendingCleanupJobs(accountId: self.accountRecordId.int64).first
        } catch {
            self.failCleanupExecutor(.databaseFinalizationFailed)
            return
        }
        guard let job else {
            self.isCleanupExecutorRunning = false
            self.reconcileArchivedMedia()
            return
        }

        let disposable = self.runCleanupJob(job).start(next: { [weak self] ids in
            guard let self else {
                return
            }
            self.queue.justDispatch {
                guard self.isAcceptingOperations else {
                    return
                }
                self.finishCleanupWaiters(jobId: job.id, ids: ids)
                self.drainNextCleanupJob()
            }
        }, error: { [weak self] error in
            guard let self else {
                return
            }
            self.queue.justDispatch {
                guard self.isAcceptingOperations else {
                    return
                }
                self.failCleanupExecutor(error)
            }
        })
        self.cleanupRunnerDisposable.set(disposable)
    }

    private func finishCleanupWaiters(jobId: UUID, ids: [MessageId]) {
        let waiters = self.takeCleanupWaiters(jobId: jobId)
        for subscriber in waiters {
            subscriber.putNext(ids)
            subscriber.putCompletion()
        }
    }

    private func failCleanupExecutor(_ error: GRVMClearDeletedError) {
        self.isCleanupExecutorRunning = false
        let waiters = self.takeAllCleanupWaiters()
        for subscriber in waiters {
            subscriber.putError(error)
        }
    }

    private func runCleanupJob(_ initialJob: GRVMCleanupJob) -> Signal<[MessageId], GRVMClearDeletedError> {
        return Signal { subscriber in
            let disposable = MetaDisposable()
            var job = initialJob
            if job.phase == .planned {
                do {
                    job = try self.store.revalidateDeletedCleanup(id: job.id)
                } catch {
                    subscriber.putError(.databaseFinalizationFailed)
                    return disposable
                }
                let removal = self.mediaStore.removeArchivedFiles(job.mediaRecords)
                guard removal.failed.isEmpty else {
                    subscriber.putError(.mediaRemovalFailed(removal.failed.count))
                    return disposable
                }
                do {
                    job = try self.store.markCleanupFilesRemoved(id: job.id)
                } catch {
                    subscriber.putError(.databaseFinalizationFailed)
                    return disposable
                }
            }

            let ids = job.messageKeys.map {
                MessageId(peerId: PeerId($0.peerId), namespace: $0.namespace, id: $0.messageId)
            }
            disposable.set(self.postbox.transaction { transaction -> [MessageId] in
                _internal_applyMessageDeletion(
                    accountPeerId: self.accountPeerId,
                    transaction: transaction,
                    mediaBox: self.mediaBox,
                    ids: ids,
                    mode: .forceCleanup
                )
                return ids
            }.start(next: { ids in
                self.queue.async {
                    guard self.isAcceptingOperations else {
                        return
                    }
                    do {
                        let keys = try self.store.finalizeDeletedCleanup(id: job.id)
                        self.index.removeDeleted(Set(keys))
                        subscriber.putNext(ids)
                        subscriber.putCompletion()
                    } catch {
                        subscriber.putError(.databaseFinalizationFailed)
                    }
                }
            }))
            return disposable
        }
    }

    private func reconcileArchivedMedia() {
        guard !self.didStartArchivedMediaReconciliation else {
            return
        }
        let records: [GRVMArchivedMedia]
        do {
            records = try self.store.archivedMedia(accountId: self.accountRecordId.int64)
        } catch {
            return
        }
        self.didStartArchivedMediaReconciliation = true
        self.disposables.add(self.mediaStore.reconcile(
            accountId: self.accountRecordId.int64,
            records: records,
            mediaBox: self.mediaBox
        ).start(next: { [weak self] updatedRecords in
            guard let self else {
                return
            }
            self.queue.async {
                do {
                    for record in updatedRecords {
                        try self.store.updateMedia(record)
                    }
                } catch {
                    return
                }
                let updatedIds = Set(updatedRecords.map(\.resourceId))
                self.restore(
                    records.filter {
                        $0.copyState == .complete && !updatedIds.contains($0.resourceId)
                    } + updatedRecords.filter { $0.copyState == .complete }
                )
            }
        }))
    }

    public func reconcilePersistentMessageState() {
        let snapshot = self.index.snapshot()
        let deletedKeys = Set(snapshot.deleted.filter { key in
            key.accountId == self.accountRecordId.int64
        })
        let revisedKeys = Set(snapshot.revised.filter { key in
            key.accountId == self.accountRecordId.int64
        })
        let keys = Array(deletedKeys.union(revisedKeys))
        let batchSize = 100

        for offset in stride(from: 0, to: keys.count, by: batchSize) {
            let batch = Array(keys[offset ..< min(offset + batchSize, keys.count)])
            let batchDeletedKeys = batch.filter { deletedKeys.contains($0) }
            self.queue.async { [weak self] in
                guard let self else {
                    return
                }

                let deletedRecords = (try? self.store.deletedMessages(keys: batchDeletedKeys)) ?? []
                let deletedByKey = Dictionary(uniqueKeysWithValues: deletedRecords.map { ($0.key, $0) })
                var latestRevisionDates: [GRVMMessageKey: Int32] = [:]
                for key in batch where revisedKeys.contains(key) {
                    if let revisions = try? self.store.editHistory(key),
                       let savedAt = revisions.last?.savedAt {
                        latestRevisionDates[key] = savedAt
                    }
                }

                let disposable = self.postbox.transaction { transaction -> Void in
                    for key in batch {
                        let messageId = MessageId(
                            peerId: PeerId(key.peerId),
                            namespace: key.namespace,
                            id: key.messageId
                        )
                        guard let message = transaction.getMessage(messageId),
                              (message.threadId ?? 0) == key.threadId else {
                            continue
                        }

                        if let record = deletedByKey[key],
                           !message.attributes.contains(where: { $0 is GRVMDeletedMessageAttribute }) {
                            _ = transaction.markMessageAsLocallyDeleted(
                                id: messageId,
                                attribute: GRVMDeletedMessageAttribute(
                                    deletedAt: record.deletedAt,
                                    source: .server,
                                    topicId: key.threadId == 0 ? nil : key.threadId,
                                    resourceIds: record.resourceIds
                                )
                            )
                        }

                        if revisedKeys.contains(key),
                           !message.attributes.contains(where: { $0 is GRVMEditHistoryMessageAttribute }) {
                            let latestRevisionAt = latestRevisionDates[key] ?? message.timestamp
                            _ = transaction.addMessageAttribute(
                                id: messageId,
                                attribute: GRVMEditHistoryMessageAttribute(latestRevisionAt: latestRevisionAt)
                            )
                        }
                    }
                }.start()
                self.disposables.add(disposable)
            }
        }
    }

    public func settingsSnapshot() -> AyuGramSettings {
        return self.settingsState.with { $0.settings }
    }

    func isBound(to accountRecordId: AccountRecordId, postbox: Postbox, mediaBox: MediaBox) -> Bool {
        return self.accountRecordId == accountRecordId
            && self.postbox === postbox
            && self.mediaBox === mediaBox
    }

    public func updateSettings(_ settings: AyuGramSettings) {
        _ = self.settingsState.swap(GRVMCoordinatorSettingsState(settings: settings))
    }

    public func messageKey(_ message: Message) -> GRVMMessageKey {
        return GRVMMessageKey(
            accountId: self.accountRecordId.int64,
            peerId: message.id.peerId.toInt64(),
            namespace: message.id.namespace,
            messageId: message.id.id,
            threadId: message.threadId ?? 0
        )
    }

    public func preserveDeletedMessages(_ messages: [Message], source: GRVMDeletionSource) -> [MessageId: [String]] {
        var result: [MessageId: [String]] = [:]
        self.queue.sync {
            guard self.isAcceptingOperations else {
                return
            }
            result = self.preserveDeletedMessagesOnQueue(messages, source: source)
        }
        return result
    }

    private func preserveDeletedMessagesOnQueue(
        _ messages: [Message],
        source: GRVMDeletionSource
    ) -> [MessageId: [String]] {
        let settings = self.settingsSnapshot()
        guard settings.saveDeletedMessages else {
            return [:]
        }

        var uniqueMessages: [GRVMMessageKey: Message] = [:]
        for message in messages {
            let directBot = message.id.peerId.namespace == Namespaces.Peer.CloudUser
                && (message.peers[message.id.peerId] as? TelegramUser)?.botInfo != nil
            if directBot && !settings.saveForBots {
                continue
            }
            uniqueMessages[self.messageKey(message)] = message
        }
        guard !uniqueMessages.isEmpty else {
            return [:]
        }

        let deletedAt = Int32(Date().timeIntervalSince1970)
        var archivedMessages: [GRVMArchivedMessage] = []
        var plannedMedia: [GRVMMessageKey: [GRVMArchivedMedia]] = [:]
        var resources: [GRVMMessageKey: [(GRVMMediaResourceReference, GRVMArchivedMedia)]] = [:]
        var result: [MessageId: [String]] = [:]

        for (key, message) in uniqueMessages {
            let messageResources = grvmMediaResources(message.media)
            let records = messageResources.map {
                self.mediaStore.plannedRecord(accountId: self.accountRecordId.int64, resource: $0)
            }
            let resourceIds = messageResources.map { $0.id.stringRepresentation }
            archivedMessages.append(GRVMArchivedMessage(
                key: key,
                senderId: message.author?.id.toInt64() ?? 0,
                timestamp: message.timestamp,
                deletedAt: deletedAt,
                text: message.text,
                entitiesData: grvmEntitiesData(message),
                mediaSummary: grvmMediaSummary(message.media),
                resourceIds: resourceIds,
                peerTitle: message.peers[message.id.peerId]?.debugDisplayTitle ?? "",
                senderName: message.author?.debugDisplayTitle ?? ""
            ))
            plannedMedia[key] = records
            resources[key] = Array(zip(messageResources, records))
            result[message.id] = resourceIds
        }

        do {
            try self.store.saveDeleted(archivedMessages, media: plannedMedia)
        } catch {
            return [:]
        }
        self.index.insertDeleted(Set(uniqueMessages.keys))

        for pairs in resources.values {
            for (resource, record) in pairs {
                self.disposables.add(self.mediaStore.archive(
                    record,
                    resource: resource,
                    mediaBox: self.mediaBox
                ).start(next: { [weak self] record in
                    guard let self else {
                        return
                    }
                    self.queue.async {
                        try? self.store.updateMedia(record)
                    }
                }))
            }
        }
        _ = source
        return result
    }

    public func preserveEditRevision(_ message: Message) -> Bool {
        var result = false
        self.queue.sync {
            guard self.isAcceptingOperations else {
                return
            }
            result = self.preserveEditRevisionOnQueue(message)
        }
        return result
    }

    private func preserveEditRevisionOnQueue(_ message: Message) -> Bool {
        let settings = self.settingsSnapshot()
        guard settings.saveEditHistory else {
            return false
        }

        let key = self.messageKey(message)
        let messageResources = grvmMediaResources(message.media)
        let records = messageResources.map {
            self.mediaStore.plannedRecord(accountId: self.accountRecordId.int64, resource: $0)
        }
        let resourceIds = messageResources.map { $0.id.stringRepresentation }
        let entitiesData = grvmEntitiesData(message)
        let mediaSummary = grvmMediaSummary(message.media)
        let fingerprint = grvmContentFingerprint(
            text: message.text,
            entitiesData: entitiesData,
            mediaSummary: mediaSummary,
            resourceIds: resourceIds
        )
        let savedAt = Int32(Date().timeIntervalSince1970)

        do {
            _ = try self.store.saveRevision(GRVMEditRevisionDraft(
                key: key,
                fingerprint: fingerprint,
                savedAt: savedAt,
                text: message.text,
                entitiesData: entitiesData,
                mediaSummary: mediaSummary,
                resourceIds: resourceIds
            ), media: records)
        } catch {
            return false
        }
        self.index.insertRevised(key)

        for (resource, record) in zip(messageResources, records) {
            self.disposables.add(self.mediaStore.archive(
                record,
                resource: resource,
                mediaBox: self.mediaBox
            ).start(next: { [weak self] record in
                guard let self else {
                    return
                }
                self.queue.async {
                    try? self.store.updateMedia(record)
                }
            }))
        }
        return true
    }

    public func clearDeleted(peerId: PeerId?, threadId: Int64?) -> Signal<[MessageId], GRVMClearDeletedError> {
        return Signal { subscriber in
            let waiterId = UUID()
            self.queue.async { [weak self] in
                guard let self else {
                    subscriber.putError(.archiveUnavailable)
                    return
                }
                guard self.isAcceptingOperations else {
                    subscriber.putError(.archiveUnavailable)
                    return
                }
                let job: GRVMCleanupJob?
                do {
                    job = try self.store.beginDeletedCleanup(
                        accountId: self.accountRecordId.int64,
                        peerId: peerId?.toInt64(),
                        threadId: threadId
                    )
                } catch {
                    subscriber.putError(.databaseFinalizationFailed)
                    return
                }
                guard let job else {
                    subscriber.putNext([])
                    subscriber.putCompletion()
                    return
                }
                self.addCleanupWaiter(jobId: job.id, waiterId: waiterId, subscriber: subscriber)
                self.startCleanupExecutorIfNeeded()
            }
            return ActionDisposable { [weak self] in
                guard let self else {
                    return
                }
                self.queue.async {
                    self.removeCleanupWaiter(waiterId)
                }
            }
        }
    }

    public func hasEditHistory(_ id: MessageId) -> Bool {
        return self.index.snapshot().revised.contains(where: {
            $0.accountId == self.accountRecordId.int64
                && $0.peerId == id.peerId.toInt64()
                && $0.namespace == id.namespace
                && $0.messageId == id.id
        })
    }

    func isMessageDeleted(peerId: Int64, messageId: Int32) -> Bool {
        return self.index.snapshot().deleted.contains(where: {
            $0.accountId == self.accountRecordId.int64
                && $0.peerId == peerId
                && $0.messageId == messageId
        })
    }

    public func deletedMessages(
        peerId: PeerId?,
        threadId: Int64?,
        query: String?
    ) -> Signal<[GRVMArchivedMessage], NoError> {
        return Signal { subscriber in
            self.queue.async {
                let result = (try? self.store.deletedMessages(GRVMArchiveQuery(
                    accountId: self.accountRecordId.int64,
                    peerId: peerId?.toInt64(),
                    threadId: threadId,
                    limit: Int32.max
                ))) ?? []
                let filtered: [GRVMArchivedMessage]
                if let query, !query.isEmpty {
                    filtered = result.filter { message in
                        return message.text.localizedCaseInsensitiveContains(query)
                            || message.peerTitle.localizedCaseInsensitiveContains(query)
                            || message.senderName.localizedCaseInsensitiveContains(query)
                            || message.mediaSummary.localizedCaseInsensitiveContains(query)
                    }
                } else {
                    filtered = result
                }
                subscriber.putNext(filtered)
                subscriber.putCompletion()
            }
            return EmptyDisposable
        }
    }

    public func editHistory(_ id: MessageId) -> Signal<[GRVMEditRevision], NoError> {
        return Signal { subscriber in
            self.queue.async {
                let key = self.index.snapshot().revised.first(where: {
                    $0.accountId == self.accountRecordId.int64
                        && $0.peerId == id.peerId.toInt64()
                        && $0.namespace == id.namespace
                        && $0.messageId == id.id
                })
                subscriber.putNext(key.flatMap { try? self.store.editHistory($0) } ?? [])
                subscriber.putCompletion()
            }
            return EmptyDisposable
        }
    }

    func isShadowBanned(_ peerId: Int64) -> Bool {
        let state = self.settingsState.with { $0 }
        return state.settings.enableFilters && state.settings.shadowBanIds.contains(peerId)
    }

    func isMessageHiddenByFilter(peerId: Int64, text: String) -> Bool {
        let state = self.settingsState.with { $0 }
        guard state.settings.enableFilters else {
            return false
        }
        if state.settings.shadowBanIds.contains(peerId) {
            return true
        }
        let isChannel = PeerId(peerId).namespace == Namespaces.Peer.CloudChannel
        if !isChannel && !state.settings.enableFiltersInChats {
            return false
        }
        let range = NSRange(text.startIndex..., in: text)
        if !text.isEmpty && state.filters.contains(where: {
            $0.firstMatch(in: text, options: [], range: range) != nil
        }) {
            return true
        }
        if !state.reversedFilters.isEmpty {
            if text.isEmpty {
                return true
            }
            return !state.reversedFilters.contains(where: {
                $0.firstMatch(in: text, options: [], range: range) != nil
            })
        }
        return false
    }

    private func restore(_ records: [GRVMArchivedMedia]) {
        for record in records {
            let id = MediaResourceId(record.resourceId)
            if self.mediaBox.completedResourcePath(id: id) == nil {
                self.disposables.add(self.mediaStore.restore(record, to: mediaBox).start())
            }
        }
    }
}
