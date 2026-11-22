import Foundation
import Postbox

public struct GRVMEditableMediaId: Codable, Equatable {
    public let namespace: Int32
    public let id: Int64

    init(_ id: MediaId) {
        self.namespace = id.namespace
        self.id = id.id
    }
}

public struct GRVMEditableDimensions: Codable, Equatable {
    public let width: Int32
    public let height: Int32

    init(_ dimensions: PixelDimensions) {
        self.width = dimensions.width
        self.height = dimensions.height
    }
}

public struct GRVMEditableMediaRepresentation: Codable, Equatable {
    public let dimensions: GRVMEditableDimensions
    public let resourceId: String
    public let startTimestamp: Double?
}

public enum GRVMEditableStickerPackReference: Codable, Equatable {
    case id(Int64)
    case name(String)
    case animatedEmoji
    case dice(String)
    case animatedEmojiAnimations
    case premiumGifts
    case emojiGenericAnimations
    case iconStatusEmoji
    case iconTopicEmoji
    case iconChannelStatusEmoji
    case tonGifts
}

public struct GRVMEditableStickerMask: Codable, Equatable {
    public let n: Int32
    public let x: Double
    public let y: Double
    public let zoom: Double
}

public enum GRVMEditableFileAttribute: Codable, Equatable {
    case fileName(String)
    case sticker(String, GRVMEditableStickerPackReference?, GRVMEditableStickerMask?)
    case imageSize(GRVMEditableDimensions)
    case animated
    case video(Double, GRVMEditableDimensions, Int32, Double?, String?)
    case audio(Bool, Int, String?, String?)
    case customEmoji(Bool, Bool, String, GRVMEditableStickerPackReference?)
}

public struct GRVMEditableTodoItem: Codable, Equatable {
    public let id: Int32
    public let text: String
    public let entities: [MessageTextEntity]
}

public struct GRVMEditableTodoContent: Codable, Equatable {
    public let flags: Int32
    public let text: String
    public let entities: [MessageTextEntity]
    public let items: [GRVMEditableTodoItem]
}

public enum GRVMEditablePollKind: Codable, Equatable {
    case poll(multipleAnswers: Bool)
    case quiz(multipleAnswers: Bool)
}

public struct GRVMEditablePollOption: Codable, Equatable {
    public let text: String
    public let entities: [MessageTextEntity]
    public let opaqueIdentifier: Data
    public let media: GRVMEditableMediaContent?
}

public struct GRVMEditablePollContent: Codable, Equatable {
    public let id: GRVMEditableMediaId
    public let publicity: Int32
    public let kind: GRVMEditablePollKind
    public let text: String
    public let entities: [MessageTextEntity]
    public let options: [GRVMEditablePollOption]
    public let correctAnswers: [Data]?
    public let isClosed: Bool
    public let deadlineTimeout: Int32?
    public let deadlineDate: Int32?
    public let openAnswers: Bool
    public let revotingDisabled: Bool
    public let shuffleAnswers: Bool
    public let hideResultsUntilClose: Bool
    public let attachedMedia: GRVMEditableMediaContent?
}

public struct GRVMEditableFileContent: Codable, Equatable {
    public let id: GRVMEditableMediaId
    public let resourceId: String
    public let previewRepresentations: [GRVMEditableMediaRepresentation]
    public let videoThumbnails: [GRVMEditableMediaRepresentation]
    public let videoCover: GRVMEditableMediaContent?
    public let mimeType: String
    public let size: Int64?
    public let attributes: [GRVMEditableFileAttribute]
    public let alternativeRepresentations: [GRVMEditableMediaContent]
}

public enum GRVMEditableImageMarkupContent: Codable, Equatable {
    case emoji(Int64)
    case sticker(GRVMEditableStickerPackReference, Int64)
}

public struct GRVMEditableImageMarkup: Codable, Equatable {
    public let content: GRVMEditableImageMarkupContent
    public let backgroundColors: [Int32]
}

public struct GRVMEditableImageContent: Codable, Equatable {
    public let id: GRVMEditableMediaId
    public let representations: [GRVMEditableMediaRepresentation]
    public let videoRepresentations: [GRVMEditableMediaRepresentation]
    public let markup: GRVMEditableImageMarkup?
    public let flags: Int32
    public let video: GRVMEditableMediaContent?
}

public struct GRVMEditableGameContent: Codable, Equatable {
    public let id: Int64
    public let name: String
    public let title: String
    public let description: String
    public let image: GRVMEditableMediaContent?
    public let file: GRVMEditableMediaContent?
}

public enum GRVMEditableExtendedMediaContent: Codable, Equatable {
    case preview(GRVMEditableDimensions?, Int32?)
    case full(GRVMEditableMediaContent)
}

