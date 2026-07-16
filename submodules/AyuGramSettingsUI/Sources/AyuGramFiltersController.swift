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
import TranslateUI
import AyuGramLib

private enum AyuGramFilterTransferError: Error {
    case invalidFile
}

private final class AyuGramFilterTransferController: NSObject, UIDocumentPickerDelegate {
    private static let maximumImportSize = 1_048_576

    private let context: AccountContext
    private let replaceFilters: ([AyuMessageFilter]) -> Void
    private let presentAlert: (ViewController) -> Void
    weak var sourceController: ViewController?

    init(
        context: AccountContext,
        replaceFilters: @escaping ([AyuMessageFilter]) -> Void,
        presentAlert: @escaping (ViewController) -> Void
    ) {
        self.context = context
        self.replaceFilters = replaceFilters
        self.presentAlert = presentAlert
        super.init()
    }

    func presentImport() {
        let controller = UIDocumentPickerViewController(documentTypes: ["public.json"], in: .import)
        controller.delegate = self
        self.context.sharedContext.applicationBindings.presentNativeController(controller)
    }

    func presentExport(filters: [AyuMessageFilter]) {
        self.exportFilters(filters)
    }

    func documentPicker(
        _ controller: UIDocumentPickerViewController,
        didPickDocumentsAt urls: [URL]
    ) {
        guard let url = urls.first else {
            return
        }
        self.importFilters(from: url)
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
    }

    private func importFilters(from url: URL) {
        let isAccessingSecurityScopedResource = url.startAccessingSecurityScopedResource()
        defer {
            if isAccessingSecurityScopedResource {
                url.stopAccessingSecurityScopedResource()
            }
        }

        do {
            let values = try url.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey])
            guard values.isRegularFile == true,
                  let fileSize = values.fileSize,
                  fileSize <= Self.maximumImportSize else {
                throw AyuGramFilterTransferError.invalidFile
            }

            let file = try FileHandle(forReadingFrom: url)
            let data = file.readData(ofLength: Self.maximumImportSize + 1)
            try? file.close()
            guard data.count <= Self.maximumImportSize else {
                throw AyuGramFilterTransferError.invalidFile
            }

            let backup = try JSONDecoder().decode(AyuMessageFilterBackup.self, from: data)
            guard backup.version == 2 else {
                throw AyuGramFilterTransferError.invalidFile
            }

            var ids = Set<UUID>()
            for filter in backup.filters {
                let expression = filter.expression.trimmingCharacters(in: .whitespacesAndNewlines)
                let options: NSRegularExpression.Options = filter.isCaseInsensitive
                    ? [.caseInsensitive]
                    : []
                guard !expression.isEmpty,
                      ids.insert(filter.id).inserted,
                      (try? NSRegularExpression(pattern: expression, options: options)) != nil else {
                    throw AyuGramFilterTransferError.invalidFile
                }
            }

