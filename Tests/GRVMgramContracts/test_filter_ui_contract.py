import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILTER_MODEL = ROOT / "submodules/AyuGramLib/Sources/AyuMessageFilter.swift"
FILTERS = ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramFiltersController.swift"
EDITOR = ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramFilterEditorController.swift"
SHADOW = ROOT / "submodules/AyuGramSettingsUI/Sources/AyuGramShadowBanController.swift"
SETTINGS_BUILD = ROOT / "submodules/AyuGramSettingsUI/BUILD"
CHAT = ROOT / "submodules/TelegramUI/Sources/ChatController.swift"
HISTORY_NODE = ROOT / "submodules/TelegramUI/Sources/ChatHistoryListNode.swift"
LIST_VIEW = ROOT / "submodules/Display/Source/ListView.swift"
MESSAGE_MENU = (
    ROOT
    / "submodules/TelegramUI/Sources/Chat/ChatControllerOpenMessageContextMenu.swift"
)
LOCALIZATION_ITEM = ROOT / "submodules/TranslateUI/Sources/LocalizationListItem.swift"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def function_window(source: str, signature: str, size: int = 8000) -> str:
    start = source.find(signature)
    if start < 0:
        return ""
    return source[start : start + size]


class FilterUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = read(FILTER_MODEL)
        cls.filters = read(FILTERS)
        cls.editor = read(EDITOR)
        cls.shadow = read(SHADOW)
        cls.settings_build = read(SETTINGS_BUILD)
        cls.chat = read(CHAT)
        cls.history_node = read(HISTORY_NODE)
        cls.list_view = read(LIST_VIEW)
        cls.message_menu = read(MESSAGE_MENU)
        cls.localization_item = read(LOCALIZATION_ITEM)

    def test_backup_envelope_is_public_and_versioned(self) -> None:
        self.assertIn(
            "public struct AyuMessageFilterBackup: Codable, Equatable", self.model
        )
        self.assertIn("public let version: Int", self.model)
        self.assertIn("public let filters: [AyuMessageFilter]", self.model)
        self.assertRegex(
            self.model,
            r"public init\(\s*version: Int,\s*filters: \[AyuMessageFilter\]",
        )

    def test_editor_factory_owns_a_local_draft_and_commits_by_uuid(self) -> None:
        self.assertRegex(
            self.editor,
            r"public func ayuGramFilterEditorController\(\s*"
            r"context: AccountContext,\s*"
            r"filter: AyuMessageFilter\? = nil,\s*"
            r"initialExpression: String = \"\",\s*"
            r"initialPeerId: PeerId\? = nil,\s*"
            r"onSaved: \(\(\) -> Void\)\? = nil\s*"
            r"\) -> ViewController",
        )
        for token in (
            "AyuGramFilterEditorState",
            "ValuePromise",
            "Atomic",
            "filter ?? AyuMessageFilter(",
            "expression: initialExpression",
            "peerId: initialPeerId?.toInt64()",
            "ItemListMultilineInputItem",
            "NSRegularExpression(pattern:",
            "textAlertController(",
            "updateGRVMSettings(",
            "accountId: context.account.peerId",
            "settings.filters.firstIndex(where: { $0.id == draft.id })",
            "settings.filters.append(draft)",
        ):
            self.assertIn(token, self.editor)
        self.assertNotIn("settings.messageFilters", self.editor)
        self.assertNotIn("settings.reversedFilters", self.editor)

    def test_filter_controllers_import_account_context_alert_adapter(self) -> None:
        for source in (self.filters, self.editor):
            self.assertIn("import PresentationDataUtils", source)
            self.assertRegex(source, r"textAlertController\(\s*context:")

    def test_editor_uses_real_single_and_multiple_peer_pickers(self) -> None:
        for token in (
            "context.sharedContext.makePeerSelectionController(",
            "PeerSelectionControllerParams(",
            "controller.peerSelected =",
            "multipleSelection: true",
            "immediatelyActivateMultipleSelection: true",
            "controller.multiplePeersSelected =",
            ".id.toInt64()",
            "excludedPeerIds",
        ):
            self.assertIn(token, self.editor)

    def test_filters_screen_uses_canonical_ordered_rows(self) -> None:
        for token in (
            "grvmSettings(accountId: context.account.peerId",
            "updateGRVMSettings(accountId: context.account.peerId",
            "settings.filters",
            "LocalizationListItem(",
            "LocalizationListItemEditing(",
            "reorderable: true",
            "removeFilter:",
            "ayuGramFilterEditorController(",
            "controller.setReorderEntry",
            "fromFilter.id",
            "toFilter.id",
        ):
            self.assertIn(token, self.filters)
        entries = function_window(self.filters, "private func ayuGramFiltersEntries(")
        self.assertNotIn("settings.messageFilters", entries)
        self.assertNotIn("settings.reversedFilters", entries)

    def test_reused_filter_row_has_a_real_reorder_handle(self) -> None:
        for token in (
            "ItemListEditableReorderControlNode.asyncLayout",
            "item.editing.reorderable",
            "strongSelf.reorderControlNode = reorderControlNode",
            "override func isReorderable(at point: CGPoint) -> Bool",
        ):
            self.assertIn(token, self.localization_item)

    def test_clear_is_confirmed_and_only_removes_filters(self) -> None:
        clear_window = function_window(self.filters, "clearFilters: {")
        self.assertIn("textAlertController(", clear_window)
        self.assertIn(".destructiveAction", clear_window)
        self.assertIn("settings.filters.removeAll()", clear_window)
        for forbidden in (
            "enableFilters =",
            "enableFiltersInChats =",
            "hideFromBlockedUsers =",
            "shadowBanIds =",
        ):
            self.assertNotIn(forbidden, clear_window)

    def test_import_is_bounded_validated_scoped_and_confirmed(self) -> None:
        for token in (
            "1_048_576",
            "UIDocumentPickerViewController(documentTypes: [\"public.json\"], in: .import)",
            "UIDocumentPickerDelegate",
            "startAccessingSecurityScopedResource()",
            "stopAccessingSecurityScopedResource()",
            ".fileSizeKey",
            ".isRegularFileKey",
            "JSONDecoder().decode(AyuMessageFilterBackup.self",
            "backup.version == 2",
            "Set<UUID>()",
            "NSRegularExpression(pattern:",
            "enabledCount",
            "reversedCount",
            "chatScopedCount",
            "textAlertController(",
            "replaceFilters(backup.filters)",
        ):
            self.assertIn(token, self.filters)

        import_window = function_window(
            self.filters, "private func importFilters(from url: URL)", 12000
        )
        self.assertLess(
            import_window.find("fileSize"),
            import_window.find("JSONDecoder().decode"),
            "file size must be checked before JSON decoding",
        )
        self.assertLess(
            import_window.find("textAlertController("),
            import_window.find("replaceFilters(backup.filters)"),
            "replacement must happen only from the confirmation action",
        )
        self.assertIn("let transferController:", self.filters)

    def test_export_is_v2_sorted_pretty_and_cleans_temp_file(self) -> None:
        export_window = function_window(
            self.filters, "private func exportFilters(_ filters: [AyuMessageFilter])", 8000
        )
        for token in (
            "AyuMessageFilterBackup(version: 2, filters: filters)",
            ".prettyPrinted",
            ".sortedKeys",
            "FileManager.default.temporaryDirectory",
            "write(to: fileUrl, options: .atomic)",
            "UIActivityViewController(",
            "activityItems: [fileUrl]",
            "completionWithItemsHandler",
            "removeItem(at: fileUrl)",
            "popoverPresentationController",
            "applicationBindings.presentNativeController(activityController)",
        ):
            self.assertIn(token, export_window)

    def test_shadow_screen_is_account_scoped_and_peer_backed(self) -> None:
        for token in (
            "grvmSettings(accountId: context.account.peerId",
            "updateGRVMSettings(accountId: context.account.peerId",
            "settings.shadowBanIds",
            "GRVMShadowBanPolicy.normalizedPeerIds(",
            "GRVMShadowBanPolicy.updatedPeerIds(",
            ".excludeSavedMessages",
            "makePeerSelectionController(",
            "controller.peerSelected =",
            "peer.id.toInt64()",
            "deleteAction:",
        ):
            self.assertIn(token, self.shadow)

    def test_message_actions_are_wired_to_real_editor_and_author_choices(self) -> None:
        for token in (
            "AyuGramHooks.matchingMessageFilterIds?(self.context.account.peerId, message)",
            "ayuGramFiltersController(context: self.context, matchingFilterIds:",
            "ayuGramFilterEditorController(",
            "initialExpression: message.text",
            "initialPeerId: message.id.peerId",
            "message.author?.id",
            "message.forwardInfo?.author?.id",
            "message.sourceAuthorInfo?.originalAuthor",
            "peerId != self.context.account.peerId",
            "settings.shadowBanIds",
            "updateGRVMSettings(accountId: self.context.account.peerId",
            "GRVMShadowBanPolicy.updatedPeerIds(",
        ):
            self.assertIn(token, self.chat)
        self.assertIn("grvmMessageFilterContextMenuItems(", self.message_menu)
        self.assertIn("actions.content = .list(itemList)", self.message_menu)
        self.assertIn("grvmSettings(", self.message_menu)
        self.assertIn("accountId: self.context.account.peerId", self.message_menu)
        self.assertIn("settings.shadowBanIds", self.message_menu)

        message_actions = function_window(
            self.chat, "func grvmMessageFilterContextMenuItems("
        )
        self.assertIn(
            "grvmFilteredVisibilityContextMenuItems(peerId: message.id.peerId)",
            message_actions,
        )
        self.assertIn("shadowBanPeerIds.contains(author.peerId)", message_actions)
        self.assertNotIn("AyuGramHooks.isShadowBanned?(", message_actions)

        shadow_start = self.chat.find("private func grvmSetShadowBanned(")
        shadow_end = self.chat.find(
            "\n    func grvmFilteredVisibilityContextMenuItems(", shadow_start
        )
        shadow_update = self.chat[shadow_start:shadow_end]
        self.assertIn(
            "self.chatDisplayNode.historyNode.refreshForRuntimeMessageFilterChange()",
            shadow_update,
        )
        self.assertNotIn("self.reloadChatLocation(", shadow_update)

    def test_show_filtered_is_runtime_only_and_reloads_history(self) -> None:
        window = function_window(self.chat, "func grvmFilteredVisibilityContextMenuItems(")
        for token in (
            "AyuGramHooks.isShowingFilteredMessages?(",
            "AyuGramHooks.setShowingFilteredMessages?(",
            "self.context.account.peerId",
            "self.chatDisplayNode.historyNode.refreshForRuntimeMessageFilterChange()",
        ):
            self.assertIn(token, window)
        self.assertNotIn("updateGRVMSettings", window)
        self.assertNotIn("self.reloadChatLocation(", window)
        self.assertIn(
            "func refreshForRuntimeMessageFilterChange()",
            self.history_node,
        )
        refresh_window = function_window(
            self.history_node, "func refreshForRuntimeMessageFilterChange()"
        )
        self.assertIn(
            "beginChatHistoryTransitions(resetScrolling: true, switchedToAnotherSource: false)",
            refresh_window,
        )
        self.assertGreaterEqual(
            self.chat.count("grvmFilteredVisibilityContextMenuItems(peerId:"), 3
        )

    def test_message_filter_save_refreshes_the_active_history_after_persistence(self) -> None:
        self.assertRegex(
            self.editor,
            r"public func ayuGramFilterEditorController\(\s*"
            r"context: AccountContext,\s*"
            r"filter: AyuMessageFilter\? = nil,\s*"
            r"initialExpression: String = \"\",\s*"
            r"initialPeerId: PeerId\? = nil,\s*"
            r"onSaved: \(\(\) -> Void\)\? = nil\s*"
            r"\) -> ViewController",
        )
        save_window = function_window(self.editor, "saveImpl = { draft in", 8000)
        completion = function_window(
            save_window, "|> deliverOnMainQueue).startStandalone(completed:"
        )
        self.assertIn("onSaved?()", completion)
        self.assertIn("dismissImpl?()", completion)
        self.assertLess(completion.index("onSaved?()"), completion.index("dismissImpl?()"))

        add_filter = function_window(
            self.chat, "if includeAddFilter {", 2500
        )
        self.assertIn("onSaved: { [weak self] in", add_filter)
        self.assertIn(
            "self?.chatDisplayNode.historyNode.refreshForRuntimeMessageFilterChange()",
            add_filter,
        )

    def test_show_filtered_recomputes_distinct_header_affinities_for_split_groups(self) -> None:
        assign = function_window(
            self.list_view, "private func assignHeaderSpaceAffinities()", 5000
        )
        for token in (
            "var claimedExistingAffinityIds = Set<Int>()",
            "func reuseExistingAffinity(",
            "claimedExistingAffinityIds.insert(existingAffinity).inserted",
            "reuseExistingAffinity(existingAffinity, for: currentAffinity)",
            "reuseExistingAffinity(existingAffinity, for: currentAffinity)",
        ):
            self.assertIn(token, assign)
        self.assertGreaterEqual(assign.count("reuseExistingAffinity("), 3)
        self.assertIn("self.assignHeaderSpaceAffinities()", self.list_view)

    def test_build_uses_only_existing_internal_ui_modules(self) -> None:
        self.assertIn('"//submodules/AlertUI:AlertUI"', self.settings_build)
        self.assertIn('"//submodules/TranslateUI:TranslateUI"', self.settings_build)
        self.assertNotIn("CocoaPods", self.settings_build)
        self.assertNotIn("SwiftPackage", self.settings_build)

    def test_modified_ui_adds_no_public_ayugram_literal(self) -> None:
        literal = re.compile(r'"[^"\n]*AyuGram[^"\n]*"')
        for source in (self.filters, self.editor, self.shadow, self.chat):
            self.assertIsNone(literal.search(source))


if __name__ == "__main__":
    unittest.main()
