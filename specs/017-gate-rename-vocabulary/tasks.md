---
description: "Task list for Feature 017 — Gate Rename & Vocabulary Pass"
---

# Tasks: Gate Rename & Vocabulary Pass

**Input**: Design documents from `specs/017-gate-rename-vocabulary/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/preflight-command.md, quickstart.md

**Tests**: Mandatory per the Constitution task gate — every story carries automated tests, written to fail first.

**Organization**: Tasks are grouped by user story (spec.md priorities) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US4 map to the spec's user stories
- Exact file paths are included in each task

## Path Conventions

Single Python project: `src/specops/`, `tests/` at repo root. Installable extension assets under `src/specops/templates/`. Dev tooling runs under `conda run -n specops …`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the green baseline the "zero regressions" criteria (SC-004/SC-006) are measured against.

- [X] T001 Confirm a clean baseline on branch `017-gate-rename-vocabulary`: run `conda run -n specops ruff check .`, `conda run -n specops mypy src`, and `conda run -n specops pytest -q` and record that all pass before any change. (baseline: ruff ✓, mypy ✓, 748 passed, 87.9% cov)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared CLI refactor both P1 stories build on. Kept behavior-preserving so the suite stays green.

**⚠️ CRITICAL**: US1 and US2 cannot begin until this is complete.

- [X] T002 Refactor `src/specops/cli.py`: extract the body of `review()` into a private shared impl `_run_gate(command_name: str, json_out: bool, soft: bool, sarif: bool)` that passes `command_name` into every `outcome.render(command_name, …)` call (replacing the hard-coded `"review"`). Leave the existing `review` command delegating to `_run_gate("review", …)` with no behavior change and no notice yet, so all existing tests still pass.

**Checkpoint**: `conda run -n specops pytest -q` still green; `specops review` behaves exactly as before.

---

## Phase 3: User Story 1 - The mechanical gate has an honest name (Priority: P1) 🎯 MVP

**Goal**: Ship `specops preflight` as the canonical name for the deterministic gate suite, byte-for-byte equivalent to the former `specops review` for the same repo state.

**Independent Test**: Run `specops preflight` (and `--json`) against a passing and a failing fixture; verify it runs the full gate suite and returns the same verdict, exit code, and stdout (with `command:"preflight"`) as the pre-rename gate, with empty stderr on success.

### Tests for User Story 1 (write first, ensure they FAIL) ⚠️

- [X] T003 [P] [US1] In `tests/unit/test_outcome_contract.py`, add a case asserting `outcome.render("preflight", outcome.PASS, verdict="APPROVED", gates=[…])` yields `"command": "preflight"` with unchanged keys/shape; confirm existing `render("review", …)` cases still hold. (SC-005)
- [X] T004 [P] [US1] Create `tests/integration/test_preflight_cli.py` with `specops preflight` cases: (a) passing fixture → `class:"pass"`, `verdict:"APPROVED"`, exit 0, `command:"preflight"`, `result.stderr == ""`; (b) failing fixture in hard mode → `class:"gate-rejection"`, exit 1, evidence on stderr; (c) `--json --soft` on a rejecting fixture → exit 0 with the verdict in JSON; (d) `--sarif` → exit 0 read-only. Use the repo's `from typer.testing import CliRunner; runner = CliRunner()` pattern and read `result.stderr`/`result.stdout` separately — do NOT pass `mix_stderr=` (removed in Click 8.4.2; finding I1). (SC-001)

### Implementation for User Story 1

- [X] T005 [US1] In `src/specops/cli.py`, register `@app.command("preflight")` delegating to `_run_gate("preflight", …)` with the identical `--json` / `--soft` / `--sarif` options and docstring; make `preflight` the canonical command. Run T003/T004 to green.

**Checkpoint**: `specops preflight` fully functional and independently testable.

---

## Phase 4: User Story 2 - Existing invocations keep working via a deprecated alias (Priority: P1)

**Goal**: Retain `specops review` as a behavior-identical deprecated alias that emits exactly one stderr line, keeping stdout byte-stable for existing consumers.

**Independent Test**: For the same fixtures as US1, `specops review` yields stdout and exit code byte-identical to `specops preflight`, plus exactly one stderr line naming `preflight` and the removal window; `review --json` stdout parses as clean JSON with `command:"review"`.

### Tests for User Story 2 (write first, ensure they FAIL) ⚠️

- [X] T006 [P] [US2] In `tests/integration/test_preflight_cli.py`, add alias tests: for identical fixture state, `specops review` stdout is byte-identical to `specops preflight` and exit codes match; stderr is exactly one line naming `specops preflight` + the removal window; `specops review --json` stdout is valid JSON with `command:"review"` and no notice text mixed in. (SC-002, FR-003/FR-004)
- [X] T007 [P] [US2] Add a help-surface test asserting `specops review --help` shows a `[DEPRECATED — use 'specops preflight']` marker in its help/short_help text and that `preflight` is presented as canonical. Do NOT assert on Click's `deprecated=` flag output. (FR-014)

### Implementation for User Story 2

- [X] T008 [US2] In `src/specops/cli.py`, register the `review` command with a `help`/`short_help` that begins `[DEPRECATED — use 'specops preflight']` and emit **exactly one** deprecation line to **stderr** via `typer.echo(<notice>, err=True)` **before** delegating to `_run_gate("review", …)`; the notice names `specops preflight` and the removal window and is NOT suppressible by any flag or env var. **Do NOT set `deprecated=True`** on the command: the installed Typer 0.27.0 / Click 8.4.2 auto-emits its own second stderr line (`DeprecationWarning: The command 'review' is deprecated.`) with the wrong wording, which would break FR-002/SC-002's "exactly one line" (analysis finding C1). The single hand-emitted notice is the only deprecation output. Run T006/T007 to green.
- [X] T009 [US2] Update `tests/integration/test_review_cli.py`: re-point the pure-behavior assertions (verdict, exit code, stdout, `result.stderr == ""`) to `specops preflight` so the newly-added alias notice does not cause a false regression; retain any assertion that legitimately exercises the `review` name as the alias. (guards SC-004)

**Checkpoint**: MVP complete — `preflight` and the `review` alias both work; upgrading breaks no existing invocation.

---

## Phase 5: User Story 3 - Shipped artifacts teach the honest name (Priority: P2)

**Goal**: The shipped workflow definition, the injected directive, the constitution, and the EN/PT READMEs name the gate `preflight`, while every legitimate "review" (phase / `/specops-review` directive / verdict) is preserved.

**Independent Test**: Inspect the shipped `workflow.yml`, directive template, constitution, and READMEs — the gate is named `preflight`, `command: specops.review` is untouched, the definition validates, and EN/PT are behaviorally equivalent.

### Tests for User Story 3 (write first, ensure they FAIL) ⚠️

- [X] T010 [P] [US3] Update `tests/unit/test_workflow_definition.py`: assert `review-soft.run` contains `specops preflight --json --soft` and `terminal-gate.run == "specops preflight"`; KEEP the assertion `semantic-review.command == "specops.review"` unchanged (over-correction guard, FR-013). (SC-003)
- [X] T011 [P] [US3] Update `tests/integration/test_review_asset.py`: change the gate assertions that currently require `"specops review" in installed_review` (≈ lines 37, 59–62) to `"specops preflight"`; keep the surgical-order, `REJECTED`, and transition assertions intact.

### Implementation for User Story 3

- [X] T012 [US3] Update `src/specops/templates/workflows/specops/workflow.yml`: rename the two `shell: specops review` steps (`review-soft` → `specops preflight --json --soft`; `terminal-gate` → `specops preflight`) and update the header comment block; DO NOT touch `command: specops.review` (the semantic directive).
- [X] T013 [US3] Update `src/specops/templates/review.md` (the `/specops-review` directive): change the gate invocation and references from `specops review` to `specops preflight`; keep the directive itself named review.
- [X] T014 [US3] Amend `.specify/memory/constitution.md` (PATCH bump 1.8.0 → 1.8.1): change gate references to `specops preflight`, explicitly reserve "review" for the phase / `/specops-review` directive / verdict, update the Sync Impact Report comment and the `**Version**` / `**Last Amended**` footer. No principle removed or redefined.
- [X] T015 [P] [US3] Update `README.md`: change gate references to `specops preflight`, resolve the "to be renamed" forward-reference (≈ line 469), and document the `specops review` deprecated alias and its removal window.
- [X] T016 [P] [US3] Update `README.pt-br.md` equivalently (≈ line 502), keeping it behaviorally equivalent to `README.md` (FR-010/SC-007).

**Checkpoint**: composing authors reading the shipped artifacts see the honest name; the semantic review is intact and the workflow validates.

---

## Phase 6: User Story 4 - Other overloaded terms are corrected or documented (Priority: P3)

**Goal**: Record a conservative vocabulary sweep — the gate is the only rename; every other user-facing overloaded term is documented, none left unaddressed.

**Independent Test**: Review the sweep catalogue — exactly one renamed entry (`review → preflight`), every other examined term has a "keep/document" disposition with a rationale, and no other living surface term was renamed.

- [ ] T017 [US4] Finalize and verify the sweep catalogue in `specs/017-gate-rename-vocabulary/research.md` §D8: confirm exactly one rename and that every other user-facing overloaded term (`gate`, `reconcile`, `consistency`, `handoff`, the reserved "review" senses) is documented "keep" with a rationale; run a grep over `src/specops/` living surfaces to confirm no additional term was renamed. (SC-008)

**Checkpoint**: sweep complete and provably conservative.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T018 Add a `CHANGELOG.md` entry under `[Unreleased]`: the `review → preflight` rename, `specops review` retained as a deprecated alias, the removal window (no earlier than next MINOR, never in a patch), "behavior unchanged", and the one-line migration ("move callers to `specops preflight`"). Do not rewrite historical entries. (FR-006/FR-015)
- [ ] T019 [P] Optional internal-comment refresh (no behavior, no user-facing surface): update gate-name mentions in `src/specops/cli.py` (≈ line 284), `src/specops/review.py`, `src/specops/gateprofiles.py` (≈ line 246), and `src/specops/shell.py` for accuracy. Skippable without affecting acceptance.
- [ ] T020 Run the grep guards: no `specops review` remains as a gate reference in `src/specops/templates/` or the living text of `.specify/memory/constitution.md`; confirm `specops.review` (semantic directive) still present in `workflow.yml`. (SC-006/FR-013)
- [ ] T021 Run the full quality gate — `conda run -n specops ruff check . && conda run -n specops mypy src && conda run -n specops pytest -q` (zero regressions, SC-004) — and execute the `quickstart.md` validation scenarios 1–6.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: no dependencies.
- **Foundational (T002)**: depends on T001; BLOCKS US1 and US2.
- **US1 (T003–T005)**: depends on T002.
- **US2 (T006–T009)**: depends on T002; T008 depends on the `preflight` command from T005 (its stdout is the alias's parity target).
- **US3 (T010–T016)**: depends on T005/T008 existing (so the workflow's `preflight` steps resolve to a real command); otherwise independent of US1/US2 test internals.
- **US4 (T017)**: depends on US3 edits being final (so the "only one rename" claim is verifiable).
- **Polish (T018–T021)**: depends on all desired stories; T020/T021 are the final gates.

### User Story Dependencies

- **US1 (P1)** and **US2 (P1)** together form the MVP; US2's parity test consumes US1's `preflight` output.
- **US3 (P2)** consumes the renamed command but is independently testable via the definition/asset tests.
- **US4 (P3)** is a documentation/verification pass over the completed rename.

### Within Each User Story

- Tests are written first and must FAIL before implementation.
- `cli.py` command registration (T005) precedes the alias notice (T008).
- Living-artifact edits (T012–T016) follow their updated tests (T010–T011).

### Parallel Opportunities

- T003 / T004 (US1 tests) — different files.
- T006 / T007 (US2 tests) — same new file section but independent cases; treat as parallel-authorable.
- T010 / T011 (US3 tests) — different files.
- T015 / T016 (README EN/PT) — different files.
- T019 (optional comment refresh) — independent.

---

## Parallel Example: User Story 1

```bash
# Author US1 tests together (write-first, must fail):
Task: "Add preflight render case in tests/unit/test_outcome_contract.py"      # T003
Task: "Create tests/integration/test_preflight_cli.py preflight cases"        # T004
```

## Parallel Example: User Story 3

```bash
# Update the two READMEs in parallel (behaviorally equivalent):
Task: "Update README.md gate refs → preflight + document alias"               # T015
Task: "Update README.pt-br.md equivalently"                                   # T016
```

---

## Implementation Strategy

### MVP First (US1 + US2 — both P1)

1. T001 Setup baseline → T002 Foundational refactor.
2. US1 (T003–T005): ship `specops preflight`.
3. US2 (T006–T009): ship the `review` deprecated alias.
4. **STOP and VALIDATE**: quickstart Scenarios 1–3 — the gate is honestly named and the alias is byte-stable with one stderr line.

### Incremental Delivery

1. MVP (US1+US2) → the working rename + alias.
2. US3 → shipped artifacts and constitution name the gate `preflight` (composing authors are taught the honest name).
3. US4 → record the conservative sweep.
4. Polish → CHANGELOG, grep guards, full gate, quickstart.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- The over-correction guard (FR-013) is load-bearing: `shell: specops review` → `preflight`, but `command: specops.review` stays. T010 pins it.
- Zero persisted-state change (FR-011): no ledger field, phase id, verdict value, or JSON key is renamed — only the command name and its invoked-name-mirrored output label.
- Frozen history (`specs/004|007|011|012|016-*`, historical CHANGELOG/ROADMAP entries) is out of scope — do not edit.
- Commit after each task or logical group; keep the branch's suite green at every checkpoint.
