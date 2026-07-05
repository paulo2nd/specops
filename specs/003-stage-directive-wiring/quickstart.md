# Quickstart: Validating Stage-Wide Directive Wiring

Runnable validation that the feature works end to end. Assumes a dev install
(`pip install -e ".[dev]"`).

## Prerequisites

- A Speckit-initialized fixture repo (the integration tests build one; see
  `tests/integration/test_init.py` fixtures).
- `specops` on `PATH`.

## Scenario 1 — All four stage prompts get injected (FR-001, FR-002, SC-007)

```bash
specops init --non-interactive
```

**Expected**: the output lists a directive status line for each of the four stage
prompts (specify, plan, tasks, implement) plus the installed review command. A
second run reports every block as `unchanged`.

Verify each prompt file contains its markers:

```bash
grep -l "SPECOPS:BEGIN specify"   .claude/skills/speckit-specify/SKILL.md
grep -l "SPECOPS:BEGIN tasks"     .claude/skills/speckit-tasks/SKILL.md
grep -l "SPECOPS:BEGIN plan"      .claude/skills/speckit-plan/SKILL.md
grep -l "SPECOPS:BEGIN implement" .claude/skills/speckit-implement/SKILL.md
```

## Scenario 2 — Ledger exists when implement starts (US1, SC-002)

Drive the tasks stage (agent generates `tasks.md`), then confirm the tasks
directive created and populated the ledger:

```bash
specops status show          # phase should read TASKS; tasks listed as pending
specops status start-task T001   # succeeds without a manual init-spec
```

**Expected**: `start-task` succeeds — proving the ledger was auto-created with the
task IDs synced from `tasks.md`.

## Scenario 3 — Phase tracks the stage (US2, SC-004)

```bash
specops status show          # after tasks stage → TASKS
# ... implement session start runs: transition-phase IMPLEMENT
specops status show          # → IMPLEMENT
# ... implement session end runs: transition-phase REVIEW
specops status show          # → REVIEW, with one open review cycle
```

**Expected**: the reported phase matches each stage; entering REVIEW shows an
open (uncompleted) review cycle for `/specops-review` to record into.

## Scenario 4 — Coverage tags pass consistency (US3, SC-003)

```bash
specops consistency          # exit 0 on freshly generated tasks.md
```

**Expected**: exit 0 — every task line the tasks stage generated carries a valid
`[SC-xxx]` tag referencing an existing spec criterion.

## Scenario 5 — Graceful degradation (SC-006)

In a Speckit repo where `specops init` was **not** run, open any stage prompt:

**Expected**: no SPECOPS markers are present; the Speckit prompt is byte-identical
to upstream and completes its core work with no SpecOps steps.

## Scenario 6 — Reversibility (SC-005)

Snapshot the four prompts, run `specops init`, then remove the blocks (uninstall
path):

**Expected**: each prompt is restored byte-for-byte to its pre-injection content.

## Automated coverage

These scenarios are exercised by:
- `tests/unit/test_speckit.py` — target resolution (Scenario 1 resolution half).
- `tests/unit/test_injection.py` — inject/idempotent/reversible (Scenarios 1, 6).
- `tests/integration/test_init.py` — full four-prompt injection end to end.

Scenarios 2–4 that require a live agent generating artifacts are validated
agent-in-the-loop (like the existing Scenario F for `/specops-review`), not by
pytest.
