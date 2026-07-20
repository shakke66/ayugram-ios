import Foundation
import Postbox
import SwiftSignalKit
import TelegramCore
import AccountContext

enum GRVMPreservedMediaEnqueueError: Error {
    case unsupported
    case unavailable
}

final class GRVMPreservedMediaEnqueuePayload {
    let message: EnqueueMessage
    private let temporaryFile: URL?
    private var ownsTemporaryFile: Bool

    init(message: EnqueueMessage, temporaryFile: URL?) {
        self.message = message
        self.temporaryFile = temporaryFile
        self.ownsTemporaryFile = temporaryFile != nil
    }

    func transferOwnership() {
        self.ownsTemporaryFile = false
    }

    deinit {
        if self.ownsTemporaryFile, let temporaryFile = self.temporaryFile {
            try? FileManager.default.removeItem(at: temporaryFile)
        }
    }
}

private enum GRVMLocalCopyMedia {
    case image(TelegramMediaImage, TelegramMediaImageRepresentation)
    case file(TelegramMediaFile)

    var resource: MediaResource {
        switch self {
        case let .image(_, representation):
            return representation.resource
        case let .file(file):
            return file.resource
        }
    }
}

private func grvmLocalCopyTextEntities(_ message: Message) -> [MessageTextEntity] {
    let text = message.text
    var entities: [MessageTextEntity] = []
    if let source = message.attributes.first(where: { $0 is TextEntitiesMessageAttribute }) as? TextEntitiesMessageAttribute {
        for entity in source.entities {
            guard entity.range.lowerBound >= 0,
                  entity.range.lowerBound < entity.range.upperBound,
                  entity.range.upperBound <= (text as NSString).length else {
                continue
            }
            switch entity.type {
            case .Mention:
                entities.append(entity)
            case .Hashtag:
                entities.append(entity)
            case .BotCommand:
                entities.append(entity)
            case .Url:
                entities.append(entity)
            case .Email:
                entities.append(entity)
            case .Bold:
                entities.append(entity)
            case .Italic:
                entities.append(entity)
            case .Code:
                entities.append(entity)
            case .Pre:
                entities.append(entity)
            case .TextUrl:
                entities.append(entity)
            case .TextMention:
                entities.append(entity)
            case .PhoneNumber:
                entities.append(entity)
            case .Strikethrough:
                entities.append(entity)
            case .BlockQuote:
                entities.append(entity)
            case .Underline:
                entities.append(entity)
            case .BankCard:
                entities.append(entity)
            case .Spoiler:
                entities.append(entity)
            case .FormattedDate:
                entities.append(entity)
            case .CustomEmoji:
                continue
            default:
                continue
            }
        }
    }
    return entities
}

private func grvmLocalCopyFileAttributes(_ file: TelegramMediaFile) -> [TelegramMediaFileAttribute] {
    var attributes: [TelegramMediaFileAttribute] = []
    for attribute in file.attributes {
        switch attribute {
        case .FileName:
            if case let .FileName(fileName) = attribute {
                attributes.append(.FileName(fileName: fileName))
            }
        case .ImageSize:
            if case let .ImageSize(dimensions) = attribute {
                attributes.append(.ImageSize(size: dimensions))
            }
        case .Sticker:
            if case let .Sticker(displayText, packReference, maskData) = attribute {
                attributes.append(.Sticker(displayText: displayText, packReference: packReference, maskData: maskData))
            }
        case .Animated:
            attributes.append(.Animated)
        case .Video:
            if case let .Video(duration, dimensions, flags, _, _, _) = attribute {
                attributes.append(.Video(duration: duration, size: dimensions, flags: flags, preloadSize: nil, coverTime: nil, videoCodec: nil))
            }
        case .Audio:
            if case let .Audio(isVoice, duration, title, performer, waveform) = attribute {
                attributes.append(.Audio(isVoice: isVoice, duration: duration, title: title, performer: performer, waveform: waveform))
            }
        default:
            break
        }
    }
    return attributes
}

