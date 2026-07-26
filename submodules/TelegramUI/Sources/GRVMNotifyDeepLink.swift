import Foundation

enum GRVMNotifyPeer: Equatable {
    case user(Int64)
    case group(Int64)
    case channel(Int64)
}

enum GRVMNotifyDeepLink: Equatable {
    case authorize(token: Data, returnURL: URL)
    case openMessage(accountUserId: Int64, peer: GRVMNotifyPeer, messageId: Int32, threadId: Int64?)

    static func parse(_ url: URL) -> GRVMNotifyDeepLink? {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.scheme == "grvmgram",
              components.user == nil,
              components.password == nil,
              components.port == nil,
              components.path.isEmpty,
              components.fragment == nil,
              let items = self.queryItems(from: components),
              items.values.allSatisfy({ $0.count == 1 }) else {
            return nil
        }

        if components.host == "notify-auth" {
            return self.parseAuthorize(items: items)
        } else if components.host == "notify-open" {
            return self.parseOpenMessage(items: items)
        } else {
            return nil
        }
    }

    private struct QueryItem {
        let value: String
        let encodedValue: String
    }

    private static func queryItems(from components: URLComponents) -> [String: [QueryItem]]? {
        guard let encodedQuery = components.percentEncodedQuery, !encodedQuery.isEmpty else {
            return nil
        }

        var result: [String: [QueryItem]] = [:]
        for rawItem in encodedQuery.split(separator: "&", omittingEmptySubsequences: false) {
            let item = String(rawItem)
            guard let separator = item.firstIndex(of: "=") else {
                return nil
            }
            let encodedName = String(item[..<separator])
            let encodedValue = String(item[item.index(after: separator)...])
            guard let name = encodedName.removingPercentEncoding,
                  let value = encodedValue.removingPercentEncoding else {
                return nil
            }
            result[name, default: []].append(QueryItem(value: value, encodedValue: encodedValue))
        }
        return result
    }

    private static func parseAuthorize(items: [String: [QueryItem]]) -> GRVMNotifyDeepLink? {
        guard Set(items.keys) == Set(["token", "return_url"]),
              let tokenItem = items["token"]?[0],
              let returnURLItem = items["return_url"]?[0] else {
            return nil
        }

        let encodedToken = tokenItem.encodedValue
        guard !encodedToken.isEmpty,
              encodedToken.count <= 4_096,
              let token = self.decodeBase64URL(tokenItem.value),
              !token.isEmpty,
              token.count <= 512,
              let returnURL = URL(string: returnURLItem.value),
              let returnComponents = URLComponents(url: returnURL, resolvingAgainstBaseURL: false),
              returnComponents.scheme == "https",
              returnComponents.host == "shakke66.github.io",
              returnComponents.port == nil,
              returnComponents.user == nil,
              returnComponents.password == nil,
              returnComponents.path == "/GRVM-Notify/setup/",
              returnComponents.query == nil,
              returnComponents.fragment == nil else {
            return nil
        }

        return .authorize(token: token, returnURL: returnURL)
    }

    private static func decodeBase64URL(_ value: String) -> Data? {
        guard !value.isEmpty,
              value.utf8.allSatisfy({ byte in
                  return (byte >= 65 && byte <= 90)
                      || (byte >= 97 && byte <= 122)
                      || (byte >= 48 && byte <= 57)
                      || byte == 45
                      || byte == 95
              }),
              value.utf8.count % 4 != 1 else {
            return nil
        }

        var base64 = value
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")
        let paddingCount = (4 - base64.utf8.count % 4) % 4
        if paddingCount != 0 {
            base64.append(String(repeating: "=", count: paddingCount))
        }
        guard let data = Data(base64Encoded: base64) else {
            return nil
        }

        let canonical = data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .trimmingCharacters(in: CharacterSet(charactersIn: "="))
        return canonical == value ? data : nil
    }

    private static func parseOpenMessage(items: [String: [QueryItem]]) -> GRVMNotifyDeepLink? {
        let requiredKeys = Set(["account_user_id", "peer_type", "peer_id", "message_id"])
        let allowedKeys = requiredKeys.union(["thread_id"])
        guard requiredKeys.isSubset(of: Set(items.keys)),
              Set(items.keys).isSubset(of: allowedKeys),
              let accountUserItem = items["account_user_id"]?[0],
              let peerTypeItem = items["peer_type"]?[0],
              let peerIdItem = items["peer_id"]?[0],
              let messageIdItem = items["message_id"]?[0],
              let accountUserId = self.positiveInt64(accountUserItem.value),
              let peerId = self.positiveInt64(peerIdItem.value),
              let messageId = self.positiveInt64(messageIdItem.value),
              let int32MessageId = Int32(exactly: messageId) else {
            return nil
        }

        let peer: GRVMNotifyPeer
        switch peerTypeItem.value {
        case "user":
            peer = .user(peerId)
        case "group":
            peer = .group(peerId)
        case "channel":
            peer = .channel(peerId)
        default:
            return nil
        }

        let threadId: Int64?
        if let threadItem = items["thread_id"]?[0] {
            guard let value = self.positiveInt64(threadItem.value) else {
                return nil
            }
            threadId = value
        } else {
            threadId = nil
        }

        return .openMessage(
            accountUserId: accountUserId,
            peer: peer,
            messageId: int32MessageId,
            threadId: threadId
        )
    }

    private static func positiveInt64(_ value: String) -> Int64? {
        guard !value.isEmpty,
              value.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }),
              let result = Int64(value),
              result > 0 else {
            return nil
        }
        return result
    }
}
