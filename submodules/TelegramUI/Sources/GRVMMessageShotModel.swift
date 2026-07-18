import Foundation
import UIKit
import Postbox
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import TelegramUIPreferences
import TelegramStringFormatting
import TextFormat
import LocalizedPeerData

public enum GRVMMessageShotModelError: Error {
    case mixedPeers
    case noAvailableMessages
}

public enum GRVMMessageShotDirection {
    case incoming
    case outgoing
}

public struct GRVMMessageShotHeader {
    public let peerId: PeerId?
    public let authorName: String
    public let authorRank: String?
    public let authorSignature: String?
    public let boostCount: Int?

    public init(peerId: PeerId?, authorName: String, authorRank: String?, authorSignature: String?, boostCount: Int?) {
        self.peerId = peerId
        self.authorName = authorName
        self.authorRank = authorRank
        self.authorSignature = authorSignature
        self.boostCount = boostCount
    }
}

public enum GRVMMessageShotReply {
    case none
    case message(peerId: PeerId?, authorName: String, text: String, entities: [MessageTextEntity], thumbnailData: Data?, hasMedia: Bool, containsSpoilers: Bool)
    case quote(peerId: PeerId?, authorName: String, text: String, entities: [MessageTextEntity], thumbnailData: Data?, hasMedia: Bool, containsSpoilers: Bool)
    case unavailable
}

public enum GRVMMessageShotMediaKind {
    case image
    case video
    case animation
    case sticker
    case voice
    case audio
    case file
    case unsupported
}

public enum GRVMMessageShotMedia {
    case thumbnail(kind: GRVMMessageShotMediaKind, data: Data, dimensions: CGSize?, isSpoiler: Bool)
    case placeholder(kind: GRVMMessageShotMediaKind, title: String, isSpoiler: Bool)
}

public struct GRVMMessageShotReaction {
    public let value: String
    public let count: Int
    public let isCustom: Bool
    public let isSelected: Bool

    public init(value: String, count: Int, isCustom: Bool, isSelected: Bool) {
        self.value = value
        self.count = count
        self.isCustom = isCustom
        self.isSelected = isSelected
    }
}

public struct GRVMMessageShotCapabilities {
    public let hasReactions: Bool
    public let hasReplies: Bool
    public let hasSpoilers: Bool
    public let hasHeaderDecorations: Bool
    public let hasMedia: Bool

    public init(hasReactions: Bool, hasReplies: Bool, hasSpoilers: Bool, hasHeaderDecorations: Bool, hasMedia: Bool) {
        self.hasReactions = hasReactions
        self.hasReplies = hasReplies
        self.hasSpoilers = hasSpoilers
        self.hasHeaderDecorations = hasHeaderDecorations
        self.hasMedia = hasMedia
    }
}

public struct GRVMMessageShotMessage {
    public let id: MessageId
    public let index: MessageIndex
    public let timestamp: Int32
    public let day: String
    public let time: String
    public let direction: GRVMMessageShotDirection
    public let header: GRVMMessageShotHeader
    public let text: String
    public let entities: [MessageTextEntity]
    public let reply: GRVMMessageShotReply
    public let media: [GRVMMessageShotMedia]
    public let reactions: [GRVMMessageShotReaction]
    public let containsSpoilers: Bool

    public init(
        id: MessageId,
        index: MessageIndex,
        timestamp: Int32,
        day: String,
        time: String,
        direction: GRVMMessageShotDirection,
        header: GRVMMessageShotHeader,
        text: String,
        entities: [MessageTextEntity],
        reply: GRVMMessageShotReply,
        media: [GRVMMessageShotMedia],
        reactions: [GRVMMessageShotReaction],
        containsSpoilers: Bool
    ) {
        self.id = id
        self.index = index
        self.timestamp = timestamp
        self.day = day
        self.time = time
        self.direction = direction
        self.header = header
        self.text = text
        self.entities = entities
        self.reply = reply
        self.media = media
        self.reactions = reactions
        self.containsSpoilers = containsSpoilers
    }
}

public struct GRVMMessageShotModel {
    public let accountPeerId: PeerId
    public let peerId: PeerId
    public let threadId: Int64?
    public let chatTitle: String
    public let messages: [GRVMMessageShotMessage]
    public let unavailableSelectedCount: Int
    public let capabilities: GRVMMessageShotCapabilities

    public init(
        accountPeerId: PeerId,
        peerId: PeerId,
        threadId: Int64?,
        chatTitle: String,
        messages: [GRVMMessageShotMessage],
        unavailableSelectedCount: Int,
        capabilities: GRVMMessageShotCapabilities
    ) {
        self.accountPeerId = accountPeerId
        self.peerId = peerId
        self.threadId = threadId
        self.chatTitle = chatTitle
        self.messages = messages
        self.unavailableSelectedCount = unavailableSelectedCount
        self.capabilities = capabilities
    }

