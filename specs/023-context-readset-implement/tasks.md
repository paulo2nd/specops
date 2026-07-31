# Tasks: Context Read-Set Consumption in IMPLEMENT

**Input**: Design documents from `/specs/023-context-readset-implement/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/implement-directive.md, quickstart.md

**Tests**: Included (Constitution task gate — no task closes without passing automated tests). Note: this feature changes **no runtime code**; the "implementation" is directive text and docs, so tests assert delivered directive content (contract C1–C7), delivery-path invariants, and the acceptance-gate coverage invariant on fixtures. Coverage-invariant tests (T003) verify existing frozen behavior and are expected to pass immediately; directive-content tests (T002/T005/T007) MUST fail before the directive edit that satisfies them.

**Organization**: Tasks are grouped by user story. All three stories edit the same directive file and test files, so stories execute **sequentially** (P1 → P2 → P3); parallelism exists only within a story where files differ.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project (per plan.md): `src/specops/` + `tests/` at repository root.
This feature touches only: `src/specops/templates/directives/implement.md`,
`docs/commands.md`, `README.md`, `README.pt-br.md`,
`tests/unit/test_implement_directive.py`, `tests/unit/test_contextmap_consume.py`.

---

## Phase 1: Setup

**Purpose**: Confirm a green baseline so every later failure is attributable to this feature's work.

- [x] T001 Run the full gate and confirm green before any change: `conda run -n specops ruff check src tests && conda run -n specops mypy src && conda run -n specops pytest` (no file changes; baseline evidence for the ledgerless dev loop)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None required — every surface this feature consumes already ships and is frozen (`context resolve` since Feature 008/009, `trace acknowledge` since Feature 010, both delivery paths wired per research.md R5). No foundational tasks.

**Checkpoint**: Baseline green (T001) — user story work can begin.

---

## Phase 3: User Story 1 — Implement sessions read only what the map prescribes (Priority: P1) 🎯 MVP

**Goal**: The implement directive instructs the agent, at session start before the first task, to resolve the IMPLEMENT-phase context package per declared context (`specops context resolve --id <cid> --phase implement`) and scope session reads to the union of the resolved packages.

**Independent Test**: `conda run -n specops pytest tests/unit/test_implement_directive.py tests/unit/test_contextmap_consume.py` — directive content carries C1/C2/C3/C7 and the fixture proves per-path packages are covered by the declared-context union.

### Tests for User Story 1 (write first, confirm the content tests FAIL) ⚠️

- [x] T002 [US1] Create tests/unit/test_implement_directive.py (pattern: tests/unit/test_lite_directive.py) with failing directive-content tests for contract C1–C3 + C7: (a) native path — `extension._build_hooks()["after_implement"]` prompt contains a Context Read Set section; (b) content — session-start-before-first-task resolution reading the `**SpecOps-Contexts**:` line of plan.md, one `specops context resolve --id <cid> --phase implement` per declared id, literal lowercase `--phase implement` (and no `--phase IMPLEMENT`), scoping to the union of `read_set` + `expanded_read_set`; (c) negative — the section names no new command/flag/record (contract "Out of contract")
- [x] T003 [P] [US1] Add acceptance-gate coverage tests to tests/unit/test_contextmap_consume.py on the existing `context_map_repo` fixture (expected to pass immediately — invariant proof, SC-001): for every plan-declared path, the package from `cmd_resolve(path=…, phase="implement")` is contained in the union of the declared contexts' `cmd_resolve(ctx_id=…, phase="implement")` packages (`read_set` + `expanded_read_set`); include a case where a dependency contributes reads via `expanded_read_set`

### Implementation for User Story 1

- [x] T004 [US1] Add the `### Context Read Set (Feature 023)` section to src/specops/templates/directives/implement.md — placed adjacent to "Context Provenance (Feature 009)"/"Discovered Paths (Feature 010)" — implementing C1 (session-start resolution per declared id), C2 (lowercase `--phase implement`), C3 (scope reads to the union; reading less is always fine), C7 (only existing surfaces named); T002 and T003 now pass

**Checkpoint**: User Story 1 fully functional — directive delivers read-set scoping; coverage invariant proven on fixture. Commit once for US1 (one commit per user story).

---

## Phase 4: User Story 2 — Genuine discoveries outside the read set follow the paved road (Priority: P2)

**Goal**: The read set is guidance plus record, never a gate: out-of-set reads block nothing, and a discovery that changes an undeclared path routes through the existing Feature 010 acknowledgement flow.

**Independent Test**: `conda run -n specops pytest tests/unit/test_implement_directive.py -k "gate or discover or acknowledg"` — content asserts C4/C5 and rejects any blocking wording or new acknowledgement type.

### Tests for User Story 2 (write first, confirm they FAIL) ⚠️

- [x] T005 [US2] Extend tests/unit/test_implement_directive.py with failing content tests for C4 + C5: (a) the section states the read set never blocks — an out-of-set read is permitted and needs no acknowledgement by itself; (b) it cross-references the existing "Discovered Paths (Feature 010)" flow (`specops trace acknowledge`) for a discovery that leads to a **changed** undeclared path, without restating the acknowledgement contract; (c) negative — no "read acknowledgement" or other new record type appears

