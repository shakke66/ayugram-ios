import Foundation
import UIKit
import Postbox
import TelegramCore
import TelegramPresentationData
import TinyThumbnail
import Display

public enum GRVMMessageShotRendererError: Error {
    case invalidCanvas
    case canvasTooLarge
}

public struct GRVMMessageShotPalette {
    public let background: UIColor
    public let incomingBubble: UIColor
    public let outgoingBubble: UIColor
    public let incomingText: UIColor
    public let outgoingText: UIColor
    public let secondaryText: UIColor
    public let separator: UIColor
    public let senderColors: [UIColor]

    static func current(theme: PresentationTheme) -> GRVMMessageShotPalette {
        return GRVMMessageShotPalette(
            background: theme.chat.defaultWallpaper.singleColor ?? theme.list.plainBackgroundColor,
            incomingBubble: theme.chat.message.incoming.bubble.withWallpaper.fill.first ?? theme.list.itemBlocksBackgroundColor,
            outgoingBubble: theme.chat.message.outgoing.bubble.withWallpaper.fill.first ?? theme.list.itemAccentColor,
            incomingText: theme.chat.message.incoming.primaryTextColor,
            outgoingText: theme.chat.message.outgoing.primaryTextColor,
            secondaryText: theme.chat.message.incoming.secondaryTextColor,
            separator: theme.list.itemPlainSeparatorColor,
            senderColors: [
                theme.list.itemAccentColor,
                UIColor(rgb: 0xe17076),
                UIColor(rgb: 0x54a981),
                UIColor(rgb: 0xa56de2),
                UIColor(rgb: 0xd18b3c)
            ]
        )
    }

    static func light(theme: PresentationTheme) -> GRVMMessageShotPalette {
        let current = self.current(theme: theme)
        return GRVMMessageShotPalette(
            background: UIColor(rgb: 0xe7ebee),
            incomingBubble: .white,
            outgoingBubble: UIColor(rgb: 0xd9fdd3),
            incomingText: .black,
            outgoingText: .black,
            secondaryText: UIColor(rgb: 0x6d7883),
            separator: UIColor(rgb: 0xd5d9dc),
            senderColors: current.senderColors
        )
    }

    static func dark(theme: PresentationTheme) -> GRVMMessageShotPalette {
        let current = self.current(theme: theme)
        return GRVMMessageShotPalette(
            background: UIColor(rgb: 0x17212b),
            incomingBubble: UIColor(rgb: 0x202b36),
            outgoingBubble: UIColor(rgb: 0x2b5278),
            incomingText: .white,
            outgoingText: .white,
            secondaryText: UIColor(rgb: 0xa8b2ba),
            separator: UIColor(rgb: 0x34404b),
            senderColors: current.senderColors
        )
    }
}

private struct GRVMMessageShotItemLayout {
    let message: GRVMMessageShotMessage
    let frame: CGRect
    let headerFrame: CGRect?
    let replyFrame: CGRect?
    let mediaFrames: [CGRect]
    let textFrame: CGRect?
    let reactionsFrame: CGRect?
    let timeFrame: CGRect
    let isFirstInGroup: Bool
    let isLastInGroup: Bool
}

private struct GRVMMessageShotLayout {
    let size: CGSize
    let headerFrame: CGRect
    let dateFrames: [(String, CGRect)]
    let items: [GRVMMessageShotItemLayout]
}

private enum GRVMMessageShotReactionKind {
    case builtin
    case custom
}

public final class GRVMMessageShotRenderer {
    public static let canvasWidth: CGFloat = 480.0
    public static let defaultScale: CGFloat = 2.0

    private let model: GRVMMessageShotModel
    private let options: GRVMMessageShotOptions
    private let theme: PresentationTheme
    private let wallpaper: TelegramWallpaper

    public init(model: GRVMMessageShotModel, options: GRVMMessageShotOptions, theme: PresentationTheme, wallpaper: TelegramWallpaper) {
        self.model = model
        self.options = options
        self.theme = theme
        self.wallpaper = wallpaper
    }

