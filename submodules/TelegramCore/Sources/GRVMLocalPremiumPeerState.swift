import Foundation
import Postbox
import SwiftSignalKit

public struct GRVMLocalPremiumPeerState: Codable, Equatable {
    public let fileId: Int64
    public let updatedAt: Int32
    public let expiresAt: Int32
    // true — статус прочитан из метки в «О себе» собеседника (GRVMLocalPremiumProfileMarker.swift).
    public let fromProfile: Bool?

    public init(fileId: Int64, updatedAt: Int32, expiresAt: Int32, fromProfile: Bool? = nil) {
        self.fileId = fileId
        self.updatedAt = updatedAt
        self.expiresAt = expiresAt
        self.fromProfile = fromProfile
    }
}

public struct GRVMLocalPremiumPresentation: Equatable {
    public let isPremium: Bool
    public let emojiStatus: PeerEmojiStatus

    public init(isPremium: Bool, emojiStatus: PeerEmojiStatus) {
        self.isPremium = isPremium
        self.emojiStatus = emojiStatus
    }
}

private let grvmLocalPremiumPeerStateCollectionId = applicationSpecificItemCacheCollectionId(15)
private let grvmLocalPremiumRemoteStateLifetime: Int32 = 7 * 24 * 60 * 60

private func grvmCurrentTimestamp() -> Int32 {
    return Int32(Date().timeIntervalSince1970)
}

private func grvmLocalPremiumPeerStateEntryId(accountPeerId: PeerId, peerId: PeerId) -> ItemCacheEntryId {
    let key = ValueBoxKey(length: 16)
    key.setInt64(0, value: accountPeerId.toInt64())
    key.setInt64(8, value: peerId.toInt64())
    return ItemCacheEntryId(collectionId: grvmLocalPremiumPeerStateCollectionId, key: key)
}

func grvmStoredLocalPremiumPeerState(transaction: Transaction, accountPeerId: PeerId, peerId: PeerId) -> GRVMLocalPremiumPeerState? {
    let entryId = grvmLocalPremiumPeerStateEntryId(accountPeerId: accountPeerId, peerId: peerId)
    return transaction.retrieveItemCacheEntry(id: entryId)?.get(GRVMLocalPremiumPeerState.self)
}

func grvmSetLocalPremiumPeerState(
    transaction: Transaction,
    accountPeerId: PeerId,
    peerId: PeerId,
    fileId: Int64,
    updatedAt: Int32,
    expiresAt: Int32
) {
    guard fileId > 0, updatedAt > 0, expiresAt > updatedAt else {
        return
    }
    if let current = grvmStoredLocalPremiumPeerState(transaction: transaction, accountPeerId: accountPeerId, peerId: peerId), current.updatedAt > updatedAt {
        return
    }
    if let entry = CodableEntry(GRVMLocalPremiumPeerState(fileId: fileId, updatedAt: updatedAt, expiresAt: expiresAt)) {
        transaction.putItemCacheEntry(
            id: grvmLocalPremiumPeerStateEntryId(accountPeerId: accountPeerId, peerId: peerId),
            entry: entry
        )
    }
}

func grvmPutLocalPremiumPeerState(
    transaction: Transaction,
    accountPeerId: PeerId,
    peerId: PeerId,
    state: GRVMLocalPremiumPeerState
) {
    if let entry = CodableEntry(state) {
        transaction.putItemCacheEntry(
            id: grvmLocalPremiumPeerStateEntryId(accountPeerId: accountPeerId, peerId: peerId),
            entry: entry
        )
    }
}

func grvmRemoveLocalPremiumPeerState(transaction: Transaction, accountPeerId: PeerId, peerId: PeerId) {
    transaction.removeItemCacheEntry(
        id: grvmLocalPremiumPeerStateEntryId(accountPeerId: accountPeerId, peerId: peerId)
    )
}

public func grvmLocalPremiumPeerState(
    postbox: Postbox,
    accountPeerId: PeerId,
    peerId: PeerId
) -> Signal<GRVMLocalPremiumPeerState?, NoError> {
    let entryId = grvmLocalPremiumPeerStateEntryId(accountPeerId: accountPeerId, peerId: peerId)
    let viewKey = PostboxViewKey.cachedItem(entryId)
    return postbox.combinedView(keys: [viewKey])
    |> map { views -> GRVMLocalPremiumPeerState? in
        guard let view = views.views[viewKey] as? CachedItemView else {
            return nil
        }
        return view.value?.get(GRVMLocalPremiumPeerState.self)
    }
    |> distinctUntilChanged
    |> mapToSignal { state -> Signal<GRVMLocalPremiumPeerState?, NoError> in
        guard let state else {
            return .single(nil)
        }
        let currentTimestamp = grvmCurrentTimestamp()
        if state.expiresAt <= currentTimestamp {
            return .single(nil)
        }
        if state.expiresAt == Int32.max {
            return .single(state)
        }
        let timeout = Double(Int64(state.expiresAt) - Int64(currentTimestamp))
        return .single(state)
        |> then(.single(nil) |> delay(timeout, queue: Queue.concurrentDefaultQueue()))
    }
}

