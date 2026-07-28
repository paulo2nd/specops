---

description: "Task list for Feature 021 — Contract Freeze for 1.0"
---

# Tasks: Contract Freeze for 1.0

**Input**: Design documents from `/specs/021-contract-freeze/`

**Prerequisites**: plan.md, spec.md (required); research.md, data-model.md, contracts/, quickstart.md (loaded)

**Tests**: Per the Constitution task gate, every story carries automated tests. For a *freeze*, the contract tests lock the **current** shape (they pass on current code — that is the deliverable); the "breaking change is caught" property (SC-003) is demonstrated in `quickstart.md` step 2, not as a permanently-red committed test.

**Organization**: Grouped by user story (spec.md priorities). Every task carries one or more `[SC-xxx]` tags (roadmap Rule).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4 map to spec.md user stories

## Path Conventions

Single-project Python CLI: `src/specops/`, `tests/`, `docs/`, repo-root `README*.md`, `CHANGELOG.md`, `.specify/memory/constitution.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Skeletons and test fixtures the stories build on

- [X] T001 [P] Create the `docs/stability.md` skeleton (section headings per `specs/021-contract-freeze/contracts/stability-policy.md`) [SC-001]
- [X] T002 [P] Create gate-profile fixtures `tests/fixtures/gate-profiles/valid.yaml` and `.../minimal.yaml` for the frozen-shape test (none exist today) [SC-002]
- [X] T003 [P] Create findings-input fixture `tests/fixtures/findings-input/valid.json` (mirroring `specs/015-external-review-ingestion/contracts/findings-input.schema.json`) for the frozen-shape test [SC-002]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one sanctioned code delta + the surface sweep. Both the envelope contract test (US2) and the policy (US1) depend on these.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [X] T004 Conduct the FR-003 observable-surface sweep; record the authoritative result ("no additional observable surface beyond the seven" or the new surface + its class) as a note in `specs/021-contract-freeze/data-model.md` [SC-001]
- [X] T005 Add `OUTPUT_VERSION = 1` to `src/specops/outcome.py` and have `render()` always emit `"output_version"` (per `specs/021-contract-freeze/contracts/frozen-envelope.md`) [SC-010]
- [X] T006 Single-source the envelope version in `src/specops/cli.py` (`_emit()` and the `preflight`/standalone `render()` call sites stop passing `output_version`); point `src/specops/trace.py`, `src/specops/handoff.py`, `src/specops/contextmap.py` CLI-envelope constants at `outcome.OUTPUT_VERSION`; leave `gateprofiles.OUTPUT_VERSION` (file schema) and `contextmap` provenance `output_version` (ledger state) untouched (depends on T005) [SC-010]

**Checkpoint**: Envelope version single-sourced and emitted uniformly; surface list authoritative.

---

## Phase 3: User Story 1 - Adopter can rely on the frozen surfaces (Priority: P1) 🎯 MVP

**Goal**: A published stability policy classifying all seven surfaces FROZEN, with per-surface additive-vs-breaking rules and the sweep result.

**Independent Test**: Read `docs/stability.md`; every named surface carries an explicit FROZEN class + additive-change rule; the FR-003 sweep result is recorded (spec §User Story 1 / SC-001).

### Tests for User Story 1 ⚠️

- [X] T007 [US1] Write `tests/unit/test_stability_doc.py` asserting `docs/stability.md` names all seven surfaces, classifies each **FROZEN**, and states an additive AND a breaking rule for each [SC-001]

### Implementation for User Story 1

- [X] T008 [US1] Author the frozen-surface table + per-surface additive/breaking rules + recorded FR-003 sweep result in `docs/stability.md`, referencing `specs/021-contract-freeze/data-model.md` and the prior contract docs (specs/012, /015, /018) rather than duplicating field lists [SC-001]
- [X] T009 [P] [US1] Cross-link `docs/stability.md` from `docs/commands.md` [SC-001] [SC-006]

**Checkpoint**: The policy is publishable and testable on its own (MVP).

---

## Phase 4: User Story 2 - A breaking change is caught mechanically (Priority: P1)

**Goal**: Schema-level contract tests lock every frozen surface (incl. the exit-code contract), the base envelope carries `output_version`, and constitution Principle VI is brought into agreement.

**Independent Test**: Inject a breaking change into each frozen surface (quickstart step 2) → the relevant contract test fails naming the surface; an additive change passes (spec §User Story 2 / SC-002/003/004).

### Tests for User Story 2 ⚠️

- [X] T010 [P] [US2] `tests/unit/test_frozen_config.py` — lock the `specops.json` frozen key set + preserve-unknown behavior; assert no version field is introduced (`src/specops/config.py`) [SC-002]
- [X] T011 [P] [US2] `tests/unit/test_frozen_ledger.py` — lock the `status.yaml` v7 required-field set of each record and pin `ledger.CURRENT_SCHEMA==7` (baseline = `records.LedgerDocument`, NOT the template literal) [SC-002]
- [X] T012 [P] [US2] `tests/unit/test_frozen_lane.py` — lock `lane.yaml` v1 top-level keys, the `state` enum, and the null-until-transition invariant (`src/specops/lane.py`) [SC-002]
- [X] T013 [P] [US2] `tests/unit/test_frozen_gateprofiles.py` — lock the gate-profile file schema (profile fields, `applies` predicate keys) and `output_version==1`, using the T002 fixtures (`src/specops/gateprofiles.py`) [SC-002]
- [X] T014 [P] [US2] `tests/unit/test_frozen_ingestion.py` — lock the findings-input `contract_version==1`, top-level + per-finding required fields, and always-advisory-on-import semantics, using the T003 fixture (`src/specops/ingestion.py`) [SC-002]
- [X] T015 [P] [US2] `tests/unit/test_frozen_envelope.py` — lock the base envelope key set `{command, outcome, class, output_version}` + value enums, assert `output_version==1` across every `--json` family, and assert a new optional/per-command key still passes (additive tolerance) [SC-002] [SC-004] [SC-010]
- [X] T016 [US2] Extend `tests/unit/test_outcome_contract.py` — lock the three-value exit-code contract (`0`/`1`/`2` meanings) and assert the envelope version is single-sourced (no divergent module constant) [SC-002] [SC-010]

### Implementation / governance for User Story 2

- [X] T017 [US2] Amend `.specify/memory/constitution.md` Principle VI to document exit `2` (infra/data/usage), bump version 1.9.2→1.9.3 (PATCH, approved), and update the Sync Impact Report — in the **same commit** as T016 (`src/specops`/tests unchanged elsewhere) [SC-009]
- [X] T018 [US2] Re-record golden captures for the `consistency`/`reconcile`/`preflight` families (`conda run -n specops pytest tests/golden/ --golden-record`) and confirm the diff is **only** the additive `output_version` key; human captures byte-identical [SC-004] [SC-010]

**Checkpoint**: Every frozen surface is mechanically locked; principle and exit-code contract agree.

---

## Phase 5: User Story 3 - Post-1.0 evolution has defined obligations (Priority: P2)

**Goal**: A versioning-and-migration policy stating bump+migration obligations, envelope `output_version` semantics, and the rename alias/deprecation discipline.

**Independent Test**: Read the policy; for each persisted format it states the bump-plus-migration obligation and points at the existing migration-test mechanism; envelope-version semantics and rename discipline are stated (spec §User Story 3 / SC-005).

### Tests for User Story 3 ⚠️

- [X] T019 [US3] Extend `tests/unit/test_stability_doc.py` to assert the Versioning & Migration section covers every persisted format's bump+migration obligation, the envelope `output_version` semantics, and the Feature 017 rename alias/deprecation discipline [SC-005]

### Implementation for User Story 3

- [X] T020 [US3] Author the Versioning & Migration Policy section of `docs/stability.md` per `specs/021-contract-freeze/contracts/versioning-policy.md` (points at `ledger.migrate_to_current` + `test_ledger_v7_migration.py` as the reused mechanism) [SC-005]

**Checkpoint**: Safe-evolution rules are published and testable.

---

## Phase 6: User Story 4 - The release is cut and documented when the criterion is met (Priority: P3)

**Goal**: CHANGELOG + EN/PT docs record the freeze; the rc tag is documented as gated on an external criterion this feature does not evaluate.

**Independent Test**: CHANGELOG links the policy; both README entry points reference the freeze; no code/test evaluates the rc criterion (spec §User Story 4 / SC-006/008).

### Tests for User Story 4 ⚠️

- [X] T021 [US4] `tests/unit/test_release_docs.py` — assert `CHANGELOG.md` links `docs/stability.md`, and both `README.md` and `README.pt-br.md` reference the freeze; assert no committed test evaluates the "real-usage criterion" (rc is not forced) [SC-006] [SC-008]

### Implementation for User Story 4

- [X] T022 [US4] Add a `CHANGELOG.md` `[Unreleased]` entry recording the contract freeze (frozen surfaces + the additive envelope `output_version`) and linking `docs/stability.md` [SC-006]
- [X] T023 [P] [US4] Add an EN "Stability & Contract Freeze" section to `README.md` linking `docs/stability.md` [SC-006]
- [X] T024 [P] [US4] Add a PT pointer/summary to `README.pt-br.md` linking `docs/stability.md` (behaviorally equivalent to the EN section; equivalence is manual per research D5) [SC-006]
- [X] T025 [US4] State in `docs/stability.md` that the 1.0.0-rc is gated on the release owner's real-usage criterion — referenced, not evaluated by this feature [SC-008]

**Checkpoint**: Freeze is discoverable in the changelog and both languages; rc left to the release owner.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T026 Run `specs/021-contract-freeze/quickstart.md` steps 1–6, including the breaking-change injection (step 2) that demonstrates SC-003 [SC-002] [SC-003] [SC-004]
- [X] T027 [P] Assert no schema bump occurred (ledger stays v7, lane v1, findings-input `contract_version` 1, gate-profile `output_version` 1) — a guard check in `tests/unit/test_frozen_ledger.py`/companions [SC-007]
- [X] T028 Run full gates: `conda run -n specops ruff check . && conda run -n specops mypy && conda run -n specops pytest -q` — green at repo thresholds [SC-007]
- [X] T029 Flip `ROADMAP.md` row 021 `ACTIVE → MERGED` as the completion change, inside this feature's own PR (roadmap protocol step 6) [SC-007]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: after Setup; **blocks all stories** (envelope delta + surface sweep). T006 depends on T005.
- **US1 (Phase 3)**: after Foundational. T008 → T007 (test first); T009 after T008.
- **US2 (Phase 4)**: after Foundational (needs the envelope delta for T015). T010–T015 parallel; T016 → T017 (same commit); T018 after T005/T006.
- **US3 (Phase 5)**: after Foundational; independent of US2. T020 → T019.
- **US4 (Phase 6)**: after US1 (policy exists to link) and US3 (versioning section exists). T022–T025 satisfy T021.
- **Polish (Phase 7)**: after all desired stories.

### Story independence

- **US1** (policy doc) and **US2** (contract tests + amendment) are both P1 and can proceed in parallel once Foundational lands (different files).
- **US3** appends a section to the already-created `docs/stability.md` — coordinate the single file with US1 (T008 vs T020 edit the same file; sequence them).
- **US4** depends on the policy being present.

### Parallel opportunities

- Setup: T001, T002, T003 together.
- US2 frozen-shape tests: T010, T011, T012, T013, T014, T015 together (six different new files).
- US4 READMEs: T023, T024 together.

---

## Parallel Example: User Story 2 frozen-shape tests

```bash
# Six independent new test files — run/author in parallel:
Task: "tests/unit/test_frozen_config.py"        # T010
Task: "tests/unit/test_frozen_ledger.py"        # T011
Task: "tests/unit/test_frozen_lane.py"          # T012
Task: "tests/unit/test_frozen_gateprofiles.py"  # T013
Task: "tests/unit/test_frozen_ingestion.py"     # T014
Task: "tests/unit/test_frozen_envelope.py"      # T015
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1 Setup → 2. Phase 2 Foundational (the envelope delta is the only code change) → 3. Phase 3 US1 (publish the frozen-surface policy) → **STOP & validate**: the freeze is *declared* and testable. This alone is a shippable 1.0-readiness artifact.

