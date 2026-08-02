---
description: "Task list for Review Round Integrity (Feature 025)"
---

# Tasks: Review Round Integrity

**Input**: Design documents from `/specs/025-review-round-integrity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Mandatory per Constitution (Development Workflow & Quality Gates — task
gate: no task is complete without tests). Every story phase includes test tasks.

**No Self-Application**: all tests run against throwaway fixtures under `tests/`;
no `specops` command is ever run against this repository.

**Organization**: grouped by user story (P1 → P2 → P3) for independent
implementation and testing. (Renumbered after `/speckit-analyze` remediation:
+K1 reconcile-exemption test, +G1 frozen-config test, +U1 resume test, +G2/U2
assertions.)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (setup, foundational, polish carry no story label)

## Path Conventions

Single project: `src/specops/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: scaffolding both the new module and the shared test fixtures depend on.

- [x] T001 [P] Create `src/specops/reviewscope.py` with the module docstring and typed stubs for `derive_range(...)` and `coverage(...)` (no logic yet), per contracts/ and data-model.md
- [x] T002 [P] Add a multi-round review fixture builder in `tests/helpers/review_rounds.py` (baseline commit + N `review_cycles` + per-round HEAD commits) reused by US1–US3 tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the v8 schema substrate every story loads/migrates against.

**⚠️ CRITICAL**: no user story work begins until this phase is complete.

- [x] T003 Bump `CURRENT_SCHEMA = 7 → 8` and update the schema-version comments in `src/specops/ledger.py`; confirm `migrate_to_current` needs no new back-fill (pure version bump per research R1)
- [x] T004 [P] Add optional `reviewed_range: str` and `review_role` (`"anchor" | "corrective"`) to `ReviewCycleRecord` and update the `LedgerDocument` docstring/keys in `src/specops/records.py`
- [x] T005 [P] Add structural validation of `reviewed_range`/`review_role` shape (string `"<from>..<to>"`; `corrective` not on the first scoped cycle) to the cycle invariants in `src/specops/ledger.py`
- [x] T006 [P] Update `tests/unit/test_frozen_ledger.py` to the v8 optional-field shape (additive; the pre-existing base key set is unchanged)
- [x] T007 Add a regression test pinning the **reconcile exemption** (research R7): `specops reconcile` stays green (exit 0) when a cycle's `reviewed_range` endpoint is unresolvable (simulated rebase/squash), proving reviewed-range endpoints are exempt from the registered-commit invariant — in `tests/unit/test_reconcile_reviewed_range_exempt.py`

**Checkpoint**: v8 ledger loads/migrates; scope fields exist, validate, and are reconcile-exempt.

---

## Phase 3: User Story 1 - Approval requires a complete defect hunt on record (Priority: P1) 🎯 MVP

**Goal**: record each Step-3 round's reviewed range (git-derived) and block DONE
unless the union covers `baseline..HEAD`; degrade to prior behavior when no scope
records exist.

**Independent Test**: on a fixture, drive reject-at-gates → anchor(reject) →
corrective(approve); approval succeeds only once recorded coverage spans
`baseline..HEAD`, and a partial-coverage feature is blocked with the uncovered
paths named.

### Tests for User Story 1 ⚠️

- [x] T008 [P] [US1] Unit tests for `reviewscope.derive_range` (anchor when no prior scoped cycle; corrective `from` = prior scoped `to`; re-run on same round is idempotent — U2) in `tests/unit/test_reviewscope.py`
- [x] T009 [P] [US1] Unit tests for `reviewscope.coverage` (target/covered/missing; ranges with unresolvable endpoints dropped; `has_scope_records` switch) in `tests/unit/test_reviewscope_coverage.py`
- [x] T010 [P] [US1] Integration tests for the approval guard — quickstart Scenarios 2, 3, 6, 7 — **plus an explicit FR-004 assertion** (G2): DONE is blocked by a missing path even when every blocking finding is VERIFIED, and is never blocked by a finding's content/merit — in `tests/integration/test_review_coverage_guard.py`

### Implementation for User Story 1

