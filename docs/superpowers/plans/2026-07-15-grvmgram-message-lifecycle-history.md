# GRVMgram Message Lifecycle and History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve every locally known deleted message inline without corrupting unread state, capture every incoming/outgoing edit revision, expose per-chat deleted archives and per-message history, and scope Local Premium correctly.

**Architecture:** Add a neutral Postbox local-deletion marker and a dedicated history-table operation that removes unread/unseen/pending state while retaining the message row and visual incoming direction. Route every user-visible deletion through one TelegramCore helper; use persistent attributes and the account archive coordinator for rendering and UI.

**Tech Stack:** Swift, Postbox ValueBox tables, TelegramCore update state, MediaBox, TelegramUI context menus, AyuGramSettingsUI, SwiftSignalKit, Python source contracts.

## Global Constraints

- Preserve only messages that existed in local Postbox; unknown server-deleted content cannot be reconstructed.
- Do not preserve technical upload/resync/unsent placeholders.
- A preserved incoming message must stop contributing to unread exactly once.
- Keep `MessageFlags.Incoming` for bubble direction while clearing the incoming-count bit in history indexes.
- Clear unread mention/reaction/poll/pinned and pending/timestamp actions, but retain normal media tags, thread membership, and history count.
- Explicit cleanup must bypass preservation and physically delete the row and archive files.
- Layout code must not query SQLite.
- Do not launch GitHub Actions during this plan.

---

## File Map

### Create

- `submodules/Postbox/Sources/LocalMessageDeletionMarker.swift`
- `submodules/TelegramCore/Sources/SyncCore/GRVMDeletedMessageAttribute.swift`
- `submodules/TelegramCore/Sources/SyncCore/GRVMEditHistoryMessageAttribute.swift`
- `submodules/TelegramCore/Sources/TelegramEngine/Messages/ApplyGRVMMessageDeletion.swift`
- `submodules/AyuGramSettingsUI/Sources/GRVMMessageHistoryController.swift`
- `Tests/GRVMgramContracts/test_local_deletion_contract.py`
- `Tests/GRVMgramContracts/test_delete_routes_contract.py`
- `Tests/GRVMgramContracts/test_edit_routes_contract.py`
- `Tests/GRVMgramContracts/test_history_ui_contract.py`

### Modify

- `submodules/Postbox/Sources/Postbox.swift`
- `submodules/Postbox/Sources/MessageHistoryTable.swift:186-228,3003-3045`
- `submodules/Postbox/Sources/MessageHistoryIndexTable.swift:136-159,224-260`
- `submodules/TelegramCore/Sources/Account/AccountManager.swift:135`
- `submodules/TelegramCore/Sources/SyncCore/SyncCore_StandaloneAccountTransaction.swift:114`
- all user-visible deletion routes listed in Task 3
- `submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift:224-340`
- `submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift:4412-4505`
- `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- `submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/StringForMessageTimestampStatus.swift:223`
- `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift:2195`
- `submodules/TelegramUI/Sources/ChatController.swift:5602-5970`
- `submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift`
- `submodules/AyuGramSettingsUI/Sources/AyuGramEditedMessagesController.swift`
- `submodules/TelegramCore/Sources/Utils/PeerUtils.swift:209`
- `submodules/TelegramUI/BUILD`

---

### Task 1: Add Postbox's neutral locally-deleted marker and index bit

**Files:**
- Create: `submodules/Postbox/Sources/LocalMessageDeletionMarker.swift`
- Modify: `submodules/Postbox/Sources/MessageHistoryIndexTable.swift`
- Modify: `submodules/Postbox/Sources/MessageHistoryTable.swift`
- Test: `Tests/GRVMgramContracts/test_local_deletion_contract.py`

**Interfaces:**
- Produces:

```swift
public protocol LocalMessageDeletionMarker: MessageAttribute {}

func isLocallyDeletedMessage(_ attributes: [MessageAttribute]) -> Bool

