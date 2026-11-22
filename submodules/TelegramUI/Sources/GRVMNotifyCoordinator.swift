import Foundation
import AccountContext
import AlertUI
import AyuGramLib
import Display
import Postbox
import PresentationDataUtils
import SwiftSignalKit
import TelegramCore
import TelegramPresentationData

final class GRVMNotifyCoordinator {
    struct Environment {
        let stateStore: GRVMNotifyStateStoring
        let activeAccounts: Signal<(primary: AccountContext?, accounts: [(AccountRecordId, AccountContext, Int32)], currentAuth: UnauthorizedAccount?), NoError>
        let authorizedContext: () -> Signal<AuthorizedApplicationContext, NoError>
        let isLocked: Signal<Bool, NoError>
        let present: (ViewController) -> Void
        let navigate: (AccountRecordId, PeerId, Int64?, MessageId) -> Void
        let openReturnURL: (URL) -> Void
    }

    private struct ResolvedAccount {
        let recordId: AccountRecordId
        let context: AccountContext
        let userId: Int64
    }

    private struct RequestOwner {
        let recordId: AccountRecordId
        let userId: Int64
    }

    private enum AuthorizationResolution {
        case target(ResolvedAccount)
        case pendingUnavailable
        case alreadyConnected
        case accountUnavailable
    }

    private enum NavigationResolution {
        case target(ResolvedAccount)
        case ownershipMismatch
        case accountUnavailable
    }

    private enum ErrorKey: String {
        case invalidLink = "GRVMgram.Notify.Error.InvalidLink"
        case pendingExpired = "GRVMgram.Notify.Error.PendingExpired"
        case alreadyConnected = "GRVMgram.Notify.Error.AlreadyConnected"
        case accountUnavailable = "GRVMgram.Notify.Error.AccountUnavailable"
        case authInvalid = "GRVMgram.Notify.Error.AuthInvalid"
        case authExpired = "GRVMgram.Notify.Error.AuthExpired"
        case authAlreadyAccepted = "GRVMgram.Notify.Error.AuthAlreadyAccepted"
        case authGeneric = "GRVMgram.Notify.Error.AuthGeneric"
        case persistence = "GRVMgram.Notify.Error.Persistence"
        case ownershipMismatch = "GRVMgram.Notify.Error.OwnershipMismatch"
        case chatUnsynchronized = "GRVMgram.Notify.Error.ChatUnsynchronized"
    }

    private let environment: Environment
    private let authDisposable = MetaDisposable()
    private let navigationDisposable = MetaDisposable()
    private let accountsDisposable = MetaDisposable()
    private let authorizationCommitDisposables = DisposableSet()
    private let authorizationFinalizationIdle = ValuePromise<Bool>(true, ignoreRepeated: true)

    private var requestGeneration: Int = 0
    private var currentOwner: RequestOwner?
    private weak var currentPrompt: ViewController?

    init(environment: Environment) {
        self.environment = environment
        self.accountsDisposable.set((environment.activeAccounts
        |> deliverOnMainQueue).start(next: { [weak self] snapshot in
            guard let self, let owner = self.currentOwner else {
                return
            }
            let matches = snapshot.accounts.filter { recordId, context, _ in
                return recordId == owner.recordId
                    && context.account.peerId.id._internalGetInt64Value() == owner.userId
            }
            if matches.count != 1 {
                self.cancelCurrentRequest()
            }
        }))
    }

    deinit {
        self.authDisposable.dispose()
        self.navigationDisposable.dispose()
        self.accountsDisposable.dispose()
        self.authorizationCommitDisposables.dispose()
    }

    @discardableResult
    func enqueue(url: URL) -> Bool {
        guard url.scheme?.lowercased() == "grvmgram" else {
            return false
        }

        let generation = self.beginRequest()
        guard let deepLink = GRVMNotifyDeepLink.parse(url) else {
            self.enqueueInvalidLink(generation: generation)
            return true
        }

        switch deepLink {
        case let .authorize(token, returnURL):
            self.enqueueAuthorization(token: token, returnURL: returnURL, generation: generation)
        case let .openMessage(accountUserId, peer, messageId, threadId):
            self.enqueueNavigation(
                accountUserId: accountUserId,
                peer: peer,
                messageId: messageId,
                threadId: threadId,
                generation: generation
            )
        }
        return true
    }

