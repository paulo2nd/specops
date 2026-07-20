# Contract: SpecOps CLI Outcome Contract

Stable, machine-readable outcome for the gate commands the `specops` workflow composes. Consumed by
Spec Kit native `do-while`/`if`/`gate` conditions. Backward-compatible: exit codes are unchanged from
today's `errors.py`; `--json` is additive and off by default.

## Exit codes (stable)

| Code | Meaning | Class | Workflow reaction |
|---|---|---|---|
| `0` | success / gate pass | `pass` | advance |
| `1` | blocking gate result **or** review `REJECTED` | `gate-rejection` | corrective loop (review) / terminal halt |
| `2` | infrastructure / data / usage error | `infra-error` | fix environment (e.g. `rebaseline`, install command) |

Notes:
- **`--json` exits are derived from the class** via `outcome.exit_for(class)`, so `class`, `outcome`,
  and exit code never drift: `pass`↔`ok`↔0, `gate-rejection`↔`blocked`↔1, `infra-error`↔`error`↔2.
  A **reconcile divergence is `infra-error` → exit 2** (fix the environment via `rebaseline`), distinct
  from a review `REJECTED` which is `gate-rejection` → exit 1 (correct the work → corrective loop).
- Plain (non-`--json`) mode preserves the legacy `errors.py` exit codes (a blocking `SpecopsError`
  exits 1); the `--json` surface intentionally uses the class-consistent code (setup/infra failures
  exit 2) so an automation consumer sees one coherent contract.
- An integration lifecycle command that crashes is **out of scope** for this contract: it is a Spec
  Kit engine abort (execution failure) recovered by `specify workflow resume`.

## `--json` output (additive)

`specops review --json`
```json
{ "command": "review", "outcome": "blocked", "class": "gate-rejection",
  "verdict": "REJECTED",
  "gates": [ {"name": "reconcile", "status": "PASS"},
             {"name": "lint", "status": "PASS"},
             {"name": "test", "status": "FAIL"},
             {"name": "working-tree", "status": "SKIPPED"} ] }
```

`specops reconcile --json` (a divergence — `rebaseline`-fixable, exit 2)
```json
{ "command": "reconcile", "outcome": "error", "class": "infra-error",
  "diverged_dimension": "baseline", "remedy": "specops status rebaseline" }
```
A commit-history/evidence violation (no divergence) is also `infra-error` (exit 2) but carries
`violations` and **no** `remedy` — `rebaseline` cannot prune a stale commit reference.

`specops consistency --json`
```json
{ "command": "consistency", "outcome": "ok", "class": "pass" }
```

## Guarantees

- **G1**: `outcome`/`class`/`exit_code` are consistent (`ok`↔0, `blocked`↔1, `error`↔2), enforced by
  deriving every `--json` exit from `outcome.exit_for(class)`.
- **G2**: `review.verdict` is present iff `command == "review"`; `REJECTED` ⇔ exit 1 with
  `class = gate-rejection`.
- **G3**: `reconcile.diverged_dimension` and `remedy = specops status rebaseline` appear **only** for a
  workspace/identity/workflow-state divergence (no new command — FR-012); a commit-history/evidence
  violation is reported without a `remedy` (it is not rebaseline-fixable).
- **G4**: JSON is emitted to stdout only; human-readable text is unchanged when `--json` is absent
  (backward compatibility).
- **G5**: Read-only invocations never mutate the ledger or repo (SC-007; Principle II).

## Tested by

`tests/unit/test_outcome_contract.py` (shape + exit-code/class consistency), plus assertions in
`test_review.py`, `test_reconcile.py`, `test_consistency.py`.
