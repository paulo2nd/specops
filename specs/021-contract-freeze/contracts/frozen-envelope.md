# Contract: Base Envelope `output_version` (the one code delta)

The single sanctioned code change (FR-009/FR-012). Before/after of the base `--json` envelope.

## Before (today)

`outcome.render()` (`outcome.py:85-89`) emits exactly:
```json
{ "command": "<name>", "outcome": "ok|blocked|error", "class": "pass|gate-rejection|infra-error" }
```
`output_version` is present **only** for the context/trace/handoff/gate families, injected by
the CLI `_emit()` path (`cli.py:597-602`) from each module's `OUTPUT_VERSION`. It is **absent**
from `consistency` (`cli.py:234`), `reconcile` (`cli.py:201`); the `preflight`/`review` path
(`cli.py:301-306`) passes it but not `status`. → inconsistent across families.

## After (this feature)

```python
# outcome.py
OUTPUT_VERSION = 1

def render(command, cls, **extra):
    obj = {
        "command": command,
        "outcome": status_for(cls),
        "class": cls,
        "output_version": OUTPUT_VERSION,   # NEW — always present
    }
    ...
```
- `render()` now guarantees `output_version` via `obj.setdefault("output_version", OUTPUT_VERSION)`:
  callers that already pass it (the `_emit` report families, `preflight`, `doctor`) keep it in
  place **byte-for-byte**; callers that do not (`consistency`, `reconcile`) get it appended.
  This is why only those two families' `--json` captures change.
- **Single-sourcing (realized as a divergence guard)**: `outcome.OUTPUT_VERSION` is the one
  authoritative envelope-version value. The report modules keep their own `OUTPUT_VERSION`
  constants (they import `outcome` *after* defining the constant, and `gateprofiles.OUTPUT_VERSION`
  is dual-purpose — it also versions the on-disk profile file), so rather than physically
  re-pointing them (risky, cosmetic), a contract test (`test_outcome_contract.py`) asserts each
  equals `outcome.OUTPUT_VERSION`, failing on any future drift. Same guarantee, zero churn,
  byte-identical output.
- **Unchanged / separate**: `gateprofiles.OUTPUT_VERSION` (persisted **file** version) and
  `contextmap` provenance `output_version` (ledger state) remain their own fields; the guard
  test treats the gate-profile *file* version as a persisted-format version (Entity 4), which
  currently equals the envelope version but is conceptually independent.

## Behavior delta (sanctioned, additive)

- `consistency`, `reconcile`, `preflight` `--json` **gain** `output_version: 1` (new key).
- Report families keep `output_version: 1` (now single-sourced).
- **Golden captures** for the affected families are **re-recorded** (`--golden-record`).
- The change is additive (a new optional key); the frozen-shape tolerance test (FR-007) must
  pass on it.

## Contract-test assertions

- Every `--json` output includes `output_version` and it equals `1` (`test_frozen_envelope.py`).
- Base envelope key set is exactly `{command, outcome, class, output_version}` + documented
  extensions; a removed/renamed base key fails (FR-004, SC-003).
- No divergent envelope-version constant exists (single-source check, extends
  `test_outcome_contract.py`).
- Human (non-`--json`) output is unchanged (golden human captures byte-identical).
