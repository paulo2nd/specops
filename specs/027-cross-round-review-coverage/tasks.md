---
description: "Task list for Feature 027 — Cross-Round Review Coverage"
---

# Tasks: Cross-Round Review Coverage

**Input**: Design documents from `/specs/027-cross-round-review-coverage/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/record-scope-output.md](./contracts/record-scope-output.md), [contracts/coverage-guard.md](./contracts/coverage-guard.md)

**Tests**: Mandatory. Constitution *Development Workflow & Quality Gates* §2 — no task is complete without tests. Tests are written before the implementation they cover. Every scenario runs against a throwaway git fixture; this repository is never self-applied (§3).

**Organization**: Grouped by user story. The one thing both US1 and US2 need — the widened managed-path exclusion — sits in Phase 2. US3 depends on US2 (it consumes the derivation); that dependency is real and is stated rather than engineered away.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 — maps to the user stories in spec.md
- `[SC-00N]` tags record success-criteria coverage

## Path Conventions

Single Python package: `src/specops/`, `tests/unit/`, `tests/integration/` at repository root. All tooling runs under `conda run -n specops …` (the `base` env carries a numpy stub that aborts mypy).

---

## Phase 1: Setup

**Purpose**: A known-green baseline, so any later regression is attributable.

- [X] T001 Confirm the baseline suite is green — run `conda run -n specops pytest -q`, `conda run -n specops mypy src`, `conda run -n specops ruff check src tests` — and record the pass counts in the task evidence

**Checkpoint**: baseline recorded.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The widened managed-path exclusion (research R5 / FR-005a). US1's emission and US2's derivation both read it, so it lands first.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### Tests

- [X] T002 [P] Write the widened-exclusion tests for `reviewscope.product_paths` — `.specify/…`, `specops.json`, `specs/<active-feature>/…` **and** `specs/<other-feature>/…` all dropped, ordinary product paths kept — in `tests/unit/test_reviewscope.py` [SC-001]
- [X] T003 [P] Write the rename-regression test: after a feature is renamed, the old `specs/<old-name>/…` paths appear in no coverage set (the Feature 026 interaction, research R5) in `tests/unit/test_reviewscope.py` [SC-001]
- [X] T004 [P] Write the containment test asserting `trace.is_managed` is unchanged — the drift gate keeps the narrow active-feature exclusion — in `tests/unit/test_trace.py`

### Implementation

- [X] T005 Widen `reviewscope.product_paths` to drop every remaining `specs/` path on top of `trace.is_managed`, with a docstring recording that the widening is coverage-scoped and that the `specs/` prefix is hardcoded to match `is_managed`'s existing hardcode (research R5, known limit), in `src/specops/reviewscope.py`

**Checkpoint**: coverage sets exclude every Spec Kit feature directory; the drift gate is untouched.

---

## Phase 3: User Story 1 — A corrective round can see the whole feature (Priority: P1)

**Goal**: `handoff record-scope` stops hiding the baseline. The reviewer receives the priority set **and** the full `baseline..HEAD` set, the remainder labelled *not yet re-verified this round*, and the directive states the tradeoff instead of forbidding the re-read.

**Independent test**: on a fixture with an anchor round recorded and a corrective round open after a fix touching one file, `handoff record-scope` emits both sets, distinguishably, in human and JSON output — with what it *persists* unchanged.

**Why first**: this is the slice that addresses the reported failures. It changes no gate and no derivation, so it carries zero false-block risk, and it is shippable on its own.

### Tests

- [X] T006 [P] [US1] Write the additive-only guard: `round`, `review_role`, `reviewed_range`, `scope_paths` still present with unchanged meaning and `output_version` still `1`, in `tests/unit/test_handoff.py`
- [X] T007 [P] [US1] Write the test that a corrective round emits `baseline_paths` equal to the full `baseline..HEAD` product set — including a file changed before the previous round's `to` and untouched since — in `tests/integration/test_corrective_scope.py` [SC-001]
- [X] T008 [P] [US1] Write the set-algebra test: `not_reverified_paths == baseline_paths − scope_paths`, disjoint from `scope_paths`, and `scope_paths ∪ not_reverified_paths ⊇ baseline_paths`, in `tests/integration/test_corrective_scope.py` [SC-001]
- [X] T009 [P] [US1] Write the anchor-round test: `scope_paths == baseline_paths`, `not_reverified_paths == []`, and the human output prints no second block (spec AS US1-2), in `tests/integration/test_corrective_scope.py` [SC-001]
- [X] T010 [P] [US1] Write the persistence-unchanged test (FR-002): for both roles the recorded `reviewed_range` and `review_role` are byte-identical to what Feature 025 records, and no emitted set is written to the ledger, in `tests/integration/test_corrective_scope.py`
- [X] T011 [P] [US1] Write the human-output tests: each set renders as a labelled block, and a block whose set is empty is omitted entirely, in `tests/unit/test_handoff.py` [SC-001]
- [X] T012 [P] [US1] Write the directive assertion: the Step-3 corrective bullet in `src/specops/templates/review.md` no longer contains "Do **not** re-hunt unchanged, already-reviewed code", and does state that the remainder of the baseline set is unverified this round and that declining to read it is the reviewer's decision to record, in `tests/unit/test_review.py`

- [X] T013 [P] [US1] Write the no-new-surface test (FR-001a): the frozen CLI command and group sets at `tests/integration/test_git_availability.py:109-110` (`_EXPECTED_COMMANDS` / `_EXPECTED_GROUPS`) are unchanged — this feature adds keys to an existing command, never a command or a report surface

### Implementation

- [X] T014 [US1] Compute `baseline_paths` (full `baseline..HEAD` product set) and `not_reverified_paths` (`baseline_paths − scope_paths`) in `cmd_record_scope`, adding both as JSON keys per [contracts/record-scope-output.md](./contracts/record-scope-output.md) and changing nothing it persists, in `src/specops/handoff.py`
- [X] T015 [US1] Render the labelled human blocks — priority set, then *not yet re-verified this round* with its `N of M` count — omitting an empty block, in `src/specops/handoff.py`
- [X] T016 [US1] Rewrite the Step-3 corrective bullet per research R7 in `src/specops/templates/review.md`, keeping the "Read exactly the files it lists" line (`record-scope` now lists everything)
- [X] T017 [US1] Amend `.specify/memory/constitution.md` to `1.13.0` — **Principle IV only**: the Token-Optimized Review clause (constitution lines 523-525) describes a corrective round as `prev_to..HEAD` plus open findings' files, which is no longer all that `record-scope` emits; broaden it to the priority-set-plus-full-baseline-set contract and update the Sync Impact Report. Governance requires this in the **same change set** as the `templates/review.md` edit, so it rides US1's commit — not US3's
- [X] T018 [US1] Run the gate suite — `pytest -q`, `mypy src`, `ruff check src tests` under `conda run -n specops` — and record the results as the user story's evidence [SC-001]

**Checkpoint**: a corrective round's reviewer sees 100% of the baseline paths. No gate behavior has changed.

---

## Phase 4: User Story 2 — The ledger names what no round has ever reached (Priority: P2)

**Goal**: derive, from recorded ranges and git alone, which baseline product paths some round reached and which none did. Reported, not yet enforced.

**Independent test**: an intact chain yields an empty never-reached set; invalidating a recorded range's endpoints or moving the baseline puts the affected paths in it, by name.

**Interim state, deliberate**: `never_reached` is added to `Assessment` **additively** here — the four coarse fields and `_gate_review_coverage` are untouched, so nothing gates on the new derivation until US3. Removing them in this phase would force the gate rewrite into it and collapse the two stories.

### Tests

- [X] T019 [P] [US2] Write the intact-chain test: anchor `baseline..t₁` plus corrective `t₁..HEAD`, all endpoints resolving ⇒ `never_reached == []` (the no-false-block case), in `tests/unit/test_reviewscope.py` [SC-002]
- [X] T020 [P] [US2] Write the transitivity test: a file changed only inside a middle segment is still reached, because segment tree-diffs compose (research R1), in `tests/unit/test_reviewscope.py` [SC-002]
- [X] T021 [P] [US2] Write the orphaned-range test: a recorded range whose endpoint no longer resolves contributes zero reached paths, and the paths it alone accounted for are named, in `tests/unit/test_reviewscope.py` [SC-003]
- [X] T022 [P] [US2] Write the moved-baseline test: with the baseline pointed at an earlier commit, the product paths changed in the newly-included span are named, in `tests/unit/test_reviewscope.py` [SC-003]
- [X] T023 [P] [US2] Write the no-anchor subsumption test: no recorded range starts at the baseline ⇒ the `baseline..t₁` paths appear in `never_reached` by name (replacing the old `has_anchor` branch), in `tests/unit/test_reviewscope.py` [SC-002]
- [X] T024 [P] [US2] Write the tail subsumption test: product change after the last recorded `to` ⇒ those paths appear in `never_reached` by name (replacing the old `unreviewed_tail` branch), in `tests/unit/test_reviewscope.py` [SC-002]
- [X] T025 [P] [US2] Write the determinism tests: two consecutive derivations on unchanged inputs return an identical sorted set, and no argument or ledger field lets a reviewer supply or alter scope, in `tests/unit/test_reviewscope.py` [SC-006]
- [X] T026 [P] [US2] Write the empty-target test: no product change since the baseline ⇒ `target_empty` true and `never_reached == []`, in `tests/unit/test_reviewscope.py` [SC-002]
- [X] T027 [P] [US2] Write the emission test: `never_reached_paths` appears in the `record-scope` JSON and as its own labelled human block, unbounded (it is a report, not an error line), in `tests/integration/test_corrective_scope.py` [SC-003]

### Implementation

- [X] T028 [US2] Add `never_reached: list[str]` to `reviewscope.Assessment`, leaving the four coarse fields in place for this phase, in `src/specops/reviewscope.py`
- [X] T029 [US2] Compute the per-path union in `assess` — target set minus the union of `product_paths(name_only_diff(from, to))` over recorded ranges whose **both** endpoints pass an explicit `gitops.commit_exists` check (never relying on `name_only_diff`'s empty-on-failure return) — sorted, in `src/specops/reviewscope.py` [SC-002] [SC-003]
- [X] T030 [US2] Emit `never_reached_paths` as the third JSON key and human block in `cmd_record_scope`, in `src/specops/handoff.py` [SC-003]
- [X] T031 [US2] Run the gate suite and record the results as the user story's evidence [SC-002] [SC-003] [SC-006]

**Checkpoint**: the never-reached set is derived and reported. Approval still behaves exactly as Feature 025 left it.

---

## Phase 5: User Story 3 — Approval fails closed on an unreached baseline path (Priority: P3)

**Goal**: make the derivation binding. The three coarse branches of `_gate_review_coverage` collapse into one that states the count and names up to 10 paths; the degradation and unresolvable-baseline rules are untouched.

**Independent test**: the roadmap's acceptance gate — REJECTED → REJECTED → APPROVED with a never-reached file fails closed and names it; the same sequence with an anchor round covering it approves; a ledger with no reviewed-scope records closes through the prior behavior.

**Depends on US2** (it consumes `never_reached`). This is the one real inter-story dependency.

### Tests

- [X] T032 [P] [US3] Write the roadmap acceptance-gate test: REJECTED → REJECTED → APPROVED where no round ever reached `src/d.py` ⇒ blocked, exit `1`, message names `src/d.py`, phase stays REVIEW, in `tests/integration/test_review_coverage_guard.py` [SC-004]
- [X] T033 [P] [US3] Write the same-sequence-plus-anchor test ⇒ approval succeeds, in `tests/integration/test_review_coverage_guard.py` [SC-004]
- [X] T034 [P] [US3] Write the degradation test: a ledger with no reviewed-scope records on any round closes through the pre-025 cycle-result path and is never blocked by this guard, in `tests/integration/test_review_coverage_guard.py` [SC-005]
- [X] T035 [P] [US3] Write the unresolvable-baseline test: records present, baseline missing ⇒ blocked with the **unchanged** Feature 025 message, in `tests/integration/test_review_coverage_guard.py` [SC-005]
- [X] T036 [P] [US3] Write the empty-target test: no product change since the baseline ⇒ approval proceeds, in `tests/integration/test_review_coverage_guard.py` [SC-004]
- [X] T037 [P] [US3] Write the bounded-message tests (research R6): with 37 never-reached paths the message states `37` and names exactly the first 10 in sorted order with a `(10 shown of 37)` suffix; with 3 it names all 3 and carries no suffix, in `tests/integration/test_review_coverage_guard.py` [SC-004]
- [X] T038 [P] [US3] Write the recovery test proving research R2's three facts: an orphaned chain suffix blocks approval; one `handoff record-scope` on the **still-open** round re-anchors over `baseline..HEAD` (the guard raised before `finalize`, so `result` is still null on disk); the retry approves; and the round count is unchanged, in `tests/integration/test_review_coverage_guard.py` [SC-004]
- [X] T039 [P] [US3] Write the guard-scope test asserting the coverage guard reads only reviewed ranges and git diffs — never a finding's state, severity, or merit (FR-011) — in `tests/integration/test_review_coverage_guard.py` [SC-006]

### Implementation

- [X] T040 [US3] ~~Remove the four coarse `Assessment` fields.~~ **Corrected during implementation**: they are retained. `test_unreviewed_commit_after_frontier_blocks` proved the per-path test does not subsume them — a path re-touched after the last round stays in the reached set, so the set difference is blind to it. `never_reached` is additive; the five Feature 025 assertions in `tests/unit/test_reviewscope.py` were widened to cover both models, in `src/specops/reviewscope.py` and `tests/unit/test_reviewscope.py`
- [X] T041 [US3] Add the never-reached block with the bounded message **ahead of** the three chain branches at `src/specops/status.py` per [contracts/coverage-guard.md](./contracts/coverage-guard.md) — all three retained with byte-identical messages, and the no-records and unresolvable-baseline branches unchanged [SC-004] [SC-005]
- [X] T042 [US3] Amend `.specify/memory/constitution.md` to `1.14.0` using the drafted replacement text in research.md — **Principle II's carve-out narrowed** (the `reconcile` exemption explicitly retained) plus the **Principle IV coverage clause** ("unless the union of recorded scopes covers `baseline..HEAD`" becomes the per-path never-reached test); the Principle IV *emission* clause already landed in US1's `1.13.0`. Update the Sync Impact Report in the same change set per Governance
- [X] T043 [US3] Run the gate suite and record the results as the user story's evidence [SC-004] [SC-005]

**Checkpoint**: the roadmap's acceptance gate passes end to end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: prove nothing else moved, and ship the adopter-facing record.

- [X] T044 [P] Add `record_scope_human` and `record_scope_json` golden scenarios — `tests/golden/harness.py` registers none today (`captures/handoff/` holds only `report_*` and `validate_*`, harness lines 413-419), so there is nothing to re-record; the new JSON contract needs a capture. Then assert every other family — `preflight`, `reconcile`, `consistency`, the remaining `handoff` commands — re-runs clean **without** `--golden-record`, in `tests/golden/harness.py` and `tests/golden/captures/handoff/` [SC-007]
- [X] T045 [P] Assert the round cap and the finding lifecycle are untouched — `tests/unit/test_config_round_cap.py` and `tests/integration/test_round_cap.py` pass unmodified [SC-007]
- [X] T046 [P] Assert `tests/unit/test_reconcile_reviewed_range_exempt.py` passes unmodified — the `reconcile` half of the Principle II carve-out is not narrowed [SC-007]
- [X] T047 [P] Assert the ledger stays at `schema_version: 9` with no new migration — extend `tests/unit/test_frozen_ledger.py` [SC-007]
- [X] T048 [P] Document the three emitted sets, the never-reached guard and the one-command recovery in `README.md`
- [X] T049 [P] Document the same equivalently in `README.pt-br.md` (full parity, same PR)
- [X] T050 Record the emission, the derivation, the guard change and the constitution bump under `[Unreleased]` in `CHANGELOG.md`
- [X] T051 Flip Feature 027 to `MERGED` in the `ROADMAP.md` status table as a commit inside this feature's own PR
- [X] T052 Run the full gate suite one last time and record the results [SC-007]

---

## Dependencies

**Story completion order**: Phase 1 → Phase 2 → US1 → US2 → US3 → Phase 6.

- **Phase 2 blocks everything.** The widened `product_paths` feeds both US1's `baseline_paths` and US2's derivation; landing it inside either story would make the other depend on it.
- **US1 is fully independent** of US2 and US3 and is releasable on its own. It carries its own constitution amendment (T017, `1.13.0`, Principle IV emission clause) because Governance requires a directive change and its template edit in the same change set — T016 and T017 must land in the same commit.
- **US2 depends on US1 only for file ordering** — T030 edits the same `cmd_record_scope` body as T014/T015. The derivation itself (T028–T029) has no US1 dependency and can be written in parallel with Phase 3.
- **US3 depends on US2.** It consumes `never_reached`; there is no version of the gate rewrite that does not. Stated rather than engineered away.
- **US3's amendment (T042, `1.14.0`) must follow T017.** It edits the same file and builds on the `1.13.0` Sync Impact entry; running them out of order produces a wrong version chain.
- **Phase 6** depends on all three stories, except T048–T049 which can begin as soon as US1 lands.

**Within a story**: tests precede the implementation they cover. Implementation tasks touching the same file are sequential — T014 and T015 both edit `src/specops/handoff.py`; T028 and T029 both edit `src/specops/reviewscope.py`; T040 also edits `src/specops/reviewscope.py` and must follow T029.

## Parallel Execution Examples

**Phase 2**: T002–T004 in parallel (three independent test cases across two files), then T005.

**US1**: T006–T013 all `[P]` — eight test tasks across five files, written concurrently. Implementation then runs T014 → T015 sequentially (same file), with T016 → T017 in parallel (a template and the constitution, but the two must land in one commit), then T018.

**US2**: T019–T027 all `[P]` — nine test tasks across two files. Implementation then runs T028 → T029 sequentially, with T030 after (different file), then T031.

**US3**: T032–T039 all `[P]` — eight test tasks in one file, so write them as one batch. Implementation runs T040 → T041 sequentially, with T042 after T041 (the amendment records what T041 changed), then T043.

**Phase 6**: T044–T049 all in parallel; T050, T051, T052 last.

## Implementation Strategy

**MVP scope**: Phase 1 + Phase 2 + US1 (T001–T018). That is the slice that addresses the reported failures — it puts every baseline file back in front of the reviewer and rewrites the directive that told them not to look. It changes no gate, so it cannot introduce a false block, and it is independently releasable if the field needs relief before the guard is ready.

**Incremental delivery**: US2 next (the derivation, reported but not binding), then US3 (the guard plus the Principle II narrowing). This order is a constraint, not a preference — US3 consumes US2's derivation.

**Two constitution amendments, deliberately**: `1.13.0` in US1 and `1.14.0` in US3. Governance requires a Principle IV directive change to propagate to `src/specops/templates/` in the same change set, and the two directive changes land in two different commits — so they are two amendments, not one deferred to the end. Each bump is MINOR (materially expanded or narrowed guidance on a non-removed principle).

**Commit granularity**: one commit per user story, per the repository's convention. Intermediate tasks close with `--evidence`; the story's final task closes with `--auto` after the single user-story-level commit.

**Not self-applied**: no `specops.json` and no `status.yaml` are created in this repository at any point (Constitution, Development Workflow §3). Every scenario above runs against a throwaway git fixture under `tests/`.
