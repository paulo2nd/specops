---
description: "Task list for Feature 010 — End-to-End Traceability"
---

# Tasks: End-to-End Traceability

**Input**: Design documents from `specs/010-end-to-end-traceability/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (trace-cli, path-classification, trace-graph, acknowledgement-ledger), quickstart.md

**Tests**: REQUIRED. Per the Constitution (Development Workflow & Quality Gates — task gate) and the Global Definition of Done ("New CLI surfaces have unit, integration, error-path, and idempotency coverage"; "Persisted formats are versioned and have forward migration tests"), every user story ships tests before/with its implementation. Per roadmap §4, every task carries one or more `[SC-xxx]` tags.

**No-Self-Application**: `specops`/`trace` commands are NOT run against this repository, and no ledger or `context-map.yaml` is created here. All behavior is proven by fixtures under `tests/` (memory: no-specops-self-application).

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US3 (user-story tasks only)
- Paths are repository-root-relative and verified against the current worktree.

## Path Conventions

Single-project layout: engine in `src/specops/`, tests in `tests/unit` + `tests/integration`, static map fixtures in `tests/fixtures/context_maps/`, shared builders in `tests/conftest.py`, directive assets in `src/specops/templates/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared test scaffolding reused across all three stories.

- [X] T001 [P] Add shared pytest builders in `tests/conftest.py` — a ledger builder producing complete-chain and broken-chain variants (DONE task without evidence; user-story-final task without commit; dangling commit/task/finding/acknowledgement reference), an `acknowledgements`-list helper, a pre-v4 ledger builder, and `revisions/revision-X.md` finding fixtures (`[File]:[Line] - <text>` lines and an `APPROVED` line) — plus a contradictory-ownership map fixture under `tests/fixtures/context_maps/` [SC-001] [SC-005] [SC-006]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The effective-diff helper, the Ledger v3→v4 acknowledgement schema, and the `trace.py` result/status contract that every story builds on.

**⚠️ CRITICAL**: Must complete before US1/US2/US3.

- [X] T002 Add `gitops.effective_diff(repo, baseline, end="HEAD")` in `src/specops/gitops.py` — `git diff --name-only --no-renames <baseline>..HEAD` so a rename decomposes into removed-old + added-new and mode-only changes are listed; leave `name_only_diff` unchanged for existing callers; unit test in `tests/unit/test_gitops.py` (rename decomposition, mode-only inclusion, empty-diff) [SC-001] [SC-002]
- [X] T003 Bump the ledger to v4 in `src/specops/ledger.py` — `CURRENT_SCHEMA` 3→4; add `ACK_*` constants; `backfill_acknowledgements(data)` (mirrors `backfill_context_provenance`); call it from `migrate_to_current`; extend `validate_invariants` to check each acknowledgement is a mapping with non-empty `path`/`task`/`reason` and a resolvable non-orphaned `task` [SC-006] [SC-007]
- [X] T004 [P] Ledger v4 tests — v3→v4 migration backfills `acknowledgements: []` with existing tasks/cycles/provenance byte-preserved and remains readable (`tests/integration/test_ledger_migration.py`); acknowledgement-shape invariants + pre-v4 read-compat (`tests/unit/test_ledger.py`) [SC-006] [SC-007]
- [X] T005 Create `src/specops/trace.py` skeleton — the `TraceResult` contract (`status → class → exit`, mirroring `contextmap.CommandResult`), the `S_*` status constants (`TRACE_OK`, `DRIFT_CLEAN`, `DRIFT_BLOCKED`, `TRACE_INCOMPLETE`, `ACK_RECORDED`, `ACK_IDEMPOTENT`, `ACK_ALREADY_PLANNED`, `ACK_CONFLICT`, `ACK_UNKNOWN_TASK`, `USAGE_ERROR`), the `_CLASS_FOR_STATUS` map (PASS/GATE_REJECTION/INFRA_ERROR → 0/1/2), and `OUTPUT_VERSION = 1` [SC-007]

