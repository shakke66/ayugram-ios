import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "grvmgram"))

from validate_read_state import validate_suppressed_push


GOOD = """
if AyuGramHooks.shouldSuppressReadReceipts?(self.stateManager.accountPeerId) == true {
    signal = self.postbox.transaction { transaction -> Void in
        transaction.confirmSynchronizedIncomingReadState(peerId)
    }
    |> castError(PeerReadStateValidationError.self)
    |> ignoreValues
} else {
    signal = synchronizePeerReadState()
}
"""

BAD = """
if AyuGramHooks.shouldSuppressReadReceipts?(self.stateManager.accountPeerId) == true {
    signal = .complete()
} else {
    signal = synchronizePeerReadState()
}
"""

ZERO_ARGUMENT = GOOD.replace("self.stateManager.accountPeerId", "")


class ReadStateContractTests(unittest.TestCase):
    def test_rejects_bare_complete(self) -> None:
        self.assertTrue(
            any("bare .complete()" in error for error in validate_suppressed_push(BAD))
        )

    def test_accepts_confirming_transaction(self) -> None:
        self.assertEqual([], validate_suppressed_push(GOOD))

    def test_rejects_zero_argument_hook(self) -> None:
        self.assertTrue(validate_suppressed_push(ZERO_ARGUMENT))

    def test_production_source_matches_contract(self) -> None:
        source = (
            ROOT
            / "submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift"
        ).read_text(encoding="utf-8")
        self.assertEqual([], validate_suppressed_push(source))


if __name__ == "__main__":
    unittest.main()
