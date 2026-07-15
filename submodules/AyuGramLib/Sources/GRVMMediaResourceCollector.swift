import Postbox
import TelegramCore

public struct GRVMMediaResourceReference {
    public let id: MediaResourceId
    public let kind: String

    public init(id: MediaResourceId, kind: String) {
        self.id = id
        self.kind = kind
    }
}

public func grvmMediaResources(_ media: [Media]) -> [GRVMMediaResourceReference] {
    var seen = Set<MediaResourceId>()
    var result: [GRVMMediaResourceReference] = []

    func append(_ resource: MediaResource, kind: String) {
        if seen.insert(resource.id).inserted {
            result.append(GRVMMediaResourceReference(id: resource.id, kind: kind))
        }
    }

    func visit(_ media: Media) {
        if let image = media as? TelegramMediaImage {
            for representation in image.representations {
                append(representation.resource, kind: "image")
            }
            for representation in image.videoRepresentations {
                append(representation.resource, kind: "video")
            }
            if let video = image.video {
                visit(video)
            }
        } else if let file = media as? TelegramMediaFile {
            append(file.resource, kind: "file")
            for representation in file.previewRepresentations {
                append(representation.resource, kind: "image")
            }
            for thumbnail in file.videoThumbnails {
                append(thumbnail.resource, kind: "videoThumbnail")
            }
            if let videoCover = file.videoCover {
                visit(videoCover)
            }
            for alternative in file.alternativeRepresentations {
                visit(alternative)
            }
        } else if let webpage = media as? TelegramMediaWebpage {
            if case let .Loaded(content) = webpage.content {
                if let image = content.image {
                    visit(image)
                }
                if let file = content.file {
                    visit(file)
                }
            }
        } else if let game = media as? TelegramMediaGame {
            if let image = game.image {
                visit(image)
            }
            if let file = game.file {
                visit(file)
            }
        } else if let paidContent = media as? TelegramMediaPaidContent {
            for extendedMedia in paidContent.extendedMedia {
                if case let .full(media) = extendedMedia {
                    visit(media)
                }
            }
        }
    }

    for item in media {
        visit(item)
    }
    return result
}