    private func beginRequest() -> Int {
        self.cancelCurrentRequest()
        return self.requestGeneration
    }

    private func cancelCurrentRequest() {
        self.requestGeneration += 1
        self.currentOwner = nil
        self.authDisposable.set(nil)
        self.navigationDisposable.set(nil)
        self.currentPrompt?.dismiss()
        self.currentPrompt = nil
    }

    private func isCurrent(_ generation: Int) -> Bool {
        return self.requestGeneration == generation
    }

    private func readyContext() -> Signal<AuthorizedApplicationContext, NoError> {
        return self.environment.authorizedContext()
        |> mapToSignal { context -> Signal<AuthorizedApplicationContext, NoError> in
            return context.isReady.get()
            |> filter { $0 }
            |> take(1)
            |> map { _ in context }
        }
        |> take(1)
        |> mapToSignal { [isLocked = self.environment.isLocked] context -> Signal<AuthorizedApplicationContext, NoError> in
            return isLocked
            |> filter { !$0 }
            |> take(1)
            |> map { _ in context }
        }
    }

    private func enqueueInvalidLink(generation: Int) {
        self.authDisposable.set((self.readyContext()
        |> deliverOnMainQueue).start(next: { [weak self] context in
            self?.showError(.invalidLink, context: context.context, generation: generation)
        }))
    }

    private func enqueueAuthorization(token: Data, returnURL: URL, generation: Int) {
        let signal = self.readyContext()
        |> mapToSignal { [weak self] context -> Signal<(AuthorizedApplicationContext, AuthorizationResolution), NoError> in
            guard let self else {
                return .complete()
            }
            return self.waitForAuthorizationFinalization()
            |> mapToSignal { [weak self] _ -> Signal<AuthorizationResolution, NoError> in
                guard let self else {
                    return .complete()
                }
                return self.resolveAuthorizationTarget()
            }
            |> map { resolution in
                return (context, resolution)
            }
        }
        |> deliverOnMainQueue

        self.authDisposable.set(signal.start(next: { [weak self] readyContext, resolution in
            guard let self, self.isCurrent(generation) else {
                return
            }
            switch resolution {
            case let .target(target):
                self.currentOwner = RequestOwner(recordId: target.recordId, userId: target.userId)
                self.loadAccountNameAndPresentConfirmation(
                    target: target,
                    token: token,
                    returnURL: returnURL,
                    generation: generation
                )
            case .pendingUnavailable:
                self.showError(.pendingExpired, context: readyContext.context, generation: generation)
            case .alreadyConnected:
                self.showError(.alreadyConnected, context: readyContext.context, generation: generation)
            case .accountUnavailable:
                self.showError(.accountUnavailable, context: readyContext.context, generation: generation)
            }
        }))
    }

    private func waitForAuthorizationFinalization() -> Signal<Void, NoError> {
        return self.authorizationFinalizationIdle.get()
        |> filter { $0 }
        |> take(1)
        |> map { _ in Void() }
    }

    private func normalizedState() -> Signal<GRVMNotifyState, NoError> {
        return self.environment.stateStore.state()
        |> map { state in
            let timestamp = Int32(clamping: Int64(Date().timeIntervalSince1970))
            return state.normalized(now: timestamp)
        }
    }

    private func resolveAuthorizationTarget(
        expectedUserId: Int64? = nil,
        expectedRecordId: AccountRecordId? = nil
    ) -> Signal<AuthorizationResolution, NoError> {
        return combineLatest(
            self.normalizedState() |> take(1),
            self.environment.activeAccounts |> take(1)
        )
        |> map { state, snapshot -> AuthorizationResolution in
            if state.pairedUserId != nil || state.sessionHash != nil {
                return .alreadyConnected
            }
            guard let pendingUserId = state.pendingAccountUserId,
                  state.pendingStartedAt != nil,
                  expectedUserId == nil || expectedUserId == pendingUserId else {
                return .pendingUnavailable
            }
            let matches = snapshot.accounts.filter { recordId, context, _ in
                guard context.account.peerId.id._internalGetInt64Value() == pendingUserId else {
                    return false
                }
                return expectedRecordId == nil || expectedRecordId == recordId
            }
            guard matches.count == 1 else {
                return .accountUnavailable
            }
            let match = matches[0]
            return .target(ResolvedAccount(recordId: match.0, context: match.1, userId: pendingUserId))
        }
    }

