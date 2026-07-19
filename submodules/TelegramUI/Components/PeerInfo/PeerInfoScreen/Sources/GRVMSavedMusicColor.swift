import Foundation
import UIKit
import Postbox
import TelegramCore
import TelegramPresentationData
import SwiftSignalKit

enum GRVMSavedMusicColor {
    private static let colorCache = Atomic<[String: UIColor]>(value: [:])
    private static let colorCacheLimit = 64

    static func largestArtworkRepresentation(for file: TelegramMediaFile) -> TelegramMediaImageRepresentation? {
        return file.previewRepresentations.max(by: { lhs, rhs in
            let lhsArea = Int64(lhs.dimensions.width) * Int64(lhs.dimensions.height)
            let rhsArea = Int64(rhs.dimensions.width) * Int64(rhs.dimensions.height)
            return lhsArea < rhsArea
        })
    }

    static func color(
        mediaBox: MediaBox,
        file: TelegramMediaFile,
        completion: @escaping (String, UIColor?) -> Void
    ) -> Disposable {
        guard let representation = self.largestArtworkRepresentation(for: file) else {
            return (Signal<(String, UIColor?), NoError>.single(("", nil))
            |> deliverOnMainQueue).startStrict(next: { result in
                completion(result.0, result.1)
            })
        }

        let resource = representation.resource
        let resourceId = representation.resource.id.stringRepresentation
        if let cachedColor = self.colorCache.with({ $0[resourceId] }) {
            return (Signal<(String, UIColor?), NoError>.single((resourceId, cachedColor))
            |> deliverOnMainQueue).startStrict(next: { result in
                completion(result.0, result.1)
            })
        }

        let result = mediaBox.resourceData(resource, attemptSynchronously: true)
        |> take(1)
        |> map { data -> (String, UIColor?) in
            guard data.complete, let image = UIImage(contentsOfFile: data.path) else {
                return (resourceId, nil)
            }

            let sourceColor = averageColor(from: image)
            var hue: CGFloat = 0.0
            var saturation: CGFloat = 0.0
            var brightness: CGFloat = 0.0
            var alpha: CGFloat = 0.0
            guard sourceColor.getHue(&hue, saturation: &saturation, brightness: &brightness, alpha: &alpha) else {
                return (resourceId, nil)
            }

            let color = UIColor(
                hue: hue,
                saturation: min(0.65, max(0.28, saturation)),
                brightness: min(0.42, max(0.18, brightness)),
                alpha: 1.0
            )
            let _ = self.colorCache.modify { current in
                var updated = current
                if updated[resourceId] == nil && updated.count >= self.colorCacheLimit, let firstKey = updated.keys.first {
                    updated.removeValue(forKey: firstKey)
                }
                updated[resourceId] = color
                return updated
            }
            return (resourceId, color)
        }

        return (result
        |> deliverOnMainQueue).startStrict(next: { result in
            completion(result.0, result.1)
        })
    }
}
