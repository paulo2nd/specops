# Implementation Plan: Native Workflow Orchestration

**Branch**: `007-native-workflow-orchestration` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-native-workflow-orchestration/spec.md`

## Summary

Ship a **SpecOps-owned `specops` workflow definition** that composes Spec Kit's native workflow engine (`specify_cli.workflows`: `command`/`shell`/`gate`/`do-while`/`if`) to run the augmented lifecycle, plus the **ledger reconciliation** and **CLI outcome contract** that keep the SpecOps ledger authoritative. SpecOps builds no engine, resume, gate, or loop — those are Spec Kit primitives (verified in `specify_cli/workflows/engine.py`). The work is: (1) a new workflow asset delivered additively by `specops extension install` into `.specify/workflows/specops/`; (2) a stable outcome contract (formalized exit codes 0/1/2 + machine-readable `--json`) so native `do-while`/`if`/gate conditions branch on the SpecOps review verdict; (3) reconciliation extended to align ledger↔workflow/repo state as a fail-closed precondition of every state-changing step, reusing Feature 006's `rebaseline` as the only remedy; (4) an additive, migration-safe ledger `workflow` block recording the run correlation and optional-step skip decisions.

## Technical Context

**Language/Version**: Python ≥ 3.10 (`pyproject.toml requires-python = ">=3.10"`, mypy/ruff target `py310`).

**Primary Dependencies**: Typer (CLI), PyYAML (ledger/workflow YAML), GitPython (git identity/evidence). **Host runtime (not a SpecOps dependency)**: Spec Kit's `specify_cli.workflows` engine, which provides the resumable orchestration, `gate`, `do-while`, and branching primitives this feature composes.

**Storage**: Files only — the per-feature ledger `specs/*/status.yaml` (YAML), the shipped workflow definition `.specify/workflows/specops/workflow.yml` (YAML), and Spec Kit's workflow registry `.specify/workflows/workflow-registry.json` (JSON, Spec Kit-owned; SpecOps writes only its own entry).

**Testing**: pytest — `tests/unit/` and `tests/integration/` (existing layout). New suites validate the workflow definition, the outcome contract, reconciliation, extension registration/prune, and ledger migration. Per the constitution, SpecOps gate behavior is validated **only** through test fixtures — never by running `specops`/the workflow against this repository.

**Target Platform**: Cross-platform CLI + Spec Kit extension asset; **offline after install** (no network to orchestrate).

**Project Type**: Single-project Python CLI + Spec Kit extension (the `specops` workflow is a delivered asset, not a service).

**Performance Goals**: Reconciliation runs as a precondition only of state-changing steps (not read-only ones), keeping per-step overhead to a single git-reachability check plus a ledger read; no measurable regression to lifecycle latency.

**Constraints**: Fail-closed on ambiguous identity/divergence and on any non-`APPROVED` terminal verdict; additive-only (Constitution Principle I — never modify Spec Kit-owned assets, including the bundled `speckit` workflow); deterministic exit codes (Principle VI); domain-agnostic (Principle V).

**Scale/Scope**: One active feature per ledger; strictly sequential steps (no fan-out, FR-026); corrective loop bounded by the native `do-while` `max_iterations`.

## Constitution Check

*GATE: evaluated pre-Phase 0 and re-checked post-Phase 1. Result: PASS (no violations).*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** (NON-NEGOTIABLE) | **PASS.** The `specops` workflow is additive and SpecOps-owned; `extension install` writes only its own registry entry and never touches the bundled `speckit` workflow (FR-001a). Removal prunes only SpecOps-owned entries, mirroring the existing command-prune logic in `extension.py`. |
| **II. Physical State Ledger (Repo-as-State)** | **PASS.** Every phase/task/review-cycle transition is a `specops status …` CLI step; the workflow engine never writes the ledger (FR-008/009). The additive `workflow` block is manipulated exclusively by CLI. `reconcile` remains the git-verifiable gate (extended, not weakened). |
| **III. Automated Evidence Collection** | **PASS.** Unchanged: the loop reuses `specops status complete-task --auto` and the existing review-cycle/evidence representation (FR-017/027). No evidence-format change (deferred to Feature 012). |
| **IV. Surgical Agent Behavior via Injected Prompts** | **PASS (coordination settled — analyze C1).** The injected lifecycle-hook directives remain the **sole owner** of forward-seam ledger creation and phase transitions; they fire on the same lifecycle commands the workflow runs. The `specops` workflow does **not** duplicate them — it owns only the corrective REVIEW→IMPLEMENT round and additive `skipped_steps` records, and every workflow-issued `specops status` call is idempotent-tolerant, so no double transition can occur. The injected directives are delivered unchanged by the same `extension install`. |
| **V. Domain Agnosticism** | **PASS.** Workflow steps and the outcome contract are stack-neutral; all client behavior stays in `specops.json` (`test_command`, `lint_command`). |
| **VI. Exit Codes as Gates** | **PASS (strengthened).** The outcome contract formalizes the existing `errors.py` codes (0 ok / 1 blocking-gate-or-rejection / 2 infra-or-data error) and adds machine-readable `--json`, so native gate/`do-while`/`if` steps compose the SpecOps gates deterministically. |

**Development-workflow compliance**: This feature is built with plain Spec Kit; no `specops.json`/`status.yaml`/`/specops-review` is installed in *this* repo, and the workflow is exercised only via `tests/` fixtures (Constitution §Development Workflow & Quality Gates).

## Project Structure

### Documentation (this feature)

```text
specs/007-native-workflow-orchestration/
├── plan.md              # This file
├── research.md          # Phase 0 output — design decisions R1–R7
├── data-model.md        # Phase 1 output — entities & ledger extension
├── quickstart.md        # Phase 1 output — install + run + validation
├── contracts/           # Phase 1 output
│   ├── cli-outcome-contract.md      # exit codes + --json schema (review/reconcile/consistency)
│   ├── specops-workflow.md          # the `specops` workflow.yml step graph
│   └── extension-registration.md    # what install/remove write to .specify/workflows/
├── checklists/
│   ├── requirements.md  # spec-quality checklist (from /speckit-specify)
│   └── orchestration.md # requirements-quality checklist (from /speckit-checklist)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Paths verified against the current worktree; action suffixes per Constitution Principle IV
(Empirical Verification). `specops consistency` (a delivered capability) validates these against
the worktree in client repos and in this feature's own tests — it is not run against this repo.

```text
src/specops/
├── templates/
│   └── workflows/specops/workflow.yml   (create)  # the shipped `specops` workflow definition
├── extension.py                          (modify)  # register/prune the workflow into .specify/workflows/ + registry
├── review.py                             (modify)  # add machine-readable verdict output (--json path)
├── reconcile.py                          (modify)  # add workflow/ledger-state reconciliation dimension + JSON
├── cli.py                                (modify)  # --json options; wire outcome-contract exit codes
├── ledger.py                             (modify)  # additive `workflow` block {skipped_steps}
├── status.py                             (modify)  # CLI seam: record optional-step skips; idempotent-tolerant transitions (C1)
└── migration.py                          (modify)  # forward-migrate: back-fill empty `workflow` block

tests/
├── unit/
│   ├── test_workflow_definition.py       (create)  # validate the shipped workflow.yml against Spec Kit's step schema
│   ├── test_outcome_contract.py          (create)  # exit codes 0/1/2 + JSON shape per command
│   ├── test_reconcile.py                 (modify)  # workflow-state divergence dimension
│   ├── test_review.py                    (modify)  # JSON verdict emission
│   ├── test_ledger.py / test_migration.py(modify)  # workflow block + back-fill
│   └── test_extension.py                 (modify)  # workflow registration/prune idempotency
└── integration/
    ├── test_workflow_orchestration.py    (create)  # end-to-end: readiness gate, corrective loop, terminal gate, resume/reconcile, failure classes
    └── test_extension_lifecycle.py       (modify)  # install/update/remove now include the workflow asset
```

**Structure Decision**: Single-project layout (existing). The only structural addition is
`src/specops/templates/workflows/specops/` holding the shipped workflow definition; everything
else is additive edits to existing modules. The workflow *executes* under Spec Kit's engine, so
no orchestration runtime is added to SpecOps.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.

## Phase 0 — Research

See [research.md](./research.md). Decisions R1 (workflow delivery via the extension), R2 (outcome
contract: exit codes + `--json`), R3 (reconciliation dimension + `rebaseline` remedy), R4 (corrective
loop + terminal deterministic gate), R5 (human skip gate), R6 (step wiring & state ownership),
R7 (additive ledger `workflow` block + migration). No `NEEDS CLARIFICATION` remain — the three
open spec decisions were resolved in `/speckit-clarify` (packaging, skip control, divergence remedy)
and two more in `/speckit-checklist` (reconcile cadence, terminal-gate nature).

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the workflow definition, the outcome contract, the additive
  ledger `workflow` block, and the reconciliation report; reuses Feature 006 entities (review cycle,
  `workflow_lane`, `active_artifact`, revision, recovery).
- [contracts/](./contracts/) — the CLI outcome contract, the `specops` workflow step graph, and the
  extension registration/prune contract.
- [quickstart.md](./quickstart.md) — install → `specify workflow run specops` → validate every SC.

**Agent context update**: no repository agent-context file is maintained for SpecOps (development is
plain Spec Kit); this step is a no-op here and recorded for traceability.
