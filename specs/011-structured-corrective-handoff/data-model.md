# Phase 1 — Data Model: Structured Corrective Handoff

Backing store: the per-feature Ledger (Feature 006, **v4 → v5**) at `specs/<feature>/status.yaml`.
All records are additive; pre-feature ledgers read unchanged (FR-019, CHK031/CHK032). Persisted
timestamps are timezone-aware (`ledger.now_utc`); read commands never echo them (R11).

---

## Entity: Corrective Handoff

Nested on a review-cycle record: `review_cycles[i].handoff`. Present only once the round records
≥1 finding (R4).

| Field | Type | Notes |
|---|---|---|
| `authorized_paths` | list[str] | Repo-relative, normalized (`trace._norm`). Shared corrective-path authorization for the round (FR-002/FR-009). Default `[]`. |
| `closed_at` | str \| null | Aware timestamp stamped by `handoff close` (FR-023); `null` while open. Audit only — the approval gate keys on closability, not this field (R7). |
| `findings` | list[Finding] | The round's structured findings (below). |

Bound to its round by nesting under `review_cycles[i]` (Feature 006 owns `round`, `result`,
`started_at`, `completed_at`, `context_provenance`). Extends, never invalidates, the cycle record.

## Entity: Finding

| Field | Type | Presence | Notes |
|---|---|---|---|
| `id` | str | required | `R<round>-F<NN>` (R2). Unique within the feature, stable across sessions/renders. |
| `severity` | `blocking` \| `advisory` | required | Closed set; unrecognized ⇒ exit 2 (FR-003). Only `blocking` gates approval. |
| `rule` | str | required | The rule/principle violated (free-form text; no controlled vocabulary in v1). |
| `file` | str | required | Repo-relative, normalized. |
| `line` | int \| null | optional | Omitted ⇒ file-level finding. |
| `action` | str | required | Concise corrective action. |
| `expected_evidence` | str | required for `blocking` | Declared descriptor of what will close it (R3); distinct from `evidence`. |
| `closure_criteria` | str | required for `blocking` | Condition for `VERIFIED`. Advisory: optional. |
| `state` | `OPEN` \| `FIXED` \| `VERIFIED` | required | Lifecycle (below). Default `OPEN` at creation. |
| `task` | str \| null | set at `FIXED` | Must resolve to a ledger task. |
| `commits` | list[str] | set at `FIXED` | ≥1 required to enter `FIXED`. |
| `evidence` | str \| null | set at `FIXED` | Actual `<CLASS>:<summary>` (Principle III); checked by `VERIFIED` precondition. |
| `fixed_at` / `verified_at` | str \| null | set on transition | Aware timestamps; ledger state, not echoed by reads. |

## State transitions: Finding lifecycle

```
OPEN ──add-fix──▶ FIXED ──verify──▶ VERIFIED
                   │
   (illegal: OPEN→VERIFIED skip, any backward move, precondition unmet ⇒ exit 2, no change)
```

| Transition | Precondition (fail ⇒ exit 2, state unchanged) | Command |
|---|---|---|
| `OPEN → FIXED` | known `task`, ≥1 `commit`, actual `evidence` present | `handoff finding fix` |
| `FIXED → VERIFIED` | actual evidence present **and** links resolve (mechanical); recorded in a review pass; **no auto-verify** | `handoff finding verify` |
| any other | rejected | — |

Monotonic and fail-closed (FR-004/FR-005/FR-006). Carry-forward across rounds (FR-024): a round's
findings persist in that round's handoff; `VERIFIED` stays `VERIFIED`; a recurrence at a seen
`file:line` in a later round is a **new** finding with a new id.

## Entity: Path Class hook (reused, not redefined)

`authorized_paths` is recorded here; **classification stays owned by Feature 010** — a corrective
change outside `authorized_paths` surfaces as `unexplained` via `trace` drift, not a new gate
(FR-009). No new path-class entity is introduced.

## Entity: Handoff Defect (validation output)

| Defect | Trigger | Exit |
|---|---|---|
| `dangling-reference` | finding references a cycle/task/commit/evidence that cannot be resolved (commit-existence deferred to `reconcile`, FR-011) | 1 |
| `missing-closure` | `blocking` finding lacks `closure_criteria` (or `expected_evidence`) | 1 |
| `contradictory-state` | `VERIFIED` with no `evidence`, or `FIXED` with no `commit`/`task` | 1 |
| `duplicate-id` | two findings share an `id` | 1 |

Each reported as a distinct diagnostic (FR-010). Validation is read-only and never mutates state.

## Derived: blocking-approval predicate

`blocking_approval_check(data)` = ids of every `blocking` finding across all cycles' handoffs whose
`state != VERIFIED` (feature-global, R6). Empty ⇒ approval permitted (and every round's handoff is
*closable*). Non-empty ⇒ `APPROVED`/`DONE` fail closed (exit 1) naming the ids (FR-007). No
handoffs present ⇒ empty ⇒ degrade to Feature 006's gate (FR-008).

## Ledger schema: v4 → v5 migration

| Aspect | Rule |
|---|---|
| `CURRENT_SCHEMA` | 4 → **5** (`ledger.py`). |
| Migration | `migrate_to_current` is additive: pre-v5 cycles simply lack `handoff`; **no backfill needed** (absence = zero findings). Idempotent; preserves every task/cycle/evidence/acknowledgement record verbatim. |
| Read-compat | A v1–v4 ledger reads without error; absent finding/handoff state is the supported prior shape (never a defect) — FR-019, CHK031. |
| Invariants | `validate_invariants` gains finding-shape checks (valid `severity`, valid `state`, `id` unique per feature, monotonic-state consistency) exempting orphaned/absent handoffs; blocks a state-changing write on violation (fail closed), mirroring the acknowledgement-shape check. |
| Forward-migration test | Upgrade a v4 fixture (with `acknowledgements`, provenance, review_cycles) to v5 with zero data loss (SC-007). |

## Output contract: status → class → exit (single source of truth)

Mirrors `outcome.render`; `_STATUS_CLASS` table in `handoff.py` (R12). Every JSON output carries
`output_version = 1` and a stable `status` field.

| Class (exit) | Statuses |
|---|---|
| **PASS (0)** | `finding-recorded`, `handoff-authorized`, `finding-fixed`, `finding-verified`, `handoff-closed`, `handoff-already-closed`, `validate-ok`, `report-ok` |
| **GATE_REJECTION (1)** | `approval-blocked`, `close-blocked`, `dangling-reference`, `missing-closure`, `contradictory-state`, `duplicate-id`, `uncovered-blocking` |
| **INFRA_ERROR (2)** | `illegal-transition`, `precondition-unmet`, `unknown-task`, `unknown-finding`, `duplicate-id-create`, `not-a-repo`, `bad-args` |

Determinism (R11): canonical finding order = (round, severity[`blocking`<`advisory`], file
codepoint, line, id); no timestamps in read output; byte-for-byte reproducible (SC-001, SC-008).
