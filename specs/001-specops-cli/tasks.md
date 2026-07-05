---

description: "Task list for SpecOps CLI implementation"
---

# Tasks: SpecOps CLI — Speckit Companion for Agent-Guided Atomic Development

**Input**: Design documents from `specs/001-specops-cli/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/ (cli-contract, ledger-schema, directive-blocks), research.md (R1–R12), quickstart.md

**Tests**: Mandatory per the Constitution's task gate — every task closes only with passing automated tests and recorded evidence. Strict TDD is not required; test tasks accompany each story and MUST pass before the story checkpoint.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in descriptions

## Path Conventions

Single project (per plan.md): `src/specops/` package, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align packaging and the existing skeleton with the plan's decisions

- [X] T001 Update `pyproject.toml`: remove `rich` from dependencies (Constitution Check), add `pytest` as dev dependency group, configure hatch to bundle `src/specops/templates/**` as package data (FR-017)
- [X] T002 [P] Translate `src/specops/cli.py` to English and replace `rich.console.Console` with plain `typer.echo` (FR-014; research R12)
- [X] T003 [P] Create test scaffolding: `tests/unit/`, `tests/integration/`, and `tests/conftest.py` with fixtures for a temporary Git repository and a fake Speckit layout (`.specify/templates/`, `.specify/feature.json`, `.specify/integration.json`, `.specify/integrations/claude.manifest.json`, `.claude/skills/speckit-{plan,implement}/SKILL.md`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared modules every story depends on — parsing, Git helpers, config, exit-code contract

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Implement `src/specops/gitops.py`: repo-presence check, current branch, HEAD, commit range `start..HEAD`, ancestor check, name-only diff harvest (GitPython; research R7)
- [X] T005 [P] Implement `src/specops/speckit.py`: Speckit detection (R1), feature-dir resolution via `.specify/feature.json` with newest-`specs/NNN-*` fallback, task-ID extraction (`- [ ] T\d+`), SC-ID extraction (`- **SC-\d+**:`), coverage-tag parsing (`[SC-xxx,…]`), path-declaration + action-suffix parsing, and manifest-driven prompt-target resolution (R2): read `integration.json` installed integrations + separators, locate `speckit{sep}plan`/`speckit{sep}implement` entries in each `.specify/integrations/<agent>.manifest.json`, fail closed on missing manifest/entry/file
- [X] T006 [P] Implement `src/specops/config.py`: load/validate `specops.json`, merge-preserving update (R10), English error messages pointing to `specops init`
- [X] T007 Add CLI conventions to `src/specops/cli.py`: exit-code helpers (0/1/2 per R9), global Git-presence guard for all non-init commands failing < 1 s (FR-002, SC-008)
- [X] T008 [P] Unit tests for gitops in `tests/unit/test_gitops.py` (range harvest, ancestor, no-commits edge)
- [X] T009 [P] Unit tests for speckit parsing in `tests/unit/test_speckit.py` (task IDs, SC IDs, coverage tags, suffixes, detection, feature-dir fallback)
- [X] T010 [P] Unit tests for config in `tests/unit/test_config.py` (merge preserves user values and unknown keys, missing-file error)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Prepare a Speckit Repository for SpecOps (Priority: P1) 🎯 MVP

**Goal**: `specops init` takes a repo from "Speckit just initialized" to fully prepared: Git validated (with offer), `specops.json`, `/specops.review` installed, marker blocks injected additively — idempotent, offline, byte-identical restore.

**Independent Test**: Quickstart Scenario A — fresh init in a fake-Speckit sandbox, re-run without duplicates, block deletion restores originals byte-identical, no-git and no-speckit failure paths.

### Implementation for User Story 1

- [X] T011 [P] [US1] Author packaged asset `src/specops/templates/specops.json` (template with `test_command`, `lint_command`, `skills_dir` defaults)
- [X] T012 [P] [US1] Author packaged asset `src/specops/templates/directives/plan.md` per contracts/directive-blocks.md: Empirical Verification with action suffixes, per-task `[SC-xxx]` coverage tags, `specops consistency` gate, stop-and-ask
- [X] T013 [P] [US1] Author packaged asset `src/specops/templates/directives/implement.md` per contracts/directive-blocks.md: Operational Silence with `<task-id> done (<commit-sha7>), starting <next-task-id>` line, ledger loop (`start-task`/`complete-task --auto`), `specops reconcile` preflight, Stop-and-Ask gates
- [X] T014 [P] [US1] Author packaged asset `src/specops/templates/review.md` per contracts/cli-contract.md (review command): skills load → reconcile-first abort → lint/test pre-filter → porcelain scope rejection (incl. empty diff) → surgical diff review → `[File]:[Line] - …` findings in `revisions/revision-X.md`; layout-neutral body (frontmatter added at install time for skills-mode targets)
- [X] T015 [US1] Implement marker-injection engine in `src/specops/initializer.py`: append `<!-- SPECOPS:BEGIN <id> v<n> -->…<!-- SPECOPS:END <id> -->` blocks at EOF, replace strictly between matching markers on re-run, fail closed (exit 1, zero writes) on corrupted markers (R3)
- [X] T016 [US1] Implement `specops init` flow in `src/specops/initializer.py` and wire in `src/specops/cli.py`: Git check with interactive offer and `--non-interactive` decline default (FR-001/016), Speckit detection abort (FR-003), manifest-driven prompt-target resolution for every installed integration failing closed (R2), `specops.json` create/merge (R10), install `review.md` per integration at the path derived from the plan-prompt pattern (`speckit{sep}plan` → `specops{sep}review`, frontmatter-wrapped for skills mode; command named `specops{sep}review`), inject both directive blocks into each integration's prompts, print created/updated/unchanged summary
- [X] T017 [P] [US1] Unit tests for the injection engine in `tests/unit/test_injection.py`: clean append, in-place update, BEGIN-without-END, duplicate BEGIN, nested markers, version bump
- [X] T018 [US1] Integration tests for Scenario A in `tests/integration/test_init.py`: fresh init, idempotent re-run (SC-005), precise block removal (block + its single blank separator) → byte-identical originals (SC-010), no-git non-interactive decline asserting the failure completes in < 1 s (SC-008), no-speckit abort, missing manifest/entry/file fail-closed (R2), a second-integration fixture (dotted `commands/speckit.plan.md` layout) receiving injection and its own `specops.review` command, config merge preservation

**Checkpoint**: `specops init` fully functional — MVP deliverable

---

## Phase 4: User Story 2 - Control Task Execution State Through the Ledger (Priority: P2)

**Goal**: `specops status` command group — ledger creation, task lifecycle with single-active-task rule, machine-collected evidence, ordered phase machine with the corrective exception.

**Independent Test**: Quickstart Scenarios B and E — full task loop with `--auto` evidence, refusal paths, phase-machine walk including REVIEW→IMPLEMENT(REJECTED).

### Implementation for User Story 2

- [X] T019 [P] [US2] Author packaged asset `src/specops/templates/status.yaml` (ledger scaffold per contracts/ledger-schema.md with `{{feature-name}}`/`{{commit-hash}}`/`{{YYYY-MM-DD}}` placeholders)
- [X] T020 [US2] Implement ledger core in `src/specops/status.py`: load/save with schema validation (corrupt YAML → exit 2 per L-invariants), task sync from `tasks.md` on every command (new → PENDING, vanished → `orphaned: true`, unknown id → exit 1; FR-008a, R5)
- [X] T021 [US2] Implement `init-spec` and `start-task` in `src/specops/status.py`: `init-spec [<name>]` with optional name defaulting to the active feature and required to match it when provided (cli-contract), scaffold instantiation with placeholder fill (R10), single-IN_PROGRESS rule, `started_commit = HEAD`, `recovery.active_task` (R5)
- [X] T022 [US2] Implement `complete-task` in `src/specops/status.py`: `--auto` runs `test_command` (missing/failing → exit 1, task stays IN_PROGRESS), harvests `started_commit..HEAD` commits + combined diff into `TEST_REPORT`/`CODE_DIFF` evidence (R7); `--evidence` validates `<CLASS>:<summary>` against the four canonical classes (L7); neither flag → exit 1 (FR-009/009a/010)
- [X] T023 [US2] Implement `transition-phase` state machine in `src/specops/status.py`: SPECIFY→…→DONE ordered, REVIEW→IMPLEMENT requires `-r REJECTED` and appends `review_cycles[]` round, DONE requires latest cycle APPROVED, invalid → exit 1 untouched (FR-008b, R8)
- [X] T024 [US2] Wire `status` subcommands in `src/specops/cli.py`: `init-spec`, `start-task`, `complete-task --auto/--evidence`, `transition-phase -r`
- [X] T025 [P] [US2] Unit tests in `tests/unit/test_status.py`: phase machine (all valid/invalid jumps, corrective rounds), task transitions, evidence format validation, orphan flagging, sync idempotency
- [X] T026 [US2] Integration tests for Scenarios B and E in `tests/integration/test_ledger.py`: full loop with real commits, `--auto` failing test command, manual evidence path, phase walk

**Checkpoint**: Ledger fully operational — US1 and US2 independently testable

---

## Phase 5: User Story 3 - Reconcile the Ledger Against Repository History (Priority: P3)

**Goal**: `specops reconcile` — deterministic exit-code gate proving every recorded commit exists in branch history.

**Independent Test**: Quickstart Scenario C — clean ledger passes; seeded fake hash fails naming task and hash.

**Depends on**: US2 (reads the ledger)

### Implementation for User Story 3

- [X] T027 [US3] Implement `src/specops/reconcile.py` and wire in `src/specops/cli.py`: every `tasks[].commits[]` hash is ancestor of HEAD, DONE tasks have commits + evidence (L1/L3), `(human)` values exempt (R11), `orphaned` entries reported, branch mismatch warns, divergences listed as `<task-id>: <reason>` → exit 1 (FR-011)
- [X] T028 [P] [US3] Unit tests in `tests/unit/test_reconcile.py`: ancestor pass/fail, `(human)` exemption, DONE-without-evidence, orphan reporting
- [X] T029 [US3] Integration test for Scenario C in `tests/integration/test_reconcile.py`: pass on real history, fail on seeded divergence (SC-003)

**Checkpoint**: Review preflight gate available

---

## Phase 6: User Story 4 - Validate Spec/Plan Consistency (Priority: P4)

**Goal**: `specops consistency` — SC-ID coverage traceability plus empirical path-suffix validation, language-agnostic.

**Independent Test**: Quickstart Scenario D — compliant pair passes; removed coverage tag and ghost `(modify)` path each fail naming the offender.

### Implementation for User Story 4

- [X] T030 [US4] Implement `src/specops/consistency.py` and wire in `src/specops/cli.py`: parse SC IDs from spec Success Criteria, match `[SC-xxx]` task tags deterministically (uncovered SC → fail; unknown SC ref → fail; no NLP per FR-012/FR-014a), validate plan path declarations against worktree (`(modify)` exists, `(create)` parent exists, `(remove)` exists locally or in history, missing suffix → warning), violations as `consistency: <file>:<line> - <rule and short action>` → exit 1
- [X] T031 [P] [US4] Unit tests in `tests/unit/test_consistency.py`: coverage matrix (covered/uncovered/unknown-ref), each suffix rule, warning vs failure, violation line format
- [X] T032 [US4] Integration test for Scenario D in `tests/integration/test_consistency.py` with a non-English prose fixture proving language-agnostic validation (FR-014a)

**Checkpoint**: Planning gate available

---

## Phase 7: User Story 5 - Token-Optimized Review Inside the Agent (Priority: P5)

**Goal**: The installed `/specops.review` command drives the reviewer through the cheapest-rejection-first order and the short revision format.

**Independent Test**: Installed asset carries every mandatory ordered directive; quickstart Scenario F validates agent-in-the-loop behavior.

**Depends on**: US1 (asset installed); full flow also exercises US3

### Implementation for User Story 5

- [X] T033 [US5] Integration test in `tests/integration/test_review_asset.py`: post-init installed review command (at the layout-derived path, e.g. `.claude/skills/specops-review/SKILL.md`) contains, in order, the mandatory directives — skills load from `skills_dir`, `specops reconcile` abort-first, lint/test zero-token pre-filter, `git status --porcelain` scope rejection including empty diff, `[File]:[Line] - [rule violated and short action]` output format, `revisions/revision-X.md` max+1 numbering
- [X] T034 [US5] Document the review workflow in `README.md`: invoking the review command (name follows the integration's invoke separator, e.g. `/specops-review`), the rejection order, revision-report format, and the Scenario F manual validation walkthrough (agent-in-the-loop, not CI-automatable)

**Checkpoint**: All five user stories independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Packaging proof, documentation, final audits

- [X] T035 [P] Write `README.md` usage manual (consolidates the review-workflow section written in T034): install, `specops init`, command reference (link contracts), `specops.json` keys, supported Speckit integration layouts and the Speckit-upgrade → re-init note (R2), language policy (English operationalization, any-language client artifacts), uninstall-by-deletion note (R11)
- [X] T036 [P] English audit: verify zero non-English strings in `src/` output/docstrings (FR-014, SC-007)
- [X] T037 Run the full integration suite covering quickstart Scenarios A–E plus the offline check (SC-009) and fix any gaps found
- [X] T038 Packaging validation: build wheel, install into a clean venv, confirm `src/specops/templates/**` assets ship in the wheel and `specops init` succeeds from the installed package alone (FR-017)
- [X] T039 [P] Integration test in `tests/integration/test_multi_stack.py`: two sandboxes with different fake stacks (npm-style vs pytest-style test/lint commands, differing only in `specops.json`) — init, full task loop, and gates behave identically in both (SC-006, FR-015)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: After Foundational — no story dependencies
- **US2 (Phase 4)**: After Foundational — no story dependencies (parallel with US1)
- **US3 (Phase 5)**: After US2 (reads the ledger)
- **US4 (Phase 6)**: After Foundational — independent of US1–US3 (parallel opportunity)
- **US5 (Phase 7)**: After US1 (installed asset); full manual flow also uses US3
- **Polish (Phase 8)**: After all desired stories

### Within Each User Story

- Assets [P] → engine modules → CLI wiring → unit tests [P] → integration tests
- Story complete only when its tests pass (Constitution task gate)

### Parallel Opportunities

- T002/T003 after T001; T004/T005/T006 together; T008/T009/T010 together
- US1 assets T011–T014 all parallel; T017 parallel with T016
- After Foundational: US1, US2, and US4 can proceed in parallel; US3 follows US2; US5 follows US1
- Polish: T035/T036/T039 parallel

## Parallel Example: User Story 1

```bash
# Launch all US1 assets together:
Task: "Author packaged asset src/specops/templates/specops.json"
Task: "Author packaged asset src/specops/templates/directives/plan.md"
Task: "Author packaged asset src/specops/templates/directives/implement.md"
Task: "Author packaged asset src/specops/templates/review.md"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → Phase 2 Foundational (blocks everything)
2. Phase 3 US1 → **STOP and VALIDATE**: quickstart Scenario A end-to-end
3. MVP: a repo can be fully prepared for SpecOps with one command

### Incremental Delivery

1. + US2 → ledger loop usable by agents (Scenarios B/E)
2. + US3 → reconcile gate (Scenario C)
3. + US4 → consistency gate (Scenario D)
4. + US5 → review flow complete (Scenario F)
5. Polish → publishable package

---

## Notes

- [P] tasks = different files, no dependencies
- Every task closes with passing tests and evidence (Constitution task gate); commit per task or logical group
- Stop at any checkpoint to validate the story independently
