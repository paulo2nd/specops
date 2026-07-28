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
- `render()` always emits `output_version: 1`.
- `_emit()` and the `preflight` path **stop** passing `output_version` explicitly (render owns
  it). The per-module `OUTPUT_VERSION` constants for the **CLI envelope** (trace/handoff/
  contextmap) are removed or made to reference `outcome.OUTPUT_VERSION`; a contract test
  asserts single-sourcing (no divergent constant).
- **Unchanged / separate**: `gateprofiles.OUTPUT_VERSION` (persisted **file** version) and
  `contextmap` provenance `output_version` (ledger state) remain their own fields.

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
