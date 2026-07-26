import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = (
    ROOT / "submodules/AyuGramSettingsUI/Sources/GRVMMessageHistoryController.swift"
)
CONTEXT_MENU = ROOT / "submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift"
ENGLISH = ROOT / "Telegram/Telegram-iOS/en.lproj/GRVMgram.strings"
RUSSIAN = ROOT / "Telegram/Telegram-iOS/ru.lproj/GRVMgram.strings"

STRINGS_LINE = re.compile(
    r'^"(?P<key>[^"]+)"\s*=\s*"(?P<value>(?:\\.|[^"\\])*)";$'
)


def parse_strings(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        match = STRINGS_LINE.fullmatch(line)
        if match is None:
            raise AssertionError(f"{path}:{number}: invalid .strings entry")
        result[match.group("key")] = match.group("value")
    return result


class HistoryPresentationContractTests(unittest.TestCase):
    def test_archived_revision_numbers_are_one_based_without_mutating_storage_order(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")

        self.assertIn(
            "strings.format(.historyRevision, version.version + 1)",
            source,
        )
        self.assertNotIn(
            "strings.format(.historyRevision, version.version)",
            source,
        )
        self.assertIn("version: revision.version", source)
        self.assertIn("return lhs.version < rhs.version", source)
        self.assertIn("? strings[.historyCurrent]", source)

    def test_revision_capture_time_and_current_message_date_are_labeled_explicitly(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")

        self.assertIn("strings.format(.historyRevisionSavedAt, date)", source)
        self.assertIn("strings.format(.historyMessageDate, date)", source)
        self.assertIn("timestamp: revision.savedAt", source)
        self.assertIn("timestamp: currentMessage.timestamp", source)

        english = parse_strings(ENGLISH)
        russian = parse_strings(RUSSIAN)
        self.assertEqual(
            english["GRVMgram.History.RevisionSavedAt"],
            "Revision saved: %@",
        )
        self.assertEqual(
            russian["GRVMgram.History.RevisionSavedAt"],
            "Версия сохранена: %@",
        )
        self.assertEqual(
            english["GRVMgram.History.MessageDate"],
            "Original message date: %@",
        )
        self.assertEqual(
            russian["GRVMgram.History.MessageDate"],
            "Дата исходного сообщения: %@",
        )

    def test_history_action_copy_is_typed_and_exact_in_both_languages(self) -> None:
        context_menu = CONTEXT_MENU.read_text(encoding="utf-8")
        english = parse_strings(ENGLISH)
        russian = parse_strings(RUSSIAN)

        self.assertIn("text: grvmStrings[.menuHistory]", context_menu)
        self.assertNotIn('text: "History"', context_menu)
        self.assertEqual(english["GRVMgram.History.Action"], "History")
        self.assertEqual(russian["GRVMgram.History.Action"], "История")
        self.assertEqual(english["GRVMgram.Menu.History"], "History")
        self.assertEqual(russian["GRVMgram.Menu.History"], "История")


if __name__ == "__main__":
    unittest.main()
