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
    private let settingsState: Atomic<GRVMCoordinatorSettingsState>

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
        self.disposables.dispose()
    }

    func prepare() throws {
        let deleted = try store.deletedKeys(accountId: accountRecordId.int64)
        let revised = try store.revisedKeys(accountId: accountRecordId.int64)
        self.index.replace(GRVMMessageArchiveSnapshot(deleted: deleted, revised: revised))

        let records = try self.store.archivedMedia(accountId: self.accountRecordId.int64)
        self.disposables.add(self.mediaStore.reconcile(
            accountId: self.accountRecordId.int64,
            records: records
        ).start(next: { [weak self] missingRecords in
            guard let self else {
                return
            }
            self.queue.async {
                let missingIds = Set(missingRecords.map(\.resourceId))
                for record in missingRecords {
                    try? self.store.updateMedia(record)
                }
                self.restore(records.filter {
                    $0.copyState == .complete && !missingIds.contains($0.resourceId)
                })
            }
        }))

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

    public func clearDeleted(peerId: PeerId?, threadId: Int64?) -> Signal<[MessageId], NoError> {
        return Signal { subscriber in
            let disposable = MetaDisposable()
            self.queue.async { [weak self] in
                guard let self else {
                    subscriber.putCompletion()
                    return
                }
                guard let keys = try? self.store.deletedMessageKeys(
                    accountId: self.accountRecordId.int64,
                    peerId: peerId?.toInt64(),
                    threadId: threadId
                ) else {
                    subscriber.putNext([])
                    subscriber.putCompletion()
                    return
                }
                guard !keys.isEmpty else {
                    subscriber.putNext([])
                    subscriber.putCompletion()
                    return
                }

                let ids = keys.map { key in
                    MessageId(
                        peerId: PeerId(key.peerId),
                        namespace: key.namespace,
                        id: key.messageId
                    )
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
                }.start(next: { [weak self] ids in
                    guard let self else {
                        subscriber.putCompletion()
                        return
                    }
                    self.queue.async {
                        guard let removedMedia = try? self.store.removeDeleted(keys) else {
                            subscriber.putNext([])
                            subscriber.putCompletion()
                            return
                        }
                        self.index.removeDeleted(Set(keys))
                        self.mediaStore.remove(removedMedia, completion: {
                            subscriber.putNext(ids)
                            subscriber.putCompletion()
                        })
                    }
                }))
            }
            return disposable
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
