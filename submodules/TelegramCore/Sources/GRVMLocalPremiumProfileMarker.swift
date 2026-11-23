import Foundation
import Postbox
import SwiftSignalKit
internal import TelegramApi
import MtProtoKit

// Статус локального Premium между клиентами GRVMgram.
//
// Сервер не хранит эмодзи-статус непремиального аккаунта, поэтому статус передаётся невидимой меткой
// в конце «О себе»: два «магических» селектора варианта и цифры из селекторов варианта U+FE00…U+FE0F
// (по 4 бита). Обычный Telegram их не рисует; GRVMgram читает метку, убирает её из показанного текста
// и показывает статус собеседника в заголовке чата и в профиле (через GRVMLocalPremiumPeerState).
//
//   U+FE0F U+FE0E + 16 цифр: id эмодзи (18 символов)
//   U+FE0F U+FE0D + 16 цифр id + 8 цифр срока (unixtime): статус на время (26 символов)

struct GRVMLocalPremiumProfileMarker: Equatable {
    let fileId: Int64
    let expiresAt: Int32?
}

private let grvmProfileMarkerDigitBase: UInt32 = 0xFE00
private let grvmProfileMarkerMagic: UInt32 = 0xFE0F
private let grvmProfileMarkerPlainKind: UInt32 = 0xFE0E
private let grvmProfileMarkerUntilKind: UInt32 = 0xFE0D
private let grvmProfileMarkerPlainLength = 2 + 16
private let grvmProfileMarkerUntilLength = 2 + 16 + 8

private func grvmProfileMarkerDecodeDigits(_ scalars: ArraySlice<Unicode.Scalar>) -> UInt64? {
    var result: UInt64 = 0
    for scalar in scalars {
        let value = scalar.value
        guard value >= grvmProfileMarkerDigitBase, value <= grvmProfileMarkerDigitBase + 0xF else {
            return nil
        }
        result = (result << 4) | UInt64(value - grvmProfileMarkerDigitBase)
    }
    return result
}

private func grvmProfileMarkerEncodeDigits(_ value: UInt64, count: Int, into view: inout String.UnicodeScalarView) {
    for index in (0 ..< count).reversed() {
        let digit = UInt32((value >> UInt64(index * 4)) & 0xF)
        if let scalar = Unicode.Scalar(grvmProfileMarkerDigitBase + digit) {
            view.append(scalar)
        }
    }
}

/// Разбирает «О себе»: текст без метки (nil, если после снятия метки ничего не осталось) и сама метка.
func grvmParseLocalPremiumProfileMarker(_ about: String?) -> (text: String?, marker: GRVMLocalPremiumProfileMarker?) {
    guard let about, !about.isEmpty else {
        return (about, nil)
    }
    let scalars = Array(about.unicodeScalars)

    func stripped(_ length: Int) -> String? {
        var view = String.UnicodeScalarView()
        view.append(contentsOf: scalars[0 ..< (scalars.count - length)])
        let text = String(view)
        return text.isEmpty ? nil : text
    }

    if scalars.count >= grvmProfileMarkerUntilLength {
        let start = scalars.count - grvmProfileMarkerUntilLength
        if scalars[start].value == grvmProfileMarkerMagic,
           scalars[start + 1].value == grvmProfileMarkerUntilKind,
           let rawFileId = grvmProfileMarkerDecodeDigits(scalars[(start + 2) ..< (start + 18)]),
           let rawUntil = grvmProfileMarkerDecodeDigits(scalars[(start + 18) ..< scalars.count]) {
            let fileId = Int64(bitPattern: rawFileId)
            let until = Int32(truncatingIfNeeded: rawUntil)
            let marker = fileId > 0 && until > 0 ? GRVMLocalPremiumProfileMarker(fileId: fileId, expiresAt: until) : nil
            return (stripped(grvmProfileMarkerUntilLength), marker)
        }
    }
    if scalars.count >= grvmProfileMarkerPlainLength {
        let start = scalars.count - grvmProfileMarkerPlainLength
        if scalars[start].value == grvmProfileMarkerMagic,
           scalars[start + 1].value == grvmProfileMarkerPlainKind,
           let rawFileId = grvmProfileMarkerDecodeDigits(scalars[(start + 2) ..< scalars.count]) {
            let fileId = Int64(bitPattern: rawFileId)
            let marker = fileId > 0 ? GRVMLocalPremiumProfileMarker(fileId: fileId, expiresAt: nil) : nil
            return (stripped(grvmProfileMarkerPlainLength), marker)
        }
    }
    return (about, nil)
}