- [x] T011 [US1] Implement `derive_range(baseline, head, cycles)` and `coverage(repo, baseline, head, cycles)` (pure) in `src/specops/reviewscope.py`
- [x] T012 [US1] Implement `cmd_record_scope` — stamp `reviewed_range`/`review_role` on the current open cycle (idempotent; fail-closed on unresolvable baseline/`from`; print the anchor scoped path list) in `src/specops/handoff.py`
- [x] T013 [US1] Wire `specops handoff record-scope [--json]` (additive envelope keys `round`, `review_role`, `reviewed_range`, `scope_paths`) in `src/specops/cli.py`; assert in the CLI test that the command exposes **no** range/positional argument (SC-006: scope is derived, never reviewer-supplied)
- [x] T014 [US1] Add the union-coverage guard in `_gate_done` (block iff `has_scope_records and missing_paths`; degrade when no records; fail closed on unresolvable baseline) in `src/specops/status.py`

**Checkpoint**: US1 fully functional — approval integrity restored (MVP).

---

## Phase 4: User Story 2 - Corrective rounds are scoped, not re-hunts (Priority: P2)

**Goal**: a corrective round reviews `prev_to..HEAD` in full file context plus the
FIXED findings, never re-hunting unchanged already-reviewed code; the directive
tells the reviewer exactly that.

