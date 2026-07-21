---
description: "Task list for Feature 009 — Context-Aware Planning and Impact"
---

# Tasks: Context-Aware Planning and Impact

**Input**: Design documents from `specs/009-context-aware-planning/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (context-consume-cli, impact-report, provenance-ledger, plan-topology), quickstart.md

**Tests**: REQUIRED. Per the Constitution (Development Workflow & Quality Gates — task gate) and the Global Definition of Done ("New CLI surfaces have unit, integration, error-path, and idempotency coverage"; "Persisted formats are versioned and have forward migration tests"), every user story ships tests before/with its implementation. Per roadmap §4, every task carries one or more `[SC-xxx]` tags.

**No-Self-Application**: `specops`/`context` commands are NOT run against this repository, and no `context-map.yaml` or ledger is created here. All behavior is proven by fixtures under `tests/` (memory: no-specops-self-application).

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 (user-story tasks only)
- Paths are repository-root-relative and verified against the current worktree.

## Path Conventions

Single-project layout: engine in `src/specops/`, tests in `tests/unit` + `tests/integration`, fixtures in `tests/fixtures/context_maps/`, shared builders in `tests/conftest.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared test scaffolding reused across stories.

- [X] T001 [P] Add shared pytest builders in `tests/conftest.py` — a dependency-graph map builder (contexts with `dependencies`/`gates`/`risk`) and a helper to read `context_provenance` off task/review ledger records — reused by US1–US4 [SC-001] [SC-006]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared status taxonomy every new `context` command maps its outcomes onto.

**⚠️ CRITICAL**: Must complete before US1/US2/US4 CLI tasks.

- [X] T002 Add the new status constants (`plan_check_ok`, `missing_declaration`, `unknown_declared_context`, `undeclared_owner`, `impact_ok`, `unbounded_expansion`, `stale_ok`, `stale_found`, and the non-blocking `unowned` detail) and map each in `_CLASS_FOR_STATUS` (PASS/GATE_REJECTION/INFRA_ERROR) in `src/specops/contextmap.py` [SC-007]

**Checkpoint**: Status taxonomy ready — command stories can begin (US1, US2, US4 in parallel; US3 after US2).

---

## Phase 3: User Story 1 — Plan with declared context topology (Priority: P1) 🎯 MVP

**Goal**: `specops context plan-check` validates a plan's declared context IDs and paths against the map (existence-agnostic), displaying the minimal phase read set.

**Independent Test**: On a fixed map + plan, assert exit `0` with the read set when topology is valid; exit `1` with the specific status for unknown ID / undeclared owner / missing declaration; exit `0` for no-map; `unowned` path is non-blocking.

### Tests for User Story 1

- [X] T003 [P] [US1] Create plan-topology fixtures — `plan.md` samples (valid declaration, missing `SpecOps-Contexts`, unknown ID, undeclared owner, unowned path) plus their maps — in `tests/fixtures/context_maps/` [SC-004]
- [X] T004 [P] [US1] Unit tests for `speckit.parse_plan_context_ids` and the `cmd_plan_check` rule matrix (rules 1–7 of plan-topology.md: no-map pass, missing-declaration block, unknown-ID block, undeclared-owner block, unowned non-blocking, existence-agnostic, fail-closed on bad map, byte-stable output) in `tests/unit/test_contextmap_consume.py` [SC-004] [SC-001] [SC-007]
- [X] T005 [P] [US1] Integration tests for `context plan-check` (exit/status/`--json` matrix, no-map exit 0, read-only before/after state check) in `tests/integration/test_context_consume_cli.py` [SC-004] [SC-007]

### Implementation for User Story 1

