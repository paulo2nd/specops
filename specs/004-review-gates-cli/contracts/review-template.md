# Template Contract — installed `/specops-review` prompt

**Feature**: `specs/004-review-gates-cli` | **Date**: 2026-07-06

Source asset: `src/specops/templates/review.md` (installed verbatim by
`initializer._install_review`, with skills-mode frontmatter wrapping when the
destination is a `SKILL.md` — no initializer change in this feature).

## Structure after the change

| Section | Status |
|---|---|
| `## /specops-review` heading + intro | unchanged |
| Step 1 — Load Skills | unchanged |
| Step 2 — Deterministic Gates | **replaces** former Steps 2 (Reconcile), 3 (Lint/Test), 4 (Working Tree) |
| Step 3 — Surgical Diff Review | former Step 5, renumbered only |
| Step 4 — Write Revision Report | former Step 6, renumbered only |
| Active Learning | unchanged |

## Step 2 required content

The collapsed step MUST instruct the agent to:

1. Run `specops review`.
2. On non-zero exit: report the command's output, set the decision to
   **REJECTED**, and stop — read no code.
3. On exit 0: proceed to the surgical diff review, carrying any `SKIPPED`
   gates forward to the revision report (`Skipped gate: <name> (<reason>)`)
   so a gate that never ran is visible in the verdict.

It MUST NOT instruct the agent to run `specops reconcile`, the lint/test
commands, or `git status` individually — those belong to the CLI now.

## Invariants

- Verdict transition commands (`specops status transition-phase ...`) remain
  in the revision-report step, agent-driven (interactive review semantics
  unchanged in this feature).
- Revision file format (`revisions/revision-X.md`, `[File]:[Line] - ...`,
  `APPROVED` single line) unchanged.
- Delivery: first `specops init` run and re-runs install the updated content
  through the existing mechanism; uninstall/restore guarantees untouched
  (FR-011). Existing installed-asset tests
  (`tests/integration/test_review_asset.py`) must be updated to assert the
  collapsed step.
