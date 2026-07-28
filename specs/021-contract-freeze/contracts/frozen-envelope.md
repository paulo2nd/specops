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
- **Two independent version axes — not one global value.** `outcome.OUTPUT_VERSION` versions the
  *thin* base envelope (`command`/`outcome`/`class`) and is the default `render()` stamps for
  families that carry no richer payload (`consistency`, `reconcile`, error paths). Command
  families with a richer JSON payload (context/trace/handoff/gate/lane/doctor) carry their **own**
  `output_version` via `_emit`, and **FR-009/SC-010 retain those unchanged**. Each bumps on its
  own schedule (versioning policy). All are `1` at 1.0. So `render()` never overrides a
  caller-supplied version — a family's value is emitted verbatim; only the *absent* case is
  defaulted. (An earlier draft asserted a single "source of truth" and a divergence guard that
  forced the family constants to equal `outcome.OUTPUT_VERSION`; that contradicted SC-010's
  retain-per-report requirement and was removed — the honest contract is per-command independence
  with a guaranteed-present base default.)
- **Persisted-format versions stay separate**: the context-map `schema_version`, the ledger
  `schema_version`, and the gate-profile *file* `output_version` version persisted formats and
  are frozen independently (Entities 2, 4, 8).
- **Known pre-1.0 coupling (documented, not fixed here)**: `gateprofiles.OUTPUT_VERSION` is
  dual-purpose — it versions both the gate-profile *file* (Entity 4) and the `gate` command's
  `--json` output; `contextmap.OUTPUT_VERSION` versions both the context command output and the
  ledger context-provenance sub-record. These conflations pre-date Feature 021 and are left
  intact to keep the freeze behavior-preserving; if either persisted side needs an independent
  bump post-1.0, split it into a distinct constant then (a MINOR, additive change).

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
