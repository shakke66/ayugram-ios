import Foundation
import TelegramCore

public func grvmGhostScheduleDelay(
    messages: [EnqueueMessage],
    proxyEnabled: Bool
) -> Int32 {
    var baseDelay = 12.0

    for message in messages {
        guard case let .message(_, _, _, mediaReference, _, _, _, _, _, _) = message,
              let mediaReference,
              let file = mediaReference.media as? TelegramMediaFile else {
            continue
        }

        if file.isVoice || file.isInstantVideo {
            baseDelay = max(baseDelay, 17.0)
        }

        switch mediaReference {
        case .standalone:
            guard let localResource = file.resource as? LocalFileMediaResource else {
                continue
            }
            guard let resourceSize = localResource.size, resourceSize >= 0 else {
                continue
            }
            let sizeMiB = Double(resourceSize) / 1_048_576.0
            let sizeDelay = ceil(sizeMiB * 0.7)
            let uploadDelay = 13.0 + max(6.0, sizeDelay)
            baseDelay = max(baseDelay, min(Double(Int32.max), max(19.0, uploadDelay)))
        default:
            break
        }
    }

    let result = proxyEnabled ? ceil(baseDelay * 1.2) : baseDelay
    return Int32(min(result, Double(Int32.max)))
}
