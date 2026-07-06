# CLI Contract — `specops review`

**Feature**: `specs/004-review-gates-cli` | **Date**: 2026-07-06

## Invocation

```
specops review
```

No options, no arguments, no interactive prompts (FR-008). Runs from any
directory inside the repository; all paths resolve from the repo root (same
resolution as `reconcile`/`consistency`).

## Behavior

Evaluate gates in fixed order with early stop:

| # | Gate | Pass condition | Fail evidence |
|---|---|---|---|
| 1 | `reconcile` | `reconcile.run(root)` returns no violations (warnings echoed, non-fatal) | violation lines |
| 2 | `lint` | `lint_command` exits 0; SKIPPED when empty | command, exit code, last 50 output lines (+ truncation note) |
| 3 | `test` | `test_command` exits 0; SKIPPED when empty | command, exit code, last 50 output lines (+ truncation note) |
| 4 | `working-tree` | porcelain status empty **at invocation time** (snapshotted before lint/test so their artifacts cannot fail the run) AND baseline resolvable in this clone AND `name_only_diff(baseline, HEAD)` non-empty | dirty-file list, or "ledger has no baseline", or "baseline commit cannot be resolved in this clone", or "no effective diff — nothing to review" |

## Exit codes & streams

| Outcome | Exit | Stream |
|---|---|---|
| All gates PASS/SKIPPED | 0 | report → stdout |
| Any gate FAIL | 1 | report + evidence → stderr (via `SpecopsError` message) |
| `specops.json` missing/invalid | 1 | `ConfigError` message → stderr |
| Ledger unparseable | 2 | `LedgerParseError` message → stderr |

No other exit codes (FR-006). No REVIEW-phase precondition; any ledger phase
is accepted (FR-008).

## Side effects

None. The command MUST NOT write to the ledger, `specops.json`, or any
repository file (FR-007). Byte-identical `status.yaml` before/after is a
required integration assertion.

## Report format

```
[gate] reconcile ...... PASS
  Warning: baseline commit 'a1b2c3d' not found in local history.
[gate] lint ........... SKIPPED (lint_command empty)
[gate] test ........... FAIL
  command: pytest
  exit code: 1
  [output: 412 lines, showing last 50]
  <last 50 lines of combined stdout+stderr>
```

On a full pass, the working-tree gate lists the effective diff — this is the
scope the reviewing agent reads in the surgical step (it is never told to run
git commands itself):

```
[gate] working-tree .... PASS
  3 file(s) changed since baseline a1b2c3d:
  src/app/main.py
  src/app/util.py
  tests/test_main.py
```

Line prefix `[gate] <name>` and the status tokens `PASS`/`FAIL`/`SKIPPED`
are stable API for prompts and CI greps; detail lines are human-readable and
not contractually stable. All output in English (FR-012).

## Module boundary (002 errors contract)

`src/specops/review.py` exposes `run_gates(root: Path) -> str`:
- returns the rendered report on success;
- raises `SpecopsError(message=<rendered report + evidence>)` on gate failure;
- never imports Typer, never prints, never calls `sys.exit`.

`cli.py` registers `review` through the existing `_handle_errors` wrapper —
the single exit-code mapper.
