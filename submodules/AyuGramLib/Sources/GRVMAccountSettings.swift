import Foundation
import Postbox
import SwiftSignalKit
import TelegramCore
import TelegramUIPreferences

public struct GRVMAccountSettings: Codable, Equatable {
    public var values: [Int64: AyuGramSettings]

    public init(values: [Int64: AyuGramSettings]) {
        self.values = values
    }
}

public func grvmSettings(
    accountId: PeerId,
    accountManager: AccountManager<TelegramAccountManagerTypes>
) -> Signal<AyuGramSettings, NoError> {
    let accountKey = accountId.toInt64()
    return accountManager.sharedData(keys: [
        ApplicationSpecificSharedDataKeys.grvmAccountSettings,
        ApplicationSpecificSharedDataKeys.ayuGramSettings
    ])
    |> map { sharedData in
        if let envelope = sharedData.entries[ApplicationSpecificSharedDataKeys.grvmAccountSettings]?.get(GRVMAccountSettings.self) {
            return envelope.values[accountKey] ?? .defaultSettings
        }
        return sharedData.entries[ApplicationSpecificSharedDataKeys.ayuGramSettings]?.get(AyuGramSettings.self) ?? .defaultSettings
    }
}

public func updateGRVMSettings(
    accountId: PeerId,
    accountManager: AccountManager<TelegramAccountManagerTypes>,
    _ f: @escaping (AyuGramSettings) -> AyuGramSettings
) -> Signal<Void, NoError> {
    let accountKey = accountId.toInt64()
    return accountManager.transaction { transaction -> Void in
        transaction.updateSharedData(ApplicationSpecificSharedDataKeys.grvmAccountSettings, { entry in
            let existingEnvelope = entry?.get(GRVMAccountSettings.self)
            var values = existingEnvelope?.values ?? [:]
            if values[accountKey] == nil {
                if existingEnvelope == nil {
                    values[accountKey] = transaction.getSharedData(ApplicationSpecificSharedDataKeys.ayuGramSettings)?.get(AyuGramSettings.self) ?? .defaultSettings
                } else {
                    values[accountKey] = .defaultSettings
                }
            }
            values[accountKey] = f(values[accountKey] ?? .defaultSettings)
            return SharedPreferencesEntry(GRVMAccountSettings(values: values))
        })
    }
}

public func migrateGRVMSettings(
    accountIds: [PeerId],
    accountManager: AccountManager<TelegramAccountManagerTypes>
) -> Signal<Void, NoError> {
    return accountManager.transaction { transaction -> Void in
        let legacy = transaction.getSharedData(ApplicationSpecificSharedDataKeys.ayuGramSettings)?.get(AyuGramSettings.self) ?? .defaultSettings
        var values = transaction.getSharedData(ApplicationSpecificSharedDataKeys.grvmAccountSettings)?.get(GRVMAccountSettings.self)?.values ?? [:]
        var changed = false
        for accountId in accountIds {
            let accountKey = accountId.toInt64()
            if values[accountKey] == nil {
                values[accountKey] = legacy
                changed = true
            }
        }
        if changed {
            transaction.updateSharedData(ApplicationSpecificSharedDataKeys.grvmAccountSettings, { _ in
                return SharedPreferencesEntry(GRVMAccountSettings(values: values))
            })
        }
    }
}