            let enabledCount = backup.filters.filter(\.isEnabled).count
            let reversedCount = backup.filters.filter(\.isReversed).count
            let chatScopedCount = backup.filters.filter { $0.peerId != nil }.count
            let summary = "Filters: \(backup.filters.count)\nEnabled: \(enabledCount)\nReversed: \(reversedCount)\nChat-scoped: \(chatScopedCount)"
            let presentationData = self.context.sharedContext.currentPresentationData.with { $0 }
            self.presentAlert(textAlertController(
                context: self.context,
                title: "Import Filters",
                text: summary,
                actions: [
                    TextAlertAction(
                        type: .genericAction,
                        title: presentationData.strings.Common_Cancel,
                        action: {}
                    ),
                    TextAlertAction(
                        type: .defaultAction,
                        title: "Replace",
                        action: { [weak self] in
                            self?.replaceFilters(backup.filters)
                        }
                    )
                ]
            ))
        } catch {
            self.presentInvalidFileAlert()
        }
    }

    private func exportFilters(_ filters: [AyuMessageFilter]) {
        var temporaryFileUrl: URL?
        do {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try encoder.encode(AyuMessageFilterBackup(version: 2, filters: filters))
            let fileUrl = FileManager.default.temporaryDirectory
                .appendingPathComponent("grvmgram-filters-\(UUID().uuidString)")
                .appendingPathExtension("json")
            temporaryFileUrl = fileUrl
            try data.write(to: fileUrl, options: .atomic)

            let activityController = UIActivityViewController(
                activityItems: [fileUrl],
                applicationActivities: nil
            )
            activityController.completionWithItemsHandler = { _, _, _, _ in
                try? FileManager.default.removeItem(at: fileUrl)
            }
            if let sourceView = self.context.sharedContext.applicationBindings.getTopWindow()
                ?? self.sourceController?.view {
                activityController.popoverPresentationController?.sourceView = sourceView
                activityController.popoverPresentationController?.sourceRect = CGRect(
                    x: sourceView.bounds.midX,
                    y: sourceView.bounds.maxY - 1.0,
                    width: 1.0,
                    height: 1.0
                )
            }
            self.context.sharedContext.applicationBindings.presentNativeController(activityController)
        } catch {
            if let temporaryFileUrl {
                try? FileManager.default.removeItem(at: temporaryFileUrl)
            }
            self.presentInvalidFileAlert()
        }
    }

    private func presentInvalidFileAlert() {
        let presentationData = self.context.sharedContext.currentPresentationData.with { $0 }
        self.presentAlert(textAlertController(
            context: self.context,
            title: "Invalid Filter File",
            text: "Choose a version 2 JSON filter backup smaller than 1 MiB.",
            actions: [
                TextAlertAction(
                    type: .defaultAction,
                    title: presentationData.strings.Common_OK,
                    action: {}
                )
            ]
        ))
    }
}

private struct AyuGramFiltersState: Equatable {
    var editing = false
    var revealedFilterId: UUID?
}

private final class AyuGramFiltersArguments {
    let context: AccountContext
    let transferController: AyuGramFilterTransferController
    let toggleFilters: (Bool) -> Void
    let toggleFiltersInChats: (Bool) -> Void
    let toggleHideFromBlocked: (Bool) -> Void
    let editFilter: (AyuMessageFilter) -> Void
    let removeFilter: (UUID) -> Void
    let setRevealedFilterId: (UUID?, UUID?) -> Void
    let pushController: (ViewController) -> Void
    let clearFilters: () -> Void

    init(
        context: AccountContext,
        transferController: AyuGramFilterTransferController,
        toggleFilters: @escaping (Bool) -> Void,
        toggleFiltersInChats: @escaping (Bool) -> Void,
        toggleHideFromBlocked: @escaping (Bool) -> Void,
        editFilter: @escaping (AyuMessageFilter) -> Void,
        removeFilter: @escaping (UUID) -> Void,
        setRevealedFilterId: @escaping (UUID?, UUID?) -> Void,
        pushController: @escaping (ViewController) -> Void,
        clearFilters: @escaping () -> Void
    ) {
        self.context = context
        self.transferController = transferController
        self.toggleFilters = toggleFilters
        self.toggleFiltersInChats = toggleFiltersInChats
        self.toggleHideFromBlocked = toggleHideFromBlocked
        self.editFilter = editFilter
        self.removeFilter = removeFilter
        self.setRevealedFilterId = setRevealedFilterId
        self.pushController = pushController
        self.clearFilters = clearFilters
    }
}

private enum AyuGramFiltersSection: Int32 {
    case master
    case filters
    case transfer
    case shadow
}

private enum AyuGramFiltersEntry: ItemListNodeEntry {
    case masterHeader(PresentationTheme)
    case enableFilters(PresentationTheme, Bool)
    case enableFiltersInChats(PresentationTheme, Bool)
    case filtersHeader(PresentationTheme)
    case filter(Int32, PresentationTheme, AyuMessageFilter, Bool, Bool)
    case empty(PresentationTheme)
    case addFilter(PresentationTheme)
    case transferHeader(PresentationTheme)
    case importFilters(PresentationTheme)
    case exportFilters(PresentationTheme, [AyuMessageFilter])
    case clearFilters(PresentationTheme)
    case shadowHeader(PresentationTheme)
    case hideFromBlocked(PresentationTheme, Bool)
    case shadowBan(PresentationTheme)

