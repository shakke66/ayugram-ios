import Foundation
import UIKit
import Display
import SwiftSignalKit
import Postbox
import TelegramCore
import TelegramPresentationData
import ItemListUI
import AccountContext
import AlertUI
import AyuGramLib

private struct AyuGramFilterEditorState: Equatable {
    var draft: AyuMessageFilter
}

private final class AyuGramFilterEditorArguments {
    let updateExpression: (String) -> Void
    let updateEnabled: (Bool) -> Void
    let updateReversed: (Bool) -> Void
    let updateCaseInsensitive: (Bool) -> Void
    let selectChat: () -> Void
    let clearChat: () -> Void
    let selectExcludedChats: () -> Void
    let clearExcludedChats: () -> Void

    init(
        updateExpression: @escaping (String) -> Void,
        updateEnabled: @escaping (Bool) -> Void,
        updateReversed: @escaping (Bool) -> Void,
        updateCaseInsensitive: @escaping (Bool) -> Void,
        selectChat: @escaping () -> Void,
        clearChat: @escaping () -> Void,
        selectExcludedChats: @escaping () -> Void,
        clearExcludedChats: @escaping () -> Void
    ) {
        self.updateExpression = updateExpression
        self.updateEnabled = updateEnabled
        self.updateReversed = updateReversed
        self.updateCaseInsensitive = updateCaseInsensitive
        self.selectChat = selectChat
        self.clearChat = clearChat
        self.selectExcludedChats = selectExcludedChats
        self.clearExcludedChats = clearExcludedChats
    }
}

private enum AyuGramFilterEditorSection: Int32 {
    case expression
    case options
    case scope
}

private enum AyuGramFilterEditorEntry: ItemListNodeEntry {
    case expressionHeader(PresentationTheme)
    case expression(PresentationTheme, String)
    case optionsHeader(PresentationTheme)
    case enabled(PresentationTheme, Bool)
    case reversed(PresentationTheme, Bool)
    case caseInsensitive(PresentationTheme, Bool)
    case scopeHeader(PresentationTheme)
    case chat(PresentationTheme, Int64?)
    case clearChat(PresentationTheme)
    case excludedChats(PresentationTheme, Int)
    case clearExcludedChats(PresentationTheme)

    var section: ItemListSectionId {
        switch self {
        case .expressionHeader, .expression:
            return AyuGramFilterEditorSection.expression.rawValue
        case .optionsHeader, .enabled, .reversed, .caseInsensitive:
            return AyuGramFilterEditorSection.options.rawValue
        case .scopeHeader, .chat, .clearChat, .excludedChats, .clearExcludedChats:
            return AyuGramFilterEditorSection.scope.rawValue
        }
    }

    var stableId: Int32 {
        switch self {
        case .expressionHeader: return 0
        case .expression: return 1
        case .optionsHeader: return 2
        case .enabled: return 3
        case .reversed: return 4
        case .caseInsensitive: return 5
        case .scopeHeader: return 6
        case .chat: return 7
        case .clearChat: return 8
        case .excludedChats: return 9
        case .clearExcludedChats: return 10
        }
    }