- [X] T006 [US1] Implement `speckit.parse_plan_context_ids(plan_text)` (parse the `**SpecOps-Contexts**: …` line; ID-regex validated; de-duplicated) in `src/specops/speckit.py` [SC-004]
- [X] T007 [US1] Implement `contextmap.cmd_plan_check(root, *, plan, phase)` (declared IDs exist → else `unknown_declared_context`; declared path owner ∈ declared IDs → else `undeclared_owner`; unowned path → non-blocking observation; empty declaration + map present → `missing_declaration`; existence-agnostic; display minimal phase read set via existing `cmd_resolve`) in `src/specops/contextmap.py` [SC-004] [SC-001]
- [X] T008 [US1] Register the `context plan-check` subcommand (`--plan`, `--phase`, `--json`, via `_emit_context`) in `src/specops/cli.py` [SC-004] [SC-007]

**Checkpoint**: US1 fully functional and independently testable (MVP).

---

## Phase 4: User Story 2 — Explain the impact of a change (Priority: P1)

**Goal**: `specops context impact` reports directly-affected contexts + transitive **reverse** dependents, each attributed to exactly one closed-set edge, bounded by construction.

**Independent Test**: On a dependency-graph map, a changed path owned by A returns A (`ownership`) + reverse dependents (`dependency`); every `via` ∈ `{ownership,dependency,policy}`; catch-all owner → `unbounded_expansion` (exit 1); clean/empty diff → empty exit 0; no-repo/no-baseline → exit 2; `--json` byte-identical across runs.

### Tests for User Story 2

- [X] T009 [P] [US2] Create impact fixtures — dependency-graph, reverse-dependent chain, dependency cycle, catch-all/near-root owner, gates-bearing (`policy`) context, and unowned-path maps — in `tests/fixtures/context_maps/` [SC-002] [SC-003]
- [X] T010 [P] [US2] Unit tests for reverse expansion (dedup, codepoint order, edge attribution, cycle-safe), closed-edge-set enforcement (no context without a `via`; no out-of-set `via`), unowned handling, bounded vs `unbounded_expansion`, and determinism in `tests/unit/test_contextmap_consume.py` [SC-002] [SC-003] [SC-001]
- [X] T011 [P] [US2] Integration tests for `context impact` — explicit `--path`; Git-default degenerate mapping (clean tree/empty diff → exit 0; not-a-repo/no-baseline → exit 2); `--json` byte-for-byte identical — in `tests/integration/test_context_consume_cli.py` [SC-002] [SC-003] [SC-007] [SC-001]

### Implementation for User Story 2

- [X] T012 [US2] Implement the reverse-adjacency index + cycle-safe reverse DFS + closed `{ownership,dependency,policy}` attribution + `unbounded_expansion` guard (catch-all/whole-map-closure) in `src/specops/contextmap.py` [SC-002] [SC-003]
- [X] T013 [US2] Implement `contextmap.cmd_impact(root, *, paths)` — explicit paths else Git-derived change set via `gitops.name_only_diff`/`is_git_repo`/ledger baseline; degenerate-case exit mapping; surface `gates`/`risk` metadata; **phase-independent (no `--phase`)** — in `src/specops/contextmap.py` [SC-002] [SC-003] [SC-007]
- [X] T014 [US2] Register the `context impact` subcommand (`--path` repeatable, `--json`; no `--phase`) in `src/specops/cli.py` [SC-002] [SC-007]

**Checkpoint**: US2 independently testable; its resolution engine is reused by US3.

---

## Phase 5: User Story 3 — Snapshot context provenance in the ledger (Priority: P2)

**Goal**: Every task and review record carries the resolved context IDs + map digest (or an explicit no-map/invalid marker); Ledger v2→v3 migration keeps prior ledgers readable.

**Dependency**: Uses the US2 impact/resolution engine (T012) to compute `context_ids` for effective paths, and the map digest (T019).

**Independent Test**: Close a task + record a review cycle on a map fixture → both records carry `{map: present, digest, context_ids}`; no-map fixture → `{map: none}`; migrate a v1/v2 ledger → readable with `{map: none}` backfilled; changed map at review → non-blocking digest-drift warning (exit 0).

### Tests for User Story 3

