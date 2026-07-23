import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift"
HEADER = ROOT / "submodules/TelegramUI/Sources/Chat/ChatControllerOpenPeer.swift"


class AR02ProfileRouteContractTests(unittest.TestCase):
    def test_profile_row_replaces_header_quick_menu_entry(self) -> None:
        profile = PROFILE.read_text(encoding="utf-8")
        header = HEADER.read_text(encoding="utf-8")

        for token in (
            "private enum GRVMPeerInfoItemId: Hashable",
            "func insertGRVMArchiveRow(",
            "text: grvmStrings[.chatMenuTitle]",
            "grvmDeletedMessagesController(",
            "anchorIds: [ItemAbout, ItemDialogId]",
            "anchorIds: [0, ItemDialogId]",
        ):
            self.assertIn(token, profile)
        self.assertEqual(profile.count("insertGRVMArchiveRow("), 4)

        self.assertNotIn(
            "items.append(contentsOf: grvmArchiveContextMenuItems(",
            header,
        )


if __name__ == "__main__":
    unittest.main()