    static func ==(lhs: AyuGramFilterEditorEntry, rhs: AyuGramFilterEditorEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.expressionHeader(lt), .expressionHeader(rt)),
             let (.optionsHeader(lt), .optionsHeader(rt)),
             let (.scopeHeader(lt), .scopeHeader(rt)),
             let (.clearChat(lt), .clearChat(rt)),
             let (.clearExcludedChats(lt), .clearExcludedChats(rt)):
            return lt === rt
        case let (.expression(lt, lv), .expression(rt, rv)):
            return lt === rt && lv == rv
        case let (.enabled(lt, lv), .enabled(rt, rv)),
             let (.reversed(lt, lv), .reversed(rt, rv)),
             let (.caseInsensitive(lt, lv), .caseInsensitive(rt, rv)):
            return lt === rt && lv == rv
        case let (.chat(lt, lv), .chat(rt, rv)):
            return lt === rt && lv == rv
        case let (.excludedChats(lt, lv), .excludedChats(rt, rv)):
            return lt === rt && lv == rv
        default:
            return false
        }
    }

    static func <(lhs: AyuGramFilterEditorEntry, rhs: AyuGramFilterEditorEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramFilterEditorArguments
        let strings = GRVMgramStrings(presentationData.strings)
        switch self {
        case .expressionHeader:
            return ItemListSectionHeaderItem(
                presentationData: presentationData,
                text: strings[.filterEditorExpressionHeader],
                sectionId: self.section
            )
        case let .expression(_, value):
            return ItemListMultilineInputItem(
                presentationData: presentationData,
                text: value,
                placeholder: strings[.filterEditorExpressionPlaceholder],
                maxLength: nil,
                sectionId: self.section,
                style: .blocks,
                capitalization: false,
                autocorrection: false,
                textUpdated: arguments.updateExpression
            )
        case .optionsHeader:
            return ItemListSectionHeaderItem(
                presentationData: presentationData,
                text: strings[.filterEditorOptionsHeader],
                sectionId: self.section
            )
        case let .enabled(_, value):
            return ItemListSwitchItem(
                presentationData: presentationData,
                title: strings[.filterEditorEnabled],
                value: value,
                sectionId: self.section,
                style: .blocks,
                updated: arguments.updateEnabled
            )
        case let .reversed(_, value):
            return ItemListSwitchItem(
                presentationData: presentationData,
                title: strings[.filterEditorReversed],
                value: value,
                sectionId: self.section,
                style: .blocks,
                updated: arguments.updateReversed
            )
        case let .caseInsensitive(_, value):
            return ItemListSwitchItem(
                presentationData: presentationData,
                title: strings[.filterEditorCaseInsensitive],
                value: value,
                sectionId: self.section,
                style: .blocks,
                updated: arguments.updateCaseInsensitive
            )
        case .scopeHeader:
            return ItemListSectionHeaderItem(
                presentationData: presentationData,
                text: strings[.filterEditorScopeHeader],
                sectionId: self.section
            )
        case let .chat(_, peerId):
            return ItemListDisclosureItem(
                presentationData: presentationData,
                title: strings[.filterEditorScopeChat],
                label: peerId.map { String($0) } ?? strings[.filterEditorScopeAllChats],
                sectionId: self.section,
                style: .blocks,
                action: arguments.selectChat
            )
        case .clearChat:
            return ItemListActionItem(
                presentationData: presentationData,
                title: strings[.filterEditorScopeUseAllChats],
                kind: .generic,
                alignment: .natural,
                sectionId: self.section,
                style: .blocks,
                action: arguments.clearChat
            )
        case let .excludedChats(_, count):
            return ItemListDisclosureItem(
                presentationData: presentationData,
                title: strings[.filterEditorExcludedChats],
                label: count == 0 ? strings[.filterEditorNone] : "\(count)",
                sectionId: self.section,
                style: .blocks,
                action: arguments.selectExcludedChats
            )
        case .clearExcludedChats:
            return ItemListActionItem(
                presentationData: presentationData,
                title: strings[.filterEditorClearExcluded],
                kind: .generic,
                alignment: .natural,
                sectionId: self.section,
                style: .blocks,
                action: arguments.clearExcludedChats
            )
        }
    }
}

private func ayuGramFilterEditorEntries(
    state: AyuGramFilterEditorState,
    presentationData: PresentationData
) -> [AyuGramFilterEditorEntry] {
    let theme = presentationData.theme
    var entries: [AyuGramFilterEditorEntry] = [
        .expressionHeader(theme),
        .expression(theme, state.draft.expression),
        .optionsHeader(theme),
        .enabled(theme, state.draft.isEnabled),
        .reversed(theme, state.draft.isReversed),
        .caseInsensitive(theme, state.draft.isCaseInsensitive),
        .scopeHeader(theme),
        .chat(theme, state.draft.peerId)
    ]
    if state.draft.peerId != nil {
        entries.append(.clearChat(theme))
    }
    entries.append(.excludedChats(theme, state.draft.excludedPeerIds.count))
    if !state.draft.excludedPeerIds.isEmpty {
        entries.append(.clearExcludedChats(theme))
    }
    return entries
}

