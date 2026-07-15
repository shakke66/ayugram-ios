# GRVMgram Full iOS Parity Design

**Date:** 2026-07-15  
**Base commit:** b3c83ff590774717fd2905a6cd58272b487ee888  
**Working branch:** codex/grvmgram-full-parity  
**Reference implementation:** AyuGram Desktop 6.7.8  
**Reference docs:** AyuGram/AyuGramDocs @ 42f5f32c6b05aab4a69a5f8d0bf7652e1cb11a9b

## Objective

Deliver a sideloadable GRVMgram IPA that:

1. preserves deleted messages from every author inline until explicit user cleanup;
2. preserves locally available deleted media outside Telegram's disposable cache;
3. records edit history for both outgoing and incoming messages and exposes it from the exact message;
4. scopes saved data and Local Premium to the active account;
5. fixes all AyuGram features that have a meaningful iOS equivalent;
6. removes non-functional settings;
7. localizes every GRVMgram-specific user-facing string into Russian with an English fallback;
8. exposes only the GRVMgram public brand and removes AyuGram project links and references;
9. builds successfully in GitHub Actions and produces a validated IPA artifact.

Desktop-only concepts without a meaningful iOS equivalent remain explicitly out of scope: tray actions, Windows Jump List, Desktop Drawer configuration, Windows URL-scheme registration, and original-project donation integrations.

## Approved Product Decisions

- Deleted messages survive application restarts and remain inline indefinitely.
- Deleted messages disappear only through an explicit per-chat/topic or per-account cleanup.
- Already downloaded photos, videos, voice messages, stickers, and files are copied to persistent GRVMgram storage before deletion.
- Persistent media is displayed and played from the original inline message bubble.
- Media that was not locally available at deletion time keeps its message card and metadata but is not represented as downloadable.
- Edit history stores revisions for both the current user and other users.
- Long-pressing a revised message exposes a History action that opens only that message's revisions.
- Every AyuGram feature with a meaningful iOS equivalent is implemented or corrected.
- Every GRVMgram-specific user-facing string receives Russian and English values.
- Public UI uses GRVMgram exclusively.
- Internal AyuGram module names, hook identifiers, Codable keys, and legacy database filename remain unchanged for build and migration compatibility.
- Intermediate one-hour CI builds are avoided. GitHub Actions runs after the complete local implementation and verification pass.
- When a final CI run fails, the failure is diagnosed and fixed, then CI is rerun until a valid IPA is produced.

## Delivery Structure

Implementation is isolated on codex/grvmgram-full-parity and divided into coherent commits:

1. Ghost read-state recursion fix and regression coverage.
2. Account-scoped storage, migrations, and persistent media backup.
3. Complete delete/edit integration, inline UI, per-chat archive, per-message history, and Local Premium.
4. Remaining applicable iOS parity work.
5. Russian localization, GRVMgram public branding, and removal of AyuGram public links.

The implementation branch is pushed as a backup only after local verification. The verified branch is then fast-forwarded into local master and master is pushed once to trigger the final CI run.

## Architecture

### Existing boundaries retained

- AyuGramLib owns settings models, pure storage models, database access, and migration logic.
- AyuGramFeatures owns account-bound feature services and hook wiring.
- AyuGramSettingsUI owns settings, archives, editors, and GRVMgram-specific screens.
- TelegramCore owns authoritative message lifecycle interception.
- TelegramUI owns message rendering, context menus, chat menus, and user-visible status marks.

### New account-bound service

The existing process-global behavior is replaced at integration points by an account-bound service created with:

- account peer ID;
- Postbox;
- MediaBox;
- the account's feature settings;
- the shared database connection.

The service exposes narrowly scoped operations:

- preserveDeletedMessages before a deletion transaction;
- preserveEditRevision before an edit transaction;
- restoreBackedUpMedia when a deleted message is rendered;
- clearDeletedMessages for an account/chat/topic;
- queryDeletedState and queryEditHistory from in-memory indexes;
- accountScopedLocalPremium for a checked peer.

Global hooks remain as compatibility shims only where Telegram's module graph requires them. Hooks that depend on identity accept account and peer identifiers instead of returning process-global booleans.

## Persistent Deleted-State Model

### Postbox attribute

An encodable AyuDeletedMessageAttribute is attached to the original Message before a server deletion can remove it. It stores:

- deletion timestamp;
- source kind: server, local user action, TTL, autoremove, secret recall, or validation;
- backed-up resource identifiers;
- optional topic/thread identifier.

The original Message remains the source for bubble layout, author, reply context, entities, reactions, and media metadata. The deleted attribute drives:

- deleted mark or icon;
- optional 0.7 opacity;
- exclusion from unread mention and unread reaction state;
- History/View Deleted behavior;
- local cleanup eligibility.

### Central deletion policy

Every deletion path calls one policy function before destructive Postbox work. The policy returns:

- preserve: update the Message with deleted state, archive metadata, and skip physical deletion;
- deleteNormally: execute the stock Telegram deletion path;
- forceCleanup: remove a previously preserved Message and its archive/media data.

