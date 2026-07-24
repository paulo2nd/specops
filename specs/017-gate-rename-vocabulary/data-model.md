# Data Model: Gate Rename & Vocabulary Pass

**Feature**: 017 | **Date**: 2026-07-24 | **Phase**: 1

This feature introduces **no persisted data** and changes **no** existing schema, ledger
field, phase identifier, verdict value, or JSON key (FR-011, SC-005). The "entities" below
are runtime/interface constructs and one documentation artifact — modeled here to pin
their attributes and invariants for tasks and tests.

## E1 — Gate command (`specops preflight`)

The canonical name for the deterministic mechanical gate suite.

| Attribute | Value / Rule |
|---|---|
| Name | `preflight` (canonical) |
| Behavior | Identical to the pre-rename `specops review`: reconcile → gate-profile suite → working-tree (→ drift), cheapest-first |
| Options | `--json`, `--soft`, `--sarif` (identical set and semantics) |
| Exit codes | `0` pass, `1` gate-rejection / REJECTED, `2` infra/data error (unchanged, Principle VI) |
| Output `command` value | `"preflight"` (mirrors invoked name, FR-004) |
| Stderr | Empty on success (no notice) |

**Invariant**: for any repository state, `preflight`'s verdict, exit code, and stdout equal
the pre-rename `review`'s, except the `command` string value.

## E2 — Deprecated alias (`specops review`)

A behavior-identical alias retained for the deprecation window.

| Attribute | Value / Rule |
|---|---|
| Name | `review` (deprecated alias of `preflight`) |
| Behavior | Identical to `preflight` for the same state (same verdict, exit code, stdout) |
| Output `command` value | `"review"` (mirrors invoked name — byte-stable for existing consumers) |
| Stderr | **Exactly one** deprecation line per invocation |
| Suppressible | **No** — no flag, no env var (Clarification Q2) |
| Help surface | Help/short_help prefixed `[DEPRECATED — use 'specops preflight']`; `preflight` shown as canonical (FR-014). NOT the Click `deprecated=` flag — it would auto-emit a competing stderr line (finding C1). |
| Lifecycle | Ships this feature; removed no earlier than next MINOR, never in a PATCH (FR-006) |

**Invariant**: `review`'s stdout and exit code are byte-identical to `preflight`'s for the
same state; the only difference is the single stderr line and the `"command"` value.

## E3 — Deprecation notice

| Attribute | Value / Rule |
|---|---|
| Stream | stderr only (FR-003) |
| Cardinality | Exactly one line per `review` invocation |
| Timing | Emitted before the gate executes (survives non-zero exits) |
| Content | Names the replacement (`specops preflight`) and the removal window |
| Effect on stdout | None — stdout/JSON remain byte-identical to pre-rename |

## E4 — Outcome JSON (`command` field) — unchanged shape

The stable outcome object (`outcome.render`) is **unchanged** in shape. Only the *value*
of the existing `command` key varies by invoked name.

| Key | Before | After |
|---|---|---|
| `command` | `"review"` | `"review"` (via alias) or `"preflight"` (canonical) — same key, name-mirrored value |
| `outcome`, `class`, `verdict`, `gates`, … | unchanged | unchanged |

**Invariant (SC-005)**: no key is added, removed, or renamed; `OUTPUT_VERSION` is not bumped.

## E5 — Reserved "review" vocabulary (unchanged)

Terms that legitimately mean *review* and MUST NOT be renamed (FR-013):

- `REVIEW` phase identifier and its ledger transitions.
- The `/specops-review` directive and the `command: specops.review` workflow step.
- The review-cycle verdict (`APPROVED` / `REJECTED`) and `review_cycles` records.

## E6 — Vocabulary sweep catalogue (documentation artifact)

The recorded dispositions of every user-facing overloaded term the sweep examined. Lives in
[research.md §D8](./research.md); not persisted in the repo state.

| Rule | Value |
|---|---|
| Renamed entries | Exactly one: `review → preflight` |
| Other entries | Disposition `keep`/`document`, each with a rationale |
| Completeness | Zero identified terms left unaddressed (SC-008) |
