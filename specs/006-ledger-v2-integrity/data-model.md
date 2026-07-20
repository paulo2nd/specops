# Phase 1 Data Model: Ledger v2 Integrity

The ledger is a single YAML document at `specs/<feature>/status.yaml`, manipulated **only** by
`specops status …` commands. This document defines the **v2** shape, the delta from v1, and the
invariants and state machine enforced on every state change.

## v2 ledger document

```yaml
schema_version: 2                       # NEW — integer; absent ⇒ v1
revision: 1                             # NEW — monotonic int; +1 per committed state change
feature: "006-ledger-v2-integrity"      # unchanged — bound feature dir name (identity)
branch: "006-ledger-v2-integrity"       # unchanged — bound branch name (identity)
baseline: "a1b2c3d…"                    # unchanged — branch-point commit = HEAD at init (identity)
workflow_lane: "full"                   # NEW — "full" (only value this feature sets)
active_artifact: "spec.md"              # NEW — artifact tied to current_phase
created_at: "2026-07-19T14:30:22+00:00" # CHANGED — timezone-aware RFC3339 (was date-only)
updated_at: "2026-07-19T14:35:10+00:00" # CHANGED — timezone-aware; only bumps on logical change

current_phase: "SPECIFY"                # unchanged — phase state machine

recovery:                               # ENRICHED
  active_task: null                     # unchanged — id of the single IN_PROGRESS task, or null
  last_commit: null                     # unchanged — most recent harvested commit
  blockers: []                          # unchanged
  last_consistent_revision: 1           # NEW — revision of last committed state (FR-024)
  last_consistent_at: "2026-07-19T14:35:10+00:00"  # NEW — timestamp of that state
  migrated_from_backup: null            # NEW — path to pre-migration backup, or null (FR-008a)

tasks: []                               # unchanged shape (id, status, started_commit, commits,
                                        #   evidence, completed_at, orphaned?)
review_cycles: []                       # unchanged shape (round, started_at, completed_at, result)
```

### Field reference (new / changed only)

| Field | Type | Semantics | Requirement |
|-------|------|-----------|-------------|
| `schema_version` | int | Ledger schema version. Absent ⇒ treated as 1. Current = 2. | FR-001, FR-002 |
| `revision` | int ≥ 1 | Monotonic; advances by exactly 1 on each committed state change; CAS token for stale-write detection. | FR-012, FR-016 |
| `workflow_lane` | str | Execution lane; only `"full"` in this feature. Forward-compatible with Feature 013. | FR-027 |
| `active_artifact` | str | Artifact bound to `current_phase`, updated on every phase transition via `artifact_for_phase()` (SPECIFY→`spec.md`, PLAN→`plan.md`, TASKS/IMPLEMENT/REVIEW/DONE→`tasks.md`). | FR-027, FR-028 |
| `created_at` / `updated_at` | str (RFC3339, +00:00) | Timezone-aware UTC. `updated_at` only changes when logical content changes. | FR-009, FR-010, FR-011 |
| `recovery.last_consistent_revision` | int | Revision of the last committed state, for deterministic resume. | FR-024 |
| `recovery.last_consistent_at` | str (RFC3339) | Timestamp of the last committed state. | FR-024 |
| `recovery.migrated_from_backup` | str \| null | Repo-relative path of the retained pre-migration backup; null when never migrated. | FR-008a |

All other fields (`feature`, `branch`, `baseline`, `current_phase`, `tasks[*]`, `review_cycles[*]`)
retain their v1 meaning and shape. **Evidence is unchanged** (FR-030).

## Version classification (Schema Version entity)

| On-disk `schema_version` | Class | State-change behavior | Read-only behavior |
|---|---|---|---|
| absent or `1` | migratable-older | Auto-migrate to 2, back up original, then proceed | Read as-is, no migration (FR-007) |
| `2` | current | Proceed | Read as-is |
| `≥ 3` | too-new | **Refuse** — "requires a newer SpecOps" (FR-005) | Best-effort report + diagnostic (FR-029a) |
| `< 1` / non-int / unrecognized | unsupported | **Refuse** — "unsupported ledger shape" (FR-006) | Best-effort report + diagnostic (FR-029a) |

