# Contract: Versioning & Migration Policy (post-1.0 evolution)

Ships as a section of `docs/stability.md`. Defines what a maintainer OWES for each kind of
change after 1.0. This is the "how to evolve safely" half of the freeze (spec FR-008/FR-009/
FR-010, SC-005).

## Obligations by change kind

| Change | Obligation |
|---|---|
| Add optional field to a persisted format | None beyond a CHANGELOG note; consumers ignore unknown fields. |
| Breaking change to a **versioned** persisted format (`status.yaml`, `lane.yaml`, gate-profile file, findings-input) | Bump that surface's version field **and** provide a forward migration covered by a migration test (reuse `ledger.migrate_to_current` + `test_ledger_v7_migration.py` pattern for the ledger; equivalent load/validate migration for lane/gate/findings). |
| Breaking change to `specops.json` (versionless) | MAJOR release only; preserve-unknown means additive changes never break — a removal/retype is a MAJOR event with a CHANGELOG migration note. |
| Change the base JSON envelope shape | Increment `outcome.OUTPUT_VERSION`; document the new shape; old consumers detect via the field. Adding a **documented per-command** key does **not** bump it. |
| Change an exit code's meaning / add a code | MAJOR release; amend constitution Principle VI in the same change set (the precedent this feature sets with exit `2`). |
| Rename any user-facing surface (command, flag, key) | Feature 017 discipline: ship the **old name as a deprecated alias**, keep it for its window, remove **no earlier than the next MINOR** and **never in a patch**. |

## `output_version` semantics (envelope)

- **Identifies**: the shape of the base command-result JSON envelope (`command`, `outcome`,
  `class`, `output_version` + documented per-command extensions).
- **Increments when**: a base key is removed/renamed, a base value enum changes, or the
  meaning of an existing base key changes. It does **not** increment for a new documented
  per-command extension key (additive).
- **Initial value**: `1`. Single-sourced in `outcome.OUTPUT_VERSION`; every `--json` output
  carries it.

## Migration-test mechanism (single-sourced, not reinvented)

- Ledger: `ledger.classify()` → `migrate_to_current()` (`ledger.py:143/215`), proven by
  `tests/unit/test_ledger_v7_migration.py` (prior dict → MIGRATABLE → migrated schema ==
  CURRENT_SCHEMA → lossless → invariants clean → idempotent). Any future schema bump adds a
  `test_ledger_v<N>_migration.py` in the same shape.
- Lane / gate-profile / findings-input: their `load`/`validate`/`parse` reject an unknown
  version today; a future bump adds an analogous load-migration + test. The policy names this
  obligation; it does not pre-build the migrations.

## Acceptance (maps to spec)

- The policy states, for every persisted format, its bump-plus-migration obligation and points
  at the existing migration-test mechanism (SC-005, FR-008).
- Envelope `output_version` semantics and increment conditions are stated (FR-009, SC-005).
- The rename alias/deprecation-window discipline is stated with its exact terms (FR-010,
  CHK035).
