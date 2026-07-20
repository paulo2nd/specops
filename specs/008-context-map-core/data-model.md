# Phase 1 — Data Model: Context Map Core

Entities are stack-neutral and serialized in `.specify/specops/context-map.yaml`. Field-level
validation is independent per FR-002 (a defect in one field is reported without conflating another).

## Context Map (root document)

| Field | Type | Rules |
|---|---|---|
| `schema_version` | integer | Required. `== 1` current; `> 1` → `too_new`; `< 1`/non-int → `unsupported` (R2). |
| `created_at` | string (RFC3339 UTC) | Optional; written by `init` via `ledger.now_utc`. Input data only — never echoed in resolution output (R11). |
| `contexts` | list[Context] | Required (may be empty → `empty_valid`). Order is the declaration order used for tie-breaking and expansion. |

Map-state classification (`load()` → discriminated result, R3): `no_map_present`, `malformed`,
`schema_invalid`, `empty_valid`, `valid`.

## Context

| Field | Type | Rules |
|---|---|---|
| `id` | string | Required, unique, `^[A-Za-z0-9][A-Za-z0-9._/-]*$` (R12). Duplicate → `duplicate_context_id`. |
| `match` | list[string] (glob) | Required, ≥1. Each is a gitignore-style pattern relative to repo root. Malformed → `invalid_path_pattern`; escapes root (`..`/absolute) → `unsafe_path_traversal`. |
| `reads` | map (see Read Set) | Optional. Keys: `base` + phase names. |
| `ownership` | string / map | Optional descriptive topology metadata (not a write boundary — Feature 009). |
| `dependencies` | list[string] (context IDs) | Optional. Each MUST reference an existing context id → else `dangling_dependency`. Participates in cycle check. |
| `gates` | list[string] | Optional. Well-formed identifiers only; resolvability NOT checked (Feature 012). |
| `risk` | map[string, any] | Optional. Validated as a string-keyed mapping only (R13). |

## Match Rule

A single glob pattern with an intrinsic **specificity** tuple used for most-specific-wins (R5):

`specificity = (literal_prefix_len DESC, wildcard_token_count ASC, segment_count DESC)`, final
tie-break by codepoint order of the pattern. Compared as a **total order**. Two *different* contexts
tying on the three semantic dimensions for a concrete path → `ambiguous_ownership` (validation error).

## Read Set

```yaml
reads:
  base: ["src/api/**"]           # phase-agnostic fallback (optional)
  plan: ["docs/api-design.md"]   # phase-specific (optional)
```

- Keyed by lifecycle phase (`specify`/`plan`/`tasks`/`implement`/`review`) plus optional `base`.
- Resolution for a phase returns that phase's list, else inherits `base`, else an explicit **empty**
  list (distinct from "no matching context"). Order = declaration order (no sort). FR-009 / SC-012.

## Dependency Edge

A directed edge `from_id -> to_id` (`to_id` MUST exist). Expanded depth-first in declaration order,
cycle-safe (each context visited once). A cycle → `dependency_cycle`, reported with participating IDs
in stable discovery order (SC-008, CHK025). A missing `to_id` → `dangling_dependency` (distinct).

## Resolved Context Package (output of `resolve`)

Fixed key set (stable shape, SC-006). See [contracts/resolved-package.md](./contracts/resolved-package.md).

| Field | Meaning |
|---|---|
| `context_id` | the selected context |
| `phase` | the requested phase (or `null`/omitted if none) |
| `read_set` | ordered phase-specific list (or `base`/empty fallback) |
| `read_set_source` | `phase` \| `base` \| `empty` (why this list) |
| `dependencies` | declared dependency edges (IDs) |
| `expanded_read_set` | deduped, ordered entries `{path, via}` (per-edge attribution, FR-012a) |
| `gates` | declared gate identifiers (unresolved) |
| `risk` | declared risk map (opaque) |

## Reason Trace (output of `explain`)

Ordered, deterministic (same shape guarantee as JSON, R7):

1. `candidates`: each matching rule `{context_id, pattern, specificity}` in comparator order.
2. `selected`: `{context_id, deciding_dimension}` — which specificity dimension (1/2/3) decided, or
   `ambiguous` when a tie was rejected.
3. `read_set_source`: `phase` | `base` | `empty` (fallback stated, FR-009).
4. `dependency_edges`: `[{from, to}]` contributing to the expanded set (per-edge).
5. `gates`: identifiers pulled in.

## Exit code / status mapping (R4, authoritative)

| `status` | `class` (`outcome.py`) | Exit | Commands |
|---|---|---|---|
| `valid` | `PASS` | 0 | validate |
| `resolved` | `PASS` | 0 | resolve, explain |
| `no_matching_context` | `PASS` | 0 | resolve, explain |
| `no_map_present` | `PASS` | 0 | validate, resolve, explain |
| `empty_valid` | `PASS` | 0 | validate (and resolve→no-match) |
| `schema_invalid` | `GATE_REJECTION` | 1 | validate, resolve, explain (fail-closed) |
| `malformed` | `GATE_REJECTION` | 1 | all (fail-closed) |
| `ambiguous_ownership` | `GATE_REJECTION` | 1 | validate, resolve, explain |
| `unsupported_version` | `GATE_REJECTION` | 1 | all |
| `usage_error` | `INFRA_ERROR` | 2 | resolve/explain (bad/conflicting selectors) |

Fail-closed (FR-017, CHK022): any `GATE_REJECTION` status is emitted **before** any resolved package;
a partially-valid map is still rejected. Read-only guarantee holds on every path including errors
(CHK024) — only `init` writes.
