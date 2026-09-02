# Contract: approval coverage guard

**Feature 027** | behavior change to `status._gate_review_coverage` | Principle II
carve-out narrowed (research R2)

Guards every DONE entry point (REVIEW→DONE, the APPROVED record, a plain DONE) —
unchanged from Feature 025.

## Evaluation order

1. **No reviewed-scope records on any round** → return (no-op). Legacy /
   in-flight ledgers keep the pre-025 cycle-result behavior. **Unchanged**
   (FR-008).
2. **Records exist but the baseline does not resolve** → block. **Unchanged**
   message (FR-009).
3. **Target set empty** (no product change since the baseline) → return.
   **Unchanged**.
4. **`never_reached` non-empty** → block, naming the paths. **New** — replaces
   the three branches below.

## Retained branches (corrected during implementation)

The plan called for these three to be replaced. They are **retained, unchanged, with
byte-identical messages** — the per-path test is added ahead of them, not in place of
them. `test_unreviewed_commit_after_frontier_blocks` (Feature 025) proved why: a path
reached by an earlier round and re-touched after the last one is still a member of the
reached set, so the set difference cannot see it.

| Branch (`status.py`) | Status | Why it cannot be dropped |
|---|---|---|
| `not has_anchor` | retained, message unchanged | a path changed both before and inside a covered range leaves the set difference empty |
| `not frontier_resolves` | retained, message unchanged | with the frontier gone the tail cannot be computed at all, so an unreviewed re-touch cannot be ruled out |
| `unreviewed_tail` | retained, message unchanged | the re-touch case above |

**Evaluation order**: `never_reached` runs **first** — it is the only branch that can
name the offending files — then the three above.

## New case that blocks

A recorded range whose endpoints no longer resolve **while the baseline still
resolves** (a corrective round's commits squashed or amended). Today this is
silently credited. Recovery is one command: `handoff record-scope` on the round
already open re-anchors over `baseline..HEAD` (`handoff.py:558-562`), closing the
hole without consuming a round.

## Message shape (FR-007, R6)

```
Cannot enter DONE: 37 product path(s) changed since the baseline have never been
reviewed by any recorded round: src/a.py, src/b.py, ... (10 shown of 37). Run
'specops handoff record-scope' to re-anchor the review scope over them.
```

- At most **10** paths named, in the derivation's sorted order.
- The total count is always stated.
- ≤10 paths ⇒ all named, no `(N shown of M)` suffix.
- The complete set reaches consumers through `never_reached_paths` in the
  `record-scope` JSON — `SpecopsError` carries no structured payload.

## Exit codes

Unchanged: blocking ⇒ `1`. Principle VI's `0`/`1`/`2` set is untouched.

## Unchanged elsewhere

The findings gate (Feature 011), the cycle-result gate (Feature 006), the round
cap (Feature 025), the `preflight` gate suite, `reconcile`'s exemption of
`reviewed_range` endpoints.
