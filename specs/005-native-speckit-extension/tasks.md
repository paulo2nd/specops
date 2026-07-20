---

description: "Task list for Native Spec Kit Extension"
---

# Tasks: Native Spec Kit Extension

**Input**: Design documents from `specs/005-native-speckit-extension/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Mandatory per Constitution (Development Workflow & Quality Gates — task gate). Each story
includes tests written before its implementation.

**SC tags**: Every task carries one or more `[SC-xxx]` coverage tags (Roadmap §4 / Global DoD). All
nine success criteria (SC-001…SC-009) are covered by at least one task.

**Organization**: Tasks are grouped by user story (US1 = native install, US2 = legacy migration,
US3 = lifecycle management) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (setup, foundational, and polish tasks have no story label)
- All paths are repository-relative and verified against the worktree (Principle IV)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare packaging and the template asset the native path ships.

- [x] T001 [P] Create the hook-manifest template asset `src/specops/templates/extensions.yml` — a minimal SpecOps-owned skeleton (hook points `after_specify`/`before_plan`/`after_tasks`/`after_implement`, a `commands:` section, and a `specops.cli_compat.min_cli_version` field) per contracts/extensions-manifest.md [SC-001]
- [x] T002 [P] Bump the package version in `pyproject.toml` to `0.3.0` (the native-extension floor, research R7) and confirm `src/specops/templates/**` (incl. `extensions.yml`) is packaged by the existing `include` glob [SC-001]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared engine every story depends on — manifest I/O, detection, integration/command
resolution, CLI-compat gate, config metadata, and the CLI subgroup skeleton.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] Add native-path resolvers to `src/specops/speckit.py`: `extensions_yml_path(root)` and `command_dir(...)` (reuse `resolve_prompt_targets` + `derive_review_path` to locate each installed integration's command path) [SC-001,SC-006]
- [x] T004 [P] Implement the CLI-compatibility gate in `src/specops/compat.py`: read installed version via `importlib.metadata.version("speckit-specops")`, compare against the `min_cli_version` floor (`>= 0.3.0`, research R7), return a satisfied/unsatisfied descriptor; missing or out-of-range ⇒ unsatisfied (FR-016) [SC-001]
- [x] T005 [P] Extend `src/specops/config.py` defaults/merge to persist `min_cli_version` while preserving existing and unknown keys (`merge_preserve`) [SC-001]
- [x] T006 Implement the manifest engine core in `src/specops/extension.py`: parse `.specify/extensions.yml` preserving foreign (non-`specops`) entries, build SpecOps hook entries from `templates/directives/*.md`, atomic write (temp-then-rename), and a `semantically_equal(a, b)` comparator over parsed SpecOps entries/commands/cli_compat (ignoring order/whitespace/timestamps) [SC-001,SC-002]
- [x] T007 Implement installation-state detection in `src/specops/migration.py`: `detect_state(root)` → `absent` | `native` | `legacy` | `native+legacy` (native via `extension: specops` entries; legacy via `initializer._scan_markers` over resolved host prompt files) [SC-001,SC-003,SC-004]
- [x] T008 Add the `extension` Typer subgroup skeleton to `src/specops/cli.py` (mirror the `status` subgroup) and wire the read-only `specops extension status` command to `migration.detect_state` + `compat` (never mutates state) [SC-001,SC-004]
- [x] T009 [P] Foundational unit tests in `tests/unit/test_extension.py` (manifest parse preserves foreign entries; atomic write; `semantically_equal` true/false cases) and `tests/unit/test_compat.py` (present / missing / out-of-range) [SC-001,SC-002]

**Checkpoint**: Engine, detection, compat gate, and CLI surface ready — stories can begin.

---

## Phase 3: User Story 1 — Native install into a Spec Kit repository (Priority: P1) 🎯 MVP

**Goal**: A single `specops extension install` registers SpecOps hooks + review command through the
host's native mechanism, touching zero host-owned files, offline-capable, idempotent, across every
installed integration, and failing closed when the CLI is missing/incompatible.

**Independent Test**: In a clean fixture repo, run install once → `.specify/extensions.yml` has the
four hook entries + a command per integration, every host `SKILL.md` hash is unchanged, and a second
run reports `unchanged`.

### Tests for User Story 1 (write first, ensure they FAIL) ⚠️

- [x] T010 [P] [US1] Integration test in `tests/integration/test_extension_lifecycle.py`: clean-repo install registers hooks + command and leaves **zero** host-owned files modified (hash comparison) [SC-001]
- [x] T011 [P] [US1] Integration test in `tests/integration/test_extension_lifecycle.py`: install is idempotent — second run is a semantic no-op (no duplicate hook/command entries) [SC-002]
- [x] T012 [P] [US1] Integration test in `tests/integration/test_extension_lifecycle.py`: install succeeds with networking disabled (offline) [SC-005]
- [x] T013 [P] [US1] Integration test in `tests/integration/test_extension_lifecycle.py`: repo with two installed integrations gets one command registration per integration; hook entries written once [SC-006]
- [x] T014 [P] [US1] Integration test in `tests/integration/test_extension_lifecycle.py`: missing/incompatible CLI ⇒ install exits 1, names the CLI, and writes nothing (fail-closed) [SC-001]

### Implementation for User Story 1

- [x] T015 [US1] Implement command registration in `src/specops/extension.py`: install the SpecOps-owned review command file per integration (reuse `initializer._install_review` / `derive_review_path`) and record each under `commands:` [SC-001,SC-006]
- [x] T016 [US1] Implement `install(root)` orchestration in `src/specops/extension.py`: fail-closed pre-checks (git, Spec Kit, CLI-compat via `compat`, ≥1 integration), then write hook entries + register commands + create/merge `specops.json`; return created/updated/unchanged using `semantically_equal` [SC-001,SC-002,SC-005,SC-006]
- [x] T017 [US1] Wire `specops extension install` in `src/specops/cli.py` to `extension.install` with `--non-interactive`; map failures through the existing error boundary (exit 1) [SC-001]

**Checkpoint**: US1 fully functional — native install is a shippable MVP.

---

## Phase 4: User Story 2 — Migrate a legacy marker-injected installation (Priority: P2)

**Goal**: `specops extension migrate` converts a legacy install to native without losing config or
ledgers, stripping SpecOps markers from host files with a pre-edit backup that auto-restores on
failure.

**Independent Test**: From a legacy fixture (markers + `specops.json` + a feature ledger), migrate →
markers gone, native registered, config and ledger unchanged; a fault mid-run restores all touched
host files exactly.

### Tests for User Story 2 (write first, ensure they FAIL) ⚠️

- [ ] T018 [P] [US2] Integration test in `tests/integration/test_extension_lifecycle.py`: legacy→native migration removes all `SPECOPS:BEGIN` markers, registers native, and leaves `specops.json` + every feature ledger unchanged [SC-003]
- [ ] T019 [P] [US2] Integration test in `tests/integration/test_extension_lifecycle.py`: a fault injected after the first host file is stripped restores **all** touched host files to exact pre-migration bytes and exits 1 [SC-008]
- [ ] T020 [P] [US2] Unit test in `tests/unit/test_migration.py`: backup set create/restore round-trips bytes (sha256), and marker strip preserves all content outside markers [SC-003,SC-008]
- [ ] T021 [P] [US2] Integration test in `tests/integration/test_extension_lifecycle.py`: migrating an already-native repo is a no-op reporting `already native`, exit 0 [SC-002]

### Implementation for User Story 2

- [ ] T022 [US2] Implement the migration backup set in `src/specops/migration.py`: back up each host file about to be edited under `.specify/.specops-backup/<run_id>/`, and `restore_all()` to exact bytes on failure/abort, discarding backups on success [SC-008]
- [ ] T023 [US2] Implement `migrate(root)` orchestration in `src/specops/migration.py`: same fail-closed pre-checks as install, then ordered interruption-safe flow — backup → strip markers via `initializer.remove_block` → `extension.install`; on any error `restore_all()` and exit 1; preserve `specops.json` + ledgers [SC-003,SC-008]
- [ ] T024 [US2] Wire `specops extension migrate` in `src/specops/cli.py` to `migration.migrate` [SC-003]

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 — Manage the extension lifecycle (Priority: P3)

**Goal**: `update`, `disable`, `enable`, and `remove [--purge]` manage the installed extension —
idempotent, state-preserving on disable/enable, clean on remove, with an explicit purge opt-in.

**Independent Test**: From an installed repo, run update → disable → enable → remove → and (from a
fresh install) remove --purge; assert idempotency, disable retains config/ledgers, remove leaves no
host-owned file modified, and purge additionally deletes config + ledgers.

### Tests for User Story 3 (write first, ensure they FAIL) ⚠️

- [ ] T025 [P] [US3] Integration test in `tests/integration/test_extension_lifecycle.py`: disable unregisters hooks + command from the host surface while retaining `specops.json` and ledgers; `status` then reports native `absent` [SC-004]
- [ ] T026 [P] [US3] Integration test in `tests/integration/test_extension_lifecycle.py`: enable re-registers identically to a fresh install (semantic equivalence) [SC-002,SC-004]
- [ ] T027 [P] [US3] Integration test in `tests/integration/test_extension_lifecycle.py`: `remove` leaves **no** integration-managed file modified and retains feature ledgers; `remove --purge` additionally deletes `specops.json` + ledgers [SC-004]
- [ ] T028 [P] [US3] Integration test in `tests/integration/test_extension_lifecycle.py`: `update` from a native install is idempotent (semantic no-op when templates unchanged) [SC-002]

### Implementation for User Story 3

- [ ] T029 [US3] Implement `disable(root)` and `enable(root)` in `src/specops/extension.py`: disable removes SpecOps hook entries + command files (retain config/ledgers); enable re-registers from retained config (reuse `install` register path) [SC-004]
- [ ] T030 [US3] Implement `remove(root, purge=False)` and `update(root)` in `src/specops/extension.py`: remove unregisters hooks + command and, when `purge`, additionally deletes `specops.json` + feature ledgers; update re-applies current templates idempotently [SC-002,SC-004]
- [ ] T031 [US3] Wire `specops extension update|disable|enable|remove` (with `--purge`) in `src/specops/cli.py`; each returns 0 on success / `unchanged` when already in the target state [SC-002,SC-004]

**Checkpoint**: All three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Parametrized interruption-safety tests in `tests/integration/test_extension_lifecycle.py`: interrupt install/migrate/remove at each write boundary; a re-run reaches a consistent state with no manual repair and no partially-registered manifest [SC-007]
- [ ] T033 [P] Document the native install + legacy migration in `README.md` (English) [SC-001,SC-003,SC-004]
- [ ] T034 [P] Mirror the native install + migration docs in `README.pt-br.md` (behaviorally equivalent to English per Global DoD) [SC-001,SC-003,SC-004]
- [ ] T035 [P] Add a `CHANGELOG.md` entry recording user-visible behavior and the legacy→native migration requirement [SC-003]
- [x] T036 Constitution amendment applied (v1.4.0, 2026-07-19): Principle I & IV broadened to name the native extension mechanism as the primary delivery path and marker injection as the retained legacy path (clears analyze finding C1) [SC-001]
- [ ] T037 Run the `quickstart.md` scenarios end-to-end against fixtures and confirm ruff + mypy + full pytest pass at repository thresholds [SC-001,SC-002,SC-003,SC-004,SC-005,SC-006,SC-007,SC-008,SC-009]
- [ ] T038 [P] Regression: assert the legacy `specops init` marker-injection path (FR-015) still installs directive blocks + the review command with no behavior change, in `tests/integration/test_init.py` [SC-009]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup; **blocks all user stories**.
- **User Stories (Phase 3–5)**: all depend on Foundational.
  - US1 (P1) has no dependency on US2/US3.
  - US2 (P2) reuses `extension.install` (T016) — sequence US1 before US2, or stub the register path.
  - US3 (P3) reuses the `install` register path (T015/T016) — sequence after US1.
- **Polish (Phase 6)**: depends on the desired stories being complete.

### Cross-story file note (limits parallelism)

- `src/specops/cli.py` is edited by T008, T017, T024, T031 — these are **sequential** (same file).
- `src/specops/extension.py` is edited by T006, T015, T016, T029, T030 — **sequential** (same file).
- `src/specops/migration.py` is edited by T007, T022, T023 — **sequential** (same file).
- Migration logic (T022–T023) lives in `migration.py`, so US2 impl can proceed in parallel with US3
  `extension.py` work once US1's register path exists.

### Within Each User Story

- Tests written first and failing → implementation → wiring.
- Module logic (`extension.py`/`migration.py`) before thin CLI wiring (`cli.py`).

### Parallel Opportunities

- Setup: T001 ‖ T002.
- Foundational: T003 ‖ T004 ‖ T005 ‖ T009 (different files); T006, T007, T008 follow.
- All per-story test tasks marked [P] run together (distinct assertions in the shared test module can
  be authored in parallel, then merged).
- Polish: T032 ‖ T033 ‖ T034 ‖ T035 (different files).

---

## Parallel Example: Foundational Phase

```bash
# Different files, no ordering — run together:
Task: "Add native-path resolvers to src/specops/speckit.py"            # T003
Task: "Implement CLI-compatibility gate in src/specops/compat.py"       # T004
Task: "Extend src/specops/config.py with min_cli_version"               # T005
Task: "Foundational unit tests in tests/unit/test_extension.py + test_compat.py"  # T009
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (CRITICAL — blocks all stories).
2. Phase 3 US1 → **STOP and VALIDATE**: native install works, zero host files modified, idempotent,
   offline, multi-integration, fail-closed on bad CLI.
3. Ship the native-install MVP.

### Incremental Delivery

1. Foundation ready → US1 (native install, MVP) → validate/demo.
2. Add US2 (legacy migration) → validate/demo.
3. Add US3 (update/disable/enable/remove/purge) → validate/demo.
4. Polish: interruption-safety matrix, bilingual docs, changelog, constitution follow-up, quickstart.

---

## Success-Criteria Coverage Map

| SC | Covered by |
|----|------------|
| SC-001 (single-action install, zero host mods) | T001,T002,T003,T004,T005,T006,T008,T009,T010,T014,T015,T016,T017,T033,T034,T036,T037 |
| SC-002 (semantic-equivalence idempotency) | T006,T009,T011,T021,T026,T028,T030,T031,T037 |
| SC-003 (migration preserves config + ledgers) | T007,T018,T020,T023,T033,T034,T035,T037 |
| SC-004 (remove leaves no host mods, retains ledgers) | T007,T008,T025,T026,T027,T029,T030,T031,T033,T034,T037 |
| SC-005 (offline) | T012,T016,T037 |
| SC-006 (multi-integration registration) | T003,T013,T015,T016,T037 |
| SC-007 (interruption safety) | T032,T037 |
| SC-008 (migration abort restores host files) | T019,T020,T022,T023,T037 |
| SC-009 (legacy `specops init` path unchanged, 0 regressions) | T038,T037 |

---

## Notes

- [P] = different files, no dependency. [Story] label maps tasks to US1/US2/US3 for traceability.
- Every task carries ≥1 `[SC-xxx]` tag; all nine SCs are covered (map above).
- Not self-applied: no `status.yaml` ledger or `specops` commands are run against this repository;
  behavior is validated through `tests/` fixtures. Dev state is tracked via these checkboxes.
- Verify tests fail before implementing. Prefer one commit per user story (Constitution III).
