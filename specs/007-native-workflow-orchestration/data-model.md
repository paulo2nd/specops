# Data Model: Native Workflow Orchestration

This feature introduces one asset (the workflow definition), one contract surface (the CLI outcome
object), and one **additive** ledger extension. It reuses Feature 006 ledger entities unchanged.

## New / extended entities

### 1. `specops` Workflow Definition (asset, not persisted state)

The shipped `.specify/workflows/specops/workflow.yml`. Composed entirely of Spec Kit native steps.

| Field | Type | Notes |
|---|---|---|
| `workflow.id` | string | `specops` (distinct from bundled `speckit`). |
| `workflow.version` | string | SemVer of the definition; bumped on step-graph changes. |
| `inputs` | map | e.g. `feature` description, `integration` (default `auto`). |
| `steps[]` | list | Ordered native steps: `command` (lifecycle), `shell` (SpecOps CLI gates/transitions), `gate` (human readiness + optional-skip), `do-while` (corrective loop), `if`/`switch` (outcome branching). |

Validation rules:
- Every `steps[].type` MUST be a Spec Kit native step type (SpecOps adds none) — FR-002.
- Exactly one human readiness `gate` between the plan step and the tasks step — FR-004.
- The corrective loop MUST be a `do-while` whose condition reads the review verdict — FR-015/016.
- A terminal `specops review`/verdict-check step MUST follow the loop and fail closed on
  verdict ≠ `APPROVED` — FR-019.

### 2. CLI Outcome Contract (transient, per-invocation)

Returned by `specops review|reconcile|consistency` (exit code always; JSON when `--json`).

| Field | Type | Values |
|---|---|---|
| `exit_code` | int | `0` ok · `1` blocking gate / review REJECTED · `2` infra/data/usage error |
| `command` | string | `review` \| `reconcile` \| `consistency` |
| `outcome` | string | `ok` \| `blocked` \| `error` |
| `class` | string | `pass` \| `gate-rejection` \| `infra-error` |
| `verdict` | string? | `APPROVED` \| `REJECTED` (review only) |
| `diverged_dimension` | string? | reconcile only: `feature` \| `branch` \| `baseline` \| `workflow-state` |
| `gates` | list? | review only: `[{name, status: PASS\|FAIL\|SKIPPED}]` |

Mapping to failure classes (FR-021/022): `pass`→advance · `gate-rejection`→corrective loop /
terminal halt · `infra-error`→fix environment (e.g. `rebaseline`, install missing command).
Execution failure (integration command crash) is **not** a SpecOps outcome — it is a Spec Kit engine
abort, remedied by `specify workflow resume` (FR-023/024).

### 3. Ledger `workflow` block (additive, persisted)

Added to `status.yaml` alongside the existing `workflow_lane`, `active_artifact`, `revision`,
`recovery`, `review_cycles`. Manipulated **only** by `specops status` CLI steps (Principle II).

| Field | Type | Notes |
|---|---|---|
| `workflow.run_id` | string | Correlates the Spec Kit workflow run to this ledger (FR-016). |
| `workflow.skipped_steps[]` | list | `{ step: "clarify\|checklist\|analyze", decision: "run\|skip", at: <tz-aware ts> }` (FR-006). |

Rules:
- New ledgers initialize `workflow` populated (empty `skipped_steps`, `run_id` set at first step).
- Migration back-fills an empty `workflow` block on Feature 006 v2 ledgers (deterministic, lossless),
  gated by the existing schema-version machinery; a forward-migration test covers it (per 006).
- Timestamps are timezone-aware and stably serialized (inherited from Feature 006 — FR-009 there).
- This is an **additive** extension, not the corrective-handoff finding schema forbidden by FR-027.

## Reused (unchanged) Feature 006 entities

- **Review Cycle** (`review_cycles[]`, strictly increasing round) — the corrective loop records each
  REJECTED round here via `status transition-phase REVIEW→IMPLEMENT -r REJECTED`. No schema change.
- **Workspace Identity** (feature / branch / baseline) + **compare-and-swap revision** — reconciliation
  and concurrency protection rely on these; `rebaseline` is the divergence remedy (FR-012/014).
- **`workflow_lane`** (default `full`) and **`active_artifact`** — already present; the `specops`
  workflow reads/advances them through the CLI.
- **Recovery metadata** — the interrupted-step guarantee (FR-011, Edge Cases) builds on 006's
  atomic-write + `last_consistent_revision`.

## State flow (phases, unchanged machine; driven by the definition)

```
SPECIFY → PLAN →[human readiness gate]→ TASKS → IMPLEMENT → REVIEW → DONE
                                                    ▲          │
                                                    └──────────┘  do-while: while verdict==REJECTED
                                                   (REVIEW→IMPLEMENT -r REJECTED, new review cycle)
                              after loop: terminal `specops review` gate — fail closed if ≠ APPROVED
```
The phase state machine (`PHASES` in `ledger.py`/`status.py`) is unchanged; this feature only drives
it deterministically from the workflow definition and records the corrective rounds already supported.