## Workspace Identity entity

Checked before every state change; first mismatch fails closed and names the dimension (FR-018/019).

| Dimension | Source of truth | Ledger field | Divergence condition |
|---|---|---|---|
| feature | `speckit.resolve_feature_dir(root).name` (None ⇒ fail closed) | `feature` | name mismatch or unresolvable |
| branch | `gitops.current_branch(repo)` | `branch` | name mismatch |
| baseline | `gitops.is_ancestor(repo, baseline)` | `baseline` | baseline not an ancestor of HEAD |

## Migration (v1 → v2)

Deterministic, ordered, pure transformation (`_v1_to_v2`), applied in memory before a single atomic
write; the original bytes are backed up first (FR-008a).

1. Set `schema_version = 2`.
2. Set `revision = 1`.
3. Convert `created_at`/`updated_at` and any timestamp fields from date-only/naive to zone-aware UTC
   (interpret naive as UTC; FR-010).
4. Set `workflow_lane = "full"`.
5. Derive `active_artifact` from `current_phase` via `artifact_for_phase()`.
6. Add `recovery.last_consistent_revision = 1`, `recovery.last_consistent_at = updated_at`,
   `recovery.migrated_from_backup = <backup path>`.
7. Preserve `tasks`, `review_cycles`, `feature`, `branch`, `baseline`, `current_phase`, and all
   evidence **byte-for-byte in meaning** (FR-004, FR-030).

Idempotency: migrating a ledger already at `schema_version: 2` is a no-op that does not rewrite the
file or reorder records (FR-008).

## Invariants (validated before every state change — FR-025/FR-026)

- **I-PHASE-1**: `current_phase ∈ {SPECIFY, PLAN, TASKS, IMPLEMENT, REVIEW, DONE}`.
- **I-PHASE-2**: Phase only advances by the allowed transitions (forward by one; `REVIEW→IMPLEMENT`
  only with `result = REJECTED`; `*→DONE` only with the latest review cycle `APPROVED`).
- **I-TASK-1**: Every task `status ∈ {PENDING, IN_PROGRESS, DONE}`.
- **I-TASK-2**: At most one non-orphaned task is `IN_PROGRESS`.
- **I-TASK-3**: A `DONE` task has non-empty `evidence`.
- **I-REC-1**: `recovery.active_task` is null or equals the single `IN_PROGRESS` task id.
- **I-REV-1**: `review_cycles[*].round` is strictly increasing from 1.
- **I-REV-2**: At most one review cycle is open (`result: null`).
- **I-REV-3**: A ledger becomes eligible for `DONE` only when the latest cycle `result = APPROVED`.

A violation blocks the operation (fail closed) with a specific message; it never results in a write.

## Concurrency model (Ledger Revision entity)

- `revision` is the compare-and-swap token. A state change captures `base_revision` at load; the
  write commits only if the on-disk `revision == base_revision`, then sets `base_revision + 1`.
- On mismatch, the write is rejected with a stale-state signal (FR-013/FR-015); no data is written.
- Concurrent writers: a short-lived `status.yaml.lock` serializes the critical section; the revision
  CAS is the durable guarantee, so at most one writer succeeds regardless of lock outcome (FR-014).
- Ordering/staleness relies on `revision`, never on `updated_at` (FR-016).

## Recovery Metadata entity

`recovery.last_consistent_revision` + `recovery.last_consistent_at` identify the last committed
state; `recovery.migrated_from_backup` points at the retained pre-migration ledger. Together they let
a fresh session determine, from repository state alone, what the last consistent state was and (if a
migration proved defective) roll back to it deterministically (FR-024, FR-008a).

## Phase state machine (unchanged transitions, now invariant-checked)

```text
SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE
                                       │
                                       └──(result=REJECTED)──▶ IMPLEMENT  (opens next review round)
```
