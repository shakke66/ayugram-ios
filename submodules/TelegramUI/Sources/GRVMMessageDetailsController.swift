import Foundation
import AccountContext
import Display
import ItemListUI
import Postbox
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData

private struct GRVMMessageDetailsArguments {
}

private enum GRVMMessageDetailsEntry: ItemListNodeEntry {
    case details(PresentationTheme, String)

    var section: ItemListSectionId {
        return 0
    }

    var stableId: Int64 {
        return 0
    }

    static func ==(lhs: GRVMMessageDetailsEntry, rhs: GRVMMessageDetailsEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.details(_, lhsText), .details(_, rhsText)):
            return lhsText == rhsText
        }
    }

    static func <(lhs: GRVMMessageDetailsEntry, rhs: GRVMMessageDetailsEntry) -> Bool {
        return false
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        switch self {
        case let .details(_, text):
            return ItemListTextItem(
                presentationData: presentationData,
                text: .plain(text),
                sectionId: self.section
            )
        }
    }
}

private func grvmMessageDetailsDate(_ timestamp: Int32) -> String {
    let formatter = DateFormatter()
    formatter.dateStyle = .medium
    formatter.timeStyle = .medium
    return formatter.string(from: Date(timeIntervalSince1970: TimeInterval(timestamp)))
}

private func grvmMessageDetailsText(
    message: Message,
    strings: GRVMgramStrings
) -> String {
    var lines: [String] = [
        strings.format(.messageDetailsPeerId, String(describing: message.id.peerId)),
        strings.format(.messageDetailsNamespace, message.id.namespace),
        strings.format(.messageDetailsMessageId, message.id.id),
        strings.format(.messageDetailsStableId, String(message.stableId)),
        strings.format(.messageDetailsDate, grvmMessageDetailsDate(message.timestamp), message.timestamp),
    ]
    if let threadId = message.threadId {
        lines.append(strings.format(.messageDetailsThreadId, String(threadId)))
    }
    if let author = message.author {
        lines.append(strings.format(.messageDetailsAuthor, author.debugDisplayTitle, String(describing: author.id)))
    }
    if let forwardInfo = message.forwardInfo {
        lines.append(strings.format(.messageDetailsForwardDate, grvmMessageDetailsDate(forwardInfo.date), forwardInfo.date))
        if let author = forwardInfo.author {
            lines.append(strings.format(.messageDetailsForwardAuthor, author.debugDisplayTitle, String(describing: author.id)))
        }
        if let source = forwardInfo.source {
            lines.append(strings.format(.messageDetailsForwardSource, source.debugDisplayTitle, String(describing: source.id)))
        }
        if let sourceMessageId = forwardInfo.sourceMessageId {
            lines.append(strings.format(.messageDetailsForwardSourceMessage, String(describing: sourceMessageId)))
        }
        if let authorSignature = forwardInfo.authorSignature, !authorSignature.isEmpty {
            lines.append(strings.format(.messageDetailsForwardSignature, authorSignature))
        }
    }
    for attribute in message.attributes {
        if let attribute = attribute as? EditedMessageAttribute {
            lines.append(strings.format(.messageDetailsEdited, grvmMessageDetailsDate(attribute.date), attribute.date))
        } else if let attribute = attribute as? ViewCountMessageAttribute {
            lines.append(strings.format(.messageDetailsViews, attribute.count))
        } else if let attribute = attribute as? ForwardCountMessageAttribute {
            lines.append(strings.format(.messageDetailsForwards, attribute.count))
        }
    }
    for media in message.media {
        if let image = media as? TelegramMediaImage {
            let sizes = image.representations.map { "\($0.dimensions.width)x\($0.dimensions.height)" }
            lines.append(strings.format(.messageDetailsImage, String(describing: image.imageId), sizes.joined(separator: ", ")))
        } else if let file = media as? TelegramMediaFile {
            var metadata = [
                strings.format(.messageDetailsFileId, String(describing: file.fileId)),
                strings.format(.messageDetailsFileMime, file.mimeType),
            ]
            if let name = file.fileName {
                metadata.append(strings.format(.messageDetailsFileName, name))
            }
            if let size = file.size {
                metadata.append(strings.format(.messageDetailsFileSize, String(size)))
            }
            if let dimensions = file.dimensions {
                metadata.append(strings.format(.messageDetailsFileDimensions, "\(dimensions.width)x\(dimensions.height)"))
            }
            if let duration = file.duration {
                metadata.append(strings.format(.messageDetailsFileDuration, String(duration)))
            }
            lines.append(strings.format(.messageDetailsFile, metadata.joined(separator: ", ")))
        } else {
            lines.append(strings.format(.messageDetailsMedia, String(describing: type(of: media))))
        }
    }
    return lines.joined(separator: "\n")
}

public func grvmMessageDetailsController(
    context: AccountContext,
    message: Message
) -> ViewController {
    let signal = context.sharedContext.presentationData
    |> map { presentationData -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let details = grvmMessageDetailsText(message: message, strings: strings)
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text(strings[.messageDetailsTitle]),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: [GRVMMessageDetailsEntry.details(presentationData.theme, details)],
            style: .blocks
        )
        return (controllerState, (listState, GRVMMessageDetailsArguments()))
    }
    return ItemListController(context: context, state: signal)
}