    var section: ItemListSectionId {
        switch self {
        case .masterHeader, .enableFilters, .enableFiltersInChats:
            return AyuGramFiltersSection.master.rawValue
        case .filtersHeader, .filter, .empty, .addFilter:
            return AyuGramFiltersSection.filters.rawValue
        case .transferHeader, .importFilters, .exportFilters, .clearFilters:
            return AyuGramFiltersSection.transfer.rawValue
        case .shadowHeader, .hideFromBlocked, .shadowBan:
            return AyuGramFiltersSection.shadow.rawValue
        }
    }

    var stableId: AnyHashable {
        switch self {
        case .masterHeader: return AnyHashable(0 as Int32)
        case .enableFilters: return AnyHashable(1 as Int32)
        case .enableFiltersInChats: return AnyHashable(2 as Int32)
        case .filtersHeader: return AnyHashable(3 as Int32)
        case let .filter(_, _, filter, _, _): return AnyHashable(filter.id)
        case .empty: return AnyHashable(4 as Int32)
        case .addFilter: return AnyHashable(5 as Int32)
        case .transferHeader: return AnyHashable(6 as Int32)
        case .importFilters: return AnyHashable(7 as Int32)
        case .exportFilters: return AnyHashable(8 as Int32)
        case .clearFilters: return AnyHashable(9 as Int32)
        case .shadowHeader: return AnyHashable(10 as Int32)
        case .hideFromBlocked: return AnyHashable(11 as Int32)
        case .shadowBan: return AnyHashable(12 as Int32)
        }
    }

    private var sortIndex: Int32 {
        switch self {
        case .masterHeader: return 0
        case .enableFilters: return 1
        case .enableFiltersInChats: return 2
        case .filtersHeader: return 3
        case let .filter(index, _, _, _, _): return 100 + index
        case .empty: return 5000
        case .addFilter: return 5001
        case .transferHeader: return 6000
        case .importFilters: return 6001
        case .exportFilters: return 6002
        case .clearFilters: return 6003
        case .shadowHeader: return 7000
        case .hideFromBlocked: return 7001
        case .shadowBan: return 7002
        }
    }