    private func loadAccountNameAndPresentConfirmation(
        target: ResolvedAccount,
        token: Data,
        returnURL: URL,
        generation: Int
    ) {
        self.authDisposable.set((target.context.engine.data.get(
            TelegramEngine.EngineData.Item.Peer.Peer(id: target.context.account.peerId)
        )
        |> take(1)
        |> deliverOnMainQueue).start(next: { [weak self] peer in
            guard let self, self.isCurrent(generation) else {
                return
            }
            guard let peer else {
                self.showError(.accountUnavailable, context: target.context, generation: generation)
                return
            }
            let accountName = peer.compactDisplayTitle.isEmpty
                ? String(target.userId)
                : peer.compactDisplayTitle
            self.presentAuthorizationConfirmation(
                accountName: accountName,
                target: target,
                token: token,
                returnURL: returnURL,
                generation: generation
            )
        }))
    }

    private func presentAuthorizationConfirmation(
        accountName: String,
        target: ResolvedAccount,
        token: Data,
        returnURL: URL,
        generation: Int
    ) {
        let presentationData = target.context.sharedContext.currentPresentationData.with { $0 }
        let title = self.localized("GRVMgram.Notify.Authorization.Title", context: target.context)
        let text = self.localized(
            "GRVMgram.Notify.Authorization.Confirmation",
            argument: accountName,
            context: target.context
        )
        let authorizeTitle = self.localized("GRVMgram.Notify.Authorization.Action", context: target.context)
        let controller = textAlertController(
            context: target.context,
            title: title,
            text: text,
            actions: [
                TextAlertAction(type: .genericAction, title: presentationData.strings.Common_Cancel, action: { [weak self] in
                    guard let self, self.isCurrent(generation) else {
                        return
                    }
                    self.cancelCurrentRequest()
                }),
                TextAlertAction(type: .defaultAction, title: authorizeTitle, action: { [weak self] in
                    self?.revalidateAndApprove(
                        target: target,
                        token: token,
                        returnURL: returnURL,
                        generation: generation
                    )
                })
            ]
        )
        self.present(controller)
    }

    private func revalidateAndApprove(
        target: ResolvedAccount,
        token: Data,
        returnURL: URL,
        generation: Int
    ) {
        guard self.isCurrent(generation) else {
            return
        }
        self.currentPrompt = nil
        let signal = self.readyContext()
        |> mapToSignal { [weak self] context -> Signal<(AuthorizedApplicationContext, AuthorizationResolution), NoError> in
            guard let self else {
                return .complete()
            }
            return self.waitForAuthorizationFinalization()
            |> mapToSignal { [weak self] _ -> Signal<AuthorizationResolution, NoError> in
                guard let self else {
                    return .complete()
                }
                return self.resolveAuthorizationTarget(
                    expectedUserId: target.userId,
                    expectedRecordId: target.recordId
                )
            }
            |> map { resolution in
                return (context, resolution)
            }
        }
        |> deliverOnMainQueue

        self.authDisposable.set(signal.start(next: { [weak self] readyContext, resolution in
            guard let self, self.isCurrent(generation) else {
                return
            }
            switch resolution {
            case let .target(freshTarget):
                self.approve(
                    target: freshTarget,
                    token: token,
                    returnURL: returnURL,
                    generation: generation
                )
            case .pendingUnavailable:
                self.showError(.pendingExpired, context: readyContext.context, generation: generation)
            case .alreadyConnected:
                self.showError(.alreadyConnected, context: readyContext.context, generation: generation)
            case .accountUnavailable:
                self.showError(.accountUnavailable, context: readyContext.context, generation: generation)
            }
        }))
    }