public func grvmLocalPremiumPresentation(
    peer: Peer?,
    state: GRVMLocalPremiumPeerState?,
    currentTimestamp: Int32
) -> GRVMLocalPremiumPresentation? {
    guard let state,
          state.fileId > 0,
          state.expiresAt > currentTimestamp,
          let user = peer as? TelegramUser,
          !user.flags.contains(.isPremium),
          user.emojiStatus == nil else {
        return nil
    }
    let expirationDate = state.expiresAt == Int32.max ? nil : state.expiresAt
    return GRVMLocalPremiumPresentation(
        isPremium: true,
        emojiStatus: PeerEmojiStatus(content: .emoji(fileId: state.fileId), expirationDate: expirationDate)
    )
}

func grvmUpdateLocalPremiumPeerStates(
    transaction: Transaction,
    accountPeerId: PeerId,
    messages: [StoreMessage]
) {
    let currentTimestamp = grvmCurrentTimestamp()
    for message in messages {
        guard message.flags.contains(.Incoming),
              let authorId = message.authorId,
              authorId != accountPeerId,
              authorId.namespace == Namespaces.Peer.CloudUser,
              let marker = message.attributes.compactMap({ $0 as? GRVMLocalPremiumEmojiMessageAttribute }).last,
              let fileId = marker.fileIds.last else {
            continue
        }
        var updatedAt = message.timestamp
        for attribute in message.attributes {
            if let edited = attribute as? EditedMessageAttribute {
                updatedAt = max(updatedAt, edited.date)
            }
        }
        let expiresAt = Int32(min(Int64(Int32.max), Int64(updatedAt) + Int64(grvmLocalPremiumRemoteStateLifetime)))
        guard expiresAt > currentTimestamp else {
            continue
        }
        // Статус из «О себе» главнее эмодзи из сообщений.
        if let current = grvmStoredLocalPremiumPeerState(transaction: transaction, accountPeerId: accountPeerId, peerId: authorId),
           current.fromProfile == true,
           current.expiresAt > currentTimestamp {
            continue
        }
        grvmSetLocalPremiumPeerState(
            transaction: transaction,
            accountPeerId: accountPeerId,
            peerId: authorId,
            fileId: fileId,
            updatedAt: updatedAt,
            expiresAt: expiresAt
        )
    }
}

/// Сервер не знает о локальном статусе и присылает свой профиль без него: пока локальный Premium включён
/// и статус действует, он остаётся на своём аккаунте после любого обновления профиля с сервера.
func grvmKeepLocalPremiumSelfStatus(transaction: Transaction, accountPeerId: PeerId, user: TelegramUser) -> TelegramUser {
    guard user.id == accountPeerId,
          user.emojiStatus == nil,
          !user.flags.contains(.isPremium),
          AyuGramHooks.isLocalPremiumEnabled?(accountPeerId) == true,
          let state = grvmStoredLocalPremiumPeerState(transaction: transaction, accountPeerId: accountPeerId, peerId: accountPeerId),
          state.fileId > 0,
          state.expiresAt > grvmCurrentTimestamp() else {
        return user
    }
    let expirationDate = state.expiresAt == Int32.max ? nil : state.expiresAt
    return user.withUpdatedEmojiStatus(PeerEmojiStatus(content: .emoji(fileId: state.fileId), expirationDate: expirationDate))
}

public func grvmClearLocalPremiumSelfState(
    account: Account
) -> Signal<Never, NoError> {
    let accountPeerId = account.peerId
    return account.postbox.transaction { transaction -> Bool in
        let state = grvmStoredLocalPremiumPeerState(
            transaction: transaction,
            accountPeerId: accountPeerId,
            peerId: accountPeerId
        )
        grvmRemoveLocalPremiumPeerState(
            transaction: transaction,
            accountPeerId: accountPeerId,
            peerId: accountPeerId
        )
        guard let state else {
            return false
        }
        if let peer = transaction.getPeer(accountPeerId) as? TelegramUser,
           !peer.flags.contains(.isPremium),
           peer.emojiStatus?.fileId == state.fileId {
            updatePeersCustom(
                transaction: transaction,
                peers: [peer.withUpdatedEmojiStatus(nil)],
                update: { _, updated in updated }
            )
        }
        return true
    }
    |> mapToSignal { hadLocalStatus -> Signal<Never, NoError> in
        // Был локальный статус — в «О себе» могла остаться метка для других клиентов GRVMgram.
        guard hadLocalStatus else {
            return .complete()
        }
        return _internal_grvmSyncLocalPremiumProfileMarker(account: account, marker: nil)
    }
}