**Checkpoint**: Diff helper, v4 ledger, and trace contract ready — US1 first (MVP), then US2 and US3 in parallel.

---

## Phase 3: User Story 1 — Block only unexplained diff drift at review (Priority: P1) 🎯 MVP

**Goal**: Classify every effective-diff path as `planned`/`discovered-and-acknowledged`/`unexplained` and make `specops review` FAIL only on `unexplained` paths.

**Independent Test**: On a fixed branch/baseline/plan (+optional map), assert every path lands in exactly one class with an attribution; the `drift` gate passes when nothing is `unexplained` and FAILs (exit `1`) listing only `unexplained` paths; a `planned`/acknowledged path never FAILs; empty diff → exit `0`; no-repo/no-baseline → exit `2`; identical inputs → byte-identical output.

### Tests for User Story 1

- [X] T006 [P] [US1] Unit tests for classification in `tests/unit/test_trace.py` — precedence (discovery > planned > unexplained), rename decomposition, deleted path, symlink matched by its own path (not followed), no-map fallback (plan paths only), exactly-one-class per path, byte-stable ordering [SC-002] [SC-001] [SC-008]
- [X] T007 [P] [US1] Unit tests for the `drift` gate in `tests/unit/test_review.py` — FAIL on unexplained, PASS on all-planned/all-acknowledged, gate is terminal in `GATE_ORDER`, and `digest_drift_warning` stays non-blocking [SC-003] [SC-008]
- [X] T008 [P] [US1] Integration tests in `tests/integration/test_trace_cli.py` — `trace classify` exit/status/`--json` matrix, empty-diff exit `0`, not-a-repo/no-baseline exit `2`, read-only before/after state check, and the drift gate inside `specops review` [SC-003] [SC-007]

### Implementation for User Story 1

- [X] T009 [US1] Implement classification in `src/specops/trace.py` — resolve baseline (`ledger["baseline"]` → merge-base fallback), derive the effective diff (`gitops.effective_diff`) or `--path` override, and assign each path a class by the precedence in path-classification.md, reusing `speckit.parse_plan_path_action`, `speckit.parse_plan_context_ids`, and `contextmap._candidates_for_path` [SC-002] [SC-008]
- [X] T010 [US1] Implement `trace classify` (`cmd_classify` + human/`--json` render with `status`/`output_version`) and register the `trace_app` group with an `_emit_trace` bridge in `src/specops/cli.py` [SC-007] [SC-001]
- [X] T011 [US1] Add the terminal `drift` gate to `GATE_ORDER` in `src/specops/review.py` — reuse the effective diff from `_working_tree_gate`, FAIL only on `unexplained` paths, keep `digest_drift_warning` non-blocking, and correct its stale "deferred to Feature 010" comment [SC-003]

**Checkpoint**: US1 fully functional — review blocks only unexplained drift; `trace classify` describes every path. MVP deliverable.

---

## Phase 4: User Story 2 — Acknowledge a legitimate discovery once (Priority: P2)

**Goal**: `specops trace acknowledge <path> --task <id> --reason <text>` records a path-level acknowledgement so the drift gate reclassifies the path as `discovered-and-acknowledged`.

**Independent Test**: Acknowledge an unexplained path → it becomes `discovered-and-acknowledged`; identical re-acknowledgement is idempotent (exit `0`, no duplicate); conflicting task/reason → exit `2` with the prior record unchanged; unknown task → exit `2`, nothing written; already-`planned` path → exit `0` no-op.

### Tests for User Story 2

- [X] T012 [P] [US2] Unit tests for `cmd_acknowledge` in `tests/unit/test_trace.py` — record appended, idempotent identical triple, `ACK_CONFLICT` (exit `2`, prior untouched), `ACK_UNKNOWN_TASK` (exit `2`, nothing written), `ACK_ALREADY_PLANNED` (exit `0`, no record), and path-level binding (survives path leaving/re-entering the diff) [SC-004]
- [X] T013 [P] [US2] Integration tests in `tests/integration/test_trace_cli.py` — `trace acknowledge` exit/status/`--json`, atomic + revision-CAS write (stale write → exit `2`), and reclassification via `trace classify` after acknowledgement [SC-004] [SC-007]