func markMessageLocallyDeleted(
    _ id: MessageId,
    attribute: MessageAttribute
) -> Bool
```

- [ ] **Step 1: Write failing Postbox source contracts**

```python
# Tests/GRVMgramContracts/test_local_deletion_contract.py
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LocalDeletionContractTests(unittest.TestCase):
    def test_marker_protocol_exists(self) -> None:
        source = (ROOT / "submodules/Postbox/Sources/LocalMessageDeletionMarker.swift").read_text(encoding="utf-8")
        self.assertIn("protocol LocalMessageDeletionMarker", source)

    def test_incoming_counts_skip_marker(self) -> None:
        source = (ROOT / "submodules/Postbox/Sources/MessageHistoryTable.swift").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("isLocallyDeletedMessage"), 2)

    def test_index_has_local_deletion_bit(self) -> None:
        source = (ROOT / "submodules/Postbox/Sources/MessageHistoryIndexTable.swift").read_text(encoding="utf-8")
        self.assertIn("HistoryEntryMessageFlagLocallyDeleted", source)
        self.assertIn("markMessageLocallyDeleted", source)
```

- [ ] **Step 2: Run tests to verify failure**

```powershell
python -m unittest Tests.GRVMgramContracts.test_local_deletion_contract -v
```

Expected: FAIL because the marker file is absent.

- [ ] **Step 3: Add the neutral protocol and helper**

```swift
import Foundation

public protocol LocalMessageDeletionMarker: MessageAttribute {
}

@inline(__always)
func isLocallyDeletedMessage(_ attributes: [MessageAttribute]) -> Bool {
    return attributes.contains(where: { $0 is LocalMessageDeletionMarker })
}
```

- [ ] **Step 4: Add a dedicated history-index flag**

```swift
private let HistoryEntryTypeMask: Int8 = 1
private let HistoryEntryMessageFlagIncoming: Int8 = 1 << 1
private let HistoryEntryMessageFlagLocallyDeleted: Int8 = 1 << 2
```

Implement `MessageHistoryIndexTable.markMessageLocallyDeleted(_ id: MessageId)` to:

1. load the existing entry;
2. preserve timestamp and message type;
3. clear `HistoryEntryMessageFlagIncoming`;
4. set `HistoryEntryMessageFlagLocallyDeleted`;
5. write the entry once;
6. return false when already marked.

Every incoming-count method must require incoming-bit set and locally-deleted-bit clear.

Update `justInsertMessage` so a message already carrying `LocalMessageDeletionMarker` writes `HistoryEntryMessageFlagLocallyDeleted` and never writes the incoming bit. This preserves the invariant when a timestamp change removes and reinserts the index entry.

- [ ] **Step 5: Skip marker attributes in full history-table count scans**

Update `incomingMessageStatsInIndices` and `incomingMessageCountInRange`:

```swift
if entry.message.id.namespace == namespace
    && !entry.message.flags.intersection(.IsIncomingMask).isEmpty
    && !isLocallyDeletedMessage(entry.message.attributes) {
    count += 1
}
```

- [ ] **Step 6: Run tests and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_local_deletion_contract -v
git diff --check
git add submodules/Postbox/Sources/LocalMessageDeletionMarker.swift submodules/Postbox/Sources/MessageHistoryIndexTable.swift submodules/Postbox/Sources/MessageHistoryTable.swift Tests/GRVMgramContracts/test_local_deletion_contract.py
git commit -m "feat: mark retained messages locally deleted"
```

### Task 2: Implement the atomic local-deletion history transition

**Files:**
- Modify: `submodules/Postbox/Sources/Postbox.swift`
- Modify: `submodules/Postbox/Sources/MessageHistoryTable.swift`
- Modify: `submodules/Postbox/Sources/MessageHistoryTagsTable.swift`
- Test: `Tests/GRVMgramContracts/test_local_deletion_contract.py`

**Interfaces:**
- Produces:

```swift
public func markMessageAsLocallyDeleted(
    id: MessageId,
    attribute: MessageAttribute
) -> Bool
```

- [ ] **Step 1: Extend the failing contract with cleanup invariants**

Assert the local-deletion method references:

```text
readStateTable.deleteMessages
unseenPersonalMessage
unseenReaction
unseenPollVote
pinned
pendingActions
timestampBasedMessageAttributes
markMessageLocallyDeleted
```

and does not call `justRemove` or `deleteMessages`.

- [ ] **Step 2: Run the focused test**

```powershell
python -m unittest Tests.GRVMgramContracts.test_local_deletion_contract -v
```