    public func render(size: CGSize? = nil, scale: CGFloat = GRVMMessageShotRenderer.defaultScale) throws -> UIImage {
        let layout: GRVMMessageShotLayout
        if let size {
            try Self.validate(size: size, scale: scale)
            let requestedSize = size
            let measuredLayout = try self.measure(width: requestedSize.width)
            guard requestedSize.height >= measuredLayout.size.height else {
                throw GRVMMessageShotRendererError.invalidCanvas
            }
            layout = GRVMMessageShotLayout(
                size: requestedSize,
                headerFrame: measuredLayout.headerFrame,
                dateFrames: measuredLayout.dateFrames,
                items: measuredLayout.items
            )
        } else {
            layout = try self.measure(width: Self.canvasWidth)
        }
        try Self.validate(size: layout.size, scale: scale)

        let format = UIGraphicsImageRendererFormat()
        format.scale = scale
        format.opaque = options.showBackground
        let renderer = UIGraphicsImageRenderer(size: layout.size, format: format)
        return renderer.image { context in
            self.draw(context: context.cgContext, layout: layout, palette: self.palette())
        }
    }

    private func measure(width: CGFloat) throws -> GRVMMessageShotLayout {
        guard width.isFinite && width > 48.0 else {
            throw GRVMMessageShotRendererError.invalidCanvas
        }

        let sideInset: CGFloat = 20.0
        let contentWidth = width - sideInset * 2.0
        let maximumBubbleWidth = contentWidth * 0.75
        let bubbleContentWidth = maximumBubbleWidth - 24.0
        guard bubbleContentWidth > 0.0 else {
            throw GRVMMessageShotRendererError.invalidCanvas
        }
        let textFont = UIFont.systemFont(ofSize: 16.0)
        var y: CGFloat = 18.0
        let headerFrame = CGRect(x: sideInset, y: y, width: contentWidth, height: 34.0)
        y = headerFrame.maxY + 14.0

        var dateFrames: [(String, CGRect)] = []
        var items: [GRVMMessageShotItemLayout] = []
        var previousMessage: GRVMMessageShotMessage?

        for (index, message) in self.model.messages.enumerated() {
            let beginsGroup = !Self.messagesAreGrouped(previousMessage, message)
            if self.options.showDate && (previousMessage == nil || previousMessage?.day != message.day) {
                dateFrames.append((message.day, CGRect(x: sideInset, y: y, width: contentWidth, height: 24.0)))
                y += 32.0
            }
            if previousMessage != nil {
                y += beginsGroup ? 6.0 : 1.0
            }

            let nextMessage = index + 1 < self.model.messages.count ? self.model.messages[index + 1] : nil
            let endsGroup = !Self.messagesAreGrouped(message, nextMessage)
            var cursor = y + 10.0
            var authorFrame: CGRect?
            if self.options.showHeader && beginsGroup {
                authorFrame = CGRect(x: 0.0, y: cursor, width: bubbleContentWidth, height: 18.0)
                cursor += 22.0
            }

            var replyFrame: CGRect?
            if case .none = message.reply {
            } else {
                replyFrame = CGRect(x: 0.0, y: cursor, width: bubbleContentWidth, height: 44.0)
                cursor += 50.0
            }

            var mediaFrames: [CGRect] = []
            for media in message.media {
                let mediaHeight = Self.mediaHeight(media: media, width: bubbleContentWidth)
                let frame = CGRect(x: 0.0, y: cursor, width: bubbleContentWidth, height: mediaHeight)
                mediaFrames.append(frame)
                cursor = frame.maxY + 6.0
            }

            var textFrame: CGRect?
            if !message.text.isEmpty {
                let textHeight = Self.textHeight(message.text, width: bubbleContentWidth, font: textFont)
                textFrame = CGRect(x: 0.0, y: cursor, width: bubbleContentWidth, height: textHeight)
                cursor += textHeight + 5.0
            }

            var reactionsFrame: CGRect?
            if self.options.showReactions && !message.reactions.isEmpty {
                let reactionsHeight = Self.reactionsHeight(message.reactions, width: bubbleContentWidth)
                reactionsFrame = CGRect(x: 0.0, y: cursor, width: bubbleContentWidth, height: reactionsHeight)
                cursor += reactionsHeight + 4.0
            }

            let timeFrame = CGRect(x: 0.0, y: cursor, width: bubbleContentWidth, height: 15.0)
            cursor += 23.0
            let bubbleFrame = CGRect(
                x: message.direction == .incoming ? sideInset : width - sideInset - maximumBubbleWidth,
                y: y,
                width: maximumBubbleWidth,
                height: cursor - y
            )
            let contentOffsetX = bubbleFrame.minX + 12.0
            func offset(_ frame: CGRect?) -> CGRect? {
                return frame?.offsetBy(dx: contentOffsetX, dy: 0.0)
            }
            items.append(GRVMMessageShotItemLayout(
                message: message,
                frame: bubbleFrame,
                headerFrame: offset(authorFrame),
                replyFrame: offset(replyFrame),
                mediaFrames: mediaFrames.map { $0.offsetBy(dx: contentOffsetX, dy: 0.0) },
                textFrame: offset(textFrame),
                reactionsFrame: offset(reactionsFrame),
                timeFrame: timeFrame.offsetBy(dx: contentOffsetX, dy: 0.0),
                isFirstInGroup: beginsGroup,
                isLastInGroup: endsGroup
            ))
            y = bubbleFrame.maxY
            previousMessage = message
        }

        y += 20.0
        return GRVMMessageShotLayout(
            size: CGSize(width: width, height: y),
            headerFrame: headerFrame,
            dateFrames: dateFrames,
            items: items
        )
    }