### Implementation for User Story 2

- [X] T014 [US2] Implement `trace.cmd_acknowledge` — route through `status._load_for_write`/`_finalize` (identity gate + migrate + CAS + atomic), append `{path, task, reason, map_digest, at}` to `acknowledgements`, and apply the ACK semantics table from data-model.md §4 [SC-004]
- [X] T015 [US2] Register the `trace acknowledge` command (`<path>`, `--task`, `--reason`, `--json`) in `src/specops/cli.py` via the `_emit_trace` bridge [SC-004] [SC-007]

**Checkpoint**: US1 + US2 work — discoveries can be accepted without losing review control.

---

## Phase 5: User Story 3 — Report and validate the end-to-end trace (Priority: P2)

**Goal**: `specops trace report` renders the full SC→corrections chain (with a distinct Discoveries section) and `specops trace validate` fails closed on the four defect classes.

**Independent Test**: On a complete-chain fixture, `trace report` resolves every completed SC to its full chain and `trace validate` exits `0`; on seeded-defect fixtures, `trace validate` exits `1` with one distinct diagnostic each for `uncovered-sc`, `missing-link` (DONE task w/o evidence; user-story-final task w/o commit), `dangling-reference`, and `contradictory-ownership`, with no false positives on the complete fixture; JSON is byte-stable.

### Tests for User Story 3

- [X] T016 [P] [US3] Unit tests for trace-graph materialization + `trace report` in `tests/unit/test_trace.py` — SC→task→paths/contexts→commits→evidence→findings/corrections edges, completed-SC = all covering tasks DONE, the Discoveries section (reason + task), and byte-stable output [SC-006] [SC-001]
- [X] T017 [P] [US3] Unit tests for `trace.validate()` in `tests/unit/test_trace.py` — the four defects as distinct diagnostics, per-task completeness (evidence always; commit only on user-story-final task), commit-existence surfaced-not-enforced (deferred to reconcile), and zero false positives on the complete fixture [SC-005] [SC-006]
- [X] T018 [P] [US3] Integration tests in `tests/integration/test_trace_cli.py` — `trace report` and `trace validate` exit/status/`--json` matrix (complete → `0`; each seeded defect → `1`), and read-only before/after state check [SC-005] [SC-006] [SC-007]

### Implementation for User Story 3

- [X] T019 [US3] Implement the trace graph in `src/specops/trace.py` — materialize edges from ledger records (`extract_sc_ids`/`extract_coverage_tags`/`extract_task_ids`, `task["commits"]`/`evidence`/`context_provenance`), review cycles, and `revisions/revision-X.md` findings (linked by `[File]` token + `round`); compute completed-SC and per-task completeness [SC-006]
- [X] T020 [US3] Implement `trace.validate()` — emit `uncovered-sc`, `missing-link`, `dangling-reference` (commit existence surfaced, deferred to `reconcile`), and `contradictory-ownership` (via `_candidates_for_path` + provenance) defects [SC-005]
- [X] T021 [US3] Implement `trace report` and `trace validate` commands (human + `--json` with `output_version`) and register them in `src/specops/cli.py` [SC-006] [SC-005] [SC-007]

**Checkpoint**: All three stories independently functional — classification/gate, acknowledgement, and report/validate.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Directive wiring, governance, docs, and the full quality-gate pass.

