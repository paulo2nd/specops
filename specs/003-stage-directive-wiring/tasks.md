# Tasks: Stage-Wide Directive Wiring

**Input**: Design documents from `specs/003-stage-directive-wiring/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. Per the Constitution (Development Workflow & Quality Gates),
no task is `DONE` without passing automated tests and recorded evidence.

**Organization**: Grouped by user story. Foundational plumbing (injection
targets + initializer wiring) is shared by all stories and must land first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (user-story phases only)
- Exact file paths are included in each task.

## Path Conventions

Single Python project: sources in `src/specops/`, tests in `tests/`.

---

## Phase 1: Setup

**Purpose**: Establish a clean baseline before touching injection code.

- [X] T001 Confirm baseline on branch `003-stage-directive-wiring`: run `pip install -e ".[dev]"` and `pytest`; the suite is green before any change.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make the injection engine aware of the specify and tasks prompts so
every user story can install its directive. **No story can start until this
phase is complete.**

- [X] T002 [P] Extend `resolve_prompt_targets` in `src/specops/speckit.py` to resolve and return `specify_path` and `tasks_path` via `_find_prompt_file(root, files, agent, sep, role)` with `role="specify"` and `role="tasks"`; preserve existing key order, list order, and the fail-closed `ManifestResolutionError` contract.
- [X] T003 [P] Create the two new directive assets `src/specops/templates/directives/specify.md` and `src/specops/templates/directives/tasks.md` with minimal English content plus the common graceful-degradation guard line, so the initializer has assets to read (full prose is authored per story below).
- [X] T004 Wire `src/specops/initializer.py` `run()` to read the specify and tasks templates and call `inject_block(specify_path, "specify", …)` and `inject_block(tasks_path, "tasks", …)`, echoing one status line per target in the existing `<path>: <role> directive <status>` format (depends on T002, T003).
- [X] T005 [P] Add unit tests in `tests/unit/test_speckit.py`: `resolve_prompt_targets` returns non-null `specify_path`/`tasks_path` pointing at existing files for the Claude fixture, and raises `ManifestResolutionError` when the specify or tasks manifest entry is missing.
- [X] T006 Add an integration assertion in `tests/integration/test_init.py`: after `run()`, all four stage prompts (specify, plan, tasks, implement) contain their `SPECOPS:BEGIN` block, and a second `run()` reports every block `unchanged` (idempotency, SC-007).
- [X] T007 [P] Add unit tests in `tests/unit/test_injection.py`: `remove_block` restores byte-identical pre-injection content for the `specify` and `tasks` block IDs (reversibility, SC-005).

**Checkpoint**: `specops init` installs four idempotent, reversible blocks.

---

## Phase 3: User Story 1 — Ledger exists when implementation starts (Priority: P1) 🎯 MVP

**Goal**: The tasks stage creates the execution ledger so the implement loop's
first `start-task` never fails for a missing ledger.

**Independent Test**: After the tasks stage runs, `specops status start-task T001`
succeeds with no manual `init-spec`.

- [X] T008 [US1] In `src/specops/templates/directives/tasks.md`, author the ledger-creation step: after `tasks.md` is finalized, run `specops status init-spec`; if it reports the ledger already exists, treat that as success and continue (non-blocking, FR-012 / US1 scenario 2).
- [X] T009 [US1] In the same tasks directive, add the "never hand-edit `status.yaml` or `tasks.md` checkboxes — the ledger is the authority" note, consistent with the implement directive.
- [X] T010 [US1] Extend `tests/integration/test_init.py` to assert the injected `tasks` block contains the `init-spec` instruction and the "already exists → continue" wording.

**Checkpoint**: The MVP is usable — implementation can start from an auto-created ledger.

---

## Phase 4: User Story 2 — Ledger phase reflects the current stage (Priority: P2)

**Goal**: The ledger phase tracks the active stage, and the review cycle is
opened automatically at implement completion.

**Independent Test**: `status show` reports the true phase after each stage, and
an open review cycle exists before `/specops-review` runs.

- [X] T011 [US2] In `src/specops/templates/directives/tasks.md`, add the phase walk after `init-spec`: run `specops status transition-phase PLAN` then `specops status transition-phase TASKS`; if a transition reports an unexpected current phase, stop and surface it rather than forcing further writes (fail-safe).
- [X] T012 [US2] In `src/specops/templates/directives/implement.md`, add: (a) `specops status transition-phase IMPLEMENT` before the first `start-task` (continue if already IMPLEMENT); (b) `specops status transition-phase REVIEW` after the final task is `DONE`, to open the review cycle, then hand off to review. Keep the existing operational-silence, ledger loop, skills, reconcile-preflight, and stop-and-ask content intact (FR-009).
- [X] T013 [US2] Extend `tests/integration/test_init.py` to assert the injected `implement` block contains both `transition-phase IMPLEMENT` and `transition-phase REVIEW`, and the injected `tasks` block contains the `PLAN`→`TASKS` phase walk.

**Checkpoint**: The phase state machine is driven end to end by the prompts.

---

## Phase 5: User Story 3 — Coverage tags where tasks are generated (Priority: P3)

**Goal**: The `[SC-xxx]` rule lives in the tasks stage; plan and specify blocks
are aligned and non-conflicting.

**Independent Test**: `specops consistency` passes on freshly generated tasks;
the plan block no longer restates the full rule.

- [X] T014 [US3] In `src/specops/templates/directives/tasks.md`, add the authoritative `[SC-xxx]` coverage-tag rule: every generated task line carries ≥1 tag using only Success Criteria IDs present in `spec.md`; comma-separate multiple IDs inside one bracket; never invent IDs.
- [X] T015 [US3] In `src/specops/templates/directives/plan.md`, replace the full "SC Coverage Tags" paragraph with a one-line pointer ("coverage tags are authored during the tasks stage; the plan stage only ensures each Success Criterion is coverable"), keeping path verification, the `specops consistency` gate, and stop-and-ask content unchanged (FR-009).
- [X] T016 [US3] Replace the T003 stub in `src/specops/templates/directives/specify.md` with the final informational content: SpecOps is active; author prose in any language while keeping structural tokens parseable; the ledger will be created at the tasks stage; no ledger command runs at this stage.
- [X] T017 [US3] Add/extend tests in `tests/integration/test_init.py` (or `tests/unit/test_injection.py`) asserting the injected `plan` block no longer contains the full SC-tag paragraph and the injected `tasks` block contains the SC-tag rule.

**Checkpoint**: All five gaps (a–e) from the spec are closed.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T018 [P] Update `README.md`: state that `specops init` injects directives into the specify, plan, tasks, and implement prompts (update the numbered init step and the Speckit-upgrade re-inject note).
- [X] T019 [P] Add a `CHANGELOG.md` entry under `## [Unreleased]` for stage-wide directive wiring (specify/tasks injection, phase transitions, `[SC-xxx]` rule relocation).
- [X] T020 Run the full quality gates and fix any regression: `ruff check .`, `mypy src/specops`, `pytest` (coverage ≥ 85%).

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** → **Phase 3 (US1)** → **Phase 4 (US2)** → **Phase 5 (US3)** → **Phase 6 (Polish)**.
- **Foundational blocks everything**: T002–T004 must land before any story authors directive prose (init must be able to inject the blocks).
- **Shared file `directives/tasks.md`** is edited by US1 (T008), US2 (T011), and US3 (T014), so those tasks are sequential, not parallel.
- **US2 T012** (implement.md) and **US3 T015/T016** (plan.md, specify.md) touch distinct files and could overlap with tasks.md edits if staffed separately.

## Parallel Opportunities

- Foundational: **T002** (speckit.py), **T003** (new template stubs), **T005** (test_speckit.py), **T007** (test_injection.py) touch distinct files → `[P]`.
- Polish: **T018** (README) and **T019** (CHANGELOG) → `[P]`.

## Implementation Strategy

- **MVP = User Story 1** (T001–T010): auto-created ledger removes the most
  common hard failure. Ship/validate this first.
- Layer **US2** (truthful phase + review cycle) and **US3** (coverage tags +
  de-dup) incrementally; each is independently testable and leaves the prior
  increment working.
- Close with Polish (docs + full gates). Per the SpecOps method, commit at
  user-story granularity and close the final task of each story with `--auto`.
