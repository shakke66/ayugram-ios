import Foundation
import AccountContext
import AlertUI
import AyuGramLib
import Display
import ItemListUI
import PresentationDataUtils
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData

private enum GRVMNotifySettingsStatus: Equatable {
    case unsupportedOS
    case notConnected
    case webSessionConnected(ownerUserId: Int64)
    case connectedToMissingAccount(ownerUserId: Int64)
    case disconnecting(ownerUserId: Int64)
    case statusNotVerified(ownerUserId: Int64)
}

private enum GRVMNotifySettingsAction: Equatable {
    case startSetup
    case continueSetup
    case openDevices
    case disconnect
}

private enum GRVMNotifySettingsOperation: Equatable {
    case idle
    case disconnecting(pairedUserId: Int64, sessionHash: Int64)
    case statusNotVerified(pairedUserId: Int64, sessionHash: Int64)
}

private struct GRVMNotifyResolvedOwner {
    let context: AccountContext
    let pairedUserId: Int64
    let sessionHash: Int64
}

private enum GRVMNotifyReconciliationResult {
    case skipped
    case success(target: GRVMNotifyResolvedOwner, hashes: Set<Int64>)
    case failure(target: GRVMNotifyResolvedOwner)
}

private enum GRVMNotifySettingsEntry: ItemListNodeEntry {
    case text(Int32, PresentationTheme, String)
    case action(Int32, PresentationTheme, GRVMNotifySettingsAction, String)

    var section: ItemListSectionId {
        return 0
    }

    var stableId: Int32 {
        switch self {
        case let .text(id, _, _), let .action(id, _, _, _):
            return id
        }
    }

    static func ==(lhs: GRVMNotifySettingsEntry, rhs: GRVMNotifySettingsEntry) -> Bool {
        switch (lhs, rhs) {
        case let (.text(lhsId, _, lhsText), .text(rhsId, _, rhsText)):
            return lhsId == rhsId && lhsText == rhsText
        case let (.action(lhsId, _, lhsAction, lhsTitle), .action(rhsId, _, rhsAction, rhsTitle)):
            return lhsId == rhsId && lhsAction == rhsAction && lhsTitle == rhsTitle
        default:
            return false
        }
    }

    static func <(lhs: GRVMNotifySettingsEntry, rhs: GRVMNotifySettingsEntry) -> Bool {
        return lhs.stableId < rhs.stableId
    }

    func item(presentationData: ItemListPresentationData, arguments: Any) -> ListViewItem {
        let arguments = arguments as! GRVMNotifySettingsModel
        switch self {
        case let .text(_, _, text):
            return ItemListTextItem(
                presentationData: presentationData,
                text: .plain(text),
                sectionId: self.section
            )
        case let .action(_, _, action, title):
            switch action {
            case .disconnect:
                return ItemListActionItem(
                    presentationData: presentationData,
                    title: title,
                    kind: .destructive,
                    alignment: .natural,
                    sectionId: self.section,
                    style: .blocks,
                    action: {
                        arguments.perform(action)
                    }
                )
            default:
                return ItemListActionItem(
                    presentationData: presentationData,
                    title: title,
                    kind: .generic,
                    alignment: .natural,
                    sectionId: self.section,
                    style: .blocks,
                    action: {
                        arguments.perform(action)
                    }
                )
            }
        }
    }
}

private func grvmNotifySettingsStatus(
    state: GRVMNotifyState,
    activeContexts: [AccountContext],
    operation: GRVMNotifySettingsOperation
) -> GRVMNotifySettingsStatus {
    guard #available(iOS 16.4, *) else {
        return .unsupportedOS
    }
    guard let pairedUserId = state.pairedUserId, let sessionHash = state.sessionHash else {
        return .notConnected
    }

    let owners = activeContexts.filter { context in
        return context.account.peerId.id._internalGetInt64Value() == pairedUserId
    }
    guard owners.count == 1 else {
        return .connectedToMissingAccount(ownerUserId: pairedUserId)
    }

    if case let .disconnecting(operationUserId, operationSessionHash) = operation,
       operationUserId == pairedUserId,
       operationSessionHash == sessionHash {
        return .disconnecting(ownerUserId: pairedUserId)
    }
    if case let .statusNotVerified(operationUserId, operationSessionHash) = operation,
       operationUserId == pairedUserId,
       operationSessionHash == sessionHash {
        return .statusNotVerified(ownerUserId: pairedUserId)
    }
    return .webSessionConnected(ownerUserId: pairedUserId)
}