**Independent Test**: after an anchor round over {a,b,c,d,e}, a fix touching only
`c` yields a corrective `reviewed_range = prev..HEAD` whose printed scope is {c}
(+ prior non-terminal findings' files) and excludes {a,b,d,e}.

**Depends on**: US1's `cmd_record_scope` (T012 — same command, extended here).

### Tests for User Story 2 ⚠️

- [x] T015 [P] [US2] Unit test: corrective printed scope = delta paths + non-terminal findings' files, excluding untouched already-reviewed files (SC-003) in `tests/unit/test_reviewscope_corrective.py`
- [x] T016 [P] [US2] Integration test (quickstart Scenario 4): corrective `reviewed_range` = `prev_to..HEAD`, `scope_paths` excludes untouched files, and re-running `record-scope` on the same corrective round is idempotent (U2) in `tests/integration/test_corrective_scope.py`

### Implementation for User Story 2

- [x] T017 [US2] Extend `cmd_record_scope` corrective output to include each prior non-terminal finding's `file` (regression surface), de-duplicated, in `src/specops/handoff.py`
- [x] T018 [US2] Rewrite Step 3 of `src/specops/templates/review.md`: call `handoff record-scope`, read exactly its scope, distinguish anchor (full `baseline..HEAD`) vs corrective (delta in full file context + verify each FIXED finding), forbid re-hunting unchanged code, and replace the old "files listed by the working-tree gate" line

**Checkpoint**: corrective rounds are bounded; the motivating incremental-anchoring failure is closed at the directive.

---

## Phase 5: User Story 3 - The review loop is bounded (Priority: P3)

**Goal**: a configurable round cap halts and asks a human, recorded as ledger
state, never fabricating a verdict — and the human can resume.

**Independent Test**: with `review_round_cap` set, driving rejections past the cap
halts (exit 1), records `review_halt`, keeps round-N `REJECTED`, and opens no
round N+1; raising the cap then lets the next round open.

### Tests for User Story 3 ⚠️

- [x] T019 [P] [US3] Unit test: `review_round_cap` default 10 + coercion guard (non-int/≤0 → default) in `tests/unit/test_config_round_cap.py`
- [x] T020 [P] [US3] Integration test (quickstart Scenario 5): exceeding the cap halts with exit 1, writes `review_halt {at_round, cap, recorded_at}`, preserves round-N `REJECTED`, appends no round N+1 in `tests/integration/test_round_cap.py`
- [x] T021 [P] [US3] Integration test for **resume after halt** (quickstart Scenario 8 / research R8 / U1): after a halt, raising `review_round_cap` opens the next round normally, and an APPROVED with complete coverage succeeds despite the retained `review_halt` marker — in `tests/integration/test_round_cap_resume.py`
- [x] T022 [P] [US3] Update `tests/unit/test_frozen_config.py` for the additive `review_round_cap` key (G1: the Feature 021 frozen `specops.json` surface stays additive-valid)

### Implementation for User Story 3

- [x] T023 [P] [US3] Add `"review_round_cap": 10` to `_DEFAULTS` in `src/specops/config.py`
- [x] T024 [US3] Add optional `review_halt` marker to `LedgerDocument` in `src/specops/records.py`
- [x] T025 [US3] Enforce the cap in `cmd_transition_phase` at the round-opening site (`_close_rejected_review`): record `review_halt` + raise `SpecopsError` (exit 1) before opening round N+1, preserving the round-N `REJECTED` verdict; re-read the cap from live config each attempt so a raised cap resumes (R8) — in `src/specops/status.py`
- [x] T026 [US3] Add a cap-halt note to `src/specops/templates/review.md` (audit-only; no verdict) including the resume paths (raise `review_round_cap`, approve, or rebaseline)

**Checkpoint**: all three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T027 Amend `.specify/memory/constitution.md` (MINOR): (a) broaden Principle IV Token-Optimized Review (record reviewed scope; approval enforces union coverage; round cap is a Stop-and-Ask); (b) **narrow the normative wording of Principle II** so the "every registered commit MUST exist / `reconcile` MUST block on divergence" invariant is scoped to **work/task commits and the baseline**, with an explicit carve-out for reviewed-range endpoints (mirroring the `(human)` sentinel precedent) — a rationale note is not enough; the MUST itself must not literally cover reviewed-range endpoints (research R7); bump version and add the Sync Impact Report entry
- [x] T028 [P] Update `README.md` and `README.pt-br.md` at parity — document `handoff record-scope`, the coverage guard, `review_round_cap`, and the resume-after-halt paths
- [x] T029 [P] Update `CHANGELOG.md` under `[Unreleased]` (do not date — only tagged versions get a dated heading)
- [x] T030 Run all 8 quickstart.md scenarios against fixtures and confirm green
- [x] T031 Run the full gate under `conda run -n specops`: ruff + mypy + pytest; resolve any fallout

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: depends on Setup; **blocks all user stories**.
- **US1 (P3)**: depends on Foundational. Delivers the MVP.
- **US2 (P4)**: depends on Foundational + US1's `cmd_record_scope` (T012).
- **US3 (P5)**: depends on Foundational only — independent of US1/US2.
- **Polish (P6)**: depends on all shipped stories.

### User Story Dependencies

- **US1** — independent (needs only Foundational).
- **US2** — extends US1's scope command; independently *testable*, sequenced after US1.
- **US3** — fully independent; could be built in parallel with US1 after Foundational.

### File-level sequencing (same-file, not parallel)

- `src/specops/handoff.py`: T012 (US1) → T017 (US2).
- `src/specops/records.py`: T004 (Foundational) → T024 (US3).
- `src/specops/templates/review.md`: T018 (US2) → T026 (US3).
- `src/specops/ledger.py`: T003 → T005 (different concerns; sequence within Foundational).
- `src/specops/status.py`: T014 (US1, `_gate_done`) and T025 (US3, `_close_rejected_review`/`cmd_transition_phase`) touch different functions in the same file — sequence them.

### Parallel Opportunities

- Setup: T001, T002 in parallel.
- Foundational: T004, T005, T006 in parallel (different concerns), then T003/T007 sequencing as needed.
- US1 tests: T008, T009, T010 in parallel before implementation.
- US3 tests: T019–T022 in parallel; US3 is parallelizable with US1 after Foundational (coordinate `records.py` T004→T024 and `status.py` T014/T025).

---

## Parallel Example: User Story 1

```bash
# Tests first (must fail before implementation):
Task: "Unit tests for reviewscope.derive_range in tests/unit/test_reviewscope.py"
Task: "Unit tests for reviewscope.coverage in tests/unit/test_reviewscope_coverage.py"
Task: "Integration tests for the approval guard in tests/integration/test_review_coverage_guard.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP and validate**:
the coverage guard restores approval integrity (the reported defect) on its own.

### Incremental Delivery

1. Setup + Foundational → v8 substrate ready.
2. US1 → approval integrity (MVP) → validate.
3. US2 → corrective scoping + directive → validate.
4. US3 → loop bound + resume → validate.
5. Polish → constitution amendment, docs parity, full gate.

### Notes

- [P] = different files, no incomplete-task dependency.
- Verify each story's tests fail before implementing.
- Prefer one commit per user story (Constitution Principle III); close intermediate
  tasks with `--evidence`, the story's final task with `--auto`.
- Constitution amendment (T027) and the schema bump (T003) land in the same change
  set as the templates/code they govern.
