# Tasks: Lifecycle Recording Coverage

**Input**: Design documents from `/specs/022-lifecycle-recording-coverage/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Mandatory per the Constitution task gate — every task closes only with passing automated tests; content/behavior tests are written first within each story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. Commit granularity: one commit per user story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project: `src/specops/` + `tests/` at repository root (per plan.md). All validation on fixtures — never `specops` against this repository (No Self-Application).

---

## Phase 1: Setup

**Purpose**: Confirm a green baseline so every later failure is attributable to this feature's work.

- [x] T001 Run the full gate and confirm green before any change: `conda run -n specops ruff check src tests && conda run -n specops mypy src && conda run -n specops pytest` (no file changes; baseline evidence for the ledgerless dev loop)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None required — every mechanism this feature builds on already ships: `_sync_tasks` merge semantics (`src/specops/status.py:105`), `record-step`/`skipped_steps` (Feature 007), the native hook manifest (`src/specops/extension.py:46`), `fsutil` atomic writes, and Spec Kit's `before_/after_converge`, `after_clarify/checklist/analyze` hook points. No foundational tasks.

**Checkpoint**: Baseline green (T001) — user story work can begin.

---

## Phase 3: User Story 1 — Converge-appended tasks enter the ledger, or converge fails closed (Priority: P1) 🎯 MVP

**Goal**: `specops status sync-tasks` (new, additive) records converge's task-list append deterministically ([contracts/sync-tasks-cli.md](contracts/sync-tasks-cli.md)); the converge directive pair fails closed **before mutation** via `sync-tasks --check` and records after via `sync-tasks` + non-blocking `consistency` report ([contracts/hooks-and-workflow.md](contracts/hooks-and-workflow.md)).

**Independent Test**: `conda run -n specops pytest tests/unit/test_status.py tests/unit/test_cli.py tests/unit/test_converge_directive.py tests/unit/test_extension.py` — sync semantics, exit codes/diagnostics, directive content, and manifest registration all proven on fixtures.

### Tests for User Story 1 (write first, confirm they FAIL) ⚠️

- [x] T002 [P] [US1] Extend tests/unit/test_status.py with `cmd_sync_tasks` semantics tests on a fixture ledger + `tasks.md` (SC-001): new IDs appended as `PENDING` with the standard task-record shape; vanished IDs → `orphaned: true` preserved; completed entries untouched; zero-append run reports "no changes" and leaves the ledger byte-identical; double run on identical input → identical ledger, no duplicates (US1-4 determinism); an appended task then flows through `cmd_start_task` → `cmd_complete_task` on the fixture and `reconcile.run` stays green afterward (SC-001 start/complete loop, remediation C1)
- [x] T003 [P] [US1] Extend tests/unit/test_cli.py with `status sync-tasks` contract tests (SC-002): exit 0 on recorded and on zero-change; exit 2 with the **specific** diagnostic for missing ledger, corrupt ledger, and missing `tasks.md`; `--check` validates and reports would-append without writing (ledger byte-identical after); `--json` emits `{appended, orphaned, unchanged, check}`; no exit-1 outcome exists
- [x] T004 [P] [US1] Create tests/unit/test_converge_directive.py (pattern: tests/unit/test_lite_directive.py) with failing directive-content tests: converge-pre — opens with the Rule-5 no-op clause for unmanaged repos, orders `specops status sync-tasks --check` **before** converge runs, stops-and-asks on non-zero without mutating, treats managed-repo-with-CLI-absent as fail-closed (FR-003); converge — SC-tagging obligation on appended tasks before recording (clarification Q2), `specops status sync-tasks` as the recording step, `specops consistency` output **reported, never gated** (FR-004); negative — neither directive names a new command beyond `status sync-tasks` or reimplements converge (Rule 8)

### Implementation for User Story 1

- [x] T005 [US1] Implement `cmd_sync_tasks(root, *, check, as_json)` in src/specops/status.py: resolve feature dir, load via the standard `load_for_write` path, apply `_sync_tasks`, report appended/orphaned/unchanged; `check=True` validates and reports without saving; write path via the standard `finalize` (lock + revision); T002 passes
- [x] T006 [US1] Wire `status sync-tasks` (+ `--check`, `--json`) in src/specops/cli.py under `status_app` with `_handle_errors` (frozen 0/2 exit mapping, specific diagnostics); T003 passes
- [x] T007 [P] [US1] Create src/specops/templates/directives/converge-pre.md (before_converge): Rule-5 no-op clause → `sync-tasks --check` precondition → stop-and-ask on failure, converge does not run
- [x] T008 [P] [US1] Create src/specops/templates/directives/converge.md (after_converge): tag appended tasks `[SC-xxx]` → `specops status sync-tasks` → `specops consistency` report (non-blocking)
- [x] T009 [US1] Register `("converge-pre", "before_converge", False, …)` and `("converge", "after_converge", False, …)` in `_HOOK_SPECS` (src/specops/extension.py) and extend tests/unit/test_extension.py to assert both entries appear in the built manifest with prompts sourced from the new directive files; T004 passes

**Checkpoint**: User Story 1 fully functional — converge has a deterministic recording path and a pre-mutation fail-closed gate, proven on fixtures. Commit once for US1 (one commit per user story).

---

## Phase 4: User Story 2 — Optional-step decisions are recorded in every entry mode (Priority: P2)

**Goal**: `record-step` becomes pre-ledger-safe via the feature-scoped buffer drained at `init-spec` ([contracts/record-step-buffer.md](contracts/record-step-buffer.md)); run decisions record via new `after_clarify/checklist/analyze` hooks, skip decisions derive at the next mandatory seam in both entry modes; the workflow's record steps return to their gates and the corrective round gains the converge gate ([contracts/hooks-and-workflow.md](contracts/hooks-and-workflow.md)).

**Independent Test**: `conda run -n specops pytest tests/unit/test_record_step_buffer.py tests/unit/test_workflow_definition.py tests/unit/test_extension.py` — buffering/drain/discard semantics, workflow step placement, and hook registration all proven on fixtures.

### Tests for User Story 2 (write first, confirm they FAIL) ⚠️

- [ ] T010 [P] [US2] Create tests/unit/test_record_step_buffer.py: pre-ledger `cmd_record_step` writes `specs/<feature>/.specops-pending-steps.json` (`version: 1`, replace-by-step on re-record, atomic); `cmd_init_spec` drains buffered entries into the new ledger's `workflow.skipped_steps` and deletes the buffer; unknown buffer `version` → discarded with stderr note, never fatal; stale buffer without `init-spec` is inert (fresh feature unaffected — abandoned-run discard, clarification Q4); ledger-present path byte-identical to today; `converge` accepted as a step value and unknown steps still exit 2; `--if-absent` records when no decision exists (buffer or ledger), no-ops with exit 0 reporting the existing decision otherwise, and never overwrites an explicit `run` (remediation U1) (SC-003, SC-006)
- [ ] T011 [P] [US2] Extend tests/unit/test_workflow_definition.py: **invert** `test_record_steps_run_after_the_ledger_exists` (#50 workaround dissolved) to pin `clarify-record`/`checklist-record` adjacent to their gates; corrective round contains `converge-gate` → `converge-record` (`record-step converge`) → conditional `speckit.converge` (FR-001a); the `--if-needed` asymmetry comment block present (FR-009); specops-lite workflow byte-untouched (spec Edge Cases)

### Implementation for User Story 2

- [ ] T012 [US2] In src/specops/status.py: add `"converge"` to `_OPTIONAL_STEPS`; make `cmd_record_step` buffer to `specs/<feature>/.specops-pending-steps.json` via `fsutil` atomic write when the ledger is absent (replace-by-step, success message notes buffering); add the `--if-absent` mode (record only when the step has no decision in buffer or ledger; otherwise no-op, exit 0, report existing decision — remediation U1); wire the flag + updated help text in src/specops/cli.py; buffer tests in T010 pass
- [ ] T013 [US2] In src/specops/status.py `cmd_init_spec`: drain the buffer into `workflow.skipped_steps` after template render/task sync, delete the buffer file, tolerate unknown `version` with a stderr note; drain tests in T010 pass
- [ ] T014 [P] [US2] Create src/specops/templates/directives/clarify.md, checklist.md, analyze.md — each: Rule-5 no-op clause (no `specops.json` → no-op) → `specops status record-step <step> --decision run`; any recording failure on a managed repo — including an unresolvable feature (`record-step` exit 2, e.g. missing `.specify/feature.json`) — → stop-and-ask, never a forced step (FR-008, remediation U2)
- [ ] T015 [US2] Modify src/specops/templates/directives/tasks.md (after `init-spec`: `specops status record-step clarify --decision skip --if-absent` and same for `checklist` — their window closed at this seam) and src/specops/templates/directives/implement.md (session start: `specops status record-step analyze --decision skip --if-absent`); `--if-absent` makes derivation deterministic and idempotent without any decision-existence check in the directive (remediation U1)
- [ ] T016 [US2] Register `("clarify", "after_clarify", False, …)`, `("checklist", "after_checklist", False, …)`, `("analyze", "after_analyze", False, …)` in `_HOOK_SPECS` (src/specops/extension.py) and extend tests/unit/test_extension.py for the three new manifest entries
- [ ] T017 [US2] Modify src/specops/templates/workflows/specops/workflow.yml: move `clarify-record`/`checklist-record` back adjacent to their gates (drop the #50 deferral comment, reference the buffer instead); insert the converge gate block (`converge-gate` → `converge-record` → `converge-run` if) inside the `corrective-round` branch after `open-corrective-round`; add the `--if-needed` deliberate-contract comment; T011 passes

**Checkpoint**: User Stories 1–2 complete — every optional-step decision is recorded in both entry modes, including pre-ledger and the workflow converge gate. Commit once for US2.

---

## Phase 5: User Story 3 — taskstoissues has a verified, documented ledger story (Priority: P3)

**Goal**: read-only contract verified by a permanent regression test (clarification Q5) and stated in the docs ([contracts/hooks-and-workflow.md](contracts/hooks-and-workflow.md) §no-entry).

**Independent Test**: `conda run -n specops pytest tests/unit/test_taskstoissues_readonly.py` — proves the contract on fixtures.

### Tests for User Story 3 (write first, confirm they FAIL where applicable) ⚠️

- [ ] T018 [P] [US3] Create tests/unit/test_taskstoissues_readonly.py (SC-004): the built manifest contains no `before_taskstoissues`/`after_taskstoissues` SpecOps entries; the SpecOps hook registry equals exactly the documented set (converge-pre, converge, clarify, checklist, analyze, lite, specify, plan, tasks, implement) so future additions are deliberate; a fixture ledger is byte-identical across `extension install` + `update`

### Implementation for User Story 3

- [ ] T019 [US3] Document the taskstoissues read-only ledger contract in docs/commands.md (lifecycle-coverage section: no hook, no directive, ledger untouched; contingency directive only if the upstream command ever mutates repo state); T018 green confirms the code side

**Checkpoint**: All user stories complete — every lifecycle command has a defined SpecOps story; spec acceptance gate satisfiable end-to-end on fixtures. Commit once for US3.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation parity, contract bookkeeping, and final validation.

- [ ] T020 Extend docs/commands.md: `status sync-tasks` (+ `--check`/`--json`, exit contract), `record-step` pre-ledger buffering + `--if-absent` + `converge` step value + skip derivation, the buffer's transient lifecycle (may appear in intermediate commits, removed at drain — remediation A1), the workflow converge gate, and the `--if-needed` asymmetry as a deliberate contract (FR-009; same file as T019 — sequential, no [P])
- [ ] T021 [P] Update README.md and README.pt-br.md equivalently (same PR, full parity — SC-007): lifecycle recording coverage — converge recording, decision parity in both entry modes, taskstoissues read-only
- [ ] T022 [P] Add the `[Unreleased]` CHANGELOG.md entry: Feature 022 — additive `status sync-tasks`, pre-ledger record-step buffering, five new native hooks, workflow converge gate, taskstoissues read-only contract
- [ ] T023 Amend .specify/memory/constitution.md (MINOR, 1.9.3 → 1.10.0, precedent Features 010–013): Principle IV Ledger & Phase Wiring broadened to the auxiliary/optional lifecycle commands (converge recording seam, optional-step decision recording in both entry modes); update the Sync Impact Report naming the template changes shipped in this change set
- [ ] T024 Run the full quickstart validation and gates: `conda run -n specops ruff check src tests && conda run -n specops mypy src && conda run -n specops pytest` — all green (quickstart.md scenario map satisfied)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — run first
- **Foundational (Phase 2)**: empty — stories start after T001
- **US1 (Phase 3)**: independent of US2/US3
- **US2 (Phase 4)**: independent of US1 for behavior; shares `src/specops/extension.py`, `src/specops/status.py`, `src/specops/cli.py`, and `tests/unit/test_extension.py` with US1 → run after US1 (single-agent sequential order avoids same-file conflicts)
- **US3 (Phase 5)**: independent; its registry-equality test (T018) expects the final hook set → run after US1/US2
- **Polish (Phase 6)**: after all stories; T020 after T019 (same file); T023 after T014/T015/T017 (amendment names the shipped templates)

### Within Each User Story

- Tests first (confirm content/behavior tests FAIL), then implementation
- status.py before cli.py wiring (T005 → T006; T012 → T013 order is internal to status.py)
- Directive files before their `_HOOK_SPECS` registration (T007/T008 → T009; T014 → T016)
- One commit per user story at the checkpoint

### Parallel Opportunities

- US1: T002, T003, T004 in parallel (different test files); T007 ∥ T008 (different directive files)
- US2: T010 ∥ T011 (different test files); T014 parallel with nothing in status.py (different files)
- Polish: T021 ∥ T022 (different files)

---

## Parallel Example: User Story 1

```bash
# Write the three US1 test surfaces together:
Task: "Extend tests/unit/test_status.py with cmd_sync_tasks semantics tests"
Task: "Extend tests/unit/test_cli.py with status sync-tasks contract tests"
Task: "Create tests/unit/test_converge_directive.py directive-content tests"

# Then the two directive templates together:
Task: "Create src/specops/templates/directives/converge-pre.md"
Task: "Create src/specops/templates/directives/converge.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 baseline → Phase 3 (US1)
2. **STOP and VALIDATE**: converge recording + fail-closed proven on fixtures — this alone discharges the data-integrity core (silent ledger divergence impossible)
3. US1 is shippable as an MVP increment

### Incremental Delivery

1. US1 → converge recording (MVP)
2. US2 → decision parity in both entry modes + workflow converge gate
3. US3 → taskstoissues contract closed
4. Polish → docs parity (EN/PT), CHANGELOG, constitution amendment, final gates

---

## Notes

- All new CLI/manifest surfaces are additive under the Feature 021 freeze; ledger stays v7 (no migration)
- No `specops` command ever runs against this repository — fixtures only
- The #50 ordering test is inverted, not deleted: it now pins the restored gate-adjacent recording
- Spec success criteria covered: SC-001 (T002/T005), SC-002 (T003/T004/T006–T009), SC-003 (T010/T012–T017), SC-004 (T018/T019), SC-005 (T004/T014 no-op clauses), SC-006 (T003/T010 byte-identity + no-migration), SC-007 (T021)
