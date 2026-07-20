---
description: "Task list for Ledger v2 Integrity"
---

# Tasks: Ledger v2 Integrity

**Input**: Design documents from `/specs/006-ledger-v2-integrity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Mandatory per the Constitution (Development Workflow & Quality Gates — task gate): every
task is closed only with passing automated tests. Each story includes its own test tasks.

**SC tags**: Per the roadmap protocol, every task carries one or more `[SC-xxx]` tags mapping it to a
Success Criterion in spec.md.

**Organization**: Tasks are grouped by user story so each story is an independently testable increment.

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 (user-story phases only)
- Exact file paths are included in every task

## Path Conventions

Single project: `src/specops/` and `tests/` at repository root (per plan.md Structure Decision).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test scaffolding and the empty module boundary shared by all stories.

- [x] T001 [P] Add synthetic ledger factory fixtures (v1 date-only/no-`schema_version`, and valid v2) plus a `ledger_bytes`/mtime snapshot helper to `tests/conftest.py` [SC-001]
- [x] T002 [P] Create `src/specops/ledger.py` with typed public-API stubs (`classify`, `migrate_to_current`, `validate_invariants`, `validate_identity`, `load`, `save`, `now_utc`) and module docstring [SC-001]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The v2 schema core in `ledger.py`, the updated template, stable serialization, the
atomic load/save refactor, and invariant enforcement — everything every story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Define schema constants (`CURRENT_SCHEMA=2`, `OLDEST_SUPPORTED=1`, `DEFAULT_WORKFLOW_LANE`) and implement `classify(data)` returning `current|migratable|too_new|unsupported` in `src/specops/ledger.py` [SC-001]
- [x] T004 [P] Implement timezone helpers (`now_utc()`, `to_aware(value)` interpreting naive as UTC) with RFC3339 `+00:00` serialization, plus `artifact_for_phase(phase)` mapping each phase to its artifact (SPECIFY→`spec.md`, PLAN→`plan.md`, TASKS/IMPLEMENT/REVIEW→`tasks.md`, DONE→`tasks.md`), in `src/specops/ledger.py` [SC-007]
- [x] T005 [P] Update `src/specops/templates/status.yaml` to the v2 shape: `schema_version: 2`, `revision: 1`, `workflow_lane: "full"`, `active_artifact`, timezone-aware `created_at`/`updated_at`, and enriched `recovery` (`last_consistent_revision`, `last_consistent_at`, `migrated_from_backup`) [SC-007]
- [x] T006 Implement atomic `load()`/`save()` in `src/specops/ledger.py` — refactor the existing `status._load_ledger`/`_save_ledger` (tmp→fsync→`os.replace`) and add the logical-content-diff stable no-op write (skip write + no `updated_at` change when nothing logical changed) [SC-005] (depends on T003, T004)
- [x] T007 [P] Implement `validate_invariants(data)` (I-PHASE-1/2, I-TASK-1/2/3, I-REC-1, I-REV-1/2/3 from data-model.md) returning violation strings in `src/specops/ledger.py` [SC-003]
- [x] T008 Refactor `src/specops/status.py` to route every read/write through `ledger.load`/`ledger.save`, have `cmd_init_spec` write the full v2 template fields for new ledgers, and set `active_artifact = artifact_for_phase(current_phase)` on init-spec **and** on every `cmd_transition_phase` so the field tracks the current phase (FR-027/FR-028) [SC-005] (depends on T004, T006)
- [x] T009 Wire `validate_invariants` into every state-changing command in `src/specops/status.py` so an invariant violation fails closed before any write [SC-003] (depends on T007, T008)
- [x] T010 [P] Unit tests for `classify`, timestamp helpers, `artifact_for_phase`, stable no-op serialization, and invariants in `tests/unit/test_ledger.py` [SC-005]
- [x] T011 Run the existing suite and fix regressions from the load/save refactor (`tests/unit/test_status.py`, `tests/integration/test_ledger.py`, `tests/unit/test_reconcile.py`) [SC-005] (depends on T008)

**Checkpoint**: Foundation ready — v2 ledgers are created, serialized stably, and invariant-checked.

---

## Phase 3: User Story 1 - Upgrade a v1 ledger to v2 without losing work (Priority: P1) 🎯 MVP

**Goal**: Deterministic, lossless v1→v2 migration with a retained pre-migration backup, triggered
automatically on first write and via an explicit `specops status migrate`; read-only inspection
never migrates and stays safe on abnormal ledgers.

**Independent Test**: Take a supported v1 ledger; run a state change (or `status migrate`) → it becomes
`schema_version: 2` with every task/evidence/review preserved and a backup recorded; a read-only
command beforehand leaves the file byte-unchanged.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [x] T012 [P] [US1] Integration test: lossless v1→v2 migration preserves tasks/evidence/review cycles and creates a backup referenced by `recovery.migrated_from_backup`, in `tests/integration/test_ledger_migration.py` [SC-001]
- [x] T013 [P] [US1] Unit tests: `too_new` and `unsupported` refuse state changes (exit 1, no write); read-only emits a diagnostic without mutating, in `tests/unit/test_ledger.py` [SC-001] [SC-006]

### Implementation for User Story 1

- [x] T014 [US1] Implement `migrate_to_current(data)` as ordered pure v1→v2 steps (back-fill `schema_version`, `revision`, `workflow_lane`, `active_artifact`, zone-aware timestamps, enriched recovery; preserve evidence byte-for-byte) in `src/specops/ledger.py` [SC-001] [SC-007]
- [x] T015 [US1] Implement the pre-migration backup under `.specify/.specops-backup/` (reuse the `migration.BackupSet` convention) and record its path in `recovery.migrated_from_backup` in `src/specops/ledger.py` [SC-001] (depends on T014)
- [x] T016 [US1] Auto-migrate migratable ledgers on the first state-changing operation in `src/specops/status.py`; refuse `too_new`/`unsupported` (fail closed), never migrate on read-only [SC-001] (depends on T014, T015)
- [x] T017 [US1] Add `cmd_migrate(root)` to `src/specops/status.py` and register the `status migrate` subcommand in `src/specops/cli.py` per contracts/cli-status-migrate.md (idempotent; `already current` no-op) [SC-001] (depends on T016)
- [x] T018 [US1] Make read-only surfaces safe on abnormal ledgers: `cmd_show` in `src/specops/status.py` and `run` in `src/specops/reconcile.py` report best-effort status + a diagnostic for `too_new`/`unsupported`/malformed, never mutating [SC-006] (depends on T016)

**Checkpoint**: US1 fully functional — v1 ledgers migrate losslessly with backup; read-only is safe.

---

## Phase 4: User Story 2 - Prevent lost updates from concurrent/stale sessions (Priority: P1)

**Goal**: A monotonic `revision` with optimistic compare-and-swap on write rejects stale writes and
guarantees at most one concurrent writer wins, with no lost or interleaved data.

**Independent Test**: Two loads at the same revision; the first save commits, the second (stale) save
is rejected with a retry signal and the first change survives; a re-read + retry then succeeds.

### Tests for User Story 2 ⚠️ (write first, ensure they fail)

- [x] T019 [P] [US2] Integration tests: stale-write rejection preserves the first change; concurrent writers yield a single winner with intact data, in `tests/integration/test_ledger.py` [SC-002]
- [x] T020 [P] [US2] Unit tests: `revision` advances by exactly 1 on a real change and does NOT bump on a stable no-op save, in `tests/unit/test_ledger.py` [SC-002] [SC-005]

### Implementation for User Story 2

- [x] T021 [P] [US2] Add `StaleLedgerError(SpecopsError)` (exit 1) with a "ledger moved on — re-read and retry" message in `src/specops/errors.py` [SC-002]
- [x] T022 [US2] Implement revision capture + compare-and-swap and a short-lived `status.yaml.lock` (`O_CREAT|O_EXCL`, released in `finally`) inside `ledger.save()`; commit `revision = base_revision + 1` only when the on-disk revision matches, else raise `StaleLedgerError` in `src/specops/ledger.py` [SC-002] (depends on T021, and Foundational T006)
- [x] T023 [US2] Thread `base_revision` (captured at load) through every state change in `src/specops/status.py` so all commands go through the CAS path [SC-002] (depends on T022)

**Checkpoint**: US1 + US2 both work — migration is lossless and concurrent writes cannot lose data.

---

## Phase 5: User Story 3 - Refuse state changes on inconsistent workspace identity (Priority: P2)

**Goal**: Before any state change, validate feature, branch, and branch-point baseline; refuse and
name the diverged dimension on mismatch; read-only stays available.

**Independent Test**: With a valid v2 ledger, switch branch / rename the feature dir / make the
baseline unreachable → each state change is refused naming the diverged dimension; a consistent
workspace passes.

### Tests for User Story 3 ⚠️ (write first, ensure they fail)

- [x] T024 [P] [US3] Integration tests: branch mismatch, unresolvable feature, and unreachable baseline each refuse state changes (exit 1, no write) naming the dimension; a consistent workspace passes, in `tests/integration/test_ledger.py` [SC-003]

### Implementation for User Story 3

- [x] T025 [US3] Implement `validate_identity(root, repo, data)` checking feature (`speckit.resolve_feature_dir`), branch (`gitops.current_branch`), and baseline (`gitops.is_ancestor`) and returning the diverged dimension, in `src/specops/ledger.py` [SC-003]
- [x] T026 [US3] Wire `validate_identity` into every state-changing command in `src/specops/status.py` before any mutation (fail closed, message names the dimension); leave read-only paths ungated [SC-003] (depends on T025)

**Checkpoint**: US1–US3 work — state changes are lossless-migrating, concurrency-safe, and identity-gated.

---

## Phase 6: User Story 4 - Survive an interrupted write with a readable ledger (Priority: P2)

**Goal**: An interrupted write always leaves the previous complete, valid ledger; recovery metadata
identifies the last consistent state.

**Independent Test**: Inject an interruption between the `.tmp` write and `os.replace`; the on-disk
ledger is the complete previous committed state (no truncation), and `recovery.last_consistent_*`
identifies it.

### Tests for User Story 4 ⚠️ (write first, ensure they fail)

- [x] T027 [P] [US4] Integration test: an injected interruption during persistence leaves the prior complete/valid ledger (no truncated/partial file), in `tests/integration/test_ledger.py` [SC-004]
- [x] T028 [P] [US4] Unit test: each committed save records `recovery.last_consistent_revision`/`last_consistent_at` for the last committed state, in `tests/unit/test_ledger.py` [SC-004]

### Implementation for User Story 4

- [x] T029 [US4] Populate `recovery.last_consistent_revision` and `recovery.last_consistent_at` on every committed save in `src/specops/ledger.py` [SC-004] (depends on T022)
- [x] T030 [US4] Formalize the interruption guarantee in `ledger.save()`: keep the atomic tmp→fsync→`os.replace` order, fsync the containing directory after replace, and document the guarantee, in `src/specops/ledger.py` [SC-004] (depends on T006, T022)

**Checkpoint**: All four stories functional and independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, changelog, and full-suite validation.

- [x] T031 [P] Record Ledger v2 behavior and the v1→v2 migration/backup in `CHANGELOG.md` [SC-001]
- [x] T032 [P] Update the ledger sections of `README.md` and `README.pt-br.md` (behaviorally equivalent EN/PT) to describe v2 fields, `status migrate`, and identity/concurrency guarantees [SC-001]
- [x] T033 Run all quickstart.md scenarios and the quality gates (`ruff check .`, `mypy src`, `pytest` with `--cov-fail-under=85`); resolve any failures [SC-004]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**.
- **User Stories (Phases 3–6)**: all depend on Foundational.
  - US1 (P1) and US2 (P1) are the MVP integrity pair; US3 (P2) and US4 (P2) follow.
  - US4's recovery-metadata task (T029) depends on US2's CAS save (T022), since both live in
    `ledger.save()`; sequence US2 before US4 to avoid same-file churn.
- **Polish (Phase 7)**: depends on all targeted stories being complete.

### User Story Dependencies

- **US1 (P1)**: after Foundational. Independent.
- **US2 (P1)**: after Foundational. Independent of US1 (touches `save()` CAS, not migration).
- **US3 (P2)**: after Foundational. Independent (adds the identity gate).
- **US4 (P2)**: after Foundational; shares `ledger.save()` with US2 — do US2 first.

### Within Each User Story

- Tests are written and fail before implementation.
- `ledger.py` core before `status.py`/`cli.py` wiring.
- Same-file tasks run sequentially; cross-file tasks marked [P] run in parallel.

### Parallel Opportunities

- Setup: T001, T002 in parallel.
- Foundational: T004, T005, T007 in parallel (distinct concerns/files); T010 in parallel with impl once its targets exist.
- US1 tests T012, T013 in parallel; US2 tests T019, T020 in parallel; US4 tests T027, T028 in parallel.
- T021 (errors.py) parallel with US2 test authoring.
- Polish: T031, T032 in parallel.

---

## Parallel Example: User Story 1

```bash
# Author both US1 test files together (they fail first):
Task: "Integration test lossless v1→v2 migration + backup in tests/integration/test_ledger_migration.py"
Task: "Unit tests too-new/unsupported refusal + read-only diagnostics in tests/unit/test_ledger.py"
```

---

## Implementation Strategy

### MVP (Integrity pair: US1 + US2)

1. Phase 1 Setup → Phase 2 Foundational (critical — blocks everything).
2. Phase 3 US1 (lossless migration + backup) → validate independently.
3. Phase 4 US2 (concurrency / lost-update protection) → validate independently.
4. **STOP and VALIDATE**: the two P1 integrity guarantees are the shippable MVP.

### Incremental Delivery

1. Foundational → v2 ledgers created and invariant-checked.
2. US1 → migration lossless with backup (demo).
3. US2 → concurrency-safe (demo).
4. US3 → identity-gated (demo).
5. US4 → interruption-safe with recovery metadata (demo).
6. Polish → docs, changelog, full-suite green.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- Every task carries a `[SC-xxx]` tag; all of SC-001…SC-007 are covered (SC-001: T001-T003,T012,T014-T017,T031-T032; SC-002: T019-T023; SC-003: T007,T009,T024-T026; SC-004: T027-T030,T033; SC-005: T006,T008,T010,T011,T020; SC-006: T013,T018; SC-007: T004,T005,T014).
- Evidence format is deliberately untouched (FR-030; deferred to Feature 012).
- No self-application: all validation is via `tests/` fixtures, never by running `specops` against this repo.
- Commit at the user-story level (constitution Principle III); intermediate tasks close with `--evidence`.
