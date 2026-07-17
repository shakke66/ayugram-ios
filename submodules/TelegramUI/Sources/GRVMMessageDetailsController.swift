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

private func grvmMessageDetailsText(message: Message) -> String {
    var lines: [String] = [
        "Peer ID: \(message.id.peerId)",
        "Namespace: \(message.id.namespace)",
        "Message ID: \(message.id.id)",
        "Stable ID: \(message.stableId)",
        "Date: \(grvmMessageDetailsDate(message.timestamp)) (\(message.timestamp))"
    ]
    if let threadId = message.threadId {
        lines.append("Thread ID: \(threadId)")
    }
    if let author = message.author {
        lines.append("Author: \(author.debugDisplayTitle) (\(author.id))")
    }
    if let forwardInfo = message.forwardInfo {
        lines.append("Forward date: \(grvmMessageDetailsDate(forwardInfo.date)) (\(forwardInfo.date))")
        if let author = forwardInfo.author {
            lines.append("Forward author: \(author.debugDisplayTitle) (\(author.id))")
        }
        if let source = forwardInfo.source {
            lines.append("Forward source: \(source.debugDisplayTitle) (\(source.id))")
        }
        if let sourceMessageId = forwardInfo.sourceMessageId {
            lines.append("Forward source message: \(sourceMessageId)")
        }
        if let authorSignature = forwardInfo.authorSignature, !authorSignature.isEmpty {
            lines.append("Forward signature: \(authorSignature)")
        }
    }
    for attribute in message.attributes {
        if let attribute = attribute as? EditedMessageAttribute {
            lines.append("Edited: \(grvmMessageDetailsDate(attribute.date)) (\(attribute.date))")
        } else if let attribute = attribute as? ViewCountMessageAttribute {
            lines.append("Views: \(attribute.count)")
        } else if let attribute = attribute as? ForwardCountMessageAttribute {
            lines.append("Forwards: \(attribute.count)")
        }
    }
    for media in message.media {
        if let image = media as? TelegramMediaImage {
            let sizes = image.representations.map { "\($0.dimensions.width)x\($0.dimensions.height)" }
            lines.append("Image: \(image.imageId), sizes: \(sizes.joined(separator: ", "))")
        } else if let file = media as? TelegramMediaFile {
            var metadata = ["id=\(file.fileId)", "mime=\(file.mimeType)"]
            if let name = file.fileName {
                metadata.append("name=\(name)")
            }
            if let size = file.size {
                metadata.append("size=\(size)")
            }
            if let dimensions = file.dimensions {
                metadata.append("dimensions=\(dimensions.width)x\(dimensions.height)")
            }
            if let duration = file.duration {
                metadata.append("duration=\(duration)")
            }
            lines.append("File: \(metadata.joined(separator: ", "))")
        } else {
            lines.append("Media: \(String(describing: type(of: media)))")
        }
    }
    return lines.joined(separator: "\n")
}

public func grvmMessageDetailsController(
    context: AccountContext,
    message: Message
) -> ViewController {
    let details = grvmMessageDetailsText(message: message)
    let signal = context.sharedContext.presentationData
    |> map { presentationData -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text("Message Details"),
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