public func ayuGramFilterEditorController(
    context: AccountContext,
    filter: AyuMessageFilter? = nil,
    initialExpression: String = "",
    initialPeerId: PeerId? = nil
) -> ViewController {
    let initialDraft = filter ?? AyuMessageFilter(
        expression: initialExpression,
        peerId: initialPeerId?.toInt64()
    )
    let initialState = AyuGramFilterEditorState(draft: initialDraft)
    let statePromise = ValuePromise(initialState, ignoreRepeated: true)
    let stateValue = Atomic(value: initialState)
    let updateState: ((AyuGramFilterEditorState) -> AyuGramFilterEditorState) -> Void = { f in
        statePromise.set(stateValue.modify(f))
    }

    var presentControllerImpl: ((ViewController, ViewControllerPresentationArguments?) -> Void)?
    var pushControllerImpl: ((ViewController) -> Void)?
    var dismissImpl: (() -> Void)?
    var saveImpl: ((AyuMessageFilter) -> Void)?

    let arguments = AyuGramFilterEditorArguments(
        updateExpression: { value in
            updateState { state in
                var state = state
                state.draft.expression = value
                return state
            }
        },
        updateEnabled: { value in
            updateState { state in
                var state = state
                state.draft.isEnabled = value
                return state
            }
        },
        updateReversed: { value in
            updateState { state in
                var state = state
                state.draft.isReversed = value
                return state
            }
        },
        updateCaseInsensitive: { value in
            updateState { state in
                var state = state
                state.draft.isCaseInsensitive = value
                return state
            }
        },
        selectChat: {
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            let strings = GRVMgramStrings(presentationData.strings)
            let controller = context.sharedContext.makePeerSelectionController(
                PeerSelectionControllerParams(
                    context: context,
                    filter: [],
                    hasContactSelector: false,
                    title: strings[.filterEditorSelectChat]
                )
            )
            controller.peerSelected = { [weak controller] peer, _ in
                updateState { state in
                    var state = state
                    state.draft.peerId = peer.id.toInt64()
                    return state
                }
                controller?.dismiss()
            }
            pushControllerImpl?(controller)
        },
        clearChat: {
            updateState { state in
                var state = state
                state.draft.peerId = nil
                return state
            }
        },
        selectExcludedChats: {
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            let strings = GRVMgramStrings(presentationData.strings)
            let controller = context.sharedContext.makePeerSelectionController(
                PeerSelectionControllerParams(
                    context: context,
                    filter: [],
                    hasContactSelector: false,
                    title: strings[.filterEditorExcludeChats],
                    multipleSelection: true,
                    immediatelyActivateMultipleSelection: true
                )
            )
            controller.multiplePeersSelected = { [weak controller] peers, _, _, _, _, _ in
                let peerIds = Set(peers.map { $0.id.toInt64() })
                updateState { state in
                    var state = state
                    state.draft.excludedPeerIds.formUnion(peerIds)
                    return state
                }
                controller?.dismiss()
            }
            pushControllerImpl?(controller)
        },
        clearExcludedChats: {
            updateState { state in
                var state = state
                state.draft.excludedPeerIds.removeAll()
                return state
            }
        }
    )

    saveImpl = { draft in
        let expression = draft.expression.trimmingCharacters(in: .whitespacesAndNewlines)
        let options: NSRegularExpression.Options = draft.isCaseInsensitive ? [.caseInsensitive] : []
        guard !expression.isEmpty,
              (try? NSRegularExpression(pattern: expression, options: options)) != nil else {
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            let strings = GRVMgramStrings(presentationData.strings)
            presentControllerImpl?(
                textAlertController(
                    context: context,
                    title: strings[.filterEditorInvalidTitle],
                    text: strings[.filterEditorInvalidText],
                    actions: [
                        TextAlertAction(
                            type: .defaultAction,
                            title: presentationData.strings.Common_OK,
                            action: {}
                        )
                    ]
                ),
                nil
            )
            return
        }

        var draft = draft
        draft.expression = expression
        let _ = (updateGRVMSettings(
            accountId: context.account.peerId,
            accountManager: context.sharedContext.accountManager
        ) { settings in
            var settings = settings
            if let index = settings.filters.firstIndex(where: { $0.id == draft.id }) {
                settings.filters[index] = draft
            } else {
                settings.filters.append(draft)
            }
            return settings
        }
        |> deliverOnMainQueue).startStandalone(completed: {
            dismissImpl?()
        })
    }

    let signal = combineLatest(
        context.sharedContext.presentationData,
        statePromise.get()
    )
    |> map { presentationData, state -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let rightNavigationButton = ItemListNavigationButton(
            content: .text(presentationData.strings.Common_Done),
            style: .bold,
            enabled: true,
            action: {
                saveImpl?(state.draft)
            }
        )
        return (
            ItemListControllerState(
                presentationData: ItemListPresentationData(presentationData),
                title: .text(filter == nil ? strings[.filterEditorAddTitle] : strings[.filterEditorEditTitle]),
                leftNavigationButton: nil,
                rightNavigationButton: rightNavigationButton,
                backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
            ),
            (
                ItemListNodeState(
                    presentationData: ItemListPresentationData(presentationData),
                    entries: ayuGramFilterEditorEntries(state: state, presentationData: presentationData),
                    style: .blocks
                ),
                arguments
            )
        )
    }

    let controller = ItemListController(context: context, state: signal)
    presentControllerImpl = { [weak controller] child, arguments in
        controller?.present(child, in: .window(.root), with: arguments)
    }
    pushControllerImpl = { [weak controller] child in
        controller?.push(child)
    }
    dismissImpl = { [weak controller] in
        controller?.dismiss()
    }
    return controller
}
