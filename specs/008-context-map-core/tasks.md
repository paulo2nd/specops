---

description: "Task list for Context Map Core (Feature 008)"
---

# Tasks: Context Map Core

**Input**: Design documents from `specs/008-context-map-core/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: MANDATORY per the Constitution (Development Workflow & Quality Gates, task gate) — every
task is closed only with passing automated tests. Test tasks are written before their implementation
within each story.

**Tagging**: Every task carries one or more `[SC-xxx]` tags (roadmap step 4) tracing it to a spec
Success Criterion.

**Organization**: Grouped by user story (US1–US4) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel — different files, no dependency on an incomplete task.
- Engine `src/specops/contextmap.py` and `src/specops/cli.py` are shared: tasks touching the same
  file are sequential (no `[P]`), even within one story.

## Path Conventions

Single project (existing): `src/specops/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test scaffolding and the shipped asset that later phases depend on.

- [ ] T001 [P] Add a `context_map_repo` pytest fixture (a `fake_speckit_repo` with a `.specify/specops/` dir and a helper to write a map) in `tests/conftest.py` [SC-004]
- [ ] T002 [P] Create the shipped starter map template at `src/specops/templates/specops/context-map.yaml` (schema_version 1, one example context with `match`/`reads.base`) [SC-009]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The engine core and CLI wiring that ALL stories build on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Promote `ledger._atomic_write` to a public `ledger.atomic_write` (keep a private alias for back-compat) in `src/specops/ledger.py` so `context init` reuses one interruption-safe write idiom [SC-009]
- [ ] T004 Create engine module `src/specops/contextmap.py` with the map-path resolver (`.specify/specops/context-map.yaml`), schema constants (`CURRENT_SCHEMA=1`, `OLDEST_SUPPORTED=1`), `classify()` (current/too_new/unsupported), and a `migrate_to_current()` identity scaffold (with a forward-migration test asserting a v1 map is returned unchanged and an unsupported version is rejected) [SC-010]
- [ ] T005 Implement the five-state `load()` classification (`no_map_present`, `malformed`, `schema_invalid`, `empty_valid`, `valid`) as a discriminated result in `src/specops/contextmap.py` [SC-005]
- [ ] T006 Implement the stdlib gitignore-style glob matcher and the total specificity comparator (literal-prefix → wildcard-count → segment-count, codepoint tie-break) in `src/specops/contextmap.py` [SC-007]
- [ ] T007 Register the `context` Typer sub-app in `src/specops/cli.py` and wire the outcome/status mapping (reuse `outcome.render`/`exit_for`: PASS→0, GATE_REJECTION→1, INFRA_ERROR→2, plus the `status` + `output_version` fields) [SC-013]

**Checkpoint**: Engine load/classification/matching + CLI plumbing ready.

---

## Phase 3: User Story 1 — Author and validate a context map (Priority: P1) 🎯 MVP

**Goal**: `context init` scaffolds a schema-valid starter map (idempotent); `context validate`
reports success or a precise, one-pass diagnostic per defect class.

**Independent Test**: `context init` on an empty repo writes a valid map; re-run does not mutate;
`context validate` exits 0 for a valid map and exits 1 naming each of the seven defect classes.

### Tests for User Story 1 (write first)

- [ ] T008 [P] [US1] Create validation fixtures — one per defect class (`invalid_path_pattern`, `unsafe_path_traversal`, `duplicate_context_id`, `ambiguous_ownership`, `dangling_dependency`, `dependency_cycle`, `unsupported_schema_version`) plus `valid` and `empty_valid` — in `tests/fixtures/context_maps/` [SC-002] [SC-005]
- [ ] T009 [US1] Write unit tests for validation (each defect class → distinct attributed `code`, one-pass aggregation, fail-closed, version diagnostic, empty-valid) in `tests/unit/test_contextmap.py` [SC-002] [SC-003] [SC-010]
- [ ] T010 [P] [US1] Write integration tests for `context init` (create → status `created`; re-run → `already_exists`, no mutation; no `.specify/` → exit 2) and `context validate` exit/status in `tests/integration/test_context_cli.py` [SC-009] [SC-013]

### Implementation for User Story 1