### Implementation for User Story 2

- [x] T006 [US2] Extend the Context Read Set section in src/specops/templates/directives/implement.md with the guidance-not-gate rule and the Feature 010 cross-reference (C4/C5, research.md R6 — reads are guidance; the drift gate governs changes); T005 now passes

**Checkpoint**: User Stories 1–2 complete — scoping plus a sanctioned, non-blocking escape hatch. Commit once for US2.

---

## Phase 5: User Story 3 — Unmapped repositories behave exactly as today (Priority: P3)

**Goal**: Rule 5 degradation — no map is a supported no-op (exit 0), an invalid map (resolve exit 1, frozen contract) means "proceed without scoping, never halt", and both delivery paths ship the identical updated directive.

**Independent Test**: `conda run -n specops pytest tests/unit/test_implement_directive.py tests/unit/test_contextmap_consume.py -k "no_map or invalid or degrad or inject or idempot"` — degradation content asserted, delivery invariants hold, fixture statuses confirmed.

### Tests for User Story 3 (write first, confirm the content tests FAIL) ⚠️

- [x] T007 [US3] Extend tests/unit/test_implement_directive.py with failing content tests for C6 plus delivery invariants: (a) content — "no map present" → supported no-op, and **any non-zero exit** of the resolution step → proceed without read-set scoping, never halt (no wording that gates); (b) legacy path — `initializer.inject_block` of the updated implement.md content is idempotent (`created` then `unchanged`, exactly one implement block), mirroring test_lite_directive.py; (c) in tests/unit/test_contextmap_consume.py, assert the R4 degradation rows through `cmd_resolve` with `phase="implement"`: no map → `no_map_present`/PASS, invalid map → GATE_REJECTION (expected to pass immediately — frozen-contract proof, SC-003/SC-004)

### Implementation for User Story 3

- [x] T008 [US3] Extend the Context Read Set section in src/specops/templates/directives/implement.md with the degradation instructions (C6) and confirm the existing Graceful Degradation section still covers the CLI-absent case unchanged; T007 now passes

**Checkpoint**: All user stories complete — spec's acceptance gate satisfiable end-to-end on fixtures. Commit once for US3.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation (EN/PT parity) and final validation.

- [ ] T009 [P] Update docs/commands.md — the "map is consumed in the lifecycle" list (currently plan-check/impact/stale, docs/commands.md:299-310) gains implement-time consumption: the implement directive resolves the phase read set via `context resolve --phase implement` and scopes agent reads to it (guidance plus record, never a gate; no-op without a map)
- [ ] T010 [P] Update README.md (context feature row/description, README.md:109) and README.pt-br.md (equivalent line, README.pt-br.md:114) so both describe implement-time read-set consumption equivalently — full EN/PT parity in the same PR (research.md R8; docs/stability.md intentionally untouched)
- [ ] T011 Run the full quickstart validation (specs/023-context-readset-implement/quickstart.md): full gate (ruff, mypy, pytest), directive-delivery tests, acceptance-gate tests, and the documentation-parity greps; confirm no test outside this feature's two test files changed behavior. Commit once for polish

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: empty — nothing blocks
- **User Stories (Phases 3–5)**: sequential (P1 → P2 → P3) — all three edit the same directive file and test file, so no cross-story parallelism
- **Polish (Phase 6)**: after Phase 5 (docs describe the final directive behavior)

### Within Each User Story

- Content tests written and observed FAILING before the directive edit (T002→T004, T005→T006, T007→T008)
- Invariant tests (T003, T007c) may pass immediately — they prove frozen behavior, not new code
- One commit per user story (Constitution, Principle III granularity), one for polish

### Parallel Opportunities

- T002 ∥ T003 (different test files)
- T009 ∥ T010 (different doc files)
- Everything else is sequential by design (shared files)

## Parallel Example: User Story 1

```bash
# Different files — can proceed together:
Task: "T002 directive-content tests in tests/unit/test_implement_directive.py"
Task: "T003 coverage-invariant tests in tests/unit/test_contextmap_consume.py"
```

---

## Implementation Strategy

**MVP = User Story 1** (Phases 1 + 3): after T004 the directive already delivers
the feature's core value — read-set-scoped implement sessions. US2 adds the
non-blocking escape hatch, US3 the degradation wording; both are small,
same-file increments. Ship only after Phase 6 (docs parity is a same-PR rule).

---

## Notes

- No runtime code changes: any diff under `src/specops/*.py` is out of scope for this feature
- Frozen contracts (021) must not shift: no CLI flag, output field, or exit-code change; `docs/stability.md` untouched
- Success-criteria coverage: SC-001 → T003; SC-002 → T005/T006; SC-003 → T007/T008; SC-004 → T003/T007 (frozen statuses) + the no-runtime-change rule; SC-005 → T009/T010
