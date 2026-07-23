# Implementation Plan: Gate Profiles and Structured Evidence

**Branch**: `012-gate-profiles-evidence` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-gate-profiles-evidence/spec.md`

## Summary

Replace SpecOps's single global `lint_command`/`test_command` pair and its flat
`<CLASS>:<summary>` evidence strings with (a) an **ordered, context-aware gate
profile** suite selected deterministically per run and executed **inside**
`specops review` (replacing the fixed `lint`/`test` gates in the existing
`reconcile → … → working-tree → drift` pipeline), and (b) **versioned structured
evidence records** carrying a cache-key-derived id, producer, command, exit code,
timestamp, commit range, affected paths, summary, and optional local-artifact
digest. A fixed **outcome taxonomy** (`required | optional | skipped | cached |
failed | unavailable`) annotates every gate, safe caching reuses a prior evidence
record only when its full cache key still matches, and a stable JSON report plus an
opt-in SARIF projection of Feature 011 findings make every review verdict fully
provenanced. The change is additive: it composes Feature 006's versioned ledger and
migration machinery (v5 → v6), Feature 008's context map / `map_digest` (`.specify/
specops/context-map.yaml`, each context's `gates` list and free-form `risk`
mapping), Feature 009's `context impact`, and Feature 010/011's evidence-linking
points — introducing no new runtime dependency (SARIF is plain JSON; digests use
`hashlib`; timeouts use `subprocess`).

## Technical Context

**Language/Version**: Python 3.10+ (`requires-python = ">=3.10"`, ruff/mypy target `py310`).

**Primary Dependencies**: Typer (CLI), PyYAML (ledger + profile config), GitPython
(diff/commit range). No new runtime dependency — SARIF output is plain `json`,
artifact digests use `hashlib` (stdlib), per-gate timeouts use `subprocess`
(stdlib). Constitution Technical-Constraints dependency budget is unchanged.

**Storage**:
- `specs/<feature>/status.yaml` — the Feature 006 ledger, migrated **v5 → v6**
  (`ledger.CURRENT_SCHEMA` 5 → 6): a new top-level `evidence` list of structured
  records, plus evidence-id references on tasks and Feature 011 findings. Legacy
  `<CLASS>:<summary>` strings are back-filled into structured records; the string
  field is retained for read-compat.
- `.specify/specops/gate-profiles.yaml` — a **new** versioned, stack-neutral profile
  config, a sibling of `contextmap.MAP_RELPATH` (`.specify/specops/context-map.yaml`).
  Absent → the legacy `test_command`/`lint_command` synthesize an implicit default
  profile (roadmap Rule 5 degrade).

**Testing**: pytest under `conda run -n specops` (643 tests today; repo coverage gate
= 85%). New unit + integration + error-path + idempotency + forward-migration
fixtures under `tests/unit`, `tests/integration`, `tests/fixtures`.

**Target Platform**: Any OS with Git; offline after install (Constitution + roadmap Rule 6).

**Project Type**: Single-project Python CLI (`src/specops/`, `tests/`).

**Performance Goals**: Deterministic, not throughput-bound. Caching avoids re-running
unchanged gates (FR-009); per-gate timeouts bound worst-case latency (FR-010).

**Constraints**: Byte-for-byte deterministic output over identical **recorded ledger
state** (FR-017/FR-018, as with Features 008–011 — determinism is over recorded
state, not over re-execution of nondeterministic client commands); read-only
commands never mutate state (FR-015); state changes atomic + interruption-safe via
Feature 006; stack-neutral core (Principle V) — no test-framework parsing, no
ordinal risk scale, no remote artifacts.

**Scale/Scope**: Per-feature ledger; a handful of profiles per repo; evidence records
proportional to gate runs across review rounds.

## Constitution Check

*GATE: evaluated pre-Phase 0 and re-checked post-Phase 1. Constitution v1.7.0.*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** | ✅ Purely additive. New modules + additive ledger migration; no Speckit file forked. Gate profiles are SpecOps verification-command suites invoked as native `shell`/`command` steps — **distinct** from Spec Kit's human `gate` step, which is neither touched nor duplicated (FR-020, roadmap Rule 8). |
| **II. Physical State Ledger** | ✅ Structured evidence is written **only** through the CLI, atomically and interruption-safely, guarded by Feature 006 concurrency control; versioned via the v6 migration. Commit-range references remain subordinate to `specops reconcile` for commit-existence (unchanged). |
| **III. Automated Evidence Collection** | ✅ **Enriches** the principle: `complete-task --auto` still harvests mechanically, and now also writes a structured evidence record alongside the retained `<CLASS>:<summary>` string. Directive-facing wording (evidence format) may need a MINOR constitution amendment at implement time (see below). |
| **IV. Surgical Agent Behavior via Injected Prompts** | ✅ The review directive already invokes the deterministic gates; profiles compose transparently inside `specops review`. A directive/template note about the `gate` inspection surface and structured evidence is an additive MINOR amendment, mirroring 009/010/011. |
| **V. Domain Agnosticism** | ✅ No stack coupling: risk matches by **named-key presence/equality** (no ordinal taxonomy), no test-framework result parsing (exit code + captured summary only), all client behavior stays in config. |
| **VI. Exit Codes as Gates** | ✅ Preserves the `0`/`1`/`2` taxonomy and the Feature 007 `outcome.py` contract; the new taxonomy is an **annotation** over PASS/FAIL, not a new exit-code scheme. |

**Constitution amendment (planned, MINOR, at implement time)**: like every Context/
Auditability feature before it (009 → v1.5.0, 010 → v1.6.0, 011 → v1.7.0), 012 will
add additive guidance to Principle III/IV wording (structured evidence + the
`specops gate` inspection surface) and update the injected templates
(`src/specops/templates/directives/implement.md` for the `--auto` evidence note, and
`review.md` for the profile-suite/verdict-provenance note) in the same change set.
No principle is removed or redefined.

**Dependency budget (Technical Constraints)**: unchanged — **no new runtime
dependency**. Documented in Complexity Tracking as an explicit non-addition.

**Result**: PASS (pre-Phase 0). Re-checked PASS post-Phase 1 (see end of Phase 1).

## Project Structure

### Documentation (this feature)

```text
specs/012-gate-profiles-evidence/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions R1–R12
├── data-model.md        # Phase 1 — entities, ledger v6 shape, config schema
├── quickstart.md        # Phase 1 — runnable validation scenarios
├── contracts/           # Phase 1 — config schema, evidence/report JSON, SARIF, CLI
│   ├── gate-profiles.config.md
│   ├── evidence-record.json.md
│   ├── gate-report.json.md
│   ├── sarif-output.md
│   └── cli-commands.md
├── checklists/
│   └── requirements.md  # from /speckit-specify + /speckit-clarify
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
src/specops/
├── gateprofiles.py      # NEW — profile schema parse/validate; deterministic selection
│                        #       (mirrors contextmap.py: profiles_path/validate/CommandResult)
├── evidence.py          # NEW — StructuredEvidence record, cache-key id derivation,
│                        #       string→record migration helpers, local-artifact digest
├── sarif.py             # NEW — optional SARIF 2.1.0 projection of Feature 011 findings
├── review.py            # MODIFY — evaluate(): replace lint/test with the selected
│                        #          profile suite; carry the outcome taxonomy on GateResult
├── shell.py             # MODIFY — add optional `timeout` to run_client_command (FR-010)
├── ledger.py            # MODIFY — CURRENT_SCHEMA 5→6; backfill_evidence(); v6 validators
├── status.py            # MODIFY — complete-task --auto also writes a structured record
├── handoff.py           # MODIFY — finding evidence links reference an evidence id;
│                        #          report JSON surfaces the linked evidence record
└── cli.py               # MODIFY — new `gate` sub-app (list/validate/report);
                         #          `--sarif` option on review/report