- [ ] T011 [US1] Implement the validation engine (all seven defect classes, one-pass aggregation, distinct `code`s; gate refs structural-only; dangling-dep distinct from cycle) in `src/specops/contextmap.py` [SC-002] [SC-003]
- [ ] T012 [US1] Implement `cmd_init` (atomic write via `ledger.atomic_write`, never overwrite, idempotent report) in `src/specops/contextmap.py` [SC-009]
- [ ] T013 [US1] Implement `cmd_validate` and wire the `context init` / `context validate` CLI subcommands (human + `--json`) in `src/specops/cli.py` [SC-002] [SC-013]

**Checkpoint**: US1 fully functional and independently testable (MVP).

---

## Phase 4: User Story 2 — Deterministically resolve context for a path or ID (Priority: P1)

**Goal**: `context resolve --path|--id [--phase]` returns an ordered, phase-specific Resolved Context
Package with a cycle-safe, deduplicated, per-edge-attributed expanded read set — identically on every run.

**Independent Test**: For a fixed map, `resolve` by ID and by path returns byte-for-byte identical
ordered packages across runs; overlapping rules pick the most-specific winner; a true tie fails
validation; unknown path/ID → no-match (exit 0); both/neither selector → exit 2.

### Tests for User Story 2 (write first)

- [ ] T014 [P] [US2] Create resolution fixtures (overlapping-rules, equal-specificity tie, dependency-expansion, dependency-cycle, base-fallback, no-base) in `tests/fixtures/context_maps/` [SC-007] [SC-011] [SC-012]
- [ ] T015 [US2] Write unit tests for resolution — determinism (repeat = identical), specificity winner per deciding dimension + tie→ambiguous, expansion (dedup/order/`via` attribution), cycle (bounded, IDs listed), phase `base` fallback + explicit empty — in `tests/unit/test_contextmap.py` [SC-001] [SC-007] [SC-008] [SC-011] [SC-012]
- [ ] T016 [P] [US2] Write integration tests for `context resolve` (`--path`/`--id`/`--phase`/`--json`, selector contract both/neither→exit 2, unknown→no-match) and the stable JSON package shape in `tests/integration/test_context_cli.py` [SC-006] [SC-015]

### Implementation for User Story 2

- [ ] T017 [US2] Implement resolution — candidate matching, most-specific selection, phase read-set with `base`/empty fallback (`read_set_source`), and Resolved Context Package assembly — in `src/specops/contextmap.py` [SC-001] [SC-007] [SC-012]
- [ ] T018 [US2] Implement cycle-safe transitive dependency expansion (depth-first in declaration order, dedup keeping first occurrence, `via` per-edge attribution) in `src/specops/contextmap.py` [SC-011] [SC-008]
- [ ] T019 [US2] Implement `cmd_resolve` and wire the `context resolve` CLI with mutually exclusive `--path`/`--id` + optional `--phase` (both/neither → usage error exit 2) in `src/specops/cli.py` [SC-015] [SC-006]

**Checkpoint**: US1 and US2 both independently functional.

---

## Phase 5: User Story 3 — Explain why a context was resolved (Priority: P2)

**Goal**: `context explain` emits a deterministic, ordered Reason Trace naming the candidates, the
selected context, the deciding specificity dimension, the read-set source, and the contributing
dependency/gate edges.

**Independent Test**: For a path matching multiple rules, `explain` lists candidates in comparator
order and names which dimension decided; identical across runs.

### Tests for User Story 3 (write first)

- [ ] T020 [US3] Write unit tests for the reason trace (candidate ordering, `deciding_dimension` per case incl. `only_candidate`, determinism) in `tests/unit/test_contextmap.py` [SC-014] [SC-001]
- [ ] T021 [P] [US3] Write integration tests for `context explain --json` (trace shape, no-match, invalid-map fail-closed) in `tests/integration/test_context_cli.py` [SC-006] [SC-014]

### Implementation for User Story 3

- [ ] T022 [US3] Implement the reason-trace builder (candidates, `selected` + `deciding_dimension`, `read_set_source`, `dependency_edges`, `gates`) in `src/specops/contextmap.py` [SC-014]
- [ ] T023 [US3] Implement `cmd_explain` and wire the `context explain` CLI (same `--path`/`--id`/`--phase` selectors as resolve) in `src/specops/cli.py` [SC-014] [SC-006]

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 — Operate safely when no map exists (Priority: P2)

**Goal**: Every read-only command treats an absent map as a first-class `no_map_present` state — no
crash, no false success, no writes — and the five map states are each distinguishable.