/// Текст «О себе» с меткой в конце (или без неё, если marker == nil).
func grvmComposeLocalPremiumProfileAbout(text: String?, marker: GRVMLocalPremiumProfileMarker?) -> String {
    var view = (text ?? "").unicodeScalars
    guard let marker, marker.fileId > 0 else {
        return String(view)
    }
    view.append(Unicode.Scalar(grvmProfileMarkerMagic)!)
    if let expiresAt = marker.expiresAt, expiresAt > 0 {
        view.append(Unicode.Scalar(grvmProfileMarkerUntilKind)!)
        grvmProfileMarkerEncodeDigits(UInt64(bitPattern: marker.fileId), count: 16, into: &view)
        grvmProfileMarkerEncodeDigits(UInt64(UInt32(bitPattern: expiresAt)), count: 8, into: &view)
    } else {
        view.append(Unicode.Scalar(grvmProfileMarkerPlainKind)!)
        grvmProfileMarkerEncodeDigits(UInt64(bitPattern: marker.fileId), count: 16, into: &view)
    }
    return String(view)
}

/// Метка, которую сейчас должен нести профиль этого аккаунта: только при включённом локальном Premium,
/// без настоящего Premium и с действующим локальным статусом.
func grvmCurrentLocalPremiumProfileMarker(transaction: Transaction, accountPeerId: PeerId) -> GRVMLocalPremiumProfileMarker? {
    guard AyuGramHooks.isLocalPremiumEnabled?(accountPeerId) == true,
          let peer = transaction.getPeer(accountPeerId) as? TelegramUser,
          !peer.flags.contains(.isPremium),
          let state = grvmStoredLocalPremiumPeerState(transaction: transaction, accountPeerId: accountPeerId, peerId: accountPeerId),
          state.fileId > 0,
          state.expiresAt > Int32(Date().timeIntervalSince1970) else {
        return nil
    }
    return GRVMLocalPremiumProfileMarker(fileId: state.fileId, expiresAt: state.expiresAt == Int32.max ? nil : state.expiresAt)
}

/// Приём: «О себе» собеседника пришло с сервера. Метка из профиля — главный источник статуса:
/// она заменяет статус из сообщений, а её исчезновение снимает статус, поставленный профилем.
/// Возвращает текст без метки — его и надо сохранять в CachedUserData.
func grvmApplyLocalPremiumProfileMarker(transaction: Transaction, accountPeerId: PeerId, peerId: PeerId, about: String?) -> String? {
    let (text, marker) = grvmParseLocalPremiumProfileMarker(about)
    guard peerId != accountPeerId, peerId.namespace == Namespaces.Peer.CloudUser else {
        return text
    }
    let current = grvmStoredLocalPremiumPeerState(transaction: transaction, accountPeerId: accountPeerId, peerId: peerId)
    let currentTimestamp = Int32(Date().timeIntervalSince1970)
    if let marker, (marker.expiresAt ?? Int32.max) > currentTimestamp {
        let expiresAt = marker.expiresAt ?? Int32.max
        if current?.fileId != marker.fileId || current?.expiresAt != expiresAt || current?.fromProfile != true {
            grvmPutLocalPremiumPeerState(
                transaction: transaction,
                accountPeerId: accountPeerId,
                peerId: peerId,
                state: GRVMLocalPremiumPeerState(fileId: marker.fileId, updatedAt: currentTimestamp, expiresAt: expiresAt, fromProfile: true)
            )
        }
    } else if current?.fromProfile == true {
        grvmRemoveLocalPremiumPeerState(transaction: transaction, accountPeerId: accountPeerId, peerId: peerId)
    }
    return text
}

/// Отправка: приводит метку в своём «О себе» к нужной (marker == nil — снять). Текст берётся свежий
/// с сервера, чтобы не затереть «О себе», изменённое с другого устройства. Если с меткой текст не влезает
/// в лимит, сервер откажет — тогда статус просто не синхронизируется.
func _internal_grvmSyncLocalPremiumProfileMarker(account: Account, marker: GRVMLocalPremiumProfileMarker?) -> Signal<Never, NoError> {
    return account.network.request(Api.functions.users.getFullUser(id: .inputUserSelf))
    |> map(Optional.init)
    |> `catch` { _ -> Signal<Api.users.UserFull?, NoError> in
        return .single(nil)
    }
    |> mapToSignal { result -> Signal<Never, NoError> in
        guard let result else {
            return .complete()
        }
        let about: String?
        switch result {
        case let .userFull(userFullData):
            switch userFullData.fullUser {
            case let .userFull(fullUserData):
                about = fullUserData.about
            }
        }
        let (text, currentMarker) = grvmParseLocalPremiumProfileMarker(about)
        if currentMarker == marker {
            return .complete()
        }
        if currentMarker == nil && marker == nil {
            return .complete()
        }
        let updatedAbout = grvmComposeLocalPremiumProfileAbout(text: text, marker: marker)
        return _internal_updateAccountProfile(account: account, firstName: nil, lastName: nil, about: updatedAbout)
        |> ignoreValues
        |> `catch` { _ -> Signal<Never, NoError> in
            return .complete()
        }
    }
}