public struct GRVMEditablePaidContent: Codable, Equatable {
    public let amount: Int64
    public let media: [GRVMEditableExtendedMediaContent]
}

public struct GRVMEditableContactContent: Codable, Equatable {
    public let firstName: String
    public let lastName: String
    public let phoneNumber: String
    public let peerId: Int64?
    public let vCardData: String?
}

public struct GRVMEditableMapVenue: Codable, Equatable {
    public let title: String
    public let address: String?
    public let provider: String?
    public let id: String?
    public let type: String?
}

public struct GRVMEditableMapAddress: Codable, Equatable {
    public let country: String
    public let state: String?
    public let city: String?
    public let street: String?
}

public struct GRVMEditableMapContent: Codable, Equatable {
    public let latitude: Double
    public let longitude: Double
    public let heading: Int32?
    public let accuracyRadius: Double?
    public let venue: GRVMEditableMapVenue?
    public let address: GRVMEditableMapAddress?
    public let liveBroadcastingTimeout: Int32?
    public let liveProximityNotificationRadius: Int32?
}

public struct GRVMEditableInvoiceContent: Codable, Equatable {
    public let title: String
    public let description: String
    public let currency: String
    public let totalAmount: Int64
    public let startParam: String
    public let flags: Int32
    public let subscriptionPeriod: Int32?
    public let extendedMedia: GRVMEditableExtendedMediaContent?
}

public enum GRVMEditableMediaContent: Codable, Equatable {
    case todo(GRVMEditableTodoContent)
    indirect case poll(GRVMEditablePollContent)
    case webpage(String?)
    indirect case file(GRVMEditableFileContent)
    indirect case image(GRVMEditableImageContent)
    indirect case game(GRVMEditableGameContent)
    indirect case paidContent(GRVMEditablePaidContent)
    case contact(GRVMEditableContactContent)
    case map(GRVMEditableMapContent)
    indirect case invoice(GRVMEditableInvoiceContent)
    case other(String, GRVMEditableMediaId?)
}

public struct GRVMEditableMessageContent: Codable, Equatable {
    public let text: String
    public let attributeData: [Data]
    public let media: [GRVMEditableMediaContent]
    public let scheduledTimestamp: Int32?

    public init(
        text: String,
        attributeData: [Data],
        media: [GRVMEditableMediaContent],
        scheduledTimestamp: Int32?
    ) {
        self.text = text
        self.attributeData = attributeData
        self.media = media
        self.scheduledTimestamp = scheduledTimestamp
    }

    public init(message: Message) {
        self.init(
            text: message.text,
            attributeData: Self.projectAttributes(message.attributes),
            media: message.media.map(Self.projectMedia),
            scheduledTimestamp: Namespaces.Message.allScheduled.contains(message.id.namespace) ? message.timestamp : nil
        )
    }

    public init(message: StoreMessage) {
        self.init(
            text: message.text,
            attributeData: Self.projectAttributes(message.attributes),
            media: message.media.map(Self.projectMedia),
            scheduledTimestamp: Namespaces.Message.allScheduled.contains(message.id.namespace) ? message.timestamp : nil
        )
    }

    public static func legacy(text: String, entitiesData: Data) -> GRVMEditableMessageContent {
        return GRVMEditableMessageContent(
            text: text,
            attributeData: entitiesData.isEmpty ? [] : [entitiesData],
            media: [],
            scheduledTimestamp: nil
        )
    }

    public var textEntities: [MessageTextEntity] {
        for data in self.attributeData {
            if let attribute = PostboxDecoder(buffer: MemoryBuffer(data: data)).decodeRootObject()
                as? TextEntitiesMessageAttribute {
                return attribute.entities
            }
        }
        return []
    }