    private func approve(
        target: ResolvedAccount,
        token: Data,
        returnURL: URL,
        generation: Int
    ) {
        self.authorizationFinalizationIdle.set(false)
        let commitDisposable = MetaDisposable()
        self.authorizationCommitDisposables.add(commitDisposable)
        let activeSessionsContext = target.context.engine.privacy.activeSessions()
        commitDisposable.set((approveAuthTransferToken(
            account: target.context.account,
            token: token,
            activeSessionsContext: activeSessionsContext
        )
        |> deliverOnMainQueue).start(next: { [weak commitDisposable] session in
            guard let commitDisposable else {
                return
            }
            self.persistApprovedSession(
                session: session,
                activeSessionsContext: activeSessionsContext,
                target: target,
                returnURL: returnURL,
                generation: generation,
                commitDisposable: commitDisposable
            )
        }, error: { [weak commitDisposable] error in
            guard let commitDisposable else {
                return
            }
            self.finishAuthorizationCommit(commitDisposable)
            guard self.isCurrent(generation) else {
                return
            }
            let key: ErrorKey
            switch error {
            case .invalid:
                key = .authInvalid
            case .expired:
                key = .authExpired
            case .alreadyAccepted:
                key = .authAlreadyAccepted
            case .generic:
                key = .authGeneric
            }
            self.showError(key, context: target.context, generation: generation)
        }))
    }

    private func persistApprovedSession(
        session: RecentAccountSession,
        activeSessionsContext: ActiveSessionsContext,
        target: ResolvedAccount,
        returnURL: URL,
        generation: Int,
        commitDisposable: MetaDisposable
    ) {
        guard session.hash != 0 else {
            self.finishAuthorizationCommit(commitDisposable)
            self.showError(.authGeneric, context: target.context, generation: generation)
            return
        }
        guard self.isCurrent(generation) else {
            self.rollbackUnverifiedSession(
                sessionHash: session.hash,
                activeSessionsContext: activeSessionsContext,
                target: target,
                generation: generation,
                commitDisposable: commitDisposable,
                reportPersistenceError: false
            )
            return
        }
        commitDisposable.set((self.resolveAuthorizationTarget(
            expectedUserId: target.userId,
            expectedRecordId: target.recordId
        )
        |> deliverOnMainQueue).start(next: { [weak commitDisposable] resolution in
            guard let commitDisposable else {
                return
            }
            guard self.isCurrent(generation), case let .target(freshTarget) = resolution else {
                self.rollbackUnverifiedSession(
                    sessionHash: session.hash,
                    activeSessionsContext: activeSessionsContext,
                    target: target,
                    generation: generation,
                    commitDisposable: commitDisposable,
                    reportPersistenceError: false
                )
                return
            }
            self.writeApprovedSession(
                sessionHash: session.hash,
                activeSessionsContext: activeSessionsContext,
                target: freshTarget,
                returnURL: returnURL,
                generation: generation,
                commitDisposable: commitDisposable
            )
        }))
    }

    private func writeApprovedSession(
        sessionHash: Int64,
        activeSessionsContext: ActiveSessionsContext,
        target: ResolvedAccount,
        returnURL: URL,
        generation: Int,
        commitDisposable: MetaDisposable
    ) {
        let state = GRVMNotifyState(
            pairedUserId: target.userId,
            sessionHash: sessionHash,
            pendingAccountUserId: nil,
            pendingStartedAt: nil
        )
        commitDisposable.set((self.environment.stateStore.writeAndVerify(state)
        |> take(1)
        |> deliverOnMainQueue).start(next: { [weak commitDisposable] verified in
            guard let commitDisposable else {
                return
            }
            if verified {
                guard self.isCurrent(generation) else {
                    self.rollbackUnverifiedSession(
                        sessionHash: sessionHash,
                        activeSessionsContext: activeSessionsContext,
                        target: target,
                        generation: generation,
                        commitDisposable: commitDisposable,
                        reportPersistenceError: false
                    )
                    return
                }
                self.finishAuthorizationCommit(commitDisposable)
                self.currentOwner = nil
                self.showAuthorizationSuccess(
                    context: target.context,
                    returnURL: returnURL,
                    generation: generation
                )
            } else {
                self.rollbackUnverifiedSession(
                    sessionHash: sessionHash,
                    activeSessionsContext: activeSessionsContext,
                    target: target,
                    generation: generation,
                    commitDisposable: commitDisposable,
                    reportPersistenceError: true
                )
            }
        }))
    }