tests/
├── unit/                # gateprofiles select/validate; evidence id + digest + migration;
│                        # sarif projection; shell timeout; ledger v5→v6 migration
├── integration/         # review pipeline with profiles; verdict provenance; caching
│                        # (cache hit / 4 invalidation vectors); default-profile degrade
└── fixtures/            # profile configs; v5 ledgers with legacy evidence strings;
                         # context maps with gates/risk; findings for SARIF
```

**Structure Decision**: Single-project layout (Constitution "Structure" constraint —
modules under `src/specops/`). Three new modules keep concerns separated
(`gateprofiles` = selection, `evidence` = records/migration, `sarif` = export); the
existing `review.py` pipeline is the single integration seam. This mirrors how 008
(`contextmap.py`), 010 (`trace.py`), and 011 (`handoff.py`) each added one cohesive
module plus surgical edits to `ledger.py`/`cli.py`.

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Three new modules (`gateprofiles`, `evidence`, `sarif`) | Selection, evidence records/migration, and SARIF export are independent concerns with distinct test surfaces | One module would entangle deterministic selection with ledger-migration and an optional export adapter, hurting testability and violating the one-cohesive-module pattern of 008/010/011 |
| Ledger **v6** migration (not evidence-string reuse) | FR-006/FR-007 require queryable structured evidence and an id for verdict/finding cross-refs; strings cannot carry exit code, commit range, paths, digest, or a stable id | Keeping only strings fails the acceptance gate ("which immutable evidence records support the result") and blocks caching (no cache key to match) |
| Retain the legacy `<CLASS>:<summary>` string field alongside structured records | Read-compat for v5 consumers and the rendered revision report (Feature 011); zero-loss migration | Replacing the string outright would break v5 readers and Feature 010/011 rendering, violating "never invalidate prior shapes" |
| **No new runtime dependency** (explicit non-addition) | SARIF is plain JSON, digests are `hashlib`, timeouts are `subprocess` | A SARIF library or hashing dep would spend the constrained dependency budget (Typer/PyYAML/GitPython) for zero capability gain |
| Feature kept **unified** (not split) despite 4 user stories / 22 FRs | The four slices share one ledger-version bump and one review-pipeline seam; each is independently *testable* against fixtures (the roadmap's split trigger is loss of independent testability, not size) — matching Feature 011's own 4-US/26-FR shape | Splitting would fork the v6 migration and the `review.py` seam across features, creating an ordering/migration coupling worse than the size it avoids |

## Phase 0 — Research

See [research.md](./research.md). Resolves: profile config location/format/schema
(R1), module layout & the `review.py` integration seam (R2), ledger v5→v6 evidence
migration shape (R3), cache-key evidence-id derivation (R4), local-artifact digest
(R5), deterministic timeout enforcement (R6), SARIF 2.1.0 projection (R7), the
outcome-taxonomy ↔ existing PASS/FAIL reconciliation (R8), selection inputs from
`context impact` + effective diff (R9), determinism-over-recorded-state (R10),
default-profile synthesis & precedence (R11), and the unified-vs-split decision (R12).
No `NEEDS CLARIFICATION` remains after `/speckit-clarify` (4 decisions locked).

## Phase 1 — Design & Contracts

See [data-model.md](./data-model.md), [contracts/](./contracts/), and
[quickstart.md](./quickstart.md). Post-design Constitution re-check: **PASS** — the
design adds no new dependency, keeps every read-only command read-only, preserves the
`0/1/2` contract, holds the core stack-neutral, and lands the evidence change as an
additive, forward-migrated v6 ledger extension. Agent context file: this repository
is developed with plain Speckit artifacts and does **not** self-apply SpecOps (No
Self-Application), so no SpecOps agent-context script is run against it.

## Phase 2 — Task planning approach (for `/speckit-tasks`, not executed here)

Tasks will be ordered by user-story priority and dependency: **US1** (profile schema
+ deterministic selection + default-profile degrade) → **US2** (structured evidence +
v5→v6 migration) → **US3** (outcome taxonomy + caching + verdict provenance, the
`review.py` seam) → **US4** (JSON report + opt-in SARIF). Every task carries one or
more `[SC-xxx]` tags. Cross-cutting: the ledger v6 migration + forward-migration test
lands early in US2 (it gates US3); the `review.py` integration lands in US3 once both
selection (US1) and evidence (US2) exist; the constitution/template MINOR amendment is
a US3/US4-adjacent task in the same change set.
</content>