Preservation is enabled only when Save Deleted Messages is active and the bot-dialog rule permits it. The explicit cleanup path always uses forceCleanup to avoid immediately preserving the same message again.

### Required deletion paths

The policy covers:

- DeleteMessagesWithGlobalIds;
- DeleteMessages;
- DeleteMessagesInteractively;
- secret-chat recall;
- clear-history operations;
- autoremove/TTL expiration;
- minimum-available-message pruning;
- history validation and direct engine deletion paths.

Global message IDs are mapped to MessageId values and messages are read before transaction deletion.

## Account-Scoped Database

The database remains physically named ayugram_messages.db for migration compatibility. Schema versioning is added and all new records include account_id.

### Deleted messages

The logical primary key is:

account_id + peer_id + message_namespace + message_id

Records include topic ID, author ID, original timestamp, deletion timestamp, text, entities, media summary, and deleted-source metadata.

### Edit revisions

The logical key is:

account_id + peer_id + message_namespace + message_id + revision_id

A revision stores the complete previous text/entities snapshot, local revision timestamp, original edit timestamp when available, and a content hash. Repeated delivery of the same update is deduplicated by content hash.

### Media backups

Media rows include:

- account ID;
- peer/message identity;
- original MediaResourceId string;
- relative persistent path;
- byte count;
- media kind;
- backup completion state.

Absolute sandbox paths are never persisted. All paths are resolved relative to the GRVMgram media root.

### Migration

- Existing tables are migrated transactionally before new writes.
- Existing single-account rows are adopted only when exactly one authorized account is available.
- With multiple authorized accounts, unattributed legacy rows remain quarantined under account_id 0 and are not exposed in normal account views.
- Legacy rows are not silently associated with the wrong account.
- Existing global settings are copied as initial defaults into each account's settings record.
- Migration failure rolls back and leaves the original database intact.

## Persistent Media

The media root is:

Documents/GRVMgramDeletedMedia/<account>/<peer>/<message>/

Before deletion, each completed local MediaBox resource is copied atomically:

1. copy to a temporary file in the destination directory;
2. verify the copied byte count;
3. rename the temporary file into its final relative path;
4. commit the media row only after the rename succeeds.

Unavailable or partial resources are recorded as unavailable metadata and are never presented as downloadable.

The original MediaResourceId remains on the Message. When MediaBox no longer has the resource but a verified backup exists, the account service restores the bytes into MediaBox under the same resource identity before playback or full-size display.

Cleanup removes database rows and files only after the corresponding Postbox messages are force-deleted. Failed file deletion is retried on the next cleanup/startup pass and does not corrupt the database transaction.

No automatic retention period or size limit is applied. The user-approved retention rule is explicit cleanup only.

## Edit History

Every edit path captures the current Message before mutating Postbox:

- incoming realtime edits;
- outgoing request-edit responses;
- update differences and offline synchronization;
- media/caption edits when the previous representable version differs.

Revisions are stored for both incoming and outgoing messages. Empty or identical snapshots are not inserted.

Message rendering uses an in-memory revision index, not a synchronous SQLite count during layout. Long-press shows History only when the index contains revisions for the exact account/peer/message key.

The History screen:

- shows only the selected message's revisions;
- orders oldest to newest;
- displays revision time and preserved text/entities;
- displays available backed-up media where applicable;
- has no global cross-message mixing.

The existing global edited-message screen may remain as an additional account-scoped archive, but it is not the primary interaction.

## Deleted Message UI

- A deleted message stays in its original chronological position.
- Replace with Icons selects the icon renderer.
- Text mode supports arbitrary Unicode text or emoji.
- The default deleted mark is 🧹.
- The edited mark is freely editable and defaults to the localized edited value.
- Translucent Deleted Messages applies 0.7 opacity to preserved messages while excluding admin log and archive presentation.
- Chat menu: GRVMgram → View Deleted and Clear Deleted.
- View Deleted filters by account, dialog, and topic and supports Search and Clear.
- Per-account settings include a global deleted archive and global cleanup.

## Local Premium

Local Premium is true only when:

- the feature is enabled for the active account; and
- checkedPeerId equals that account's own peer ID.

It may unlock local UI gates and draw the local premium badge for the current account. It does not modify arbitrary peers, server feature flags, server limits, or remote premium state.

## Ghost Mode Parity

Ghost Mode contains five independent account-scoped components:

1. suppress message read receipts;
2. suppress story views;
3. suppress online presence;
4. suppress typing/upload activities;
5. send an offline packet after forced online activity.

Additional behavior:

- locked components are not changed by the master toggle;
- Read on Interact covers sending, reactions, and poll voting;
- Read on Interact and Schedule Messages are mutually exclusive;
- Story Ghost prompt appears before opening and can enable Ghost before the view operation;
- Send without Sound supports Never, In Ghost, and Always;
- scheduling uses current Desktop 6.7.8 timing:
  - text/existing media: 12 seconds;
  - voice/video message: 17 seconds;
  - new file: 13 + max(6, ceil(sizeMiB × 0.7)), minimum 19 seconds;
  - proxy: ceil(delay × 1.2).