Expected: FAIL with missing transition anchors.

- [ ] **Step 3: Implement an idempotent transition**

Within one Postbox transaction:

1. get the current message and index;
2. return false when it already contains a `LocalMessageDeletionMarker`;
3. call `readStateTable.deleteMessages` once for that index;
4. remove only `.unseenPersonalMessage`, `.unseenReaction`, `.unseenPollVote`, and `.pinned` summary/tag entries;
5. remove pending actions and timestamp-based actions;
6. preserve media tags, local tags unrelated to unread, thread ID, grouping, and the message row;
7. update the message attributes with the deletion marker;
8. call `messageHistoryIndexTable.markMessageLocallyDeleted`;
9. emit a normal `.Update` history operation so views redraw.

Do not clear `MessageFlags.Incoming` on the Message object.

- [ ] **Step 4: Expose the transaction method**

```swift
public func markMessageAsLocallyDeleted(id: MessageId, attribute: MessageAttribute) -> Bool {
    return self.postbox?.markMessageAsLocallyDeleted(
        transaction: self,
        id: id,
        attribute: attribute
    ) ?? false
}
```

Add the matching `fileprivate PostboxImpl.markMessageAsLocallyDeleted(transaction:id:attribute:)` next to `updateMessage(transaction:id:update:)`. It forwards every current operation accumulator (`currentOperationsByPeerId`, read-state, pending actions, tag summaries, local tags, and timestamp attributes) into `MessageHistoryTable.markMessageAsLocallyDeleted`, then invokes installed store/update actions for the retained updated message.

- [ ] **Step 5: Add idempotency and tag-preservation source fixtures**

The contract must reject a transition that:

- calls unread deletion after the marker check fails;
- removes all message tags;
- clears `.Incoming`;
- physically removes the row.

- [ ] **Step 6: Run and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_local_deletion_contract -v
git diff --check
git add submodules/Postbox/Sources/Postbox.swift submodules/Postbox/Sources/MessageHistoryTable.swift submodules/Postbox/Sources/MessageHistoryIndexTable.swift submodules/Postbox/Sources/MessageHistoryTagsTable.swift Tests/GRVMgramContracts/test_local_deletion_contract.py
git commit -m "feat: preserve deleted rows without unread drift"
```

### Task 3: Add persistent TelegramCore attributes and preserve them across merges

**Files:**
- Create: `submodules/TelegramCore/Sources/SyncCore/GRVMDeletedMessageAttribute.swift`
- Create: `submodules/TelegramCore/Sources/SyncCore/GRVMEditHistoryMessageAttribute.swift`
- Modify: `submodules/TelegramCore/Sources/Account/AccountManager.swift:135`
- Modify: `submodules/TelegramCore/Sources/SyncCore/SyncCore_StandaloneAccountTransaction.swift:114`
- Test: `Tests/GRVMgramContracts/test_local_deletion_contract.py`

**Interfaces:**
- Produces:

```swift
public enum GRVMDeletionSource: Int32 {
    case server = 0
    case localAction = 1
    case ttl = 2
    case secretRecall = 3
    case validation = 4
    case minimumAvailable = 5
}

public final class GRVMDeletedMessageAttribute: MessageAttribute, LocalMessageDeletionMarker, Equatable {
    public let deletedAt: Int32
    public let source: GRVMDeletionSource
    public let topicId: Int64?
    public let resourceIds: [String]
}

public final class GRVMEditHistoryMessageAttribute: MessageAttribute, Equatable {
    public let latestRevisionAt: Int32
}
```

- [ ] **Step 1: Add failing registration/merge assertions**

Assert both classes are declared through `declareEncodable` and explicitly retained by `mergeMessageAttributes`.

- [ ] **Step 2: Run tests**

```powershell
python -m unittest Tests.GRVMgramContracts.test_local_deletion_contract -v
```

Expected: FAIL with missing attributes.

- [ ] **Step 3: Implement compact Postbox encoding**

Use keys `d`, `s`, `t`, and `r` for deleted timestamp/source/topic/resources; use `d` for edit-history timestamp. Decode missing optional fields safely for forward compatibility.

- [ ] **Step 4: Register and merge local attributes**

Register both types in `telegramUIDeclareEncodables`/AccountManager next to `EditedMessageAttribute`. When server attributes merge, retain the previous local deleted/history attributes unless an explicit force-cleanup transaction removed them.

- [ ] **Step 5: Run and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_local_deletion_contract -v
git diff --check
git add submodules/TelegramCore/Sources/SyncCore/GRVMDeletedMessageAttribute.swift submodules/TelegramCore/Sources/SyncCore/GRVMEditHistoryMessageAttribute.swift submodules/TelegramCore/Sources/Account/AccountManager.swift submodules/TelegramCore/Sources/SyncCore/SyncCore_StandaloneAccountTransaction.swift Tests/GRVMgramContracts/test_local_deletion_contract.py
git commit -m "feat: persist GRVMgram message state"
```

