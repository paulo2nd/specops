# Implementation Plan: Deterministic Review Gates in the CLI (`specops review`)

**Branch**: `004-review-gates-cli` | **Date**: 2026-07-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-review-gates-cli/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a `specops review` CLI command that runs the deterministic review gates
(reconcile → lint → test → working-tree/effective-diff) in pure Python,
cheapest-first with early stop, read-only on the ledger, exiting 0/1 (2 for
ledger parse errors). Collapse steps 2–4 of the installed
`/specops-review` prompt template into a single "run `specops review`"
instruction. The gates reuse the existing `reconcile`, `config`, and
`gitops` modules; lint/test execution mirrors the `shell=True` captured
subprocess convention already used by `complete-task --auto`
(src/specops/status.py:269). Headless AI dispatch after the gates is out of
scope (documented direction in
[future-headless-dispatch-draft.md](./future-headless-dispatch-draft.md)).

## Technical Context

**Language/Version**: Python ≥ 3.10 (existing `pyproject.toml` floor)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), GitPython (git ops) — no new runtime dependencies

**Storage**: Repository files — `specops.json` (read), `status.yaml` ledger (read-only in this feature)

**Testing**: pytest (unit + integration via Typer runner, existing `tests/conftest.py` fixtures)

**Target Platform**: Cross-platform CLI (macOS/Linux/Windows), same as the rest of SpecOps

**Project Type**: Single-package CLI

**Performance Goals**: Gate overhead (excluding client lint/test commands) negligible — sub-second; total runtime dominated by the client's own `lint_command`/`test_command`

**Constraints**: No interactive prompts; read-only on ledger and worktree; exit-code vocabulary stays {0, 1, 2}; English output; no timeout on client commands (spec Assumption)

**Scale/Scope**: One new CLI command, one new business module, two small helper additions, one template edit, docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Speckit Extension, Never Replacement | PASS — additive CLI command; template change flows through the existing `specops init` install path (`_install_review`); no Speckit file touched, uninstall guarantees preserved. |
| II. Physical State Ledger | PASS — the command reads the ledger (baseline) and never writes it (spec FR-007); ledger mutation stays exclusive to `status` commands. |
| III. Automated Evidence Collection | PASS (untouched) — gates reuse the same machine-collection philosophy; `complete-task` flows unchanged. |
| IV. Surgical Agent Behavior via Injected Prompts | PASS — the Token-Optimized Review directive's gate steps move from prompt prose into the CLI; the change is made in the SpecOps template (`templates/review.md`) so every client receives it on next `specops init`, exactly as the principle requires. |
| V. Domain Agnosticism | PASS — client specifics enter only via `specops.json` (`lint_command`, `test_command`); no tool-specific logic. |
| VI. Exit Codes as Gates | PASS — 0 success / 1 blocking failure, no prompts; `specops review` joins `reconcile` and `consistency` as a composable gate. |
| Technical Constraints | PASS — deps unchanged; new module under `src/specops/`; business module raises `SpecopsError` and never imports Typer (002 errors contract). |

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-review-gates-cli/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/specops/review.py                    (create)  — gate pipeline: run_gates(root) → GateReport; raises SpecopsError on failure
src/specops/shell.py                     (create)  — shared runner for client-configured commands (review gates and complete-task --auto)
src/specops/cli.py                       (modify)  — register `specops review` command through the existing _handle_errors mapper
src/specops/gitops.py                    (modify)  — add dirty_files(repo) helper (git status --porcelain)
src/specops/status.py                    (modify)  — expose a public read-only ledger accessor for the baseline (no mutation paths added)
src/specops/templates/review.md          (modify)  — collapse steps 2–4 into the single `specops review` instruction
tests/unit/test_review.py                (create)  — gate ordering, early stop, skip semantics, truncation, report rendering
tests/integration/test_review_cli.py     (create)  — exit codes / streams through the Typer runner, ledger immutability, template content after init
tests/integration/test_review_asset.py   (modify)  — assert the collapsed gate step in the installed prompt
README.md                                (modify)  — document `specops review` + CI/workflow shell-step example
```

> Note: SpecOps is intentionally NOT self-applied in this repository (no
> `specops.json`, no ledger, no injected blocks) while the tool is still
> being defined — development state is tracked by plain Speckit artifacts.

**Structure Decision**: Single-package layout preserved. Gate logic lives in a
new dedicated business module `src/specops/review.py` (mirrors
`reconcile.py`/`consistency.py`: pure logic, `SpecopsError` on failure, no
Typer imports per the 002 errors contract). `cli.py` only wires the command.
`reconcile.py` and `config.py` are reused as-is (no modification).

## Complexity Tracking

No constitution violations to justify.
