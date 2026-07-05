# Implementation Plan: CLI Hardening & Developer Experience

**Branch**: `main` (no feature branch — pre-1.0 single-branch development) | **Date**: 2026-07-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-cli-hardening-dx/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Harden the existing `specops-cli` package and its development workflow. Five work
streams, in priority order: (1) fix the review approval flow — apply a supplied
`-r` result to the open review cycle **before** the DONE entry gate, restrict
results to APPROVED/REJECTED, and correct the packaged review directive that
currently instructs an invalid `transition-phase REVIEW -r ...` call; (2) add a
read-only `specops status show` ledger summary and a root `--version` option;
(3) make ledger writes crash-safe via write-temp-then-rename and enforce the
evidence grammar strictly (single validation path, non-empty summaries);
(4) refactor the business modules to raise a structured `SpecopsError` hierarchy
instead of terminating the process, with the CLI layer as the single exit-code
mapper, plus removal of all identified dead code and numeric feature-dir
ordering; (5) add development tooling — Ruff, mypy, pytest-cov with a blocking
85% threshold, and a GitHub Actions pipeline on Python 3.10 + latest stable.
No runtime dependency changes; no Speckit file rewrites.

## Technical Context

**Language/Version**: Python 3.10+ (existing `pyproject.toml` floor; CI adds latest stable — 3.14)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), GitPython (evidence) — unchanged. New **dev-only** dependencies: ruff, mypy, pytest-cov (+ types-PyYAML for stubs).

**Storage**: Files in the client repository — `status.yaml` (per-feature ledger, now written atomically), `specops.json`. No database, no network.

**Testing**: pytest with existing tmp-git-repo fixtures; new unit tests for the transition fix, show rendering, atomic writes, evidence grammar, numeric ordering; existing suite adapted to assert on raised errors instead of `SystemExit` where unit-level.

**Target Platform**: macOS/Linux/Windows terminals (anywhere Python 3.10 + Git run)

**Project Type**: Single project — CLI package with bundled assets

**Performance Goals**: `status show` and `--version` complete in < 1 s (SC-002, SC-003); no regression on existing < 1 s git-presence failure

**Constraints**: Exit-code contract preserved exactly (0 ok / 1 blocking / 2 unexpected); atomic ledger persistence (SC-004); all CLI output in English (FR-014); runtime dependency set frozen by constitution

**Scale/Scope**: ~9 existing modules touched, 1 new module, 1 packaged template corrected, 1 CI workflow, ~15 new/adapted test groups; coverage gate ≥ 85% statements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|---|---|---|
| I. Speckit Extension, Never Replacement | PASS | No Speckit files touched; changes are internal to the SpecOps package and its packaged assets (FR-001..FR-013) |
| II. Physical State Ledger | PASS | Feature *strengthens* the principle: the P1 fix removes the only flow that forced hand-editing `status.yaml`; atomic writes protect ledger integrity (FR-001, FR-006) |
| III. Automated Evidence Collection | PASS | Evidence grammar enforced strictly by a single validation path; `--auto` harvesting unchanged (FR-007) |
| IV. Surgical Agent Behavior via Injected Prompts | PASS | The packaged `review.md` Step 6 instructs an invalid transition (`transition-phase REVIEW -r ...` while already in REVIEW); corrected in the packaged template so client repos receive it on next `specops init` (FR-001; contracts/cli-interface.md) |
| V. Domain Agnosticism | PASS | No client-stack coupling added; tooling (Ruff/mypy/CI) applies to SpecOps development only, not to clients |
| VI. Exit Codes as Gates | PASS | Exit-code semantics preserved and centralized in one CLI-layer mapper; `status show` is read-only with 0/1 contract (FR-009, FR-010) |
| Technical Constraints (deps) | PASS | Runtime deps unchanged (Typer, PyYAML, GitPython). ruff/mypy/pytest-cov/types-PyYAML are dev-extra only — not runtime dependencies, no justification required |
| Workflow gates (dogfooding) | PASS | `specops consistency` now exists and was run against this plan (path-suffix declarations below verified against the worktree); `.github/workflows/` pre-created so the `(create)` parent rule is verifiable |

**Post-design re-check (after Phase 1)**: PASS — contracts introduce no new runtime
dependencies, no Speckit interactions, no network; the error-hierarchy design keeps
Typer usage confined to `cli.py` and `initializer.py` (the one interactive command).

