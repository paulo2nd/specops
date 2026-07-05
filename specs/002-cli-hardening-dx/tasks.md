---

description: "Task list for CLI Hardening & Developer Experience"
---

# Tasks: CLI Hardening & Developer Experience

**Input**: Design documents from `specs/002-cli-hardening-dx/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/ (cli-interface, errors), research.md (R1–R12), quickstart.md

**Tests**: Mandatory per the Constitution's task gate — every task closes only with passing automated tests and recorded evidence. Strict TDD is not required; test tasks accompany each story and MUST pass before the story checkpoint.

**Organization**: Tasks are grouped by user story. Coverage tags map tasks to spec Success Criteria for `specops consistency`.

## Format: `[ID] [P?] [Story] Description [SC coverage]`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in descriptions

## Path Conventions

Single project (per plan.md): `src/specops/` package, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared test fixtures the story phases rely on

- [X] T001 Extend `tests/conftest.py` with shared fixtures: a ledger-in-REVIEW factory (feature repo with `status.yaml` at phase REVIEW and one open review cycle) and a `read_ledger(feature_dir)` YAML helper, reusing the existing tmp-git-repo fixture

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The error vocabulary and the single CLI exit-code mapper — new code in every story is written against them (research R6; contracts/errors.md)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Create `src/specops/errors.py`: `SpecopsError(Exception)` with `message` and class-level `exit_code = 1`, `LedgerParseError(SpecopsError)` with `exit_code = 2`; re-parent `ConfigError` in `src/specops/config.py` and `ManifestResolutionError` in `src/specops/speckit.py` to `SpecopsError`
- [X] T003 Add the single boundary wrapper in `src/specops/cli.py` (helper or decorator applied to every command body): catch `SpecopsError`, echo `message` to stderr, raise `typer.Exit(e.exit_code)`; existing `sys.exit` paths keep working unchanged during migration

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Complete the review approval flow via CLI (Priority: P1) 🎯 MVP

**Goal**: `transition-phase DONE -r APPROVED` works from REVIEW in one command; result vocabulary closed to APPROVED/REJECTED; packaged review directive instructs the two real outcomes

**Independent Test**: quickstart Scenario A — approve and close a feature with zero manual `status.yaml` edits

### Tests for User Story 1 (mandatory per Constitution task gate) ⚠️

- [X] T004 [US1] Add failing tests in `tests/unit/test_status.py` using the T001 fixture: (a) `DONE -r APPROVED` from REVIEW records APPROVED + `completed_at` on the open cycle and advances the phase in one save; (b) `DONE -r REJECTED` exits 1, message names `transition-phase IMPLEMENT -r REJECTED`, ledger unchanged; (c) `-r "note ok"` exits 1 before any ledger read (invalid vocabulary); (d) `DONE` with pre-APPROVED cycle still passes; (e) result applies to the open placeholder cycle when a closed REJECTED round precedes it [SC-001]

### Implementation for User Story 1

- [X] T005 [US1] Fix `cmd_transition_phase` in `src/specops/status.py` per research R1/R2: validate `-r` vocabulary (APPROVED|REJECTED, case-insensitive, stored uppercase) before any state read; apply the result to the latest open review cycle in memory before evaluating the DONE gate; persist result + phase in one `_save_ledger` call; a valid result supplied on a transition that does not consume it (e.g. `PLAN -r APPROVED`) is silently ignored (compatible with current behavior); update the `-r/--result` help text in `src/specops/cli.py` to `APPROVED|REJECTED` [SC-001]
- [X] T006 [P] [US1] Correct packaged directive `src/specops/templates/review.md` Step 6 per research R3: replace the invalid `transition-phase REVIEW -r <...>` instruction with `APPROVED → specops status transition-phase DONE -r APPROVED` / `REJECTED → specops status transition-phase IMPLEMENT -r REJECTED`; adjust `tests/integration/test_review_asset.py` if it asserts the old text [SC-001]
- [X] T007 [US1] Add end-to-end lifecycle test in `tests/integration/test_ledger.py`: SPECIFY→PLAN→TASKS→IMPLEMENT→REVIEW→DONE including `DONE -r APPROVED`, via the Typer runner only — proves SC-001 with no manual ledger edits [SC-001]

**Checkpoint**: The P1 bug is fixed and demonstrably closed end to end — MVP delivered

---

## Phase 4: User Story 2 - Inspect ledger state at a glance (Priority: P2)

**Goal**: `specops status show` renders the ledger summary read-only; `specops --version` works anywhere

**Independent Test**: quickstart Scenario B — `show` and `--version` complete in < 1 s with contract-conformant output

### Tests for User Story 2 (mandatory per Constitution task gate) ⚠️

- [X] T008 [P] [US2] Create `tests/unit/test_show.py`: rendering of a populated ledger (phase, active task, counts including orphaned, cycles with `open`/result + dates), legacy ledger without `review_cycles`/empty `tasks` renders zero counts, ledger file bytes untouched after `show` (read-only), missing ledger raises the standard not-found error [SC-002]

### Implementation for User Story 2

- [X] T009 [US2] Implement `cmd_show` in `src/specops/status.py` per research R8 and contracts/cli-interface.md: load ledger read-only (no task re-sync, no save), return the structured plain-text summary; raise `SpecopsError`/`LedgerParseError` on failures; wire `status show` subcommand in `src/specops/cli.py` [SC-002]
- [X] T010 [P] [US2] Add eager `--version` root option in `src/specops/cli.py` via `importlib.metadata.version("specops-cli")` printing `specops <version>` (research R9); replace hardcoded `__version__` in `src/specops/__init__.py` with metadata lookup + `0.0.0.dev0` fallback [SC-003]
- [X] T011 [US2] Create `tests/integration/test_cli_surface.py` (initial scope): `--version` succeeds inside and outside a Git repository, `status show` end-to-end through the Typer runner matches the contract format [SC-002,SC-003]

**Checkpoint**: Ledger state and version discoverable with single commands

---

## Phase 5: User Story 3 - Trust the ledger under failure and bad input (Priority: P3)

**Goal**: Crash-safe ledger persistence, strict evidence grammar, numeric feature-dir ordering

**Independent Test**: quickstart Scenario C — malformed evidence rejected; interruption tests leave a parseable ledger

### Tests for User Story 3 (mandatory per Constitution task gate) ⚠️

- [X] T012 [P] [US3] Add tests in `tests/unit/test_status.py`: evidence grammar matrix per data-model.md (`CLI_LOG:` empty summary, `LOG:x` unknown class, `CLI_LOG:a; done` orphan segment, missing colon, valid single and multi-part) all reject/accept correctly with task state preserved on rejection; atomic save — simulate interruption (monkeypatched `os.replace` failure) and assert previous ledger content intact, stale `status.yaml.tmp` ignored on read and overwritten by next save [SC-004,SC-005]

### Implementation for User Story 3

- [X] T013 [US3] Implement in `src/specops/status.py` per research R4/R5: `_save_ledger` writes to sibling `status.yaml.tmp`, flush+fsync, `os.replace` onto `status.yaml`; delete dead `_EVIDENCE_RE`; rebuild `_validate_evidence` as the single path — strict `"; "` split, every part matching a compiled regex built from `EVIDENCE_CLASSES` with non-empty summary [SC-004,SC-005]
- [X] T014 [P] [US3] Numeric-prefix ordering in `resolve_feature_dir` fallback in `src/specops/speckit.py` (sort by `int` of leading digits desc, tie-break full name, per research R7); add `specs/9-*` vs `specs/10-*` cases to `tests/unit/test_speckit.py`

**Checkpoint**: Ledger integrity and input validation hardened

---

## Phase 6: User Story 4 - Consistent failure behavior across the CLI (Priority: P4)

**Goal**: Business modules raise `SpecopsError` instead of exiting; exit-code contract preserved byte-identically; dead code gone

**Independent Test**: quickstart Scenario D — business calls raise catchable errors; full-suite exit-code sweep green

### Implementation for User Story 4

- [X] T015 [US4] Migrate `src/specops/status.py` to contracts/errors.md: replace `_fail`/`sys.exit`/local `typer` imports with `SpecopsError`/`LedgerParseError` raises and returned success messages (CLI echoes them via the T003 boundary); remove duplicate `import sys` and unused `_ok`; adapt `tests/unit/test_status.py` to `pytest.raises` with message assertions [SC-006]
- [X] T016 [P] [US4] Add public action-suffix parsing helper in `src/specops/speckit.py` (line → `(path, action)` extraction, replacing consumers' private `_ACTION_SUFFIX_RE` + ad-hoc path regexes); unit tests in `tests/unit/test_speckit.py`
- [X] T017 [P] [US4] Migrate `src/specops/reconcile.py`: raise `SpecopsError` on blocking preconditions, return `(warnings, violations)`; CLI layer prints warnings→stdout, violations→stderr and maps exit per contracts/errors.md; adapt `tests/unit/test_reconcile.py` and `tests/integration/test_reconcile.py` [SC-006]
- [X] T018 [US4] Migrate `src/specops/consistency.py` (after T016): same error/return refactor; hoist the in-loop `import re`/private-regex imports to module top and consume the T016 public helper; report uncovered SCs against the SC's definition line in `spec.md` instead of `:0`; adapt `tests/unit/test_consistency.py` and `tests/integration/test_consistency.py` [SC-006]
- [X] T019 [P] [US4] Dead-code removal per research R12 in remaining modules: unused `end`/`start` computations in `commits_in_range` in `src/specops/gitops.py`; unused `command_name` in `_install_review` in `src/specops/initializer.py`; remove superseded `exit_ok`/`exit_fail`/`exit_error` helpers from `src/specops/cli.py`
- [X] T020 [US4] Extend `tests/integration/test_cli_surface.py` into the full exit-code regression sweep: every command's documented failure modes assert byte-identical stderr messages, output streams, and exit codes 0/1/2 through the Typer runner (SC-006 gate) [SC-006]

**Checkpoint**: One failure vocabulary, one exit mapper, no dead code — all stories still green

---

## Phase 7: User Story 5 - Automated quality gates for the project itself (Priority: P5)

**Goal**: Ruff + mypy + pytest-cov (85% blocking) locally; GitHub Actions CI on 3.10 + 3.14 blocking on every push/PR

**Independent Test**: quickstart Scenario E — seeded lint/type/test violations each block; clean tree passes

### Implementation for User Story 5

- [X] T021 [US5] Configure `pyproject.toml` per research R10: dev extras `ruff`, `mypy`, `pytest-cov`, `types-PyYAML`; `[tool.ruff]` target py310 with rule families E,F,W,I,UP,B,SIM; `[tool.mypy]` py310, `disallow_untyped_defs` on `src/` (tests exempt), `warn_unused_ignores`, `check_untyped_defs`; `[tool.pytest.ini_options]` `addopts = "--cov=specops --cov-report=term-missing --cov-fail-under=85"` [SC-008]
- [X] T022 [US5] Fix all `ruff check .` findings and `mypy src/specops` errors across `src/specops/` and `tests/` (add missing type annotations; no `# noqa`/`# type: ignore` suppressions for the R12 dead-code rules) until both run clean [SC-007]
- [X] T023 [US5] Bring statement coverage to ≥ 85% if below threshold after T021: targeted unit tests for uncovered branches (likely `src/specops/cli.py` option paths and `src/specops/initializer.py` non-interactive branches) in `tests/unit/` [SC-008]
- [X] T024 [US5] Create `.github/workflows/ci.yml` per research R11: triggers `push` + `pull_request`; matrix Python 3.10 and 3.14; steps checkout → setup-python → `pip install -e .[dev]` → `ruff check .` → `mypy src/specops` → `pytest` [SC-007]
- [X] T025 [US5] Validate the pipeline per quickstart Scenario E: three throwaway commits (unused import / type error / failing assert) each fail their step on both Python versions; revert → green. Record run URLs or logs as `CLI_LOG` evidence [SC-007]

