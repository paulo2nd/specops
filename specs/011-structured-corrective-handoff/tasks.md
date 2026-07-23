---
description: "Task list for Feature 011 — Structured Corrective Handoff"
---

# Tasks: Structured Corrective Handoff

**Input**: Design documents from `specs/011-structured-corrective-handoff/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R15), data-model.md, contracts/ (handoff-cli, finding-lifecycle, handoff-ledger, revision-render), quickstart.md

**Tests**: REQUIRED. Per the Constitution (Development Workflow & Quality Gates — task gate) and the Global Definition of Done ("New CLI surfaces have unit, integration, error-path, and idempotency coverage"; "Persisted formats are versioned and have forward migration tests"), every user story ships tests before/with its implementation. Per roadmap §4, every task carries one or more `[SC-xxx]` tags.

**No-Self-Application**: `specops`/`handoff` commands are NOT run against this repository, and no ledger is created here. All behavior is proven by fixtures under `tests/` (memory: no-specops-self-application).

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 (user-story tasks only)
- Paths are repository-root-relative and verified against the current worktree.

## Path Conventions

Single-project layout: engine in `src/specops/`, tests in `tests/unit` + `tests/integration`, shared builders in `tests/conftest.py`, directive assets in `src/specops/templates/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared test scaffolding reused across all four stories.

- [ ] T001 [P] Add shared pytest builders in `tests/conftest.py` — a v5 ledger builder producing a rejected-cycle handoff with findings in each state (`OPEN`/`FIXED`/`VERIFIED`, mixed `blocking`/`advisory`), a v4 (pre-feature) ledger builder, a `revisions/revision-X.md` legacy-prose fixture (`<file>:<line> - <action>` lines + an `APPROVED` line), and defect seeds (dangling task/commit/evidence/cycle reference, blocking finding missing closure, `VERIFIED`-without-evidence / `FIXED`-without-commit, duplicate id) [SC-001] [SC-005] [SC-007]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The Ledger v4→v5 schema and the `handoff.py` result/status contract every story builds on.

**⚠️ CRITICAL**: Must complete before US1–US4.

- [ ] T002 Bump the ledger to v5 in `src/specops/ledger.py` — `CURRENT_SCHEMA` 4→5; `migrate_to_current` stays additive (pre-v5 cycles gain **no** `handoff` key — absence = zero findings; every task/cycle/evidence/acknowledgement/provenance field byte-preserved); extend `validate_invariants` with finding-shape checks (valid `severity`∈{blocking,advisory}, valid `state`∈{OPEN,FIXED,VERIFIED}, feature-unique `id`, no `blocking` finding lacking `closure_criteria`/`expected_evidence`, `FIXED`/`VERIFIED` correction-link presence), exempting absent handoffs and orphaned records [SC-007]
- [ ] T003 [P] Ledger v5 tests — v4→v5 additive migration preserves acknowledgements/provenance/review_cycles with zero data loss and remains readable (`tests/integration/test_ledger_migration.py`); finding-shape invariant enforcement/tolerance + pre-v5 read-compat (`tests/unit/test_ledger.py`) [SC-007]
- [ ] T004 Create `src/specops/handoff.py` skeleton — the `HandoffResult` contract (`status → class → exit`, mirroring `trace.TraceResult`), the `_STATUS_CLASS` table and status constants per data-model (`finding-recorded`, `handoff-authorized`, `finding-fixed`, `finding-verified`, `handoff-closed`, `handoff-already-closed`, `validate-ok`, `report-ok`, `approval-blocked`, `close-blocked`, the four defect statuses, `illegal-transition`, `precondition-unmet`, `unknown-task`, `unknown-finding`, `duplicate-id-create`, `not-a-repo`, `bad-args`), `OUTPUT_VERSION = 1`, the `R<round>-F<NN>` id-assignment helper, the current-round accessor over `review_cycles`, and the canonical finding sort key (round, severity, file codepoint, line, id) [SC-001] [SC-008]

