---
description: "Task list for Feature 014 — Diagnostics and Machine Reports"
---

# Tasks: Diagnostics and Machine Reports

**Input**: Design documents from `specs/014-diagnostics-machine-reports/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Per the Constitution (Development Workflow & Quality Gates — task gate), every
task is closed only with passing automated tests; test tasks are included per story.

**SC tagging**: Per the roadmap protocol (§4), every task carries one or more `[SC-xxx]`
tags mapping it to the spec's Success Criteria.

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks).
- **[Story]**: US1 / US2 / US3 (setup, foundational, polish carry no story label).
- Exact file paths are included in each task.

## Path Conventions

Single Python package: source under `src/specops/`, tests under `tests/unit/` and
`tests/integration/`. Reused read-only APIs are documented with `file:line` in
`research.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Module scaffold and shared test fixtures.

- [ ] T001 Scaffold `src/specops/doctor.py`: module docstring, `OUTPUT_VERSION = 1`, `Severity` constants + strict ordering (`ok<warning<blocking<execution-error`), the fixed ordered domain-id constants (`environment`, `cli_extension`, `integration`, `legacy_artifacts`, `configuration`, `feature_identity`, `ledger`, `context_map`, `workflow_divergence`, `gate_availability`), and the v1 `next_action_code` constant set per `data-model.md`. [SC-002]
- [ ] T002 [P] Add Feature 014 fixtures/builders to `tests/conftest.py` reusing existing builders: broken-in-tree-commit ledger, too-new (`schema_version: 99`) and migratable (`schema_version: 5`) ledgers, no-active-feature repo, unavailable-gate-command profile, invalid context map (cycle / unsafe traversal), an OPEN blocking-finding handoff, and a **second, deliberately-broken feature ledger** under another `specs/NNN-*/status.yaml` (to prove active-feature-only scope, FR-012a). [SC-004]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The report/finding data model and the verdict→exit contract that every story
depends on. **No user story can proceed until this phase is complete.**

- [ ] T003 Define dataclasses in `src/specops/doctor.py`: `Finding` (severity, message, next_action_code, next_action, id), `DomainResult` (domain, severity, findings), and `DoctorResult(outcome.CommandResult)` with a `_CLASS_MAP` mapping module statuses (`S_OK`/`S_WARNING`/`S_BLOCKING`/`S_EXECUTION_ERROR`) to `outcome` classes (`pass`/`gate-rejection`/`infra-error`). [SC-004]
- [ ] T004 Implement in `src/specops/doctor.py` the severity rollup (`verdict = max severity`), the per-domain severity rollup, and the deterministic serializer producing the schema in `contracts/doctor-output.schema.json` (fixed domain order; findings sorted by `(id, message)`; no timestamps/absolute paths). [SC-005]
- [ ] T005 [P] Unit tests in `tests/unit/test_doctor.py` for the foundational contract: severity ordering + verdict rollup, `DoctorResult` status→class→exit-code (0/1/2) mapping, and serializer determinism (same input → byte-identical). [SC-004] [SC-005]

---

## Phase 3: User Story 1 — Diagnose why a workflow cannot safely continue (Priority: P1)

**Goal**: A single read-only command inspects every domain and produces a
severity-classified, next-action-bearing human report with an overall verdict.

**Independent test**: Point `specops doctor` at fixtures with known-broken surfaces and
confirm the correct per-domain severities, that all domains appear, that every problem is
reported in one run, and that the repository is left unchanged.

