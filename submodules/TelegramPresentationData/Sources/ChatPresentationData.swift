import Foundation
import UIKit
import Display
import TelegramCore
import TelegramUIPreferences

public final class ChatPresentationThemeData: Equatable {
    public let theme: PresentationTheme
    public let wallpaper: TelegramWallpaper
    
    public init(theme: PresentationTheme, wallpaper: TelegramWallpaper) {
        self.theme = theme
        self.wallpaper = wallpaper
    }
    
    public func withTheme(_ theme: PresentationTheme) -> ChatPresentationThemeData {
        return ChatPresentationThemeData(theme: theme, wallpaper: self.wallpaper)
    }
    
    public static func ==(lhs: ChatPresentationThemeData, rhs: ChatPresentationThemeData) -> Bool {
        return lhs.theme === rhs.theme && lhs.wallpaper == rhs.wallpaper
    }
}

public final class ChatPresentationData {
    public let theme: ChatPresentationThemeData
    public let accountPeerId: PeerId?
    public let fontSize: PresentationFontSize
    public let strings: PresentationStrings
    public let dateTimeFormat: PresentationDateTimeFormat
    public let nameDisplayOrder: PresentationPersonNameOrder
    public let disableAnimations: Bool
    public let largeEmoji: Bool
    public let chatBubbleCorners: PresentationChatBubbleCorners
    public let animatedEmojiScale: CGFloat
    public let isPreview: Bool
    private let sourceChatBubbleCorners: PresentationChatBubbleCorners
    private let chatAppearance: GRVMAppearanceSettings?
    
    public let messageFont: UIFont
    public let messageEmojiFont: UIFont
    public let messageBoldFont: UIFont
    public let messageItalicFont: UIFont
    public let messageBoldItalicFont: UIFont
    public let messageFixedFont: UIFont
    public let messageBlockQuoteFont: UIFont
    
    public init(theme: ChatPresentationThemeData, fontSize: PresentationFontSize, strings: PresentationStrings, dateTimeFormat: PresentationDateTimeFormat, nameDisplayOrder: PresentationPersonNameOrder, disableAnimations: Bool, largeEmoji: Bool, chatBubbleCorners: PresentationChatBubbleCorners, animatedEmojiScale: CGFloat = 1.0, isPreview: Bool = false, accountPeerId: PeerId? = nil, chatAppearance: GRVMAppearanceSettings? = nil) {
        self.theme = theme
        self.accountPeerId = accountPeerId
        self.fontSize = fontSize
        self.strings = strings
        self.dateTimeFormat = dateTimeFormat
        self.nameDisplayOrder = nameDisplayOrder
        self.disableAnimations = disableAnimations
        self.sourceChatBubbleCorners = chatBubbleCorners
        self.chatAppearance = chatAppearance
        let appearance: GRVMAppearanceSettings
        if let chatAppearance {
            appearance = chatAppearance
        } else if let accountPeerId {
            appearance = AyuGramHooks.chatAppearance(accountPeerId: accountPeerId).appearance
        } else {
            appearance = GRVMChatAppearanceSettings.default.appearance
        }
        let messageBubbleRadius = min(16, max(0, appearance.messageBubbleRadius))
        let radiusScale = CGFloat(messageBubbleRadius) / 16.0
        self.chatBubbleCorners = PresentationChatBubbleCorners(
            mainRadius: chatBubbleCorners.mainRadius * radiusScale,
            auxiliaryRadius: chatBubbleCorners.auxiliaryRadius * radiusScale,
            mergeBubbleCorners: chatBubbleCorners.mergeBubbleCorners,
            hasTails: chatBubbleCorners.hasTails
        )
        self.largeEmoji = largeEmoji
        self.isPreview = isPreview
        
        let baseFontSize = fontSize.baseDisplaySize
        self.messageFont = Font.regular(baseFontSize)
        self.messageEmojiFont = Font.regular(53.0)
        self.messageBoldFont = Font.bold(baseFontSize)
        self.messageItalicFont = Font.italic(baseFontSize)
        self.messageBoldItalicFont = Font.semiboldItalic(baseFontSize)
        let fontName = appearance.codeFontName
        if !fontName.isEmpty {
            self.messageFixedFont = UIFont(name: fontName, size: baseFontSize) ?? Font.monospace(baseFontSize)
        } else {
            self.messageFixedFont = Font.monospace(baseFontSize)
        }
        self.messageBlockQuoteFont = Font.regular(baseFontSize - 1.0)
        
        self.animatedEmojiScale = animatedEmojiScale
    }
    
    public func withTheme(_ theme: ChatPresentationThemeData) -> ChatPresentationData {
        return ChatPresentationData(
            theme: theme,
            fontSize: self.fontSize,
            strings: self.strings,
            dateTimeFormat: self.dateTimeFormat,
            nameDisplayOrder: self.nameDisplayOrder,
            disableAnimations: self.disableAnimations,
            largeEmoji: self.largeEmoji,
            chatBubbleCorners: self.sourceChatBubbleCorners,
            animatedEmojiScale: self.animatedEmojiScale,
            isPreview: self.isPreview,
            accountPeerId: self.accountPeerId,
            chatAppearance: self.chatAppearance
        )
    }
}

extension ChatPresentationData {
    public convenience init(presentationData: PresentationData) {
        self.init(theme: ChatPresentationThemeData(theme: presentationData.theme, wallpaper: presentationData.chatWallpaper), fontSize: presentationData.chatFontSize, strings: presentationData.strings, dateTimeFormat: presentationData.dateTimeFormat, nameDisplayOrder: presentationData.nameDisplayOrder, disableAnimations: true, largeEmoji: presentationData.largeEmoji, chatBubbleCorners: presentationData.chatBubbleCorners)
    }
}
