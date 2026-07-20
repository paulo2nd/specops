# Quickstart: Validating Ledger v2 Integrity

Runnable validation scenarios that prove the feature end-to-end. Per the constitution, SpecOps is
**not** self-applied to this repository — all scenarios run against **pytest fixtures** (synthetic
ledgers in temp Git repos), never by running `specops` against this repo.

## Prerequisites

```bash
pip install -e ".[dev]"      # editable install with test extras
```

Fixtures used (from `tests/conftest.py`): `tmp_git_repo`, `read_ledger`, and new v1/v2 ledger
factories added under `tests/`.

## Run the whole suite + gates

```bash
ruff check .
mypy src
pytest            # includes --cov-fail-under=85
```

Expected: ruff clean, mypy clean, all tests pass, coverage ≥ 85%.

## Scenario 1 — Lossless v1 → v2 migration (US1, SC-001)

**Given** a synthetic v1 ledger (no `schema_version`, date-only timestamps, one DONE task with
evidence, one review cycle) in a temp repo,
**when** a state-changing command runs (or `specops status migrate`),
**then** the ledger gains `schema_version: 2`, a `revision`, zone-aware timestamps, and every task,
evidence entry, and review cycle is preserved.

```bash
pytest tests/integration/test_ledger_migration.py -k lossless -q
```

Verify: `read_ledger(feature_dir)["schema_version"] == 2`; task/evidence/review data equal to the
v1 input; `recovery["migrated_from_backup"]` points at a file that exists under
`.specify/.specops-backup/`.

## Scenario 2 — Read-only never migrates (FR-007, SC-006)

**Given** the same v1 ledger, **when** `specops status show` / `specops reconcile` run, **then** the
on-disk bytes are unchanged.

```bash
pytest tests/unit/test_reconcile.py -k readonly_no_mutation -q
pytest tests/unit/test_status.py    -k show_no_mutation     -q
```

Verify: file mtime/bytes identical before and after; output still renders a summary.

## Scenario 3 — Too-new refusal (FR-005) & unsupported refusal (FR-006)

**Given** a ledger with `schema_version: 99` (too-new) and another with `schema_version: 0`
(unsupported), **when** a state change is attempted, **then** it is refused (exit 1) and the ledger
is unmodified; **when** read-only inspection runs, it still reports a diagnostic (FR-029a).

```bash
pytest tests/unit/test_ledger.py -k "too_new or unsupported" -q
```

## Scenario 4 — Lost-update protection (US2, SC-002)

**Given** two loads at the same `revision`, **when** the first save commits and the second saves
against its stale `base_revision`, **then** the second raises `StaleLedgerError` (exit 1) and the
first change survives; a re-read + retry succeeds.

```bash
pytest tests/integration/test_ledger.py -k "stale_write or concurrent" -q
```

Verify: at most one writer wins; `revision` advanced by exactly 1; no interleaved data.

## Scenario 5 — Workspace identity gate (US3, SC-003)

**Given** a valid v2 ledger, **when** a state change runs after (a) switching branch, (b) renaming
the feature dir, or (c) making the baseline commit unreachable (reset/rewrite), **then** each is
refused (exit 1) with a message naming the diverged dimension; the ledger is unmodified. A consistent
workspace passes.

```bash
pytest tests/integration/test_ledger.py -k identity -q
```

## Scenario 6 — Interruption safety + recovery metadata (US4, SC-004)

**Given** a state change interrupted between the `.tmp` write and `os.replace` (simulated), **when**
the ledger is read, **then** it is the complete previous committed state (no truncation); recovery
metadata (`last_consistent_revision`/`last_consistent_at`) identifies that state.

```bash
pytest tests/integration/test_ledger.py -k interrupt -q
```

## Scenario 7 — Stable no-op save (FR-011, SC-005)

**Given** a v2 ledger, **when** an operation that changes nothing logical is re-run, **then** the
file is byte-identical (no `updated_at`/`revision` churn).

```bash
pytest tests/unit/test_ledger.py -k stable_noop -q
```

## Scenario 8 — Timezone-aware timestamps (SC-007)

**Given** a migrated ledger, **then** every timestamp is timezone-aware RFC3339 (`+00:00`), and a
pre-existing naive value maps to the same instant interpreted as UTC.

```bash
pytest tests/unit/test_ledger.py -k timestamp -q
```

## Success signal

All scenarios pass and the three quality gates (ruff, mypy, pytest ≥85%) are green. Cross-reference:
[data-model.md](./data-model.md), [contracts/ledger-schema.md](./contracts/ledger-schema.md),
[contracts/state-change-preconditions.md](./contracts/state-change-preconditions.md),
[contracts/cli-status-migrate.md](./contracts/cli-status-migrate.md).