    private func rollbackUnverifiedSession(
        sessionHash: Int64,
        activeSessionsContext: ActiveSessionsContext,
        target: ResolvedAccount,
        generation: Int,
        commitDisposable: MetaDisposable,
        reportPersistenceError: Bool
    ) {
        let clearState = self.environment.stateStore.update { state in
            var state = state
            if state.pairedUserId == target.userId && state.sessionHash == sessionHash {
                state.pairedUserId = nil
                state.sessionHash = nil
            }
            return state
        }
        |> take(1)
        |> deliverOnMainQueue

        commitDisposable.set(clearState.start(next: { [weak commitDisposable] _ in
            guard let commitDisposable else {
                return
            }
            commitDisposable.set((activeSessionsContext.remove(hash: sessionHash)
            |> deliverOnMainQueue).start(error: { [weak commitDisposable] _ in
                guard let commitDisposable else {
                    return
                }
                self.finishAuthorizationCommit(commitDisposable)
                if reportPersistenceError {
                    self.showError(.persistence, context: target.context, generation: generation)
                }
            }, completed: { [weak commitDisposable] in
                guard let commitDisposable else {
                    return
                }
                self.finishAuthorizationCommit(commitDisposable)
                if reportPersistenceError {
                    self.showError(.persistence, context: target.context, generation: generation)
                }
            }))
        }))
    }

    private func finishAuthorizationCommit(_ disposable: MetaDisposable) {
        self.authorizationCommitDisposables.remove(disposable)
        self.authorizationFinalizationIdle.set(true)
    }

    private func showAuthorizationSuccess(
        context: AccountContext,
        returnURL: URL,
        generation: Int
    ) {
        guard self.isCurrent(generation) else {
            return
        }
        let presentationData = context.sharedContext.currentPresentationData.with { $0 }
        let success = self.localized("GRVMgram.Notify.Authorization.Success", context: context)
        let fallback = self.localized("GRVMgram.Notify.Authorization.OpenPWAFallback", context: context)
        let controller = textAlertController(
            context: context,
            title: self.localized("GRVMgram.Notify.Title", context: context),
            text: success + "\n\n" + fallback,
            actions: [
                TextAlertAction(type: .defaultAction, title: presentationData.strings.Common_OK, action: {})
            ]
        )
        self.present(controller)
        self.environment.openReturnURL(returnURL)
    }

    private func enqueueNavigation(
        accountUserId: Int64,
        peer: GRVMNotifyPeer,
        messageId: Int32,
        threadId: Int64?,
        generation: Int
    ) {
        let signal = self.readyContext()
        |> mapToSignal { [weak self] context -> Signal<(AuthorizedApplicationContext, NavigationResolution), NoError> in
            guard let self else {
                return .complete()
            }
            return self.waitForAuthorizationFinalization()
            |> mapToSignal { [weak self] _ -> Signal<NavigationResolution, NoError> in
                guard let self else {
                    return .complete()
                }
                return self.resolveNavigationTarget(accountUserId: accountUserId)
            }
            |> map { resolution in (context, resolution) }
        }
        |> deliverOnMainQueue

        self.navigationDisposable.set(signal.start(next: { [weak self] readyContext, resolution in
            guard let self, self.isCurrent(generation) else {
                return
            }
            switch resolution {
            case let .target(target):
                self.currentOwner = RequestOwner(recordId: target.recordId, userId: target.userId)
                self.waitForPeerAndNavigate(
                    target: target,
                    peer: peer,
                    messageId: messageId,
                    threadId: threadId,
                    generation: generation
                )
            case .ownershipMismatch:
                self.showError(.ownershipMismatch, context: readyContext.context, generation: generation)
            case .accountUnavailable:
                self.showError(.accountUnavailable, context: readyContext.context, generation: generation)
            }
        }))
    }

    private func resolveNavigationTarget(
        accountUserId: Int64,
        expectedRecordId: AccountRecordId? = nil
    ) -> Signal<NavigationResolution, NoError> {
        return combineLatest(
            self.normalizedState() |> take(1),
            self.environment.activeAccounts |> take(1)
        )
        |> map { state, snapshot -> NavigationResolution in
            guard state.pairedUserId == accountUserId,
                  let sessionHash = state.sessionHash,
                  sessionHash != 0 else {
                return .ownershipMismatch
            }
            let matches = snapshot.accounts.filter { recordId, context, _ in
                guard context.account.peerId.id._internalGetInt64Value() == accountUserId else {
                    return false
                }
                return expectedRecordId == nil || expectedRecordId == recordId
            }
            guard matches.count == 1 else {
                return .accountUnavailable
            }
            let match = matches[0]
            return .target(ResolvedAccount(recordId: match.0, context: match.1, userId: accountUserId))
        }
    }