    public static func load(
        postbox: Postbox,
        accountPeerId: PeerId,
        peerId: PeerId,
        threadId: Int64?,
        selectedIds: Set<MessageId>,
        strings: PresentationStrings,
        dateTimeFormat: PresentationDateTimeFormat,
        nameDisplayOrder: PresentationPersonNameOrder
    ) -> Signal<Result<GRVMMessageShotModel, GRVMMessageShotModelError>, NoError> {
        return postbox.transaction { transaction -> Result<GRVMMessageShotModel, GRVMMessageShotModelError> in
            do {
                let chatTitle: String
                if let peer = transaction.getPeer(peerId) {
                    chatTitle = EnginePeer(peer).displayTitle(strings: strings, displayOrder: nameDisplayOrder)
                } else {
                    chatTitle = "Chat"
                }

                var messages: [GRVMMessageShotMessage] = []
                var unavailableSelectedCount = 0
                for id in selectedIds {
                    guard id.peerId == peerId else {
                        throw GRVMMessageShotModelError.mixedPeers
                    }
                    guard let message = transaction.getMessage(id) else {
                        unavailableSelectedCount += 1
                        continue
                    }
                    messages.append(self.mapMessage(
                        transaction: transaction,
                        message: message,
                        chatTitle: chatTitle,
                        strings: strings,
                        dateTimeFormat: dateTimeFormat,
                        nameDisplayOrder: nameDisplayOrder
                    ))
                }
                guard !messages.isEmpty else {
                    throw GRVMMessageShotModelError.noAvailableMessages
                }
                messages.sort { $0.index < $1.index }
                return .success(GRVMMessageShotModel(
                    accountPeerId: accountPeerId,
                    peerId: peerId,
                    threadId: threadId,
                    chatTitle: chatTitle,
                    messages: messages,
                    unavailableSelectedCount: unavailableSelectedCount,
                    capabilities: self.capabilities(messages: messages)
                ))
            } catch let error as GRVMMessageShotModelError {
                return .failure(error)
            } catch {
                return .failure(.noAvailableMessages)
            }
        }
    }

    private static func mapMessage(
        transaction: Transaction,
        message: Message,
        chatTitle: String,
        strings: PresentationStrings,
        dateTimeFormat: PresentationDateTimeFormat,
        nameDisplayOrder: PresentationPersonNameOrder
    ) -> GRVMMessageShotMessage {
        let entities = (message.attributes.first(where: { $0 is TextEntitiesMessageAttribute }) as? TextEntitiesMessageAttribute)?.entities ?? []
        let hasTextSpoilers = entities.contains(where: { entity in
            if case .Spoiler = entity.type {
                return true
            }
            return false
        })
        let hasMediaSpoiler = message.attributes.contains(where: { $0 is MediaSpoilerMessageAttribute })

        let authorName: String
        if let author = message.author {
            authorName = EnginePeer(author).displayTitle(strings: strings, displayOrder: nameDisplayOrder)
        } else {
            authorName = chatTitle
        }
        let authorRank = (message.attributes.first(where: { $0 is ParticipantRankMessageAttribute }) as? ParticipantRankMessageAttribute)?.rank
        let authorSignature = (message.attributes.first(where: { $0 is AuthorSignatureMessageAttribute }) as? AuthorSignatureMessageAttribute)?.signature
        let boostCount = (message.attributes.first(where: { $0 is BoostCountMessageAttribute }) as? BoostCountMessageAttribute)?.count
        let header = GRVMMessageShotHeader(
            peerId: message.author?.id,
            authorName: authorName,
            authorRank: authorRank,
            authorSignature: authorSignature,
            boostCount: boostCount
        )

        let reply: GRVMMessageShotReply
        if let replyAttribute = message.attributes.first(where: { $0 is ReplyMessageAttribute }) as? ReplyMessageAttribute {
            if let replyMessage = transaction.getMessage(replyAttribute.messageId) {
                let replyEntities = (replyMessage.attributes.first(where: { $0 is TextEntitiesMessageAttribute }) as? TextEntitiesMessageAttribute)?.entities ?? []
                let replySpoilers = replyEntities.contains(where: { entity in
                    if case .Spoiler = entity.type {
                        return true
                    }
                    return false
                }) || replyMessage.attributes.contains(where: { $0 is MediaSpoilerMessageAttribute })
                let replyAuthorName = replyMessage.author.map {
                    EnginePeer($0).displayTitle(strings: strings, displayOrder: nameDisplayOrder)
                } ?? chatTitle
                reply = .message(
                    peerId: replyMessage.author?.id,
                    authorName: replyAuthorName,
                    text: replyMessage.text,
                    entities: replyEntities,
                    thumbnailData: self.immediateThumbnailData(media: replyMessage.media.first),
                    hasMedia: !replyMessage.media.isEmpty,
                    containsSpoilers: replySpoilers
                )
            } else if let quote = replyAttribute.quote {
                reply = .quote(
                    peerId: nil,
                    authorName: "Quoted reply",
                    text: quote.text,
                    entities: quote.entities,
                    thumbnailData: self.immediateThumbnailData(media: quote.media),
                    hasMedia: quote.media != nil,
                    containsSpoilers: quote.entities.contains(where: { entity in
                        if case .Spoiler = entity.type {
                            return true
                        }
                        return false
                    })
                )
            } else {
                reply = .unavailable
            }
        } else if let quotedAttribute = message.attributes.first(where: { $0 is QuotedReplyMessageAttribute }) as? QuotedReplyMessageAttribute {
            if let quote = quotedAttribute.quote {
                reply = .quote(
                    peerId: quotedAttribute.peerId,
                    authorName: quotedAttribute.authorName ?? "Quoted reply",
                    text: quote.text,
                    entities: quote.entities,
                    thumbnailData: self.immediateThumbnailData(media: quote.media),
                    hasMedia: quote.media != nil,
                    containsSpoilers: quote.entities.contains(where: { entity in
                        if case .Spoiler = entity.type {
                            return true
                        }
                        return false
                    })
                )
            } else {
                reply = .unavailable
            }
        } else {
            reply = .none
        }

        var reactions: [GRVMMessageShotReaction] = []
        if let reactionsAttribute = message.attributes.first(where: { $0 is ReactionsMessageAttribute }) as? ReactionsMessageAttribute {
            reactions = reactionsAttribute.reactions.map { reaction in
                switch reaction.value {
                case let .builtin(value):
                    return GRVMMessageShotReaction(value: value, count: Int(reaction.count), isCustom: false, isSelected: reaction.isSelected)
                case let MessageReaction.Reaction.custom(fileId):
                    return GRVMMessageShotReaction(value: "Custom \(fileId)", count: Int(reaction.count), isCustom: true, isSelected: reaction.isSelected)
                case .stars:
                    return GRVMMessageShotReaction(value: "Stars", count: Int(reaction.count), isCustom: false, isSelected: reaction.isSelected)
                }
            }
        }

        return GRVMMessageShotMessage(
            id: message.id,
            index: message.index,
            timestamp: message.timestamp,
            day: stringForDate(timestamp: message.timestamp, timeZone: .current, strings: strings),
            time: stringForMessageTimestamp(timestamp: message.timestamp, dateTimeFormat: dateTimeFormat),
            direction: message.flags.contains(.Incoming) ? .incoming : .outgoing,
            header: header,
            text: message.text,
            entities: entities,
            reply: reply,
            media: self.mapMedia(message.media, isSpoiler: hasMediaSpoiler),
            reactions: reactions,
            containsSpoilers: hasTextSpoilers || hasMediaSpoiler
        )
    }