private func grvmNotifySettingsEntries(
    status: GRVMNotifySettingsStatus,
    presentationData: PresentationData
) -> [GRVMNotifySettingsEntry] {
    let strings = GRVMgramStrings(presentationData.strings)
    let theme = presentationData.theme
    var entries: [GRVMNotifySettingsEntry] = []

    func appendText(_ id: Int32, _ key: GRVMgramStringKey) {
        entries.append(.text(id, theme, strings[key]))
    }
    func appendOwner(_ ownerUserId: Int64) {
        entries.append(.text(1, theme, strings.format(.notifyOwnerAccount, String(ownerUserId))))
    }
    func appendAction(_ id: Int32, _ action: GRVMNotifySettingsAction, _ key: GRVMgramStringKey) {
        entries.append(.action(id, theme, action, strings[key]))
    }
    func appendConnectedActions() {
        appendAction(10, .continueSetup, .notifyContinueSetup)
        appendAction(11, .openDevices, .notifyOpenDevices)
        appendAction(12, .disconnect, .notifyDisconnect)
    }

    switch status {
    case .unsupportedOS:
        appendText(0, .notifyUnsupportedOS)
    case .notConnected:
        appendText(0, .notifyNotConnected)
        appendText(1, .notifyInstallInstructions)
        appendAction(10, .startSetup, .notifyStartSetup)
    case let .webSessionConnected(ownerUserId):
        appendText(0, .notifyWebSessionConnected)
        appendOwner(ownerUserId)
        appendText(2, .notifyWebSessionDisclaimer)
        appendConnectedActions()
    case let .connectedToMissingAccount(ownerUserId):
        appendText(0, .notifyOrphanedSession)
        appendOwner(ownerUserId)
        appendText(2, .notifyOrphanedInstructions)
    case let .disconnecting(ownerUserId):
        appendText(0, .notifyDisconnecting)
        appendOwner(ownerUserId)
    case let .statusNotVerified(ownerUserId):
        appendText(0, .notifyStatusNotVerified)
        appendOwner(ownerUserId)
        appendText(2, .notifyStatusNotVerifiedInfo)
        appendText(3, .notifyWebSessionDisclaimer)
        appendConnectedActions()
    }
    return entries
}

private final class GRVMNotifySettingsModel {
    private static let setupURL = "https://grvm-notify.pages.dev/setup/?grvm_notify=1"

    private let context: AccountContext
    private let stateStore: GRVMNotifyStateStore
    private let actionDisposable = MetaDisposable()
    private let reconciliationDisposable = MetaDisposable()

    let operationState = ValuePromise<GRVMNotifySettingsOperation>(.idle, ignoreRepeated: true)

    var pushController: ((ViewController) -> Void)?
    var presentController: ((ViewController) -> Void)?
    var navigationController: (() -> NavigationController?)?

    init(context: AccountContext, stateStore: GRVMNotifyStateStore) {
        self.context = context
        self.stateStore = stateStore
    }

    deinit {
        self.actionDisposable.dispose()
        self.reconciliationDisposable.dispose()
    }

    func perform(_ action: GRVMNotifySettingsAction) {
        switch action {
        case .startSetup:
            self.startSetup()
        case .continueSetup:
            self.continueSetup()
        case .openDevices:
            self.openDevices()
        case .disconnect:
            self.requestDisconnect()
        }
    }

    private func startSetup() {
        let userId = self.context.account.peerId.id._internalGetInt64Value()
        guard userId > 0 else {
            return
        }
        let startedAt = Int32(clamping: Int64(Date().timeIntervalSince1970))
        self.actionDisposable.set((self.stateStore.update { state in
            var state = state
            guard state.pairedUserId == nil, state.sessionHash == nil else {
                return state
            }
            state.pendingAccountUserId = userId
            state.pendingStartedAt = startedAt
            return state
        }
        |> take(1)
        |> deliverOnMainQueue).start(next: { [weak self] state in
            guard let self,
                  state.pairedUserId == nil,
                  state.sessionHash == nil,
                  state.pendingAccountUserId == userId,
                  state.pendingStartedAt == startedAt else {
                return
            }
            self.openSetupURL()
        }))
    }

