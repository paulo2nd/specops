# Implementation Plan: Context Map Core

**Branch**: `008-context-map-core` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-context-map-core/spec.md`

## Summary

Deliver a **versioned, stack-neutral SpecOps context map** stored under the SpecOps-owned namespace `.specify/specops/context-map.yaml`, plus four commands — `specops context init | validate | resolve | explain` — that create, check, and **deterministically** interpret it. The core is a new engine module `contextmap.py` that owns the on-disk contract (mirroring how `ledger.py` owns `status.yaml`): it classifies the five map states (absent / malformed / schema-invalid / empty-valid / valid), validates every defect class in one pass, and resolves a path or ID into an ordered, phase-specific **Resolved Context Package** with a cycle-safe transitive expanded read set and an auditable **Reason Trace**. Path matching is gitignore-style globbing implemented in the **standard library** (no new runtime dependency); most-specific-wins uses a **total** specificity comparator (literal-prefix length → wildcard count → segment count), with genuine equal-specificity conflicts reported as ambiguous ownership. Every command reuses Feature 007's `outcome.py` exit contract (`0`/`1`/`2`) and adds a stable `status` field carrying the fine-grained outcome. Planning/review consumption is deferred to Feature 009; this feature ships only the deterministic foundation and its tests against fixtures — never run against this repository (No Self-Application).

## Technical Context

**Language/Version**: Python ≥ 3.10 (`pyproject.toml requires-python = ">=3.10"`; ruff/mypy target `py310`).

**Primary Dependencies**: Typer (CLI), PyYAML (map serialization, matching the ledger). **No new dependency** — gitignore-style glob matching and the specificity comparator are implemented with the standard library (`re`, `fnmatch`-style translation), honoring the constitution's dependency limit (Typer/PyYAML/GitPython only). GitPython is used only to locate the repository root, reusing `gitops.find_repo`.

**Storage**: One repository-level file — `.specify/specops/context-map.yaml` (YAML). It is **not** the ledger and is unrelated to `specs/*/status.yaml`. The map is repo-wide (one map per repository), not per-feature.

**Testing**: pytest — `tests/unit/test_contextmap.py` (engine: classification, validation, comparator, resolution, expansion, fallback) and `tests/integration/test_context_cli.py` (CLI: exit-code/status matrix, `--json`, absent-map, selectors). Sample maps live under `tests/fixtures/context_maps/`. Per the constitution, `context` behavior is proven **only** by these fixtures — never by creating a map in this repository.

**Target Platform**: Cross-platform CLI; **fully offline** (validation and resolution read only the map file; validation never touches the filesystem, per FR-005).

**Project Type**: Single-project Python CLI + Spec Kit extension (the `context` commands register through the existing Typer app; Feature 005's extension install ships the starter template asset).

**Performance Goals**: Resolution is a pure function of the parsed map and inputs; determinism is total (SC-001). No network, no filesystem walk during resolve/validate. Expansion is cycle-safe (each context expanded at most once), bounding work to O(contexts + edges).

**Constraints**: Deterministic and locale-independent (codepoint ordering, no locale-sensitive sort); read-only except `context init` (atomic create, never overwrite); fail-closed on unsound maps before emitting any resolution (FR-017); domain-agnostic (Principle V); exit codes as gates (Principle VI).

**Scale/Scope**: Four subcommands; one engine module; additive CLI wiring; no changes to ledger/workflow/review behavior.

## Constitution Check

*GATE: evaluated pre-Phase 0 and re-checked post-Phase 1. Result: PASS (no violations).*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** (NON-NEGOTIABLE) | **PASS.** The map is a SpecOps-owned artifact under `.specify/specops/`; the four commands are additive Typer subcommands. No Speckit-owned file, command, or workflow is modified. The starter template ships via Feature 005's extension asset mechanism. |
| **II. Physical State Ledger (Repo-as-State)** | **PASS.** The context map is distinct from the execution ledger and does not touch `status.yaml`. Read-only commands never mutate any state; `context init` writes only the map, atomically, and never overwrites. |
| **III. Automated Evidence Collection** | **PASS (unaffected).** No task-completion or evidence path is involved. |
| **IV. Surgical Agent Behavior via Injected Prompts** | **PASS.** No new injected directive and no change to existing directives — planning/review consumption of the map is deferred to Feature 009. No constitution amendment required (delivery mechanism and directive content unchanged). |
| **V. Domain Agnosticism** | **PASS.** The schema is stack-neutral (glob patterns, generic phases, free-form risk map); no framework/business coupling; **no new runtime dependency** (stdlib glob). |
| **VI. Exit Codes as Gates** | **PASS.** Every command maps its outcome onto the existing `outcome.py` contract — `0` success (incl. supported absent-map / no-match reads), `1` blocking/fail-closed (invalid/ambiguous/malformed/unsupported-version), `2` usage error — plus a stable `status` field for fine-grained branching. |

**Development-workflow compliance**: Built with plain Spec Kit; **no** `.specify/specops/context-map.yaml` is created in this repository and no `context` command is run against it. All behavior is exercised via `tests/` fixtures (Constitution §Development Workflow & Quality Gates; memory: No Self-Application).

## Project Structure

### Documentation (this feature)

```text
specs/008-context-map-core/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions R1–R13
├── data-model.md        # Phase 1 output — entities, schema, comparator, taxonomies
├── quickstart.md        # Phase 1 output — install + run + validate every SC
├── contracts/           # Phase 1 output
│   ├── context-cli.md            # the 4 commands: args, exit codes, status taxonomy, output
│   ├── context-map-schema.md     # the versioned YAML schema + defect classes
│   └── resolved-package.md       # Resolved Context Package + Reason Trace JSON shape
├── checklists/
│   ├── requirements.md  # spec-quality checklist (from /speckit-specify)
│   └── readiness.md     # requirements-quality checklist (from /speckit-checklist)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Paths verified against the current worktree; action suffixes per Constitution Principle IV
(Empirical Verification). `specops consistency` (a delivered capability) validates these against
the worktree in client repos and in this feature's own tests — it is not run against this repo.

```text
src/specops/
├── contextmap.py                         (create)  # engine + on-disk contract: schema/version,
│                                                   # state classification, validation, glob matching,
│                                                   # specificity comparator, resolution + expansion,
│                                                   # reason trace, atomic init writer; cmd_* entry fns
├── templates/specops/context-map.yaml    (create)  # shipped starter map for `context init`
├── cli.py                                 (modify)  # add `context` sub-app: init/validate/resolve/explain;
│                                                   # wire --path/--id/--phase/--json + outcome exit codes
└── ledger.py                              (modify)  # promote `_atomic_write` → public `atomic_write`
                                                     # (thin rename + alias) so init reuses one atomic idiom

tests/
├── unit/
│   └── test_contextmap.py                 (create)  # classification (5 states), validation (7 defect
│                                                   # classes, one-pass), comparator (per dimension + tie),
│                                                   # resolution determinism, expansion (dedup/order/attrib/
│                                                   # cycle), base fallback, init idempotency+atomicity
├── integration/
│   └── test_context_cli.py                (create)  # CLI end-to-end: exit/status matrix, --json shape,
│                                                   # absent-map across all read-only cmds, selector contract
└── fixtures/
    └── context_maps/                      (create)  # sample maps: valid, empty, malformed, schema-invalid,
                                                     # unsupported-version, overlapping, tie, dangling-dep,
                                                     # cycle, traversal, base-fallback
```

**Structure Decision**: Single-project layout (existing). One new engine module (`contextmap.py`)
mirrors the `ledger.py` role (owns an on-disk contract); the CLI wiring mirrors how
`reconcile`/`consistency`/`review` are thin commands over their module. The only shared edit is
promoting the atomic-write helper in `ledger.py` to public so both the ledger and the map use one
interruption-safe write idiom (DRY). No orchestration runtime, no new dependency.

## Complexity Tracking

> No Constitution Check violations and no new runtime dependency — this section is intentionally empty.

## Phase 0 — Research

See [research.md](./research.md). Decisions R1 (namespace/format), R2 (schema versioning & migration
scaffold), R3 (five-state classification), R4 (exit + `status` taxonomy reusing `outcome.py`),
R5 (total specificity comparator + stdlib glob), R6 (deterministic read-set & expansion ordering),
R7 (stable JSON envelope + diagnostic object + reason-trace shape), R8 (one-pass validation & the
seven defect classes), R9 (atomic, idempotent `init`), R10 (explicit `--path`/`--id` selectors),
R11 (determinism inputs: locale/timezone/fs-order invariance), R12 (context-ID format), R13 (risk &
gate-reference validation depth). All eight prior clarifications (two `/speckit-clarify` sessions)
are folded in; **no `NEEDS CLARIFICATION` remain**. The deferred `readiness.md` items (JSON/error
shape, ordering keys, `init` atomicity, version range, ID format, risk structure) are resolved here.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the Context Map / Context / Match Rule / Read Set / Dependency
  Edge / Resolved Context Package / Reason Trace entities, the specificity comparator definition, the
  state-classification and defect taxonomies, and the exit/`status` mapping table.
- [contracts/](./contracts/) — the CLI contract (args, exit codes, `status`), the versioned map schema,
  and the Resolved Package + Reason Trace JSON shape.
- [quickstart.md](./quickstart.md) — `context init` → edit → `validate` → `resolve`/`explain` → validate
  each Success Criterion via fixtures.

**Agent context update**: no repository agent-context file is maintained for SpecOps (development is
plain Spec Kit); this step is a no-op here and recorded for traceability.
