---

description: "Task list for Feature 013 — Lightweight Workflow Lane"
---

# Tasks: Lightweight Workflow Lane

**Input**: Design documents from `/specs/013-lightweight-workflow-lane/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (cli-lane,
lane-record.schema, workflow-lite, lite-directive)

**Tests**: Test tasks are included per the Constitution (Development Workflow & Quality Gates —
Task gate: no task is complete without passing automated tests). The `specops-lite`
`workflow.yml` and `lite.md` directive are validated *structurally* (their end-to-end agent
behavior needs a live integration and is not CI-reproducible — mirrors the full workflow).

**Organization**: Grouped by user story so each is independently implementable and testable.
Actor note (operating model): `specops lane *` commands are agent/engine-issued; tests drive the
CLI primitives directly (that is the agent's job at runtime, not the human's).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5; Setup / Foundational / Operating-Model / Polish carry no story label
- All paths are repo-relative; single-project layout (`src/specops/`, `tests/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding the lane work depends on (the package already exists).

- [X] T001 [P] Create `tests/fixtures/lane/` with fixture repos/diffs: an eligible small change, one diff per **diff-detectable** category (migration, secret, dependency, destructive), attestation cases for the two attested categories (root-cause, public-contract), and a multi-commit branch for promotion
- [X] T002 [P] Create the lane-record scaffold `src/specops/templates/lane.yaml` per data-model §1 (schema_version 1, state OPEN, eligibility/decisions/closure/promotion placeholders)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The lane record layer and CLI wiring every story hangs off. ⚠️ No user story can proceed until this is done.

- [X] T003 Create `src/specops/lane.py` — lane-record load/save/validate with atomic write and `updated_at` refresh, schema constants and invariants INV-1…INV-6 (schema_version==1, terminal-state exclusivity, no bypass field, commit-reachability via `gitops.is_ancestor`, `status.yaml` mutual-exclusion), reusing `ledger.now_utc` and `gitops`
- [X] T004 Register a `lane` Typer sub-app in `src/specops/cli.py` (`app.add_typer(lane_app, name="lane")`) and add a `LaneResult(CommandResult)` outcome mapping in `src/specops/lane.py` so every lane command renders via `outcome.render` with 0/1/2 exit codes (Principle VI)

**Checkpoint**: Lane record + CLI surface exist; story implementation can begin.

---

## Phase 3: User Story 1 — Complete a small reversible change with proportional ceremony (Priority: P1) 🎯 MVP

**Goal**: Agent-driven lane lifecycle for a small change — `start` (eligibility, fail-closed), `status`, and a `close` that runs the preflight suite fail-closed and records a closure with retrospective + evidence refs — with no spec/plan/tasks artifacts and no review cycle.

**Independent Test**: Drive `lane start` → commits → `lane close` against a fixture; assert no `spec.md`/`plan.md`/`tasks.md`/`status.yaml` created, no review cycle opened, a `lane.yaml` closure recorded, and no human-issued `specops` command required (SC-001, SC-008).

### Tests for User Story 1 ⚠️

- [X] T005 [P] [US1] Unit tests for `lane start`/`status`/`close` happy path + eligibility fail-closed + `status.yaml` mutual-exclusion in `tests/unit/test_lane.py`
- [X] T006 [P] [US1] Integration test of the clean-lane flow (start → commit → close, asserting absence of full-lifecycle artifacts) in `tests/integration/test_lane_flow.py`

### Implementation for User Story 1

- [X] T007 [US1] Implement `specops lane start` in `src/specops/lane.py` + `src/specops/cli.py`: record eligibility answers (criteria v1), fail closed (exit 1) if any criterion unconfirmed, refuse (exit 2) if `lane.yaml` or `status.yaml` already exists (INV-6)
- [X] T008 [US1] Implement `specops lane status [--json]` (read-only summary: state, baseline, decision count, terminal outcome) in `src/specops/lane.py` + `src/specops/cli.py`
- [X] T009 [US1] Implement `specops lane close [--json]` core in `src/specops/lane.py` + `src/specops/cli.py`: run the `review` preflight gate-profile suite, fail closed on a required FAIL/unavailable or a missing/flagged attestation (both must be `clear`), set `state: CLOSED`, write the `closure` block with evidence refs and a retrospective summary (C-1)