### Task 4: Centralize all user-visible deletion routes

**Files:**
- Create: `submodules/TelegramCore/Sources/TelegramEngine/Messages/ApplyGRVMMessageDeletion.swift`
- Modify: deletion routes listed below
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Modify: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Test: `Tests/GRVMgramContracts/test_delete_routes_contract.py`

**Interfaces:**
- Produces:

```swift
public static var preserveDeletedMessages: ((PeerId, [Message], GRVMDeletionSource) -> [MessageId: [String]])?

public func preserveDeletedMessages(_ messages: [Message], source: GRVMDeletionSource) -> [MessageId: [String]]

public enum GRVMDeletionMode {
    case server(GRVMDeletionSource)
    case forceCleanup
}

func _internal_applyMessageDeletion(
    accountPeerId: PeerId,
    transaction: Transaction,
    mediaBox: MediaBox,
    ids: [MessageId],
    mode: GRVMDeletionMode
) -> [MessageId]
```

- [ ] **Step 1: Write a failing route inventory test**

The test contains an exact path/anchor map and requires every anchor to call `_internal_applyMessageDeletion`:

```text
AccountStateManagementUtils.swift: DeleteMessagesWithGlobalIds
AccountStateManagementUtils.swift: DeleteMessages
DeleteMessagesInteractively.swift
ManagedAutoremoveMessageOperations.swift
ProcessSecretChatIncomingDecryptedOperations.swift
HistoryViewStateValidation.swift
UpdateCachedPeerData.swift
DeleteMessages.swift range/author/forward-author
RemovePeerChat.swift
TelegramEngineMessages.swift
```

- [ ] **Step 2: Run the inventory**

```powershell
python -m unittest Tests.GRVMgramContracts.test_delete_routes_contract -v
```

Expected: FAIL and list every unconverted route.

- [ ] **Step 3: Implement eligibility and partitioning**

```swift
private func grvmCanArchive(_ message: Message) -> Bool {
    switch message.id.namespace {
    case Namespaces.Message.Cloud, Namespaces.Message.SecretIncoming:
        return true
    case Namespaces.Message.Local:
        return message.flags.intersection([.Unsent, .Failed, .Sending]).isEmpty
    default:
        return false
    }
}
```

The helper:

1. loads messages before deletion;
2. keeps any already marked message unless mode is `.forceCleanup`, even if saving is now disabled;
3. partitions the remaining technical and user-visible messages;
4. calls `preserveDeletedMessages` for the exact account and candidate messages;
5. treats only dictionary entries returned after a successful synchronous metadata commit as preserved;
6. marks those messages locally deleted and stores each entry's resource-ID array in `GRVMDeletedMessageAttribute`;
7. physically deletes technical, disabled, and persistence-failed messages through stock `_internal_deleteMessages`;
8. returns the preserved message/resource dictionary.

The coordinator returns an empty dictionary when `saveDeletedMessages` is disabled. `saveForBots` is checked only when the deleted message's dialog peer is a direct bot user; it does not gate group/channel messages authored by bots and never gates edit-history capture.

- [ ] **Step 4: Convert ID-based and range-based routes**

- For global IDs, call `transaction.messageIdsForGlobalIds(ids)` before mutation.
- For ranges, author, forward-author, and peer removal, collect IDs through `Transaction.withAllMessages` before applying the helper.
- Keep the stock fast range deletion only when Save Deleted Messages is disabled.
- Pass `.forceCleanup` from GRVMgram Clear Deleted actions.

- [ ] **Step 5: Exclude technical routes**

