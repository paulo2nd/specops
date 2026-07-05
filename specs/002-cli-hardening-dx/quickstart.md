# Quickstart Validation: CLI Hardening & Developer Experience

**Feature**: `specs/002-cli-hardening-dx` | **Date**: 2026-07-05

Runnable scenarios proving each user story end to end. Contracts:
[cli-interface.md](contracts/cli-interface.md), [errors.md](contracts/errors.md).

## Prerequisites

```bash
pip install -e .[dev]     # installs specops + ruff/mypy/pytest-cov
```

Scenarios A–D use a throwaway Speckit-shaped repo:

```bash
export SB=$(mktemp -d) && cd $SB
git init -q . && git commit -q --allow-empty -m init
mkdir -p .specify/templates specs/001-demo
printf '{"feature_directory": "specs/001-demo"}' > .specify/feature.json
printf -- '- [ ] T001 Demo task\n' > specs/001-demo/tasks.md
specops status init-spec
```

## Scenario A — Review approval via CLI only (US1 / SC-001)

```bash
for p in PLAN TASKS IMPLEMENT REVIEW; do specops status transition-phase $p; done
specops status transition-phase DONE -r APPROVED   # exit 0  ← the P1 fix
grep -A2 'review_cycles' specs/001-demo/status.yaml # result: APPROVED, phase DONE
```

Negative paths (ledger must remain unchanged after each):

```bash
specops status transition-phase DONE -r REJECTED    # exit 1, points to IMPLEMENT -r REJECTED
specops status transition-phase DONE -r "note ok"   # exit 1, invalid result value
```

(run these from a second repo still in REVIEW, or before the approval above)

**Expected**: approval requires zero manual edits of `status.yaml`.

## Scenario B — Ledger at a glance (US2 / SC-002, SC-003)

```bash
specops status show        # exit 0; phase/active task/counts/cycles, 1 fact per line
cd /tmp && specops --version   # exit 0; "specops 0.1.0" — no git repo needed
```

**Expected**: both complete in < 1 s; `show` output matches the
[contract format](contracts/cli-interface.md#specops-status-show-new).

## Scenario C — Crash-safe writes & strict evidence (US3 / SC-004, SC-005)

Evidence grammar (from the sandbox repo, with T001 started):

```bash
specops status start-task T001
specops status complete-task T001 --evidence "CLI_LOG:"            # exit 1 (empty summary)
specops status complete-task T001 --evidence "LOG:x"               # exit 1 (unknown class)
specops status complete-task T001 --evidence "CLI_LOG:a; done"     # exit 1 (orphan segment)
specops status complete-task T001 --evidence "CLI_LOG:checked ok"  # exit 0
```

Atomicity + numeric ordering are unit-verified (simulated interruption in
`tests/unit/test_status.py`; `specs/9-*` vs `specs/10-*` in
`tests/unit/test_speckit.py`):

```bash
pytest --no-cov tests/unit/test_status.py tests/unit/test_speckit.py
```

(`--no-cov` on subset runs — the 85% threshold in `addopts` is meant for
full-suite runs and would fail spuriously on partial coverage)

## Scenario D — Exit-code contract preserved (US4 / SC-006)

```bash
pytest --no-cov tests/integration/test_cli_surface.py  # sweep: streams + exit codes
pytest                                          # entire suite green, coverage ≥ 85%
```

Library usability spot check (no process exit from business code):

```bash
python -c "
from pathlib import Path
from specops import status, errors
try: status.cmd_start_task(Path('.'), 'T999')
except errors.SpecopsError as e: print('raised:', e.message)"
```

## Scenario E — Quality gates (US5 / SC-007, SC-008)

Local (from the project repo):

```bash
ruff check .           # 0 findings
mypy src/specops       # success
pytest                 # green, coverage ≥ 85% enforced by --cov-fail-under
```

CI: push a branch with (1) an unused import, (2) a `str`-vs-`int` type error,
(3) a failing assert — three separate commits. **Expected**: each commit's
pipeline run fails on the corresponding step (lint / type / test) for both
Python 3.10 and 3.14 jobs; reverting all three turns the pipeline green.

## Cleanup

```bash
rm -rf $SB
```