    private func continueSetup() {
        self.openSetupURL()
    }

    private func openSetupURL() {
        let presentationData = self.context.sharedContext.currentPresentationData.with { $0 }
        self.context.sharedContext.openExternalUrl(
            context: self.context,
            urlContext: .generic,
            url: Self.setupURL,
            forceExternal: true,
            presentationData: presentationData,
            navigationController: self.navigationController?(),
            dismissInput: {}
        )
    }

    private func activeContexts() -> Signal<[AccountContext], NoError> {
        return self.context.sharedContext.activeAccountContexts
        |> map { _, accounts, _ -> [AccountContext] in
            return accounts.map { $0.1 }
        }
    }

    private func resolveOwner() -> Signal<GRVMNotifyResolvedOwner?, NoError> {
        return combineLatest(
            self.stateStore.state() |> take(1),
            self.activeContexts() |> take(1)
        )
        |> map { state, activeContexts -> GRVMNotifyResolvedOwner? in
            guard let pairedUserId = state.pairedUserId,
                  let sessionHash = state.sessionHash else {
                return nil
            }
            let owners = activeContexts.filter { context in
                return context.account.peerId.id._internalGetInt64Value() == pairedUserId
            }
            guard owners.count == 1, let owner = owners.first else {
                return nil
            }
            return GRVMNotifyResolvedOwner(
                context: owner,
                pairedUserId: pairedUserId,
                sessionHash: sessionHash
            )
        }
    }

    private func openDevices() {
        self.actionDisposable.set((self.resolveOwner()
        |> take(1)
        |> deliverOnMainQueue).start(next: { [weak self] target in
            guard let self, let target else {
                return
            }
            let activeSessionsContext = target.context.engine.privacy.activeSessions()
            self.pushController?(target.context.sharedContext.makeRecentSessionsController(
                context: target.context,
                activeSessionsContext: activeSessionsContext
            ))
        }))
    }

    private func requestDisconnect() {
        self.actionDisposable.set((self.resolveOwner()
        |> take(1)
        |> deliverOnMainQueue).start(next: { [weak self] target in
            guard let self, let target else {
                return
            }
            let presentationData = self.context.sharedContext.currentPresentationData.with { $0 }
            let strings = GRVMgramStrings(presentationData.strings)
            self.presentController?(textAlertController(
                context: self.context,
                title: strings[.notifyDisconnectConfirmationTitle],
                text: strings[.notifyDisconnectConfirmationText],
                actions: [
                    TextAlertAction(
                        type: .genericAction,
                        title: presentationData.strings.Common_Cancel,
                        action: {}
                    ),
                    TextAlertAction(
                        type: .destructiveAction,
                        title: strings[.notifyDisconnectConfirmationAction],
                        action: { [weak self] in
                            self?.performDisconnect(
                                pairedUserId: target.pairedUserId,
                                sessionHash: target.sessionHash
                            )
                        }
                    )
                ]
            ))
        }))
    }

    private func performDisconnect(
        pairedUserId: Int64,
        sessionHash: Int64
    ) {
        self.actionDisposable.set((self.resolveOwner()
        |> take(1)
        |> deliverOnMainQueue).start(next: { [weak self] target in
            guard let self else {
                return
            }
            guard let target,
                  target.pairedUserId == pairedUserId,
                  target.sessionHash == sessionHash else {
                self.operationState.set(.statusNotVerified(
                    pairedUserId: pairedUserId,
                    sessionHash: sessionHash
                ))
                return
            }

            self.operationState.set(.disconnecting(
                pairedUserId: pairedUserId,
                sessionHash: sessionHash
            ))
            self.actionDisposable.set((target.context.engine.privacy.terminateAnotherSession(id: sessionHash)
            |> timeout(10.0, queue: .mainQueue(), alternate: .fail(.generic))
            |> deliverOnMainQueue).start(error: { [weak self] _ in
                guard let self else {
                    return
                }
                self.operationState.set(.statusNotVerified(
                    pairedUserId: pairedUserId,
                    sessionHash: sessionHash
                ))
                self.showDisconnectFailed()
            }, completed: { [weak self] in
                guard let self else {
                    return
                }
                self.actionDisposable.set((self.clearPair(
                    expectedUserId: pairedUserId,
                    sessionHash: sessionHash
                )
                |> deliverOnMainQueue).start(next: { [weak self] _ in
                    self?.operationState.set(.idle)
                }))
            }))
        }))
    }

