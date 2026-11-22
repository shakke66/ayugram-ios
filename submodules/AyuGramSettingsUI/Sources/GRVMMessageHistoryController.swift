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
    let content: GRVMEditableMessageContent
    let legacyMediaSummary: String
    let legacyResourceIds: [String]
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
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case .empty:
            return ItemListTextItem(
                presentationData: presentationData,
                text: .plain(strings[.historyEmpty]),
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

private func grvmHistoryMediaLabel(
    _ media: GRVMEditableMediaContent,
    strings: GRVMgramStrings
) -> String {
    switch media {
    case .todo:
        return strings[.historyMediaTodo]
    case .poll:
        return strings[.historyMediaPoll]
    case .webpage:
        return strings[.historyMediaLinkPreview]
    case let .file(file):
        for attribute in file.attributes {
            if case let .fileName(name) = attribute {
                return name
            }
        }
        return strings[.historyMediaFile]
    case .image:
        return strings[.historyMediaPhoto]
    case let .game(game):
        return game.title.isEmpty ? strings[.historyMediaGame] : game.title
    case .paidContent:
        return strings[.historyMediaPaid]
    case let .contact(contact):
        let name = "\(contact.firstName) \(contact.lastName)".trimmingCharacters(in: .whitespaces)
        return name.isEmpty ? strings[.historyMediaContact] : name
    case .map:
        return strings[.historyMediaLocation]
    case let .invoice(invoice):
        return invoice.title.isEmpty ? strings[.historyMediaInvoice] : invoice.title
    case let .other(type, _):
        return type
    }
}

private func grvmHistoryAttributedText(
    _ version: GRVMHistoryVersion,
    presentationData: ItemListPresentationData
) -> NSAttributedString {
    let strings = GRVMgramStrings(presentationData.strings)
    let dateFormatter = DateFormatter()
    dateFormatter.dateStyle = .short
    dateFormatter.timeStyle = .short
    let date = dateFormatter.string(from: Date(timeIntervalSince1970: TimeInterval(version.timestamp)))
    let label = version.isCurrent
        ? strings[.historyCurrent]
        : strings.format(.historyRevision, version.version + 1)
    let timestamp = version.isCurrent
        ? strings.format(.historyMessageDate, date)
        : strings.format(.historyRevisionSavedAt, date)
    let result = NSMutableAttributedString(
        string: strings.format(.historyEntryHeader, label, timestamp),
        font: Font.semibold(14.0),
        textColor: presentationData.theme.list.itemSecondaryTextColor
    )

    if version.content.text.isEmpty {
        result.append(NSAttributedString(
            string: strings[.historyMessageEmpty],
            font: Font.regular(16.0),
            textColor: presentationData.theme.list.itemPrimaryTextColor
        ))
    } else {
        result.append(stringWithAppliedEntities(
            version.content.text,
            entities: version.content.textEntities,
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

    var mediaParts = version.content.media.map { grvmHistoryMediaLabel($0, strings: strings) }
    if mediaParts.isEmpty, !version.legacyMediaSummary.isEmpty {
        mediaParts.append(version.legacyMediaSummary)
    }
    if version.content.media.isEmpty, !version.legacyResourceIds.isEmpty {
        mediaParts.append(strings.format(.historyArchivedResources, Int32(version.legacyResourceIds.count)))
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
                content: revision.editableContent,
                legacyMediaSummary: revision.mediaSummary,
                legacyResourceIds: revision.resourceIds,
                isCurrent: false
            )
        }
        if let currentMessage {
            let content = GRVMEditableMessageContent(message: currentMessage)
            versions.append(GRVMHistoryVersion(
                stableId: Int64.max,
                version: (revisions.map(\.version).max() ?? 0) + 1,
                timestamp: currentMessage.timestamp,
                content: content,
                legacyMediaSummary: "",
                legacyResourceIds: [],
                isCurrent: true
            ))
        }
        return versions
    }

    let arguments = GRVMHistoryArguments(context: context)
    let signal = combineLatest(context.sharedContext.presentationData, versions)
    |> map { presentationData, versions -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text(strings[.historyTitle]),
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