### Incremental delivery (recommended commit granularity — one commit per story)

1. Setup + Foundational (envelope delta) → commit.
2. US1 policy doc → commit.
3. US2 contract tests + Principle VI amendment + golden re-record → commit (amendment + `test_outcome_contract.py` together per SC-009).
4. US3 versioning-policy section → commit.
5. US4 CHANGELOG + READMEs + rc note → commit.
6. Polish (gates green, ROADMAP MERGED flip) → final commit.

---

## Notes

- Every task carries `[SC-xxx]`; coverage: SC-001 (T001/T004/T007/T008/T009), SC-002 (T002/T003/T010–T016/T026), SC-003 (T026), SC-004 (T015/T018/T026), SC-005 (T019/T020), SC-006 (T009/T021–T024), SC-007 (T027/T028/T029), SC-008 (T021/T025), SC-009 (T017), SC-010 (T005/T006/T015/T016/T018).
- The contract tests lock the **current** frozen shape and pass on current code — that is the deliverable, not a red-first test. SC-003 (breaking-change caught) is proven by the quickstart injection (T026).
- No Self-Application: all tests use fixtures + golden captures against tmp repos; `specops` is never run against this repo.
- `docs/stability.md` is edited by T001/T008/T020/T025 — keep those edits sequenced (same file), not parallel.
- The single sanctioned behavior delta is the additive envelope `output_version`; T018 confirms the golden diff contains nothing else.
