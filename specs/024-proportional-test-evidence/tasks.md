---
description: "Task list for Feature 024 — Test Execution Only at the Review Gate"
---

# Tasks: Test Execution Only at the Review Gate

**Input**: Design documents from `/specs/024-proportional-test-evidence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contracts.md, quickstart.md

**Tests**: Included. This repo is test-driven and the constitution requires a passing test gate per task; each story ships with its tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2
- All commands run under `conda run -n specops …` (per project convention).

## Path Conventions

Single project: `src/specops/`, `tests/` at repo root.

---

## Phase 1: Setup

**Purpose**: Establish a known-green baseline before behavior changes.

- [x] T001 Confirm the baseline suite is green on this branch: `conda run -n specops pytest -q` — and note the two tests that this feature will deliberately change (`tests/integration/test_gate_readonly_determinism.py::test_review_and_gate_report_read_only`, plus the `--auto` test-run assertions in `tests/unit/test_status.py`), so their later modification is intentional, not a regression.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-story blocking work.

**None.** US1 and US2 touch disjoint modules (`review.py`/`evidence.py`/`gitops.py` vs `status.py`) and are independently implementable and testable. Story-local prerequisites live inside each story's phase. Proceed directly to Phase 3.

---

## Phase 3: User Story 1 - Terminal gate reuses the soft gate's result (Priority: P1) 🎯 MVP

**Goal**: Activate the Feature 012 evidence cache so `preflight` persists a passing `lint`/`test` gate run and a later identical run reuses it (`cached`) instead of re-executing — guarded by a working-tree digest, limited to command-executing gates, superseding by cache key. Full-suite executions per corrective-loop iteration drop from 2 to 1.

**Independent Test**: Run `specops preflight --json --soft` then `specops preflight` on an unchanged tree; the second reports the `test` gate as `cached` and does not re-run the command. Make an uncommitted edit and confirm the next run re-executes.

### Tests for User Story 1 (write first; MUST fail before implementation)

- [x] T002 [P] [US1] In `tests/unit/test_evidence_record.py`, add tests: `cache_key(...)` includes a `worktree_digest` field **only when provided**, and an `auto`-style call (no digest) yields a byte-identical dict / id to the pre-feature key (id stability, no migration). Also assert back-compat (FR-009): existing `auto` evidence-record ids are unchanged (no schema migration triggered).
- [x] T003 [P] [US1] In `tests/unit/test_gitops.py`, add tests for `worktree_digest(repo)`: deterministic on identical tree state; changes on a tracked-file modification; changes on a new untracked file; stable "clean" value on a clean tree.
- [x] T004 [P] [US1] In `tests/unit/test_review.py` / `tests/integration/test_gate_cache.py`, add tests: a passing `test`/`lint` gate records a `gate:<name>@<ver>` cache record in the git-dir cache (superseding the prior one for the same producer); a second identical evaluation returns `disposition="cached"` with **no** command execution; a cached record with non-zero `exit_code` is NOT reported as PASS; `reconcile`/`working-tree`/`drift` are never cached; an uncommitted edit (changed `worktree_digest`) forces re-execution; the committed ledger and working tree are byte-identical before/after.
- [x] T005 [P] [US1] In `tests/integration/test_preflight_cli.py`, add an end-to-end test: `preflight --json --soft` then `preflight` over an unchanged tree → `test` gate `required` then `cached`, suite executed once; after an uncommitted edit the following run re-executes (per quickstart Scenarios 2–3).

### Implementation for User Story 1

- [x] T006 [P] [US1] Add to `src/specops/gitops.py`: `git_dir(repo: Repository) -> Path` (`rev-parse --git-dir`, resolved absolute) and `worktree_digest(repo: Repository) -> str` (`"sha256:" + sha256(<git diff HEAD bytes> + b"\0" + "\n".join(sorted(<porcelain -uall lines>)).encode())`; see data-model.md → Working-tree digest).
- [x] T007 [P] [US1] Add optional `worktree_digest: str | None = None` to `evidence.cache_key(...)` in `src/specops/evidence.py`, included in the returned dict **only when not None** (preserving `auto` id stability). Update the module docstring's cache-key tuple note.
- [x] T008a [P] [US1] Add `src/specops/gatecache.py`: ephemeral gate-run cache at `<git-dir>/specops/gate-cache/<feature>.yaml`. `load(repo, feature_dir) -> list[EvidenceRecord]` (missing → `[]`) and `persist(repo, feature_dir, records) -> None` (mkdir parents, atomic YAML write). No working-tree writes.
- [x] T008 [US1] In `src/specops/review.py` (depends on T006, T007, T008a): (a) in `profile_gates`, compute `worktree_digest` once and thread it into `_run_profile_gate`; use `gatecache.load(repo, feature_dir)` as the cache source instead of `existing_evidence`; (b) build the gate cache key with the digest; (c) on a **passing** run (`exit_code == 0`) collect the `gate:<name>@<ver>` record, and after the loop `evidence.append_record(..., supersede=True)` each into the loaded cache list and `gatecache.persist(...)` once; (d) harden the cache-hit branch (returns PASS unconditionally today, lines ~183-186) to report PASS only when the cached record's `exit_code == 0`; (e) leave `_reconcile_gate`/`_working_tree_gate`/`_drift_gate` untouched so only `lint`/`test` are cacheable; (f) update the `existing_evidence`/gate-cache note to reflect that caching reads/writes the git-dir cache and the **ledger stays read-only**.
- [x] T009 [US1] Update `tests/integration/test_gate_readonly_determinism.py::test_review_and_gate_report_read_only`: the `snapshot_tree == before` assertion still holds (cache lives in `.git`, excluded from `snapshot_tree`) — keep it. Reframe determinism only: a fresh run then a cached run differ in the gate `disposition`, so assert repeated **cached** runs are byte-identical (`r2 == r3`) instead of `r1 == r2`; `gate report`/`gate list`/`gate validate` remain fully read-only.

- [x] T010 [US1] Verify US1: `conda run -n specops pytest tests/unit/test_evidence_record.py tests/unit/test_gitops.py tests/unit/test_review.py tests/integration/test_gate_cache.py tests/integration/test_preflight_cli.py tests/integration/test_gate_readonly_determinism.py -q` all green; `conda run -n specops mypy src/specops/review.py src/specops/evidence.py src/specops/gitops.py src/specops/gatecache.py` clean.

**Checkpoint**: US1 is independently functional — terminal-gate reuse works; the redundant back-to-back full-suite run is eliminated. This is the MVP.

---

## Phase 4: User Story 2 - Closing a user story runs no tests (Priority: P2)

**Goal**: `complete-task --auto` stops running any test command and records only mechanical commit + `CODE_DIFF` evidence; test enforcement lives entirely at the review gate.

**Independent Test**: With a `test_command` that drops a sentinel when run, close a user story's final task with `--auto`; the sentinel is absent and the task is `DONE` with `CODE_DIFF:…` evidence. With `test_command` unset, the close still succeeds.

### Tests for User Story 2 (write first; MUST fail before implementation)

- [x] T011 [P] [US2] In `tests/unit/test_status.py`, update/add tests: `complete-task --auto` invokes **no** test command (assert `shell.run_client_command` is not called with the test command / sentinel absent); the recorded legacy string is `CODE_DIFF:…` with no `TEST_REPORT`; the structured `auto` record has `command="(auto)"`; `test_command` unset is **not** an error for `--auto`; the "no commits since task start" guard still fails closed.

### Implementation for User Story 2

- [x] T012 [US2] In `src/specops/status.py`, rewrite `_auto_evidence` (~line 602): remove the `test_command` lookup, the `shell.run_client_command` call, and the non-zero fail path; keep `gitops.commits_in_range` harvesting and the `CODE_DIFF:` summary; return evidence string `CODE_DIFF:<n files across m commits: …>` and evidence command `"(auto)"`. Adjust `_record_completion`/callers so the structured `auto` record uses `command="(auto)"`. Preserve the no-commits guard.

- [x] T013 [US2] Verify US2: `conda run -n specops pytest tests/unit/test_status.py -q` green; `conda run -n specops mypy src/specops/status.py` clean.

**Checkpoint**: US1 AND US2 both work independently — per-story test runs are gone; the gate is the single test-enforcement point.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T014 [P] Amend `.specify/memory/constitution.md`: narrow **Principle III only** (`--auto` collects commit + `CODE_DIFF` evidence, runs no test; verification at the gate). **Principle IV is unchanged** — the git-dir gate cache keeps `preflight` byte-for-byte read-only. Bump version 1.10.0 → 1.11.0; update the Sync Impact Report comment and `Last Amended` date. (Depends on T012 behavior existing.)
- [x] T015 [P] Update injected templates for the amended directives: revise the Ledger Loop wording in `src/specops/templates/directives/implement.md` so `--auto` is described as recording diff/commit evidence (no test run); then sweep for stale "byte-for-byte read-only" / per-close test-execution claims **beyond templates** — `grep -rn "read-only\|byte-for-byte\|test_command\|TEST_REPORT" src/specops/templates/ docs/ README.md README.pt-br.md` and the CLI help strings for `preflight`/`review`/`complete-task` in `src/specops/cli.py` — and fix each to match the narrowed contract. Keep `README.md` and `README.pt-br.md` in parity in the same change.
- [x] T016 Verify the corrective-loop reuse end-to-end in `tests/integration/test_workflow_orchestration.py` (or add an assertion): across a happy-path run the full suite executes once at `review-soft` and `terminal-gate` reuses it; add coverage if absent. **Also assert the enforcement invariant (FR-008/SC-006)**: a hard `preflight` with a failing/blocking required gate still yields REJECTED (non-zero exit) and no path reaches DONE without a passing full-suite gate result — i.e. moving tests out of the dev phase did not weaken the gate's blocking behavior.
- [x] T017 Run the quickstart validation scenarios in `specs/024-proportional-test-evidence/quickstart.md` (Scenarios 1–6) against a scratch fixture repo; confirm each expected outcome.
- [x] T018 Full gate: `conda run -n specops pytest -q` (whole suite green, including golden), `conda run -n specops mypy src/specops`, `conda run -n specops ruff check src tests`.
- [x] T019 [P] Add a CHANGELOG `[Unreleased]` entry describing the behavior change (tests only at the review gate; `--auto` records diff evidence; terminal-gate reuse) and the constitution 1.11.0 amendment.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: none — start immediately.
- **Foundational (Phase 2)**: empty; does not block.
- **US1 (Phase 3)** and **US2 (Phase 4)**: both depend only on Setup; they are mutually independent and may proceed in parallel or in priority order (US1 first as MVP).
- **Polish (Phase 5)**: T014/T015 depend on US1 (T008) and US2 (T012) behavior; T016–T018 depend on both stories; T019 is independent.

### Within User Story 1

- Tests T002–T005 written first (fail) → implementation T006/T007 (parallel, different files) → T008 (needs T006+T007) → T009 (test narrowing) → T010 verify.

### Within User Story 2

- Test T011 first (fail) → T012 implementation → T013 verify.

### Parallel Opportunities

- US1 tests: T002, T003, T004, T005 in parallel (distinct files).
- US1 impl primitives: T006 and T007 in parallel (distinct files); T008 waits on both.
- Across stories: entire US2 (T011–T013) can run in parallel with US1 (disjoint files).
- Polish: T014, T015, T019 in parallel.

---

## Parallel Example: User Story 1

```bash
# Tests (write-first, expect failures):
Task: "T002 cache_key worktree_digest + auto-id stability in tests/unit/test_evidence.py"
Task: "T003 worktree_digest determinism/invalidation in tests/unit/test_gitops.py"
Task: "T004 gate persistence/cached/exit_code/scope in tests/unit/test_review.py"
Task: "T005 terminal reuse + invalidation in tests/integration/test_preflight_cli.py"

# Implementation primitives (parallel):
Task: "T006 gitops.worktree_digest in src/specops/gitops.py"
Task: "T007 evidence.cache_key optional worktree_digest in src/specops/evidence.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup (T001).
2. Phase 3 US1 (T002–T010) → **STOP and VALIDATE** the terminal-gate reuse independently (quickstart Scenarios 2–5). This alone removes the most-complained redundancy and is shippable.

### Incremental Delivery

1. US1 → validate → the review-soft/terminal-gate double-run is gone.
2. US2 → validate → per-story test runs are gone (U+2 → 1).
3. Polish → constitution 1.11.0 + directive wording + full gate + CHANGELOG.

---

## Notes

- Commit granularity: one commit per user story (US1, then US2), plus a Polish commit — per repo convention.
- Do not run `specops` against this repo itself; validate with the pytest suite and scratch fixtures (Principle / project memory: no self-application).
- The constitution amendment (T014) and its directive template update (T015) MUST land in the same change set as the behavior (governance rule).
