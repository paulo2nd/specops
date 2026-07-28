# Quickstart: Validating the Contract Freeze

How to prove the freeze works end-to-end. Run under the `specops` conda env (per repo
tooling guidance); the CLI is never run against this repo (No Self-Application) — tests use
fixtures and golden captures.

## Prerequisites

- Dev install: `pip install -e '.[dev]'`
- Tools: `conda run -n specops pytest`, `... ruff check`, `... mypy` (base env has a numpy stub that aborts mypy).

## 1. Frozen shapes are locked (FR-004/005/006, SC-002)

```bash
conda run -n specops pytest tests/unit/test_frozen_config.py \
  tests/unit/test_frozen_ledger.py tests/unit/test_frozen_lane.py \
  tests/unit/test_frozen_gateprofiles.py tests/unit/test_frozen_ingestion.py \
  tests/unit/test_frozen_envelope.py tests/unit/test_outcome_contract.py -q
```
**Expected**: all pass. Each asserts the live schema (from `config.py`/`records.py`/`lane.py`/
`gateprofiles.py`/`ingestion.py`/`outcome.py`) matches the frozen field tables in
`data-model.md`, and that version baselines are pinned (`schema_version=7`, lane `=1`,
`contract_version=1`, gate `output_version=1`, envelope `output_version=1`).

## 2. A breaking change is caught (SC-003)

On a throwaway branch, make one breaking edit per surface and confirm a contract test fails
naming that surface. Examples:
- Remove a `FindingRecord` required key in `records.py` → `test_frozen_ledger` fails.
- Rename `outcome`→`status` in `outcome.render()` → `test_frozen_envelope` fails.
- Change `EXIT_ERROR = 2` → `3` in `outcome.py` → `test_outcome_contract` fails.
- Bump `INPUT_CONTRACT_VERSION` without schema update → `test_frozen_ingestion` fails.

**Expected**: each edit turns exactly the relevant test red with a message identifying the
surface. Revert after.

## 3. An additive change is allowed (FR-007, SC-004)

Add a new **optional** key to a surface (e.g. a new optional `TaskRecord` field, or a new
documented per-command envelope extension) → the frozen-shape tests still **pass** (no false
positive).

## 4. The envelope delta is additive and golden-clean (FR-009, SC-010)

```bash
conda run -n specops pytest tests/golden/ -q          # after re-recording affected captures
```
**Expected**: `consistency`/`reconcile`/`preflight` `--json` captures now include
`output_version: 1`; human captures are byte-identical; all other families unchanged.
Re-record once with `pytest tests/golden/ --golden-record` when intentionally adopting the
additive key, then review the diff (only `output_version` added).

## 5. The policy is published and linked (FR-001/011, SC-001/006)

- `docs/stability.md` exists, classifies all seven surfaces **FROZEN**, and records the FR-003
  sweep result.
- `README.md` (EN section) + `README.pt-br.md` (PT pointer) + `docs/commands.md` +
  `CHANGELOG.md` link it.

## 6. Governance is consistent (FR-014, SC-009)

- `.specify/memory/constitution.md` Principle VI documents exit `0`/`1`/`2`; version bumped;
  Sync Impact Report updated — landing in the same change set as `test_outcome_contract.py`.

## 7. Full gates

```bash
conda run -n specops ruff check . && conda run -n specops mypy && conda run -n specops pytest -q
```
**Expected**: green at repo thresholds. No schema bump; the only behavior delta is the additive
envelope `output_version`.

## Out of scope to validate here

- The 1.0.0-rc tag — gated on the release owner's real-usage judgment (FR-013); not asserted by
  any test in this feature.
