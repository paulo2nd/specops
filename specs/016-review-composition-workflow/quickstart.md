# Quickstart: Review Composition in the Workflow

Validation guide for Feature 016. It proves the shipped workflow now *performs and
enforces* the semantic review, not only the deterministic gates. See
`contracts/workflow-corrective-loop.md` for the step contract and `data-model.md` for
the consumed state.

## Prerequisites

- Repo checked out on `016-review-composition-workflow`.
- Tooling env: run quality gates under `conda run -n specops …` (repo convention).
- Spec Kit engine is **optional** for the CI checks below; the engine-parse test skips
  when it is absent. A full end-to-end run (Scenario D) needs a live integration.

## CI-reproducible checks (no engine, no agent)

### 1. Quality gates

```bash
conda run -n specops ruff check src tests
conda run -n specops mypy src
conda run -n specops pytest tests/unit/test_workflow_definition.py \
                         tests/integration/test_workflow_orchestration.py -q
conda run -n specops pytest -q          # full suite at repo thresholds
```

Expected: all green; no regressions in the existing workflow/handoff/status suites.

### 2. Structural assertions (what the unit tests encode)

Parse `src/specops/templates/workflows/specops/workflow.yml` and confirm:

- The corrective loop body contains, in order: `review-soft` → a `command:
  specops.review` step guarded by `review-soft…verdict != 'REJECTED'` →
  `handoff report --json`.
- `corrective-loop.condition` references **both** `REJECTED` and `remaining_blocking`.
- Every step type ∈ the native set (`command`/`shell`/`if`/`do-while`/…); no
  SpecOps-authored primitive.
- `terminal-gate.run == "specops review"` (hard, no `--soft`); order
  `corrective-loop < terminal-gate < done`.
- `corrective-loop.max_iterations` is unchanged from Feature 007.

### 3. Co-installation invariant (fail-closed enabler, FR-016)

Install SpecOps into a fixture repo and assert the review command file is written
wherever the workflow is written:

```bash
# (as exercised by tests/integration/test_workflow_orchestration.py)
# install() -> both .specify/workflows/specops/workflow.yml
#          and the per-integration /specops-review command file exist
```

Expected: a repo that has the workflow always has the `specops.review` command, so the
hard `command:` step can never silently degrade — an un-runnable review aborts the run.

## Behavioral scenarios (map to Success Criteria)

### Scenario A — review executes and records a finding (SC-001)

Given a fixture feature whose effective diff violates a declared requirement, running
the workflow drives `specops.review`, which records ≥1 structured finding.
Check: `specops handoff report --json` → `data.findings` non-empty (was empty under the
pre-feature workflow).

### Scenario B — unverified blocking cannot complete (SC-002)

With one **blocking** finding open, the loop re-iterates (condition true via
`remaining_blocking`) and `specops status transition-phase DONE` fails closed. Even
with the correction budget exhausted, `terminal-gate` / the `done` transition halt the
run before completion.
Check: exit is non-zero at completion; ledger phase never reaches `DONE`.

### Scenario C — verify, then complete (SC-003)

After the blocking finding is fixed and `specops handoff finding verify <id>` succeeds,
`remaining_blocking` empties, the loop exits, and completion succeeds.

### Scenario D — degrade with no findings (SC-004)

A conformant fixture (or a legacy repo with no handoff block) records zero findings;
`remaining_blocking == []`, so completion is decided by the mechanical verdict —
identical to the pre-feature workflow. No block on an empty set.

### Scenario E — mechanical gate is the precondition (SC-005)

A fixture that fails a mechanical gate: `review-soft` returns `REJECTED`, the
`semantic-review` guard is false, so the semantic review does **not** run that round;
the loop opens a corrective round instead.

> Scenarios A–E exercising the live `command:` steps require a real integration/agent
> and are **not** CI-reproducible (spec Assumptions); run them manually via
> `specify workflow run specops` against a sample repo, or assert the composed CLI
> effects directly by pre-seeding handoff state in a fixture.

## Docs & changelog

- `README.md` / `README.pt-br.md`: the workflow now performs and enforces the semantic
  review; enforcement is always-on with automatic degrade when no findings are
  recorded (behaviorally-equivalent EN/PT).
- `CHANGELOG.md`: user-visible note under `[Unreleased]`.