    static func ==(lhs: AyuGramFiltersEntry, rhs: AyuGramFiltersEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.masterHeader(lt), .masterHeader(rt)),
             let (.filtersHeader(lt), .filtersHeader(rt)),
             let (.empty(lt), .empty(rt)),
             let (.addFilter(lt), .addFilter(rt)),
             let (.transferHeader(lt), .transferHeader(rt)),
             let (.importFilters(lt), .importFilters(rt)),
             let (.clearFilters(lt), .clearFilters(rt)),
             let (.shadowHeader(lt), .shadowHeader(rt)),
             let (.shadowBan(lt), .shadowBan(rt)):
            return lt === rt
        case let (.enableFilters(lt, lv), .enableFilters(rt, rv)),
             let (.enableFiltersInChats(lt, lv), .enableFiltersInChats(rt, rv)),
             let (.hideFromBlocked(lt, lv), .hideFromBlocked(rt, rv)):
            return lt === rt && lv == rv
        case let (.filter(li, lt, lf, le, lr), .filter(ri, rt, rf, re, rr)):
            return li == ri && lt === rt && lf == rf && le == re && lr == rr
        case let (.exportFilters(lt, lf), .exportFilters(rt, rf)):
            return lt === rt && lf == rf
        default:
            return false
        }
    }

    static func <(lhs: AyuGramFiltersEntry, rhs: AyuGramFiltersEntry) -> Bool {
        return lhs.sortIndex < rhs.sortIndex
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! AyuGramFiltersArguments
        switch self {
        case .masterHeader:
            return ItemListSectionHeaderItem(
                presentationData: presentationData,
                text: "Message Filters",
                sectionId: self.section
            )
        case let .enableFilters(_, value):
            return ItemListSwitchItem(
                presentationData: presentationData,
                title: "Enable Filters",
                value: value,
                sectionId: self.section,
                style: .blocks,
                updated: arguments.toggleFilters
            )
        case let .enableFiltersInChats(_, value):
            return ItemListSwitchItem(
                presentationData: presentationData,
                title: "Enable Filters in Chats",
                value: value,
                sectionId: self.section,
                style: .blocks,
                updated: arguments.toggleFiltersInChats
            )
        case .filtersHeader:
            return ItemListSectionHeaderItem(
                presentationData: presentationData,
                text: "Filters",
                sectionId: self.section
            )
        case let .filter(_, _, filter, editing, revealed):
            var details: [String] = []
            details.append(filter.isReversed ? "Reversed" : "Normal")
            details.append(filter.isCaseInsensitive ? "Case Insensitive" : "Case Sensitive")
            details.append(filter.peerId.map { "Chat \($0)" } ?? "All Chats")
            if !filter.excludedPeerIds.isEmpty {
                details.append("\(filter.excludedPeerIds.count) Excluded")
            }
            return LocalizationListItem(
                presentationData: presentationData,
                id: filter.id.uuidString,
                title: filter.expression,
                subtitle: details.joined(separator: " | "),
                checked: filter.isEnabled,
                activity: false,
                loading: false,
                editing: LocalizationListItemEditing(
                    editable: true,
                    editing: editing,
                    revealed: revealed,
                    reorderable: true
                ),
                sectionId: self.section,
                alwaysPlain: false,
                action: {
                    arguments.editFilter(filter)
                },
                setItemWithRevealedOptions: { current, previous in
                    arguments.setRevealedFilterId(
                        current.flatMap { UUID(uuidString: $0) },
                        previous.flatMap { UUID(uuidString: $0) }
                    )
                },
                removeItem: { id in
                    if let id = UUID(uuidString: id) {
                        arguments.removeFilter(id)
                    }
                }
            )
        case .empty:
            return ItemListTextItem(
                presentationData: presentationData,
                text: .plain("No filters"),
                sectionId: self.section
            )
        case .addFilter:
            return ItemListActionItem(
                presentationData: presentationData,
                title: "Add Filter",
                kind: .generic,
                alignment: .natural,
                sectionId: self.section,
                style: .blocks,
                action: {
                    arguments.pushController(ayuGramFilterEditorController(context: arguments.context))
                }
            )
        case .transferHeader:
            return ItemListSectionHeaderItem(
                presentationData: presentationData,
                text: "Backup",
                sectionId: self.section
            )
        case .importFilters:
            return ItemListActionItem(
                presentationData: presentationData,
                title: "Import",
                kind: .generic,
                alignment: .natural,
                sectionId: self.section,
                style: .blocks,
                action: {
                    arguments.transferController.presentImport()
                }
            )
        case let .exportFilters(_, filters):
            return ItemListActionItem(
                presentationData: presentationData,
                title: "Export",
                kind: .generic,
                alignment: .natural,
                sectionId: self.section,
                style: .blocks,
                action: {
                    arguments.transferController.presentExport(filters: filters)
                }
            )
        case .clearFilters:
            return ItemListActionItem(
                presentationData: presentationData,
                title: "Clear",
                kind: .destructive,
                alignment: .natural,
                sectionId: self.section,
                style: .blocks,
                action: arguments.clearFilters
            )
        case .shadowHeader:
            return ItemListSectionHeaderItem(
                presentationData: presentationData,
                text: "People",
                sectionId: self.section
            )
        case let .hideFromBlocked(_, value):
            return ItemListSwitchItem(
                presentationData: presentationData,
                title: "Hide from Blocked Users",
                value: value,
                sectionId: self.section,
                style: .blocks,
                updated: arguments.toggleHideFromBlocked
            )
        case .shadowBan:
            return ItemListDisclosureItem(
                presentationData: presentationData,
                title: "Shadow Ban",
                label: "",
                sectionId: self.section,
                style: .blocks,
                action: {
                    arguments.pushController(ayuGramShadowBanController(context: arguments.context))
                }
            )
        }
    }
}