    private func draw(context: CGContext, layout: GRVMMessageShotLayout, palette: GRVMMessageShotPalette) {
        self.drawBackground(context: context, size: layout.size, palette: palette)
        self.drawText(
            self.model.chatTitle,
            in: layout.headerFrame,
            font: UIFont.boldSystemFont(ofSize: 22.0),
            color: palette.incomingText,
            alignment: .center
        )
        for (date, frame) in layout.dateFrames {
            self.drawText(
                date,
                in: frame,
                font: UIFont.systemFont(ofSize: 13.0, weight: .semibold),
                color: palette.secondaryText,
                alignment: .center
            )
        }

        for item in layout.items {
            let incoming = item.message.direction == .incoming
            let bubbleColor = incoming ? palette.incomingBubble : palette.outgoingBubble
            let textColor = incoming ? palette.incomingText : palette.outgoingText
            let topRadius: CGFloat = item.isFirstInGroup ? 16.0 : 8.0
            let bottomRadius: CGFloat = item.isLastInGroup ? 16.0 : 8.0
            let radius = min(topRadius, bottomRadius)
            context.setFillColor(bubbleColor.cgColor)
            context.addPath(UIBezierPath(roundedRect: item.frame, cornerRadius: radius).cgPath)
            context.fillPath()

            if let frame = item.headerFrame {
                var title = item.message.header.authorName
                if self.options.showHeaderDecorations {
                    let decorations = [
                        item.message.header.authorRank,
                        item.message.header.authorSignature,
                        item.message.header.boostCount.map { "Boost \($0)" }
                    ].compactMap { $0 }
                    if !decorations.isEmpty {
                        title += " | " + decorations.joined(separator: " | ")
                    }
                }
                self.drawText(
                    title,
                    in: frame,
                    font: UIFont.systemFont(ofSize: 14.0, weight: .semibold),
                    color: self.stableColor(peerId: item.message.header.peerId, palette: palette),
                    alignment: .left
                )
            }
            if let frame = item.replyFrame {
                self.drawReply(item.message.reply, frame: frame, palette: palette, textColor: textColor)
            }
            for (index, frame) in item.mediaFrames.enumerated() {
                self.drawMedia(item.message.media[index], frame: frame, palette: palette)
            }
            if let frame = item.textFrame {
                self.drawText(item.message.text, in: frame, font: UIFont.systemFont(ofSize: 16.0), color: textColor, alignment: .left)
                if !options.revealSpoilers {
                    self.drawSpoilers(in: item.message.text, entities: item.message.entities, frame: frame, font: UIFont.systemFont(ofSize: 16.0), color: textColor)
                }
            }
            if let frame = item.reactionsFrame {
                self.drawReactions(item.message.reactions, frame: frame, palette: palette, textColor: textColor)
            }
            self.drawText(item.message.time, in: item.timeFrame, font: UIFont.systemFont(ofSize: 11.0), color: palette.secondaryText, alignment: .right)
        }
    }

