# Quickstart / Validation: Gate Rename & Vocabulary Pass

**Feature**: 017 | **Date**: 2026-07-24

Runnable checks that prove the rename ships correctly with **no behavior change** and a
working deprecated alias. Run tooling under the project env: `conda run -n specops …`.

## Prerequisites

- Repo checked out on branch `017-gate-rename-vocabulary` (create it before implementing;
  we build with plain Spec Kit artifacts — no SpecOps ledger in this repo).
- Dev env: `conda run -n specops pytest -q` passes on `main` before starting.

## Scenario 1 — Canonical gate runs and is honestly named (SC-001)

```bash
# In a fixture Speckit repo in a passing state:
specops preflight --json
# Expect: {"command":"preflight","outcome":"ok","class":"pass","verdict":"APPROVED",...}
# Exit 0. stderr empty.

specops preflight            # human mode
# Expect: [gate] reconcile … [gate] working-tree … ; exit 0
```

**Pass**: `command` is `"preflight"`; verdict/exit/stdout match the pre-rename gate for the
same state; no deprecation text anywhere.

## Scenario 2 — Deprecated alias is byte-stable + one stderr line (SC-002)

```bash
specops review --json 1>out.json 2>err.txt
# out.json: byte-identical to `specops preflight --json` EXCEPT "command":"review"
# err.txt : exactly ONE line, naming `specops preflight` and the removal window
python -c "import json,sys; json.load(open('out.json'))"   # stdout is clean JSON
wc -l err.txt                                               # -> 1
```

**Pass**: stdout parses; `command` is `"review"`; exactly one stderr line; exit code equals
`preflight`'s. No flag/env var suppresses the line.

## Scenario 3 — Fail-closed hard mode unchanged (SC-001)

```bash
# Fixture with a stray untracked file (working-tree gate fails):
specops preflight ; echo "exit=$?"     # exit=1, evidence (e.g. stray path) on stderr
specops review    ; echo "exit=$?"     # exit=1 too, plus the one deprecation line
```

**Pass**: both exit `1`; evidence identical on stderr; the alias adds only its one notice.

## Scenario 4 — Shipped workflow uses `preflight`, keeps the semantic review (SC-003, FR-013)

```bash
conda run -n specops pytest tests/unit/test_workflow_definition.py -q
```

**Pass**: `review-soft` runs `specops preflight --json --soft`; `terminal-gate` runs
`specops preflight`; `semantic-review.command` is still `specops.review`; the definition
validates against the engine.

## Scenario 5 — No consumer breaks; docs & constitution consistent (SC-004/006/007)

```bash
conda run -n specops ruff check . && conda run -n specops mypy src && conda run -n specops pytest -q
# grep guards:
! grep -rn "specops review" src/specops/templates/ .specify/memory/constitution.md   # gate refs gone from living templates/constitution
grep -rn "specops.review" src/specops/templates/workflows/specops/workflow.yml       # semantic directive still present
```

**Pass**: full suite green (zero regressions); living templates and the constitution no
longer call the gate "review"; the semantic `specops.review` directive is intact; README.md
and README.pt-br.md describe `preflight` + the alias equivalently.

## Scenario 6 — Conservative sweep recorded (SC-008)

Confirm [research.md §D8](./research.md) lists every examined user-facing term with a
disposition, exactly one of which is a rename (`review → preflight`) and the rest
"keep/document".

**Pass**: catalogue complete; no identified term left unaddressed; `gate` deliberately kept.

## Definition of validation done

- [ ] Scenarios 1–3: `preflight` and the `review` alias behave per contract (SC-001/002).
- [ ] Scenario 4: workflow definition updated + validates; semantic review untouched (SC-003).
- [ ] Scenario 5: ruff + mypy + pytest green; living docs/constitution consistent (SC-004/006/007).
- [ ] Scenario 6: sweep catalogue complete and conservative (SC-008).
- [ ] CHANGELOG entry added (rename, alias, window, behavior-unchanged); constitution PATCH-bumped to 1.8.1 with Sync Impact Report.
