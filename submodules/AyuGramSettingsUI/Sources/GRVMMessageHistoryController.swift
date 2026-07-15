import Foundation
import UIKit
import AccountContext
import AyuGramFeatures
import AyuGramLib
import Display
import ItemListUI
import Postbox
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData
import TelegramUIPreferences
import TextFormat

private struct GRVMHistoryVersion: Equatable {
    let stableId: Int64
    let version: Int32
    let timestamp: Int32
    let text: String
    let entitiesData: Data
    let mediaSummary: String
    let resourceIds: [String]
    let isCurrent: Bool
}

private struct GRVMHistoryArguments {
    let context: AccountContext
}

private enum GRVMHistorySection: Int32 {
    case versions
}

private enum GRVMHistoryEntry: ItemListNodeEntry {
    case empty(PresentationTheme)
    case version(Int32, PresentationTheme, GRVMHistoryVersion)

    var section: ItemListSectionId {
        return GRVMHistorySection.versions.rawValue
    }

    var stableId: Int64 {
        switch self {
        case .empty:
            return 0
        case let .version(_, _, version):
            return version.stableId
        }
    }

    private var sortIndex: Int32 {
        switch self {
        case .empty:
            return 0
        case let .version(index, _, _):
            return index + 1
        }
    }

    static func ==(lhs: GRVMHistoryEntry, rhs: GRVMHistoryEntry) -> Bool {
        switch (lhs, rhs) {
        case (.empty, .empty):
            return true
        case let (.version(lhsIndex, _, lhsVersion), .version(rhsIndex, _, rhsVersion)):
            return lhsIndex == rhsIndex && lhsVersion == rhsVersion
        default:
            return false
        }
    }

    static func <(lhs: GRVMHistoryEntry, rhs: GRVMHistoryEntry) -> Bool {
        return lhs.sortIndex < rhs.sortIndex
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! GRVMHistoryArguments
        switch self {
        case .empty:
            return ItemListTextItem(
                presentationData: presentationData,
                text: .plain(presentationData.strings.ChatList_Search_NoResults),
                sectionId: self.section
            )
        case let .version(_, _, version):
            return ItemListTextItem(
                presentationData: presentationData,
                text: .custom(
                    context: arguments.context,
                    string: grvmHistoryAttributedText(version, presentationData: presentationData)
                ),
                sectionId: self.section
            )
        }
    }
}

private func grvmHistoryEntities(_ data: Data) -> [MessageTextEntity] {
    guard !data.isEmpty,
          let attribute = PostboxDecoder(buffer: MemoryBuffer(data: data)).decodeRootObject()
            as? TextEntitiesMessageAttribute else {
        return []
    }
    return attribute.entities
}

private func grvmHistoryEntitiesData(_ message: Message) -> Data {
    guard let attribute = message.attributes.first(where: { $0 is TextEntitiesMessageAttribute }) else {
        return Data()
    }
    let encoder = PostboxEncoder()
    encoder.encodeRootObject(attribute)
    return encoder.makeData()
}

private func grvmHistoryMediaSummary(_ media: [Media]) -> String {
    return media.compactMap { item -> String? in
        if item is TelegramMediaImage {
            return "photo"
        } else if let file = item as? TelegramMediaFile {
            if file.isInstantVideo {
                return "video message"
            } else if file.isVideo {
                return "video"
            } else if file.isVoice {
                return "voice message"
            } else if file.isSticker {
                return "sticker"
            } else if file.isMusic {
                return "audio"
            } else {
                return file.fileName ?? "document"
            }
        } else if item is TelegramMediaContact {
            return "contact"
        } else if item is TelegramMediaMap {
            return "location"
        } else if item is TelegramMediaPoll {
            return "poll"
        } else {
            return nil
        }
    }.joined(separator: ", ")
}