**Checkpoint**: v5 ledger and handoff contract ready — US1 first (MVP), then US2, US3, US4.

---

## Phase 3: User Story 1 — Record a resumable corrective handoff at rejection (Priority: P1) 🎯 MVP

**Goal**: Record structured findings (stable id, severity, rule, location, action, per-finding expected evidence + closure criteria) and the handoff's shared authorized paths in the ledger, bound to the originating review cycle, so a fresh session reconstructs the rejected review from repository state alone.

**Independent Test**: Record a handoff with several mixed-severity findings + authorized paths; reload the ledger in a fresh process and confirm every field round-trips with a stable `R<round>-F<NN>` id, the write was atomic and cycle-bound, and repeated reads are byte-identical.

### Tests for User Story 1

- [ ] T005 [P] [US1] Unit tests in `tests/unit/test_handoff.py` — deterministic `R<round>-F<NN>` assignment + stability across reloads; finding-record shape and field optionality (line optional; blocking requires closure/expected-evidence); handoff created on first finding; authorized-paths normalization; zero-findings ⇒ no `handoff` key; byte-stable ordering [SC-001] [SC-002]
- [ ] T006 [P] [US1] Integration tests in `tests/integration/test_handoff_cli.py` — `handoff finding add` and `handoff authorize` exit/status/`--json` (`output_version`) matrix; `duplicate-id-create` and `bad-args`/`unknown` fail closed (exit 2) leaving state unchanged; not-a-repo exit 2; before/after ledger round-trip proves resumability [SC-002] [SC-008]

### Implementation for User Story 1

- [ ] T007 [US1] Implement `cmd_finding_add` and `cmd_authorize` in `src/specops/handoff.py` — assign the id, create the current round's `handoff` if absent, validate severity/required fields, normalize paths via `trace._norm`, and write through `status._load_for_write` + `status._finalize` (identity gate + revision-CAS + atomic) [SC-001] [SC-002]
- [ ] T008 [US1] Register `handoff finding add` and `handoff authorize` in `src/specops/cli.py` — new `handoff_app` Typer group + `_emit_handoff` bridge (mirror `_emit_trace`), `--severity/--rule/--file/--line/--action/--expected-evidence/--closure` and repeatable `--path`, with `--json` [SC-008]

**Checkpoint**: US1 fully functional — a rejected review's findings + authorized paths persist and reload deterministically.

---

## Phase 4: User Story 2 — Drive findings to verified and gate approval (Priority: P2)

**Goal**: `OPEN → FIXED → VERIFIED` monotonic lifecycle (mechanical guard, no auto-verify) with correction links; a feature-global blocking-approval invariant that blocks `APPROVED`/`DONE` while any blocking finding is unverified and degrades when no structured findings exist; and `handoff close`.

**Independent Test**: From seeded findings, every legal transition succeeds with its links and every illegal one fails closed (exit 2, unchanged); `APPROVED`/`DONE` is blocked (exit 1, names findings) while any blocking finding is unverified and permitted once all are `VERIFIED`; advisory-only open findings never block; `close` is closability-gated and idempotent.

### Tests for User Story 2

- [ ] T009 [P] [US2] Unit tests in `tests/unit/test_handoff.py` — `OPEN→FIXED` (task/commit/evidence) and `FIXED→VERIFIED` (mechanical precondition) preconditions; illegal transitions (`OPEN→VERIFIED` skip, backward, precondition-unmet) exit 2 unchanged; `blocking_approval_check` feature-global across rounds; carry-forward (VERIFIED persists, recurrence gets new id); `close` closability + idempotency [SC-003] [SC-004] [SC-010] [SC-011]
- [ ] T010 [P] [US2] Unit tests in `tests/unit/test_status.py` — the approval gate blocks `APPROVED`/`DONE` with unverified blocking findings, permits when all `VERIFIED`, is unaffected by advisory findings (0% false-block), and degrades to the Feature 006 cycle-result gate when no handoffs exist [SC-003] [SC-008]
- [ ] T011 [P] [US2] Integration tests in `tests/integration/test_handoff_cli.py` — `handoff finding fix|verify` and `handoff close` exit/status/`--json`; approval-block surfaced via `status transition-phase DONE -r APPROVED` (exit 1, `approval-blocked`); **FR-009 composition**: a corrective change touching a path **not** in the handoff's `authorized_paths` (and not planned/acknowledged) classifies `unexplained` via `specops trace` drift — SpecOps adds **no** new gate here, it reuses Feature 010 [SC-003] [SC-004] [SC-010]

