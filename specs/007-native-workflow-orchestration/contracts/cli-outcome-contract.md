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
- `1` vs `2` already exist (`SpecopsError=1`, `LedgerParseError=2`, `StaleLedgerError=1`). This
  contract documents them and forbids drift.
- A review `REJECTED` (exit `1`) and a reconcile divergence (exit `1`) are disambiguated by **which
  step ran** and by the JSON `class`/`diverged_dimension` — the workflow never infers class from the
  bare number.
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

`specops reconcile --json`
```json
{ "command": "reconcile", "outcome": "blocked", "class": "infra-error",
  "diverged_dimension": "baseline", "remedy": "specops status rebaseline" }
```

`specops consistency --json`
```json
{ "command": "consistency", "outcome": "ok", "class": "pass" }
```

## Guarantees

- **G1**: `outcome`/`class`/`exit_code` are consistent (`ok`↔0, `blocked`↔1, `error`↔2).
- **G2**: `review.verdict` is present iff `command == "review"`; `REJECTED` ⇔ exit 1 with
  `class = gate-rejection`.
- **G3**: `reconcile.diverged_dimension` is present iff a divergence was found; `remedy` is always
  `specops status rebaseline` (no new command — FR-012).
- **G4**: JSON is emitted to stdout only; human-readable text is unchanged when `--json` is absent
  (backward compatibility).
- **G5**: Read-only invocations never mutate the ledger or repo (SC-007; Principle II).

## Tested by

`tests/unit/test_outcome_contract.py` (shape + exit-code/class consistency), plus assertions in
`test_review.py`, `test_reconcile.py`, `test_consistency.py`.
