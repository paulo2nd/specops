---
description: "Task list for Feature 026 — Supported Recovery Operations"
---

# Tasks: Supported Recovery Operations

**Input**: Design documents from `/specs/026-supported-recovery-operations/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli-commands.md](./contracts/cli-commands.md)

**Tests**: Mandatory. Per the Global Definition of Done, every new CLI surface carries unit, integration, error-path, and idempotency coverage, and every persisted-format change carries a forward-migration test. Tests are written before the implementation they cover.

**Organization**: Grouped by user story. The two shared foundations both stories need — the `feature.py` module and the feature-resolution alignment — live in Phase 2, so no story depends on another.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 — maps to the user stories in spec.md
- `[SC-00N]` tags record success-criteria coverage (validated by `specops consistency`)

## Path Conventions

Single Python package: `src/specops/`, `tests/unit/`, `tests/integration/` at repository root. All tooling runs under `conda run -n specops …`.

---

## Phase 1: Setup

**Purpose**: Establish a known-green baseline before touching a versioned persisted format.

- [X] T001 Confirm the baseline suite is green — run `conda run -n specops pytest -q`, `mypy src/`, `ruff check .` and record the pass counts in the task evidence
- [X] T002 [P] Add the v8 ledger builder the migration test reads from, inline in `tests/unit/test_ledger_v9_migration.py` — the house pattern for migration tests (v6/v7 both build inline); `tests/fixtures/` holds external *input* formats, not ledgers

**Checkpoint**: baseline recorded; a later regression is attributable.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The v8 → v9 schema bump, the amendment record shape, and the two pieces US2 and US3 share.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### Tests

- [X] T003 [P] Write the forward-migration test asserting v8 → v9 is a pure version bump — every task, evidence, acknowledgement and review-cycle record identical, only `schema_version` changed — in `tests/unit/test_ledger_v9_migration.py` [SC-011]
- [X] T004 [P] Write tests for the additive `amendment` / `reason` fields on `EvidenceRecord`: absent by default, present and typed when supplied, and `reason` required whenever `amendment` is true, in `tests/unit/test_evidence_record.py`
- [X] T005 [P] Write the id-derivation test asserting two amendments on the same task with an identical reason and commit range receive distinct ids via the amendment index, in `tests/unit/test_evidence_record.py`
- [X] T006 [P] Write the resolution-precedence tests: override before pointer file before inference, with a relative override normalized against the repo root exactly as Spec Kit normalizes it, in `tests/unit/test_speckit_resolution.py` [SC-007]
- [X] T007 [P] Write the non-persistence test asserting resolution never writes `.specify/feature.json` (SpecOps reads are read-only resolutions, research D6), in `tests/unit/test_speckit_resolution.py` [SC-007]
- [X] T008 [P] Write the provenance test asserting resolution reports `override` / `pointer` / `inferred`, in `tests/unit/test_speckit_resolution.py` [SC-007]
- [X] T009 [P] Write the unresolvable-override test: an override naming a non-existent directory is reported as such and never silently falls back to the pointer file, in `tests/unit/test_speckit_resolution.py` [SC-007] [SC-009]

### Implementation

- [X] T010 Add the optional `amendment: bool` and `reason: str` fields to `EvidenceRecord` in `src/specops/records.py`
- [X] T011 Extend `build_record` to accept and emit `amendment` / `reason`, and accept the amendment subject form `<task_id>#amend<N>:<reason>`, in `src/specops/evidence.py`
- [X] T012 Bump `CURRENT_SCHEMA` 8 → 9 with the v9 documentation block explaining the pure-version-bump rationale, in `src/specops/ledger.py`
- [X] T013 Add the v9 invariant to `_evidence_violations` — a record with `amendment: true` must carry a non-empty `reason` — in `src/specops/ledger.py` [SC-011]
- [X] T014 Remove the stale `schema_version: 4` declaration from `src/specops/templates/status.yaml` so the template is a pure content seed, and assert a fresh `init-spec` ledger classifies CURRENT (regression guard for #69) [SC-011]
- [X] T015 Add `SPECIFY_FEATURE_DIRECTORY` as the top-precedence source in `resolve_feature_dir`, normalizing a relative value against the repo root, without persisting it, in `src/specops/speckit.py` [SC-007]
- [X] T016 Return resolution provenance (`override` / `pointer` / `inferred`) alongside the resolved path, keeping the existing single-value entry point intact for current callers, in `src/specops/speckit.py`
- [X] T017 Create `src/specops/feature.py` with the module docstring and no commands yet, and register the empty `feature` sub-app in `src/specops/cli.py` — the scaffold US2 and US3 each extend independently

**Checkpoint**: schema v9 lands with zero behavior change; resolution matches Spec Kit; the full suite is green.

---

## Phase 3: User Story 1 — Correct the evidence on an already-closed task (Priority: P1) 🎯 MVP

**Goal**: A task closed with wrong or missing evidence can be corrected, append-only, without reopening it.

**Independent Test**: on a fixture with a `DONE` task carrying known-wrong evidence, run `amend-task` with corrected evidence and a reason; the task stays `DONE`, the original record is present, unmodified and marked superseded, the new record is current and carries its reason, and `reconcile` accepts the ledger.

### Tests for User Story 1 ⚠️

- [X] T018 [P] [US1] Write the happy-path test: amending a `DONE` task leaves status, `completed_at`, `commits`, `started_commit` and `context_provenance` untouched, in `tests/unit/test_amend_task.py` [SC-001]
- [X] T019 [P] [US1] Write the append-only test: after one amendment the prior record is present with its original summary and timestamp and `superseded_by` set; exactly one referenced record has `superseded_by: null`, in `tests/unit/test_amend_task.py` [SC-002]
- [X] T020 [P] [US1] Write the repeated-amendment test: amending twice yields three retained records in order with only the newest current, in `tests/unit/test_amend_task.py` [SC-002]
- [X] T021 [P] [US1] Write the task-scoped supersede test proving an amendment on task A leaves another task's evidence records untouched (the failure mode of the producer-scoped helper, research D3), in `tests/unit/test_amend_task.py` [SC-002]
- [X] T022 [P] [US1] Write the multi-record test: a task whose `evidence_refs` holds several current records has all of them superseded together by one amendment, in `tests/unit/test_amend_task.py` [SC-002]
- [X] T023 [P] [US1] Write the no-identifier test asserting `amend-task` exposes no option to target a single prior evidence record and rejects one if supplied (FR-002b), in `tests/unit/test_amend_task.py` [SC-002]
- [X] T024 [P] [US1] Write the legacy-string test: a current-schema ledger whose `DONE` task has a non-empty `evidence` string but empty `evidence_refs` gets the original materialized as a record before the amendment supersedes it, in `tests/unit/test_amend_task.py` [SC-002]
- [X] T025 [P] [US1] Write the identical-evidence test: amending with evidence identical to the current value is still recorded as an amendment, never dropped as a duplicate, in `tests/unit/test_amend_task.py` [SC-002]
- [X] T026 [P] [US1] Write the orphaned-task test: a `DONE` but orphaned task can be amended, in `tests/unit/test_amend_task.py` [SC-001]
- [X] T027 [P] [US1] Write the reason-not-judged test asserting an arbitrary, low-quality, or nonsensical reason is recorded verbatim and never scored, gated on, or rejected for its content (FR-007), in `tests/unit/test_amend_task.py` [SC-001]
- [X] T028 [P] [US1] Write the no-session-inference test asserting a task closed in the current run can be amended — the recovery-only restriction is instructional and never mechanically enforced (FR-023, FR-026), in `tests/unit/test_amend_task.py` [SC-001]
- [X] T029 [P] [US1] Write the error-path tests asserting non-zero exit and no write for: task not found, task not `DONE`, missing/empty `--reason`, evidence violating the grammar — in `tests/unit/test_amend_task.py` [SC-009]
- [X] T030 [P] [US1] Write the exit-2 tests asserting an unparseable ledger and a run outside a Git repository return 2, not 1, in `tests/unit/test_amend_task.py` [SC-009]
- [X] T031 [P] [US1] Write the no-reopen test asserting no command path returns a `DONE` task to `IN_PROGRESS` or `PENDING`, in `tests/unit/test_amend_task.py` [SC-001]
- [X] T032 [P] [US1] Write the `reconcile` acceptance test over an amended ledger, in `tests/unit/test_amend_task.py` [SC-001]
- [X] T033 [P] [US1] Write the trace-report test asserting `evidence_amended` and `evidence_history` appear for an amended task and are absent for an ordinary close, in `tests/unit/test_trace.py` [SC-003]
- [X] T034 [P] [US1] Write the inherited-evidence test: closing a finding with `--auto` against an amended task produces a finding evidence record carrying the amendment provenance, never presenting the corrected value as ordinary close-time evidence (FR-006a), in `tests/unit/test_handoff.py` [SC-004]
- [X] T035 [P] [US1] Write the integration test driving close → wrong evidence → amend → `reconcile` → `trace report` → finding fix end to end, in `tests/integration/test_recovery_amend.py` [SC-001] [SC-003] [SC-004]

### Implementation for User Story 1

- [X] T036 [US1] Implement the task-scoped supersede helper marking exactly the task's current `evidence_refs` records as superseded by a new id, in `src/specops/status.py`
- [X] T037 [US1] Implement the legacy-string materialize step that converts a non-empty `evidence` string with no refs into a structured record before superseding it, in `src/specops/status.py`
- [X] T038 [US1] Implement `cmd_amend_task` — validate reason and evidence grammar before any read, require `DONE`, build the amendment record with `producer="amend"`, supersede the task's current records, append the new ref, and update the legacy `evidence` string to the amended value — in `src/specops/status.py` [SC-001] [SC-002]
- [X] T039 [US1] Register `status amend-task <TASK_ID> --evidence --reason` with the success and refusal output from contracts/cli-commands.md, in `src/specops/cli.py` [SC-009]
- [X] T040 [US1] Surface the amendment in `trace report` via the additive `evidence_amended` / `evidence_history` keys, in `src/specops/trace.py` [SC-003]
- [X] T041 [US1] Carry the amendment provenance into evidence inherited by `finding fix --auto` from an amended task, in `src/specops/handoff.py` [SC-004]

**Checkpoint**: US1 is complete and shippable on its own — the ledger has its correction path.

---

## Phase 4: User Story 2 — Point at the feature actually under work (Priority: P2)

**Goal**: The active-feature pointer is moved by command, never by hand, and SpecOps resolves the same feature Spec Kit resolves.

**Independent Test**: with the pointer on feature A, `feature use` against B makes every pointer-reading command resolve B; `init-spec` on a fresh feature C leaves the pointer on C and `consistency` validates C with no hand edit; with the environment override set to A, SpecOps resolves A and refuses a repoint to B.

### Tests for User Story 2 ⚠️

- [X] T042 [P] [US2] Write the `feature use` happy-path and idempotency tests: repoint reports old → new; repointing to the already-active feature is a no-op that says so, in `tests/unit/test_feature_use.py` [SC-005]
- [X] T043 [P] [US2] Write the missing-artifact reporting test: absent `plan.md` / `tasks.md` / `status.yaml` are named without failing the command, in `tests/unit/test_feature_use.py` [SC-005]
- [X] T044 [P] [US2] Write the outgoing-work test: repointing away from a feature with an `IN_PROGRESS` task or an open review round succeeds and names the unfinished work, without requiring any override flag, in `tests/unit/test_feature_use.py` [SC-006]
- [X] T045 [P] [US2] Write the no-ledger test: repointing away from a never-initialized feature reports no outgoing-state warning, in `tests/unit/test_feature_use.py` [SC-006]
- [X] T046 [P] [US2] Write the foreign-ledger test: repointing to a directory whose ledger names a different feature succeeds and reports the mismatch rather than pre-judging it, in `tests/unit/test_feature_use.py` [SC-005]
- [X] T047 [P] [US2] Write the error-path tests asserting non-zero exit and an untouched pointer for: missing directory, directory outside `specs/`, no `spec.md`, and an active override naming a different directory — in `tests/unit/test_feature_use.py` [SC-007] [SC-009]
- [X] T048 [P] [US2] Write the exit-2 tests asserting a malformed `.specify/feature.json` and a run outside a Git repository return 2, in `tests/unit/test_feature_use.py` [SC-009]
- [X] T049 [P] [US2] Write the `init-spec` repoint test: initializing a feature leaves the pointer resolving to it, in `tests/unit/test_status.py` [SC-005]
- [X] T050 [P] [US2] Write the echo tests asserting `status show`, `consistency` and `preflight` name the resolved directory and carry the `(inferred — …)` suffix only when the answer was inferred, in `tests/unit/test_cli.py` [SC-007]
- [X] T051 [P] [US2] Write the integration test: author a new feature, repoint, `init-spec`, and validate with `consistency` without editing `feature.json`, in `tests/integration/test_recovery_pointer.py` [SC-005]

### Implementation for User Story 2

- [X] T052 [US2] Implement `cmd_use` in `src/specops/feature.py` — validate existence, `specs/` containment and `spec.md`; refuse when an override names a different directory; report old → new, missing artifacts, a foreign ledger name, and outgoing unfinished work — writing the pointer through `fsutil.atomic_write` [SC-005] [SC-006] [SC-007]
- [X] T053 [US2] Repoint the pointer to the initialized feature at the end of `cmd_init_spec`, after the ledger write persists, in `src/specops/status.py` [SC-005]
- [X] T054 [US2] Echo the resolved feature directory in `cmd_show`, in `src/specops/status.py`
- [X] T055 [US2] Add the inference suffix to `_resolved_feature` and the additive `feature_source` key to the `consistency` / `preflight` JSON output, in `src/specops/cli.py`
- [X] T056 [US2] Register `feature use <DIR>` on the Phase 2 sub-app, in `src/specops/cli.py` [SC-009]

**Checkpoint**: US2 complete — the pointer is CLI-managed and the two tools can no longer disagree.

---

## Phase 5: User Story 3 — Renumber a feature without demolishing its ledger (Priority: P3)

**Goal**: Renaming carries directory, ledger identity, branch reference and pointer together, preserving every record.

**Independent Test**: on a fixture feature with a populated ledger, rename it and assert the directory moved, the pointer followed, ledger identity and the `**Feature Branch**` header match the new name, every prior record is preserved, remaining old-name occurrences are reported and unmodified, and `reconcile` plus `consistency` pass.

### Tests for User Story 3 ⚠️

- [ ] T057 [P] [US3] Write the record-preservation test: after a rename, tasks, evidence, acknowledgements, review cycles and the revision counter are identical, in `tests/unit/test_feature_rename.py` [SC-008]
- [ ] T058 [P] [US3] Write the identity tests: the ledger `feature` field and the specification's `**Feature Branch**` header both name the new feature, in `tests/unit/test_feature_rename.py` [SC-008]
- [ ] T059 [P] [US3] Write the branch-reference tests: `--branch` updates the ledger reference; its absence leaves it unchanged and the output says so, in `tests/unit/test_feature_rename.py` [SC-008]
- [ ] T060 [P] [US3] Write the pointer-follow tests: the pointer follows when the renamed feature was active and is left alone otherwise, with the output stating which happened, in `tests/unit/test_feature_rename.py` [SC-008]
- [ ] T061 [P] [US3] Write the override-refusal test: a rename whose source is named by `SPECIFY_FEATURE_DIRECTORY` refuses with a non-zero exit, names the override, and changes nothing — completing it would leave the override dangling (FR-019a), in `tests/unit/test_feature_rename.py` [SC-007] [SC-009]
- [ ] T062 [P] [US3] Write the stale-reference test: occurrences of the old name in `plan.md` / `tasks.md` / checklists are reported with file and line and left byte-identical, in `tests/unit/test_feature_rename.py` [SC-008]
- [ ] T063 [P] [US3] Write the error-path tests asserting non-zero exit and no change for: existing target, missing source, non-feature source, target outside `specs/` — in `tests/unit/test_feature_rename.py` [SC-009]
- [ ] T064 [P] [US3] Write the exit-2 tests asserting an unparseable ledger and a run outside a Git repository return 2, in `tests/unit/test_feature_rename.py` [SC-009]
- [ ] T065 [P] [US3] Write the atomicity test: a failure injected at the ledger write and at the directory move each leave the feature in its pre-rename state — no half-moved directory, no pointer at a non-existent path, in `tests/unit/test_feature_rename.py` [SC-008]
- [ ] T066 [P] [US3] Write the integration test driving a full renumber on a populated fixture, then `reconcile` and `consistency` under the new name, in `tests/integration/test_recovery_rename.py` [SC-008]

### Implementation for User Story 3

- [ ] T067 [US3] Implement the up-front validation pass — source is a feature directory, target does not exist and lies under `specs/`, no override names the source, ledger loads and identity checks — in `src/specops/feature.py` [SC-007] [SC-009]
- [ ] T068 [US3] Implement the ordered mutation per research D9: ledger identity write into the source directory, identity-header rewrite, `os.rename` of the directory, pointer write last — in `src/specops/feature.py` [SC-008]
- [ ] T069 [US3] Implement the stale-reference scan reporting file and line for every remaining old-name or old-branch occurrence, changing nothing, in `src/specops/feature.py` [SC-008]
- [ ] T070 [US3] Report in the rename output that a `--branch` update will make the next command fail closed until the Git branch is renamed (data-model §5), in `src/specops/feature.py`
- [ ] T071 [US3] Register `feature rename <OLD> <NEW> [--branch NAME]` on the Phase 2 sub-app, in `src/specops/cli.py` [SC-009]

**Checkpoint**: all three user stories complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T072 [P] Add the recovery-move directive text to `src/specops/templates/directives/implement.md`, stating that amendment corrects a previous session's record and is never a way to revise a close made in the current run [SC-010]
- [ ] T073 [P] Write the directive test asserting every template mentioning amendment states the recovery-only restriction, in `tests/unit/test_extension.py` [SC-010]
- [ ] T074 [P] Write the CLI-wide refusal test asserting every new command exits non-zero on every documented refusal path, in `tests/unit/test_cli.py` [SC-009]
- [ ] T075 [P] Document `status amend-task`, `feature use` and `feature rename` — options, output, exit codes — in `docs/commands.md`
- [ ] T076 [P] Document the recovery operations in `README.md`
- [ ] T077 [P] Document the recovery operations equivalently in `README.pt-br.md`
- [ ] T078 Record the v9 bump, the three new commands, the resolution-precedence alignment and the migration requirement under `[Unreleased]` in `CHANGELOG.md` [SC-011]
- [ ] T079 Run the full gate suite — `conda run -n specops pytest -q`, `mypy src/`, `ruff check .` — and record the results as the user story's evidence [SC-011]

---

## Dependencies

**Story completion order**: Phase 1 → Phase 2 → {US1, US2, US3 in any order} → Phase 6.

- **Phase 2 blocks everything.** It carries the v9 record shape (what US1 writes), the resolution alignment (what US2 and US3 both refuse on), and the `feature.py` scaffold plus its sub-app registration (what US2 and US3 both extend).
- **US1, US2 and US3 are mutually independent** once Phase 2 lands. Putting the scaffold or the resolution work inside a story would have made the others depend on it — the reason both sit in Phase 2.
- **Phase 6** depends on all three stories, except T075–T077 which can begin as soon as their story lands.

**Within a story**: tests precede the implementation they cover. Implementation tasks touching the same file are sequential — T036, T037 and T038 all edit `src/specops/status.py`; T052 and T067–T070 all edit `src/specops/feature.py`; T055 and T056 both edit `src/specops/cli.py`.

## Parallel Execution Examples

**Phase 2**: T003–T009 in parallel (seven independent test cases across two files), then T010 → T011 → T012 → T013 → T014 sequentially, with T015 → T016 (same file) and T017 in parallel.

**US1**: T018–T035 are all `[P]` — eighteen test tasks across four files, written concurrently. Implementation then runs T036 → T037 → T038 → T039 sequentially, with T040 and T041 in parallel (different files).

**US2**: T042–T051 in parallel; then T052, T053/T054 and T055 in parallel (three different files), then T056.

**US3**: T057–T066 in parallel; then T067 → T068 → T069 → T070 → T071 sequentially.

**Phase 6**: T072–T077 all in parallel; T078 and T079 last.

## Implementation Strategy

**MVP scope**: Phase 1 + Phase 2 + US1 (T001–T041). That delivers the correction path the ledger has never had — the gap with no workaround at all — and is independently releasable.

**Incremental delivery**: US2 next (the pointer failure is silent and reports success), then US3 (the rarest, and the only one with an existing — destructive — workaround). Because the stories are independent, this order is a preference, not a constraint.

**Commit granularity**: one commit per user story, per the repository's convention. Intermediate tasks close with `--evidence`; the story's final task closes with `--auto` after the single user-story-level commit.