Do not route these through preservation:

```text
EnqueueMessage.swift unsent placeholder
PendingPeerMediaUploadManager.swift upload placeholder
QuickReplyMessages.swift resync cleanup
ScheduledMessages.swift sent placeholder
ManagedSecretChatOutgoingOperations.swift failed outgoing cleanup
```

Document them in the route inventory allowlist so a future direct delete is reviewed.

- [ ] **Step 6: Break validation ranges around retained markers**

In `HistoryViewStateValidation.swift:171,279`, treat a locally deleted marker as a boundary. At the physical-delete sites around lines 987 and 1170, guard against deleting marked messages.

- [ ] **Step 7: Run route tests and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_delete_routes_contract -v
rg -n "_internal_deleteMessages\(|transaction\.deleteMessages\(" submodules/TelegramCore/Sources -g "*.swift"
git diff --check
git add submodules/TelegramCore/Sources submodules/Postbox/Sources submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift Tests/GRVMgramContracts/test_delete_routes_contract.py
git commit -m "feat: preserve every visible deletion route"
```

Expected: route tests PASS; remaining direct deletes are all technical allowlist entries.

### Task 5: Capture incoming and outgoing edit revisions before mutation

**Files:**
- Modify: `submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift:224-340`
- Modify: `submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift:4468`
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Modify: `submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift`
- Test: `Tests/GRVMgramContracts/test_edit_routes_contract.py`

**Interfaces:**
- Hook:

```swift
public static var preserveEditRevision: ((PeerId, Message) -> Bool)?

public func preserveEditRevision(_ message: Message) -> Bool
```

- [ ] **Step 1: Write failing route and dedupe tests**

Require pre-update hook calls for:

```text
RequestEditMessage.swift updateEditMessage
RequestEditMessage.swift updateNewMessage
RequestEditMessage.swift updateNewChannelMessage
RequestEditMessage.swift updateEditChannelMessage
AccountStateManagementUtils.swift EditMessage
```

Also require the coordinator to compute a canonical fingerprint before store insertion.

- [ ] **Step 2: Run tests**

```powershell
python -m unittest Tests.GRVMgramContracts.test_edit_routes_contract -v
```

Expected: FAIL for the four outgoing response branches.

- [ ] **Step 3: Extract one outgoing-update helper**

```swift
private func grvmApplyEditedMessage(
    accountPeerId: PeerId,
    transaction: Transaction,
    id: MessageId,
    message: StoreMessage
) {
    var shouldMarkHistory = false
    if let previous = transaction.getMessage(id) {
        shouldMarkHistory = AyuGramHooks.preserveEditRevision?(accountPeerId, previous) == true
    }
    transaction.updateMessage(id, update: { previous in
        return .update(grvmMergedEditedMessage(
            previous: previous,
            incoming: message,
            markHistory: shouldMarkHistory
        ))
    })
}
```

Use it in all four response cases. The incoming state-manager hook remains before its update.

- [ ] **Step 4: Add the persistent edit marker**

`preserveEditRevision` collects the previous version's media resources, atomically stores the revision plus `.copying` blob/mapping rows, and schedules the same persistent-media copier used for deletions. After it returns true, update the current message with `GRVMEditHistoryMessageAttribute(latestRevisionAt:)`. Fingerprint includes stable JSON for text, entities, media kind, and resource IDs. Identical content produces no new row.

- [ ] **Step 5: Run and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_edit_routes_contract -v
git diff --check
git add submodules/TelegramCore/Sources/PendingMessages/RequestEditMessage.swift submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift submodules/TelegramCore/Sources/AyuGramHooks.swift submodules/AyuGramFeatures/Sources/GRVMMessageArchiveCoordinator.swift Tests/GRVMgramContracts/test_edit_routes_contract.py
git commit -m "feat: capture every message edit revision"
```

### Task 6: Render deleted/edited state without SQLite layout calls