    private func clearPair(
        expectedUserId: Int64,
        sessionHash: Int64
    ) -> Signal<GRVMNotifyState, NoError> {
        return self.stateStore.update { state in
            guard state.pairedUserId == expectedUserId,
                  state.sessionHash == sessionHash else {
                return state
            }
            return .empty
        }
        |> take(1)
    }

    private func showDisconnectFailed() {
        let presentationData = self.context.sharedContext.currentPresentationData.with { $0 }
        let strings = GRVMgramStrings(presentationData.strings)
        self.presentController?(textAlertController(
            context: self.context,
            title: strings[.notifyTitle],
            text: strings[.notifyDisconnectFailed],
            actions: [
                TextAlertAction(
                    type: .defaultAction,
                    title: presentationData.strings.Common_OK,
                    action: {}
                )
            ]
        ))
    }

    func startReconciliation() {
        let reconciliation = self.resolveOwner()
        |> take(1)
        |> mapToSignal { target -> Signal<GRVMNotifyReconciliationResult, NoError> in
            guard let target else {
                return .single(.skipped)
            }
            return target.context.engine.privacy.grvmNotifySessionHashesOnce()
            |> timeout(5.0, queue: .mainQueue(), alternate: .fail(.network))
            |> map { hashes -> GRVMNotifyReconciliationResult in
                return .success(target: target, hashes: hashes)
            }
            |> `catch` { _ -> Signal<GRVMNotifyReconciliationResult, NoError> in
                return .single(.failure(target: target))
            }
        }
        |> deliverOnMainQueue

        self.reconciliationDisposable.set(reconciliation.start(next: { [weak self] result in
            guard let self else {
                return
            }
            switch result {
            case .skipped:
                break
            case let .success(target, hashes):
                if !hashes.contains(target.sessionHash) {
                    self.reconciliationDisposable.set((self.clearPair(
                        expectedUserId: target.pairedUserId,
                        sessionHash: target.sessionHash
                    )
                    |> deliverOnMainQueue).start(next: { [weak self] _ in
                        self?.operationState.set(.idle)
                    }))
                }
            case let .failure(target):
                self.operationState.set(.statusNotVerified(
                    pairedUserId: target.pairedUserId,
                    sessionHash: target.sessionHash
                ))
            }
        }))
    }
}

public func grvmNotifySettingsController(context: AccountContext) -> ViewController {
    let stateStore = GRVMNotifyStateStore(accountManager: context.sharedContext.accountManager)
    let model = GRVMNotifySettingsModel(context: context, stateStore: stateStore)
    let activeContexts = context.sharedContext.activeAccountContexts
    |> map { _, accounts, _ -> [AccountContext] in
        return accounts.map { $0.1 }
    }

    let signal = combineLatest(
        context.sharedContext.presentationData,
        stateStore.state(),
        activeContexts,
        model.operationState.get()
    )
    |> map { presentationData, state, activeContexts, operation -> (ItemListControllerState, (ItemListNodeState, Any)) in
        let strings = GRVMgramStrings(presentationData.strings)
        let status = grvmNotifySettingsStatus(
            state: state,
            activeContexts: activeContexts,
            operation: operation
        )
        let entries = grvmNotifySettingsEntries(
            status: status,
            presentationData: presentationData
        )
        let controllerState = ItemListControllerState(
            presentationData: ItemListPresentationData(presentationData),
            title: .text(strings[.notifyTitle]),
            leftNavigationButton: nil,
            rightNavigationButton: nil,
            backNavigationButton: ItemListBackButton(title: presentationData.strings.Common_Back)
        )
        let listState = ItemListNodeState(
            presentationData: ItemListPresentationData(presentationData),
            entries: entries,
            style: .blocks
        )
        return (controllerState, (listState, model))
    }

    let controller = ItemListController(context: context, state: signal)
    model.pushController = { [weak controller] child in
        controller?.push(child)
    }
    model.presentController = { [weak controller] child in
        controller?.present(child, in: .window(.root))
    }
    model.navigationController = { [weak controller] in
        return controller?.navigationController as? NavigationController
    }
    model.startReconciliation()
    return controller
}
