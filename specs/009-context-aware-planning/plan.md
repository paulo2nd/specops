# Implementation Plan: Context-Aware Planning and Impact

**Branch**: `009-context-aware-planning` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-context-aware-planning/spec.md`

## Summary

Turn the static Feature 008 context map into an **active input** to the SpecOps-augmented planning, implementation, and review phases, without building any Spec Kit primitive (Rule 8) and without a language-specific dependency parser (Principle V). The feature delivers four consumption surfaces plus ledger provenance:

1. **Plan-topology validation** — a new read-only command `specops context plan-check` that parses the plan's declared context IDs and its declared paths (reusing the existing `speckit.parse_plan_path_action` action-suffix convention), then validates them against the map: unknown declared ID and path-owned-by-undeclared-context are **blocking** (exit `1`); an **unowned** declared path is a non-blocking observation (exit `0`); a missing declaration when a map is present is blocking. Existence-agnostic (never inspects the filesystem).
2. **Explainable impact** — a new read-only command `specops context impact` that maps changed paths to directly-affected contexts, then expands to **reverse** dependents (contexts declaring a dependency *on* an affected context) over a new cycle-safe reverse-adjacency walk, attributing every in-scope context to exactly one edge from the closed set `{ownership, dependency, policy}`. Changed paths come from explicit `--path` args or, when omitted, from Git (`gitops.name_only_diff` baseline→HEAD).
3. **Stale-map detection** — a new read-only command `specops context stale` that reports context-map `match` patterns matching **zero Git-tracked files** (moved/removed), with the owning context, without touching `context validate` (which stays syntactic-only).
4. **Context provenance** — the resolved context IDs and a new **map digest** snapshotted into every task and review record via a Ledger schema bump (`v2 → v3`) with a deterministic migration that backfills an explicit no-map marker onto pre-feature records (read-compatible).
5. **Directive wiring** — the injected `plan`/`implement`/`review` directive templates gain context-aware behavior (run `plan-check`, record provenance, scope review by `impact`, surface a **non-blocking** digest-drift warning). This extends the Principle IV directives and therefore carries a **MINOR constitution amendment** (governance step, see Constitution Check).

The **map digest is greenfield** (Feature 008 emits none): a new `contextmap.map_digest()` computes a deterministic `sha256` over the canonically-serialized parsed map (stdlib `hashlib`, no new dependency). All new commands reuse `outcome.py`'s `0`/`1`/`2` contract, the `CommandResult`/`_emit_context` bridge, and Feature 008's `Context` model, `validate`, and `_matches`/`_candidates_for_path` engine — so nothing in the resolver is reimplemented. Every behavior is proven by fixtures under `tests/`, never by running `specops` against this repository (No Self-Application).

## Technical Context

**Language/Version**: Python ≥ 3.10 (`pyproject.toml` `requires-python = ">=3.10"`; ruff/mypy target `py310`).

**Primary Dependencies**: Typer (CLI), PyYAML (map/ledger), GitPython (changed-path diff + tracked-file listing). **No new runtime dependency** — the map digest uses stdlib `hashlib.sha256`; reverse expansion and stale matching reuse Feature 008's stdlib glob engine. This honors the constitution's dependency limit (Typer/PyYAML/GitPython only).

**Storage**: Reads the existing repo-wide map `.specify/specops/context-map.yaml` (Feature 008). Writes only the per-feature ledger `specs/*/status.yaml` (Feature 006) to add provenance; the ledger schema advances `v2 → v3`. No new persisted file is introduced.

**Testing**: pytest. New/extended: `tests/unit/test_contextmap_consume.py` (digest determinism, reverse expansion, unowned/bounded/unbounded, stale over tracked files, plan-topology parsing/validation), `tests/integration/test_context_consume_cli.py` (exit/status/`--json` matrix for `plan-check`/`impact`/`stale`, Git-default degenerate cases), plus extensions to `tests/unit/test_ledger.py` + `tests/integration/test_ledger_migration.py` (v2→v3 provenance migration, read-compat) and provenance recording in `tests/unit/test_status.py` / `test_review.py`. Fixtures under `tests/fixtures/context_maps/` (dependency-graph, stale, policy) and existing ledger fixtures. Coverage threshold **85%** (`--cov-fail-under=85`).

**Target Platform**: Cross-platform CLI. `plan-check` and `stale` structural parsing are offline; `impact` and `stale` read Git (tracked files / diff) via GitPython; resolution/validation remain pure functions of the parsed map.

**Project Type**: Single-project Python CLI + Spec Kit extension. New `context` subcommands register through the existing `context_app` Typer group; the extension install ships any updated directive templates.

**Performance Goals**: Determinism is total (SC-001): digest, impact, plan-check, and stale outputs are byte-for-byte reproducible (Unicode-codepoint ordering, no timestamps, canonical serialization). Reverse expansion is cycle-safe (each context visited at most once) → O(contexts + edges). Stale detection is O(patterns × tracked-files) with a single `ls-files` read.

**Constraints**: Read-only for all three new commands (FR-012, verified by before/after state comparison); provenance writes go through the existing atomic + revision-CAS `ledger.save` (interruption-safe, lost-update-safe); fail-closed on invalid/ambiguous/unsupported map, deferring to `context validate` (FR-017); domain-agnostic (Principle V); exit codes as gates (Principle VI).

**Scale/Scope**: Three new read-only commands + one engine helper (`map_digest`) + reverse-expansion/stale/plan-topology logic in `contextmap.py`; a Ledger v3 provenance migration; provenance recording in `status`/`review`; additive directive-template wiring; a MINOR constitution amendment.

## Constitution Check

*GATE: evaluated pre-Phase 0 and re-checked post-Phase 1. Result: PASS, contingent on the human-approved MINOR constitution amendment noted under Principle IV.*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** (NON-NEGOTIABLE) | **PASS.** All new surfaces are additive Typer subcommands and SpecOps-owned directive templates. No Speckit-owned file, command, or workflow is forked or destructively edited. No Spec Kit primitive (engine/gate/resume/loop) is reimplemented (Rule 8). |
| **II. Physical State Ledger (Repo-as-State)** | **PASS.** Provenance extends the existing ledger through a versioned schema bump (`v2 → v3`) with a deterministic forward migration and read-compat for prior shapes; writes use the existing atomic + revision-CAS `save`. The three read-only commands never mutate ledger or repo state. |
| **III. Automated Evidence Collection** | **PASS (unaffected).** Evidence representation is untouched (structured evidence is Feature 012). Provenance is recorded mechanically at close time, not by agent narration. |
| **IV. Surgical Agent Behavior via Injected Prompts** | **PASS — requires a MINOR constitution amendment (1.4.0 → 1.5.0).** This feature *extends* the existing **Empirical Verification** directive (plan-check now also validates declared context topology) and the **Ledger & Phase Wiring** directive (records provenance; review is scoped by `impact`; digest drift is surfaced non-blocking). Per Governance, a Principle IV directive change bumps the version and propagates to `src/specops/templates/directives/`. The amendment is additive (no principle removed/redefined) and is submitted in the same change set for **explicit human approval** (roadmap §3). |
| **V. Domain Agnosticism** | **PASS.** Provenance (list of context-ID strings + digest string + explicit marker), the digest (generic content hash), reverse expansion, and stale matching are all stack-neutral; no framework/business coupling; **no new runtime dependency** (stdlib `hashlib`). No source-code dependency parser (FR-019). |
| **VI. Exit Codes as Gates** | **PASS.** `plan-check`, `impact`, and `stale` map every outcome onto `outcome.py` — `0` (success incl. supported no-map/no-match/unowned/empty-diff), `1` (blocking: invalid/ambiguous/unsupported map, missing declaration, unknown ID, undeclared owner), `2` (usage/input error incl. can't-derive-from-Git) — plus a stable `status` field for fine-grained branching. |

**Development-workflow compliance**: Built with plain Spec Kit; **no** ledger, `context-map.yaml`, or `specops` invocation is created/run against this repository. All delivered behavior is exercised via `tests/` fixtures (Constitution §Development Workflow & Quality Gates; memory: [[no-specops-self-application]]). The directive templates are product assets edited here but never executed against this repo.

## Project Structure

### Documentation (this feature)

```text
specs/009-context-aware-planning/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions R1–R12
├── data-model.md        # Phase 1 output — entities, digest, reverse-edge model, provenance record, taxonomies
├── quickstart.md        # Phase 1 output — run + validate every SC via fixtures
├── contracts/           # Phase 1 output
│   ├── context-consume-cli.md   # plan-check / impact / stale: args, exit codes, status, output
│   ├── impact-report.md         # reverse-edge model, closed edge set, bounded-expansion + Impact JSON shape
│   ├── provenance-ledger.md     # map digest def, ledger v3 provenance record, v2→v3 migration
│   └── plan-topology.md         # plan declaration surface + topology validation rules
├── checklists/
│   ├── requirements.md  # spec-quality checklist (from /speckit-specify)
│   └── readiness.md     # requirements-quality checklist (from /speckit-checklist)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Paths verified against the current worktree; action suffixes per Constitution Principle IV
(Empirical Verification). `specops consistency` (a delivered capability) validates these against
the worktree in this feature's own tests — it is not run against this repo.

```text
src/specops/
├── contextmap.py                         (modify)  # + map_digest() (canonical sha256, no new dep);
│                                                   # + cmd_plan_check(), cmd_impact(), cmd_stale();
│                                                   # + reverse-adjacency + cycle-safe reverse expansion;
│                                                   # + closed edge-set attribution + bounded-expansion guard;
│                                                   # + new S_* statuses (impact/stale/plan-check/unowned/unbounded)
├── speckit.py                            (modify)  # + parse_plan_context_ids(): parse plan-declared context IDs
│                                                   #   (mirrors parse_plan_path_action's declaration convention)
├── ledger.py                            (modify)  # CURRENT_SCHEMA 2→3; migrate_to_current backfills
│                                                   #   context_provenance no-map marker on task/review records;
│                                                   #   validate_invariants tolerant of absent/present provenance
├── status.py                            (modify)  # record context_provenance on task close (ids + digest | marker)
├── review.py                            (modify)  # record provenance on review cycle; emit non-blocking
│                                                   #   digest-drift warning when plan-time vs review-time digest differ
├── cli.py                               (modify)  # register `context plan-check | impact | stale`; wire
│                                                   #   --path/--phase/--json + _emit_context exit bridge
└── templates/directives/
    ├── plan.md                          (modify)  # run `context plan-check`; declare context IDs (additive)
    ├── implement.md                     (modify)  # provenance recorded at task close (additive)
    └── review.md                        (modify)  # scope review by `context impact`; digest-drift warning (additive)

.specify/memory/constitution.md          (modify)  # MINOR amendment 1.4.0→1.5.0 (Principle IV directive extension)

tests/
├── unit/
│   ├── test_contextmap_consume.py       (create)  # digest determinism; reverse expansion (dedup/order/attrib/
│   │                                               #   cycle); unowned; bounded vs unbounded; stale (tracked-only,
│   │                                               #   symlink-by-path); plan-topology parse + validation matrix
│   ├── test_ledger.py                   (modify)  # + v3 provenance shape + validate_invariants tolerance
│   ├── test_status.py                   (modify)  # + provenance recorded on task close (ids+digest | marker)
│   └── test_review.py                   (modify)  # + provenance on cycle + digest-drift warning
├── integration/
│   ├── test_context_consume_cli.py      (create)  # exit/status/--json matrix for plan-check/impact/stale;
│   │                                               #   Git-default degenerate cases (clean/no-repo/no-baseline)
│   └── test_ledger_migration.py         (modify)  # + v2→v3 migration + backfill + read-compat
└── fixtures/
    └── context_maps/                    (modify)  # + dependency-graph, reverse-dependent, cycle, policy(gates),
                                                    #   stale (moved/removed), unowned-path fixtures
```

**Structure Decision**: Single-project layout (existing). Map-touching logic (digest, reverse expansion, stale, plan-topology) is added to `contextmap.py` because it consumes the module's private engine (`Context`, `validate`, `_matches`, `_candidates_for_path`) and owns the on-disk contract — the same cohesion rationale Feature 008 used for keeping all `cmd_*` there. Provenance lives in the ledger domain (`ledger`/`status`/`review`) behind the versioned schema. Plan-declaration parsing joins the other plan parsers in `speckit.py`. No new engine module, no orchestration runtime, no new dependency.

## Complexity Tracking

> No Constitution Check *violations*. The MINOR constitution amendment (Principle IV directive extension) is a required **governance action**, not a complexity exception, and is listed here only for visibility. No new runtime dependency is introduced. This table is otherwise intentionally empty.

| Item | Why Needed | Simpler Alternative Rejected Because |
|------|------------|--------------------------------------|
| Constitution amendment 1.4.0→1.5.0 | Feature 009's mandate is to integrate the map into planning/implementation/review, which are governed by the Principle IV injected directives | Shipping only the CLI commands without directive wiring would leave the roadmap's "resolve and display the minimum context package at each lifecycle phase" undelivered; the amendment is additive and human-approved |

## Phase 0 — Research

See [research.md](./research.md). Decisions **R1** (map digest: canonical `sha256`, greenfield — corrects the spec Assumption), **R2** (reverse-adjacency impact model + closed `{ownership, dependency, policy}` edge set; `policy` defined-but-reserved given the current schema), **R3** (bounded-expansion trigger), **R4** (plan declaration surface reusing the action-suffix convention + a context-ID line), **R5** (Ledger v2→v3 provenance schema + migration + read-compat), **R6** (provenance content: resolved IDs from effective paths + digest; markers for no-map/invalid-map), **R7** (`impact` Git-default via `gitops.name_only_diff`/baseline + degenerate-case exit mapping), **R8** (stale over Git-tracked files, symlink-by-path), **R9** (phase-token mapping planning→`plan`/implementation→`implement`/review→`review`), **R10** (new `S_*` status + exit taxonomy for the three commands), **R11** (directive wiring + MINOR constitution amendment scope), **R12** (determinism inputs: canonical serialization, codepoint order, no timestamps). All eleven prior clarifications (three `/speckit-clarify` sessions) are folded in; **no `NEEDS CLARIFICATION` remain**. The deferred `readiness.md` items (declaration surface CHK001, provenance record shape CHK004, error object CHK008, ledger upgrade CHK025, digest pre-existence CHK034) are resolved here.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the Plan Context Declaration, Phase-Scoped Context Package, Impact Report (reverse edges + closed edge set), Context Provenance Record, Map Digest, and Stale Reference entities; the reverse-expansion algorithm; the provenance schema and v2→v3 migration table; and the new exit/`status` mapping.
- [contracts/](./contracts/) — the CLI contract for the three new commands, the Impact Report + bounded-expansion JSON shape, the provenance/digest + migration contract, and the plan-topology declaration + validation rules.
- [quickstart.md](./quickstart.md) — install → author a dependency-graph map → `plan-check` → `impact` → `stale` → record provenance → validate every Success Criterion via fixtures.

**Agent context update**: no repository agent-context file is maintained for SpecOps (development is plain Spec Kit); this step is a no-op here and recorded for traceability.