func GRVMPreservedMediaEnqueue(
    context: AccountContext,
    message: Message
) -> Signal<GRVMPreservedMediaEnqueuePayload, GRVMPreservedMediaEnqueueError> {
    return (context.account.postbox.transaction { transaction -> Message? in
        guard let currentMessage = transaction.getMessage(message.id),
              currentMessage.stableId == message.stableId else {
            return nil
        }
        return currentMessage
    }
    |> castError(GRVMPreservedMediaEnqueueError.self))
    |> mapToSignal { freshMessage -> Signal<GRVMPreservedMediaEnqueuePayload, GRVMPreservedMediaEnqueueError> in
    guard let message = freshMessage else {
        return .fail(.unavailable)
    }
    let marker = message.attributes.first(where: {
        $0 is GRVMPreservedConsumableMediaAttribute
    }) as? GRVMPreservedConsumableMediaAttribute
    let media: [Media]
    if message.media.contains(where: { $0 is TelegramMediaExpiredContent }) {
        guard let marker else {
            return .fail(.unavailable)
        }
        media = marker.media
    } else {
        media = message.media
    }
    guard media.count <= 1 else {
        return .fail(.unsupported)
    }
    let textEntities = grvmLocalCopyTextEntities(message)
    var messageAttributes: [MessageAttribute] = []
    if !textEntities.isEmpty {
        messageAttributes.append(TextEntitiesMessageAttribute(entities: textEntities))
    }
    if media.isEmpty {
        guard !message.text.isEmpty else {
            return .fail(.unsupported)
        }
        let enqueueMessage: EnqueueMessage = .message(
            text: message.text,
            attributes: messageAttributes,
            inlineStickers: [:],
            mediaReference: nil,
            threadId: nil,
            replyToMessageId: nil,
            replyToStoryId: nil,
            localGroupingKey: nil,
            correlationId: nil,
            bubbleUpEmojiOrStickersets: []
        )
        return .single(GRVMPreservedMediaEnqueuePayload(
            message: enqueueMessage,
            temporaryFile: nil
        ))
    }
    guard media.count == 1 else {
        return .fail(.unsupported)
    }

    let localCopyMedia: GRVMLocalCopyMedia
    if let image = media[0] as? TelegramMediaImage,
       let representation = largestImageRepresentation(image.representations) {
        localCopyMedia = .image(image, representation)
    } else if let file = media[0] as? TelegramMediaFile {
        localCopyMedia = .file(file)
    } else {
        return .fail(.unsupported)
    }

    let restoration: Signal<Bool, NoError>
    if let path = context.account.postbox.mediaBox.completedResourcePath(id: localCopyMedia.resource.id),
       let byteCount = (try? FileManager.default.attributesOfItem(atPath: path)[.size]) as? NSNumber,
       byteCount.int64Value > 0 {
        restoration = .single(true)
    } else {
        restoration = AyuGramHooks.restoreConsumableMedia?(
            context.account.peerId,
            message
        ) ?? .single(false)
    }

    return (restoration
    |> castError(GRVMPreservedMediaEnqueueError.self)
    |> deliverOn(Queue.concurrentDefaultQueue()))
    |> mapToSignal { restored in
        guard restored else {
            return .fail(.unavailable)
        }
        guard let source = context.account.postbox.mediaBox.completedResourcePath(id: localCopyMedia.resource.id).map({
            URL(fileURLWithPath: $0)
        }) else {
            return .fail(.unavailable)
        }
        guard let sizeValue = (try? FileManager.default.attributesOfItem(atPath: source.path)[.size]) as? NSNumber else {
            return .fail(.unavailable)
        }
        let size = sizeValue.int64Value
        guard size > 0 else {
            return .fail(.unavailable)
        }

        let temp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        do {
            try FileManager.default.linkItem(at: source, to: temp)
        } catch {
            do {
                try FileManager.default.copyItem(at: source, to: temp)
            } catch {
                try? FileManager.default.removeItem(at: temp)
                return .fail(.unavailable)
            }
        }

        let mediaId = Int64.random(in: Int64.min ... Int64.max)
        let localResource = LocalFileReferenceMediaResource(
            localFilePath: temp.path,
            randomId: mediaId,
            isUniquelyReferencedTemporaryFile: true,
            size: size
        )
        switch localCopyMedia {
        case let .image(_, representation):
            let clone = TelegramMediaImage(
                imageId: MediaId(namespace: Namespaces.Media.LocalImage, id: mediaId),
                representations: [TelegramMediaImageRepresentation(
                    dimensions: representation.dimensions,
                    resource: localResource,
                    progressiveSizes: [],
                    immediateThumbnailData: nil,
                    hasVideo: false,
                    isPersonal: false
                )],
                videoRepresentations: [],
                immediateThumbnailData: nil,
                emojiMarkup: nil,
                reference: nil,
                partialReference: nil,
                flags: [],
                video: nil
            )
            let enqueueMessage: EnqueueMessage = .message(
                text: message.text,
                attributes: messageAttributes,
                inlineStickers: [:],
                mediaReference: .standalone(media: clone),
                threadId: nil,
                replyToMessageId: nil,
                replyToStoryId: nil,
                localGroupingKey: nil,
                correlationId: nil,
                bubbleUpEmojiOrStickersets: []
            )
            return .single(GRVMPreservedMediaEnqueuePayload(
                message: enqueueMessage,
                temporaryFile: temp
            ))
        case let .file(file):
            let clone = TelegramMediaFile(
                fileId: MediaId(namespace: Namespaces.Media.LocalFile, id: mediaId),
                partialReference: nil,
                resource: localResource,
                previewRepresentations: [],
                videoThumbnails: [],
                videoCover: nil,
                immediateThumbnailData: nil,
                mimeType: file.mimeType,
                size: size,
                attributes: grvmLocalCopyFileAttributes(file),
                alternativeRepresentations: []
            )
            let enqueueMessage: EnqueueMessage = .message(
                text: message.text,
                attributes: messageAttributes,
                inlineStickers: [:],
                mediaReference: .standalone(media: clone),
                threadId: nil,
                replyToMessageId: nil,
                replyToStoryId: nil,
                localGroupingKey: nil,
                correlationId: nil,
                bubbleUpEmojiOrStickersets: []
            )
            return .single(GRVMPreservedMediaEnqueuePayload(
                message: enqueueMessage,
                temporaryFile: temp
            ))
        }
    }
    }
}
