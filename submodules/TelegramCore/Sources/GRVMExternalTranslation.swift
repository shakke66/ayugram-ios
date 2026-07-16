import Foundation
import SwiftSignalKit

private enum GRVMExternalTranslationParsingError: Error {
    case invalidResponse
}

private let maximumConcurrentGoogleRequests = 4

func grvmExternalTranslate(
    texts: [String],
    toLang: String,
    provider: GRVMTranslationProvider
) -> Signal<[String], TranslationError> {
    guard !texts.isEmpty else {
        return .single([])
    }

    switch provider {
    case .telegram:
        return .fail(.generic)
    case .google:
        return grvmGoogleTranslate(texts: texts, toLang: toLang)
    case .yandex:
        return grvmYandexTranslate(texts: texts, toLang: toLang)
    }
}

private func grvmGoogleTranslate(
    texts: [String],
    toLang: String
) -> Signal<[String], TranslationError> {
    var batches: [[String]] = []
    var index = 0
    while index < texts.count {
        let upperBound = min(index + maximumConcurrentGoogleRequests, texts.count)
        batches.append(Array(texts[index ..< upperBound]))
        index = upperBound
    }

    var result: Signal<[String], TranslationError> = .single([])
    for batch in batches {
        result = result
        |> mapToSignal { current in
            let requests = batch.map { text in
                grvmGoogleTranslate(text: text, toLang: toLang)
            }
            return combineLatest(requests)
            |> map { current + $0 }
        }
    }
    return result
    |> mapToSignal { responseTexts in
        guard responseTexts.count == texts.count else {
            return .fail(.generic)
        }
        return .single(responseTexts)
    }
}

private func grvmGoogleTranslate(
    text: String,
    toLang: String
) -> Signal<String, TranslationError> {
    guard !text.isEmpty else {
        return .fail(.generic)
    }

    var components = URLComponents()
    components.scheme = "https"
    components.host = "translate.googleapis.com"
    components.path = "/translate_a/single"
    components.queryItems = [
        URLQueryItem(name: "client", value: "gtx"),
        URLQueryItem(name: "sl", value: "auto"),
        URLQueryItem(name: "tl", value: toLang),
        URLQueryItem(name: "dt", value: "t"),
        URLQueryItem(name: "q", value: text)
    ]
    guard let url = components.url else {
        return .fail(.generic)
    }

    var request = URLRequest(url: url)
    request.httpMethod = "GET"
    request.timeoutInterval = 15.0
    return grvmExternalTranslationRequest(request)
    |> mapToSignal { data in
        do {
            return .single(try grvmParseGoogleTranslation(data))
        } catch {
            return .fail(.generic)
        }
    }
}

private func grvmYandexTranslate(
    texts: [String],
    toLang: String
) -> Signal<[String], TranslationError> {
    var components = URLComponents()
    components.scheme = "https"
    components.host = "translate.yandex.net"
    components.path = "/api/v1/tr.json/translate"
    components.queryItems = [
        URLQueryItem(name: "srv", value: "android"),
        URLQueryItem(name: "id", value: "\(UUID().uuidString)-0-0")
    ]
    guard let url = components.url else {
        return .fail(.generic)
    }

    var form = URLComponents()
    form.queryItems = [URLQueryItem(name: "lang", value: toLang)]
        + texts.map { URLQueryItem(name: "text", value: $0) }
    guard let body = form.percentEncodedQuery?.data(using: .utf8) else {
        return .fail(.generic)
    }

    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.httpBody = body
    request.timeoutInterval = 15.0
    request.setValue(
        "application/x-www-form-urlencoded; charset=utf-8",
        forHTTPHeaderField: "Content-Type"
    )
    return grvmExternalTranslationRequest(request)
    |> mapToSignal { data in
        do {
            let responseTexts = try grvmParseYandexTranslation(data)
            guard responseTexts.count == texts.count,
                  responseTexts.allSatisfy({ !$0.isEmpty }) else {
                return .fail(.generic)
            }
            return .single(responseTexts)
        } catch {
            return .fail(.generic)
        }
    }
}

private func grvmExternalTranslationRequest(
    _ request: URLRequest
) -> Signal<Data, TranslationError> {
    return Signal { subscriber in
        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            guard error == nil,
                  let response = response as? HTTPURLResponse,
                  (200 ..< 300).contains(response.statusCode),
                  let data else {
                subscriber.putError(.generic)
                return
            }
            subscriber.putNext(data)
            subscriber.putCompletion()
        }
        task.resume()
        return ActionDisposable {
            task.cancel()
        }
    }
}

private func grvmParseGoogleTranslation(_ data: Data) throws -> String {
    guard let root = try JSONSerialization.jsonObject(with: data) as? [Any],
          let segments = root.first as? [Any],
          !segments.isEmpty else {
        throw GRVMExternalTranslationParsingError.invalidResponse
    }

    var result = ""
    for value in segments {
        guard let segment = value as? [Any],
              let text = segment.first as? String else {
            throw GRVMExternalTranslationParsingError.invalidResponse
        }
        result.append(text)
    }
    guard !result.isEmpty else {
        throw GRVMExternalTranslationParsingError.invalidResponse
    }
    return result
}

private func grvmParseYandexTranslation(_ data: Data) throws -> [String] {
    guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
          let texts = root["text"] as? [String] else {
        throw GRVMExternalTranslationParsingError.invalidResponse
    }
    return texts
}
