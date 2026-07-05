# CLI Interface Contract — Changes & Additions

**Feature**: `specs/002-cli-hardening-dx` | **Date**: 2026-07-05

Delta against `specs/001-specops-cli/contracts/cli-contract.md`. Commands not
listed here are unchanged. All output in English. Exit codes: 0 success,
1 blocking failure, 2 unexpected/parse error.

## `specops --version` (new root option)

```
specops --version
```

- Prints `specops <version>` (version from installed package metadata).
- Exit 0. Works in any directory — no Git, Speckit, or ledger requirement.
- Eager: short-circuits before any other validation.

## `specops status show` (new)

```
specops status show
```

Read-only. Never writes the ledger (no task re-sync side effect).

**Success (exit 0)** — structured plain text, one fact per line:

```
feature: 002-cli-hardening-dx
branch: main
phase: REVIEW
active task: none
tasks: 12 total — 3 pending, 0 in progress, 9 done, 0 orphaned
review cycles: 2
  round 1: REJECTED (2026-07-05 → 2026-07-05)
  round 2: open
```

- `active task:` shows the IN_PROGRESS task id, or `none`.
- Cycles with `result: null` render as `open`; `started_at`/`completed_at`
  render when present.
- Legacy ledgers (no `review_cycles`, empty `tasks`) render zero counts —
  never a crash.

**Failures**:

| Condition | Exit | stderr |
|---|---|---|
| No ledger for active feature | 1 | `Ledger not found: <path>. Run 'specops status init-spec' first.` |
| Cannot resolve feature dir | 1 | `Cannot resolve active feature directory. Check .specify/feature.json.` |
| Corrupt ledger YAML | 2 | `Cannot parse ledger <path>: <reason>` |

## `specops status transition-phase <phase> [-r <result>]` (changed)

**Result vocabulary (breaking help-text fix)**: `-r/--result` accepts exactly
`APPROVED` or `REJECTED`, case-insensitive, stored uppercase. Help text no
longer advertises free-text `note`. Any other value:

```
exit 1: Invalid result '<value>'. Expected APPROVED or REJECTED.
```
(ledger untouched — validated before any read/write)

**Order-of-application fix**: a result supplied with `DONE` is applied to the
latest open review cycle **before** the DONE gate is evaluated; the cycle
result + `completed_at` and the phase advance are persisted in one write.

**Non-consuming transitions**: a *valid* result supplied on a transition that
does not consume it (e.g. `transition-phase PLAN -r APPROVED`) is silently
ignored — the transition proceeds as if `-r` were absent (compatible with
current behavior). Vocabulary validation still applies first: an *invalid*
value fails with exit 1 on any transition.

| Invocation (from REVIEW) | Behavior | Exit |
|---|---|---|
| `transition-phase DONE -r APPROVED` | cycle ← APPROVED + completed_at; phase ← DONE | 0 |
| `transition-phase DONE` (latest cycle already APPROVED) | phase ← DONE | 0 |
| `transition-phase DONE` (latest cycle open/REJECTED) | gate failure; message states APPROVED result required | 1 |
| `transition-phase DONE -r REJECTED` | rejected; message points to `transition-phase IMPLEMENT -r REJECTED` | 1 |
| `transition-phase IMPLEMENT -r REJECTED` | corrective round (unchanged) | 0 |

## Packaged review directive (changed asset)

`src/specops/templates/review.md` Step 6 — the post-report instruction
becomes the two real outcomes:

```
- APPROVED → specops status transition-phase DONE -r APPROVED
- REJECTED → specops status transition-phase IMPLEMENT -r REJECTED
```

(replaces the invalid `specops status transition-phase REVIEW -r
<APPROVED|REJECTED>`). Client repositories receive the fix on the next
`specops init` re-run.

## Exit-code regression sweep (unchanged surface, guarded)

All previously documented failure modes keep byte-identical messages and exit
codes after the error-hierarchy refactor. Verified by
`tests/integration/test_cli_surface.py` invoking each command through the
Typer runner.