- [X] T015 [P] [US3] Add v2 (and reuse v1 `make_v1_ledger`) ledger fixtures + map fixtures for provenance/migration in `tests/conftest.py` and `tests/fixtures/context_maps/` [SC-006]
- [X] T016 [P] [US3] Unit tests for `map_digest` determinism (canonical, comment/whitespace-invariant) + the three provenance variants + `validate_invariants` tolerance in `tests/unit/test_contextmap_consume.py` and `tests/unit/test_ledger.py` [SC-006] [SC-008] [SC-001]
- [X] T017 [P] [US3] Integration tests for v1→v3 and v2→v3 migration (backfill `{map: none}`, read-compat, idempotent) in `tests/integration/test_ledger_migration.py` [SC-006]
- [X] T018 [P] [US3] Unit tests for provenance recording at task close and review-cycle record, plus the non-blocking digest-drift warning, in `tests/unit/test_status.py` and `tests/unit/test_review.py` [SC-006] [SC-008]

### Implementation for User Story 3

- [X] T019 [US3] Implement `contextmap.map_digest(root)` — canonical `sha256` over parsed contexts (stdlib `hashlib`), `None` on absent map, marker semantics on invalid — in `src/specops/contextmap.py` [SC-008] [SC-001]
- [X] T020 [US3] Bump `CURRENT_SCHEMA` 2→3, extend `migrate_to_current` (backfill `context_provenance: {map: none}` on task + review records), relax `validate_invariants` to accept present/absent provenance, in `src/specops/ledger.py` [SC-006]
- [X] T021 [US3] Record `context_provenance` on task close (resolve `context_ids` via the US2 engine + `map_digest`; `{map: none}`/`{map: invalid}` markers) through `ledger.save` in `src/specops/status.py` [SC-006]
- [X] T022 [US3] Record provenance on review-cycle record and emit the non-blocking digest-drift warning (plan-time vs current digest) in `src/specops/review.py` [SC-008] [SC-006]

**Checkpoint**: US3 independently testable; provenance auditable and migration-safe.

---

## Phase 6: User Story 4 — Detect a stale context map (Priority: P3)

**Goal**: `specops context stale` reports context-map `match` patterns matching zero Git-tracked files, with owning context, deterministically, without editing the map.

**Independent Test**: On a repo where a declared pattern's files were moved/removed → `stale_found` names `(context_id, pattern)`; all-matching → `stale_ok`; results independent of untracked/gitignored files; map never modified.

### Tests for User Story 4

- [X] T023 [P] [US4] Create stale fixtures — sample repos with a moved-file pattern, a removed-file pattern, an all-matching map, and a symlink entry — under `tests/fixtures/context_maps/` (+ conftest helper) [SC-005]
- [X] T024 [P] [US4] Unit tests for stale detection (tracked-files-only, symlink-by-path/not-followed, map-patterns-only not plan create-targets, no false positives, determinism/repeatability, map unchanged) in `tests/unit/test_contextmap_consume.py` [SC-005] [SC-001]
- [X] T025 [P] [US4] Integration tests for `context stale` (`stale_found`/`stale_ok`/no-map exit 0/not-a-repo exit 2, `--json`, read-only) in `tests/integration/test_context_consume_cli.py` [SC-005] [SC-007]

### Implementation for User Story 4

- [X] T026 [US4] Implement `contextmap.cmd_stale(root)` — list Git-tracked files (`repo.git.ls_files()`), report each `match` pattern with zero tracked matches as a stale reference with its owning context, symlink-by-path, codepoint-ordered, fail-closed on bad map — in `src/specops/contextmap.py` [SC-005] [SC-001]
- [X] T027 [US4] Register the `context stale` subcommand (`--json`) in `src/specops/cli.py` [SC-005] [SC-007]

**Checkpoint**: US4 independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Directive wiring, governance, docs, and quality gates. Directive/constitution tasks are product assets edited here — never executed against this repo.