**Checkpoint**: Machine-enforced quality gates active locally and in CI

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final validation

- [X] T026 [P] Update `README.md`: document `specops status show`, `specops --version`, the closed APPROVED/REJECTED result vocabulary on `transition-phase`, atomic-write behavior note, and a Development section with the local gate commands (`ruff check .`, `mypy src/specops`, `pytest`)
- [X] T027 Re-run `specops init` in this repository to refresh the installed review command (`.claude/skills/specops-review/SKILL.md`) with the T006 directive fix, then run all quickstart.md scenarios A–E end to end and record outcomes; fix any discrepancy found

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on nothing in Phase 1 (parallel-safe) but MUST complete before any story
- **User Stories (Phases 3–7)**: All depend on Phase 2. Priority order US1 → US2 → US3 → US4 → US5; US1–US3 are mutually independent; US4 touches files modified by US1–US3, so run it after them (or accept rebase cost); US5 runs last — its gates check the final code shape
- **Polish (Phase 8)**: After all stories

### Within-Story Dependencies

- US1: T004 (tests) → T005; T006 parallel to T005; T007 last
- US2: T008 before/with T009; T010 parallel; T011 last
- US3: T012 → T013; T014 fully parallel
- US4: T016 before T018; T015/T017/T019 mutually parallel; T020 last
- US5: T021 → T022 → T023 → T024 → T025 (sequential — each gate builds on the previous)

