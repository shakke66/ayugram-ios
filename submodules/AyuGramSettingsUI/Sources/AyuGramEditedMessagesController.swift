import Foundation
import UIKit
import Display
import SwiftSignalKit
import Postbox
import TelegramCore
import TelegramPresentationData
import TelegramUIPreferences
import ItemListUI
import PresentationDataUtils
import AccountContext
import AyuGramLib

private enum AyuEditedSection: Int32 {
    case messages
}

private enum AyuEditedEntry: ItemListNodeEntry {
    case header(PresentationTheme, String)
    case empty(PresentationTheme)
    case message(Int32, PresentationTheme, String, String)

    var section: ItemListSectionId {
        return AyuEditedSection.messages.rawValue
    }

    var stableId: Int32 {
        switch self {
        case .header:
            return 0
        case .empty:
            return 1
        case let .message(index, _, _, _):
            return 100 + index
        }
    }

    static func ==(lhs: AyuEditedEntry, rhs: AyuEditedEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.header(_, lText), .header(_, rText)):
            return lText == rText
        case (.empty, .empty):
            return true
        case let (.message(lIndex, _, lText, lDate), .message(rIndex, _, rText, rDate)):
            return lIndex == rIndex && lText == rText && lDate == rDate
        default:
            return false
        }
    }

    static func <(lhs: AyuEditedEntry, rhs: AyuEditedEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        switch self {
        case let .header(_, text):
            return ItemListSectionHeaderItem(presentationData: presentationData, text: text, sectionId: self.section)
        case .empty:
            return ItemListTextItem(presentationData: presentationData, text: .plain("No edit history has been saved yet."), sectionId: self.section)
        case let .message(_, _, text, dateLabel):
            return ItemListDisclosureItem(presentationData: presentationData, icon: nil, title: text, label: dateLabel, sectionId: self.section, style: .blocks, action: {})
        }
    }
}

private func ayuEditedEntries(messages: [AyuSavedMessage], presentationData: PresentationData) -> [AyuEditedEntry] {
    var entries: [AyuEditedEntry] = []
    entries.append(.header(presentationData.theme, "Recent Edited Messages (previous versions)"))

    if messages.isEmpty {
        entries.append(.empty(presentationData.theme))
        return entries
    }

    let formatter = DateFormatter()
    formatter.dateStyle = .short
    formatter.timeStyle = .short

    var index: Int32 = 0
    for message in messages {
        var body = message.text
        if body.isEmpty {
            body = message.mediaDescription.isEmpty ? "[empty]" : "[\(message.mediaDescription)]"
        } else if !message.mediaDescription.isEmpty {
            body = "[\(message.mediaDescription)] \(body)"
        }
        let who = [message.senderName, message.peerTitle].filter { !$0.isEmpty }.joined(separator: " · ")
        let prefix = who.isEmpty ? "" : "\(who): "
        var display = "\(prefix)\(body) (v\(message.editVersion))"
        if !message.mediaResourceIds.isEmpty {
            display += " 📎"
        }
        let date = Date(timeIntervalSince1970: TimeInterval(message.date))
        entries.append(.message(index, presentationData.theme, display, formatter.string(from: date)))
        index += 1
    }

    return entries
}

public func ayuGramEditedMessagesController(context: AccountContext) -> ViewController {
    let messages = AyuDeletedMessagesDB.shared.getAllEditedMessages()

    let signal = context.sharedContext.presentationData
    |> map { presentationData -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let entries = ayuEditedEntries(messages: messages, presentationData: presentationData)
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text("Edit History"),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: entries,
            style: .blocks
        )
        return (controllerState, (listState, ()))
    }

    return ItemListController(context: context, state: signal)
}
