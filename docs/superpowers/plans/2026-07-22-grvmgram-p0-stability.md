# GRVMgram P0 Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the confirmed ST03 profile-ID hard freeze without changing ID formatting, copy behavior, or stock profile interactions.

**Architecture:** Keep the existing typed GRVM ID formatter and one native `contextAction` route. Remove the duplicate `longTapAction` route that independently presents the same context controller, so a single gesture can create only one controller and the selected action dismisses the only presented menu.

**Tech Stack:** Swift, UIKit, AsyncDisplayKit/ContextUI, Python 3.12 `unittest` source-contract tests.

## Global Constraints

- Work on `codex/grvmgram-full-parity`; do not push or trigger GitHub Actions from this plan.
- Preserve the normal tap copy of the currently selected ID format.
- Preserve both context actions: Copy Telegram ID and Copy Bot API ID.
- Preserve user, group, and channel profile reachability.
- Use one context-menu recognizer path only; do not add delays, gesture flags, or dismissal workarounds.
- Run the focused RED/GREEN test before any broader gate.
- Do not commit device screenshots or personal data.

---

### Task 1: Make the ID-row context menu single-route

**Files:**
- Modify: `Tests/GRVMgramContracts/test_peer_identity_contract.py`
- Modify: `submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoProfileItems.swift`

**Interfaces:**
- Consumes: existing `grvmFormatPeerId(_:format:)`, `PeerInfoScreenLabeledValueItem`, and `contextAction` gesture route.
- Produces: one ID-row context-menu presentation path while retaining tap copy and both format actions.

- [ ] **Step 1: Write the failing source contract**

In `test_profile_id_rows_are_account_scoped_and_offer_both_formats`, replace the positive `"longTapAction:"` requirement with a scoped row assertion:

```python
        id_row = source_region(
            function,
            "return PeerInfoScreenLabeledValueItem(id: itemId",
            "\n    }\n    \n    if let user = data.peer as? TelegramUser",
        )
        self.assertNotIn("longTapAction:", id_row)
        self.assertEqual(id_row.count("contextAction:"), 1)
        self.assertEqual(id_row.count("openContextMenu(sourceNode"), 1)
```

Keep the existing assertions for both localized copy actions, account-scoped display mode, extracted/reference context sources, and all three peer types.

- [ ] **Step 2: Run the focused test and confirm RED**

Run from the repository root:

```powershell
python -m unittest Tests.GRVMgramContracts.test_peer_identity_contract.PeerIdentitySourceContractTests.test_profile_id_rows_are_account_scoped_and_offer_both_formats -v
```

Expected: one failure because the ID row still contains `longTapAction:` and calls `openContextMenu(sourceNode` twice.

- [ ] **Step 3: Remove only the duplicate recognizer route**

Change the ID item construction to:

```swift
        return PeerInfoScreenLabeledValueItem(id: itemId, label: "ID", text: idString, textColor: .primary, action: { _, _ in
            UIPasteboard.general.string = idString
        }, contextAction: { sourceNode, gesture, _ in
            openContextMenu(sourceNode, gesture)
        }, requestLayout: { animated in
            interaction.requestLayout(animated)
        })
```

Do not change `openContextMenu`, `copyAction`, menu labels, pasteboard values, or presentation source selection.

- [ ] **Step 4: Run focused GREEN and the full peer-identity contract**

```powershell
python -m unittest Tests.GRVMgramContracts.test_peer_identity_contract.PeerIdentitySourceContractTests.test_profile_id_rows_are_account_scoped_and_offer_both_formats -v
python -m unittest Tests.GRVMgramContracts.test_peer_identity_contract -v
git diff --check
```

Expected: all peer-identity tests pass and `git diff --check` exits 0.

- [ ] **Step 5: Independent task review**

Review the exact diff against the checklist ST03 observation. Reject any change that removes either copy format, normal tap copy, group/channel/user reachability, or modifies shared gesture infrastructure.

- [ ] **Step 6: Record the task**

After review is clean, append one line to `.superpowers/sdd/progress.md` with the base/head commits and focused test result. Commit the plan, contract, and Swift fix together as one focused P0 change.
