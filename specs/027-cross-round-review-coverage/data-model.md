# Phase 1 Data Model: Cross-Round Review Coverage

**Feature**: 027 | **Date**: 2026-09-02

Nothing in this feature is persisted. Ledger schema stays at **v9**; no migration
(R8). Every entity below is derived at evaluation time from records Feature 025
already writes plus the git repository.

---

## Persisted input (unchanged, read-only here)

### `review_cycles[].reviewed_range` / `review_role`

`records.ReviewCycleRecord`, optional since v8 (`records.py:98-102`).

| Field | Type | Notes |
|---|---|---|
| `reviewed_range` | `str` | `"<from>..<to>"`, git-derived, never reviewer-supplied |
| `review_role` | `str` | `"anchor"` \| `"corrective"` |

Structural validation (`ledger._reviewed_scope_violations`) is **unchanged**:
string-shape only, never a git round-trip. Resolvability stays a lazy property
checked by the coverage derivation, so a rebased-away endpoint remains a
*coverage* fact, not a ledger *violation*.

---

## Derived entities

### 1. Product path set

`reviewscope.product_paths(paths, feature_name) -> list[str]`

Drops, for coverage purposes:

- everything `trace.is_managed` drops — `.specify/`, `specops.json`, and
  `specs/<active-feature>/`;
- **new (FR-005a)**: every remaining path under `specs/` — any feature's
  directory, not just the active one (R5).

`trace.is_managed` is not modified; the drift gate's exclusion is untouched.

### 2. Reached set

Union, over every recorded range whose **both** endpoints resolve
(`gitops.commit_exists`), of `product_paths(name_only_diff(from, to))`.

A range with an unresolvable endpoint contributes the empty set (FR-004, R2).

### 3. Target set

`product_paths(name_only_diff(baseline, HEAD))`. Empty target ⇒ nothing to
review; coverage is vacuously satisfied (spec AS US3-5).

### 4. Never-reached set

`sorted(target − reached)`. The feature's central derived value.

- Consumed by the approval guard (FR-007).
- Reported by name in `handoff record-scope` output (FR-001, FR-001a).
- Never persisted (FR-010). Recomputed on every evaluation, so it cannot go stale
  against a moved baseline or a rewritten history.

### 5. `Assessment` (reshaped)

`reviewscope.Assessment` — the single value `assess()` returns.

| Field | Type | Meaning |
|---|---|---|
| `has_scope_records` | `bool` | any round carries a well-formed range — the FR-008 degradation switch |
| `target_empty` | `bool` | no product change since the baseline |
| `never_reached` | `list[str]` | entity 4, sorted |

**Removed** (R3): `has_anchor`, `frontier`, `frontier_resolves`,
`unreviewed_tail`. All four are special cases of `never_reached` being non-empty;
`assess` has one caller (`status._gate_review_coverage`), and `Assessment` is
internal — not part of the Feature 021 freeze.

### 6. Emitted scope sets (`handoff record-scope`)

| Set | Derivation | Persisted |
|---|---|---|
| priority (`scope_paths`) | **unchanged** — anchor: target; corrective: `prev_to..HEAD` + still-open findings' files | no |
| `baseline_paths` | entity 3 | no |
| `not_reverified_paths` | `baseline_paths − scope_paths` | no |
| `never_reached_paths` | entity 4 | no |

Invariants: `scope_paths ∪ not_reverified_paths ⊇ baseline_paths`;
`not_reverified_paths ∩ scope_paths = ∅`; on an anchor round
`not_reverified_paths = ∅`.

`reviewed_range` and `review_role` remain the only things `record-scope` writes
(FR-002).

---

## State transitions

None. No entity here has a lifecycle — each is a pure function of
(ledger records, git repository) at the moment it is evaluated.
