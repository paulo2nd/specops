# Tasks: Internal Hardening

**Input**: Design documents from `/specs/018-internal-hardening/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included per the Constitution task gate — every task closes only with passing automated tests. The golden-capture harness (Foundational) is itself the feature's primary test instrument (contracts/cli-output.md).

**Organization**: Tasks are grouped by user story. Stories are independently deliverable, but the recommended order is strictly P1 → P2 → P3 → P4: US2's renames touch the files US1 refactors, so parallel story execution is NOT recommended for this feature (same-file conflicts).

## Format: `[ID] [P?] [Story] Description (SC-xxx)`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- **(SC-xxx)**: success criteria from spec.md the task serves (roadmap protocol §4)
- Include exact file paths in descriptions

## Path Conventions

Single project: `src/specops/`, `tests/` at repository root (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: branch, roadmap registration, baseline measurements

- [X] T001 Create branch `018-internal-hardening` from `main`; commit the `specs/018-internal-hardening/` artifacts and the `.specify/feature.json` pointer
- [X] T002 Feature 018 entry (ACTIVE) registered in `ROADMAP.md` via the dedicated plan PR #31 (merged 2026-07-25); the ACTIVE→MERGED flip still happens inside this feature's PR at merge time, per repo convention
- [X] T003 Record baselines for later comparison in the PR description: baseline commit SHA, `time pytest tests/ -q` wall-clock (full suite and `tests/integration/` alone), and the SC-002 scan output (expected: 39 sites) using the script in `specs/018-internal-hardening/quickstart.md` §2 (SC-002, SC-005)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the behavior-freeze instrument every story validates against (research.md D8, contracts/cli-output.md)

**⚠️ CRITICAL**: no refactor lands before the golden baseline is recorded

- [X] T004 Build the golden-capture harness in `tests/golden/` (new): fixture repos per command family (context, trace, handoff, gate, lane, status/report, reconcile), capturing `(stdout, stderr, exit_code)` in human and `--json` modes; `--golden-record` flag in `tests/golden/conftest.py` writes captures, default mode diffs against them (SC-001, SC-006)
- [X] T005 Record the baseline captures on the unmodified tree and commit them under `tests/golden/captures/`; replay must pass with zero diffs before any refactor task starts (SC-001)

**Checkpoint**: golden replay green on the untouched tree — refactoring may begin

---

## Phase 3: User Story 1 — One place to define a command's result and output (Priority: P1) 🎯 MVP

**Goal**: one `CommandResult` abstraction and one `_emit` function serve all five command families; the lane JSON envelope divergence is fixed (the feature's single behavior delta).

**Independent Test**: golden replay shows zero diffs except lane `--json` gaining `output_version` + `status`; full suite green.

### Tests for User Story 1 (mandatory per Constitution task gate) ⚠️

- [X] T006 [P] [US1] Add failing test in `tests/unit/test_lane.py` asserting lane `--json` output contains top-level `output_version` and `status` (currently absent — must fail before T010) (SC-001)
- [X] T007 [P] [US1] Add tests in `tests/unit/test_outcome_contract.py` asserting the trace and handoff result types are `outcome.CommandResult` subclasses whose `_CLASS_MAP` reproduces today's status→exit-code mapping exactly (enumerate all statuses of both families) (SC-003)

### Implementation for User Story 1

- [X] T008 [US1] Refactor `src/specops/trace.py`: delete the `TraceResult` dataclass body and module-level `_CLASS_FOR_STATUS`-as-API; define `TraceResult(outcome.CommandResult)` carrying only `_CLASS_MAP` (mirroring `contextmap.py:134-138`); update all in-module constructors/usages (SC-003)
- [X] T009 [US1] Refactor `src/specops/handoff.py` the same way: `HandoffResult(outcome.CommandResult)` with `_CLASS_MAP`; update all in-module usages (including the `_load_write` isinstance sites — mechanical, no contract change in this story) (SC-003)
- [X] T010 [US1] Unify the five emit helpers in `src/specops/cli.py` (`_emit_context` 587, `_emit_trace` 725, `_emit_handoff` 790, `_emit_gate` 1001, `_emit_lane` 1096) into one `_emit(result, json_out, *, output_version, soft=False)`; all call sites pass their module's `OUTPUT_VERSION`; lane adopts the full envelope (sanctioned delta) and keeps `soft` exit semantics (SC-001, SC-003)
- [X] T011 [US1] Re-record only the lane captures (`--golden-record` scoped to lane), verify every other family's replay is byte-identical, run the full suite, and add the CHANGELOG `[Unreleased]` entry describing the lane envelope addition as the feature's single behavior change (SC-001, SC-006)

**Checkpoint**: US1 fully functional — golden replay green (lane delta only), suite green

---

## Phase 4: User Story 2 — Module boundaries are explicit contracts (Priority: P2)

**Goal**: zero cross-module references to underscore-prefixed helpers in `src/specops/`; every promoted name carries a documented contract (contracts/internal-api.md).

**Independent Test**: the SC-002 static scan reports 0 (baseline 39); full suite green; golden replay unchanged.

### Tests for User Story 2 (mandatory per Constitution task gate) ⚠️

- [X] T012 [US2] Add `tests/unit/test_module_boundaries.py` implementing the SC-002 scan (quickstart §2) as a pytest that fails while any cross-module private reference remains in `src/specops/` (fails now at 39 — must fail before T013) (SC-002)

### Implementation for User Story 2

> Renames follow contracts/internal-api.md exactly (no aliases; docstring contract at each definition site; consumers updated in the same task). Sequential — the batches share consumer files.

- [X] T013 [US2] Promote `status.py` helpers: `_load_for_write`→`load_for_write`, `_finalize`→`finalize`, `_get_feature_dir`→`get_feature_dir`; update consumers `src/specops/handoff.py` (11 sites) and `src/specops/trace.py` (3 sites) and all test references (SC-002)
- [X] T014 [US2] Promote `trace.py` helpers: `_norm`→`norm_path`, `_is_managed`→`is_managed`; update consumers `src/specops/handoff.py`, `src/specops/ingestion.py`, `src/specops/lane.py` and test references (SC-002)
- [X] T015 [US2] Promote `contextmap.py` names: `_matches`→`matches`, `_classify_pattern`→`classify_pattern`, `_candidates_for_path`→`candidates_for_path`, `_RESOLVABLE`→`RESOLVABLE`, `_CLASS_FOR_STATUS`→`CLASS_FOR_STATUS`; update consumers `src/specops/gateprofiles.py`, `src/specops/trace.py`, `src/specops/doctor.py` and test references (SC-002)
- [X] T016 [US2] Promote `ledger._ledger_path`→`ledger.ledger_path` (consumer `src/specops/lane.py`, 5 sites), `review._profile_gates`→`profile_gates` (lane), `review._existing_evidence`→`existing_evidence` (cli), `gateprofiles._affected_for`→`affected_for` (review) and test references (SC-002)
- [X] T017 [US2] Promote `handoff._canonical`→`canonical_finding` (consumer `src/specops/sarif.py`), `initializer._install_review`→`install_review` (extension), `initializer._scan_markers`→`scan_markers` (migration) and test references (SC-002)
- [X] T018 [US2] Sweep remaining test-side private references (FR-014): rewrite behavior-level tests against the public surface where it expresses the same assertion (`review._run_profile_gate`→via `evaluate`, `extension._merge_manifest`→via `install`, per research.md R7 list); pure-helper unit tests may keep testing the now-public names (SC-002)
- [X] T019 [US2] Verify: T012 boundary test green (0 sites), full suite green, golden replay byte-identical (no delta expected in this story) (SC-001, SC-002)

**Checkpoint**: US1 + US2 independently verified — boundaries are contracts

---

## Phase 5: User Story 3 — Single authority for shared grammars and records (Priority: P3)

**Goal**: one ledger-loading path, one evidence-grammar owner, one finding factory, co-located finding-line parse/render with a round-trip guarantee.

**Independent Test**: corrupted-ledger fixture yields the identical diagnostic + exit 2 from `status show`, `status report`, and `reconcile`; round-trip test passes; golden replay unchanged on valid inputs.

### Tests for User Story 3 (mandatory per Constitution task gate) ⚠️

- [X] T020 [P] [US3] Add convergence tests in `tests/integration/test_ledger_diagnostics.py` (new): one corrupted-ledger fixture asserted to produce the identical `load_raw` diagnostic and exit code 2 across `status show`/`status report`/`reconcile`, and one non-mapping-task fixture asserted to render filtered (not crash) in both `show` and `report` — write first, fails on current divergence (SC-004)
- [X] T021 [P] [US3] Add round-trip test in `tests/unit/test_findings.py` (new): `parse_finding_line(format_finding_line(f))` lossless for findings with and without `line`; plus factory-shape test asserting the three creation paths share one identical base dict (SC-003)
- [X] T022 [P] [US3] Add equivalence test in `tests/unit/test_evidence_record.py`: `evidence.validate_string` accepts/rejects the exact corpus `status._validate_evidence` does today (capture the corpus from the 11 existing `_validate_evidence` tests before moving) (SC-003)

### Implementation for User Story 3

- [X] T023 [US3] Create `src/specops/findings.py`: `new_finding(...)` (base shape per data-model.md, kwargs for `imported`/`producer`/`reviewed_digest`), `parse_finding_line`/`format_finding_line` (regex from `trace.py:63` + renderer from `handoff.py:804-820`, side by side); migrate consumers: `src/specops/handoff.py` (3 construction sites + import parse + render), `src/specops/trace.py`, `src/specops/sarif.py` (SC-003)
- [X] T024 [US3] Consolidate the evidence grammar into `src/specops/evidence.py`: move `EVIDENCE_CLASSES`, the part regex, and validation from `src/specops/status.py:23-27,155-167` as `evidence.validate_string`; consumers `status.py` (task close) and `handoff.py` (finding close) import from there (SC-003)
- [X] T025 [US3] Route `status.cmd_show` (`src/specops/status.py:533-555`) through `ledger.load_raw` and render counts/listing from the `compact_status` snapshot (adopting tolerant filtering per spec Assumptions) (SC-003, SC-004)
- [X] T026 [US3] Route `reconcile.load_state` (`src/specops/reconcile.py:23-34`) through `ledger.load_raw`, retiring the divergent "Cannot parse ledger" wording (contracts/cli-output.md §invalid-input convergences) (SC-004)
- [X] T027 [US3] Verify: T020–T022 green, full suite green, golden replay byte-identical on valid inputs; update captures only where the enumerated invalid-input convergences apply (SC-001, SC-004)

**Checkpoint**: all shared grammars have exactly one owner

---

## Phase 6: User Story 4 — A test suite cheap to extend and fast to run (Priority: P4)

**Goal**: one git helper, shared parametrized ledger builders, in-process integration tests by default with an explicit subprocess smoke set; ≥30% integration wall-clock reduction.

**Independent Test**: duplicate-definition scans return single/zero hits (quickstart §3); `pytest -m subprocess` runs the smoke set; timed run beats baseline by ≥30% on the integration portion; coverage ≥85%.

### Tests for User Story 4 (mandatory per Constitution task gate) ⚠️

> This story's deliverable IS test infrastructure; the "tests" are the scans and gates in T031 plus the suite itself staying green after each task.

### Implementation for User Story 4

- [X] T028 [US4] Consolidate helpers in `tests/conftest.py`: export `git(root, *args)` with `check=True`; delete the five local copies (`tests/unit/test_lane.py:19`, `tests/integration/test_context_consume_cli.py:35`, `tests/integration/test_preflight_cli.py:21`, `tests/integration/test_ledger_migration.py:17`, `tests/integration/test_lane_flow.py:31`); migrate manual `git init` call sites (`tests/unit/test_consistency.py`, `test_show.py`, `test_reconcile.py`, `test_status.py`, `test_cli.py`) to the `tmp_git_repo` fixture (SC-003)
- [X] T029 [US4] Consolidate ledger builders in `tests/conftest.py`: parametrize `make_v1_ledger` to cover the variants; delete `tests/unit/test_status.py:18` `_make_ledger`; re-express the `ledger_in_review` fixture via the shared builder (SC-003)
- [X] T030 [US4] Migrate subprocess CLI invocations to Typer `CliRunner` across `tests/integration/` (~17 files spawning the `specops` binary); register the `subprocess` marker in `pyproject.toml` `[tool.pytest.ini_options]`; keep/mark a smoke set of ~one command per family (context, trace, handoff, gate, lane, status, reconcile, doctor) as `@pytest.mark.subprocess` covering real exit codes, stream separation, and encoding (SC-005)
- [X] T031 [US4] Verify and record: duplicate scans single/zero hits, `pytest -m subprocess` green, full suite + coverage ≥85% green, timed run vs T003 baseline shows ≥30% integration reduction (record both numbers in the PR description) (SC-003, SC-005)

**Checkpoint**: all four stories independently verified

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Run the full `specs/018-internal-hardening/quickstart.md` validation end-to-end (all six sections) and fix any residue (SC-001, SC-002, SC-003, SC-004, SC-005, SC-006)
- [ ] T033 [P] Final gates: `ruff check .`, `mypy src/`, full suite with coverage, golden replay — all green on the branch tip (SC-006)
- [ ] T034 Flip the ROADMAP.md Feature 018 entry ACTIVE→MERGED inside this feature's PR (repo convention); confirm the CHANGELOG `[Unreleased]` section lists the lane envelope delta and the internal consolidation summary (SC-006)
- [ ] T035 Close absorbed overlaps: verify none of issues #23–#28 was accidentally implemented here (scope guard per spec Assumptions); cross-link the PR to the review triage (issues #29/#30 remain untouched)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → nothing
- **Foundational (Phase 2)** → Setup; **blocks all stories** (no refactor before the golden baseline exists)
- **US1 (Phase 3)** → Foundational
- **US2 (Phase 4)** → Foundational; **strongly recommended after US1** (renames touch trace.py/handoff.py/cli.py that US1 restructures — doing US2 first forces double edits)
- **US3 (Phase 5)** → Foundational; depends on US2's promoted names for its moves (evidence/findings consumers import public names)
- **US4 (Phase 6)** → Foundational; T028/T029 are independent of US1–US3, but T030's CliRunner migration should land **after** US1–US3 so migrated tests don't need re-touching (they assert against the final surface)
- **Polish (Phase 7)** → all stories

### Within Each User Story

- Test tasks are written first and must fail before their implementation tasks
- Golden replay + full suite green at every story checkpoint before the next story starts

### Parallel Opportunities

- T006/T007 (US1 tests), T020/T021/T022 (US3 tests), T032/T033 (polish) are [P] within their phases
- T028 and T029 touch `tests/conftest.py` both — sequential despite being conceptually independent
- Cross-story parallelism is deliberately NOT recommended (same-file conflicts, see Organization note)

---

## Parallel Example: User Story 3

```bash
# Write the three US3 test tasks together (different new/existing test files):
Task: "Convergence tests in tests/integration/test_ledger_diagnostics.py"
Task: "Round-trip + factory tests in tests/unit/test_findings.py"
Task: "Evidence-grammar equivalence corpus in tests/unit/test_evidence_record.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phases 1–2 (branch, roadmap, baselines, golden harness)
2. Phase 3 (US1) → golden replay shows exactly the lane delta → suite green
3. **STOP and VALIDATE**: US1 alone already delivers the consolidation's highest-leverage piece and the only behavior fix; it is a mergeable increment if needed

### Incremental Delivery

Each story ends at a checkpoint with golden replay + full suite green, so the PR can be cut after any story. Recommended single PR with one commit per user story (repo convention: commit granularity per user story), in strict P1→P2→P3→P4 order.

---

## Notes

- [P] tasks = different files, no dependencies
- Golden captures are committed test assets; re-record only when a sanctioned delta says so (T011, T027)
- No Self-Application: every validation runs on fixtures under `tests/`, never against this repository
- Commit per user story, not per task (repo convention); stop at any checkpoint to validate independently
