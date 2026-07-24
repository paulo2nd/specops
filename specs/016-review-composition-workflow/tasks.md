---

description: "Task list for Feature 016 — Review Composition in the Workflow"
---

# Tasks: Review Composition in the Workflow

**Input**: Design documents from `specs/016-review-composition-workflow/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/workflow-corrective-loop.md, quickstart.md

**Tests**: Per the Constitution task gate, every task closes with passing automated tests. Because the composed `command:` steps need a live agent (spec Assumptions), acceptance is delivered by **structural** unit tests over the parsed `workflow.yml` and **integration** tests over install + ledger effects — not a CI end-to-end run. Every task carries one or more `[SC-xxx]` tags (roadmap §4).

**Organization**: Grouped by user story. The single behavioral artifact is `src/specops/templates/workflows/specops/workflow.yml`; because all stories edit that one file, its edits are **sequential** (never `[P]` with each other), while per-story tests and docs are independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 from spec.md
- Exact file paths are included in each description

## Path Conventions

- Workflow template: `src/specops/templates/workflows/specops/workflow.yml`
- Unit tests: `tests/unit/test_workflow_definition.py`
- Integration tests: `tests/integration/test_workflow_orchestration.py`
- Docs: `README.md`, `README.pt-br.md`, `CHANGELOG.md`
- Run tooling under `conda run -n specops …` (repo convention)

---

## Phase 1: Setup (Shared Baseline)

**Purpose**: Establish a green baseline and capture the current loop structure before editing.

- [X] T001 Run `conda run -n specops pytest tests/unit/test_workflow_definition.py tests/integration/test_workflow_orchestration.py -q` and confirm all pass; record the current corrective-loop step ids/order in `src/specops/templates/workflows/specops/workflow.yml` (`reconcile-pre-impl → implement → review-soft → corrective-round`, terminal `terminal-gate → done`) as the modification baseline. [SC-006]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None beyond Setup. The behavioral change is a single atomic edit to `workflow.yml` applied incrementally within the story phases below; there is no separate foundational code layer.

**⚠️ Sequencing note**: US1's edit (review step + guard) must land before US2's edit (report step + condition) because both modify the same corrective-loop body. US3 and US4 are primarily assertion/test stories over the emergent behavior of those two edits.

**Checkpoint**: Baseline green → begin User Story 1.

---

## Phase 3: User Story 1 - A workflow-driven run performs the actual code review (Priority: P1) 🎯 MVP

**Goal**: The corrective loop invokes the semantic review (`command: specops.review`) so a workflow-driven run records structured findings, guarded so it runs only when the mechanical gate passes.

**Independent Test**: Parse `workflow.yml` and confirm the loop body contains a `command: specops.review` step, guarded by the mechanical-pass condition and ordered after `review-soft`; only native step types are used.

### Tests for User Story 1 ⚠️

- [X] T002 [US1] Add unit assertions in `tests/unit/test_workflow_definition.py`: the corrective-loop body contains a `command: specops.review` step wrapped in a `type: if` guard on `review-soft.output.data.verdict != 'REJECTED'`, positioned after `review-soft`; extend `test_all_steps_are_native_types` and `test_no_duplicate_step_ids` to cover the new steps. [SC-001][SC-005]

### Implementation for User Story 1

- [X] T003 [US1] Edit `src/specops/templates/workflows/specops/workflow.yml`: inside `corrective-loop.steps`, after `review-soft`, add a `type: if` step `semantic-review-round` (condition `{{ steps.review-soft.output.data.verdict != 'REJECTED' }}`) whose `then` contains `semantic-review` — a hard `command: specops.review` step with `integration: "{{ inputs.integration }}"`. Do not wrap it in any error-tolerance. [SC-001][SC-005]

**Checkpoint**: The workflow drives the semantic review after a passing mechanical gate; T002 passes.

---

## Phase 4: User Story 2 - An unverified blocking finding cannot fall through to completion (Priority: P1)

**Goal**: The loop condition and completion react to unverified blocking findings via the existing `handoff report` surface; the terminal gate stays fail-closed.

**Independent Test**: `corrective-loop.condition` references both `REJECTED` and `remaining_blocking`; the terminal hard `specops review` gate and idempotent `done` remain; `max_iterations` unchanged; the workflow yaml issues no new forward transitions.

### Tests for User Story 2 ⚠️

- [X] T004 [US2] Add unit assertions in `tests/unit/test_workflow_definition.py`: `corrective-loop.condition` contains both `REJECTED` and `remaining_blocking`; a `handoff-report` step runs `specops handoff report --json` with `output_format: json`; `terminal-gate.run == "specops review"`; order `corrective-loop < terminal-gate < done`; `corrective-loop.max_iterations` equals the Feature-007 value. [SC-002][SC-003]
- [X] T005 [US2] Extend `tests/integration/test_workflow_orchestration.py::test_workflow_has_no_forward_transition_or_initspec_steps` to confirm the only workflow-issued transition remains the corrective `IMPLEMENT -r REJECTED` (the `semantic-review` command issues its owned transitions at runtime, not in the yaml), asserting FR-009. [SC-002]
- [X] T018 [US2] Add an integration test in `tests/integration/test_workflow_orchestration.py` that evidences the terminal fail-closed guarantee in CI (no live agent): in a fixture repo with an open review cycle, record one unverified blocking finding (`specops handoff finding add --severity blocking …`), assert `specops status transition-phase DONE -r APPROVED` exits non-zero and the ledger phase does **not** become `DONE`; then `specops handoff finding verify <id>` and assert the same transition now succeeds. This is the CI evidence for SC-002/FR-004/FR-005 (the `command:`-driven halt itself stays manual, quickstart Scenario B). [SC-002]
- [X] T019 [US2] Add an integration test in `tests/integration/test_workflow_orchestration.py` that the findings-aware condition input is re-derived from **persisted** ledger state (FR-011, resumability): with an unverified blocking finding present, invoke `specops handoff report --json` from a fresh process/root (simulating `specify workflow resume`) and assert `data.remaining_blocking` is non-empty and byte-identical to a prior invocation — proving the loop condition reads persisted state, not in-memory step context. [SC-002][SC-006]

### Implementation for User Story 2

- [X] T006 [US2] Edit `src/specops/templates/workflows/specops/workflow.yml`: after `semantic-review-round`, add a read-only `handoff-report` step (`shell: specops handoff report --json`, `output_format: json`); extend `corrective-loop.condition` to `{{ steps.review-soft.output.data.verdict == 'REJECTED' or steps.handoff-report.output.data.remaining_blocking }}`. Leave `open-corrective-round` guarded on the mechanical `REJECTED`, and leave `terminal-gate`/`done` unchanged. [SC-002][SC-003]

**Checkpoint**: The loop re-iterates on unverified blocking findings; completion stays fail-closed via the existing `transition-phase DONE` (evidenced by T018) and the condition survives resume (T019); T004/T005 pass.

---

## Phase 5: User Story 3 - Repositories that record no findings still complete (Priority: P2)

**Goal**: A run that records no findings degrades automatically to deterministic-only completion, with no configuration flag gating enforcement.

**Independent Test**: With an empty `remaining_blocking` (no findings / legacy repo), the read-only report + terminal gate leave the ledger unmutated and completion is decided by the mechanical verdict; no config field disables enforcement.

### Tests for User Story 3 ⚠️

- [X] T007 [US3] Add an integration test in `tests/integration/test_workflow_orchestration.py`: in a fixture repo with no handoff findings, `specops handoff report --json` returns `data.remaining_blocking == []` and running the read-only gates (`review --json`, `handoff report --json`) does not mutate `status.yaml` — proving the auto-degrade path leaves completion to the mechanical verdict. [SC-004]
- [X] T008 [US3] Add a unit assertion in `tests/unit/test_workflow_definition.py` that no step gates the `semantic-review` or the loop on any configuration/`inputs` flag (only on `review-soft` verdict / `remaining_blocking`), encoding FR-015 (no opt-in/opt-out). [SC-009]

**Checkpoint**: Zero-finding and legacy runs complete unchanged; T007/T008 pass.

---

## Phase 6: User Story 4 - The mechanical gate stays a fail-closed precondition (Priority: P2)

**Goal**: The mechanical gate is the ordered precondition (review skipped on mechanical reject), and an un-runnable semantic review fails closed.

**Independent Test**: The `semantic-review` guard is exactly `verdict != 'REJECTED'`; installing SpecOps writes the `/specops-review` command wherever it writes the workflow (so the hard command step can never silently degrade).

### Tests for User Story 4 ⚠️

- [X] T009 [US4] Add a unit assertion in `tests/unit/test_workflow_definition.py` that the `semantic-review-round` guard condition is `review-soft.output.data.verdict != 'REJECTED'` and that `review-soft` precedes `semantic-review` in the loop body (mechanical-first, FR-002/Story 4). [SC-005]
- [X] T010 [US4] Add an integration test in `tests/integration/test_workflow_orchestration.py` asserting the co-installation invariant: after `extension.install()`, both `.specify/workflows/specops/workflow.yml` and the per-integration `/specops-review` command file exist — so the hard `command: specops.review` step fails closed (aborts) rather than degrading if the review is ever unavailable (FR-016). [SC-008]

**Checkpoint**: Mechanical-first ordering and fail-closed-on-unavailable are both asserted; T009/T010 pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, the in-file rationale comment, and full-suite validation.

- [X] T011 [P] Update `README.md`: the shipped workflow now performs and enforces the semantic review (not only the deterministic gates); enforcement is always-on with automatic degrade when a review records no findings; no persisted-format or CLI change. [SC-007]
- [X] T012 [P] Update `README.pt-br.md` with the behaviorally-equivalent Portuguese text for the same section. [SC-007]
- [X] T013 [P] Add a `[Unreleased]` entry to `CHANGELOG.md` describing the user-visible behavior (workflow performs+enforces review; always-on/auto-degrade; fail-closed when review unavailable) and noting no migration is required. [SC-007]
- [X] T014 Update the corrective-loop rationale comment block in `src/specops/templates/workflows/specops/workflow.yml` to describe the composed semantic review, the mechanical-first guard, and the findings-aware condition, preserving the existing non-CI-reproducible verification caveat. [SC-001]
- [X] T015 Run full gates: `conda run -n specops ruff check src tests`, `conda run -n specops mypy src`, `conda run -n specops pytest -q`; confirm `test_definition_parses_in_real_speckit_engine` passes or skips (engine absent) and there are no regressions. [SC-006]
- [X] T016 Walk `quickstart.md` CI-reproducible checks (steps 1–3) against the edited template and confirm the structural + co-installation assertions match the delivered `workflow.yml`. [SC-006]
- [ ] T017 In the feature's own PR commit, flip the ROADMAP.md row 016 from `ACTIVE` to `MERGED` (repo policy: MERGED flip lands inside the feature PR, not a separate chore PR). [SC-007]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately.
- **Foundational (Phase 2)**: no code; only the sequencing note.
- **User Stories (Phase 3–6)**: all depend on Setup. **US2 (T006) depends on US1 (T003)** because both edit the same `corrective-loop` body. US3 and US4 are assertion/test stories over the emergent behavior of T003 + T006, so their tests (T007–T010) depend on those two edits.
- **Polish (Phase 7)**: after the story phases; T015/T016 depend on all edits; T017 is the PR/completion commit.

### Single-file coupling (important)

`T003` and `T006` and `T014` all edit `workflow.yml` → **sequential, never `[P]` together**. `T002/T004/T008/T009` edit `tests/unit/test_workflow_definition.py` → sequential with each other. `T005/T007/T010/T018/T019` edit `tests/integration/test_workflow_orchestration.py` → sequential with each other. `T018` and `T019` assert behavior that exists independently of the workflow edits (Feature 011 `transition-phase DONE` fail-closed and the read-only `handoff report`), so they can be written any time after Setup, but are grouped in US2 as the enforcement evidence.

### Parallel Opportunities

- **Docs**: `T011` (README.md), `T012` (README.pt-br.md), `T013` (CHANGELOG.md) touch different files → `[P]` together.
- Everything else is serialized by the two shared source files above.

---

## Parallel Example: Phase 7 docs

```bash
# Different files, no interdependency — run together:
Task: "Update README.md workflow review-and-enforce section"
Task: "Update README.pt-br.md equivalent section"
Task: "Add CHANGELOG.md [Unreleased] entry"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup (T001).
2. Phase 3 US1 (T002–T003): the workflow drives the semantic review after a passing mechanical gate.
3. **STOP and VALIDATE**: T002 green; the review is composed. This is the minimum that closes the core gap.

### Incremental Delivery

1. US1 → the review runs (findings get recorded).
2. US2 → the loop + completion enforce unverified blocking findings.
3. US3 → confirm safe degrade for zero-finding/legacy runs.
4. US4 → confirm mechanical-first ordering and fail-closed-on-unavailable.
5. Polish → docs, changelog, in-file rationale, full gates, roadmap flip.

### Commit granularity

One commit per user story (repo convention): commit after each story's tests+edit pass, and a final polish commit. Never one monolith.

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- Acceptance for the live `command:` behavior (Scenarios A–E in `quickstart.md`) is **manual** via `specify workflow run specops`; CI covers the structural + install + read-only-idempotency layers.
- No persisted-format change, no `specops handoff`/CLI change, no new engine/loop/gate primitive (Rule 8) — if any task appears to require one, stop and re-check the plan.
- Do not hand-edit `status.yaml` or ledger state; this feature adds none.