- [X] T022 [P] Wire the directives — `src/specops/templates/review.md` gains a step to run the drift gate / `specops trace validate` and honor recorded acknowledgements; `src/specops/templates/directives/implement.md` gains a note to `specops trace acknowledge` a genuine discovered path (both degrade to no-ops where SpecOps is uninitialized) [SC-003] [SC-004]
- [X] T023 Apply the MINOR constitution amendment 1.5.0→1.6.0 (Principle IV directive extension: review drift gate + implement acknowledgement) in `.specify/memory/constitution.md` [SC-003]
- [X] T024 [P] Update `CHANGELOG.md` and behaviorally-equivalent EN/PT docs for the `trace` commands, the v3→v4 migration, and the drift gate [SC-006]
- [X] T025 Run the full quality gate — `ruff`, `mypy`, and `pytest` at the 85% coverage threshold — and execute the `quickstart.md` validation against fixtures (never against this repo) [SC-001] [SC-002] [SC-003] [SC-004] [SC-005] [SC-006] [SC-007] [SC-008]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**. T002/T003/T005 are independent code files (T004 depends on T003); T005 has no dependency on T002/T003.
- **User Stories (Phase 3–5)**: all depend on Foundational. US1 is the MVP and should land first; US2 and US3 are independent of each other and may proceed in parallel after Foundational.
- **Polish (Phase 6)**: depends on the user stories it documents/wires (T022 after US1+US2; T023 after US1; T025/T026 last).

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on US2/US3.
- **US2 (P2)**: after Foundational. Independent of US3. (Classification in US1 already reads the `acknowledgements` list, so US2 makes the discovery path *writable*; US1 tests seed acknowledgements directly.)
- **US3 (P2)**: after Foundational. Independent of US2.

### Within Each User Story

- Tests are written first and MUST fail before implementation.
- In `trace.py`: classification (US1) → acknowledgement (US2) and graph/validate (US3) add sibling functions to the same module — sequence the module-touching tasks within a story; different test files stay `[P]`.

### Parallel Opportunities

- T004 runs `[P]` alongside T005 (different files) once T003 lands.
- All per-story test tasks (T006/T007/T008; T012/T013; T016/T017/T018) are `[P]` — different files.
- After Foundational, US2 and US3 can be built in parallel by different developers.
- Polish T022 and T024 are `[P]`.

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together (different files):
Task: "Unit tests for classification in tests/unit/test_trace.py"
Task: "Unit tests for the drift gate in tests/unit/test_review.py"
Task: "Integration tests in tests/integration/test_trace_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (diff helper, v4 ledger, trace contract).
2. Phase 3 US1 → **STOP and VALIDATE**: `specops review` blocks only unexplained drift; `trace classify` labels every path.
3. This is a shippable increment: silent scope drift is now caught deterministically.

### Incremental Delivery

1. Foundation → US1 (drift gate) → demo.
2. Add US2 (acknowledge) → discoveries become first-class and clearable → demo.
3. Add US3 (report + validate) → full auditable trace + defect detection → demo.
4. Polish: directive wiring, constitution amendment, docs, quality gate, roadmap flip.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- Every task carries `[SC-xxx]` tags; `specops consistency` (a delivered capability, run in tests) checks that every spec Success Criterion is covered by ≥1 task.
- Commit granularity: one commit per user story (Constitution Principle III) — intermediate tasks close with `--evidence`, the story-final task with `--auto`.
- No `specops`/`trace` command is run against this repository; all behavior is proven by `tests/` fixtures.
- **Completion step (not an SC-tagged task):** at merge, flip the `ROADMAP.md` row 010 from `ACTIVE` to `MERGED` as a commit inside this feature's own PR (memory: roadmap-merged-flip-in-feature-pr).
- All eight Success Criteria are covered: SC-001 (T001,T002,T006,T016), SC-002 (T002,T006,T009), SC-003 (T007,T008,T011,T022,T023), SC-004 (T012,T013,T014,T015,T022), SC-005 (T001,T017,T018,T020), SC-006 (T001,T003,T004,T016,T019,T021,T024), SC-007 (T003,T004,T005,T008,T010,T013,T015,T018,T021), SC-008 (T006,T007,T009).
