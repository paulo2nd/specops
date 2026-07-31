# Implementation Plan: Lifecycle Recording Coverage

**Branch**: `022-lifecycle-recording-coverage` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/022-lifecycle-recording-coverage/spec.md`

## Summary

Give every Spec Kit lifecycle command a defined SpecOps story. Three legs:

1. **Converge recording** — new `before_converge`/`after_converge` native
   hooks deliver a converge directive pair: fail closed **before mutation**
   via a new additive `specops status sync-tasks --check` precondition
   (stop-and-ask, no mutation, specific diagnostic), then record the append
   with `specops status sync-tasks` — an explicit, deterministic exposure of
   the existing `_sync_tasks` merge (**append** semantics; rebaseline
   rejected, research R1) — with the SC-tagging obligation in the directive
   and `specops consistency` as the non-blocking coverage surface.
2. **Optional-step decision parity** — `specops status record-step` becomes
   pre-ledger-safe by transparently buffering to a feature-scoped
   `.specops-pending-steps.json`, drained into `workflow.skipped_steps` at
   `init-spec` (generalizing the #50 fix). New `after_clarify`/
   `after_checklist`/`after_analyze` hooks record **run** decisions in
   slash-command mode; **skip** is derived at the next mandatory seam (tasks
   directive for clarify/checklist, implement directive for analyze) in both
   modes. The workflow's record steps move back adjacent to their gates, and
   the full workflow gains an optional **converge gate** in the corrective
   round (`record-step converge`, new step value).
3. **taskstoissues** — verified read-only (no hook, no directive), protected
   by a permanent regression test; `--if-needed` asymmetry documented as a
   deliberate contract.

Ledger schema stays **v7** — no migration. All CLI/manifest changes are
additive under the Feature 021 freeze.

## Technical Context

**Language/Version**: Python 3.11+ (existing package; no change)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), `packaging` — unchanged; no new dependencies

**Storage**: ledger `status.yaml` stays at schema v7 (no migration; `workflow.skipped_steps` entry shape unchanged, `converge` is a new allowed step value). One new SpecOps-owned transient artifact: `specs/<feature>/.specops-pending-steps.json` (pre-ledger decision buffer, atomic writes via `fsutil`, drained and deleted at `init-spec`).

**Testing**: pytest (`conda run -n specops pytest`), following the established patterns: directive tests (`tests/unit/test_lite_directive.py`, `test_implement_directive.py`), workflow-definition tests (`tests/unit/test_workflow_definition.py` — the #50 ordering test inverts), extension-manifest tests (`tests/unit/test_extension.py`), status/CLI tests (`tests/unit/test_status.py`, `test_cli.py`)

**Target Platform**: anywhere the CLI runs (macOS/Linux/Windows); directives and workflow are platform-neutral

**Project Type**: CLI tool + prompt-template product assets (this feature touches CLI code, template assets, docs, and tests)

**Performance Goals**: N/A — a handful of extra read/write-one-file CLI invocations per lifecycle; no hot paths

**Constraints**: Feature 021 contract freeze — all changes additive (new subcommand `status sync-tasks`, new `record-step` step value and `--if-absent` flag, new hook registrations, new success path where `record-step` previously exited 2 pre-ledger); frozen exit-code set 0/1/2 preserved; no machine-output shape changes. Rule 5: every new directive is a no-op without SpecOps. Rule 8: converge/taskstoissues themselves are never reimplemented.

**Scale/Scope**: 2 modules modified (`status.py`, `extension.py` + CLI wiring in `cli.py`), 5 new directive templates + 2 modified, 1 workflow template modified, 3 docs files + CHANGELOG, ~6 test files (3 new, 3 extended); no schema migration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Evaluation | Result |
|-----------|------------|--------|
| I. Speckit Extension, Never Replacement | All new behavior enters through Spec Kit's native extension surfaces: five new hook registrations (`before_/after_converge`, `after_clarify/checklist/analyze`) in the SpecOps-owned manifest, sourced from SpecOps directive templates. Converge and taskstoissues themselves are untouched (Rule 8). | PASS |
| II. Physical State Ledger | Strengthened: the converge seam closes a silent-divergence window; appended tasks enter `status.yaml` exclusively via the CLI (`status sync-tasks` reusing `_sync_tasks`); `reconcile` remains the backstop. The pre-ledger buffer is transient SpecOps state drained into the ledger at its constitutional creation seam (tasks stage) — the ledger remains the single source of record. | PASS |
| III. Automated Evidence Collection | Untouched — task close, evidence records, and commit granularity unchanged; converge-appended tasks flow through the normal start/complete loop. | PASS |
| IV. Surgical Agent Behavior via Injected Prompts | This feature is a Principle IV change and follows its rule: every behavior change ships in `src/specops/templates/` (5 new directives, tasks/implement directive edits, workflow.yml) so clients receive it on `extension install`/`update`. Anticipated MINOR constitution amendment during implement (Ledger & Phase Wiring broadened to auxiliary/optional commands — precedent: Features 010–013). | PASS |
| V. Domain Agnosticism | Directives reference only SpecOps' own surfaces (`status sync-tasks`, `record-step`, `consistency`); no stack or client coupling. | PASS |
| VI. Exit Codes as Gates | Preserved: `sync-tasks`/`--check` adopt the frozen 0/1/2 contract and serve as the converge precondition gate; `record-step` pre-ledger changes an exit-2 error path into a success path (additive capability, no successful behavior reshaped; no frozen test pins the old failure — research R4). | PASS |
| Dev Workflow (No Self-Application) | All behavior validated through test fixtures under `tests/`; no `specops` command runs against this repository. | PASS |

**Post-design re-check (after Phase 1)**: PASS — no new dependency, no schema
migration, no frozen-surface reshape; Complexity Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/022-lifecycle-recording-coverage/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── sync-tasks-cli.md
│   ├── record-step-buffer.md
│   └── hooks-and-workflow.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

**SpecOps-Contexts**: n/a — this repository does not self-apply SpecOps (no
context map here; the declaration below is the plain path/action list required
by the Empirical Verification directive).

```text
src/specops/
├── status.py                           (modify)  # cmd_sync_tasks (new); record-step buffering + "converge" step; init-spec buffer drain
├── cli.py                              (modify)  # `status sync-tasks` command (+ --check, --json); record-step help text
└── extension.py                        (modify)  # _HOOK_SPECS + converge-pre/converge/clarify/checklist/analyze entries

