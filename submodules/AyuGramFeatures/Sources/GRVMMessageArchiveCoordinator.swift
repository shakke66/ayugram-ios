import Foundation
import SwiftSignalKit
import Postbox
import TelegramCore
import AyuGramLib

private struct GRVMCoordinatorSettingsState {
    let settings: AyuGramSettings

    init(settings: AyuGramSettings) {
        self.settings = settings
    }
}

private struct GRVMConsumableMediaPreparation {
    let message: Message
    let key: GRVMMessageKey
    let resources: [GRVMMediaResourceReference]
    let fetchResources: [GRVMConsumableMediaFetchResource]
    let plannedMedia: [GRVMArchivedMedia]
    let requiredPrimaryIds: [String]
    let alreadyPrepared: Bool
}

private struct GRVMConsumableMediaFetchResource {
    let resource: MediaResource
    let reference: MediaResourceReference
    let userContentType: MediaResourceUserContentType
}

private struct GRVMConsumableMediaRestoreContext {
    let key: GRVMMessageKey
    let resourceIds: [String]
    let requiresConsumableMarker: Bool
}

private func grvmPrimaryMediaResourceIds(_ media: [Media]) -> [String]? {
    var resourceIds = Set<String>()
    for item in media {
        if let image = item as? TelegramMediaImage {
            guard let representation = largestImageRepresentation(image.representations) else {
                return nil
            }
            resourceIds.insert(representation.resource.id.stringRepresentation)
        } else if let file = item as? TelegramMediaFile {
            resourceIds.insert(file.resource.id.stringRepresentation)
        } else {
            return nil
        }
    }
    guard !resourceIds.isEmpty else {
        return nil
    }
    return resourceIds.sorted()
}

private func grvmNonCancellable<T>(_ signal: Signal<T, NoError>) -> Signal<T, NoError> {
    return Signal { subscriber in
        let _ = signal.startStandalone(
            next: subscriber.putNext,
            completed: subscriber.putCompletion
        )
        return EmptyDisposable
    }
}

private func grvmMediaResources(_ message: Message) -> [GRVMMediaResourceReference] {
    return grvmMediaResources(message.media)
}