private func ayuGramFiltersEntries(
    settings: AyuGramSettings,
    visibleFilters: [AyuMessageFilter],
    state: AyuGramFiltersState,
    matchingOnly: Bool,
    presentationData: PresentationData
) -> [AyuGramFiltersEntry] {
    let theme = presentationData.theme
    var entries: [AyuGramFiltersEntry] = []
    if !matchingOnly {
        entries.append(.masterHeader(theme))
        entries.append(.enableFilters(theme, settings.enableFilters))
        entries.append(.enableFiltersInChats(theme, settings.enableFiltersInChats))
    }
    entries.append(.filtersHeader(theme))
    for (index, filter) in visibleFilters.enumerated() {
        entries.append(.filter(
            Int32(index),
            theme,
            filter,
            !matchingOnly && state.editing,
            state.revealedFilterId == filter.id
        ))
    }
    if visibleFilters.isEmpty {
        entries.append(.empty(theme))
    }
    if !matchingOnly {
        entries.append(.addFilter(theme))
        entries.append(.transferHeader(theme))
        entries.append(.importFilters(theme))
        entries.append(.exportFilters(theme, settings.filters))
        if !settings.filters.isEmpty {
            entries.append(.clearFilters(theme))
        }
        entries.append(.shadowHeader(theme))
        entries.append(.hideFromBlocked(theme, settings.hideFromBlockedUsers))
        entries.append(.shadowBan(theme))
    }
    return entries
}