src/specops/templates/
├── directives/
│   ├── converge-pre.md                 (create)  # before_converge: fail-closed precondition (sync-tasks --check) or Rule-5 no-op
│   ├── converge.md                     (create)  # after_converge: tag appended tasks → sync-tasks → consistency report (non-blocking)
│   ├── clarify.md                      (create)  # after_clarify: record-step clarify --decision run (Rule-5 no-op)
│   ├── checklist.md                    (create)  # after_checklist: record-step checklist --decision run (Rule-5 no-op)
│   ├── analyze.md                      (create)  # after_analyze: record-step analyze --decision run (Rule-5 no-op)
│   ├── tasks.md                        (modify)  # after init-spec: derive skip for unrecorded clarify/checklist
│   └── implement.md                    (modify)  # session start: derive skip for unrecorded analyze
└── workflows/specops/workflow.yml      (modify)  # record steps back adjacent to gates; converge gate in corrective round; --if-needed contract comment

docs/
└── commands.md                         (modify)  # sync-tasks; record-step buffering + converge; taskstoissues read-only; --if-needed asymmetry

README.md                               (modify)  # lifecycle-coverage description
README.pt-br.md                         (modify)  # equivalent Portuguese update (same PR, full parity)
CHANGELOG.md                            (modify)  # [Unreleased] feature entry

tests/unit/
├── test_status.py                      (modify)  # sync-tasks semantics (append/orphan/completed-preserved/zero-append/determinism)
├── test_cli.py                         (modify)  # sync-tasks + --check exit codes; record-step converge value
├── test_record_step_buffer.py          (create)  # pre-ledger buffering, drain at init-spec, abandoned-run discard, replace semantics
├── test_converge_directive.py          (create)  # directive content + hook registration (pattern: test_lite_directive.py)
├── test_workflow_definition.py         (modify)  # invert #50 ordering test; converge gate + record placement; asymmetry comment presence
├── test_extension.py                   (modify)  # new hook entries in built manifest; hook registry equals documented set
└── test_taskstoissues_readonly.py      (create)  # no taskstoissues hooks in manifest; ledger byte-identical across install/update
```

**Structure Decision**: single existing project (`src/specops/` + `tests/`);
no new modules or directories. New CLI surface lives in the existing
`status.py`/`cli.py` pair; all agent-facing behavior ships as template assets.

## Complexity Tracking

No Constitution Check violations — table intentionally empty.