**Checkpoint**: US1 is a runnable MVP lane — start, status, fail-closed close — testable via the CLI primitives.

---

## Phase 4: User Story 2 — The non-pierceable safety core halts high-risk work (Priority: P1)

**Goal**: Hybrid safety core — deterministic detection of the four diff-detectable categories plus two always-on attestations (root-cause, public-contract) — that halts with only halt/promote (no recordable bypass).

**Independent Test**: Introduce each of the four diff-detectable categories one at a time → `lane check` exits 1 and flags it; `lane attest` with either dimension `flag` exits 1; assert no schema path lets the lane continue past a trip by recording a reason (SC-002, D-1/INV-3).

### Tests for User Story 2 ⚠️

- [X] T010 [P] [US2] Unit tests for the safety detector — one per **diff-detectable** category (migration, secret, dependency, destructive) + generic-default patterns + `specops.json` override + non-removable floor — and the **two** attestations (root-cause, public-contract), asserting each is always presented and a flag answer halts, in `tests/unit/test_safety.py`
- [X] T011 [P] [US2] Integration test that each detected category and a flagged attestation (root-cause or public-contract) halt the lane and offer only halt/promote in `tests/integration/test_lane_flow.py`

### Implementation for User Story 2

- [X] T012 [P] [US2] Create `src/specops/safety.py` — `detect(diff_status, overrides) -> [Detection]` over `gitops.effective_diff_status` for the **four** diff-detectable categories (migration, secret, dependency, destructive) with generic built-in path/pattern defaults (research R5), plus the model for the **two** always-on attestations (root-cause, public-contract)
- [X] T013 [P] [US2] Add an optional `lane` overrides block to `src/specops/config.py` (per-category glob add/replace; the built-in detection floor is non-removable to protect the core — Complexity Tracking)
- [X] T014 [US2] Implement `specops lane check [--staged] [--json]` (read-only; `detections`/`categories` over the four diff-detectable categories; exit 1 on any detection) in `src/specops/lane.py` + `src/specops/cli.py` using `safety.py`
- [X] T015 [US2] Implement `specops lane attest --root-cause {clear|flag} --public-contract {clear|flag} [--json]` (record both always-on attestations; either `flag` → exit 1) in `src/specops/lane.py` + `src/specops/cli.py`

**Checkpoint**: The safety core halts every category; the record schema cannot express a bypass.

---

## Phase 5: User Story 3 — Lossless promotion to the full feature workflow (Priority: P1)

**Goal**: `lane promote` synthesizes a full `status.yaml` at PLAN from the lane record + branch history, importing every commit and carrying lane context, with zero commit loss.

**Independent Test**: Start a lane with N commits, `lane promote`; assert `status.yaml` at `current_phase: PLAN` with `promoted_from_lane` + non-empty `lane_provenance`, the reachable-from-HEAD commit set identical before/after, and `lane.yaml` → PROMOTED (SC-003, P-1).

### Tests for User Story 3 ⚠️

- [X] T016 [P] [US3] Unit tests for ledger synthesis-at-PLAN and the commit-preservation invariant (reachable set unchanged) in `tests/unit/test_lane.py`
- [X] T017 [P] [US3] Integration test of promotion via both triggers (`safety-trip`, `scope-growth`) using the identical path (FR-016) in `tests/integration/test_lane_flow.py`

### Implementation for User Story 3

- [X] T018 [P] [US3] Add additive promotion-provenance keys (`promoted_from_lane`, `lane_provenance`) and a small helper to `src/specops/ledger.py` (no schema bump; v6 stays current)
- [X] T019 [P] [US3] Add a synthesize-full-ledger-at-PLAN helper to `src/specops/status.py`, reusing the `status.yaml` template-fill logic (baseline, `current_phase: PLAN`, imported commits as existing work)
- [X] T020 [US3] Implement `specops lane promote --reason {safety-trip|scope-growth} [--json]` in `src/specops/lane.py` + `src/specops/cli.py`: reachability-check every commit (`gitops.is_ancestor`; exit 2 on divergence), synthesize the ledger, copy lane context into `lane_provenance`, mark `state: PROMOTED`

