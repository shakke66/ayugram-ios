# GRVMgram Crash Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commit the proven Ghost read-state recursion fix with a mutation-tested local contract that prevents a bare synchronous completion from returning.

**Architecture:** Keep Telegram's existing read-state operation flow and consume a suppressed Push through the same Postbox confirmation transaction used by the stock no-push path. Add a Python source contract because Swift/Bazel cannot run on the Windows host; the contract validates both a deliberately bad fixture and the production branch.

**Tech Stack:** Swift, TelegramCore/Postbox, Python 3.12 unittest, Git.

## Global Constraints

- Preserve the user-authored Opus change in `ManagedSynchronizePeerReadStates.swift`.
- Do not send a read receipt while Ghost read suppression is active.
- Do not use a bare `.complete()` for a pending Push operation.
- Do not launch GitHub Actions during this phase.
- Keep this fix in its own implementation commit.

---

### Task 1: Add the Ghost read-state source contract

**Files:**
- Create: `tools/grvmgram/validate_read_state.py`
- Create: `Tests/GRVMgramContracts/test_read_state_contract.py`

**Interfaces:**
- Consumes: UTF-8 Swift source text.
- Produces: `validate_suppressed_push(source: str) -> list[str]` and a zero/nonzero CLI exit code.

- [ ] **Step 1: Write the failing contract tests**

```python
# Tests/GRVMgramContracts/test_read_state_contract.py
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "grvmgram"))

from validate_read_state import validate_suppressed_push


GOOD = """
if AyuGramHooks.shouldSuppressReadReceipts?() == true {
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
if AyuGramHooks.shouldSuppressReadReceipts?() == true {
    signal = .complete()
} else {
    signal = synchronizePeerReadState()
}
"""


class ReadStateContractTests(unittest.TestCase):
    def test_rejects_bare_complete(self) -> None:
        self.assertTrue(
            any("bare .complete()" in error for error in validate_suppressed_push(BAD))
        )

    def test_accepts_confirming_transaction(self) -> None:
        self.assertEqual([], validate_suppressed_push(GOOD))

    def test_production_source_matches_contract(self) -> None:
        source = (
            ROOT
            / "submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift"
        ).read_text(encoding="utf-8")
        self.assertEqual([], validate_suppressed_push(source))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify the missing validator fails**

Run:

```powershell
python -m unittest Tests.GRVMgramContracts.test_read_state_contract -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'validate_read_state'`.

- [ ] **Step 3: Implement the minimal validator**

```python
# tools/grvmgram/validate_read_state.py
from __future__ import annotations

import argparse
from pathlib import Path


def _suppressed_branch(source: str) -> str:
    marker = "if AyuGramHooks.shouldSuppressReadReceipts?() == true {"
    start = source.find(marker)
    if start < 0:
        return ""
    end = source.find("} else {", start)
    return source[start:end] if end >= 0 else source[start:]


def validate_suppressed_push(source: str) -> list[str]:
    branch = _suppressed_branch(source)
    errors: list[str] = []
    if not branch:
        return ["suppressed read-receipt branch is missing"]
    if "signal = .complete()" in branch:
        errors.append("bare .complete() leaves the Push operation pending")
    if "confirmSynchronizedIncomingReadState(peerId)" not in branch:
        errors.append("suppressed Push is not confirmed locally")
    if "postbox.transaction" not in branch:
        errors.append("suppressed Push completion is not transaction-backed")
    if "synchronizePeerReadState(" in branch:
        errors.append("suppressed Push still calls the network synchronizer")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate_suppressed_push(args.path.read_text(encoding="utf-8"))
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and production contract**

Run:

```powershell
python -m unittest Tests.GRVMgramContracts.test_read_state_contract -v
python tools/grvmgram/validate_read_state.py submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift
```

Expected: three tests PASS; validator exits 0 with no output.

- [ ] **Step 5: Prove the contract rejects the pre-fix source**

Run:

```powershell
$old = Join-Path $env:TEMP "ManagedSynchronizePeerReadStates.pre-fix.swift"
git show b3c83ff5:submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift | Set-Content -Encoding UTF8 $old
python tools/grvmgram/validate_read_state.py $old
if ($LASTEXITCODE -eq 0) { throw "Mutation check unexpectedly passed" }
```

