import AyuGramLib
import Emoji
import Foundation
import Postbox
import TelegramCore

public final class GRVMMessageFilterEngine {
    public let accountPeerId: PeerId
    let settings: AyuGramSettings
    let blockedPeerIds: Set<PeerId>

    private struct CompiledFilter {
        let filter: AyuMessageFilter
        let regularExpression: NSRegularExpression?

        func matches(_ candidate: String) -> Bool {
            guard let regularExpression else {
                return false
            }
            return regularExpression.firstMatch(
                in: candidate,
                range: NSRange(candidate.startIndex..., in: candidate)
            ) != nil
        }
    }

    private let shadowBanPeerIds: Set<PeerId>
    private let compiledFilters: [CompiledFilter]

    public init(
        accountPeerId: PeerId,
        settings: AyuGramSettings,
        blockedPeerIds: Set<PeerId>
    ) {
        self.accountPeerId = accountPeerId
        self.settings = settings
        self.blockedPeerIds = blockedPeerIds
        self.shadowBanPeerIds = Set(GRVMShadowBanPolicy.normalizedPeerIds(
            settings.shadowBanIds,
            accountPeerId: accountPeerId.toInt64()
        ).map(PeerId.init))

        var compiledFilters: [CompiledFilter] = []
        for filter in settings.filters {
            guard filter.isEnabled else {
                continue
            }
            var options: NSRegularExpression.Options = [.anchorsMatchLines]
            if filter.isCaseInsensitive {
                options.insert(.caseInsensitive)
            }
            compiledFilters.append(CompiledFilter(
                filter: filter,
                regularExpression: try? NSRegularExpression(pattern: filter.expression, options: options)
            ))
        }
        self.compiledFilters = compiledFilters
    }

    public func isShadowBanned(_ peerId: PeerId) -> Bool {
        return self.settings.enableFilters
            && peerId != self.accountPeerId
            && self.shadowBanPeerIds.contains(peerId)
    }

    public func matchingFilterIds(for message: Message) -> [String] {
        guard self.settings.enableFilters,
              message.effectivelyIncoming(self.accountPeerId) else {
            return []
        }
        let candidate = self.candidate(for: message)
        return self.compiledFilters.compactMap { filter in
            guard self.isApplicable(filter.filter, chatPeerId: message.id.peerId),
                  filter.matches(candidate) else {
                return nil
            }
            return filter.filter.id.uuidString
        }
    }

    public func isMessageHidden(_ message: Message) -> Bool {
        var visitedMessageIds = Set<MessageId>()
        return self.isMessageHidden(message, visitedMessageIds: &visitedMessageIds)
    }

    private func isMessageHidden(_ message: Message, visitedMessageIds: inout Set<MessageId>) -> Bool {
        guard self.settings.enableFilters,
              message.effectivelyIncoming(self.accountPeerId) else {
            return false
        }
        guard visitedMessageIds.insert(message.id).inserted else {
            return false
        }

        var senderPeerIds = Set<PeerId>()
        if let authorId = message.author?.id {
            senderPeerIds.insert(authorId)
        }
        if let forwardedAuthorId = message.forwardInfo?.author?.id {
            senderPeerIds.insert(forwardedAuthorId)
        }
        if let originalAuthorId = message.sourceAuthorInfo?.originalAuthor {
            senderPeerIds.insert(originalAuthorId)
        }
        if !senderPeerIds.isDisjoint(with: self.shadowBanPeerIds) {
            return true
        }
        if self.settings.hideFromBlockedUsers
            && !senderPeerIds.isDisjoint(with: self.blockedPeerIds) {
            return true
        }

        let applicableFilters = self.compiledFilters.filter {
            $0.regularExpression != nil
                && self.isApplicable($0.filter, chatPeerId: message.id.peerId)
        }
        let applicableNormalFilters = applicableFilters.filter { !$0.filter.isReversed }
        let applicableReversedFilters = applicableFilters.filter { $0.filter.isReversed }
        let candidate = self.candidate(for: message)

        if applicableNormalFilters.contains(where: { $0.matches(candidate) }) {
            return true
        }
        if !applicableReversedFilters.isEmpty
            && !applicableReversedFilters.contains(where: { $0.matches(candidate) }) {
            return true
        }
        for attribute in message.attributes {
            guard let replyAttribute = attribute as? ReplyMessageAttribute,
                  let replyMessage = message.associatedMessages[replyAttribute.messageId] else {
                continue
            }
            if self.isMessageHidden(replyMessage, visitedMessageIds: &visitedMessageIds) {
                return true
            }
        }
        return false
    }