**Checkpoint**: All three P1 stories complete — the lane runs and escapes losslessly.

---

## Phase 6: Operating Model — Directive + Workflow (Cross-Cutting, FR-022/FR-023)

**Purpose**: Make SpecOps agent-driven — compose the P1 commands into the `specops-lite` workflow and inject the recognition directive so the human never conducts the CLI. Depends on the Phase 3–5 commands existing.

**Independent Test**: `specops extension install` registers `specops-lite` additively (foreign + `specops`/`speckit` entries preserved) and injects the `lite.md` directive idempotently; in a repo without SpecOps the directive degrades to a no-op (Scenario F, SC-008).

### Tests

- [ ] T021 [P] Unit test additive install/unregister of the `specops-lite` workflow with registry preservation in `tests/unit/test_extension_lite.py`
- [ ] T022 [P] Unit test the `lite.md` directive install/update/no-op (native + legacy marker paths) in `tests/unit/test_lite_directive.py`

### Implementation

- [ ] T023 Create `src/specops/templates/workflows/specops-lite/workflow.yml` — native steps composing `eligibility-gate` → `lane start` → work → `lane check` + `root-cause-attest` → `stop-and-ask` (halt|promote only) → `lane close`/`lane promote`, encoding guarantees G-1…G-5 (no bypass, no review cycle, minimal state, safe degrade)
- [ ] T024 [P] Create `src/specops/templates/directives/lite.md` — Principle IV directive: recognize → propose (never auto-classify) → drive the lane, deferring safety to the core, escalating on growth (B-1…B-5, D-1…D-2)
- [ ] T025 Generalize `install_workflow`/`unregister_workflow` in `src/specops/extension.py` to iterate `("specops", "specops-lite")`, each with its own template + registry entry (preserve foreign entries; never touch the bundled `speckit`)
- [ ] T026 Inject the `lite.md` directive on the native path in `src/specops/extension.py` and the legacy marker-block path in `src/specops/initializer.py`, additively and idempotently (parity with existing directives)
- [ ] T027 Amend `.specify/memory/constitution.md` — extend the Principle IV directive list with the lite-lane recognition directive, update the Sync Impact Report, MINOR bump (no principle removed/redefined) — in the same change set as T024/T026 (governance rule)

**Checkpoint**: The lane is agent-driven end-to-end; both workflows install cleanly.

---

## Phase 7: User Story 4 — Concise retrospective and evidence at closure (Priority: P2)

**Goal**: Harden closure into a durable audit record — full Feature-012 structured evidence per gate (with skipped/unavailable dispositions) and a rendered `retrospective.md` projection.

**Independent Test**: Close a lane (including a case with a skipped/unavailable optional gate); assert each gate's disposition + reason are captured and a `retrospective.md` referencing the commits is rendered (SC-004, C-2/C-3).

### Tests for User Story 4 ⚠️

- [ ] T028 [P] [US4] Unit tests for per-gate evidence taxonomy (disposition/reason, skipped/unavailable) and the `retrospective.md` render/projection in `tests/unit/test_lane.py`

### Implementation for User Story 4

- [ ] T029 [US4] Record the full Feature-012 structured evidence per gate at closure (reusing `evidence`/`gateprofiles`) in `src/specops/lane.py`, including optional-gate skipped/unavailable dispositions
- [ ] T030 [US4] Render the `retrospective.md` projection under `specs/<feature>/` from `closure.retrospective` (authoritative state stays in `lane.yaml`; mirrors `handoff render`) in `src/specops/lane.py`

**Checkpoint**: A lightweight change is fully auditable from its closure record.

---

## Phase 8: User Story 5 — Bundle adjacent reversible changes under human supervision (Priority: P3)

**Goal**: Permit bundling adjacent reversible changes into one lane under explicit confirmation, with the safety core evaluating the combined set (a trip in any change halts the whole bundle).

**Independent Test**: Bundle two adjacent changes; introduce a high-risk change in one → the whole bundle halts (not partially completed) (US5 acceptance).

