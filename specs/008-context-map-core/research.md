# Phase 0 — Research: Context Map Core

All decisions are grounded in the current worktree (Principle IV). Each `[CHK…]` tag marks a
`readiness.md` item this decision resolves.

## R1 — Namespace and file format

**Decision**: One repository-level map at `.specify/specops/context-map.yaml`, serialized as YAML via
PyYAML. `.specify/specops/` is the SpecOps-owned area under Spec Kit's `.specify/` root; the repo root
is located with `gitops.find_repo` and the Spec Kit install is confirmed with `speckit.has_speckit`
(`.specify/templates/`).

**Rationale**: Keeps the map inside the SpecOps namespace (Principle I), reuses the ledger's
human-editable YAML style, and stays offline. The map is repository-wide (describes all contexts),
so it is not placed under `specs/<feature>/`.

**Alternatives**: Per-feature map (rejected — the map is repo topology, not feature state); JSON
(rejected — YAML is the established, human-editable SpecOps serialization).

## R2 — Schema versioning and migration scaffold [CHK030, CHK032]

**Decision**: Mirror `ledger.py`'s versioning: `CURRENT_SCHEMA = 1`, `OLDEST_SUPPORTED = 1`, and a
`classify()` returning `current` / `too_new` / `unsupported`. A map declaring a version `> CURRENT`
is `too_new`; a version `< OLDEST_SUPPORTED` or non-integer is `unsupported`; both are rejected with a
version-specific diagnostic. Because v1 is the first schema, `migrate_to_current()` is an identity
scaffold today (no prior shape to migrate), present so future versions add forward migrations without
reshaping callers.

**Rationale**: Reuses a proven, tested pattern (Feature 006) and satisfies FR-020 without inventing a
second versioning idiom. Supported range is explicit, so "unsupported version" is objectively decidable.

**Alternatives**: No version field (rejected — FR-020); semver string (rejected — the ledger uses a
monotonic integer; consistency wins).

## R3 — Five-state classification [CHK029, CHK014]

**Decision**: `load()` returns one of five discriminated states, each mapped to a distinct `status`:
`no_map_present` (file absent), `malformed` (YAML parse error or non-mapping root), `schema_invalid`
(parses but fails schema/structural validation), `empty_valid` (valid, zero contexts), `valid`
(valid, ≥1 context). These are distinguishable from the command outcome alone (human + JSON).

**Rationale**: FR-013/FR-014 require callers to act differently per state; a single discriminated
result keeps every command consistent and testable (SC-005).

## R4 — Exit codes and status taxonomy [CHK009]

**Decision**: Reuse `outcome.py` unchanged. Map outcome **class** → exit code:

| Situation | `outcome` class | Exit | `status` field |
|---|---|---|---|
| valid map / resolved / no-match / absent-map (read-only queries) | `PASS` | `0` | `valid` / `resolved` / `no_matching_context` / `no_map_present` |
| schema-invalid / malformed / ambiguous ownership / unsupported version | `GATE_REJECTION` | `1` | `schema_invalid` / `malformed` / `ambiguous_ownership` / `unsupported_version` |
| usage error (bad/conflicting `--path`/`--id`, unknown args) | `INFRA_ERROR` | `2` | `usage_error` |

The fine-grained `status` is added as an extra key via `outcome.render(...)`; `class`/`outcome`
already drive the exit code through `outcome.exit_for`.

**Deliberate divergence (noted)**: a *malformed* (unparseable) map is classified **blocking (exit 1)**,
not exit 2, even though `LedgerParseError` uses exit 2 for a corrupt ledger. Rationale: for a
context map, "unsound map" is precisely the fail-closed *validation* outcome `context validate` exists
to report (confirmed in `/speckit-clarify` Q5); exit 2 is reserved for **caller** usage errors. This
keeps "the map is bad → 1" vs "you called it wrong → 2" clean. Recorded so the split cannot drift.

**Rationale**: No second exit contract; native gate/loop steps already understand `outcome.py`.

## R5 — Total specificity comparator + stdlib glob [CHK011, CHK012]

**Decision**: Gitignore-style glob matching implemented with the standard library (translate a pattern
to a regex handling `*`, `**`, `?`, and directory boundaries; no `pathspec`/`fnmatch` dependency).
Specificity is a **total** comparator over a tuple, compared in priority order:
1. **literal-prefix length** (count of leading non-wildcard characters) — longer wins;
2. **wildcard-token count** — fewer wins;
3. **path-segment count** — more wins.
If two *different* contexts tie on all three for a concrete path, that path has **ambiguous ownership**
→ validation error (never silently resolved). A single context's own equal-specificity patterns do not
conflict. A final codepoint-lexicographic order over the pattern string breaks ties only among
non-conflicting candidates to guarantee a total, locale-independent order.

**Rationale**: Guarantees SC-001 determinism and SC-007 most-specific-wins; adds no dependency
(Principle V / Technical Constraints). Matches the confirmed clarification (FR-008).

**Alternatives**: `pathspec` library (rejected — new dependency); single-criterion longest-prefix
(rejected — cannot distinguish `src/**` from `src/**/*.py`, collapsing distinctions into errors).

## R6 — Deterministic read-set and expansion ordering [CHK012, CHK013]

**Decision**: A phase read set preserves **declaration order** within the phase (or the inherited
`base`). The **expanded** read set is built by walking dependency edges in **declaration order**,
depth-first, cycle-safe (each context visited once), appending each dependency's own phase read set,
then **deduplicated keeping first occurrence**. Every expanded entry records its originating edge
(`via: <from>-><to>`) for the reason trace. No sorting is applied to file entries (author order is the
contract), so ordering is stable and locale-independent.

