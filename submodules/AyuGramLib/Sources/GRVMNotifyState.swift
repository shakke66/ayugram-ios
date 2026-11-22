import Foundation
import Postbox
import SwiftSignalKit
import TelegramCore
import TelegramUIPreferences

public struct GRVMNotifyState: Codable, Equatable {
    public var pairedUserId: Int64?
    public var sessionHash: Int64?
    public var pendingAccountUserId: Int64?
    public var pendingStartedAt: Int32?

    public static let empty = GRVMNotifyState(
        pairedUserId: nil,
        sessionHash: nil,
        pendingAccountUserId: nil,
        pendingStartedAt: nil
    )

    public init(
        pairedUserId: Int64?,
        sessionHash: Int64?,
        pendingAccountUserId: Int64?,
        pendingStartedAt: Int32?
    ) {
        self.pairedUserId = pairedUserId
        self.sessionHash = sessionHash
        self.pendingAccountUserId = pendingAccountUserId
        self.pendingStartedAt = pendingStartedAt
    }

    public func normalized(now: Int32) -> GRVMNotifyState {
        var result = self
        if !(result.pairedUserId.map { $0 > 0 } ?? false)
            || !(result.sessionHash.map { $0 != 0 } ?? false) {
            result.pairedUserId = nil
            result.sessionHash = nil
        }
        if !result.hasValidPending(now: now) {
            result.pendingAccountUserId = nil
            result.pendingStartedAt = nil
        }
        return result
    }

    public func hasValidPending(now: Int32) -> Bool {
        guard let pendingAccountUserId = self.pendingAccountUserId,
              pendingAccountUserId > 0,
              let pendingStartedAt = self.pendingStartedAt,
              pendingStartedAt > 0 else {
            return false
        }
        return Int64(now) < Int64(pendingStartedAt) + 86_400
    }
}

private struct GRVMNotifyStateEnvelope: Codable {
    let state: GRVMNotifyState

    init(state: GRVMNotifyState) {
        self.state = state
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: StringCodingKey.self)
        let data = try container.decode(Data.self, forKey: "state")
        self.state = try JSONDecoder().decode(GRVMNotifyState.self, from: data)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: StringCodingKey.self)
        let data = try JSONEncoder().encode(self.state)
        try container.encode(data, forKey: "state")
    }
}

public protocol GRVMNotifyStateStoring: AnyObject {
    func state() -> Signal<GRVMNotifyState, NoError>
    func update(_ f: @escaping (GRVMNotifyState) -> GRVMNotifyState) -> Signal<GRVMNotifyState, NoError>
    func writeAndVerify(_ state: GRVMNotifyState) -> Signal<Bool, NoError>
}

public final class GRVMNotifyStateStore: GRVMNotifyStateStoring {
    private let accountManager: AccountManager<TelegramAccountManagerTypes>

    public init(accountManager: AccountManager<TelegramAccountManagerTypes>) {
        self.accountManager = accountManager
    }

    public func state() -> Signal<GRVMNotifyState, NoError> {
        return self.accountManager.sharedData(keys: [ApplicationSpecificSharedDataKeys.grvmNotifyState])
        |> map { sharedData in
            return Self.decode(sharedData.entries[ApplicationSpecificSharedDataKeys.grvmNotifyState])
                .normalized(now: Self.currentTimestamp())
        }
    }

    public func update(_ f: @escaping (GRVMNotifyState) -> GRVMNotifyState) -> Signal<GRVMNotifyState, NoError> {
        return self.accountManager.transaction { transaction -> GRVMNotifyState in
            let now = Self.currentTimestamp()
            let current = Self.decode(
                transaction.getSharedData(ApplicationSpecificSharedDataKeys.grvmNotifyState)
            ).normalized(now: now)
            let updated = f(current).normalized(now: now)
            transaction.updateSharedData(ApplicationSpecificSharedDataKeys.grvmNotifyState, { _ in
                return SharedPreferencesEntry(GRVMNotifyStateEnvelope(state: updated))
            })
            return updated
        }
    }

    public func writeAndVerify(_ state: GRVMNotifyState) -> Signal<Bool, NoError> {
        return self.accountManager.transaction { transaction -> GRVMNotifyState in
            let normalized = state.normalized(now: Self.currentTimestamp())
            transaction.updateSharedData(ApplicationSpecificSharedDataKeys.grvmNotifyState, { _ in
                return SharedPreferencesEntry(GRVMNotifyStateEnvelope(state: normalized))
            })
            return normalized
        }
        |> mapToSignal { [accountManager = self.accountManager] requested in
            return accountManager.sharedData(keys: [ApplicationSpecificSharedDataKeys.grvmNotifyState])
            |> take(1)
            |> map { sharedData in
                let now = Self.currentTimestamp()
                let stored = Self.decode(
                    sharedData.entries[ApplicationSpecificSharedDataKeys.grvmNotifyState]
                ).normalized(now: now)
                return stored == requested.normalized(now: now)
            }
        }
    }

    private static func decode(_ entry: PreferencesEntry?) -> GRVMNotifyState {
        return entry?.get(GRVMNotifyStateEnvelope.self)?.state ?? .empty
    }

    private static func currentTimestamp() -> Int32 {
        return Int32(clamping: Int64(Date().timeIntervalSince1970))
    }
}