    private static func immediateThumbnailData(media: Media?) -> Data? {
        if let image = media as? TelegramMediaImage {
            return image.immediateThumbnailData
        } else if let file = media as? TelegramMediaFile {
            return file.immediateThumbnailData
        }
        return nil
    }

    private static func mapMedia(_ media: [Media], isSpoiler: Bool) -> [GRVMMessageShotMedia] {
        return media.map { item in
            if let image = item as? TelegramMediaImage {
                let dimensions = image.representations.last.map {
                    CGSize(width: CGFloat($0.dimensions.width), height: CGFloat($0.dimensions.height))
                }
                if let data = image.immediateThumbnailData {
                    return .thumbnail(kind: .image, data: data, dimensions: dimensions, isSpoiler: isSpoiler)
                }
                return .placeholder(kind: .image, title: "Photo unavailable", isSpoiler: isSpoiler)
            } else if let file = item as? TelegramMediaFile {
                let kind: GRVMMessageShotMediaKind
                if file.isVideo {
                    kind = .video
                } else if file.isAnimated {
                    kind = .animation
                } else if file.isSticker {
                    kind = .sticker
                } else if file.isVoice {
                    kind = .voice
                } else if file.isMusic {
                    kind = .audio
                } else {
                    kind = .file
                }
                let dimensions = file.dimensions.map {
                    CGSize(width: CGFloat($0.width), height: CGFloat($0.height))
                }
                if let data = file.immediateThumbnailData {
                    return .thumbnail(kind: kind, data: data, dimensions: dimensions, isSpoiler: isSpoiler)
                }
                return .placeholder(kind: kind, title: file.fileName ?? "File unavailable", isSpoiler: isSpoiler)
            }
            return .placeholder(kind: .unsupported, title: "Media unavailable", isSpoiler: isSpoiler)
        }
    }

    private static func capabilities(messages: [GRVMMessageShotMessage]) -> GRVMMessageShotCapabilities {
        return GRVMMessageShotCapabilities(
            hasReactions: messages.contains(where: { !$0.reactions.isEmpty }),
            hasReplies: messages.contains(where: {
                if case .none = $0.reply {
                    return false
                }
                return true
            }),
            hasSpoilers: messages.contains(where: { $0.containsSpoilers }),
            hasHeaderDecorations: messages.contains(where: {
                $0.header.authorRank != nil || $0.header.authorSignature != nil || $0.header.boostCount != nil
            }),
            hasMedia: messages.contains(where: { !$0.media.isEmpty })
        )
    }
}
