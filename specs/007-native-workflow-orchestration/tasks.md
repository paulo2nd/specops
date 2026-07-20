---

description: "Task list for Feature 007 — Native Workflow Orchestration"
---

# Tasks: Native Workflow Orchestration

**Input**: Design documents from `specs/007-native-workflow-orchestration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: Mandatory per Constitution (Development Workflow & Quality Gates, task gate) — every task is closed only with passing automated tests; test tasks precede implementation within each story.

**SC tags**: Every task carries one or more `[SC-xxx]` tags (ROADMAP protocol §4). Coverage map at the end.

**Organization**: Grouped by user story for independent implementation and testing. The single workflow asset `src/specops/templates/workflows/specops/workflow.yml` is built incrementally (US1 happy-path → US2 reconcile preconditions → US3 loop/terminal gate → US4 branch wiring); tasks editing it are therefore **not** cross-story parallel.

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 (user-story phases only)
- Exact file paths included; all paths relative to repo root

## Path Conventions

Single project: `src/specops/`, `tests/unit/`, `tests/integration/` (existing layout).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding and test infrastructure for driving Spec Kit workflows.

- [x] T001 Create the workflow asset package dir `src/specops/templates/workflows/specops/` with a placeholder `workflow.yml` (header + empty `steps`) committed as a SpecOps-owned asset [SC-001][SC-002]
- [x] T002 [P] Workflow test infrastructure: a `specify workflow info` subprocess smoke test (skipped when Spec Kit is absent — `specify_cli` is not importable in the miniconda test env) plus direct CLI-step drivers against a real ledger, in `tests/integration/test_workflow_orchestration.py` [SC-001]
- [x] T003 [P] Add a Spec Kit-initialized sample client-repo fixture (with `specops.json`, an integration, a bundled `speckit` workflow) under `tests/integration/` for orchestration tests [SC-001]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ledger extension + the shared outcome-contract primitive that every story consumes.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [x] T004 Add the additive `workflow` block `{skipped_steps[]}` to the ledger via `ensure_workflow_block` + `migrate_to_current` back-fill (no `run_id`; reconciliation uses Feature 006 identity) in `src/specops/ledger.py` [SC-004][SC-007]
- [x] T005 Back-fill the `workflow` block on the write path (an **additive within-v2 field**, normalized in `_load_for_write`, not a schema bump — the field carries no invariants and old readers ignore it, so a version bump forcing every v2 ledger to re-migrate would be disproportionate) in `src/specops/status.py` + `src/specops/templates/status.yaml` [SC-004]
- [x] T006 [P] Back-fill tests (v1 migration produces the block; a v2 ledger gains it on a state change without re-migrating; ensure/idempotency/shape-repair) in `tests/unit/test_ledger.py` and `tests/integration/test_ledger_migration.py` [SC-004]
- [x] T007 Add the shared outcome-contract primitive (exit-code constants 0/1/2 + JSON emitter matching `contracts/cli-outcome-contract.md`) in `src/specops/errors.py` (+ a small helper module/function) [SC-006]
- [x] T008 [P] Unit tests for the outcome-contract primitive (exit_code↔class↔outcome consistency, G1) in `tests/unit/test_outcome_contract.py` [SC-006]

**Checkpoint**: Ledger + outcome contract ready — user stories can begin.

---

## Phase 3: User Story 1 — Install and run the augmented lifecycle (Priority: P1) 🎯 MVP

**Goal**: The additive `specops` workflow installs and runs the lifecycle with the enforced human readiness gate and explicit, ledger-recorded optional-step skips.

**Independent Test**: `specops extension install` → `specify workflow list` shows `specops` with the bundled `speckit` untouched; `specify workflow run specops` pauses at the readiness gate before tasks and generates tasks only after approval; a "skip" choice at an optional gate is recorded in `status.yaml`'s `workflow.skipped_steps`.

### Tests for User Story 1 (write first; must fail before implementation) ⚠️

- [x] T009 [P] [US1] Unit test: validate the shipped `workflow.yml` against Spec Kit `validate_workflow`, assert native-only step types, the readiness-gate position between plan and tasks, and the absence of any `fan-out` step (C1–C4, FR-026) in `tests/unit/test_workflow_definition.py` [SC-002][SC-003]
- [x] T010 [P] [US1] Integration test: `install`→`list` shows `specops`, foreign/bundled registry entries and `.specify/workflows/speckit/*` preserved byte-for-byte; `remove` prunes only `specops` (E1–E4) in `tests/integration/test_extension_lifecycle.py` [SC-001]
- [x] T011 [P] [US1] Integration coverage (a full agent-driven run is not CI-reproducible — command steps need a live integration/LLM and gates need a TTY): the definition parses in Spec Kit's engine (`specify workflow info`); the workflow issues no forward transition/init-spec steps (C1); skip decisions land in the ledger; the DONE transition is idempotent when a directive already advanced the ledger — in `tests/integration/test_workflow_orchestration.py` [SC-001][SC-003][SC-007]

### Implementation for User Story 1

- [x] T012 [US1] Author the happy-path `specops` workflow (specify → clarify/checklist skip-gates → plan → human readiness `gate` → tasks → analyze skip-gate → implement → `specops review` → done). Do **not** add forward-seam `transition-phase`/`init-spec` steps — those are owned by the injected Principle IV directives that fire on the lifecycle commands (analyze C1). In `src/specops/templates/workflows/specops/workflow.yml` [SC-001][SC-003]
- [x] T013 [US1] Add a `specops status` seam to record an optional-step run/skip decision into ledger `workflow.skipped_steps` in `src/specops/status.py` and wire it in `src/specops/cli.py` [SC-001]
- [x] T014 [US1] Make the workflow-owned `specops status` calls (corrective round, final DONE, skip records) idempotent-tolerant — no-op-and-continue when the ledger is already in the target state — so they never double-issue a Principle IV directive transition (analyze C1), in `src/specops/status.py` and `src/specops/cli.py` [SC-007]
- [x] T015 [US1] Register the `specops` workflow additively in `src/specops/extension.py install` (write `.specify/workflows/specops/workflow.yml` + the `specops` key in `workflow-registry.json`; fail-closed preflight; idempotent `created/updated/unchanged`) [SC-001]
- [x] T016 [US1] Prune the `specops` workflow file + registry key on extension `disable`/`remove` (mirror `_prune_specops`, preserve foreign entries) in `src/specops/extension.py` [SC-001]

**Checkpoint**: US1 fully functional and independently testable — MVP.

---

## Phase 4: User Story 2 — Keep the ledger authoritative and reconciled (Priority: P1)

**Goal**: Reconciliation aligns ledger↔workflow/repo state as a fail-closed precondition of every state-changing step and after resume; the sole remedy for irreconcilable divergence is Feature 006's `rebaseline`.

**Independent Test**: Interrupt then `specify workflow resume` → reconcile realigns with no duplicate advance; desync past the baseline → `specops reconcile` exits 1 with `diverged_dimension` and halts, pointing to `specops status rebaseline` (no new command).

### Tests for User Story 2 (write first) ⚠️

- [x] T017 [P] [US2] Unit tests: workflow/ledger-state divergence detection, `reconcile --json` shape, `remedy == "specops status rebaseline"` (G3) in `tests/unit/test_reconcile.py` [SC-004]
- [x] T018 [P] [US2] Integration test: interrupt+resume realigns with 0 duplicate advances; desync → exit 1 + `diverged_dimension`, run halts, ledger unmodified; a ledger advanced out of band is treated as authoritative on the next reconcile (FR-013); concurrent runs against the same feature cannot double-advance (FR-014, via Feature 006 CAS), in `tests/integration/test_workflow_orchestration.py` [SC-004]

### Implementation for User Story 2

- [x] T019 [US2] Add the workflow/ledger-state reconciliation dimension (phase/active-artifact vs effective repo + run state) on top of the existing hash-reachability check in `src/specops/reconcile.py` [SC-004]
- [x] T020 [US2] Add `--json` to `specops reconcile` (emit `diverged_dimension` + `remedy`) via the outcome-contract primitive in `src/specops/cli.py` [SC-004][SC-006]
- [x] T021 [US2] Wire `specops reconcile` as a fail-closed precondition step before every state-changing `status` step and once after resume in `src/specops/templates/workflows/specops/workflow.yml` [SC-004]

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 — Bounded corrective loop + terminal gate (Priority: P2)

**Goal**: Review rejection drives Spec Kit's native `do-while`, conditioned on the review verdict; a terminal deterministic gate blocks completion while the verdict is not `APPROVED`.

**Independent Test**: Force the review gate to reject → the loop iterates implement→review recording a new review cycle each round; when `max_iterations` is exhausted still rejecting, the terminal `specops review` gate fails closed and the run halts (does not reach DONE); a passing verdict exits the loop and reaches DONE.

### Tests for User Story 3 (write first) ⚠️

- [x] T022 [P] [US3] Unit test: the workflow's `do-while` + terminal-gate structure (C7–C9) in `tests/unit/test_workflow_definition.py` [SC-005][SC-008]
- [x] T023 [P] [US3] Unit test: `review --json` verdict emission (`REJECTED` ⇔ exit 1, `gates[]` present, G2) in `tests/unit/test_review.py` [SC-005]
- [x] T024 [P] [US3] Integration test: reject → loop + new review cycle per round; exhaust bound still-rejecting → terminal gate halts with 0 fall-through to DONE; then pass → DONE, in `tests/integration/test_workflow_orchestration.py` [SC-005][SC-008]

### Implementation for User Story 3

- [x] T025 [US3] Add machine-readable verdict output (`--json`: `verdict`, `gates[]`) to `specops review` in `src/specops/review.py` and `src/specops/cli.py` [SC-005][SC-006]
- [x] T026 [US3] Replace the US1 linear implement→review→done segment with a native `do-while` (body: reconcile-pre → implement → review → record-verdict; condition `verdict == "REJECTED"`; native `max_iterations`) in `src/specops/templates/workflows/specops/workflow.yml` [SC-005]
- [x] T027 [US3] Add the terminal deterministic gate step (final `specops review`; fail closed when verdict ≠ `APPROVED`; not a human gate) after the loop in `src/specops/templates/workflows/specops/workflow.yml` [SC-005][SC-008]
- [x] T028 [US3] Wire each REJECTED round to open a new review cycle via a `specops status transition-phase REVIEW→IMPLEMENT -r REJECTED` step in `src/specops/templates/workflows/specops/workflow.yml` [SC-005]

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 — Classify outcomes through a stable CLI contract (Priority: P2)

**Goal**: Gate rejection, execution failure, and infrastructure error are distinguishable via the CLI outcome contract; execution/infra failures never record a rejection or advance the ledger.

**Independent Test**: Inject each class — `reconcile` divergence (infra-error), `review` rejection (gate-rejection), an integration-command crash (execution failure → engine abort/resume) — and verify each is a distinct `class`/exit, and that the ledger phase is not advanced and no review rejection is recorded for the infra/exec cases.

### Tests for User Story 4 (write first) ⚠️

- [x] T029 [P] [US4] Unit tests: `review`/`reconcile`/`consistency` JSON `class`↔exit consistency, missing-command/integration → `infra-error` before any mutation, read-only non-mutation (G1–G5) in `tests/unit/test_outcome_contract.py` and `tests/unit/test_consistency.py` [SC-006][SC-007]
- [x] T030 [P] [US4] Integration test: inject gate-rejection / infra-error / execution-failure → distinct `class`; assert 0 ledger advances and 0 rejections recorded for infra/exec, in `tests/integration/test_workflow_orchestration.py` [SC-006]

### Implementation for User Story 4

- [x] T031 [US4] Add `--json` to `specops consistency` and finalize the class taxonomy across all three commands per `contracts/cli-outcome-contract.md` in `src/specops/cli.py` [SC-006]
- [x] T032 [US4] Ensure a required-but-missing integration/SpecOps command surfaces as `infra-error` (exit 2) before any state mutation, in `src/specops/cli.py`/`src/specops/errors.py`/`src/specops/extension.py` [SC-006]
- [x] T033 [US4] Wire the workflow branch conditions (`if`/`switch` on `class`): gate-rejection→corrective loop, infra-error→halt (rebaseline out-of-band), execution-failure→`specify workflow resume`, in `src/specops/templates/workflows/specops/workflow.yml` [SC-006]

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T034 [P] Update `CHANGELOG.md`, `README.md`, and `README.pt-br.md` (behaviorally equivalent EN/PT) at the repo root for the `specops` workflow, the outcome contract, and the reconcile changes [SC-001][SC-006]
- [ ] T035 [P] Sync `specs/007-native-workflow-orchestration/contracts/*` and `quickstart.md` with the final workflow step IDs [SC-002]
- [ ] T036 Run the full repository quality gates — ruff, mypy, and the complete pytest suite at repo thresholds — confirming unit + integration + error-path + idempotency coverage across all stories [SC-001][SC-002][SC-003][SC-004][SC-005][SC-006][SC-007][SC-008]

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → depends on Setup; **blocks all user stories**.
- **US1 (P3)** → after Foundational. **MVP.**
- **US2 (P4)** → after Foundational; edits `workflow.yml` created by US1 (T021 depends on T012).
- **US3 (P5)** → after Foundational; replaces the US1 implement→review segment (T026/T027 depend on T012, and on T025 for the verdict JSON).
- **US4 (P6)** → after Foundational; T033 branch-wiring depends on the loop (T026) and reconcile JSON (T020); its contract work (T029–T032) is otherwise independent.
- **Polish (P7)** → after all desired stories.

### Shared-file note (workflow.yml)

`src/specops/templates/workflows/specops/workflow.yml` is edited by T012 (US1), T021 (US2), T026/T027/T033 (US3/US4) — these are **sequential**, not parallel. All are single-file edits building on the prior segment.

### Within each story

Tests (write first, ensure they fail) → implementation → integration. Ledger/CLI changes before the workflow.yml wiring that depends on them.

### Parallel opportunities

- Setup: T002, T003 in parallel.
- Foundational: T006, T008 in parallel (after their targets exist).
- Per story, the `[P]` test tasks run together; the outcome-contract command edits (review/reconcile/consistency) touch different code paths and can parallelize across stories where not blocked.

---

## Parallel Example: User Story 1

```bash
# Tests first (parallel):
Task: "Unit test workflow.yml validation in tests/unit/test_workflow_definition.py"
Task: "Integration test extension workflow lifecycle in tests/integration/test_extension_lifecycle.py"
Task: "Integration test happy-path run in tests/integration/test_workflow_orchestration.py"
```

---

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate**: install + run + readiness gate + skip recording. Ship the additive `specops` workflow as MVP.

### Incremental delivery

US1 (install + run) → US2 (reconciliation authority) → US3 (corrective loop) → US4 (outcome classification). Each adds value without breaking the prior; each independently testable via `test_workflow_orchestration.py` scenarios.

---

## Success-Criteria Coverage Map

| SC | Tasks |
|---|---|
| SC-001 | T001, T002, T003, T011, T012, T015, T016, T034, T036 |
| SC-002 | T001, T009, T035, T036 |
| SC-003 | T009, T011, T012, T036 |
| SC-004 | T004, T005, T006, T017, T018, T019, T020, T021, T036 |
| SC-005 | T022, T023, T024, T025, T026, T027, T028, T036 |
| SC-006 | T007, T008, T020, T025, T029, T030, T031, T032, T033, T034, T036 |
| SC-007 | T004, T011, T014, T029, T036 |
| SC-008 | T022, T024, T027, T036 |

All eight success criteria have task coverage.

## Notes

- `[P]` = different files, no incomplete-task dependency.
- `[SC-xxx]` tags satisfy the ROADMAP protocol (§4) and enable `speckit-analyze` cross-artifact checks.
- Tests must fail before implementation (Constitution task gate).
- Per the No Self-Application constraint, none of these tasks run `specops`/the workflow against *this* repository — all behavior is proven via `tests/` fixtures and sample client repos.
- Commit granularity: one commit per user story (Constitution Principle III); intermediate tasks closed with evidence.