    private func waitForPeerAndNavigate(
        target: ResolvedAccount,
        peer: GRVMNotifyPeer,
        messageId: Int32,
        threadId: Int64?,
        generation: Int
    ) {
        let peerId: PeerId
        switch peer {
        case let .user(rawId):
            peerId = PeerId(namespace: Namespaces.Peer.CloudUser, id: PeerId.Id._internalFromInt64Value(rawId))
        case let .group(rawId):
            peerId = PeerId(namespace: Namespaces.Peer.CloudGroup, id: PeerId.Id._internalFromInt64Value(rawId))
        case let .channel(rawId):
            peerId = PeerId(namespace: Namespaces.Peer.CloudChannel, id: PeerId.Id._internalFromInt64Value(rawId))
        }
        let cloudMessageId = MessageId(peerId: peerId, namespace: Namespaces.Message.Cloud, id: messageId)
        let peerSignal: Signal<EnginePeer?, NoError> = target.context.engine.data.subscribe(
            TelegramEngine.EngineData.Item.Peer.Peer(id: peerId)
        )
        |> filter { $0 != nil }
        |> take(1)
        |> timeout(5.0, queue: .mainQueue(), alternate: .single(nil))

        self.navigationDisposable.set((peerSignal
        |> deliverOnMainQueue).start(next: { [weak self] localPeer in
            guard let self, self.isCurrent(generation) else {
                return
            }
            guard localPeer != nil else {
                self.showError(.chatUnsynchronized, context: target.context, generation: generation)
                return
            }
            self.revalidateAndNavigate(
                target: target,
                peerId: peerId,
                threadId: threadId,
                messageId: cloudMessageId,
                generation: generation
            )
        }))
    }

    private func revalidateAndNavigate(
        target: ResolvedAccount,
        peerId: PeerId,
        threadId: Int64?,
        messageId: MessageId,
        generation: Int
    ) {
        self.navigationDisposable.set((self.resolveNavigationTarget(
            accountUserId: target.userId,
            expectedRecordId: target.recordId
        )
        |> deliverOnMainQueue).start(next: { [weak self] resolution in
            guard let self, self.isCurrent(generation) else {
                return
            }
            switch resolution {
            case let .target(freshTarget):
                self.currentOwner = nil
                self.environment.navigate(freshTarget.recordId, peerId, threadId, messageId)
            case .ownershipMismatch:
                self.showError(.ownershipMismatch, context: target.context, generation: generation)
            case .accountUnavailable:
                self.showError(.accountUnavailable, context: target.context, generation: generation)
            }
        }))
    }

    private func showError(_ key: ErrorKey, context: AccountContext, generation: Int) {
        guard self.isCurrent(generation) else {
            return
        }
        self.currentOwner = nil
        let presentationData = context.sharedContext.currentPresentationData.with { $0 }
        let controller = textAlertController(
            context: context,
            title: self.localized("GRVMgram.Notify.Title", context: context),
            text: self.localized(key.rawValue, context: context),
            actions: [
                TextAlertAction(type: .defaultAction, title: presentationData.strings.Common_OK, action: {})
            ]
        )
        self.present(controller)
    }

    private func present(_ controller: ViewController) {
        self.currentPrompt?.dismiss()
        self.currentPrompt = controller
        self.environment.present(controller)
    }

    private func localized(_ rawValue: String, context: AccountContext) -> String {
        let presentationData = context.sharedContext.currentPresentationData.with { $0 }
        let strings = GRVMgramStrings(presentationData.strings)
        guard let key = GRVMgramStringKey(rawValue: rawValue) else {
            return rawValue
        }
        return strings[key]
    }

    private func localized(_ rawValue: String, argument: String, context: AccountContext) -> String {
        let presentationData = context.sharedContext.currentPresentationData.with { $0 }
        let strings = GRVMgramStrings(presentationData.strings)
        guard let key = GRVMgramStringKey(rawValue: rawValue) else {
            return rawValue + "\n" + argument
        }
        return strings.format(key, argument)
    }
}
