# Implementation Plan: Review Composition in the Workflow

**Branch**: `016-review-composition-workflow` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/016-review-composition-workflow/spec.md`

## Summary

The shipped SpecOps lifecycle workflow (`src/specops/templates/workflows/specops/workflow.yml`, Feature 007) runs a corrective `do-while` whose only in-loop review is the **deterministic** gate `specops review --json --soft`. It never invokes the **semantic** review (`/specops-review`), so a workflow-driven run records no structured findings and the Feature 011 blocking-approval invariant gates an empty set.

This feature composes the semantic review into the loop and makes the loop condition + completion react to unverified blocking findings, using **only** Spec Kit native steps (`command`/`shell`/`if`/`do-while`) and the existing `specops` CLI. The technical approach:

1. Inside the loop, keep `review-soft` (mechanical gate) as the **fail-closed precondition** (FR-002); only when it passes, run a new `command: specops.review` step that reads the diff, records structured findings, verifies fixed ones, and executes the outcome transition it already owns (FR-001, FR-009).
2. Add a read-only `shell: specops handoff report --json` step and extend the do-while condition to re-iterate while the mechanical verdict is `REJECTED` **or** the report's `remaining_blocking` set is non-empty (FR-003) — the findings signal comes from the existing report surface (FR-008), no CLI change.
3. Keep the terminal hard `specops review` gate as the mechanical fail-closed guard; the completion transition (`transition-phase DONE`) already fails closed while any blocking finding is unverified (Feature 011), delivering FR-004/FR-005.
4. Degrade automatically: a run that records no findings has an empty `remaining_blocking`, so completion is decided by the mechanical verdict exactly as before (FR-006); a run where the semantic review **cannot** run fails closed because `command:` steps abort on an unresolvable command (FR-016).

No new Python module, no persisted-schema change, no handoff-CLI change. The deliverable is the edited workflow template, EN/PT docs, the changelog, and structural + integration tests.

## Technical Context

**Language/Version**: Python 3.10+ (repo standard; CLI unchanged here)

**Primary Dependencies**: None new. Consumes Spec Kit's native workflow engine (`command`/`shell`/`if`/`do-while`, `speckit_version >= 0.8.5`) and the existing `specops` CLI surfaces (`review`, `handoff report`, `reconcile`, `status transition-phase`). Testing uses PyYAML to parse the template.

**Storage**: N/A — no new persisted state. Reads existing Ledger v6 `handoff.findings` **indirectly**, only through `specops handoff report --json` (read-only projection).

**Testing**: pytest — `tests/unit/test_workflow_definition.py` (structural assertions over the parsed `workflow.yml`) and `tests/integration/test_workflow_orchestration.py` (ledger/step behavior; engine-parse test skips when Spec Kit is absent). Ruff + mypy at repo thresholds.

**Target Platform**: Any Spec Kit repository with SpecOps installed; offline after install.

**Project Type**: CLI / methodology tooling — the artifact changed is a shipped workflow **definition**, not application code.

**Performance Goals**: N/A (definition change). Preserve token discipline: the cheap mechanical gate runs before the token-expensive semantic review every round (FR-002, Principle IV §18).

**Constraints**: Compose native steps only (Rule 8 / Principle I); no new engine/loop/gate primitive; deterministic and read-only for all inspection steps; the corrective loop stays bounded by the existing `max_iterations` (FR-010); forward-seam transitions stay owned by directives (FR-009).

**Scale/Scope**: One workflow template, ~2 new steps + 1 condition change; ~4 new unit assertions + 1–2 integration checks; EN/PT doc + changelog updates.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** | PASS. Change is additive to a SpecOps-owned template; composes Spec Kit native steps; modifies no integration-owned file. The `command: specops.review` step references the SpecOps-registered command installed by the same `install()` path as the workflow. |
| **II. Physical State Ledger** | PASS. No new ledger state and no hand-edited state. The semantic review's own owned transitions (`DONE`/`IMPLEMENT -r REJECTED`) move the phase; the workflow's existing `open-corrective-round`/`done` steps remain `--if-needed` idempotent-tolerant. |
| **III. Automated Evidence Collection** | PASS. Unchanged; findings/evidence continue to flow through the existing `handoff`/`status` CLI invoked by the review directive. |
| **IV. Surgical Agent Behavior via Injected Prompts** | PASS — directly advances it. The `/specops-review` directive is the always-on baseline reviewer; this feature makes the shipped workflow actually invoke it, with the mechanical gate kept first for token discipline (§18). |
| **V. Domain Agnosticism** | PASS. No stack coupling; behavior enters via existing generic CLI + `specops.json`. |
| **VI. Exit Codes as Gates** | PASS. Mechanical soft gate drives the loop (exit 0, verdict in JSON); terminal hard gate fails closed; the `command:` step fails closed when the review is unavailable (FR-016). |
| **Rule 8 (no reimplementation)** | PASS. No SpecOps engine/loop/gate/resume primitive; only `command`/`shell`/`if`/`do-while` + existing CLI. |

**Result**: PASS, no violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/016-review-composition-workflow/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (step/condition contract; no persisted schema)
├── quickstart.md        # Phase 1 output (validation guide)
├── contracts/
│   └── workflow-corrective-loop.md   # Composed-loop step contract
└── checklists/
    └── requirements.md  # From /speckit-specify + /speckit-clarify
```

### Source Code (repository root)

```text
src/specops/templates/workflows/specops/
└── workflow.yml         # MODIFY: add semantic-review command step + handoff-report
                         #         shell step; extend corrective-loop condition;
                         #         keep terminal hard gate and idempotent done step

tests/
├── unit/
│   └── test_workflow_definition.py       # MODIFY: assert semantic review composed,
│                                         #         ordered after the soft gate, guarded
│                                         #         by mechanical pass; condition reacts
│                                         #         to remaining_blocking; native types only
└── integration/
    └── test_workflow_orchestration.py    # MODIFY: co-installation invariant (review
                                          #         command installed with workflow);
                                          #         no new forward transitions; degrade shape

README.md                # MODIFY: workflow now performs+enforces semantic review; always-on/auto-degrade
README.pt-br.md          # MODIFY: behaviorally-equivalent PT update
CHANGELOG.md             # MODIFY: user-visible behavior note under [Unreleased]
```

**Structure Decision**: This is a **workflow-definition** feature. The single behavioral change lives in the SpecOps-owned template `src/specops/templates/workflows/specops/workflow.yml`; there is no new `src/specops/*.py` module and no persisted-format change. Coverage is delivered by extending the existing workflow structural unit tests and the orchestration integration tests, plus EN/PT docs and the changelog. `specs/**`, `.specify/**`, and `specops.json` are methodology state and excluded from product drift.

## Complexity Tracking

> No constitution violations. No entries required.
