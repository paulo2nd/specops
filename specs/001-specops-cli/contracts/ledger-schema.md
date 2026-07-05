# Ledger Schema Contract: `status.yaml`

**Plan**: [../plan.md](../plan.md) | **Data model**: [../data-model.md](../data-model.md)

Location: `<feature_directory>/status.yaml` (R4). Written exclusively by
`specops status`; hand-editing is a methodology violation detectable by `reconcile`.

```yaml
feature: "001-specops-cli"          # string, feature directory name
branch: "main"                       # string, branch at creation
baseline: "c5533dc..."               # string, full commit hash at creation
created_at: "2026-07-05"             # ISO date
updated_at: "2026-07-05"             # ISO date, touched by every write

current_phase: "IMPLEMENT"           # SPECIFY|PLAN|TASKS|IMPLEMENT|REVIEW|DONE

recovery:
  active_task: "T003"                # string|null — the single IN_PROGRESS task
  last_commit: "a1b2c3d..."          # string|null — latest harvested commit
  blockers: []                       # string[] — stop-and-ask notes

tasks:                               # mirrored from tasks.md (R5), order preserved
  - id: "T001"                       # Speckit id verbatim, unique
    status: "DONE"                   # PENDING|IN_PROGRESS|DONE
    started_commit: "c5533dc..."     # string|null — HEAD at start-task
    commits:                         # string[] — started_commit..HEAD at completion
      - "a1b2c3d..."
    evidence: "TEST_REPORT:pytest 42 passed; CODE_DIFF:3 files across 1 commit: cli.py, status.py, test_status.py"
    completed_at: "2026-07-05"       # date|null
  - id: "T002"
    status: "PENDING"
    started_commit: null
    commits: []
    evidence: null
    completed_at: null
    # orphaned: true                 # present only when id vanished from tasks.md

review_cycles:                       # one entry per REVIEW entry / corrective round
  - round: 1
    started_at: "2026-07-05"
    completed_at: null
    result: null                     # APPROVED|REJECTED|null while open
```

## Invariants (enforced by the CLI; checked by `reconcile`)

| # | Rule | Enforced by |
|---|---|---|
| L1 | No task DONE without non-empty `commits[]` AND `evidence` | `complete-task` refuses; `reconcile` exit 1 |
| L2 | At most one task IN_PROGRESS; it equals `recovery.active_task` | `start-task` refuses |
| L3 | Every hash in `commits[]` is an ancestor of HEAD (except literal `(human)`) | `reconcile` exit 1 |
| L4 | `current_phase` only changes via `transition-phase` following the state machine | `transition-phase` refuses |
| L5 | `DONE` phase requires latest `review_cycles[].result == APPROVED` | `transition-phase` refuses |
| L6 | Task ids exist in `tasks.md` or are flagged `orphaned` | sync (R5); `reconcile` reports |
| L7 | Evidence matches `<CLASS>:<summary>` with class ∈ CLI_LOG, TEST_REPORT, SCREENSHOT_PATH, CODE_DIFF; multiple entries `; `-separated | `complete-task` validates |

Corrupt YAML or schema violation on load → exit 2 (unexpected error, R9) with file
path; commands never attempt auto-repair.