private func grvmHistoryAttributedText(
    _ version: GRVMHistoryVersion,
    presentationData: ItemListPresentationData
) -> NSAttributedString {
    let dateFormatter = DateFormatter()
    dateFormatter.dateStyle = .short
    dateFormatter.timeStyle = .short
    let date = dateFormatter.string(from: Date(timeIntervalSince1970: TimeInterval(version.timestamp)))
    let label = version.isCurrent ? "Current" : "Version \(version.version)"
    let result = NSMutableAttributedString(
        string: "\(label) - \(date)\n",
        font: Font.semibold(14.0),
        textColor: presentationData.theme.list.itemSecondaryTextColor
    )

    if version.text.isEmpty {
        result.append(NSAttributedString(
            string: "[empty]",
            font: Font.regular(16.0),
            textColor: presentationData.theme.list.itemPrimaryTextColor
        ))
    } else {
        result.append(stringWithAppliedEntities(
            version.text,
            entities: grvmHistoryEntities(version.entitiesData),
            baseColor: presentationData.theme.list.itemPrimaryTextColor,
            linkColor: presentationData.theme.list.itemAccentColor,
            baseFont: Font.regular(16.0),
            linkFont: Font.regular(16.0),
            boldFont: Font.semibold(16.0),
            italicFont: Font.italic(16.0),
            boldItalicFont: Font.semiboldItalic(16.0),
            fixedFont: Font.monospace(16.0),
            blockQuoteFont: Font.regular(16.0),
            message: nil
        ))
    }

    var mediaParts: [String] = []
    if !version.mediaSummary.isEmpty {
        mediaParts.append("Media: \(version.mediaSummary)")
    }
    if !version.resourceIds.isEmpty {
        mediaParts.append("Archived resources: \(version.resourceIds.count)")
    }
    if !mediaParts.isEmpty {
        result.append(NSAttributedString(
            string: "\n\(mediaParts.joined(separator: " - "))",
            font: Font.regular(13.0),
            textColor: presentationData.theme.list.itemSecondaryTextColor
        ))
    }
    return result
}

private func grvmHistoryEntries(
    versions: [GRVMHistoryVersion],
    presentationData: PresentationData
) -> [GRVMHistoryEntry] {
    guard !versions.isEmpty else {
        return [.empty(presentationData.theme)]
    }
    return versions.enumerated().map { index, version in
        .version(Int32(index), presentationData.theme, version)
    }
}

/// Displays archived edits for one message followed by its current Postbox version.
public func grvmMessageHistoryController(
    context: AccountContext,
    messageId: MessageId
) -> ViewController {
    let revisions = AyuGramFeatures.editHistory?(context.account.peerId, messageId) ?? .single([])
    let currentMessage = context.account.postbox.transaction { transaction -> Message? in
        return transaction.getMessage(messageId)
    }
    let versions = combineLatest(revisions, currentMessage)
    |> map { revisions, currentMessage -> [GRVMHistoryVersion] in
        var versions = revisions.sorted { lhs, rhs in
            if lhs.savedAt == rhs.savedAt {
                return lhs.version < rhs.version
            }
            return lhs.savedAt < rhs.savedAt
        }.map { revision in
            GRVMHistoryVersion(
                stableId: revision.rowId,
                version: revision.version,
                timestamp: revision.savedAt,
                text: revision.text,
                entitiesData: revision.entitiesData,
                mediaSummary: revision.mediaSummary,
                resourceIds: revision.resourceIds,
                isCurrent: false
            )
        }
        if let currentMessage {
            versions.append(GRVMHistoryVersion(
                stableId: Int64.max,
                version: (revisions.map(\.version).max() ?? 0) + 1,
                timestamp: currentMessage.timestamp,
                text: currentMessage.text,
                entitiesData: grvmHistoryEntitiesData(currentMessage),
                mediaSummary: grvmHistoryMediaSummary(currentMessage.media),
                resourceIds: grvmMediaResources(currentMessage.media).map(\.id.stringRepresentation),
                isCurrent: true
            ))
        }
        return versions
    }

    let arguments = GRVMHistoryArguments(context: context)
    let signal = combineLatest(context.sharedContext.presentationData, versions)
    |> map { presentationData, versions -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text("GRVMgram History"),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: grvmHistoryEntries(versions: versions, presentationData: presentationData),
            style: .blocks
        )
        return (controllerState, (listState, arguments))
    }
    return ItemListController(context: context, state: signal)
}