public func ayuGramFiltersController(
    context: AccountContext,
    matchingFilterIds: Set<UUID>? = nil
) -> ViewController {
    let initialState = AyuGramFiltersState()
    let statePromise = ValuePromise(initialState, ignoreRepeated: true)
    let stateValue = Atomic(value: initialState)
    let updateState: ((AyuGramFiltersState) -> AyuGramFiltersState) -> Void = { f in
        statePromise.set(stateValue.modify(f))
    }

    var presentControllerImpl: ((ViewController, ViewControllerPresentationArguments?) -> Void)?
    var pushControllerImpl: ((ViewController) -> Void)?

    let transferController = AyuGramFilterTransferController(
        context: context,
        replaceFilters: { filters in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                var settings = settings
                settings.filters = filters
                return settings
            }.startStandalone()
        },
        presentAlert: { controller in
            presentControllerImpl?(controller, nil)
        }
    )

    let arguments = AyuGramFiltersArguments(
        context: context,
        transferController: transferController,
        toggleFilters: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                var settings = settings
                settings.enableFilters = value
                return settings
            }.startStandalone()
        },
        toggleFiltersInChats: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                var settings = settings
                settings.enableFiltersInChats = value
                return settings
            }.startStandalone()
        },
        toggleHideFromBlocked: { value in
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                var settings = settings
                settings.hideFromBlockedUsers = value
                return settings
            }.startStandalone()
        },
        editFilter: { filter in
            pushControllerImpl?(ayuGramFilterEditorController(context: context, filter: filter))
        },
        removeFilter: { id in
            updateState { state in
                var state = state
                if state.revealedFilterId == id {
                    state.revealedFilterId = nil
                }
                return state
            }
            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                var settings = settings
                settings.filters.removeAll { $0.id == id }
                return settings
            }.startStandalone()
        },
        setRevealedFilterId: { id, previousId in
            updateState { state in
                var state = state
                if (id == nil && state.revealedFilterId == previousId)
                    || (id != nil && previousId == nil) {
                    state.revealedFilterId = id
                }
                return state
            }
        },
        pushController: { controller in
            pushControllerImpl?(controller)
        },
        clearFilters: {
            let presentationData = context.sharedContext.currentPresentationData.with { $0 }
            presentControllerImpl?(textAlertController(
                context: context,
                title: "Clear Filters",
                text: "Remove every filter from this account?",
                actions: [
                    TextAlertAction(
                        type: .genericAction,
                        title: presentationData.strings.Common_Cancel,
                        action: {}
                    ),
                    TextAlertAction(
                        type: .destructiveAction,
                        title: presentationData.strings.Common_Delete,
                        action: {
                            let _ = updateGRVMSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager) { settings in
                                var settings = settings
                                settings.filters.removeAll()
                                return settings
                            }.startStandalone()
                        }
                    )
                ]
            ), nil)
        }
    )

    let signal = combineLatest(
        context.sharedContext.presentationData,
        grvmSettings(accountId: context.account.peerId, accountManager: context.sharedContext.accountManager),
        statePromise.get()
    )
    |> map { presentationData, settings, state -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let visibleFilters: [AyuMessageFilter]
        if let matchingFilterIds {
            visibleFilters = settings.filters.filter { matchingFilterIds.contains($0.id) }
        } else {
            visibleFilters = settings.filters
        }

        let rightNavigationButton: ItemListNavigationButton?
        if matchingFilterIds == nil && !settings.filters.isEmpty {
            rightNavigationButton = ItemListNavigationButton(
                content: .text(
                    state.editing
                        ? presentationData.strings.Common_Done
                        : presentationData.strings.Common_Edit
                ),
                style: state.editing ? .bold : .regular,
                enabled: true,
                action: {
                    updateState { state in
                        var state = state
                        state.editing.toggle()
                        state.revealedFilterId = nil
                        return state
                    }
                }
            )
        } else {
            rightNavigationButton = nil
        }

        return (
            ItemListControllerState(
                presentationData: ItemListPresentationData(presentationData),
                title: .text(matchingFilterIds == nil ? "Filters" : "Matching Filters"),
                leftNavigationButton: nil,
                rightNavigationButton: rightNavigationButton,
                backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
            ),
            (
                ItemListNodeState(
                    presentationData: ItemListPresentationData(presentationData),
                    entries: ayuGramFiltersEntries(
                        settings: settings,
                        visibleFilters: visibleFilters,
                        state: state,
                        matchingOnly: matchingFilterIds != nil,
                        presentationData: presentationData
                    ),
                    style: .blocks
                ),
                arguments
            )
        )
    }

    let controller = ItemListController(context: context, state: signal)
    controller.setReorderEntry { (
        fromIndex: Int,
        toIndex: Int,
        entries: [AyuGramFiltersEntry]
    ) -> Signal<Bool, NoError> in
        guard matchingFilterIds == nil,
              fromIndex >= 0,
              fromIndex < entries.count,
              toIndex >= 0,
              toIndex < entries.count,
              case let .filter(_, _, fromFilter, _, _) = entries[fromIndex],
              case let .filter(_, _, toFilter, _, _) = entries[toIndex],
              fromFilter.id != toFilter.id else {
            return .single(false)
        }
        return updateGRVMSettings(
            accountId: context.account.peerId,
            accountManager: context.sharedContext.accountManager
        ) { settings in
            var settings = settings
            guard let sourceIndex = settings.filters.firstIndex(where: { $0.id == fromFilter.id }),
                  let targetIndex = settings.filters.firstIndex(where: { $0.id == toFilter.id }) else {
                return settings
            }
            let filter = settings.filters.remove(at: sourceIndex)
            settings.filters.insert(filter, at: targetIndex)
            return settings
        }
        |> map { true }
    }
    presentControllerImpl = { [weak controller] child, arguments in
        controller?.present(child, in: .window(.root), with: arguments)
    }
    pushControllerImpl = { [weak controller] child in
        controller?.push(child)
    }
    transferController.sourceController = controller
    return controller
}
