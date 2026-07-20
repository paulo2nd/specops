# Contract: Ledger v2 Schema & Version Handling

Defines the on-disk contract of `specs/<feature>/status.yaml` at schema version 2, the version
classification rules, and the migration/backup guarantees. Owned by `src/specops/ledger.py`.

## Constants (src/specops/ledger.py)

```python
CURRENT_SCHEMA = 2
OLDEST_SUPPORTED = 1        # v1 == a ledger with no `schema_version` key
DEFAULT_WORKFLOW_LANE = "full"
```

## Serialization contract

- **Encoding**: UTF-8. **Format**: YAML via `yaml.dump(..., default_flow_style=False,
  allow_unicode=True)` with default `sort_keys=True` (deterministic key ordering).
- **Timestamps**: RFC 3339 / ISO 8601 UTC strings with explicit `+00:00` offset. Produced with
  `datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")`.
- **Stability (FR-011)**: Re-persisting a ledger whose logical content (all fields except
  `updated_at`) is unchanged MUST be a byte-for-byte no-op — no `updated_at` change, no `revision`
  change, no reordering.

## Version classification API

```python
def classify(data: dict) -> str:
    """Return one of: 'current' | 'migratable' | 'too_new' | 'unsupported'."""
```

| Input `schema_version` | Return |
|---|---|
| absent or `1` | `"migratable"` |
| `2` | `"current"` |
| integer `>= 3` | `"too_new"` |
| `< 1`, non-integer, or unrecognized | `"unsupported"` |

## Migration API

```python
def migrate_to_current(data: dict) -> dict:
    """Deterministically upgrade a migratable ledger to CURRENT_SCHEMA. Pure; no I/O.
    Idempotent when data is already current (returns an equivalent dict, no reordering)."""
```

- MUST preserve every phase, task, evidence entry, review cycle, and recovery record with identical
  meaning (FR-004).
- MUST back-fill: `schema_version`, `revision=1`, `workflow_lane`, `active_artifact`, zone-aware
  timestamps, and the enriched `recovery` fields.
- MUST NOT alter evidence representation (FR-030).

## Backup guarantee (FR-008a)

Before an older ledger is overwritten by an auto- or explicit migration, `ledger.py` MUST copy the
original bytes to a retained backup under `.specify/.specops-backup/` mirroring the ledger's
repo-relative path (reusing the `migration.BackupSet` convention), and record that path in
`recovery.migrated_from_backup`. The backup is retained (not discarded) so a defective migration can
be rolled back deterministically.

## Invariant validation API

```python
def validate_invariants(data: dict) -> list[str]:
    """Return a list of human-readable invariant-violation strings ([] when valid).
    A non-empty result MUST block a state change (fail closed, FR-025)."""
```

Enforces I-PHASE-1/2, I-TASK-1/2/3, I-REC-1, I-REV-1/2/3 (see data-model.md).

## Load / save API

```python
def load(feature_dir: Path) -> LedgerLoad:
    """Read raw ledger + captured base_revision + classification. Never mutates disk."""

def save(feature_dir: Path, data: dict, *, base_revision: int) -> None:
    """Concurrency-safe, atomic write:
      1. acquire short-lived status.yaml.lock (O_CREAT|O_EXCL);
      2. re-read on-disk `revision`; if != base_revision -> raise StaleLedgerError (no write);
      3. if logical content unchanged -> return without writing (stable no-op);
      4. else set revision = base_revision + 1, refresh updated_at, write via tmp->fsync->os.replace;
      5. release lock in finally."""
```

- `save` MUST be atomic and interruption-safe (FR-022/FR-023): an interrupted write leaves the
  previous complete, valid ledger readable.
- Stale detection MUST use `revision`, not timestamps (FR-016).

## Error mapping (reuses src/specops/errors.py)

| Condition | Exception | Exit code |
|---|---|---|
| Stale write (revision moved) | `StaleLedgerError(SpecopsError)` | 1 |
| Identity mismatch (feature/branch/baseline) | `SpecopsError` | 1 |
| Too-new schema (state change) | `SpecopsError` | 1 |
| Unsupported schema (state change) | `SpecopsError` | 1 |
| Invariant violation | `SpecopsError` | 1 |
| Unparseable YAML / invalid structure | `LedgerParseError` | 2 |

Read-only commands never raise these as hard failures for too-new/unsupported/malformed states;
they emit a best-effort report + diagnostic and exit non-destructively (FR-029a) — reserving
`LedgerParseError` (exit 2) only for genuinely unreadable YAML.
