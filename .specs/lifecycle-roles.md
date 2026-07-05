# SpecOps × Speckit — Lifecycle, Roles, and Execution Map

This document makes explicit **what runs at each stage of the combined
Speckit + SpecOps lifecycle, and under which role**. It is design input for the
technical plan of spec `001-specops-cli` and adapts the canonical flow of
[reference/methodology.md §2](reference/methodology.md) (architect → implementer →
reviewer) to the Speckit lifecycle.

## Command Surfaces

SpecOps exposes two distinct surfaces:

| Surface | Invoked by | Examples |
|---|---|---|
| **Terminal CLI** (`specops …`) | Humans, CI, and agents following injected directives | `specops init`, `specops status …`, `specops reconcile`, `specops consistency` |
| **Agent commands** (`/specops.…`) | Humans inside the coding agent | `/specops.review` (the only agent command in v1) |

The injected directive blocks (installed by `specops init` into Speckit's implement
and plan prompts) are what make agents call the terminal CLI at the right moments.

## Ledger Phases

The ledger's fixed phase set maps onto the Speckit lifecycle:
`SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE` (ordered transitions enforced by
`specops status transition-phase`). Single exception: `REVIEW → IMPLEMENT` with
result `REJECTED` opens a corrective round; each corrective round registers a new
review cycle in the ledger.

## Stage-by-Stage Execution Map

### Stage 0 — Repository Preparation (one-time)

- **Role**: human operator.
- **Runs**: `speckit init` (Speckit's own setup), then `specops init` from the
  terminal.
- **SpecOps behavior**: validates Git (offers `git init` when absent), detects the
  Speckit structure (aborts with guidance when absent), generates `specops.json`,
  installs `/specops.review`, injects marker-delimited directive blocks into
  Speckit's **implement** and **plan** prompts. Idempotent on re-run.

### Stage 1 — SPECIFY (`/speckit.specify`, `/speckit.clarify`)

- **Role**: architect (planning role).
- **Speckit runs**: specification creation and clarification.
- **SpecOps runs**: `specops status init-spec <name>` (terminal) — creates the ledger
  inside the active Speckit feature directory; phase starts at `SPECIFY`.
- **Gates**: none yet (task list may not exist; ledger tasks sync later).

### Stage 2 — PLAN (`/speckit.plan`, with injected SpecOps directive block)

- **Role**: architect.
- **Speckit runs**: technical plan generation.
- **Injected directives (agent-side)**: Empirical Verification (§17.4) — every
  declared path carries an action suffix (`(create)`, `(modify)`, `(remove)`) proven
  against the worktree; each task declares the success-criterion IDs (`SC-001`, …) it
  covers, enabling deterministic coverage validation; no memory-based declarations;
  stop-and-ask on ambiguity.
- **SpecOps runs**: `specops status transition-phase PLAN` at stage entry;
  `specops consistency` (terminal) as the **closing gate** — exit code 1 blocks the
  handoff until spec/plan are corrected.
- **Human gate**: Readiness Gate — explicit human approval of the planning artifacts
  before implementation starts (§2).

### Stage 3 — TASKS (`/speckit.tasks`)

- **Role**: architect.
- **Speckit runs**: task list generation (`tasks.md`).
- **SpecOps runs**: `specops status transition-phase TASKS`; from here on, every
  ledger command idempotently syncs the ledger task list from `tasks.md`
  (new tasks enter as `PENDING`; unknown task ids are rejected).

### Stage 4 — IMPLEMENT (`/speckit.implement`, with injected SpecOps directive block)

- **Role**: implementer (execution role).
- **SpecOps runs at entry**: `specops status transition-phase IMPLEMENT`;
  `specops reconcile` as preflight (divergence blocks any write).
- **Per-task loop (driven by injected directives)**:
  1. `specops status start-task <task_id>` — marks `IN_PROGRESS`, sets recovery
     point.
  2. Implement the task; one commit per task; write scope limited to the task's
     declared paths.
  3. `specops status complete-task <task_id> --auto` — runs the client's
     `test_command`, harvests commit hashes and diff, records the
     `<CLASS>:<summary>` evidence entry; failing tests keep the task
     `IN_PROGRESS`.
  4. Emit exactly one chat line — `<task-id> done (<commit-sha7>), starting
     <next-task-id>` (Speckit identifiers, e.g., `T001 done (a1b2c3d), starting
     T002`) — and continue immediately (Operational Silence §6).
- **Stop-and-Ask gates (§8.2)**: persisted schema changes, secrets, public contract
  breaks, dependency changes, root-cause ambiguity — halt and ask the human.
- **Exit**: when no `PENDING` tasks remain, `specops status transition-phase REVIEW`.

### Stage 5 — REVIEW (`/specops.review` — SpecOps agent command)

- **Role**: reviewer.
- **Runs (in the prompt's mandatory order — see
  [reference/review-prompt.md](reference/review-prompt.md))**:
  1. Load required skills from `specops.json > skills_dir`.
  2. `specops reconcile` (terminal) — abort immediately on failure.
  3. Client lint + test commands must pass (zero-token pre-filter).
  4. `git status --porcelain` scope check — out-of-plan files ⇒ `REJECTED` without
     reading code.
  5. Surgical diff review against acceptance criteria; evidence check per task.
  6. Emit `revisions/revision-X.md` (short non-conformity format).
- **Outcomes**:
  - `REJECTED` → corrective package; ledger returns to `IMPLEMENT`
    (`transition-phase` with result `REJECTED`); implementer executes the corrective
    round; back to REVIEW.
  - `APPROVED` → versioned decision; human confirms PR opening;
    `specops status transition-phase DONE -r APPROVED`.

### Stage 6 — DONE

- **Role**: reviewer (closure) / human (merge).
- **Runs**: PR opened only after versioned `APPROVED`; final merge is always human.

## Role Summary

| Role | Speckit stages | SpecOps terminal commands | Agent commands / injected directives |
|---|---|---|---|
| **Architect** | specify, clarify, plan, tasks | `status init-spec`, `status transition-phase`, `consistency` | Plan prompt directive block (Empirical Verification, consistency gate) |
| **Implementer** | implement | `status start-task`, `status complete-task --auto`, `status transition-phase`, `reconcile` (preflight) | Implement prompt directive block (Operational Silence, ledger loop, Stop-and-Ask) |
| **Reviewer** | review, done | `reconcile`, `status transition-phase` | `/specops.review` |
| **Human** | all (gates) | `specops init`, any command | Readiness Gate approval, Stop-and-Ask decisions, PR confirmation, merge |

## Out of Scope in v1

- The lightweight fix lane ([workflow/roles/fixer.json](reference/workflow/roles/fixer.json))
  is vendored as reference but not part of the Speckit-integrated v1 flow.
- `/specops.review` is the only agent command; all other operations are terminal
  commands triggered by injected directives.