**Files:**
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageDateAndStatusNode/Sources/StringForMessageTimestampStatus.swift:223`
- Modify: `submodules/TelegramUI/Components/Chat/ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift`
- Modify: grouped/sticker/file media nodes identified by the existing date/status path
- Test: `Tests/GRVMgramContracts/test_history_ui_contract.py`

**Interfaces:**
- Consumes: `GRVMDeletedMessageAttribute`, `GRVMEditHistoryMessageAttribute`, account settings snapshot.
- Produces: localized free-form marks/icons and optional 0.7 opacity.

- [ ] **Step 1: Write failing render contracts**

Assert:

- timestamp status checks message attributes;
- no `isMessageDeletedCheck` or `hasEditHistoryCheck` call remains in layout code;
- no `AyuDeletedMessagesDB` reference exists under TelegramUI components;
- deleted opacity checks the attribute and excludes admin-log/archive subjects.

- [ ] **Step 2: Run tests**

```powershell
python -m unittest Tests.GRVMgramContracts.test_history_ui_contract -v
```

Expected: FAIL on current synchronous DB hooks.

- [ ] **Step 3: Render marks from attributes**

Use:

```swift
let isDeleted = message.attributes.contains(where: { $0 is GRVMDeletedMessageAttribute })
let hasHistory = message.attributes.contains(where: { $0 is GRVMEditHistoryMessageAttribute })
```

When icon mode is off, display the arbitrary user string. Default deleted mark resolves to `🧹`; empty edited mark resolves through GRVMgram localization.

- [ ] **Step 4: Apply opacity at the common item-node level**

Set content alpha to 0.7 only for locally deleted normal chat messages. Keep 1.0 for admin log, View Deleted, selection overlays, and context-menu previews.

- [ ] **Step 5: Run and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_history_ui_contract -v
rg -n "AyuDeletedMessagesDB|isMessageDeletedCheck|hasEditHistoryCheck" submodules/TelegramUI -g "*.swift"
git diff --check
git add submodules/TelegramUI/Components Tests/GRVMgramContracts/test_history_ui_contract.py
git commit -m "feat: render persistent deleted message state"
```

Expected: contract PASS and grep has no layout-path database query.

### Task 7: Add per-message History and account/chat/topic deleted archives

**Files:**
- Create: `submodules/AyuGramSettingsUI/Sources/GRVMMessageHistoryController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramDeletedMessagesController.swift`
- Modify: `submodules/AyuGramSettingsUI/Sources/AyuGramEditedMessagesController.swift`
- Modify: `submodules/AyuGramLib/Sources/AyuDeletedMessagesDB.swift`
- Modify: `submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift:2195`
- Modify: `submodules/TelegramUI/Sources/ChatController.swift:5602-5970`
- Modify: `submodules/TelegramUI/BUILD`
- Test: `Tests/GRVMgramContracts/test_history_ui_contract.py`

**Interfaces:**
- Produces:

```swift
public func grvmDeletedMessagesController(
    context: AccountContext,
    peerId: PeerId? = nil,
    threadId: Int64? = nil
) -> ViewController

public func grvmMessageHistoryController(
    context: AccountContext,
    messageId: MessageId
) -> ViewController

public func clearDeleted(peerId: PeerId?, threadId: Int64?) -> Signal<[MessageId], NoError>

public static var hasEditHistory: ((PeerId, MessageId) -> Bool)?
```

- [ ] **Step 1: Extend failing UI contracts**

Require:

- History only for one selected message with a persistent history marker or an account index hit from migrated revisions;
- controller call includes exact `message.id`;
- deleted controller receives `context.account.peerId`, peer, and thread;
- Clear Deleted calls force cleanup and waits for completion;
- item actions are non-empty;
- search filters archived text for the active account only.

- [ ] **Step 2: Run tests**

```powershell
python -m unittest Tests.GRVMgramContracts.test_history_ui_contract -v
```

Expected: FAIL because the per-message controller is absent and global rows have empty actions.

- [ ] **Step 3: Implement the message History screen**

Load revisions asynchronously from the current account service, append the current Postbox message as the last version, sort oldest-to-newest, and render preserved text/entities/media. An empty legacy query shows the localized empty state.

- [ ] **Step 4: Add the long-press History action**

Insert near the existing edited/details block:

```swift
if selectedMessages.count == 1,
   (message.attributes.contains(where: { $0 is GRVMEditHistoryMessageAttribute })
       || AyuGramHooks.hasEditHistory?(context.account.peerId, message.id) == true) {
    items.append(.action(ContextMenuActionItem(
        text: grvmStrings[.messageMenuHistory],
        icon: { theme in generateTintedImage(image: UIImage(bundleImageName: "Chat/Context Menu/History"), color: theme.contextMenu.primaryColor) },
        action: { [weak controller] _, dismiss in
            dismiss(.default)
            controller?.push(grvmMessageHistoryController(context: context, messageId: message.id))
        }
    )))
}
```

- [ ] **Step 5: Implement View Deleted and Clear Deleted**

Add GRVMgram submenu items to every real chat menu path, including regular chats, reply threads, forum topics, bot forums, and Saved Messages. The query is `account + peer + optional thread`. Clear presents confirmation and calls the coordinator, which reads cleanup keys, force-deletes those Postbox rows in one transaction, then removes database mappings/rows and now-unreferenced media files. Refresh only after that signal completes; a failure before Postbox deletion leaves database rows and files intact.

- [ ] **Step 6: Add the direct module dependency**

Add `//submodules/AyuGramSettingsUI:AyuGramSettingsUI` to TelegramUI's BUILD dependencies. Verify no reverse dependency from AyuGramSettingsUI to TelegramUI exists.

- [ ] **Step 7: Retire the legacy synchronous database API**

Run `rg -n "AyuDeletedMessagesDB" submodules -g "*.swift"` and require that only the compatibility declaration remains. Replace its implementation with an empty deprecated compatibility enum (the module graph does not allow AyuGramLib to import AyuGramFeatures); remove `getDeletedMessages`, `getAllDeletedMessages`, `getEditHistory`, `getAllEditedMessages`, `isMessageDeleted`, and `hasEditHistory` after the grep proves there are no consumers.

- [ ] **Step 8: Run tests and commit**

```powershell
python -m unittest Tests.GRVMgramContracts.test_history_ui_contract -v
git diff --check
git add submodules/AyuGramSettingsUI/Sources submodules/AyuGramLib/Sources/AyuDeletedMessagesDB.swift submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift submodules/TelegramUI/Sources/ChatController.swift submodules/TelegramUI/BUILD Tests/GRVMgramContracts/test_history_ui_contract.py
git commit -m "feat: add chat archives and message history"
```

### Task 8: Scope Local Premium to the current account's own peer

**Files:**
- Modify: `submodules/TelegramCore/Sources/AyuGramHooks.swift`
- Modify: `submodules/TelegramCore/Sources/Utils/PeerUtils.swift:209`
- Modify: `submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift`
- Test: `Tests/GRVMgramContracts/test_local_premium_contract.py`

**Interfaces:**
- Hook:

```swift
public static var isLocalPremiumEnabled: ((PeerId) -> Bool)?
```

- [ ] **Step 1: Write failing scope tests**

Assert:

- `PeerUtils` passes `self.id`;
- manager returns true only when the primary account's settings enable Local Premium and the tested peer equals that primary account's own peer ID;
- no zero-argument Local Premium hook remains.

- [ ] **Step 2: Run tests**

```powershell
python -m unittest Tests.GRVMgramContracts.test_local_premium_contract -v
```

Expected: FAIL on the current zero-argument closure.

- [ ] **Step 3: Implement the scoped predicate**

```swift
AyuGramHooks.isLocalPremiumEnabled = { [weak self] checkedPeerId in
    guard let self else { return false }
    guard let service = self.registry.primaryService() else { return false }
    return checkedPeerId == service.accountPeerId
        && service.settingsSnapshot().localTelegramPremium
}
```

Preserve the stock server value for every other peer.

- [ ] **Step 4: Run the complete lifecycle gate**

```powershell
python -m unittest discover -s Tests/GRVMgramContracts -p "test_*.py" -v
rg -n "isLocalPremiumEnabled\?\(\)" submodules -g "*.swift"
git diff --check
```

Expected: all tests PASS; grep returns no zero-argument consumer.

- [ ] **Step 5: Commit**

```powershell
git add submodules/TelegramCore/Sources/AyuGramHooks.swift submodules/TelegramCore/Sources/Utils/PeerUtils.swift submodules/AyuGramFeatures/Sources/AyuGramFeatureManager.swift Tests/GRVMgramContracts/test_local_premium_contract.py
git commit -m "fix: scope Local Premium to own accounts"
```
