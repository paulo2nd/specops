# Implementation Plan: Internal Hardening

**Branch**: `018-internal-hardening` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-internal-hardening/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Consolidate the internal infrastructure duplicated across Features 008–013 into single definition sites — one command-result abstraction, one output-emission function, explicit public cross-module contracts, one ledger-loading path, one evidence-grammar owner, one finding factory with a co-located line parser/renderer, and a deduplicated test harness — with byte-identical CLI behavior throughout, except the single sanctioned delta: lane JSON output gains the standard envelope fields it was missing. Technical approach: extend the existing `outcome.CommandResult` pattern (already proven by contextmap/doctor/gateprofiles) to the two remaining copies, collapse the five `_emit_*` helpers into one, rename the 39 verified cross-module private call targets to public names, and route all ledger reads through `ledger.load_raw`. No new runtime dependencies; no schema bump (ledger stays at v7).

## Technical Context

**Language/Version**: Python 3.10+ (existing project floor; `pyproject.toml` `requires-python = ">=3.10"`)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), GitPython (evidence collection) — unchanged; FR-013 forbids additions

**Storage**: repository files — `status.yaml` ledger (v7, no schema change), `lane.yaml`, `specops.json`; serialization formats untouched

**Testing**: pytest + pytest-cov (≥85% enforced floor), ruff, mypy strict — all existing gates; Typer `CliRunner` for the in-process integration migration (already used by 27 test files)

**Target Platform**: cross-platform CLI (macOS/Linux/Windows), same as today

**Project Type**: single Python CLI package (`src/specops/`)

**Performance Goals**: integration-suite wall-clock reduction ≥30% after the in-process migration (SC-005); no runtime performance change expected or required for the CLI itself

**Constraints**: byte-identical human/JSON output and exit codes for every command (FR-003), with the lane JSON envelope addition as the only sanctioned delta; zero new runtime dependencies; No Self-Application (constitution §Development Workflow) — all verification via test fixtures

**Scale/Scope**: ~10,100 lines across 27 production modules; 39 verified cross-module private call sites; 5 emit helpers → 1; 2 duplicated result dataclasses → 0; 6 `_git` test helpers → 1; 3 ledger builders → shared parametrized factories; ~17 integration files migrating from subprocess to in-process invocation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|-----------|------------|--------|
| I. Speckit Extension, Never Replacement | Pure internal refactor of SpecOps' own modules. No Spec Kit surface, workflow, template, or integration file is touched. | PASS |
| II. Physical State Ledger | Ledger semantics, schema (v7), and CLI-exclusive manipulation unchanged. Consolidating reads onto `ledger.load_raw` strengthens the single-authority property. | PASS |
| III. Automated Evidence Collection | Evidence grammar and structured records unchanged; grammar gains a single owning module (`evidence.py`) with identical accept/reject behavior (FR-007). | PASS |
| IV. Surgical Agent Behavior via Injected Prompts | No directive content changes; templates under `src/specops/templates/` untouched. No constitution amendment required. | PASS |
| V. Domain Agnosticism | No client-facing configuration or stack coupling introduced. | PASS |
| VI. Exit Codes as Gates | Exit codes are part of the byte-identical contract (FR-003); the unified emit preserves each family's status→class→exit-code mapping via `outcome.exit_for`. | PASS |
| Technical Constraints (deps) | Typer/PyYAML/GitPython only — unchanged. Nothing to justify in Complexity Tracking. | PASS |
| Dev Workflow (No Self-Application) | All verification runs through `tests/` fixtures; the golden output capture (quickstart) runs against fixture repos, never this repository. | PASS |

**Sanctioned exception**: the lane `--json` envelope gains `output_version` and `status` fields (additive only). This is FR-003's single delta, recorded in CHANGELOG as the feature's only behavior change. It does not violate any principle — it brings lane output *into* conformance with the envelope contract every other family already honors.

**Post-Phase-1 re-check (2026-07-25)**: design artifacts introduce no new dependencies, no schema changes, and no Spec Kit surface changes. All gates still PASS.

## Project Structure

### Documentation (this feature)

```text
specs/018-internal-hardening/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: verified inventories + consolidation decisions
├── data-model.md        # Phase 1: internal shapes (result, envelope, finding, evidence)
├── quickstart.md        # Phase 1: validation guide (golden capture, scans, timing)
├── contracts/
│   ├── cli-output.md    # Byte-identical output contract + the one lane delta
│   └── internal-api.md  # The promoted public helper contracts (old → new names)
├── checklists/
│   └── requirements.md  # Spec quality checklist (complete)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/specops/
├── outcome.py           # (modify) canonical CommandResult — absorbs trace/handoff result usage
├── cli.py               # (modify) five _emit_* helpers → one _emit; gate_report preamble dedup
├── trace.py             # (modify) TraceResult → outcome.CommandResult subclass; path-norm/finding-line consumers move to public homes
├── handoff.py           # (modify) HandoffResult → subclass; consume shared finding factory; canonicalization promoted
├── contextmap.py        # (modify) promote matches/classify_pattern/candidates_for_path/RESOLVABLE/CLASS_FOR_STATUS for cross-module consumers
├── status.py            # (modify) promote load_for_write/finalize/get_feature_dir; cmd_show → ledger.load_raw + compact_status snapshot; evidence grammar moves out
├── ledger.py            # (modify) promote ledger_path; remains the single loading authority
├── evidence.py          # (modify) becomes sole owner of the <CLASS>:<summary> grammar (validation + parsing)
├── findings.py          # (create) shared finding-record factory + finding-line parse/render pair
├── reconcile.py         # (modify) load_state delegates to ledger.load_raw
├── review.py            # (modify) promote existing_evidence/profile_gates
├── gateprofiles.py      # (modify) promote affected_for; consume public contextmap names
├── ingestion.py         # (modify) consume public path-normalization name
├── sarif.py             # (modify) consume public canonicalization name
├── lane.py              # (modify) consume public ledger/review/trace names; lane emit joins unified _emit
├── doctor.py            # (modify) consume public contextmap status map
├── initializer.py       # (modify) promote install_review/scan_markers
├── migration.py         # (modify) consume public initializer name
└── extension.py         # (modify) consume public initializer name

tests/
├── conftest.py          # (modify) export single git() helper (check=True) + parametrized ledger builders
├── unit/                # (modify) drop local _git/_make_ledger copies; rename private refs to public names
└── integration/         # (modify) migrate subprocess CLI invocations → CliRunner; explicit subprocess smoke set (@pytest.mark.subprocess)
```

**Structure Decision**: single-project layout, unchanged. One new module (`src/specops/findings.py`) co-locates the finding factory with the line parser/renderer (FR-008/FR-009); everything else is in-place modification. No packaging or build changes.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.