### Implementation for User Story 2

- [ ] T012 [US2] Implement `cmd_finding_fix` and `cmd_finding_verify` in `src/specops/handoff.py` — resolve the target finding **by id across any round's handoff** (carry-forward is structural per research R1 — findings stay in their round; already-`VERIFIED` findings from a prior round are untouched); `fix` links known task + ≥1 commit (`--commit`/`--auto` via `gitops.commits_in_range`) + actual `<CLASS>:<summary>` evidence (`status._validate_evidence`); `verify` enforces the mechanical precondition and no-auto-verify; illegal/precondition failures return exit-2 statuses leaving state unchanged; writes via `status._finalize` [SC-004] [SC-011]
- [ ] T013 [US2] Implement `cmd_close` and `blocking_approval_check(data)` in `src/specops/handoff.py` — `close` verifies all blocking findings in the **current** round `VERIFIED` then stamps `closed_at` (idempotent re-close = no-op), else `close-blocked` (exit 1); `blocking_approval_check` scans **every** cycle's handoff (feature-global, all rounds) and returns the unverified blocking-finding ids, so a still-open finding from an earlier round blocks approval [SC-010] [SC-003] [SC-011]
- [ ] T014 [US2] Wire `blocking_approval_check` into `status.cmd_transition_phase` in `src/specops/status.py` — hook **all three** DONE/APPROVED entry points so none can bypass the invariant: (a) the `REVIEW→DONE` APPROVED-record path (≈ line 580, before `cycles[-1]["result"] = "APPROVED"`), (b) the `current=="REVIEW" and target=="DONE"` gate (≈ line 573), and (c) the plain `elif target=="DONE"` gate (≈ line 593); fail closed (exit 1) naming the unverified blocking findings; an empty result (incl. no handoffs) falls through to the existing Feature 006 cycle-result gate unchanged (T010 asserts both DONE branches) [SC-003]
- [ ] T015 [US2] Register `handoff finding fix|verify` and `handoff close` in `src/specops/cli.py` — `<ID>` argument, `--task`, repeatable `--commit`, `--evidence`/`--auto`, `--json` [SC-008]

**Checkpoint**: US1 + US2 work independently — findings reach `VERIFIED` and approval is gated on them.

---

## Phase 5: User Story 3 — Validate and report the corrective handoff (Priority: P2)

