# Tasks: Hardening II — API & State Robustness

**Input**: Design documents from `/specs/019-api-state-robustness/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included per the Constitution task gate — every task closes only with passing automated tests. The Feature 018 golden-capture harness (`tests/golden/`) is reused as this feature's behavior-freeze instrument: SC-001 demands **zero** capture diffs (unlike 018, there is no sanctioned delta).

**Organization**: Tasks are grouped by user story. Stories are independently deliverable, but the recommended order is strictly P1 → P2 → P3 → P4: `status.py` is touched by US2/US3/US4, `handoff.py` by US3/US4, and `ledger.py` by US1/US3/US4, so parallel story execution is NOT recommended (same-file conflicts). Run all commands via `conda run -n specops …`.

## Format: `[ID] [P?] [Story] Description (FR/SC-xxx)`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- **(FR/SC-xxx)**: requirement / success criterion from spec.md the task serves
- Include exact file paths in descriptions

## Path Conventions

Single project: `src/specops/`, `tests/` at repository root (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: branch bookkeeping, roadmap registration, baseline measurements

- [X] T001 Commit the `specs/019-api-state-robustness/` artifacts (spec, plan, research, data-model, contracts, quickstart, checklists) and the updated `.specify/feature.json` on branch `019-api-state-robustness` (branch already exists)
- [X] T002 Flip the Feature 019 row `PLANNED → ACTIVE` in `ROADMAP.md` (§Feature Overview table, line ~90) as a commit in this feature's PR
- [X] T003 Record baselines in the PR description: the quickstart §4 scan outputs on the untouched tree (expected: 9 `isinstance(loaded, HandoffResult)`, 2 `--name-status` parse loops, 1 `(human)` hit in `gitops.py`, 2 `"no review cycles recorded"` occurrences in `status.py`) (SC-003, SC-004)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: prove the behavior-freeze instrument is green before any refactor lands

**⚠️ CRITICAL**: no refactor task starts before this passes

- [X] T004 Run the full gate on the untouched tree and confirm green: `conda run -n specops ruff check src tests && conda run -n specops mypy src && conda run -n specops python -m pytest` (golden replay in `tests/golden/` included via pytest); any pre-existing failure blocks the feature and must be triaged first (SC-001 baseline)

**Checkpoint**: baseline green — refactoring may begin

---

## Phase 3: User Story 1 — Concurrent ledger access cannot double-grant the lock (Priority: P1) 🎯 MVP

**Goal**: fix the stale-reclaim TOCTOU in `_LedgerLock` with an atomic-rename reclaim; single-winner property proven by a race test that fails on the old code.

**Independent Test**: `tests/unit/test_ledger_lock.py` passes repeatedly against the new lock and demonstrably fails against the old reclaim arm; full suite + golden replay byte-identical.

### Tests for User Story 1 (mandatory per Constitution task gate) ⚠️

- [X] T005 [US1] Create `tests/unit/test_ledger_lock.py` per `contracts/lock-protocol.md` §Regression test: (a) single-winner race — lock file pre-created with `os.utime` mtime older than `stale`, ≥4 barrier-synchronized threads enter `_LedgerLock.__enter__` (short `stale`, generous `timeout`), each acquirer asserts the concurrency counter reads 1 AND the lock file still holds its own token, looped ≥20 iterations; (b) fresh-lock contention — timeout raises `SpecopsError` with the exact "Ledger is locked by another process" message; (c) crash recovery — a reclaim winner's leaked lock is again reclaimable by age (G6). Falsification run: verify (a) FAILS against the current unlink+recreate reclaim before implementing T006, and record that in the task's commit message (FR-002, SC-002)

### Implementation for User Story 1

- [X] T006 [US1] Harden `_LedgerLock.__enter__` in `src/specops/ledger.py`: replace the `unlink+continue` stale arm with the reclaim-mutex sentinel (`<lock>.reclaim` via `O_CREAT|O_EXCL`; staleness re-checked UNDER the mutex before unlinking the main lock; token-checked sentinel release; stale sentinel breakable by age). NOTE: the plan's original atomic-rename design was FALSIFIED by the T005 race test (rename grabs the name's current inode — it stole the winner's fresh lock, 3 simultaneous holders); research D1 and contracts/lock-protocol.md updated to the sentinel design. Preserve token stamping, fsync, timeout deadline and message, 30 s default stale threshold, and the token-checked `__exit__` (FR-001)
- [X] T007 [US1] Close the story: T005 race test green across its amplification loop, full suite + golden replay zero diffs, timeout diagnostic byte-identical (SC-001, SC-002)

**Checkpoint**: the ledger's locking is race-free — MVP delivered

---

## Phase 4: User Story 2 — State transitions read as named steps with one DONE gate (Priority: P2)

**Goal**: `cmd_transition_phase` and `cmd_complete_task` become thin orchestrators over named sub-steps; the verbatim-duplicated Feature 006 DONE cycle gate collapses to one `_require_approved_cycle`.

**Independent Test**: characterization tests pin every failure-path message; after decomposition the suite + golden replay are byte-identical and `grep -c "no review cycles recorded" src/specops/status.py` returns 1.

### Tests for User Story 2 (mandatory per Constitution task gate) ⚠️

- [X] T008 [US2] Add characterization tests in `tests/unit/test_status_decomposition.py` asserting the **exact message** of every reachable `cmd_transition_phase` / `cmd_complete_task` failure path before refactoring: invalid result vocabulary, unknown phase, invalid sequence, REVIEW→IMPLEMENT without `-r REJECTED`, DONE with no cycles, DONE with latest cycle not APPROVED, DONE with result REJECTED (all via the REVIEW→DONE path — the `elif target == "DONE"` twin at `status.py:711-721` is statically DEAD code: sequence validation only admits `target=DONE` from REVIEW, which the first branch captures, so do NOT attempt a non-REVIEW characterization), blocking-findings refusal, evidence-XOR violations, task-not-IN_PROGRESS, missing `started_commit` (SC-001)

### Implementation for User Story 2

- [X] T009 [US2] Extract `_require_approved_cycle(cycles) -> None` in `src/specops/status.py` carrying today's exact "Cannot enter DONE: no review cycles recorded." / "latest review cycle result is …" messages; both DONE branches of `cmd_transition_phase` (lines ~702-721) call it — noting the `elif target == "DONE"` branch is a *defensive dead* duplicate (see T008): the consolidation absorbs it into the single gate rather than deleting the defense (research D2) (FR-004, SC-003)
- [X] T010 [US2] Decompose `cmd_transition_phase` in `src/specops/status.py` into the research D3 sub-steps — `_normalize_result`, `_validate_transition`, `_enter_review`, `_close_rejected_review`, `_gate_done` (blocking-findings check then `_require_approved_cycle`, order preserved) — leaving the command a thin orchestrator; behavior byte-identical (FR-003)
- [X] T011 [US2] Decompose `cmd_complete_task` in `src/specops/status.py` into `_validate_evidence_args`, `_require_in_progress`, `_auto_evidence` / `_manual_evidence`, `_record_completion` (research D3); behavior byte-identical (FR-003)
- [X] T012 [US2] Close the story: T008 characterization tests + full suite + golden replay green; `grep -c "no review cycles recorded" src/specops/status.py` → 1 (SC-001, SC-003)

**Checkpoint**: the state machine reads as named steps; the DONE gate has one implementation

---

## Phase 5: User Story 3 — Internal contracts are typed, not conventions (Priority: P3)

**Goal**: `TypedDict` schemas for all ledger records in a new `records.py` (static-only, serialization untouched); the handoff mutation loader gets a typed error path with zero class-probing call sites.

**Independent Test**: mypy clean with no new suppressions; a seeded record-key typo fails mypy; `grep -c "isinstance(loaded, HandoffResult)" src/specops/handoff.py` → 0; suite + golden replay unchanged.

### Tests for User Story 3 (mandatory per Constitution task gate) ⚠️

- [ ] T013 [P] [US3] Create `tests/unit/test_records_typing.py`: key-set parity between the `records.py` TypedDicts and the dicts the factories actually emit — `findings.new_finding` ↔ `FindingRecord` base keys, `evidence.build_record` ↔ `EvidenceRecord`, the rendered `src/specops/templates/status.yaml` top level ↔ `LedgerDocument`, `status._sync_tasks`'s new-task dict ↔ `TaskRecord` required keys (the SC-007 serialization guard) (FR-005, SC-007)

### Implementation for User Story 3

- [ ] T014 [P] [US3] Create `src/specops/records.py` (stdlib-only, no intra-package imports) with the 7 TypedDicts per data-model.md: `TaskRecord`, `FindingRecord`, `ReviewCycleRecord`, `HandoffRecord`, `EvidenceRecord`, `ContextProvenance`, `LedgerDocument` — `total=False` sections exactly as tabulated (FR-005)
- [ ] T015 [US3] Adopt the types at the producer signatures: `findings.new_finding -> records.FindingRecord` in `src/specops/findings.py`; `evidence.build_record`/`append_record` -> `records.EvidenceRecord` in `src/specops/evidence.py` (both stay dependency-light — records is stdlib-only); runtime dicts and key order untouched (FR-005)
- [ ] T016 [US3] Adopt the types at the consumer signatures: `src/specops/ledger.py` (`validate_invariants`, `finding_structural_defects`, invariant helpers take `records.LedgerDocument`/record types), `src/specops/status.py` (the US2 sub-steps + `_sync_tasks`, `compact_status`), `src/specops/handoff.py` (`_cycles`, `_iter_findings -> Iterator[tuple[ReviewCycleRecord, FindingRecord]]`, `_find_by_id`, view builders), `src/specops/trace.py` where it reads tasks/acknowledgements; casts happen once at the canonical load points; `conda run -n specops mypy src` clean with no new ignores/overrides (FR-005, FR-006)
- [ ] T017 [US3] Replace the `handoff._load_write` union in `src/specops/handoff.py`: frozen dataclass `LoadedLedger(feature_dir, data, base_revision, base_violations, repo)` + module-private `HandoffLoadRefused(status, human)` raised on the not-a-repo refusal + `_handoff_command(cmd)` decorator as the single exception→`HandoffResult` conversion point; update all 9 call sites (`cmd_finding_add`, `cmd_authorize`, `cmd_finding_fix`, `cmd_finding_verify`, `cmd_finding_dismiss`, `cmd_close`, `cmd_import`, `_apply_import`, `cmd_finding_promote`); refusal output byte-identical (research D5) (FR-007, SC-004)
- [ ] T018 [US3] Close the story: seeded-typo falsification (temporarily `task["staus"]` in `status.py` → mypy MUST fail → revert, per quickstart §3), `grep -c "isinstance(loaded, HandoffResult)" src/specops/handoff.py` → 0, full suite + golden replay green (SC-004, SC-005)

**Checkpoint**: record shapes and the loader contract are statically checked

---

## Phase 6: User Story 4 — One authority for each remaining parser, sentinel, and rendering rule (Priority: P4)

**Goal**: one `--name-status` parser (rename-awareness parameterized), sentinel out of the git layer, loud template-drift failure via `fsutil.render_template`, one gate-profile field table, doctor without exception-threading.

**Independent Test**: quickstart §4 scans hit their stated counts; the template-drift test proves the loud failure; suite + golden replay unchanged.

### Tests for User Story 4 (mandatory per Constitution task gate) ⚠️

- [ ] T019 [P] [US4] Extend `tests/unit/test_gitops.py` (existing module test file — repo convention, one file per module) with parser tests: `gitops.parse_name_status` on plain/rename (`R100\told\tnew`)/blank-line input; `name_status_diff` mode matrix — `rename_aware=False` ⇒ `--no-renames` decomposition, `True` ⇒ single `R` on new path, `cached=True` ⇒ staged diff — against a fixture repo (FR-008)
- [ ] T020 [P] [US4] Add sentinel tests in `tests/unit/test_human_commit.py`: `gitops.is_ancestor(repo, "(human)")` now returns False at the git layer; `ledger.is_human_commit` truth table; command-level exemptions preserved — `handoff validate` does not flag `(human)` finding commits, `reconcile` keeps the R11 pass, `validate_identity` passes a hand-edited `(human)` baseline (FR-009)
- [ ] T021 [P] [US4] Extend `tests/unit/test_fsutil.py` (existing module test file) with render tests: `fsutil.render_template` fills every `{{key}}`; a template with a novel `{{new-placeholder}}` raises `SpecopsError` naming it (never writes residue); extra mapping keys ignored (FR-010, SC-006)

### Implementation for User Story 4

- [ ] T022 [US4] Caller-side sentinel filters FIRST (behavior-identical while the gitops short-circuit still exists — double protection, suite stays green at this boundary): in `src/specops/ledger.py` add `HUMAN_COMMIT = "(human)"` + `is_human_commit(sha)` and filter the sentinel in `validate_identity` (baseline arm); in `src/specops/reconcile.py` the baseline-warn arm gains the filter and the task-commit loop switches its literal to `ledger.HUMAN_COMMIT`; in `src/specops/handoff.py` `cmd_validate` (line ~693) skip `is_human_commit` shas before `gitops.is_ancestor` (research D7 audit table) (FR-009)
- [ ] T023 [US4] In `src/specops/gitops.py`: add `parse_name_status(raw)` and `name_status_diff(repo, start_sha, end_sha="HEAD", *, rename_aware, cached=False)`; `effective_diff_status` becomes a thin `rename_aware=False` wrapper (same name/signature/`[]`-on-error); remove the `(human)` short-circuit from `is_ancestor` — safe now because every ledger-value caller filters since T022; T020's git-layer assertion (`is_ancestor("(human)") is False`) turns green here (research D6, D7) (FR-008, FR-009)
- [ ] T024 [US4] In `src/specops/lane.py` (depends on T023): delete `_parse_name_status`; `_diff_status` composes `gitops.name_status_diff(rename_aware=True, …)` preserving the `contextlib.suppress` degrade and the committed+staged union (FR-008, SC-003)
- [ ] T025 [US4] Add `render_template(text, mapping)` to `src/specops/fsutil.py` (raises `SpecopsError` naming unfilled `{{...}}`; extra keys ignored); switch the three render sites — `cmd_init_spec` and `synthesize_ledger_at_plan` in `src/specops/status.py`, `cmd_start` in `src/specops/lane.py` — to it (research D8) (FR-010)
- [ ] T026 [US4] In `src/specops/gateprofiles.py`: introduce the declarative field table (name/type-spec/default/defect-message per field, `applies` keys derived from it) consumed by BOTH `_parse_profile`/`_parse_predicate` and `validate`/`_validate_applies`; every lenient fallback and every defect message byte-identical — existing gateprofile tests must pass unchanged (research D9) (FR-011)
- [ ] T027 [US4] In `src/specops/doctor.py`: extract `_error_domain(domain, exc)` from `_run`'s except-arms; `diagnose` builds the cli_extension/legacy error domains directly on a `detect_state` failure; drop the `state_error` parameter from `_domain_cli_extension` and `_domain_legacy`; existing doctor tests prove output parity (research D10) (FR-012)
- [ ] T028 [US4] Close the story: full suite + golden replay green; quickstart §4 scans at stated counts (0 lane parse loop, 0 `(human)` in gitops.py, 0 `state_error` threaded into `_domain_*`) (SC-001, SC-003, SC-006)

**Checkpoint**: every US4 concern has exactly one implementation

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: changelog, docs, final validation, roadmap close-out

- [ ] T029 [P] Add the CHANGELOG.md `[Unreleased]` entry: internal hardening with zero user-visible change; note the lock stale-reclaim race fix (defect, not behavior change) and the internal API additions (records, render_template, name_status_diff, HUMAN_COMMIT) per contracts/internal-api.md
- [ ] T030 [P] Sweep `docs/` (EN and PT) for references to renamed/changed internals (lock reclaim behavior, `(human)` handling, handoff loader); update only where internals are actually described
- [ ] T031 Run the full quickstart validation end-to-end (quickstart §1–§7) and record the §4 scan outputs + §2 falsification note in the PR description (all SC)
- [ ] T032 Flip the Feature 019 row `ACTIVE → MERGED` in `ROADMAP.md` as the final commit inside this feature's PR (repo convention: the flip rides the feature PR, never a separate chore PR)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately
- **Foundational (Phase 2)**: after Setup — BLOCKS all stories (baseline must be green)
- **User Stories (Phases 3–6)**: all depend on Phase 2. Recommended strictly sequential P1 → P2 → P3 → P4 (same-file overlaps: `status.py` in US2/US3/US4; `handoff.py` in US3/US4; `ledger.py` in US1/US3/US4)
- **Polish (Phase 7)**: after all stories; T032 is the final commit

### Story ordering rationale

- **US1 (P1)** is self-contained in `ledger.py`'s lock class + one new test file — the true MVP (the only defect fix)
- **US2 (P2)** must precede US3's typing of the new sub-step signatures (T016 types what T010/T011 create)
- **US3 (P3)** must precede nothing structurally, but its handoff decorator (T017) touches the same command bodies US4's sentinel filter (T023) edits — keep the order
- **US4 (P4)** lands last; sentinel order is deliberate — T022 (caller filters, harmless with the gitops short-circuit still present) strictly BEFORE T023 (short-circuit removal), so the suite is green at every task boundary

### Within Each User Story

- Tests written and observed to FAIL (or characterize current behavior) before implementation
- Each story closes with: full suite + golden replay green (zero capture diffs — SC-001)
- One commit per user story (repo convention); intermediate task closes need no commit

### Parallel Opportunities

- T013/T014 (US3): parity test + records module — different new files
- T019/T020/T021 (US4): the three new test files — independent
- T029/T030 (Polish): changelog + docs — different files
- Cross-story parallelism: NOT recommended (see overlaps above)

---

## Parallel Example: User Story 4

```bash
# The three US4 test tasks touch disjoint files and can be authored together:
Task: "Parser tests extended in tests/unit/test_gitops.py"
Task: "Sentinel tests in tests/unit/test_human_commit.py (cross-module: gitops/ledger/reconcile/handoff)"
Task: "Render tests extended in tests/unit/test_fsutil.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phases 1–2 (Setup + baseline green)
2. Phase 3: the lock race fix with its falsified-then-green race test
3. **STOP and VALIDATE**: suite + golden replay byte-identical; the one real defect is retired
4. US2–US4 are pure maintainability increments on top

### Incremental Delivery

Each story ends at a checkpoint with the full gate green and byte-identical captures, so the branch is mergeable after any story if priorities shift. The scans (quickstart §4) quantify progress story by story (9→0 probes, 2→1 parsers, 2→1 gates, 1→0 sentinel).

---

## Notes

- Byte-identical means byte-identical: no golden capture may change; a diff in any capture is a defect in the task that produced it, not a capture to re-record (unlike 018, there is NO sanctioned delta)
- No Self-Application: everything runs through `tests/` fixtures; never run `specops` against this repository
- `conda run -n specops` for mypy/ruff/pytest (the base env's numpy stub breaks mypy)
- Commit granularity: one commit per user story; `T00x done` progress rides tasks.md checkboxes
