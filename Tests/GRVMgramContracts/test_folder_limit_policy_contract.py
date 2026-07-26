from pathlib import Path
from collections.abc import Callable
import unittest


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = (
    "submodules/TelegramUI/Components/ChatList/"
    "ChatListFilterTabContainerNode/Sources/ChatListFilterTabContainerNode.swift"
)
CHAT_LIST_PATH = "submodules/ChatListUI/Sources/ChatListController.swift"
CHAT_LIST_NODE_PATH = "submodules/ChatListUI/Sources/ChatListControllerNode.swift"
PEER_SELECTION_PATH = (
    "submodules/TelegramUI/Components/PeerSelectionController/"
    "Sources/PeerSelectionController.swift"
)
HORIZONTAL_TABS_PATH = (
    "submodules/TelegramUI/Components/HorizontalTabsComponent/"
    "Sources/HorizontalTabsComponent.swift"
)


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def swift_block(text: str, signature: str) -> str:
    start = text.find(signature)
    if start == -1:
        raise AssertionError(f"Missing Swift block: {signature}")
    opening_brace = text.index("{", start)
    depth = 0
    for index in range(opening_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unterminated Swift block: {signature}")


def allowed_ids(filter_ids: list[str], limit: int | None) -> list[str]:
    custom_ordinal = 0
    result: list[str] = []
    for filter_id in filter_ids:
        if filter_id == "all":
            result.append(filter_id)
        else:
            if limit is None or custom_ordinal < limit:
                result.append(filter_id)
            custom_ordinal += 1
    return result


def adjacent_allowed_id(
    filter_ids: list[str], selected_id: str, direction: str, limit: int | None
) -> str | None:
    selected_index = filter_ids.index(selected_id)
    if direction == "previous":
        candidate_indices = range(selected_index - 1, -1, -1)
    else:
        candidate_indices = range(selected_index + 1, len(filter_ids))
    allowed = set(allowed_ids(filter_ids, limit))
    for index in candidate_indices:
        if filter_ids[index] in allowed:
            return filter_ids[index]
    return None


class PendingFilterSwitchModel:
    def __init__(self, selected_id: str, available_ids: list[str]) -> None:
        self.selected_id = selected_id
        self.available_ids = available_ids
        self.pending_id: str | None = None
        self.pending_completions: list[Callable[[], None]] = []

    def switch_to(self, filter_id: str, completion=None) -> None:
        if filter_id == self.selected_id or filter_id not in self.available_ids:
            return
        if self.pending_id is not None and self.pending_id != filter_id:
            self.pending_id = None
            self.pending_completions.clear()
        if self.pending_id is None:
            self.pending_id = filter_id
            if completion is not None:
                self.pending_completions.append(completion)
        elif completion is not None:
            self.pending_completions.append(completion)

    def become_ready(self, filter_id: str) -> None:
        if self.pending_id != filter_id:
            return
        completions = self.pending_completions
        self.pending_completions = []
        self.pending_id = None
        self.selected_id = filter_id
        for completion in completions:
            completion()


class FolderLimitPolicyContractTests(unittest.TestCase):
    def test_limit_counts_only_custom_folders_without_normalizing_all(self) -> None:
        cases = [
            (["all", "a", "b", "c"], 2, ["all", "a", "b"]),
            (["a", "all", "b", "c"], 2, ["a", "all", "b"]),
            (["a", "b", "c", "all"], 2, ["a", "b", "all"]),
            (["a", "b", "c"], 2, ["a", "b"]),
            (["a", "all", "b"], None, ["a", "all", "b"]),
        ]
        for raw_ids, limit, expected in cases:
            with self.subTest(raw_ids=raw_ids, limit=limit):
                self.assertEqual(expected, allowed_ids(raw_ids, limit))

        policy = swift_block(
            source(POLICY_PATH), "public struct ChatListFilterTabAccessPolicy"
        )
        for token in [
            "public let filterIds: [ChatListFilterTabEntryId]",
            "public let limit: Int32?",
            "public func customFolderOrdinal(for id: ChatListFilterTabEntryId)",
            "case .all:",
            "continue",
            "case .filter:",
            "ordinal += 1",
            "public func isAllowed(_ id: ChatListFilterTabEntryId) -> Bool",
            "public var allowedFilterIds: [ChatListFilterTabEntryId]",
            "self.filterIds.filter { self.isAllowed($0) }",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, policy)

    def test_selection_and_swipe_share_directional_allowed_policy(self) -> None:
        self.assertEqual(
            "all",
            adjacent_allowed_id(
                ["a", "b", "c", "all"], "b", "next", limit=2
            ),
            "swipe must skip the blocked limit+1 custom folder to a trailing .all",
        )
        self.assertEqual(
            "b",
            adjacent_allowed_id(
                ["a", "b", "c", "all"], "all", "previous", limit=2
            ),
        )
        self.assertIsNone(
            adjacent_allowed_id(["a", "b", "c"], "b", "next", limit=2)
        )

        policy = swift_block(
            source(POLICY_PATH), "public struct ChatListFilterTabAccessPolicy"
        )
        for token in [
            "public func resolvedSelection(",
            "return self.allowedFilterIds.first",
            "public func adjacentAllowedFilter(",
            "direction: ChatListFilterTabNavigationDirection",
            "public func hasBlockedCustomFolder(",
            "case .previous",
            "case .next",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, policy)

        presentation = swift_block(source(POLICY_PATH), "public func chatListFilterTabPresentation(")
        self.assertIn("limit: Int32? = nil", presentation)
        self.assertIn("let accessPolicy = ChatListFilterTabAccessPolicy(", presentation)
        self.assertIn("accessPolicy.resolvedSelection(selectedFilter)", presentation)
        self.assertIn("accessPolicy: accessPolicy", presentation)

        pan = swift_block(source(CHAT_LIST_NODE_PATH), "@objc private func panGesture(")
        for token in [
            "self.filterAccessPolicy",
            "adjacentAllowedFilter(from: self.selectedId, direction: .previous)",
            "adjacentAllowedFilter(from: self.selectedId, direction: .next)",
            "hasBlockedCustomFolder(from: self.selectedId, direction: .previous)",
            "hasBlockedCustomFolder(from: self.selectedId, direction: .next)",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, pan)
        next_boundary = swift_block(pan, "if nextFilterId == nil")
        self.assertIn(
            "hasBlockedCustomFolder(from: self.selectedId, direction: .next)",
            next_boundary,
        )
        self.assertNotIn("$0 + 1", pan)
        self.assertNotIn("selectedIndex >= filtersLimit", pan)

    def test_main_and_peer_load_only_allowed_content_in_visible_order(self) -> None:
        for path in (CHAT_LIST_PATH, PEER_SELECTION_PATH):
            reload_filters = swift_block(source(path), "private func reloadFilters(")
            with self.subTest(path=path):
                self.assertIn("limit: filtersLimit", reload_filters)
                self.assertIn(
                    "let allowedFilterIds = Set(tabPresentation.accessPolicy.allowedFilterIds)",
                    reload_filters,
                )
                self.assertIn("visibleFilterIds.contains($0.id)", reload_filters)
                self.assertIn("allowedFilterIds.contains($0.id)", reload_filters)
                self.assertIn(
                    "updateAvailableFilters(availableFilters, accessPolicy: tabPresentation.accessPolicy)",
                    reload_filters,
                )
                self.assertNotIn("insert(.all, at: 0)", reload_filters)

    def test_tap_context_and_legacy_tabs_use_custom_folder_policy(self) -> None:
        node = source(CHAT_LIST_NODE_PATH)
        tabs_start = node.index("tabs = AnyComponent(HorizontalTabsComponent(")
        tabs_end = node.index("selectedTab: selectedTab", tabs_start)
        tabs = node[tabs_start:tabs_end]
        self.assertEqual(
            2, tabs.count("!tabPresentation.accessPolicy.isAllowed(entry.id)")
        )
        self.assertNotIn("firstIndex(where: { $0.id ==", tabs)

        legacy_update = swift_block(source(POLICY_PATH), "public func update(size containerSize:")
        self.assertIn("let accessPolicy = ChatListFilterTabAccessPolicy(", legacy_update)
        self.assertIn("!accessPolicy.isAllowed(filter.id)", legacy_update)
        self.assertNotIn("var folderIndex", legacy_update)

    def test_premium_policy_change_refreshes_horizontal_tab_closures(self) -> None:
        horizontal = source(HORIZONTAL_TABS_PATH)
        tab = swift_block(horizontal, "public final class Tab: Equatable")
        for token in [
            "public let actionRevision: Int",
            "actionRevision: Int = 0",
            "self.actionRevision = actionRevision",
            "if lhs.actionRevision != rhs.actionRevision",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, tab)

        node = source(CHAT_LIST_NODE_PATH)
        tabs_start = node.index("tabs = AnyComponent(HorizontalTabsComponent(")
        tabs_end = node.index("selectedTab: selectedTab", tabs_start)
        tabs = node[tabs_start:tabs_end]
        self.assertIn(
            "actionRevision: tabPresentation.accessPolicy.isAllowed(entry.id) ? 1 : 0",
            tabs,
        )

    def test_limit_refreshes_when_filters_are_unchanged(self) -> None:
        update_available = swift_block(
            source(CHAT_LIST_NODE_PATH), "public func updateAvailableFilters("
        )
        for token in [
            "accessPolicy: ChatListFilterTabAccessPolicy",
            "let filtersChanged = self.availableFilters != availableFilters",
            "let accessPolicyChanged = self.filterAccessPolicy != accessPolicy",
            "strongSelf.filterAccessPolicy = accessPolicy",
            "else if accessPolicyChanged",
            "self.filterAccessPolicy = accessPolicy",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, update_available)

    def test_pending_fallback_keeps_late_readiness_completion(self) -> None:
        node = source(CHAT_LIST_NODE_PATH)
        switch_to_filter = swift_block(node, "public func switchToFilter(")
        for token in [
            "private var pendingFilterCompletions: [() -> Void] = []",
            "self.pendingFilterCompletions.append(completion)",
            "self.pendingItemNode?.0 == id",
            "let pendingFilterCompletions = strongSelf.pendingFilterCompletions",
            "strongSelf.pendingFilterCompletions.removeAll()",
            "for completion in pendingFilterCompletions",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, node if token.startswith("private var") else switch_to_filter)

    def test_different_pending_id_is_superseded_by_policy_fallback(self) -> None:
        model = PendingFilterSwitchModel(
            selected_id="X", available_ids=["X", "Y", "Z"]
        )
        model.switch_to("Y")

        applied: list[list[str]] = []

        def apply_downgraded_filters() -> None:
            model.available_ids = ["Z"]
            applied.append(list(model.available_ids))

        model.switch_to("Z", completion=apply_downgraded_filters)
        model.become_ready("Y")
        self.assertEqual("X", model.selected_id)
        self.assertEqual([], applied)

        model.become_ready("Z")
        self.assertEqual("Z", model.selected_id)
        self.assertEqual([["Z"]], applied)

        switch_to_filter = swift_block(
            source(CHAT_LIST_NODE_PATH), "public func switchToFilter("
        )
        replacement = swift_block(
            switch_to_filter,
            "if let pendingItemNode = self.pendingItemNode, pendingItemNode.0 != id",
        )
        for token in [
            "pendingItemNode.2.dispose()",
            "self.pendingItemNode = nil",
            "self.pendingFilterCompletions.removeAll()",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, replacement)

        replace_index = switch_to_filter.index(
            "if let pendingItemNode = self.pendingItemNode, pendingItemNode.0 != id"
        )
        create_index = switch_to_filter.index("if self.pendingItemNode == nil")
        self.assertLess(replace_index, create_index)

    def test_swipe_indicator_targets_allowed_filter_in_both_tab_uis(self) -> None:
        legacy_update = swift_block(source(POLICY_PATH), "public func update(size containerSize:")
        for token in [
            "let previousAllowedFilterId = accessPolicy.adjacentAllowedFilter(",
            "let nextAllowedFilterId = accessPolicy.adjacentAllowedFilter(",
            "filter.id == nextAllowedFilterId",
            "filter.id == previousAllowedFilterId",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, legacy_update)
        self.assertNotIn(
            "resolvedSelectedFilter == visibleFilters[i - 1].id", legacy_update
        )
        self.assertNotIn(
            "resolvedSelectedFilter == visibleFilters[i + 1].id", legacy_update
        )

        horizontal = source(HORIZONTAL_TABS_PATH)
        update_fraction = swift_block(horizontal, "public func updateTabSwitchFraction(")
        self.assertIn("targetTab: HorizontalTabsComponent.Tab.Id? = nil", update_fraction)
        self.assertIn("self.tabSwitchTargetId = targetTab", update_fraction)
        component_update = swift_block(horizontal, "func update(component: HorizontalTabsComponent")
        self.assertIn("self.tabSwitchTargetId", component_update)
        self.assertIn("self.itemViews[targetTab]", component_update)

        main_transition = swift_block(
            source(CHAT_LIST_PATH),
            "self.chatListDisplayNode.mainContainerNode.currentItemFilterUpdated =",
        )
        for token in [
            "let tabPresentation = chatListFilterTabPresentation(",
            "tabPresentation.accessPolicy.adjacentAllowedFilter(",
            "targetTab: targetTab",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, main_transition)


if __name__ == "__main__":
    unittest.main()