**Goal**: Read-only `handoff validate` (four defect classes, distinct diagnostics, reconcile deferral for commit existence) and `handoff report` (human + JSON parity rendering each finding's chain and the remaining-blocking set).

**Independent Test**: A well-formed handoff validates at exit 0 and reports the full chain; each seeded defect exits 1 with one specific diagnostic and zero false positives; JSON output is byte-for-byte reproducible; both commands never mutate state.

### Tests for User Story 3

- [ ] T016 [P] [US3] Unit tests in `tests/unit/test_handoff.py` — each of the four defects (`dangling-reference`, `missing-closure`, `contradictory-state`, `duplicate-id`) detected as a distinct diagnostic at exit 1; zero false positives on a clean handoff; report human/JSON parity + canonical ordering + `output_version`; commit-dangling defers to reconcile (surfaced, not authoritative) [SC-005] [SC-008]
- [ ] T017 [P] [US3] Integration tests in `tests/integration/test_handoff_cli.py` — `handoff validate` and `handoff report` exit/status/`--json` matrix; read-only before/after ledger comparison; determinism across repeated runs [SC-005] [SC-008]

### Implementation for User Story 3

- [ ] T018 [US3] Implement `cmd_validate` in `src/specops/handoff.py` — read-only over `ledger.load_raw`; emit one distinct diagnostic per defect (dangling reference / missing closure on a blocking finding / contradictory state / duplicate id); defer commit-existence to `specops reconcile` (surface the dangling reference only) [SC-005]
- [ ] T019 [US3] Implement `cmd_report` in `src/specops/handoff.py` — render every handoff, each finding's `id → severity → rule → file:line → state → task/commit/evidence`, and the remaining unverified blocking set from `blocking_approval_check`, in canonical order; human and JSON from the same result object (parity); no timestamps in read output [SC-008] [SC-001]
- [ ] T020 [US3] Register `handoff validate` and `handoff report` in `src/specops/cli.py` — read-only, `--json` [SC-008]

**Checkpoint**: US1–US3 work independently — the handoff is inspectable and its integrity is enforced.

---

## Phase 6: User Story 4 — Render compatible revision reports and migrate legacy prose (Priority: P3)

**Goal**: Render `revisions/revision-X.md` deterministically from the structured state in the 010-compatible `<file>:<line> - <action>` format; re-source Feature 010's trace findings to stable ids with a legacy fallback; and opt-in import of legacy revision prose into structured findings.

**Independent Test**: Rendered `revision-X.md` is byte-deterministic and format-compatible with prior consumers; a legacy prose fixture reads without error, is never a defect, and imports with zero loss of location/action; the Feature 010 trace resolves stable ids when structured and falls back otherwise with all 010 fixtures still passing.

### Tests for User Story 4

- [ ] T021 [P] [US4] Unit tests in `tests/unit/test_handoff.py` and `tests/unit/test_trace.py` — `render_revision()` byte-equality + `<file>:<line> - <action>` compatibility + `APPROVED`/`Skipped gate:` preservation + canonical order; `trace._findings` prefers structured (emits stable id) and falls back to legacy parsing; import preserves every legacy line's location/action, defaults `advisory`/`OPEN` [SC-006] [SC-007] [SC-009]
- [ ] T022 [P] [US4] Integration tests in `tests/integration/test_handoff_cli.py` — `handoff import` exit/status/`--json`; **no regression**: existing Feature 010 trace fixtures continue to pass unchanged (legacy fallback path) [SC-009] [SC-007]

### Implementation for User Story 4

- [ ] T023 [US4] Implement `render_revision(feature_dir, round)` in `src/specops/handoff.py` — deterministic projection from the round's handoff to `revisions/revision-X.md` in the `<file>:<line> - <action>` format (ids stay in the ledger), preserving `APPROVED`/`Skipped gate:` lines, in canonical order [SC-006]
- [ ] T024 [US4] Re-source findings in `src/specops/trace.py` — `_findings()` prefers structured handoff findings (emit `{id, file, line, round, text}`) when any cycle has a `handoff`, else falls back to the current `revision-*.md` parsing; additive `id` on finding nodes; no 010 report-contract regression [SC-009]
- [ ] T025 [US4] Implement `cmd_import` in `src/specops/handoff.py` and register `handoff import [--round N]` in `src/specops/cli.py` — read legacy `<file>:<line> - <action>` lines, create `advisory`/`OPEN` structured findings preserving location/action, opt-in only, write via `status._finalize` [SC-007]

**Checkpoint**: All four stories independently functional; legacy consumers and Feature 010 unaffected.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Directive/governance wiring and the full quality gate.

- [ ] T026 [P] Update directive assets — `src/specops/templates/review.md` (author structured findings via `handoff finding add`; `handoff finding verify` + `handoff close`; `revision-X.md` is rendered, not hand-authored) and `src/specops/templates/directives/implement.md` (mark a resolved finding `FIXED` via `handoff finding fix`) [SC-002] [SC-003]
- [ ] T027 Amend `.specify/memory/constitution.md` — MINOR 1.6.0→1.7.0 recording the Principle IV directive extension (structured findings replace `revision-X.md` prose; review verifies/closes); additive, human-approved in this change set [SC-002]
- [ ] T028 [P] Update `CHANGELOG.md` (user-visible behavior + the v4→v5 migration requirement) and the EN/PT docs so both remain behaviorally equivalent for the new `handoff` surface (FR-026) [SC-008]
- [ ] T029 Run `quickstart.md` end-to-end against fixtures — verify every SC, `output_version`, the `0/1/2` taxonomy, read-only guarantees, and byte-for-byte determinism [SC-001] [SC-006] [SC-008]
- [ ] T030 Full quality gate under `conda run -n specops` — `ruff check`, `mypy` (`disallow_untyped_defs`), and `pytest --cov=specops --cov-fail-under=85`; flip the ROADMAP row 011 ACTIVE→MERGED in this feature's final commit [SC-001] [SC-002] [SC-003] [SC-004] [SC-005] [SC-006] [SC-007] [SC-008] [SC-009] [SC-010] [SC-011]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **BLOCKS all user stories** (v5 ledger + `handoff.py` contract).
- **User Stories (Phases 3–6)**: all depend on Foundational. US1 is the MVP; US2/US3/US4 depend only on the foundation and are independently testable (US3 report reuses `blocking_approval_check` from US2 — sequence US2 before US3, or stub the predicate in US3 tests).
- **Polish (Phase 7)**: depends on all shipped stories.

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on other stories.
- **US2 (P2)**: after Foundational. Independent of US1 (operates over seeded findings), though it reads records US1 writes in practice.
- **US3 (P2)**: after Foundational. Reuses `blocking_approval_check` (US2) for the remaining-blocking set — run after US2 or stub in tests.
- **US4 (P3)**: after Foundational. Independent; touches `trace.py` and rendering only.

### Within Each User Story

- Tests written and failing before implementation (Constitution task gate).
- `handoff.py` command logic before its `cli.py` registration.
- Story complete and independently green before the next priority.

### Parallel Opportunities

- T001 (setup) stands alone.
- Within Phase 2, T003 runs parallel to T004 (different files) after T002.
- Each story's `[P]` test tasks run together; implementation tasks touching `handoff.py` are sequential (same file), while `cli.py`/`trace.py`/`status.py` edits are separable.
- With capacity: US1, US2, US4 can proceed in parallel after Foundational; US3 trails US2.

---

## Parallel Example: User Story 2

```bash
# Launch US2 test tasks together (different files):
Task: "Unit tests for lifecycle + approval predicate in tests/unit/test_handoff.py"
Task: "Unit tests for the approval gate in tests/unit/test_status.py"
Task: "Integration tests for fix/verify/close + approval-block in tests/integration/test_handoff_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → 2. Phase 2 Foundational (v5 ledger + `handoff.py` contract) → 3. Phase 3 US1.
4. **STOP and VALIDATE**: record findings + authorized paths, reload the ledger, confirm resumability.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → structured findings persist & reload (MVP).
3. US2 → lifecycle + approval gate.
4. US3 → validation + reports.
5. US4 → render + legacy compat + 010 re-source.
6. Polish → directives, constitution amendment, docs, full gate.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- `[SC-xxx]` maps every task to the Success Criteria it satisfies (roadmap §4).
- Findings/handoffs are written **only** through `status._load_for_write`/`_finalize` (atomic + CAS); reads use `ledger.load_raw`.
- No `specops`/`handoff` command is run against this repository; all behavior is fixture-proven.
- Commit per user story / logical group (Constitution Principle III granularity; memory: commit-granularity-per-user-story).