## Project Structure

### Documentation (this feature)

```text
specs/002-cli-hardening-dx/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── cli-interface.md # Changed/new command surface (transition-phase, show, --version)
│   └── errors.md        # SpecopsError hierarchy ↔ exit-code mapping
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Full paths from repository root, one declaration per line:

- `src/specops/errors.py` (create) — `SpecopsError` base (message, exit code 1) + `LedgerParseError` (exit 2) + `ConfigError` re-parented; the single failure vocabulary for business modules
- `src/specops/status.py` (modify) — apply `-r` result before the DONE gate; restrict results to APPROVED/REJECTED; atomic `_save_ledger`; strict single-path evidence validation (drop dead `_EVIDENCE_RE` or make it the one path); new `cmd_show` renderer; raise `SpecopsError` instead of `sys.exit`; drop duplicate `import sys` and unused `_ok`
- `src/specops/cli.py` (modify) — root `--version` eager option via `importlib.metadata`; `status show` subcommand; single try/except boundary mapping `SpecopsError` → stderr + `typer.Exit`; remove unused duplicate exit helpers
- `src/specops/reconcile.py` (modify) — return findings, raise `SpecopsError` on blocking preconditions; no `sys.exit`/`typer` in module
- `src/specops/consistency.py` (modify) — same error refactor; hoist loop-level imports to module top; use public parsing helpers from `speckit.py` instead of the private regex; fix `:0` line reporting for uncovered SCs (report against the spec's SC definition line)
- `src/specops/speckit.py` (modify) — numeric-prefix ordering in `resolve_feature_dir` fallback; expose a public action-suffix parsing helper (path + action extraction) consumed by `consistency.py`
- `src/specops/gitops.py` (modify) — remove unused `end`/`start` computations in `commits_in_range`
- `src/specops/initializer.py` (modify) — remove unused `command_name`; no behavioral change
- `src/specops/config.py` (modify) — `ConfigError` inherits from `SpecopsError`
- `src/specops/__init__.py` (modify) — version sourced from installed metadata (single source of truth in `pyproject.toml`)
- `src/specops/templates/review.md` (modify) — Step 6: replace invalid `transition-phase REVIEW -r <...>` with the two real outcomes (`DONE -r APPROVED` / `IMPLEMENT -r REJECTED`)
- `pyproject.toml` (modify) — dev extras (ruff, mypy, pytest-cov, types-PyYAML); `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` with `--cov` + `--cov-fail-under=85`
- `.github/workflows/ci.yml` (create) — lint + type + test jobs on push/PR, Python matrix 3.10 and 3.14
- `README.md` (modify) — document `status show`, `--version`, closed result vocabulary, local gate commands
- `tests/conftest.py` (modify) — shared fixture updates for error-based assertions
- `tests/unit/test_status.py` (modify) — transition-fix cases, atomic-write interruption test, evidence grammar matrix, error-raise assertions
- `tests/unit/test_speckit.py` (modify) — numeric ordering cases (9 vs 10), public suffix-helper tests
- `tests/unit/test_reconcile.py` (modify) — error-based assertions
- `tests/unit/test_consistency.py` (modify) — error-based assertions, SC line-number reporting
- `tests/unit/test_show.py` (create) — `status show` rendering: populated ledger, legacy ledger without `review_cycles`, counts
- `tests/integration/test_ledger.py` (modify) — end-to-end lifecycle including `DONE -r APPROVED` via CLI only (SC-001)
- `tests/integration/test_cli_surface.py` (create) — `--version` inside/outside git repo; exit-code contract regression sweep across commands

**Structure Decision**: Keep the existing single `src/specops/` package layout
(verified against the worktree). One new module (`errors.py`) so failure semantics
live in one import-cycle-free place; everything else is in-place modification.
`.github/workflows/` is a new top-level directory holding only the CI pipeline.
Tests keep the existing `tests/unit` + `tests/integration` split; two new test
files cover the two genuinely new surfaces (`show`, CLI-level contract sweep).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The only dependency additions are development extras (linter, type
checker, coverage plugin, type stubs), which the constitution's runtime-dependency
constraint does not govern; the runtime set remains Typer + PyYAML + GitPython.
