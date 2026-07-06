# Tasks: Deterministic Review Gates in the CLI (`specops review`)

**Input**: Design documents from `/specs/004-review-gates-cli/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — per the Constitution (Development Workflow & Quality Gates, task gate), every task is closed only with passing automated tests and recorded evidence. Test tasks are written first and must fail before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] [SC-xxx] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- **[SC-xxx]**: Spec Success Criteria covered by the task (SpecOps coverage tags)
- Include exact file paths in descriptions

## Path Conventions

Single project: `src/specops/`, `tests/` at repository root (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

No setup tasks — existing installed package (`pip install -e .`), no new
dependencies, no scaffolding required (plan.md Technical Context).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Git/ledger helpers both the gate pipeline and its tests depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T001 [P] [SC-001] Unit tests for `gitops.dirty_files(repo)` (clean tree → empty list; modified/untracked files → porcelain lines) in tests/unit/test_gitops.py — write first, confirm they fail
- [ ] T002 [P] [SC-001] Unit tests for the public read-only baseline accessor (ledger with baseline → value; ledger without baseline → None/empty; no mutation of status.yaml) in tests/unit/test_status.py — write first, confirm they fail
- [ ] T003 [SC-001] Implement `dirty_files(repo) -> list[str]` wrapping `repo.git.status("--porcelain")` in src/specops/gitops.py (research R3); T001 passes
- [ ] T004 [SC-001] Implement the public read-only baseline accessor in src/specops/status.py (no new mutation paths, reuses `_get_feature_dir`/`_load_ledger`); T002 passes

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - One command runs all deterministic review gates (Priority: P1) 🎯 MVP

**Goal**: `specops review` evaluates reconcile → lint → test → working-tree cheapest-first with early stop, read-only, exit 0/1 (2 on ledger parse), per contracts/review-command.md

**Independent Test**: quickstart.md Scenarios 1–5 (pass report, reconcile rejection with early stop, failing test with 50-line truncation, dirty tree / no-diff rejection, byte-identical ledger)

### Tests for User Story 1 (mandatory per Constitution task gate) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T005 [P] [US1] [SC-001,SC-003] Unit tests in tests/unit/test_review.py: fixed gate order; early stop (no later gate evaluated after a FAIL); SKIPPED for empty lint/test commands; last-50-lines truncation with total-size note; reconcile warnings echoed on PASS; report rendering (`[gate] <name> ... STATUS` lines); missing-baseline failure — write first, confirm they fail
- [ ] T006 [P] [US1] [SC-001,SC-004,SC-006] Integration tests in tests/integration/test_review_cli.py via the Typer runner: all-pass → report on stdout exit 0; gate failure → evidence on stderr exit 1; corrupt status.yaml → exit 2; missing specops.json → ConfigError exit 1 with init guidance; status.yaml byte-identical before/after every outcome (FR-007) — write first, confirm they fail

### Implementation for User Story 1

- [ ] T007 [US1] [SC-001] Create src/specops/review.py with `GateResult`/`GateReport` and the report renderer per data-model.md and contracts/review-command.md (no Typer imports, 002 errors contract)
- [ ] T008 [US1] [SC-001] Implement the reconcile gate in src/specops/review.py: call `reconcile.run(root)` in-process; violations → FAIL with violation lines; warnings echoed in detail and gate PASSes (research R6)
- [ ] T009 [US1] [SC-001] Implement the lint and test gates in src/specops/review.py: `subprocess.run(cmd, shell=True, capture_output=True, text=True)`, no timeout; non-zero → FAIL with command, exit code, last 50 lines of combined stdout+stderr plus truncation note; empty command → SKIPPED (research R1/R2)
- [ ] T010 [US1] [SC-001] Implement the working-tree gate in src/specops/review.py: `gitops.dirty_files` non-empty → FAIL with file list; `gitops.name_only_diff(baseline, HEAD)` empty → FAIL "no effective diff — nothing to review"; missing/empty ledger baseline → FAIL with explanatory message (research R4)
- [ ] T011 [US1] [SC-001,SC-003] Implement `run_gates(root) -> str` orchestration in src/specops/review.py: fixed order, early stop, rendered report returned on success, `SpecopsError` carrying report + evidence raised on failure (research R5); T005 passes
- [ ] T012 [US1] [SC-004] Register the `review` command in src/specops/cli.py through the existing `_handle_errors` decorator (single exit-code mapper); T006 passes

**Checkpoint**: User Story 1 fully functional — validate with quickstart.md Scenarios 1–5

---

## Phase 4: User Story 2 - The installed review prompt delegates gates to the command (Priority: P2)

**Goal**: Installed `/specops-review` prompt collapses gate steps 2–4 into a single `specops review` instruction, delivered by `specops init`, per contracts/review-template.md

**Independent Test**: quickstart.md Scenario 6 — re-run `specops init` in a fixture repo and inspect the installed review command file

### Tests for User Story 2 (mandatory per Constitution task gate) ⚠️

- [ ] T013 [P] [US2] [SC-005] Update tests/integration/test_review_asset.py: installed prompt contains the collapsed gate step (run `specops review`; non-zero exit → REJECTED, report output, stop, read no code) and no longer instructs `specops reconcile`, lint/test commands, or `git status` individually; remaining sections renumbered and intact — write first, confirm it fails

### Implementation for User Story 2

- [ ] T014 [US2] [SC-002,SC-003,SC-005] Collapse Steps 2–4 of src/specops/templates/review.md into the single "Step 2 — Deterministic Gates" per contracts/review-template.md, renumbering the surgical-review and revision-report steps; verdict transition and Active Learning unchanged; T013 passes

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Standalone CI gate (Priority: P3)

**Goal**: The command is adoptable as a CI/workflow gate: any ledger phase, non-interactive, exit-code driven

**Independent Test**: quickstart.md Scenario 7 — run with closed stdin in a phase ≠ REVIEW

### Tests for User Story 3 (mandatory per Constitution task gate) ⚠️

- [ ] T015 [P] [US3] [SC-004] Integration tests in tests/integration/test_review_cli.py: gates evaluate normally when ledger phase is not REVIEW (no phase precondition); run with closed stdin completes without prompting — write first, confirm they fail (or pass trivially against T011/T012, then lock the invariant)

### Implementation for User Story 3

- [ ] T016 [US3] [SC-004] Document `specops review` in README.md: command reference entry plus a CI usage example and a Speckit-workflow `shell`-step example (user-owned YAML calling `specops review`)

**Checkpoint**: All user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Release hygiene and full-regression proof

- [ ] T017 [P] [SC-006] Add the feature entry to CHANGELOG.md (new `specops review` command, template collapse, no breaking changes)
- [ ] T018 [P] [SC-004] Mirror the README.md `specops review` documentation in README.pt-br.md
- [ ] T019 [SC-006] Run the full regression suite (`pytest -q`) and walk quickstart.md Scenarios 1–7; confirm all pre-existing messages/exit codes/streams untouched outside the review flow

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — BLOCKS all user stories
- **User Stories (Phases 3–5)**: All depend on Phase 2 completion
  - US1 (Phase 3) has no dependency on other stories
  - US2 (Phase 4) is independent of US1 code (template-only) but is only meaningful once `specops review` exists — schedule after US1
  - US3 (Phase 5) locks invariants of US1's implementation and adds docs — schedule after US1
- **Polish (Phase 6)**: Depends on all user stories being complete

### Within Each User Story

- Tests are written and failing before implementation (T001/T002 → T003/T004; T005/T006 → T007–T012; T013 → T014; T015 → T016)
- Entities before pipeline: T007 → T008/T009/T010 → T011 → T012

### Parallel Opportunities

- T001 ‖ T002 (different test files)
- T005 ‖ T006 (different test files, after Phase 2)
- T013 ‖ US1 implementation tail (different files) — meaningful only near US1 completion
- T017 ‖ T018 (different files)

---

## Parallel Example: User Story 1

```bash
# Launch both test tasks together (different files):
Task: "Unit tests for the gate pipeline in tests/unit/test_review.py"
Task: "Integration tests for exit codes/streams in tests/integration/test_review_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001–T004)
2. Complete Phase 3: User Story 1 (T005–T012)
3. **STOP and VALIDATE**: quickstart.md Scenarios 1–5 — `specops review` is already usable interactively and in CI even before the template change
4. Then US2 (template delivery), US3 (CI docs/invariants), Polish

### Incremental Delivery

1. Phase 2 → helpers proven by unit tests
2. US1 → the command works standalone (MVP)
3. US2 → clients receive the collapsed prompt on next `specops init`
4. US3 → CI adoption documented and invariants locked
5. Polish → changelog, pt-BR parity, full regression (SC-006)

---

## Notes

- [P] tasks = different files, no dependencies
- Commit granularity: one commit per user story (Constitution III); intermediate tasks close with `--evidence`, the story's final task closes with `specops status complete-task --auto`
- Never hand-edit status.yaml or tasks.md checkboxes — the ledger is the authority