- [ ] T006 [US1] Implement the install/environment domain checks in `src/specops/doctor.py`: `environment` (`gitops.is_git_repo`/`find_repo`, `speckit.has_speckit`), `cli_extension` (`compat.installed_version`/`compat.check`), `integration` (`speckit.resolve_prompt_targets`/`host_prompt_paths`; emit `run_specify_check` next action — no `specify` execution), `legacy_artifacts` (`migration.detect_state` → `migrate_legacy_install` on legacy/both), `configuration` (`config.load`, catch `ConfigError`). [SC-002]
- [ ] T007 [US1] Implement the feature-state domain checks in `src/specops/doctor.py`: `feature_identity` (`speckit.resolve_feature_dir`; `None` → `ok` + `start_or_select_feature`; `ledger.validate_identity` divergence / ambiguity → `blocking`, fail-closed) and `ledger` (`ledger.load_raw` + `classify`/`diagnostic_line`/`refusal_message`; `validate_invariants` + `finding_structural_defects`; migratable → `warning`+`run_status_migrate`, too-new/unsupported → `blocking`). [SC-002]
- [ ] T008 [US1] Implement the `context_map` (`contextmap.validate` diagnostics → `fix_context_map`; `map_digest`/`review.digest_drift_warning` → `refresh_context_provenance`; no-map → `ok`) and `workflow_divergence` (`reconcile.run` violations → `blocking`+`reconcile_repository`, warnings → `warning`; `reconcile.divergence`) domain checks in `src/specops/doctor.py`. [SC-002] [SC-007]
- [ ] T009 [US1] Implement the `gate_availability` domain check in `src/specops/doctor.py`: enumerate `gateprofiles.profiles_for(root)`, run `gateprofiles.validate(root)` for config defects, and probe each command read-only with `shutil.which(shlex.split(cmd)[0])`; unresolvable → `warning`+`install_gate_command`. Must not execute any command. [SC-002]
- [ ] T010 [US1] Implement `cmd_doctor(root: Path) -> DoctorResult` in `src/specops/doctor.py`: run all ten domains in fixed order, collect `DomainResult`s, roll up the verdict, and build the human rendering (per-domain line + next-action text; verdict summary line). [SC-001] [SC-002] [SC-006] [SC-007]
- [ ] T011 [US1] Wire the CLI in `src/specops/cli.py`: add `@app.command("doctor")` decorated with `@_handle_errors`, a `--json` option, and an `_emit_doctor` renderer modeled on `_emit_trace` (human→stdout on PASS / stderr otherwise; `raise typer.Exit(result.exit_code)`). [SC-001]
- [ ] T012 [P] [US1] Unit tests in `tests/unit/test_doctor.py`: per-domain check severity + `next_action_code` for each fixture (healthy, migratable, too-new, no-feature, ambiguous identity, invalid map, divergence, unavailable gate, blocking handoff). [SC-002] [SC-006]
- [ ] T013 [P] [US1] Integration test in `tests/integration/test_doctor_cli.py`: human `specops doctor` on healthy / blocking / no-feature / multi-problem fixtures asserts the correct verdict, that **all** domains are present (SC-002), and that a multi-problem fixture reports every finding in one run (SC-007). MUST also assert **active-feature-only scope** (FR-012a): with a second, broken feature ledger present, doctor reports only the active feature and never surfaces the other feature's ledger. [SC-001] [SC-002] [SC-007]

**Checkpoint**: US1 delivers the human diagnostic MVP — usable on its own.

---

## Phase 4: User Story 2 — Stable machine-readable diagnostics for CI (Priority: P1)

**Goal**: The same diagnostic emits a stable, versioned JSON document and deterministic
exit codes so CI can gate on it.

**Independent test**: Run `specops doctor --json` against per-verdict fixtures; validate
the document against `contracts/doctor-output.schema.json`, confirm byte-identical output
on repeated runs, and confirm the exit code maps deterministically to the verdict.

- [ ] T014 [US2] Implement `--json` rendering in `src/specops/doctor.py`/`cli.py` via `outcome.render("doctor", cls, output_version=OUTPUT_VERSION, verdict=..., domains=...)` conforming to `contracts/doctor-output.schema.json` (command, output_version, outcome, class, verdict, domains[]). [SC-004]
- [ ] T015 [US2] Implement execution-error handling in `src/specops/doctor.py`: a domain whose input is unreadable/corrupt (`LedgerParseError` and peers) is reported as an `execution-error` finding (never omitted or silently `ok`), driving verdict → `infra-error` → exit `2`; confirm exit mapping via `DoctorResult.exit_code`. [SC-004]
- [ ] T016 [P] [US2] Integration test in `tests/integration/test_doctor_cli.py`: `--json` document validates against the schema, and exit codes are mutually distinct across the three classes (0 ok/warning, 1 blocking, 2 execution-error). [SC-004]
- [ ] T017 [P] [US2] Integration test in `tests/integration/test_doctor_readonly_determinism.py`: `snapshot_tree` before/after equal (read-only) and two `--json` runs are byte-identical, following the `test_gate_readonly_determinism` pattern. MUST also assert **no side effects** beyond stdout (FR-017): no new files created and no network access — offline, no telemetry, no auto-repair. [SC-003] [SC-005]
- [ ] T018 [P] [US2] Integration test in `tests/integration/test_doctor_cli.py`: corrupt-ledger fixture → exit `2`, `ledger` domain reported as `execution-error`, no domain omitted. [SC-004]

