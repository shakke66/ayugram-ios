import Foundation
import Postbox
import SwiftSignalKit
import TelegramCore
import TelegramUIPreferences

public struct GRVMAccountSettings: Codable, Equatable {
    public var settings: AyuGramSettings

    public init(settings: AyuGramSettings) {
        self.settings = settings
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: StringCodingKey.self)
        let data = try container.decode(Data.self, forKey: "settings")
        self.settings = try JSONDecoder().decode(AyuGramSettings.self, from: data)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: StringCodingKey.self)
        let data = try JSONEncoder().encode(self.settings)
        try container.encode(data, forKey: "settings")
    }
}

private struct LegacyGRVMAccountSettings: Decodable {
    let values: [Int64: AyuGramSettings]

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: StringCodingKey.self)
        if let data = try? container.decode(Data.self, forKey: "values"),
           let values = try? JSONDecoder().decode([Int64: AyuGramSettings].self, from: data) {
            self.values = values
        } else {
            self.values = (try? container.decode([Int64: AyuGramSettings].self, forKey: "values")) ?? [:]
        }
    }
}

public func grvmSettings(
    accountId: PeerId,
    accountManager: AccountManager<TelegramAccountManagerTypes>
) -> Signal<AyuGramSettings, NoError> {
    _ = accountId
    return accountManager.sharedData(keys: [
        ApplicationSpecificSharedDataKeys.grvmAccountSettings,
        ApplicationSpecificSharedDataKeys.ayuGramSettings
    ])
    |> map { sharedData in
        if let envelope = sharedData.entries[ApplicationSpecificSharedDataKeys.grvmAccountSettings]?.get(GRVMAccountSettings.self) {
            return envelope.settings
        }
        return sharedData.entries[ApplicationSpecificSharedDataKeys.ayuGramSettings]?.get(AyuGramSettings.self) ?? .defaultSettings
    }
}

public func updateGRVMSettings(
    accountId: PeerId,
    accountManager: AccountManager<TelegramAccountManagerTypes>,
    _ f: @escaping (AyuGramSettings) -> AyuGramSettings
) -> Signal<Void, NoError> {
    _ = accountId
    return accountManager.transaction { transaction -> Void in
        transaction.updateSharedData(ApplicationSpecificSharedDataKeys.grvmAccountSettings, { entry in
            let currentSettings = entry?.get(GRVMAccountSettings.self)?.settings
                ?? transaction.getSharedData(ApplicationSpecificSharedDataKeys.ayuGramSettings)?.get(AyuGramSettings.self)
                ?? .defaultSettings
            return SharedPreferencesEntry(GRVMAccountSettings(settings: f(currentSettings)))
        })
    }
}

public func migrateGRVMSettings(
    accountIds: [PeerId],
    primaryAccountId: PeerId?,
    accountManager: AccountManager<TelegramAccountManagerTypes>
) -> Signal<Void, NoError> {
    return accountManager.transaction { transaction -> Void in
        let existingEntry = transaction.getSharedData(ApplicationSpecificSharedDataKeys.grvmAccountSettings)
        if existingEntry?.get(GRVMAccountSettings.self) != nil {
            return
        }
        let legacyValues = existingEntry?.get(LegacyGRVMAccountSettings.self)?.values ?? [:]
        let primarySettings = primaryAccountId.flatMap { legacyValues[$0.toInt64()] }
        let fallbackSettings = accountIds.map { $0.toInt64() }.sorted()
            .compactMap { legacyValues[$0] }
            .first
        let legacySettings = transaction.getSharedData(ApplicationSpecificSharedDataKeys.ayuGramSettings)?.get(AyuGramSettings.self)
        let settings = primarySettings ?? fallbackSettings ?? legacySettings ?? .defaultSettings
        transaction.updateSharedData(ApplicationSpecificSharedDataKeys.grvmAccountSettings, { _ in
            return SharedPreferencesEntry(GRVMAccountSettings(settings: settings))
        })
    }
}
