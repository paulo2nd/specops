# Data Model: Supported Recovery Operations

**Feature**: 026 | **Date**: 2026-08-31 | **Phase**: 1

Ledger schema **v8 → v9**. Every change is an additive optional field; the
migration is a pure version bump with no backfill (see research D5).

---

## 1. `EvidenceRecord` — two additive optional fields

Defined in `src/specops/records.py` (`EvidenceRecord`, `total=False` extras).

| Field | Type | Presence | Meaning |
|---|---|---|---|
| `amendment` | `bool` | optional | `true` marks this record as a correction recorded after the task closed. Absent on every record written at close time and on every pre-v9 record. |
| `reason` | `str` | optional | The operator's stated reason for the correction. Required whenever `amendment` is `true`; never present otherwise. |

The record's existing fields carry their normal meaning, with these bindings:

- `producer` — `"amend"` (a new value alongside `auto` / the gate producers).
- `command` — the invocation that recorded it, for audit symmetry with `auto`.
- `exit_code` — `0`; an amendment is an operator assertion, not a program result.
- `timestamp` — when the amendment was recorded (not the original close time).
- `commit_range` — the task's range as it stands at amendment time, unchanged
  from the task's recorded `started_commit`..head.
- `superseded_by` — `null` when current; set to the next amendment's id when a
  later amendment displaces it.

**Validation**: `reason` MUST be non-empty when `amendment` is `true`. No
validation of the reason's *content* (FR-007).

### Id derivation

`id` stays a pure function of the cache key (`evidence.derive_id`). The amendment
path supplies:

```
subject = "<task_id>#amend<N>:<reason>"      # N = count of existing amendments on the task
```

`N` is what makes a repeated amendment with an identical reason and commit range a
distinct record instead of an idempotent no-op (research D2, and the spec's
"amending with identical evidence" edge case).

## 2. `TaskRecord` — no shape change

`evidence_refs: list[str]` already exists and is the sole attachment point. After
an amendment it holds **every** record ever attached to the task, ordered oldest
first; exactly one entry has `superseded_by == null` — that one is current.

`evidence: str | None` (the legacy flat string) continues to hold the task's
**current** evidence summary, so the DONE-needs-evidence invariant
(`ledger.validate_invariants`, `reconcile.py:72`) and `trace report`
(`trace.py:454`) all read the amended value.

### Derived: "current evidence of a task"

Not persisted. Computed as the single `evidence_refs` entry whose record has
`superseded_by is None`. Invariant after any amendment: exactly one.

### Derived: `evidence_history`

Not persisted. The task's `evidence_refs` entries whose records have a non-null
`superseded_by`, oldest first — i.e. everything the amendments displaced. Emitted
as a list of record ids by `trace report` alongside `evidence_amended`, so the
audit trail is reachable from the report without reading the ledger. Empty (and
therefore omitted) for a task that was never amended.

### Inherited evidence (FR-006a)

`handoff finding fix --auto` copies the task's current `evidence` string into the
finding and builds the finding its own structured record
(`src/specops/handoff.py:417`). When the copied value is an amendment, the
finding's record carries the same two fields — `amendment: true` and the
originating `reason` — so a corrected value cannot become unmarked evidence by
passing through a second record. The finding's `producer` is unchanged; only the
provenance travels.

## 3. State transitions

Task status is **unchanged** by amendment — this is the point of the feature.

```
PENDING ──start-task──> IN_PROGRESS ──complete-task──> DONE ──┐
                                                        ▲     │ amend-task
                                                        └─────┘   (evidence only)
```

`amend-task` is a self-loop on `DONE`. There is no edge out of `DONE` (FR-003).

Evidence-record lifecycle within a task:

```
current ──(a later amendment lands)──> superseded    [terminal]
```

Superseded is terminal: no record ever returns to current, and no record's content
is ever altered after it is written (FR-002).

## 4. Active-feature pointer — resolution model

`.specify/feature.json` is unchanged on disk (`{"feature_directory": "<repo-relative path>"}`).
What changes is how it is *resolved*, to match Spec Kit exactly:

| Precedence | Source | Normalization | On failure |
|---|---|---|---|
| 1 | `SPECIFY_FEATURE_DIRECTORY` env var | relative → joined to repo root | reported as an unresolvable override, named |
| 2 | `.specify/feature.json` → `feature_directory` | relative → joined to repo root | fall through |
| 3 | newest `specs/NNN-*` by numeric prefix | — | `None` |

Level 3 is SpecOps-only (Spec Kit errors instead) and is **retained** for
compatibility, but resolution now reports *which* level answered so an inferred
result can be labelled (FR-014a, research D7).

### Derived: resolution provenance

Not persisted. A value in `{override, pointer, inferred}` returned alongside the
resolved path, consumed by the resolved-feature echo in `consistency`,
`preflight`, `status show`, and `report`.

## 5. Feature identity (rename)

Three co-located facts that a rename moves together:

| Fact | Lives in | Updated by rename |
|---|---|---|
| directory name | `specs/<name>/` | yes — the directory is moved |
| ledger feature name | `status.yaml` → `feature` | yes |
| ledger branch reference | `status.yaml` → `branch` | only when the operator supplies the new name (FR-017) |
| specification identity header | `spec.md` → `**Feature Branch**` | yes (FR-016a) |
| active pointer | `.specify/feature.json` | only when the renamed feature was active (FR-018) |
| any other prose mention | plan/tasks/checklists | **no** — reported only (FR-016b) |

Every ledger record (tasks, evidence, acknowledgements, review cycles, revision
counter) is carried through byte-identical. The rename is an identity change, not
a history change.

**Note on `branch`**: `ledger.validate_identity` (`ledger.py:669-671`) refuses any
write when the ledger's `branch` differs from the current Git branch. A rename
that updates `branch` to a name the operator has not yet created in Git therefore
makes the *next* command fail closed until they rename the branch. That is
correct fail-closed behaviour, and the rename's output must say so — it is the
difference between a confusing refusal and an expected one.