Expected: exit 1 and messages mentioning `bare .complete()` and missing local confirmation.

### Task 2: Verify and commit the focused Ghost fix

**Files:**
- Modify: `submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift:91`
- Test: `Tests/GRVMgramContracts/test_read_state_contract.py`

**Interfaces:**
- Consumes: `Transaction.confirmSynchronizedIncomingReadState(_ peerId: PeerId)`.
- Produces: a `Signal<Never, PeerReadStateValidationError>` that completes after consuming the local Push operation.

- [ ] **Step 1: Verify the implementation is the approved transaction pattern**

```swift
if AyuGramHooks.shouldSuppressReadReceipts?() == true {
    signal = self.postbox.transaction { transaction -> Void in
        transaction.confirmSynchronizedIncomingReadState(peerId)
    }
    |> castError(PeerReadStateValidationError.self)
    |> ignoreValues
} else {
    signal = synchronizePeerReadState(
        network: self.network,
        postbox: self.postbox,
        stateManager: stateManager,
        peerId: peerId,
        push: true,
        validate: thenSync
    )
    |> ignoreValues
}
```

- [ ] **Step 2: Compare with Telegram's stock no-push pattern**

Run:

```powershell
rg -n -C 5 "confirmSynchronizedIncomingReadState" submodules/TelegramCore/Sources/State/SynchronizePeerReadState.swift submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift
```

Expected: both branches confirm the incoming read state through a Postbox transaction.

- [ ] **Step 3: Run focused verification**

Run:

```powershell
python -m unittest Tests.GRVMgramContracts.test_read_state_contract -v
python tools/grvmgram/validate_read_state.py submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift
git diff --check
```

Expected: tests PASS, validator exit 0, and no whitespace errors.

- [ ] **Step 4: Stage only the crash fix and its contract**

Run:

```powershell
git add -- tools/grvmgram/validate_read_state.py Tests/GRVMgramContracts/test_read_state_contract.py submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift
git diff --cached --name-only
```

Expected exactly:

```text
Tests/GRVMgramContracts/test_read_state_contract.py
submodules/TelegramCore/Sources/State/ManagedSynchronizePeerReadStates.swift
tools/grvmgram/validate_read_state.py
```

- [ ] **Step 5: Commit**

```powershell
git commit -m "fix: consume suppressed read-state operations"
```

Expected: one focused commit; `git status --short` no longer lists the Opus file.

### Task 3: Audit the other Ghost operation suppressors

**Files:**
- Inspect: `submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift`
- Inspect: `submodules/TelegramCore/Sources/State/ManagedSynchronizeViewStoriesOperations.swift`
- Modify only if the contract fails: `tools/grvmgram/validate_read_state.py`

**Interfaces:**
- Consumes: operation-log removal patterns in TelegramCore.
- Produces: evidence that no second pending-operation recursion exists.

- [ ] **Step 1: Locate every synchronous completion in Ghost-related operation managers**

Run:

```powershell
rg -n -C 8 "\.complete\(\)|shouldSuppress(ContentRead|StoryRead|ReadReceipts)" submodules/TelegramCore/Sources/State -g "*.swift"
```

Expected: read-state uses the confirming transaction; consume-content and view-story suppression are wrapped by operation-taking/removal logic.

- [ ] **Step 2: Verify operation removal**

Run:

```powershell
rg -n -C 12 "withTakenOperation|operationLogRemoveEntry" submodules/TelegramCore/Sources/State/ManagedSynchronizeConsumeMessageContentsOperations.swift submodules/TelegramCore/Sources/State/ManagedSynchronizeViewStoriesOperations.swift
```

Expected: each suppressed operation is removed before or as its signal completes.

- [ ] **Step 3: Record the audit in the implementation commit body**

Run:

```powershell
git show -1 --format=fuller --stat
```

Expected: the focused commit from Task 2 is present; no additional source edit is needed when both managers remove their operation entries.