**Independent Test**: In a repo with no map, `validate`/`resolve`/`explain` each report
`no_map_present` (exit 0) and create/mutate nothing; the five states are distinct in human + JSON.

### Tests for User Story 4 (write first)

- [ ] T024 [US4] Write unit tests: `load()` on an absent map → `no_map_present`, no filesystem writes on any path (incl. error paths) in `tests/unit/test_contextmap.py` [SC-004]
- [ ] T025 [P] [US4] Write integration tests: all three read-only commands on an absent map → `no_map_present` exit 0, no file created; five-state distinguishability (absent/malformed/schema-invalid/empty/valid) in `tests/integration/test_context_cli.py` [SC-004] [SC-005]

### Implementation for User Story 4

- [ ] T026 [US4] Wire the absent-map (`no_map_present`) outcome and the read-only-on-every-path guarantee across `context validate`/`resolve`/`explain` in `src/specops/cli.py` and finalize the absent-map branch in `src/specops/contextmap.py` [SC-004]

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Contract stability, docs, and repository quality gates.

- [ ] T027 [P] Add the exit-code/status matrix test and a stable-JSON-shape snapshot test across all commands in `tests/integration/test_context_cli.py` [SC-006] [SC-013]
- [ ] T028 [P] Document the `context` command group in `README.md` and `README.pt-br.md` (behaviorally equivalent, EN/PT) [SC-013]
- [ ] T029 [P] Add a `CHANGELOG.md` entry for the versioned context map and the four `context` commands (note the new `.specify/specops/context-map.yaml` asset) [SC-010]
- [ ] T030 Execute the `quickstart.md` SC→test validation matrix and confirm every SC-001..SC-015 has passing coverage [SC-001] [SC-002] [SC-003] [SC-004] [SC-005] [SC-006] [SC-007] [SC-008] [SC-009] [SC-010] [SC-011] [SC-012] [SC-013] [SC-014] [SC-015]
- [ ] T031 Run `ruff check .`, `mypy src/specops`, and `pytest -q`; resolve to repository thresholds [SC-001] [SC-013]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; **blocks all user stories**. Internal order: T003 (independent) ∥ T004 → T005 → T006 (same file, sequential); T007 after T004.
- **User Stories (Phases 3–6)**: all depend on Foundational. US1 (P1) is the MVP. US2 (P1) depends only on Foundational. US3 (P2) depends on US2's resolution engine (the trace explains a resolution). US4 (P2) depends on Foundational's `load()` and the three commands existing (US1–US3 wiring), so it is sequenced last to verify cross-command behavior.
- **Polish (Phase 7)**: depends on US1–US4.

### Within Each User Story

- Tests are written first and must fail before implementation (constitution task gate).
- Engine functions (`contextmap.py`) before CLI wiring (`cli.py`).
- Same-file tasks are sequential; the constitution's preferred commit granularity is one commit per user story.

### Parallel Opportunities

- T001 ∥ T002 (Setup, different files).
- Within a story: the fixtures task and the integration-test task are `[P]` with the unit-test task only when they touch different files (fixtures / `test_context_cli.py` vs `test_contextmap.py`).
- Polish T027 ∥ T028 ∥ T029 (different files).
- US1 and US2 (both P1) can be staffed in parallel by different developers **after** Foundational, coordinating on `contextmap.py`/`cli.py` merge points.

---

## Parallel Example: User Story 1

```bash
# After Foundational, launch the independent-file tasks together:
Task: "T008 Create validation fixtures in tests/fixtures/context_maps/"
Task: "T010 Write integration tests in tests/integration/test_context_cli.py"
# Then T009 (unit tests) → T011 → T012 (contextmap.py, sequential) → T013 (cli.py)
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (blocks everything) → 3. Phase 3 US1 →
4. **STOP and VALIDATE**: a repo can author and validate a context map end-to-end.

### Incremental Delivery

Foundation → US1 (author+validate, MVP) → US2 (resolve) → US3 (explain) → US4 (safe-when-absent) →
Polish. Each story adds value and stays independently testable; determinism (SC-001) and the JSON
contract (SC-006) are guarded continuously and locked in Polish.

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- Every task is `[SC-xxx]`-tagged for traceability; `/speckit-analyze` will verify full SC coverage.
- This feature is developed with plain Spec Kit — no `context` command is run against this
  repository; all behavior is proven via `tests/fixtures/context_maps/` (No Self-Application).
- Verify tests fail before implementing; commit per user story (final task with evidence).