**Rationale**: Satisfies FR-012a / SC-011 (dedup, deterministic order, per-edge attribution) without a
sort that could reorder author intent.

## R7 — Stable JSON envelope, diagnostic object, reason-trace shape [CHK010, CHK014, CHK021]

**Decision**: Every command's `--json` output extends the `outcome.render` envelope
(`command`, `outcome`, `class`) with: `status` (R4), `output_version` (integer, starts at `1`, bumped
only on breaking shape change), and a command-specific payload. Diagnostics are a **list** of objects
`{code, message, context_id?, field?}` (validation may report **all** defects in one pass, R8). The
Resolved Package and Reason Trace have fixed key sets (see contracts) so the shape is stable across
runs (SC-006). Field presence is guaranteed; optional values are omitted (never `null`) exactly as
`outcome.render` already does.

**Rationale**: Makes "stable JSON shape" concrete and gives Feature 009 a versioned contract to depend
on; the reason trace gets the same stability guarantee as other JSON (closes the FR-011↔FR-015 gap).

## R8 — One-pass validation and the seven defect classes [CHK008, CHK005, CHK006, CHK018, CHK019]

**Decision**: `validate` aggregates and reports **all** defects in a single pass (never first-fail),
each with a distinct `code`. The seven classes (exactly mirroring FR-005 ↔ SC-002):
`invalid_path_pattern`, `unsafe_path_traversal` (distinct subclass — well-formed pattern escaping the
repo root via `..`/absolute), `duplicate_context_id`, `ambiguous_ownership`, `dangling_dependency`
(edge → unknown context ID), `dependency_cycle`, `unsupported_schema_version`. Gate/policy references
are validated for **well-formedness only** (non-empty string identifiers), not resolvability — their
target system arrives in Feature 012.

**Rationale**: One-pass aggregation makes fixing a map efficient and gives SC-002 one fixture per class;
the invalid-vs-traversal split and FR-005↔SC-002 alignment close the consistency findings.

## R9 — Atomic, idempotent `init` [CHK023]

**Decision**: `context init` writes the shipped starter template
(`src/specops/templates/specops/context-map.yaml`) to `.specify/specops/context-map.yaml` only when
absent, via one atomic write. Promote `ledger._atomic_write` to a public `ledger.atomic_write`
(keeping a private alias for back-compat) and reuse it (tmp → fsync → `os.replace` → dir fsync). A
second run never overwrites/mutates and reports "map already exists" (idempotent, SC-009). `init` is
the only writer; a failed/interrupted write leaves no partial map (no `.tmp` is promoted).

**Rationale**: One interruption-safe write idiom across the codebase (DRY); satisfies FR-003/FR-016.

## R10 — Explicit `--path` / `--id` selectors [CHK003, CHK004, CHK016]

**Decision**: `resolve`/`explain` take mutually exclusive `--path <p>` and `--id <id>` options and an
optional `--phase <phase>`. Both selectors, or neither, is a **usage error** (exit 2). An `--id` absent
from the map yields **no matching context** (exit 0, `status: no_matching_context`) — distinct from a
usage error. No inference of path-vs-ID from a single token.

**Rationale**: Removes the ambiguity entirely (an ID may contain `/`); deterministic and testable
(SC-015). Matches confirmed clarification Q8.

## R11 — Determinism inputs: locale / timezone / filesystem-order invariance [CHK026]

**Decision**: Resolution output contains **no timestamps** and performs **no filesystem walk**
(validation is syntactic/safety-only per FR-005), so it is invariant to fs ordering and the clock. All
ordering uses Unicode codepoint comparison (never locale-sensitive `str.casefold`/locale collation).
The only timestamp in the system is an optional `created_at` written **into** the map by `init` (via
`ledger.now_utc`), which is input data, not resolution output.

**Rationale**: Nails SC-001's "byte-for-byte identical" guarantee against every environmental variable.

## R12 — Context-ID format [CHK001]

**Decision**: A context ID is a non-empty string matching `^[A-Za-z0-9][A-Za-z0-9._/-]*$` (may contain
`/` — which is why selectors are explicit, R10), case-sensitive, and unique within the map. A
duplicate is `duplicate_context_id`; a malformed ID is a `schema_invalid` field error.

**Rationale**: Predictable, stable IDs for trace/dedup; permits hierarchical names without enabling
whitespace/control characters.

## R13 — Risk and gate-reference validation depth [CHK007, CHK006]

**Decision**: `risk` is a free-form mapping validated only as *a mapping of string keys* (values
opaque this feature — interpretation is Feature 009+). `gates` is a list of well-formed identifier
strings (non-empty, no whitespace), validated for structure only, not resolvability (Feature 012 owns
the gate registry).

**Rationale**: Stores the fields the schema promises (FR-002 e/f) with independent per-field validation
while refusing to couple 008 to unbuilt features (Rule 8 / roadmap boundary).

## Consolidated: readiness items resolved here

R2→CHK030/032 · R3→CHK029/014 · R4→CHK009 · R5→CHK011/012 · R6→CHK012/013 · R7→CHK010/014/021 ·
R8→CHK008/005/006/018/019 · R9→CHK023 · R10→CHK003/004/016 · R11→CHK026 · R12→CHK001 · R13→CHK007/006.
Remaining `readiness.md` items are covered by data-model.md / contracts (CHK013 ordering,
CHK015 version range, CHK017 no-match token, CHK020 terminology, CHK022 partial-map fail-closed,
CHK024 read-only-on-error, CHK025 deterministic cycle report, CHK027/028 measurability/traceability,
CHK031 JSON compat, CHK033/034 scope boundaries).