- [X] T028 [P] Additive directive wiring: run `context plan-check` and declare context IDs in `src/specops/templates/directives/plan.md` (degrades to no-op when the map is absent) [SC-004]
- [X] T029 [P] Additive directive wiring: provenance recorded at task close in `src/specops/templates/directives/implement.md` [SC-006]
- [X] T030 [P] Additive directive wiring: scope review by `context impact` + surface the non-blocking digest-drift warning in `src/specops/templates/directives/review.md` [SC-008]
- [X] T031 Constitution MINOR amendment 1.4.0→1.5.0 (extend the Empirical Verification + Ledger & Phase Wiring directives; update the Sync Impact Report) in `.specify/memory/constitution.md` — **MUST be committed in the same change set as T028–T030** (Governance: a Principle IV directive change and the amendment travel together) and **requires human approval before merge** [SC-004] [SC-006] [SC-008]
- [X] T032 [P] Update `CHANGELOG.md` (new `context plan-check`/`impact`/`stale`; Ledger v3 provenance + migration note) [SC-006]
- [X] T033 [P] Update `README.md` and `README.pt-br.md` for the three commands + provenance, keeping the two behaviorally equivalent [SC-002] [SC-005]
- [X] T034 Run the repository quality gates — `ruff check .`, `mypy src/specops`, `pytest` (`--cov-fail-under=85`) — and resolve findings [SC-001] [SC-007]

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002)** → user stories.
- **US1 (T003–T008)**, **US2 (T009–T014)**, **US4 (T023–T027)** are mutually independent — parallelizable after T002.
- **US3 (T015–T022)** depends on **US2** (reuses the T012 reverse-resolution engine) and on **T019** (`map_digest`).
- **Polish (T028–T034)** depends on all stories; **T031** (constitution amendment) also depends on explicit human approval and **MUST land in the same commit/PR as the directive edits T028–T030** (§Governance: directive-template change + constitution amendment travel in one change set); **T034** runs last.
- **Within `src/specops/contextmap.py`**: T002, T007, T012/T013, T019, T026 edit the same file and therefore serialize (not `[P]` with each other), even though their stories are independent.

## Parallel Opportunities

- All test + fixture tasks marked `[P]` within a story run in parallel (distinct files): T003/T004/T005; T009/T010/T011; T015/T016/T017/T018; T023/T024/T025.
- Across stories after T002: the US1, US2, US4 test/fixture blocks can proceed concurrently.
- Polish docs/directives T028/T029/T030/T032/T033 are `[P]` (distinct files).

## Independent Test Criteria (per story)

- **US1**: plan-check exit/status matrix + read-set display + no-map + unowned-non-blocking (SC-004, SC-001, SC-007).
- **US2**: reverse-edge impact, closed edge set, bounded/unbounded, Git-default degenerate cases, determinism (SC-002, SC-003, SC-001, SC-007).
- **US3**: provenance on every task/review record, v1/v2→v3 migration + read-compat, digest drift non-blocking (SC-006, SC-008, SC-001).
- **US4**: stale detection over tracked files, no false positives, map unchanged, determinism (SC-005, SC-001, SC-007).

## MVP Scope

**US1 alone** (T001–T008) is the MVP: it turns the static Feature 008 map into an active planning input (`context plan-check`) with the minimal phase read set displayed — the core value — and is independently shippable and testable.

## Success-Criteria Coverage

| SC | Covered by |
|----|-----------|
| SC-001 | T001, T004, T010, T011, T016, T019, T024, T026, T034 |
| SC-002 | T009, T010, T012, T013, T014, T033 |
| SC-003 | T009, T010, T011, T012, T013 |
| SC-004 | T003, T004, T005, T006, T007, T008, T028, T031 |
| SC-005 | T023, T024, T025, T026, T027, T033 |
| SC-006 | T001, T015, T016, T017, T018, T020, T021, T029, T031, T032 |
| SC-007 | T002, T005, T008, T011, T014, T025, T027, T034 |
| SC-008 | T016, T018, T019, T022, T030, T031 |