### Parallel Opportunities

- T005 ∥ T006 (different files: status.py vs packaged template)
- T008 ∥ T010 (new test file vs cli/__init__ version plumbing)
- T013 ∥ T014 (status.py vs speckit.py)
- T015 ∥ T016 ∥ T017 ∥ T019 (status.py / speckit.py / reconcile.py / gitops+initializer)
- T026 ∥ any remaining Phase 8 work

## Parallel Example: User Story 4

```bash
# After T003, launch together:
Task: "Migrate src/specops/status.py to SpecopsError raises"        # T015
Task: "Public action-suffix helper in src/specops/speckit.py"       # T016
Task: "Migrate src/specops/reconcile.py to (warnings, violations)"  # T017
Task: "Dead-code removal in gitops.py, initializer.py, cli.py"      # T019
# Then: T018 (consistency.py, needs T016) → T020 (regression sweep)
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (T001) + Phase 2 (T002–T003)
2. Phase 3: US1 (T004–T007)
3. **STOP and VALIDATE**: quickstart Scenario A — the approval flow works via CLI only
4. This alone removes the constitution-violating manual-edit workaround

### Incremental Delivery

Each story checkpoint is a releasable increment: US1 fixes the state machine, US2 adds observability, US3 hardens persistence, US4 pays down the structural debt (invisible to users, protected by the regression sweep), US5 locks everything in with machine gates.

### Commit Granularity

Per the constitution (Principle III): one commit per user story; intermediate tasks close with `--evidence`, the story's final task closes with `complete-task --auto` after the story-level commit.

## Notes

- [P] tasks = different files, no dependencies
- Coverage tags `[SC-00N]` map tasks to spec Success Criteria (validated by `specops consistency`)
- T014 and T016 carry no SC tag: they serve FR-008/FR-011 acceptance via unit tests, not a measurable outcome line
- Verify story tests fail before implementing (T004, T008, T012)