    private func isApplicable(_ filter: AyuMessageFilter, chatPeerId: PeerId) -> Bool {
        if filter.excludedPeerIds.contains(chatPeerId.toInt64()) {
            return false
        }
        if let peerId = filter.peerId {
            return peerId == chatPeerId.toInt64()
        }
        if chatPeerId.namespace == Namespaces.Peer.CloudChannel {
            return true
        }
        return self.settings.enableFiltersInChats
    }

    private func candidate(for message: Message) -> String {
        var values: [String] = []
        func append(_ value: String) {
            if !value.isEmpty {
                values.append(value)
            }
        }
        func payload(for action: ReplyMarkupButtonAction) -> String {
            switch action {
            case let .url(url):
                return url
            case let .urlAuth(url, _):
                return url
            case let .callback(_, data):
                return String(decoding: data.makeData(), as: UTF8.self)
            case let .switchInline(_, query, _):
                return query
            case let .openWebView(url, _):
                return url
            case let .copyText(payload):
                return payload
            default:
                return ""
            }
        }

        append(message.text)
        let nsText = message.text as NSString
        for attribute in message.attributes {
            if let entities = attribute as? TextEntitiesMessageAttribute {
                for entity in entities.entities {
                    switch entity.type {
                    case .Url:
                        guard entity.range.lowerBound >= 0,
                              entity.range.upperBound <= nsText.length else {
                            continue
                        }
                        let range = NSRange(
                            location: entity.range.lowerBound,
                            length: entity.range.upperBound - entity.range.lowerBound
                        )
                        append(nsText.substring(with: range))
                    case let .TextUrl(url):
                        append(url)
                    default:
                        break
                    }
                }
            } else if let replyMarkup = attribute as? ReplyMarkupMessageAttribute {
                for row in replyMarkup.rows {
                    for button in row.buttons {
                        let buttonPayload = payload(for: button.action)
                        append(button.title)
                        append(buttonPayload)
                        let buttonContent = [button.title, buttonPayload]
                            .filter { !$0.isEmpty }
                            .joined(separator: " ")
                        append("<button>\(buttonContent)</button>")
                    }
                }
            }
        }
        append("<type>\(self.messageType(for: message))</type>")
        return values.joined(separator: "\n")
    }

    private func messageType(for message: Message) -> Int {
        if message.attributes.contains(where: { $0 is AdMessageAttribute }) {
            return 0
        }

        for media in message.media {
            if let action = media as? TelegramMediaAction {
                return self.actionType(action.action)
            } else if media is TelegramMediaPaidContent {
                return 29
            } else if media is TelegramMediaGiveawayResults {
                return 28
            } else if media is TelegramMediaGiveaway {
                return 26
            } else if media is TelegramMediaDice {
                return 15
            } else if media is TelegramMediaImage {
                return 1
            } else if media is TelegramMediaMap {
                return 4
            } else if media is TelegramMediaContact {
                return 12
            } else if media is TelegramMediaPoll || media is TelegramMediaTodo {
                return 17
            } else if let story = media as? TelegramMediaStory {
                return story.isMention ? 24 : 23
            } else if let file = media as? TelegramMediaFile {
                if file.isAnimatedSticker || file.isVideoSticker {
                    return 15
                } else if file.isSticker {
                    return 13
                } else if file.isInstantVideo {
                    return 5
                } else if file.isVoice {
                    return 2
                } else if file.isMusic {
                    return 14
                } else if file.isAnimated {
                    return 8
                } else if file.isVideo {
                    return 3
                } else {
                    return 9
                }
            } else if media is TelegramMediaExpiredContent {
                return 10
            }
        }

        if message.media.contains(where: {
            $0 is TelegramMediaGame || $0 is TelegramMediaInvoice || $0 is TelegramMediaWebpage
        }) {
            return 0
        }
        let emojiText = message.text.filter { !$0.isWhitespace }
        if message.media.isEmpty && emojiText.containsOnlyEmoji {
            return 19
        }
        return 0
    }

    private func actionType(_ action: TelegramMediaActionType) -> Int {
        switch action {
        case let .photoUpdated(image):
            return image == nil ? 10 : 11
        case .suggestedProfilePhoto:
            return 21
        case .setChatWallpaper, .setSameChatWallpaper:
            return 22
        case .phoneCall, .groupPhoneCall, .conferenceCall:
            return 16
        case .inviteToGroupPhoneCall:
            return 16
        case .giftPremium:
            return 18
        case let .giftCode(_, _, _, boostPeerId, _, _, _, _, _, _, _):
            return boostPeerId == nil ? 18 : 25
        case .giftStars, .prizeStars, .starGift, .starGiftUnique, .giftTon:
            return 30
        case .giveawayLaunched:
            return 26
        case .giveawayResults:
            return 28
        default:
            return 10
        }
    }
}