The pending Opus change consumes the read-state operation through confirmSynchronizedIncomingReadState without sending a server receipt. A bare synchronous complete signal is not used.

## Remaining Applicable iOS Parity

The current section 9 matrix in bdopus.md is the functional checklist. Applicable partial/missing behavior includes:

- blocked-user filters;
- author/forward-aware Shadow Ban;
- per-filter case sensitivity and type/button inputs;
- working translation-provider selection from providers available on iOS;
- external-link warning control;
- Desktop-style supported-domain link rewriting;
- independent Webview height/width controls;
- complete added-sticker filtering;
- Hide/Mute/Discuss channel bottom-button behavior;
- real context-menu semantics for Local Hide, User Messages, Details, Repeat, Add Filter, and modifier state;
- freely editable deleted/edited marks;
- deleted-message translucency;
- message bubble radius and single-corner behavior;
- complete premium-status hiding;
- Message Shot;
- Attach/Emoji popup equivalents appropriate to touch UI;
- crash-reporting consumer;
- seeking controls;
- service-message time;
- channel badge;
- jump to beginning;
- callback-data copy;
- local/server Read All;
- Send as Sticker;
- Copy ID actions;
- account/chat/channel profile dates;
- Streamer privacy using iOS screen-capture APIs;
- all other applicable entries listed in section 9.8 of bdopus.md.

No setting remains visible if it has no consumer and no implementation in this release.

## Localization and Public Branding

All GRVMgram-specific user-visible text is moved out of Swift string literals into localization resources with:

- complete Russian values;
- complete English fallback values.

Telegram's normal language selection remains authoritative.

Public branding rules:

- GRVMgram is used in settings titles, menus, alerts, archives, explanatory text, crash UI, display name, and app metadata;
- the About/Project/Links section is removed;
- AyuGram channels, chats, documentation, GitHub, Crowdin, Boosty, crypto, and original-project URLs are removed from user-facing UI;
- no user-visible AyuGram name remains;
- internal AyuGram module/type/hook names, Codable keys, and the database filename remain unchanged.

## Performance and Concurrency

- Message layout never performs synchronous SQLite COUNT queries.
- Deleted and revised message identities are held in account-scoped in-memory sets.
- Sets are loaded at account-service startup and updated atomically with writes.
- Mutable settings and compiled filter collections have a single synchronization owner.
- Database operations use one serialized queue; UI reads use immutable snapshots.
- Media copying runs outside the main thread.

## Error Handling

- Database migrations and multi-row writes are transactional.
- A failed archive write does not suppress the original Telegram deletion unless preservation state was safely committed.
- A failed media backup preserves the message and metadata but marks the resource unavailable.
- Cleanup is idempotent.
- Duplicate server updates do not duplicate deletion records or revisions.
- Account mismatch never returns data from another account.
- Missing backup files degrade to unavailable media instead of crashing.

## Verification

Implementation follows red-green-refactor for testable logic.

Required local checks:

- schema creation and migration tests;
- single-account legacy adoption test;
- multi-account legacy quarantine test;
- account-isolation queries;
- deleted-message idempotency;
- edit-revision deduplication and ordering;
- media backup/restore/cleanup;
- force-cleanup bypass;
- Ghost scheduling formulas;
- Local Premium account/peer predicate;
- filter and Shadow Ban predicates;
- localization key completeness;
- static hook producer/consumer audit;
- search for remaining user-visible AyuGram strings and removed URLs;
- secret scan;
- correctness review;
- security review of paths, account boundaries, and stored data.

Windows cannot compile the complete iOS Bazel graph. Static verification therefore precedes one final GitHub Actions build.

## Final CI and IPA Validation

1. Push the verified implementation branch as backup.
2. Fast-forward local master to the verified branch.
3. Push master once, triggering the CI workflow.
4. Monitor the run with gh until completion.
5. On failure, read the complete compiler/linker ERROR block, identify the root cause, add or adjust a regression/static check where possible, commit the focused fix, push, and monitor the replacement run.
6. Repeat until CI succeeds.
7. Download the artifact.
8. Verify that the IPA is non-empty, opens as a ZIP, contains Payload/*.app, and reports the GRVMgram display name.
9. Provide the successful run ID and artifact name to the user for iPhone installation.

## Acceptance Criteria

The release is complete only when:

- deleted messages from every known author remain inline after restart;
- downloaded deleted media still opens after Telegram cache cleanup;
- explicit per-chat/topic and account cleanup removes bubbles, database rows, and backup files;
- edit history contains outgoing and incoming revisions and opens from the exact message;
- no account can see another account's saved data;
- Local Premium affects only the active account's own peer;
- all applicable matrix entries have working consumers and Desktop-equivalent or documented iOS-native behavior;
- all GRVMgram-specific UI is localized in Russian with English fallback;
- no user-facing AyuGram project reference or URL remains;
- GitHub Actions is green;
- the downloaded artifact passes IPA structure and branding checks.
