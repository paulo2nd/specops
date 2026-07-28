# SpecOps Stability Policy

**Status**: Frozen for 1.0 · **Applies from**: 1.0.0-rc

This document is the contract between SpecOps and the automation you build on it. It states,
for every surface an adopter can bind to, whether it is **frozen**, what an **additive
(non-breaking)** change looks like, and how any **breaking** change would be versioned and
announced. If a surface is not listed here, it is not part of the frozen contract.

Contract tests in `tests/unit/test_frozen_*.py` and `tests/unit/test_outcome_contract.py` lock
these shapes; a breaking change to any frozen surface fails the test suite.

## Frozen surfaces

All surfaces below are **FROZEN** at 1.0.

| Surface | What it is | Version field | Additive change | Breaking change |
|---|---|---|---|---|
| `specops.json` | project config | *(none; preserve-unknown)* | new optional key | remove/rename/retype an existing key |
| `status.yaml` | execution ledger (schema **v7**) | `schema_version` | new optional field/record | remove/rename/retype a required field |
| `lane.yaml` | lightweight-lane state (schema **v1**) | `schema_version` | new optional field | change a top-level/sub-shape or the `state` enum |
| `.specify/specops/gate-profiles.yaml` | gate-profile suite config | `output_version` (**1**) | new optional profile/`applies` key | change/rename a profile field or predicate key |
| JSON output envelope | every `--json` command result | `output_version` (**1**) | new documented per-command key | remove/rename a base key or change a value enum |
| exit codes | process exit status | *(the closed set {0,1,2})* | *(none — the set is closed)* | change a code's meaning or add a code |
| findings-input contract | external-review ingestion (**v1**) | `contract_version` | new optional finding field | change a required field or the version semantics |
| `.specify/specops/context-map.yaml` | context map (schema **v1**) | `schema_version` | new optional field | remove/rename/retype a required field |
| SARIF output (`--sarif`) | CI-consumable findings export | `version` (**2.1.0**) | new optional SARIF property | change the SARIF version or the level mapping |

**FR-003 sweep result (2026-07-28)**: the sweep over every observable CLI/persisted surface
found **two** adopter-facing surfaces beyond the roadmap's original seven — the context-map
file and the SARIF output — both now frozen above. No observable surface is left unclassified.

### The base JSON envelope

Every `specops … --json` output carries these four keys:

- `command` — the invoked command name
- `outcome` — one of `ok` · `blocked` · `error`
- `class` — one of `pass` · `gate-rejection` · `infra-error`
- `output_version` — the envelope version (**1**)

Commands may add **documented per-command** keys (e.g. `verdict`/`gates` on `preflight`,
`warnings` on `reconcile`, `package` on `context resolve`). Those extensions are additive and
do not change `output_version`. The per-command keys are documented in
[`docs/commands.md`](./commands.md) and the per-feature contract docs under `specs/*/contracts/`.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | blocking gate result / review `REJECTED` |
| `2` | infrastructure / data / usage error |

No command emits a code outside this set. The constitution's Principle VI documents all three.

### Field-level reference

The exact frozen field of every surface is enumerated in the feature's
[`data-model.md`](../specs/021-contract-freeze/data-model.md) and the shipped per-feature
contract docs: gate profiles (`specs/012-*/contracts/gate-profiles.config.md`), findings-input
(`specs/015-*/contracts/findings-input.schema.json`), CLI output
(`specs/018-*/contracts/cli-output.md`). This policy references those rather than duplicating
the field lists.

## Versioning & migration policy (post-1.0 evolution)

What a maintainer owes for each kind of change after 1.0:

| Change | Obligation |
|---|---|
| Add an optional field to a persisted format | CHANGELOG note only; consumers ignore unknown fields. |
| Breaking change to a **versioned** persisted format (`status.yaml`, `lane.yaml`, gate-profile file, findings-input, context-map) | Bump that surface's version field **and** ship a forward migration covered by a migration test (the ledger uses `ledger.migrate_to_current` + `tests/unit/test_ledger_v7_migration.py`; other formats add an equivalent load-migration + test). |
| Breaking change to `specops.json` (versionless) | MAJOR release only; unknown keys are always preserved, so additive changes never break — a removal/retype is a MAJOR event with a migration note. |
| Change the base JSON envelope shape | Increment `output_version`; document the new shape. Adding a documented per-command key does **not** bump it. |
| Change an exit code's meaning / add a code | MAJOR release; amend constitution Principle VI in the same change set. |
| Rename any user-facing surface (command, flag, key) | Ship the old name as a **deprecated alias**, keep it for its window, and remove it **no earlier than the next MINOR** and **never in a patch** (the Feature 017 discipline). |

### `output_version` semantics

- **Identifies** the shape of the base command-result envelope.
- **Increments** when a base key is removed/renamed, a base value enum changes, or the meaning
  of an existing base key changes. It does **not** increment for a new documented per-command key.
- **Initial value**: `1`, single-sourced in `outcome.OUTPUT_VERSION`; every `--json` output carries it.

## Not frozen

Internal module APIs, `src/specops/templates/` literals, test fixtures, log/prose wording, and
any surface a future sweep explicitly records as still-evolving are **not** part of this
contract and may change without a version bump.

## Release status

The 1.0.0-rc is cut once the milestone-based release strategy's **real-usage criterion** is
satisfied — a judgment made by the release owner, recorded in the release process. This policy
and its contract tests land independently of that tag; the freeze does not force the rc.