    public func encodedData() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return try encoder.encode(self)
    }

    public static func decode(_ data: Data) throws -> GRVMEditableMessageContent {
        return try JSONDecoder().decode(GRVMEditableMessageContent.self, from: data)
    }

    private static func projectAttributes(_ attributes: [MessageAttribute]) -> [Data] {
        return attributes.compactMap { attribute in
            let isEditable = attribute is TextEntitiesMessageAttribute
                || attribute is ReplyMarkupMessageAttribute
                || attribute is MediaSpoilerMessageAttribute
                || attribute is WebpagePreviewMessageAttribute
                || attribute is InvertMediaMessageAttribute
                || attribute is OutgoingScheduleInfoMessageAttribute
                || attribute is ScheduledRepeatAttribute
            guard isEditable else {
                return nil
            }
            let encoder = PostboxEncoder()
            encoder.encodeRootObject(attribute)
            return encoder.makeData()
        }
    }

    private static func projectMedia(_ media: Media) -> GRVMEditableMediaContent {
        if let todo = media as? TelegramMediaTodo {
            return .todo(GRVMEditableTodoContent(
                flags: todo.flags.rawValue,
                text: todo.text,
                entities: todo.textEntities,
                items: todo.items.map {
                    GRVMEditableTodoItem(id: $0.id, text: $0.text, entities: $0.entities)
                }
            ))
        } else if let poll = media as? TelegramMediaPoll {
            let kind: GRVMEditablePollKind
            switch poll.kind {
            case let .poll(multipleAnswers):
                kind = .poll(multipleAnswers: multipleAnswers)
            case let .quiz(multipleAnswers):
                kind = .quiz(multipleAnswers: multipleAnswers)
            }
            return .poll(GRVMEditablePollContent(
                id: GRVMEditableMediaId(poll.pollId),
                publicity: poll.publicity.rawValue,
                kind: kind,
                text: poll.text,
                entities: poll.textEntities,
                options: poll.options.map {
                    GRVMEditablePollOption(
                        text: $0.text,
                        entities: $0.entities,
                        opaqueIdentifier: $0.opaqueIdentifier,
                        media: $0.media.map(Self.projectMedia)
                    )
                },
                correctAnswers: poll.correctAnswers,
                isClosed: poll.isClosed,
                deadlineTimeout: poll.deadlineTimeout,
                deadlineDate: poll.deadlineDate,
                openAnswers: poll.openAnswers,
                revotingDisabled: poll.revotingDisabled,
                shuffleAnswers: poll.shuffleAnswers,
                hideResultsUntilClose: poll.hideResultsUntilClose,
                attachedMedia: poll.attachedMedia.map(Self.projectMedia)
            ))
        } else if let webpage = media as? TelegramMediaWebpage {
            return .webpage(webpage.content.url)
        } else if let file = media as? TelegramMediaFile {
            return .file(Self.projectFile(file))
        } else if let image = media as? TelegramMediaImage {
            return .image(Self.projectImage(image))
        } else if let game = media as? TelegramMediaGame {
            return .game(GRVMEditableGameContent(
                id: game.gameId,
                name: game.name,
                title: game.title,
                description: game.description,
                image: game.image.map(Self.projectMedia),
                file: game.file.map(Self.projectMedia)
            ))
        } else if let paid = media as? TelegramMediaPaidContent {
            return .paidContent(GRVMEditablePaidContent(
                amount: paid.amount,
                media: paid.extendedMedia.map { item in
                    switch item {
                    case let .preview(dimensions, _, videoDuration):
                        return .preview(dimensions.map(GRVMEditableDimensions.init), videoDuration)
                    case let .full(media):
                        return .full(Self.projectMedia(media))
                    }
                }
            ))
        } else if let contact = media as? TelegramMediaContact {
            return .contact(GRVMEditableContactContent(
                firstName: contact.firstName,
                lastName: contact.lastName,
                phoneNumber: contact.phoneNumber,
                peerId: contact.peerId?.toInt64(),
                vCardData: contact.vCardData
            ))
        } else if let map = media as? TelegramMediaMap {
            return .map(GRVMEditableMapContent(
                latitude: map.latitude,
                longitude: map.longitude,
                heading: map.heading,
                accuracyRadius: map.accuracyRadius,
                venue: map.venue.map {
                    GRVMEditableMapVenue(
                        title: $0.title,
                        address: $0.address,
                        provider: $0.provider,
                        id: $0.id,
                        type: $0.type
                    )
                },
                address: map.address.map {
                    GRVMEditableMapAddress(
                        country: $0.country,
                        state: $0.state,
                        city: $0.city,
                        street: $0.street
                    )
                },
                liveBroadcastingTimeout: map.liveBroadcastingTimeout,
                liveProximityNotificationRadius: map.liveProximityNotificationRadius
            ))
        } else if let invoice = media as? TelegramMediaInvoice {
            return .invoice(GRVMEditableInvoiceContent(
                title: invoice.title,
                description: invoice.description,
                currency: invoice.currency,
                totalAmount: invoice.totalAmount,
                startParam: invoice.startParam,
                flags: invoice.flags.rawValue,
                subscriptionPeriod: invoice.subscriptionPeriod,
                extendedMedia: invoice.extendedMedia.map(Self.projectExtendedMedia)
            ))
        } else {
            return .other(String(describing: type(of: media)), media.id.map(GRVMEditableMediaId.init))
        }
    }

    private static func projectExtendedMedia(
        _ media: TelegramExtendedMedia
    ) -> GRVMEditableExtendedMediaContent {
        switch media {
        case let .preview(dimensions, _, videoDuration):
            return .preview(dimensions.map(GRVMEditableDimensions.init), videoDuration)
        case let .full(media):
            return .full(Self.projectMedia(media))
        }
    }

    private static func projectFile(_ file: TelegramMediaFile) -> GRVMEditableFileContent {
        var attributes: [GRVMEditableFileAttribute] = []
        for attribute in file.attributes {
            switch attribute {
            case let .FileName(fileName):
                attributes.append(.fileName(fileName))
            case let .Sticker(displayText, packReference, maskData):
                attributes.append(.sticker(
                    displayText,
                    packReference.map(Self.projectStickerPackReference),
                    maskData.map { GRVMEditableStickerMask(n: $0.n, x: $0.x, y: $0.y, zoom: $0.zoom) }
                ))
            case let .ImageSize(size):
                attributes.append(.imageSize(GRVMEditableDimensions(size)))
            case .Animated:
                attributes.append(.animated)
            case let .Video(duration, size, flags, _, coverTime, videoCodec):
                attributes.append(.video(duration, GRVMEditableDimensions(size), flags.rawValue, coverTime, videoCodec))
            case let .Audio(isVoice, duration, title, performer, _):
                attributes.append(.audio(isVoice, duration, title, performer))
            case let .CustomEmoji(isPremium, isSingleColor, alt, packReference):
                attributes.append(.customEmoji(
                    isPremium,
                    isSingleColor,
                    alt,
                    packReference.map(Self.projectStickerPackReference)
                ))
            case .HasLinkedStickers, .hintFileIsLarge, .hintIsValidated, .NoPremium:
                break
            }
        }
        return GRVMEditableFileContent(
            id: GRVMEditableMediaId(file.fileId),
            resourceId: file.resource.id.stringRepresentation,
            previewRepresentations: file.previewRepresentations.map {
                GRVMEditableMediaRepresentation(
                    dimensions: GRVMEditableDimensions($0.dimensions),
                    resourceId: $0.resource.id.stringRepresentation,
                    startTimestamp: nil
                )
            },
            videoThumbnails: file.videoThumbnails.map {
                GRVMEditableMediaRepresentation(
                    dimensions: GRVMEditableDimensions($0.dimensions),
                    resourceId: $0.resource.id.stringRepresentation,
                    startTimestamp: nil
                )
            },
            videoCover: file.videoCover.map(Self.projectMedia),
            mimeType: file.mimeType,
            size: file.size,
            attributes: attributes,
            alternativeRepresentations: file.alternativeRepresentations.map(Self.projectMedia)
        )
    }

    private static func projectImage(_ image: TelegramMediaImage) -> GRVMEditableImageContent {
        let markup: GRVMEditableImageMarkup?
        if let value = image.emojiMarkup {
            let content: GRVMEditableImageMarkupContent
            switch value.content {
            case let .emoji(fileId):
                content = .emoji(fileId)
            case let .sticker(packReference, fileId):
                content = .sticker(Self.projectStickerPackReference(packReference), fileId)
            }
            markup = GRVMEditableImageMarkup(content: content, backgroundColors: value.backgroundColors)
        } else {
            markup = nil
        }
        return GRVMEditableImageContent(
            id: GRVMEditableMediaId(image.imageId),
            representations: image.representations.map {
                GRVMEditableMediaRepresentation(
                    dimensions: GRVMEditableDimensions($0.dimensions),
                    resourceId: $0.resource.id.stringRepresentation,
                    startTimestamp: nil
                )
            },
            videoRepresentations: image.videoRepresentations.map {
                GRVMEditableMediaRepresentation(
                    dimensions: GRVMEditableDimensions($0.dimensions),
                    resourceId: $0.resource.id.stringRepresentation,
                    startTimestamp: $0.startTimestamp
                )
            },
            markup: markup,
            flags: image.flags.rawValue,
            video: image.video.map(Self.projectMedia)
        )
    }

    private static func projectStickerPackReference(
        _ reference: StickerPackReference
    ) -> GRVMEditableStickerPackReference {
        switch reference {
        case let .id(id, _):
            return .id(id)
        case let .name(value):
            return .name(value)
        case .animatedEmoji:
            return .animatedEmoji
        case let .dice(value):
            return .dice(value)
        case .animatedEmojiAnimations:
            return .animatedEmojiAnimations
        case .premiumGifts:
            return .premiumGifts
        case .emojiGenericAnimations:
            return .emojiGenericAnimations
        case .iconStatusEmoji:
            return .iconStatusEmoji
        case .iconTopicEmoji:
            return .iconTopicEmoji
        case .iconChannelStatusEmoji:
            return .iconChannelStatusEmoji
        case .tonGifts:
            return .tonGifts
        }
    }
}
