from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class ItemListAdaptiveContractTests(unittest.TestCase):
    def test_switch_adaptive_layout_is_explicit_and_stock_default_stays_single_line(self) -> None:
        switch = source(
            "submodules/ItemListUI/Sources/Items/ItemListSwitchItem.swift"
        )

        self.assertIn("let adaptiveLayout: Bool", switch)
        self.assertIn("adaptiveLayout: Bool = false", switch)
        self.assertIn("self.adaptiveLayout = adaptiveLayout", switch)
        self.assertIn("maximumNumberOfLines: Int = 1", switch)
        self.assertIn(
            "let titleMaximumNumberOfLines = item.adaptiveLayout",
            switch,
        )
        self.assertIn(
            "maximumNumberOfLines: titleMaximumNumberOfLines",
            switch,
        )
        self.assertIn(
            "contentSize.height = max(contentSize.height, titleLayout.size.height + topInset * 2.0)",
            switch,
        )

    def test_disclosure_adaptive_layout_stacks_multiline_title_and_value(self) -> None:
        disclosure = source(
            "submodules/ItemListUI/Sources/Items/ItemListDisclosureItem.swift"
        )

        self.assertIn("let adaptiveLayout: Bool", disclosure)
        self.assertIn("adaptiveLayout: Bool = false", disclosure)
        self.assertIn("maximumTitleNumberOfLines: Int = 1", disclosure)
        self.assertIn("self.adaptiveLayout = adaptiveLayout", disclosure)
        self.assertIn(
            "let stackTitleAndLabel = item.adaptiveLayout",
            disclosure,
        )
        self.assertIn(
            "maximumNumberOfLines: titleMaximumNumberOfLines",
            disclosure,
        )
        self.assertIn(
            "let multilineLabel = stackTitleAndLabel",
            disclosure,
        )
        self.assertIn(
            "if stackTitleAndLabel {",
            disclosure,
        )

    def test_grvm_filters_opt_in_without_changing_global_itemlist_defaults(self) -> None:
        filters = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramFiltersController.swift"
        )
        editor = source(
            "submodules/AyuGramSettingsUI/Sources/AyuGramFilterEditorController.swift"
        )

        self.assertIn("adaptiveLayout: true", filters)
        self.assertIn("adaptiveLayout: true", editor)


if __name__ == "__main__":
    unittest.main()