**Checkpoint**: US1 + US2 deliver the full diagnostic surface (human + CI-gradable JSON).

---

## Phase 5: User Story 3 — Compact project/feature status report (Priority: P2)

**Goal**: A compact read-only `specops report` (human + JSON) of the active feature's
identity, phase, task progress, review/handoff state, and workflow lane.

**Independent test**: Run `specops report` against a mid-feature fixture and confirm the
reported fields match the ledger, in both human and JSON forms, without mutation.

- [ ] T019 [US3] Factor the compact-status computation (feature/branch/phase, task tallies pending/in_progress/done/orphaned/total, active task, review cycles, `workflow_lane`, handoff `blocking_open`) out of `status.cmd_show` into a shared read-only helper (in `src/specops/status.py`), and build the `StatusReport` in `src/specops/doctor.py` per `data-model.md`. No behavior change to `status show`. [SC-003]
- [ ] T020 [US3] Implement `cmd_report(root: Path)` in `src/specops/doctor.py` and wire the CLI in `src/specops/cli.py`: `@app.command("report")` with `@_handle_errors`, `--json`, and an emit helper; no-active-feature → `ok` with null fields, corrupt ledger → exit `2`. [SC-003]
- [ ] T021 [P] [US3] Tests in `tests/unit/test_doctor_report.py` and `tests/integration/test_report_cli.py`: field mapping (human + `--json`), read-only (`snapshot_tree`), byte-identical determinism, no-active-feature (`ok`), corrupt-ledger (exit `2`). [SC-003] [SC-005]

**Checkpoint**: All three user stories delivered.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation parity, changelog, and full-suite verification.

- [ ] T022 [P] Add EN documentation for `specops doctor` and `specops report` to `README.md` (new `### specops doctor` / `### specops report` reference sections, incl. severities, exit codes, and JSON schema pointer). [SC-008]
- [ ] T023 [P] Add behaviorally-equivalent PT documentation for `specops doctor` and `specops report` to `README.pt-br.md`. [SC-008]
- [ ] T024 [P] Record the new read-only commands and output schema v1 under `[Unreleased]` in `CHANGELOG.md`. [SC-008]
- [ ] T025 Run `conda run -n specops ruff check .`, `conda run -n specops mypy src`, and `conda run -n specops pytest` to green; walk the `quickstart.md` scenarios 1–10 against fixtures. [SC-001] [SC-002] [SC-003] [SC-004] [SC-005] [SC-006] [SC-007] [SC-008]

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T005)** must complete before any story.
- **US1 (T006–T013)** is the MVP and depends only on Foundational. T006–T011 touch the
  same files (`doctor.py`, then `cli.py`) so they run **sequentially**; T012–T013 (tests,
  separate files) are **[P]**.
- **US2 (T014–T018)** builds on US1's report structure. T014–T015 (`doctor.py`/`cli.py`)
  are sequential; T016–T018 (separate test files) are **[P]**.
- **US3 (T019–T021)** depends on Foundational (and reuses `status.py`); independent of
  US2. T019–T020 sequential; T021 test is **[P]**.
- **Polish (T022–T025)**: T022–T024 are **[P]** (different files); T025 runs last.

## Parallel Execution Examples

- After Foundational: run **T012, T013** together (US1 tests) once T006–T011 land.
- In US2: run **T016, T017, T018** together (independent test files).
- In Polish: run **T022, T023, T024** together (README EN, README PT, CHANGELOG).

## Implementation Strategy

- **MVP = User Story 1** (T001–T013): a working, read-only human `specops doctor` with
  correct severities and verdict — independently valuable and testable.
- **Increment 2 = User Story 2** (T014–T018): the CI-gradable JSON + exit-code contract.
- **Increment 3 = User Story 3** (T019–T021): the compact `specops report`.
- Commit granularity: one commit per user story (Phase 3, Phase 4, Phase 5), plus a
  foundational commit (Phases 1–2) and a polish commit (Phase 6), per the repo's
  per-user-story granularity preference.
