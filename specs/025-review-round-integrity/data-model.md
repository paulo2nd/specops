# Phase 1 Data Model — Review Round Integrity

Schema **v7 → v8**. All additions are optional; a pre-v8 record simply lacks
them. No field is removed, renamed, retyped, or enum-narrowed (Feature 021
freeze: additive-only).

## 1. `ReviewCycleRecord` — new optional `reviewed_range` + `review_role`

Current (`records.py:89-97`) carries `round`, `started_at`, `completed_at`,
`result`, `context_provenance`, `handoff`. This feature adds:

| Field | Type | Meaning |
|-------|------|---------|
| `reviewed_range` | `str` (optional) | The commit range this round's Step-3 review covered, in the existing `"<from>..<to>"` convention. Absent on rounds that never performed Step-3 (gate-rejected rounds) and on all pre-v8 cycles. |
| `review_role` | `"anchor" \| "corrective"` (optional) | How the range was derived: `anchor` = `from` is the ledger baseline; `corrective` = `from` is the prior scoped round's `to`. Present iff `reviewed_range` is. |

```yaml
review_cycles:
  - round: 1                       # anchor round: full baseline..HEAD hunt
    started_at: "...Z"
    completed_at: "...Z"
    result: REJECTED               # found blocking findings — still recorded scope
    reviewed_range: "53199654..a1b2c3d"
    review_role: anchor
    handoff: { ... }
  - round: 2                       # corrective round: only the fix delta
    started_at: "...Z"
    completed_at: null
    result: null
    reviewed_range: "a1b2c3d..e4f5061"
    review_role: corrective
    handoff: { ... }
```

**Derivation (never self-reported)** — computed by `reviewscope` from git:

- `to = gitops.head_sha(repo)` at record time (tree is clean at review).
- `from = status.read_baseline(root)` when no earlier cycle has a
  `reviewed_range` → `review_role = anchor`.
- `from =` the most recent earlier cycle's `reviewed_range.to` otherwise →
  `review_role = corrective`.

**Validation** (extends `finding_structural_defects` / cycle invariants,
`ledger.py`): when present, `reviewed_range` MUST be a `"<from>..<to>"` string
with non-empty endpoints and `review_role ∈ {anchor, corrective}`; a `corrective`
role MUST NOT appear on the first scoped cycle. These are structural checks on the
string shape only — never a git round-trip at validation time (git resolvability
is checked lazily by the coverage guard, R3/R5).

**Reconcile exemption (R7)**: the commit ids inside `reviewed_range` are **not**
subject to `reconcile`'s "registered commit must exist" invariant — they are
historical review HEADs a legitimate rebase can orphan. `reconcile` does not
verify them (unchanged behavior); the coverage guard tolerates an unresolvable
endpoint by dropping that range. This is a deliberate, documented exemption
(analogous to the `HUMAN_COMMIT = "(human)"` sentinel), pinned by a regression
test so a future change cannot silently start blocking on rebased history.

## 2. Ledger document — new optional `review_halt` marker

Added to `LedgerDocument` (`records.py:141-162`) as an optional top-level key,
written only when the round cap is hit:

| Field | Type | Meaning |
|-------|------|---------|
| `review_halt` | object (optional) | Records that the review loop reached its configured bound and handed control to a human. Distinct from any review verdict. |
| `review_halt.at_round` | `int` | The round after which opening the next round was refused. |
| `review_halt.cap` | `int` | The configured cap in effect. |
| `review_halt.recorded_at` | `str` | Timezone-aware timestamp (`ledger.now_utc()`). |

```yaml
review_halt:
  at_round: 10
  cap: 10
  recorded_at: "2026-08-02T13:00:00+00:00"
```

The marker is informational/audit state; it does **not** itself gate future
transitions. **Resume (R8)**: the cap is re-evaluated from live `specops.json` on
each round-opening attempt, so a human resumes by raising `review_round_cap`
(the next round then opens normally), by approving (DONE stays reachable when
coverage is complete and blocking findings verified), or by `rebaseline`. The
`review_halt` record is never cleared automatically — it stays for audit — and it
carries **no** verdict on any finding (FR-006).

## 3. Coverage evaluation — derived, not persisted

`reviewscope.coverage(repo, baseline, head, cycles) -> Coverage` is pure and
computed on demand at approval time:

| Field | Type | Meaning |
|-------|------|---------|
| `target_paths` | `set[str]` | `name_only_diff(baseline, head)` — the current effective diff. |
| `covered_paths` | `set[str]` | Union of `name_only_diff(from, to)` over each scoped cycle whose endpoints both `commit_exists`. |
| `missing_paths` | `list[str]` | `sorted(target_paths − covered_paths)`; empty ⇒ complete. |
| `has_scope_records` | `bool` | Whether any cycle carries a `reviewed_range` (the degradation switch, R5). |

Consumed by the `_gate_done` guard: block iff `has_scope_records and missing_paths`.
When `not has_scope_records` → no-op (legacy degradation). When the baseline is
unresolvable while scope records exist → fail closed (exit 1), never silent pass.

## 4. Configuration — new optional `review_round_cap`

`config._DEFAULTS` (`config.py:12-17`) gains `"review_round_cap": 10`. Seeded into
`specops.json` by `init`/`merge_preserve`. Read with a defensive coercion at the
consumer (no central validator exists; mirror `lane_safety_overrides`):

```python
raw = cfg.get("review_round_cap")
cap = raw if isinstance(raw, int) and raw > 0 else 10
```

## Migration summary (v7 → v8)

- `ledger.CURRENT_SCHEMA = 8`.
- No `backfill_*` helper (pure version bump; parity with v6→v7). Legacy cycles
  gain no `reviewed_range` → the coverage guard degrades (R1/R5).
- `LedgerDocument` docstring/keys and `ReviewCycleRecord` updated in `records.py`.
- Frozen-ledger test updated to the v8 optional-field shape (additive; the base
  key set is unchanged for pre-existing consumers).
