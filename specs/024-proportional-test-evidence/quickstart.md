# Quickstart: Validating Test Execution Only at the Review Gate

Runnable validation scenarios that prove the feature end-to-end. Run tests under the project env:

```bash
conda run -n specops pytest -q
```

## Prerequisites

- A Spec Kit client repo with `specops.json` defining a `test_command` (and optionally `lint_command`).
- An initialized SpecOps ledger with at least one user story and its tasks.

## Scenario 1 — Closing a user story runs no tests (US2)

**Setup**: `test_command` set to a command that writes a sentinel when invoked (e.g. `sh -c 'touch .ran-tests; pytest'`).

**Steps**:
1. `specops status start-task <final-task-of-story>`
2. Make the story's change, commit it.
3. `specops status complete-task <final-task-of-story> --auto`

**Expected**:
- `.ran-tests` sentinel is **absent** — no test command ran (Contract: `--auto` runs no tests).
- The task is `DONE` with a `CODE_DIFF:…` evidence string and an `auto` structured record (`command="(auto)"`).
- Removing `test_command` entirely and repeating still closes the task with diff evidence (no error).

**Reference**: contracts/cli-contracts.md → `complete-task --auto`; data-model.md → Development-phase completion evidence.

## Scenario 2 — Terminal gate reuses the soft gate's result (US1)

**Setup**: a feature at REVIEW with a clean tree and a passing `test_command`.

**Steps**:
1. `specops preflight --json --soft` (the `review-soft` step) → note the `test` gate `disposition`.
2. Without changing the tree, `specops preflight` (the `terminal-gate` step) → note the `test` gate `disposition`.

**Expected**:
- Step 1: `test` disposition is `required` (freshly executed); a `gate:test@<version>` evidence record now exists in the ledger.
- Step 2: `test` disposition is `cached`; the test command did **not** run again (verify via a sentinel as in Scenario 1, or by timing/log).
- The full test suite executed **exactly once** across both steps (SC-001/SC-003).

**Reference**: contracts/cli-contracts.md → `preflight`.

## Scenario 3 — A tree change invalidates reuse (Clarify Q1 / FR-003)

**Steps**:
1. `specops preflight --json --soft` on a clean tree (persists a passing `test` record).
2. Make an **uncommitted** edit to a source file (do not commit).
3. `specops preflight --json --soft` again.

**Expected**:
- Step 3: `test` disposition is `required` (re-executed), **not** `cached` — the `worktree_digest` in the cache key changed even though the commit range did not.

**Reference**: research.md R4; data-model.md → Working-tree digest.

## Scenario 4 — Only lint/test are cacheable (Clarify Q2 / FR-003a)

**Expected across Scenarios 2–3**:
- `reconcile`, `working-tree`, and `drift` never report `cached` — they recompute every run.
- Only `lint` and `test` ever appear with a `cached` disposition or a persisted `gate:<name>@…` record.

## Scenario 5 — Read-only boundary is preserved (FR-004 / SC-005)

**Steps**:
1. Snapshot the ledger.
2. Run `specops preflight --json` twice.

**Expected**:
- Task, phase, finding, and recovery state are byte-identical before/after; **only** the `evidence` list changed (one appended `gate:test@…` record, plus a `superseded_by` marker on any prior gate record).
- `specops gate report --json` before and after is byte-identical and mutates nothing.

**Reference**: research.md R7; contracts/cli-contracts.md → read-only boundary.

## Scenario 6 — Full-run count (SC-002)

Drive a full happy-path workflow run (specify → … → implement → corrective-loop [1 iter, APPROVED] → terminal-gate) on a U-story feature with a test sentinel.

**Expected**: the sentinel shows the full suite executed **exactly once** (at `review-soft`); `terminal-gate` reused it; no per-story `--auto` executed tests. Down from U+2.

**Reference**: integration/test_workflow_orchestration.py.
