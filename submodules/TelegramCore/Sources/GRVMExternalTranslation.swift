import Foundation
import SwiftSignalKit

private enum GRVMExternalTranslationParsingError: Error {
    case invalidResponse
}

private final class GRVMGoogleRequestSchedulerItem {
    let signal: Signal<String, TranslationError>
    let next: (String) -> Void
    let error: (TranslationError) -> Void
    let completion: () -> Void
    var isActive = false
    var disposable: Disposable?

    init(
        signal: Signal<String, TranslationError>,
        next: @escaping (String) -> Void,
        error: @escaping (TranslationError) -> Void,
        completion: @escaping () -> Void
    ) {
        self.signal = signal
        self.next = next
        self.error = error
        self.completion = completion
    }

    deinit {
        self.disposable?.dispose()
    }
}

private final class GRVMGoogleRequestSchedulerImpl {
    private let queue: Queue
    private let maxConcurrentRequests: Int
    private var items: [GRVMGoogleRequestSchedulerItem] = []

    init(queue: Queue, maxConcurrentRequests: Int) {
        self.queue = queue
        self.maxConcurrentRequests = maxConcurrentRequests
    }

    func add(
        signal: Signal<String, TranslationError>,
        next: @escaping (String) -> Void,
        error: @escaping (TranslationError) -> Void,
        completion: @escaping () -> Void
    ) -> Disposable {
        let queue = self.queue
        let item = GRVMGoogleRequestSchedulerItem(
            signal: signal,
            next: next,
            error: error,
            completion: completion
        )
        self.items.append(item)
        self.update()

        return ActionDisposable { [weak self, weak item] in
            queue.async {
                guard let strongSelf = self, let item else {
                    return
                }
                for i in 0 ..< strongSelf.items.count {
                    if strongSelf.items[i] === item {
                        item.disposable?.dispose()
                        strongSelf.items.remove(at: i)
                        strongSelf.update()
                        break
                    }
                }
            }
        }
    }

    private func update() {
        let queue = self.queue
        var activeCount = self.items.reduce(into: 0) { count, item in
            if item.isActive {
                count += 1
            }
        }

        while activeCount < self.maxConcurrentRequests {
            guard let item = self.items.first(where: { !$0.isActive }) else {
                break
            }
            item.isActive = true
            activeCount += 1
            item.disposable = item.signal.start(next: { [weak item] value in
                queue.async {
                    item?.next(value)
                }
            }, error: { [weak self, weak item] value in
                queue.async {
                    guard let strongSelf = self, let item else {
                        return
                    }
                    for i in 0 ..< strongSelf.items.count {
                        if strongSelf.items[i] === item {
                            strongSelf.items.remove(at: i)
                            item.error(value)
                            strongSelf.update()
                            break
                        }
                    }
                }
            }, completed: { [weak self, weak item] in
                queue.async {
                    guard let strongSelf = self, let item else {
                        return
                    }
                    for i in 0 ..< strongSelf.items.count {
                        if strongSelf.items[i] === item {
                            strongSelf.items.remove(at: i)
                            item.completion()
                            strongSelf.update()
                            break
                        }
                    }
                }
            })
        }
    }
}

private final class GRVMGoogleRequestScheduler {
    private let queue: Queue
    private let impl: QueueLocalObject<GRVMGoogleRequestSchedulerImpl>

    init(maxConcurrentRequests: Int) {
        let queue = Queue(name: "GRVMGoogleRequestScheduler")
        self.queue = queue
        self.impl = QueueLocalObject(queue: queue, generate: {
            return GRVMGoogleRequestSchedulerImpl(
                queue: queue,
                maxConcurrentRequests: maxConcurrentRequests
            )
        })
    }

    func wrap(_ signal: Signal<String, TranslationError>) -> Signal<String, TranslationError> {
        return Signal { subscriber in
            let disposable = MetaDisposable()
            self.impl.with { impl in
                disposable.set(impl.add(signal: signal, next: { value in
                    subscriber.putNext(value)
                }, error: { error in
                    subscriber.putError(error)
                }, completion: {
                    subscriber.putCompletion()
                }))
            }
            return disposable
        }
    }
}

private let grvmGoogleRequestScheduler = GRVMGoogleRequestScheduler(maxConcurrentRequests: 4)

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
    let requests = texts.map { text in
        grvmGoogleTranslate(text: text, toLang: toLang)
    }
    return combineLatest(requests)
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
    let signal = grvmExternalTranslationRequest(request)
    |> mapToSignal { data in
        do {
            return .single(try grvmParseGoogleTranslation(data))
        } catch {
            return .fail(.generic)
        }
    }
    return grvmGoogleRequestScheduler.wrap(signal)
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