### Tests for User Story 5 ⚠️

- [ ] T031 [P] [US5] Integration test of bundling (combined-set evaluation; one high-risk change halts the whole bundle) in `tests/integration/test_lane_flow.py`

### Implementation for User Story 5

- [ ] T032 [US5] Implement `--bundle NOTE` on `specops lane start` and combined-change-set evaluation across `src/specops/lane.py`, `src/specops/cli.py`, and `src/specops/safety.py` (`eligibility.bundled: true`; safety `detect` runs over the union diff)

**Checkpoint**: All user stories independently functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T033 [P] Document the lightweight lane (usage = agent-driven; human only at gates) in `README.md` and `README.pt-br.md`, standardizing wording ("lightweight lane" concept, `specops-lite` workflow id) (L2)
- [ ] T034 [P] Add a Feature 013 entry under `[Unreleased]` in `CHANGELOG.md`
- [ ] T035 Run the `quickstart.md` scenarios A–F against a fixture repo (never this repository — No Self-Application)
- [ ] T036 Run the full quality gates — `conda run -n specops ruff check`, `conda run -n specops mypy src`, `conda run -n specops pytest` — and resolve findings; assert no `lane` command or `specops-lite` step names a gate "review" (FR-021 vocabulary guard, L1)
- [X] T037 [P] Integration test: safe degradation (no context map present) and offline operation for `lane check`/`close`/`promote` in `tests/integration/test_lane_flow.py` (FR-019/SC-006, G1)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS all stories (record layer + CLI wiring).
- **US1 / US2 / US3 (Phases 3–5)**: each depends only on Foundational; independently testable at the CLI-primitive level. US3 also reuses `status`/`ledger` (existing).
- **Operating Model (Phase 6)**: depends on the Phase 3–5 commands (the workflow composes them); the directive itself (T024) is independent.
- **US4 (Phase 7)**: depends on US1's `close` (extends it).
- **US5 (Phase 8)**: depends on US1 (`start`) + US2 (`safety.py`).
- **Polish (Phase 9)**: depends on all desired stories.

### Within a story

- Tests first (write, watch fail), then implementation.
- In `lane.py`/`cli.py`, command tasks touching the same file run sequentially (not [P]).
- Different-file tasks marked [P] may run together.

### Parallel opportunities

- Setup: T001, T002 together.
- US2: T012 (`safety.py`) ∥ T013 (`config.py`); tests T010 ∥ T011.
- US3: T018 (`ledger.py`) ∥ T019 (`status.py`); tests T016 ∥ T017.
- Operating Model: T023 (`workflow.yml`) ∥ T024 (`lite.md`); tests T021 ∥ T022.
- Polish: T033 ∥ T034.

---

## Parallel Example: User Story 2

```bash
# Tests (different files) together:
Task: "Unit tests for the safety detector in tests/unit/test_safety.py"
Task: "Integration test that detections/ambiguous halt in tests/integration/test_lane_flow.py"

# Then implementation modules in different files together:
Task: "Create src/specops/safety.py detector"
Task: "Add optional lane overrides to src/specops/config.py"
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1.
2. **STOP and VALIDATE**: drive the clean-lane flow via the CLI primitives; confirm no
   full-lifecycle artifacts and a recorded closure.

### Incremental delivery

1. Foundation → US1 (MVP lane) → US2 (safety core) → US3 (lossless promotion) — the three P1
   guarantees.
2. Operating Model (Phase 6) makes it agent-driven end-to-end (the whole point: human never
   conducts the CLI).
3. US4 (audit hardening) → US5 (bundling) → Polish.

### Notes

- [P] = different files, no dependency. [Story] label maps to spec.md user stories.
- `workflow.yml` + `lite.md` are validated structurally; their live agent behavior is not
  CI-reproducible (documented, mirrors the full workflow).
- Prefer one commit per user story (Constitution Principle III); the constitution amendment
  (T027) rides in the same change set as the directive it documents.
- No Self-Application: all lane behavior is proven by fixtures under `tests/`, never by running
  `specops` against this repository.
