import Foundation
import SwiftSignalKit
import TelegramApi

public enum GRVMNotifySessionFetchError: Error {
    case network
}

func _internal_grvmNotifySessionHashesOnce(account: Account) -> Signal<Set<Int64>, GRVMNotifySessionFetchError> {
    return account.network.request(Api.functions.account.getAuthorizations())
    |> mapError { _ -> GRVMNotifySessionFetchError in
        return .network
    }
    |> map { result -> Set<Int64> in
        switch result {
        case let .authorizations(authorizationsData):
            return Set(authorizationsData.authorizations.map { authorization in
                return RecentAccountSession(apiAuthorization: authorization).hash
            })
        }
    }
}