    private func drawBackground(context: CGContext, size: CGSize, palette: GRVMMessageShotPalette) {
        let fallbackColor = options.showBackground ? palette.background : UIColor.clear
        guard self.options.showBackground else {
            context.setFillColor(fallbackColor.cgColor)
            context.fill(CGRect(origin: .zero, size: size))
            return
        }

        switch self.wallpaper {
        case let .color(value):
            context.setFillColor(UIColor(rgb: value).cgColor)
            context.fill(CGRect(origin: .zero, size: size))
        case let .gradient(value):
            let colors = value.colors.map { UIColor(rgb: $0).cgColor }
            if colors.count >= 2, let gradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors as CFArray, locations: nil) {
                context.drawLinearGradient(gradient, start: .zero, end: CGPoint(x: size.width, y: size.height), options: [])
            } else {
                context.setFillColor((colors.first ?? palette.background.cgColor))
                context.fill(CGRect(origin: .zero, size: size))
            }
        case .builtin:
            context.setFillColor(palette.background.cgColor)
            context.fill(CGRect(origin: .zero, size: size))
        case .file, .image, .emoticon:
            context.setFillColor(self.unsupportedWallpaperFallback(palette: palette).cgColor)
            context.fill(CGRect(origin: .zero, size: size))
            return
        }
    }

    private func unsupportedWallpaperFallback(palette: GRVMMessageShotPalette) -> UIColor {
        return palette.background
    }

    private func drawReply(_ reply: GRVMMessageShotReply, frame: CGRect, palette: GRVMMessageShotPalette, textColor: UIColor) {
        let accent: UIColor
        let title: String
        let body: String
        let entities: [MessageTextEntity]
        let thumbnailData: Data?
        let hasMedia: Bool
        switch reply {
        case .none:
            return
        case let .message(peerId, authorName, text, replyEntities, data, hasReplyMedia, _):
            accent = self.options.colorfulReplies ? self.stableColor(peerId: peerId, palette: palette) : palette.secondaryText
            title = authorName
            body = text
            entities = replyEntities
            thumbnailData = data
            hasMedia = hasReplyMedia
        case let .quote(peerId, authorName, text, replyEntities, data, hasReplyMedia, _):
            accent = self.options.colorfulReplies ? self.stableColor(peerId: peerId, palette: palette) : palette.secondaryText
            title = authorName
            body = text
            entities = replyEntities
            thumbnailData = data
            hasMedia = hasReplyMedia
        case .unavailable:
            accent = palette.secondaryText
            title = "Reply"
            body = "Message unavailable"
            entities = []
            thumbnailData = nil
            hasMedia = false
        }

        accent.setFill()
        UIBezierPath(roundedRect: CGRect(x: frame.minX, y: frame.minY, width: 3.0, height: frame.height), cornerRadius: 1.5).fill()
        let thumbnailFrame = hasMedia ? CGRect(x: frame.maxX - 36.0, y: frame.minY + 4.0, width: 36.0, height: 36.0) : nil
        let textWidth = max(0.0, (thumbnailFrame?.minX ?? frame.maxX) - frame.minX - 12.0)
        self.drawText(title, in: CGRect(x: frame.minX + 8.0, y: frame.minY, width: textWidth, height: 18.0), font: UIFont.systemFont(ofSize: 13.0, weight: .semibold), color: accent, alignment: .left)
        let bodyFrame = CGRect(x: frame.minX + 8.0, y: frame.minY + 20.0, width: textWidth, height: 20.0)
        let font = UIFont.systemFont(ofSize: 13.0)
        self.drawText(body, in: bodyFrame, font: font, color: textColor, alignment: .left)
        if !options.revealSpoilers {
            self.drawSpoilers(in: body, entities: entities, frame: bodyFrame, font: font, color: textColor)
        }
        if hasMedia, let thumbnailFrame {
            self.drawReplyThumbnail(thumbnailData: thumbnailData, in: thumbnailFrame, palette: palette)
        }
    }

    private func drawReplyThumbnail(thumbnailData: Data?, in frame: CGRect, palette: GRVMMessageShotPalette) {
        palette.separator.setFill()
        UIBezierPath(roundedRect: frame, cornerRadius: 4.0).fill()
        guard let data = thumbnailData,
              let decodedData = decodeTinyThumbnail(data: data),
              let image = UIImage(data: decodedData) else {
            self.drawText("Reply media unavailable", in: frame.insetBy(dx: 2.0, dy: 2.0), font: UIFont.systemFont(ofSize: 8.0), color: palette.secondaryText, alignment: .center)
            return
        }
        let imageRect = Self.aspectFillRect(imageSize: image.size, bounds: frame)
        UIGraphicsGetCurrentContext()?.saveGState()
        UIBezierPath(roundedRect: frame, cornerRadius: 4.0).addClip()
        image.draw(in: imageRect)
        UIGraphicsGetCurrentContext()?.restoreGState()
    }

    private func drawMedia(_ media: GRVMMessageShotMedia, frame: CGRect, palette: GRVMMessageShotPalette) {
        palette.separator.setFill()
        UIBezierPath(roundedRect: frame, cornerRadius: 10.0).fill()
        switch media {
        case let .thumbnail(_, data, _, isSpoiler):
            if !options.revealSpoilers && isSpoiler {
                self.drawSpoilerMask(frame: frame, color: palette.secondaryText)
            } else if let decodedData = decodeTinyThumbnail(data: data), let image = UIImage(data: decodedData) {
                let imageRect = Self.aspectFillRect(imageSize: image.size, bounds: frame)
                UIGraphicsGetCurrentContext()?.saveGState()
                UIBezierPath(roundedRect: frame, cornerRadius: 10.0).addClip()
                image.draw(in: imageRect)
                UIGraphicsGetCurrentContext()?.restoreGState()
            } else {
                self.drawText("Media unavailable", in: frame.insetBy(dx: 10.0, dy: 10.0), font: UIFont.systemFont(ofSize: 14.0), color: palette.secondaryText, alignment: .center)
            }
        case let .placeholder(_, title, isSpoiler):
            if !options.revealSpoilers && isSpoiler {
                self.drawSpoilerMask(frame: frame, color: palette.secondaryText)
            } else {
                self.drawText(title, in: frame.insetBy(dx: 10.0, dy: 10.0), font: UIFont.systemFont(ofSize: 14.0), color: palette.secondaryText, alignment: .center)
            }
        }
    }

    private func drawReactions(_ reactions: [GRVMMessageShotReaction], frame: CGRect, palette: GRVMMessageShotPalette, textColor: UIColor) {
        let frames = Self.reactionFrames(reactions, width: frame.width).map {
            $0.offsetBy(dx: frame.minX, dy: frame.minY)
        }
        for (reaction, pillFrame) in zip(reactions, frames) {
            let kind: GRVMMessageShotReactionKind = reaction.isCustom ? .custom : .builtin
            let value: String
            switch kind {
            case .custom:
                value = "  \(reaction.count)"
            case .builtin:
                value = "\(reaction.value) \(reaction.count)"
            }
            (reaction.isSelected ? palette.separator.withAlphaComponent(0.9) : palette.separator.withAlphaComponent(0.5)).setFill()
            UIBezierPath(roundedRect: pillFrame, cornerRadius: 12.0).fill()
            if kind == .custom {
                self.drawCustomReactionPlaceholder(frame: CGRect(x: pillFrame.minX + 6.0, y: pillFrame.minY + 4.0, width: 16.0, height: 16.0), palette: palette)
            }
            self.drawText(value, in: pillFrame, font: UIFont.systemFont(ofSize: 13.0), color: textColor, alignment: .center)
        }
    }

    private func drawCustomReactionPlaceholder(frame: CGRect, palette: GRVMMessageShotPalette) {
        palette.secondaryText.setFill()
        UIBezierPath(ovalIn: frame).fill()
    }

    private func drawSpoilers(in text: String, entities: [MessageTextEntity], frame: CGRect, font: UIFont, color: UIColor) {
        let textLength = (text as NSString).length
        guard textLength > 0 else {
            return
        }
        let spoilerRanges: [NSRange] = entities.compactMap { entity in
            guard case .Spoiler = entity.type else {
                return nil
            }
            let lowerBound = max(0, min(textLength, entity.range.lowerBound))
            let upperBound = max(lowerBound, min(textLength, entity.range.upperBound))
            guard upperBound > lowerBound else {
                return nil
            }
            return NSRange(location: lowerBound, length: upperBound - lowerBound)
        }
        guard !spoilerRanges.isEmpty else {
            return
        }

        let storage = NSTextStorage(string: text, attributes: [.font: font])
        let layoutManager = NSLayoutManager()
        let textContainer = NSTextContainer(size: frame.size)
        textContainer.lineFragmentPadding = 0.0
        textContainer.maximumNumberOfLines = 0
        textContainer.lineBreakMode = .byTruncatingTail
        layoutManager.addTextContainer(textContainer)
        storage.addLayoutManager(layoutManager)
        _ = layoutManager.glyphRange(for: textContainer)
        for range in spoilerRanges {
            let glyphRange = layoutManager.glyphRange(forCharacterRange: range, actualCharacterRange: nil)
            layoutManager.enumerateEnclosingRects(forGlyphRange: glyphRange, withinSelectedGlyphRange: NSRange(location: NSNotFound, length: 0), in: textContainer) { rect, _ in
                self.drawSpoilerMask(frame: rect.offsetBy(dx: frame.minX, dy: frame.minY).insetBy(dx: -1.0, dy: 0.0), color: color)
            }
        }
    }

    private func drawSpoilerMask(frame: CGRect, color: UIColor) {
        color.withAlphaComponent(0.78).setFill()
        UIBezierPath(roundedRect: frame, cornerRadius: 3.0).fill()
    }

    private func drawText(_ text: String, in frame: CGRect, font: UIFont, color: UIColor, alignment: NSTextAlignment) {
        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = alignment
        paragraph.lineBreakMode = .byTruncatingTail
        (text as NSString).draw(
            with: frame,
            options: [.usesLineFragmentOrigin, .usesFontLeading],
            attributes: [.font: font, .foregroundColor: color, .paragraphStyle: paragraph],
            context: nil
        )
    }

    private func palette() -> GRVMMessageShotPalette {
        switch self.options.theme {
        case .current:
            return .current(theme: self.theme)
        case .light:
            return .light(theme: self.theme)
        case .dark:
            return .dark(theme: self.theme)
        }
    }

    private func stableColor(peerId: PeerId?, palette: GRVMMessageShotPalette) -> UIColor {
        guard let peerId, !palette.senderColors.isEmpty else {
            return palette.secondaryText
        }
        let value = peerId.toInt64()
        let count = Int64(palette.senderColors.count)
        let index = Int(((value % Int64(palette.senderColors.count)) + count) % count)
        return palette.senderColors[index]
    }

    private static func messagesAreGrouped(_ lhs: GRVMMessageShotMessage?, _ rhs: GRVMMessageShotMessage?) -> Bool {
        guard let lhs, let rhs, lhs.day == rhs.day, lhs.direction == rhs.direction else {
            return false
        }
        if lhs.header.peerId != rhs.header.peerId {
            return false
        }
        return Int64(rhs.timestamp) - Int64(lhs.timestamp) <= 300
    }

    private static func mediaHeight(media: GRVMMessageShotMedia, width: CGFloat) -> CGFloat {
        let dimensions: CGSize?
        switch media {
        case let .thumbnail(_, _, value, _):
            dimensions = value
        case .placeholder:
            dimensions = nil
        }
        guard let dimensions, dimensions.width.isFinite, dimensions.height.isFinite, dimensions.width > 0.0, dimensions.height > 0.0 else {
            return min(180.0, width * 0.62)
        }
        return max(84.0, min(220.0, width * dimensions.height / dimensions.width))
    }

    private static func textHeight(_ text: String, width: CGFloat, font: UIFont) -> CGFloat {
        let height = ceil((text as NSString).boundingRect(
            with: CGSize(width: width, height: CGFloat.greatestFiniteMagnitude),
            options: [.usesLineFragmentOrigin, .usesFontLeading],
            attributes: [.font: font],
            context: nil
        ).height)
        return max(ceil(font.lineHeight), height)
    }

    private static func textWidth(_ text: String, font: UIFont) -> CGFloat {
        return (text as NSString).size(withAttributes: [.font: font]).width
    }

    private static func reactionFrames(_ reactions: [GRVMMessageShotReaction], width: CGFloat) -> [CGRect] {
        guard width > 0.0 else {
            return []
        }
        let font = UIFont.systemFont(ofSize: 13.0)
        let spacing: CGFloat = 5.0
        let pillHeight: CGFloat = 24.0
        let rowHeight: CGFloat = 28.0
        var frames: [CGRect] = []
        var x: CGFloat = 0.0
        var y: CGFloat = 0.0
        for reaction in reactions {
            let value = reaction.isCustom ? "  \(reaction.count)" : "\(reaction.value) \(reaction.count)"
            let pillWidth = min(width, max(46.0, ceil(Self.textWidth(value, font: font)) + 16.0))
            if x > 0.0 && x + pillWidth > width {
                x = 0.0
                y += rowHeight
            }
            frames.append(CGRect(x: x, y: y, width: pillWidth, height: pillHeight))
            x += pillWidth + spacing
        }
        return frames
    }

    private static func reactionsHeight(_ reactions: [GRVMMessageShotReaction], width: CGFloat) -> CGFloat {
        guard let lastFrame = self.reactionFrames(reactions, width: width).last else {
            return 0.0
        }
        return lastFrame.maxY
    }

    private static func aspectFillRect(imageSize: CGSize, bounds: CGRect) -> CGRect {
        guard imageSize.width > 0.0, imageSize.height > 0.0 else {
            return bounds
        }
        let scale = max(bounds.width / imageSize.width, bounds.height / imageSize.height)
        let size = CGSize(width: imageSize.width * scale, height: imageSize.height * scale)
        return CGRect(x: bounds.midX - size.width * 0.5, y: bounds.midY - size.height * 0.5, width: size.width, height: size.height)
    }

    private static func validate(size: CGSize, scale: CGFloat) throws {
        guard size.width.isFinite, size.height.isFinite, scale.isFinite,
              size.width > 0.0, size.height > 0.0,
              scale >= 1.0 && scale <= 3.0 else {
            throw GRVMMessageShotRendererError.invalidCanvas
        }
        let pixelWidth = size.width * scale
        let pixelHeight = size.height * scale
        let estimatedBytes = pixelWidth * pixelHeight * 4.0
        guard pixelWidth <= 16384.0, pixelHeight <= 16384.0,
              estimatedBytes <= 48.0 * 1024.0 * 1024.0 else {
            throw GRVMMessageShotRendererError.canvasTooLarge
        }
    }
}