private func grvmPositiveFileSize(_ path: String) -> Int64 {
    guard let value = (try? FileManager.default.attributesOfItem(atPath: path)[.size]) as? NSNumber else {
        return 0
    }
    return value.int64Value
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
        let visibleDeleted = try store.deletedKeys(
            accountId: accountRecordId.int64,
            excludingSenderId: self.accountPeerId.toInt64()
        )
        let revised = try store.revisedKeys(accountId: accountRecordId.int64)
        _ = try? store.beginExcludedSenderCleanup(
            accountId: accountRecordId.int64,
            senderId: self.accountPeerId.toInt64()
        )
        self.index.replace(GRVMMessageArchiveSnapshot(deleted: visibleDeleted, revised: revised))

        assert(visibleDeleted.isSubset(of: deleted))

        self.disposables.add(self.mediaBox.didRemoveResourceIds.start(next: { [weak self] ids in
            guard let self, !ids.isEmpty else {
                return
            }
            self.queue.async {
                guard self.isAcceptingOperations else {
                    return
                }
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

    func shutdownForReplacement() -> [Subscriber<[MessageId], GRVMClearDeletedError>] {
        var waiters: [Subscriber<[MessageId], GRVMClearDeletedError>] = []
        self.queue.sync {
            guard self.isAcceptingOperations else {
                return
            }
            self.isAcceptingOperations = false
            self.cleanupRunnerDisposable.dispose()
            self.disposables.dispose()
            self.isCleanupExecutorRunning = false
            waiters = self.takeAllCleanupWaiters()
        }
        return waiters
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
                        let keySet = Set(keys)
                        self.index.removeDeleted(keySet)
                        self.index.removeRevised(keySet)
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
        guard self.isAcceptingOperations, !self.didStartArchivedMediaReconciliation else {
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
                guard self.isAcceptingOperations else {
                    return
                }
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
                guard self.isAcceptingOperations else {
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
                                    source: GRVMDeletionSource(rawValue: record.deletionSource) ?? .server,
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

    public func prepareConsumableMedia(_ message: Message) -> Signal<Bool, NoError> {
        guard self.settingsSnapshot().saveDeletedMessages else {
            return .single(false)
        }

        return self.postbox.transaction { transaction -> Bool in
            guard let currentMessage = transaction.getMessage(message.id),
                  currentMessage.stableId == message.stableId else {
                return false
            }
            if currentMessage.attributes.contains(where: { $0 is GRVMPreservedConsumableMediaAttribute }) {
                return true
            }
            _ = currentMessage.media
            _ = grvmMediaResources(currentMessage)
            return false
        }
        |> mapToSignal { [weak self] markerPresent -> Signal<Bool, NoError> in
            guard let self else {
                return .single(false)
            }
            if markerPresent {
                return Signal<Bool, NoError>.single(markerPresent)
            }

            return self.postbox.transaction { transaction -> GRVMConsumableMediaPreparation? in
                guard let freshMessage = transaction.getMessage(message.id),
                      freshMessage.stableId == message.stableId else {
                    return nil
                }
                let key = self.messageKey(freshMessage)
                if freshMessage.attributes.contains(where: { $0 is GRVMPreservedConsumableMediaAttribute }) {
                    return GRVMConsumableMediaPreparation(
                        message: freshMessage,
                        key: key,
                        resources: [],
                        fetchResources: [],
                        plannedMedia: [],
                        requiredPrimaryIds: [],
                        alreadyPrepared: true
                    )
                }

                var selectedResourceSet = Set<MediaResourceId>()
                var preservedMedia: [Media] = []
                var fetchResources: [GRVMConsumableMediaFetchResource] = []
                let messageReference = MessageReference(freshMessage)
                for media in freshMessage.media {
                    if let image = media as? TelegramMediaImage {
                        guard let representation = largestImageRepresentation(image.representations) else {
                            return nil
                        }
                        selectedResourceSet.insert(representation.resource.id)
                        preservedMedia.append(image)
                        fetchResources.append(GRVMConsumableMediaFetchResource(
                            resource: representation.resource,
                            reference: MediaResourceReference.media(
                                media: AnyMediaReference.message(message: messageReference, media: image),
                                resource: representation.resource
                            ),
                            userContentType: .image
                        ))
                    } else if let file = media as? TelegramMediaFile {
                        selectedResourceSet.insert(file.resource.id)
                        preservedMedia.append(file)
                        fetchResources.append(GRVMConsumableMediaFetchResource(
                            resource: file.resource,
                            reference: MediaResourceReference.media(
                                media: AnyMediaReference.message(message: messageReference, media: file),
                                resource: file.resource
                            ),
                            userContentType: MediaResourceUserContentType(file: file)
                        ))
                    } else {
                        return nil
                    }
                }
                guard !selectedResourceSet.isEmpty, preservedMedia.count == freshMessage.media.count else {
                    return nil
                }

                let requiredResources = grvmMediaResources(freshMessage).filter {
                    selectedResourceSet.contains($0.id)
                }
                let requiredPrimaryIds = requiredResources.map { $0.id.stringRepresentation }.sorted()
                guard Set(requiredPrimaryIds) == Set(selectedResourceSet.map(\.stringRepresentation)),
                      requiredResources.count == requiredPrimaryIds.count,
                      fetchResources.count == requiredResources.count else {
                    return nil
                }
                let plannedMedia = requiredResources.map {
                    self.mediaStore.plannedRecord(accountId: self.accountRecordId.int64, resource: $0)
                }
                return GRVMConsumableMediaPreparation(
                    message: freshMessage,
                    key: key,
                    resources: requiredResources,
                    fetchResources: fetchResources,
                    plannedMedia: plannedMedia,
                    requiredPrimaryIds: requiredPrimaryIds,
                    alreadyPrepared: false
                )
            }
            |> mapToSignal { preparation -> Signal<Bool, NoError> in
                guard let preparation else {
                    return .single(false)
                }
                if preparation.alreadyPrepared {
                    return Signal<Bool, NoError>.single(preparation.alreadyPrepared)
                }

                let fetchSignals: [Signal<Bool, NoError>] = preparation.fetchResources.map { fetchResource in
                    let fetch = fetchedMediaResource(
                        mediaBox: self.mediaBox,
                        userLocation: .peer(preparation.message.id.peerId),
                        userContentType: fetchResource.userContentType,
                        reference: fetchResource.reference,
                        reportResultStatus: true,
                        continueInBackground: true
                    )
                    |> map { _ -> Bool in
                        return true
                    }
                    |> `catch` { _ -> Signal<Bool, NoError> in
                        return .single(false)
                    }

                    return fetch
                    |> mapToSignal { fetched -> Signal<Bool, NoError> in
                        guard fetched else {
                            return .single(false)
                        }
                        return self.mediaBox.resourceData(
                            fetchResource.resource,
                            option: .complete(waitUntilFetchStatus: true),
                            attemptSynchronously: false
                        )
                        |> filter { $0.complete }
                        |> take(1)
                        |> map { data -> Bool in
                            return data.complete && grvmPositiveFileSize(data.path) > 0
                        }
                    }
                }

                return combineLatest(fetchSignals)
                |> mapToSignal { fetched -> Signal<Bool, NoError> in
                    guard fetched.allSatisfy({ $0 }) else {
                        return .single(false)
                    }
                    for resource in preparation.resources {
                        guard let path = self.mediaBox.completedResourcePath(id: resource.id),
                              grvmPositiveFileSize(path) > 0 else {
                            return .single(false)
                        }
                    }

                let requiredPrimaryIds = preparation.requiredPrimaryIds
                guard let reservation = try? self.store.reserveConsumableMedia(
                    key: preparation.key,
                    media: preparation.plannedMedia
                ) else {
                    return .single(false)
                }
                let recordsById = Dictionary(uniqueKeysWithValues: reservation.media.map { ($0.resourceId, $0) })
                let archiveSignals: [Signal<GRVMArchivedMedia, NoError>] = preparation.resources.compactMap { resource in
                    guard let record = recordsById[resource.id.stringRepresentation] else {
                        return nil
                    }
                    return self.mediaStore.archive(record, resource: resource, mediaBox: self.mediaBox)
                }
                guard archiveSignals.count == preparation.resources.count, !archiveSignals.isEmpty else {
                    let orphanedMedia = (try? self.store.rollbackConsumableMediaReservation(
                        key: preparation.key,
                        insertedResourceIds: reservation.insertedResourceIds
                    )) ?? []
                    var invalidOrphanedMedia = false
                    for record in orphanedMedia {
                        if record.accountId != self.accountRecordId.int64 || record.relativePath.isEmpty {
                            invalidOrphanedMedia = true
                            break
                        }
                    }
                    guard !invalidOrphanedMedia else {
                        return .single(false)
                    }
                    _ = self.mediaStore.removeArchivedFiles(orphanedMedia)
                    return .single(false)
                }

                return grvmNonCancellable(
                    combineLatest(archiveSignals)
                    |> mapToSignal { terminalRecords -> Signal<Bool, NoError> in
                    do {
                        for record in terminalRecords {
                            try self.store.updateMedia(record)
                        }
                    } catch {
                        let orphanedMedia = (try? self.store.rollbackConsumableMediaReservation(
                            key: preparation.key,
                            insertedResourceIds: reservation.insertedResourceIds
                        )) ?? []
                        _ = self.mediaStore.removeArchivedFiles(orphanedMedia)
                        return .single(false)
                    }

                    let terminalRecordsComplete = terminalRecords.allSatisfy {
                        $0.copyState == .complete && $0.byteCount > 0
                    }
                    let terminalResourceIds = terminalRecords.map(\.resourceId).sorted()
                    let terminalIdsMatch = Set(requiredPrimaryIds) == Set(terminalResourceIds)
                    guard terminalRecordsComplete else {
                        let orphanedMedia = (try? self.store.rollbackConsumableMediaReservation(
                            key: preparation.key,
                            insertedResourceIds: reservation.insertedResourceIds
                        )) ?? []
                        _ = self.mediaStore.removeArchivedFiles(orphanedMedia)
                        return .single(false)
                    }
                    guard terminalIdsMatch else {
                        let orphanedMedia = (try? self.store.rollbackConsumableMediaReservation(
                            key: preparation.key,
                            insertedResourceIds: reservation.insertedResourceIds
                        )) ?? []
                        _ = self.mediaStore.removeArchivedFiles(orphanedMedia)
                        return .single(false)
                    }

                    return self.postbox.transaction { transaction -> Bool in
                        guard let freshMessage = transaction.getMessage(message.id),
                              freshMessage.stableId == message.stableId,
                              let freshPrimaryResourceIds = grvmPrimaryMediaResourceIds(freshMessage.media),
                              Set(freshPrimaryResourceIds) == Set(requiredPrimaryIds) else {
                            return false
                        }
                        if freshMessage.attributes.contains(where: { $0 is GRVMPreservedConsumableMediaAttribute }) {
                            return true
                        }
                        var attributes = freshMessage.attributes
                        attributes.removeAll(where: { $0 is GRVMPreservedConsumableMediaAttribute })
                        attributes.append(GRVMPreservedConsumableMediaAttribute(
                            resourceIds: terminalResourceIds,
                            media: freshMessage.media,
                            preparedAt: Int32(Date().timeIntervalSince1970)
                        ))
                        transaction.updateMessage(freshMessage.id, update: { currentMessage in
                            var storeForwardInfo: StoreMessageForwardInfo?
                            if let forwardInfo = currentMessage.forwardInfo {
                                storeForwardInfo = StoreMessageForwardInfo(authorId: forwardInfo.author?.id, sourceId: forwardInfo.source?.id, sourceMessageId: forwardInfo.sourceMessageId, date: forwardInfo.date, authorSignature: forwardInfo.authorSignature, psaType: forwardInfo.psaType, flags: forwardInfo.flags)
                            }
                            return .update(StoreMessage(id: currentMessage.id, customStableId: nil, globallyUniqueId: currentMessage.globallyUniqueId, groupingKey: currentMessage.groupingKey, threadId: currentMessage.threadId, timestamp: currentMessage.timestamp, flags: StoreMessageFlags(currentMessage.flags), tags: currentMessage.tags, globalTags: currentMessage.globalTags, localTags: currentMessage.localTags, forwardInfo: storeForwardInfo, authorId: currentMessage.author?.id, text: currentMessage.text, attributes: attributes, media: currentMessage.media))
                        })
                        return true
                    }
                    |> map { attached -> Bool in
                        if !attached {
                            let orphanedMedia = (try? self.store.rollbackConsumableMediaReservation(
                                key: preparation.key,
                                insertedResourceIds: reservation.insertedResourceIds
                            )) ?? []
                            _ = self.mediaStore.removeArchivedFiles(orphanedMedia)
                        }
                        return attached
                    }
                    }
                )
                }
            }
        }
    }

    public func restoreArchivedMedia(for message: Message) -> Signal<Bool, NoError> {
        return self.postbox.transaction { transaction -> GRVMConsumableMediaRestoreContext? in
            guard let currentMessage = transaction.getMessage(message.id),
                  currentMessage.stableId == message.stableId else {
                return nil
            }
            if let attribute = currentMessage.attributes.first(where: {
                $0 is GRVMPreservedConsumableMediaAttribute
            }) as? GRVMPreservedConsumableMediaAttribute {
                return GRVMConsumableMediaRestoreContext(
                    key: self.messageKey(currentMessage),
                    resourceIds: attribute.resourceIds,
                    requiresConsumableMarker: true
                )
            }
            guard let deletedAttribute = currentMessage.attributes.first(where: {
                $0 is GRVMDeletedMessageAttribute
            }) as? GRVMDeletedMessageAttribute,
                  let primaryResourceIds = grvmPrimaryMediaResourceIds(currentMessage.media),
                  Set(primaryResourceIds).isSubset(of: Set(deletedAttribute.resourceIds)) else {
                return nil
            }
            return GRVMConsumableMediaRestoreContext(
                key: self.messageKey(currentMessage),
                resourceIds: primaryResourceIds,
                requiresConsumableMarker: false
            )
        }
        |> mapToSignal { [weak self] context -> Signal<Bool, NoError> in
            guard let self, let context else {
                return .single(false)
            }
            guard context.key.accountId == self.accountRecordId.int64 else {
                return .single(false)
            }
            guard let records = try? self.store.consumableMedia(key: context.key, resourceIds: Set(context.resourceIds)),
                  !records.isEmpty else {
                return .single(false)
            }
            guard records.allSatisfy({ $0.copyState == .complete && $0.byteCount > 0 }),
                  Set(context.resourceIds) == Set(records.map(\.resourceId)) else {
                return .single(false)
            }
            let restoreSignals = records.map { record in
                self.mediaStore.restore(record, to: self.mediaBox)
            }
            return combineLatest(restoreSignals)
            |> mapToSignal { restored -> Signal<Bool, NoError> in
                guard restored.allSatisfy({ $0 }) else {
                    return .single(false)
                }
                for resourceId in context.resourceIds {
                    guard let path = self.mediaBox.completedResourcePath(id: MediaResourceId(resourceId)) else {
                        return .single(false)
                    }
                    let fileSize = grvmPositiveFileSize(path)
                    guard fileSize > 0 else {
                        return .single(false)
                    }
                }

                return self.postbox.transaction { transaction -> Bool in
                    guard let freshMessage = transaction.getMessage(message.id),
                          freshMessage.stableId == message.stableId else {
                        return false
                    }
                    let replacementMedia: [Media]?
                    if context.requiresConsumableMarker {
                        guard let attribute = freshMessage.attributes.first(where: {
                            $0 is GRVMPreservedConsumableMediaAttribute
                        }) as? GRVMPreservedConsumableMediaAttribute,
                              Set(attribute.resourceIds) == Set(context.resourceIds) else {
                            return false
                        }
                        replacementMedia = attribute.media
                    } else {
                        guard let deletedAttribute = freshMessage.attributes.first(where: {
                            $0 is GRVMDeletedMessageAttribute
                        }) as? GRVMDeletedMessageAttribute,
                              let primaryResourceIds = grvmPrimaryMediaResourceIds(freshMessage.media),
                              Set(primaryResourceIds) == Set(context.resourceIds),
                              Set(primaryResourceIds).isSubset(of: Set(deletedAttribute.resourceIds)) else {
                            return false
                        }
                        replacementMedia = nil
                    }
                    if let replacementMedia,
                       freshMessage.media.contains(where: { $0 is TelegramMediaExpiredContent }) {
                        transaction.updateMessage(freshMessage.id, update: { currentMessage in
                            var storeForwardInfo: StoreMessageForwardInfo?
                            if let forwardInfo = currentMessage.forwardInfo {
                                storeForwardInfo = StoreMessageForwardInfo(authorId: forwardInfo.author?.id, sourceId: forwardInfo.source?.id, sourceMessageId: forwardInfo.sourceMessageId, date: forwardInfo.date, authorSignature: forwardInfo.authorSignature, psaType: forwardInfo.psaType, flags: forwardInfo.flags)
                            }
                            return .update(StoreMessage(id: currentMessage.id, customStableId: nil, globallyUniqueId: currentMessage.globallyUniqueId, groupingKey: currentMessage.groupingKey, threadId: currentMessage.threadId, timestamp: currentMessage.timestamp, flags: StoreMessageFlags(currentMessage.flags), tags: currentMessage.tags, globalTags: currentMessage.globalTags, localTags: currentMessage.localTags, forwardInfo: storeForwardInfo, authorId: currentMessage.author?.id, text: currentMessage.text, attributes: currentMessage.attributes, media: replacementMedia))
                        })
                    }
                    return true
                }
            }
        }
    }

    public func preserveDeletedMessages(_ messages: [Message], source: GRVMDeletionSource) -> GRVMDeletedMessagesPreservationResult {
        var result: GRVMDeletedMessagesPreservationResult = .unavailable
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
    ) -> GRVMDeletedMessagesPreservationResult {
        let settings = self.settingsSnapshot()
        guard settings.saveDeletedMessages else {
            return .disabled
        }

        var uniqueMessages: [GRVMMessageKey: Message] = [:]
        for message in messages {
            if message.author?.id == self.accountPeerId {
                continue
            }
            let directBot = message.id.peerId.namespace == Namespaces.Peer.CloudUser
                && (message.peers[message.id.peerId] as? TelegramUser)?.botInfo != nil
            if directBot && !settings.saveForBots {
                continue
            }
            uniqueMessages[self.messageKey(message)] = message
        }
        guard !uniqueMessages.isEmpty else {
            return .preserved([:])
        }

        let deletedAt = Int32(Date().timeIntervalSince1970)
        var archivedMessages: [GRVMArchivedMessage] = []
        var plannedMedia: [GRVMMessageKey: [GRVMArchivedMedia]] = [:]
        var resources: [GRVMMessageKey: [GRVMMediaResourceReference]] = [:]

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
                deletionSource: source.rawValue,
                text: message.text,
                entitiesData: grvmEntitiesData(message),
                mediaSummary: grvmMediaSummary(message.media),
                resourceIds: resourceIds,
                peerTitle: message.peers[message.id.peerId]?.debugDisplayTitle ?? "",
                senderName: message.author?.debugDisplayTitle ?? ""
            ))
            plannedMedia[key] = records
            resources[key] = messageResources
        }

        let admittedMedia: [GRVMMessageKey: [GRVMArchivedMedia]]
        do {
            admittedMedia = try self.store.saveDeleted(archivedMessages, media: plannedMedia)
        } catch {
            return .unavailable
        }
        let admittedKeys = Set(admittedMedia.keys)
        self.index.insertDeleted(admittedKeys)

        var result: [MessageId: [String]] = [:]
        for key in admittedKeys {
            guard let message = uniqueMessages[key] else {
                continue
            }
            result[message.id] = (resources[key] ?? []).map { $0.id.stringRepresentation }
        }

        for key in admittedKeys {
            guard let messageResources = resources[key] else {
                continue
            }
            let recordsById = Dictionary(uniqueKeysWithValues: (admittedMedia[key] ?? []).map {
                ($0.resourceId, $0)
            })
            for resource in messageResources {
                guard let record = recordsById[resource.id.stringRepresentation] else {
                    continue
                }
                self.disposables.add(self.mediaStore.archive(
                    record,
                    resource: resource,
                    mediaBox: self.mediaBox
                ).start(next: { [weak self] record in
                    guard let self else {
                        return
                    }
                    self.queue.async {
                        guard self.isAcceptingOperations else {
                            return
                        }
                        try? self.store.updateMedia(record)
                    }
                }))
            }
        }
        return .preserved(result)
    }

    public func preserveEditRevision(_ message: Message, content: GRVMEditableMessageContent) -> Bool {
        var result = false
        self.queue.sync {
            guard self.isAcceptingOperations else {
                return
            }
            result = self.preserveEditRevisionOnQueue(message, content: content)
        }
        return result
    }

    private func preserveEditRevisionOnQueue(
        _ message: Message,
        content: GRVMEditableMessageContent
    ) -> Bool {
        let settings = self.settingsSnapshot()
        guard settings.saveEditHistory else {
            return false
        }

        let key = self.messageKey(message)
        let messageResources = grvmMediaResources(message.media)
        var records = messageResources.map {
            self.mediaStore.plannedRecord(accountId: self.accountRecordId.int64, resource: $0)
        }
        let resourceIds = messageResources.map { $0.id.stringRepresentation }
        let entitiesData = grvmEntitiesData(message)
        let mediaSummary = grvmMediaSummary(message.media)
        let savedAt = Int32(Date().timeIntervalSince1970)

        do {
            let fingerprint = try grvmContentFingerprint(content)
            let saved = try self.store.saveRevision(GRVMEditRevisionDraft(
                key: key,
                fingerprint: fingerprint,
                savedAt: savedAt,
                editableContent: content,
                text: message.text,
                entitiesData: entitiesData,
                mediaSummary: mediaSummary,
                resourceIds: resourceIds
            ), media: records)
            records = saved.media
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
                    guard self.isAcceptingOperations else {
                        return
                    }
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

    public func removeDeletedMessage(_ key: GRVMMessageKey) -> Signal<[MessageId], GRVMClearDeletedError> {
        return Signal { subscriber in
            let waiterId = UUID()
            self.queue.async { [weak self] in
                guard let self,
                      self.isAcceptingOperations,
                      key.accountId == self.accountRecordId.int64 else {
                    subscriber.putError(.archiveUnavailable)
                    return
                }
                let job: GRVMCleanupJob?
                do {
                    job = try self.store.beginDeletedCleanup(key: key)
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

    public func purgeDeletedMessage(_ message: Message) -> Signal<[MessageId], GRVMClearDeletedError> {
        return self.removeDeletedMessage(self.messageKey(message))
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
                ), excludingSenderId: self.accountPeerId.toInt64())) ?? []
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

    private func restore(_ records: [GRVMArchivedMedia]) {
        guard self.isAcceptingOperations else {
            return
        }
        for record in records {
            let id = MediaResourceId(record.resourceId)
            if self.mediaBox.completedResourcePath(id: id) == nil {
                self.disposables.add(self.mediaStore.restore(record, to: mediaBox).start())
            }
        }
    }
}
