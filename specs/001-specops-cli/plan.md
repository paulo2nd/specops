# Implementation Plan: SpecOps CLI — Speckit Companion for Agent-Guided Atomic Development

**Branch**: `main` (no feature branch — pre-1.0 single-branch development) | **Date**: 2026-07-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-specops-cli/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build the `specops-cli` Python package: a pip-installable companion that layers the
agent-guided atomic development methodology on top of GitHub Speckit. Four command
groups (`init`, `status`, `reconcile`, `consistency`) plus one installed agent command
(`/specops.review`). `specops init` prepares a Speckit repository additively
(marker-delimited directive blocks injected into Speckit's plan/implement prompts,
`specops.json`, packaged assets only); the `status` group controls the physical
execution ledger (`status.yaml`) with machine-collected evidence; `reconcile` and
`consistency` are deterministic exit-code gates. Ports the vendored reference scripts
in `.specs/reference/`, adapted to Speckit artifacts (`T001` task ids, `SC-001`
criterion-ID coverage traceability, SPECIFY→DONE phase machine with the
REVIEW→IMPLEMENT(REJECTED) corrective exception).

## Technical Context

**Language/Version**: Python 3.10+ (per existing `pyproject.toml`)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), GitPython (evidence/reconciliation). `rich` currently in `pyproject.toml` will be REMOVED (see Constitution Check).

**Storage**: Files in the client repository — `status.yaml` (per-feature ledger), `specops.json` (client config), `revisions/revision-X.md` (review reports). No database, no network.

**Testing**: pytest (dev dependency only) with temporary Git repositories as fixtures; a fake Speckit layout fixture for init/injection tests.

**Target Platform**: macOS/Linux/Windows terminals (anywhere Python 3.10 + Git run)

**Project Type**: Single project — CLI package with bundled assets

**Performance Goals**: Git-presence failure < 1 s (SC-008); full `specops init` < 1 min (SC-001); all commands offline (SC-009)

**Constraints**: Offline-only; exit codes as contract (0 ok / 1 blocking / 2 unexpected error); additive-only injection with byte-identical restore (SC-010); all operational output in English (FR-014); client prose language-agnostic — structural tokens only (FR-014a)

**Scale/Scope**: 6 CLI commands, 1 agent command template, 2 directive blocks, ~8 modules; prompt targets resolved at runtime from Speckit's integration manifests (2 prompts per installed integration, any of Speckit's 40+ agent layouts)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|---|---|---|
| I. Speckit Extension, Never Replacement | PASS | Init detects `.specify/` + Claude skills layout, injects marker-delimited blocks only, updates in place on re-run, never rewrites Speckit content (FR-006/007, SC-010; contracts/directive-blocks.md) |
| II. Physical State Ledger | PASS | `status` command group is the sole ledger writer; `reconcile` blocks on divergence (FR-008/011; contracts/ledger-schema.md) |
| III. Automated Evidence Collection | PASS | `complete-task --auto` runs `test_command`, harvests `started_commit..HEAD`, records `<CLASS>:<summary>`; manual path requires `--evidence` (FR-009/009a/010) |
| IV. Surgical Agent Behavior via Injected Prompts | PASS | Directives ship as packaged assets injected by init; changes propagate via re-init (FR-006, FR-017) |
| V. Domain Agnosticism | PASS | Client specifics only via `specops.json`; no stack assumptions; language-agnostic parsing via structural tokens (FR-015, FR-014a) |
| VI. Exit Codes as Gates | PASS | 0/1 contract, non-interactive validation commands; init's git-offer is the sole prompt with `--non-interactive` decline default (FR-016) |
| Technical Constraints (deps) | ATTENTION → RESOLVED | `rich` is in `pyproject.toml` but not constitution-sanctioned; Typer works without it. Decision: remove `rich`, use plain `typer.echo`. No new runtime dependencies added |
| Workflow gates (dogfooding) | PASS (manual) | `specops consistency` does not exist yet; this plan was checked manually per constitution's transition rule. Paths below verified empirically via `ls`/`grep` |

**Post-design re-check (after Phase 1)**: PASS — contracts introduce no new dependencies, no Speckit file rewrites, no network; `rich` removal recorded as task input.

## Project Structure

### Documentation (this feature)

```text
specs/001-specops-cli/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── cli-contract.md
│   ├── ledger-schema.md
│   └── directive-blocks.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/specops/
├── __init__.py              (modify) — version metadata
├── cli.py                   (modify) — Typer entrypoint; translate to English, drop rich, wire subcommands
├── speckit.py               (create) — Speckit detection, integration.json + per-agent manifest reading, prompt-target resolution (R2), feature-dir/tasks/SC parsing (structural tokens only)
├── gitops.py                (create) — GitPython helpers: repo presence, branch, commit ranges, diff harvesting
├── config.py                (create) — specops.json load/merge/validate
├── initializer.py           (create) — `specops init`: git check/offer, asset install, marker-block injection (idempotent)
├── status.py                (create) — ledger engine: init-spec, start-task, complete-task, transition-phase, task sync
├── reconcile.py             (create) — ledger↔git history validator
├── consistency.py           (create) — SC-ID coverage + path-suffix empirical validation
└── templates/               (create) — packaged assets (FR-017)
    ├── review.md            (create) — /specops.review agent command
    ├── status.yaml          (create) — ledger scaffold
    ├── specops.json         (create) — client config template
    └── directives/
        ├── plan.md          (create) — block for Speckit's plan prompt
        └── implement.md     (create) — block for Speckit's implement prompt

tests/
├── unit/                    (create) — parsing, config merge, marker grammar, phase machine
└── integration/             (create) — tmp git repo + fake Speckit layout: init idempotency/restore, task loop, gates
```

**Structure Decision**: Single `src/specops/` package (existing layout, verified via
`ls`), matching `objective.md` §2 with two additions: `speckit.py`/`gitops.py`/
`config.py` extracted so `status`/`reconcile`/`consistency` stay thin ports of the
reference scripts, and `templates/` extended with the directive-block and config
assets that FR-017 requires bundled. Tests live at repo root per the plan template's
single-project convention.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No unresolved violations. The one flagged item (`rich` runtime dependency) is
resolved by removal rather than justification — Typer's plain output suffices and the
dependency list returns to the constitution's sanctioned set (Typer, PyYAML,
GitPython).
