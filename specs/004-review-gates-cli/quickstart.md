# Quickstart Validation: `specops review`

**Feature**: `specs/004-review-gates-cli` | **Date**: 2026-07-06

Runnable scenarios proving the feature end-to-end. Details:
[contracts/review-command.md](./contracts/review-command.md),
[contracts/review-template.md](./contracts/review-template.md).

## Prerequisites

```bash
pip install -e .          # from the repo root
specops --version         # sanity
```

Scenarios use a throwaway fixture repo (or the pytest fixtures in
`tests/conftest.py`, which already build initialized ledgers):

```bash
# minimal fixture: speckit-shaped repo with specops initialized and a ledger
mkdir /tmp/review-fx && cd /tmp/review-fx
git init -q && mkdir -p .specify/templates specs/001-demo
printf 'spec' > specs/001-demo/spec.md && git add -A && git commit -qm base
specops init            # creates specops.json, installs review command
specops status init-spec 001-demo   # ledger with baseline = HEAD
```

## Scenario 1 — All gates pass (US1, SC-001)

```bash
printf 'change' >> specs/001-demo/spec.md && git commit -aqm change
specops review; echo "exit=$?"
```

**Expected**: four `[gate] ... PASS/SKIPPED` lines on stdout (lint/test
SKIPPED or PASS depending on `specops.json`), `exit=0`.

## Scenario 2 — Reconcile rejection, early stop (US1)

```bash
# corrupt: register a fake commit in the ledger via a tampered copy
python3 - <<'EOF'
import yaml, glob
p = glob.glob('specs/001-demo/status.yaml')[0]
d = yaml.safe_load(open(p)); d.setdefault('tasks', []).append(
    {'id': 'T099', 'status': 'DONE', 'commits': ['deadbeef'*5], 'evidence': ['TEST_REPORT:x']})
yaml.dump(d, open(p, 'w'))
EOF
specops review; echo "exit=$?"
```

**Expected**: `[gate] reconcile ... FAIL` with the violation on stderr,
`exit=1`, **no lint/test executed** (verify: no tool output), ledger file
otherwise untouched.

## Scenario 3 — Failing test command, output truncation (US1)

```bash
git checkout -- specs/ 2>/dev/null || git restore specs/
python3 -c "import json; c=json.load(open('specops.json')); c['test_command']='sh -c \"seq 1 200; exit 1\"'; json.dump(c, open('specops.json','w'), indent=2)"
specops review; echo "exit=$?"
```

**Expected**: reconcile PASS, `[gate] test ... FAIL` with exit code, a
truncation note (200 lines → last 50 shown), `exit=1`.

## Scenario 4 — Dirty working tree and no-diff (US1)

```bash
python3 -c "import json; c=json.load(open('specops.json')); c['test_command']=''; json.dump(c, open('specops.json','w'), indent=2)"
echo dirt > dirt.txt
specops review; echo "exit=$?"     # expect working-tree FAIL: dirty list, exit=1
rm dirt.txt && git checkout -- . 2>/dev/null || git restore .
# reset baseline == HEAD → no effective diff
specops review; echo "exit=$?"     # expect FAIL: "no effective diff", exit=1  (test_command shows SKIPPED)
```

## Scenario 5 — Ledger read-only invariant (US1, FR-007)

```bash
shasum specs/001-demo/status.yaml; specops review >/dev/null 2>&1; shasum specs/001-demo/status.yaml
```

**Expected**: identical checksums regardless of outcome.

## Scenario 6 — Template collapse delivered by init (US2, SC-005)

```bash
specops init   # re-run in the fixture
grep -n "specops review" <installed review command file>
```

**Expected**: the installed prompt contains the single gate instruction
(run `specops review`; non-zero → REJECTED, stop) and no longer instructs
`specops reconcile` / lint / test / `git status` individually.

## Scenario 7 — CI gate, any phase, non-interactive (US3, SC-004)

```bash
specops status show   # confirm phase is not REVIEW (e.g., TASKS)
specops review </dev/null; echo "exit=$?"
```

**Expected**: gates evaluated normally with stdin closed and no prompt;
outcome fully determined by exit code.

## Automated suite

```bash
pytest tests/unit/test_review.py tests/integration/test_review_cli.py -q   # feature tests
pytest -q                                                                  # full regression (SC-006)
```
