# Contract — Acknowledgement Record & Ledger v3 → v4

## Schema bump

- `ledger.CURRENT_SCHEMA`: **3 → 4**. `OLDEST_SUPPORTED` unchanged (1).
- New top-level list `acknowledgements: []` (default empty).

## Record shape

```yaml
acknowledgements:
  - path: src/specops/foo.py      # required, non-empty
    task: T012                    # required, must resolve to a known non-orphaned task
    reason: "needed to fix circular import discovered during T012"  # required, ≤200 chars
    map_digest: "sha256:…" | null # provenance only; never gates classification
    at: "2026-07-21T18:40:00+00:00"  # RFC3339 UTC; stored, not emitted by read commands
```

## Migration (v3 → v4, deterministic, pure)

`migrate_to_current` (extended): after the existing v→v3 steps, `data.setdefault("acknowledgements", [])`. A dedicated `backfill_acknowledgements(data)` mirrors `backfill_context_provenance` so a pre-v4 ledger gains `acknowledgements: []` rather than an omitted key. Idempotent. Read-compat: pre-v4 ledgers load and trace without error (FR-016); absent list ⇒ zero acknowledgements ⇒ discovered paths are `unexplained` until acknowledged.

## Invariants (`validate_invariants` extension)

Each acknowledgement record MUST be a mapping with non-empty `path`, `task`, `reason`, and its `task` MUST match a known non-orphaned task id; otherwise a violation string (fails closed on write, per `_finalize`, only when newly introduced). Absent list is valid (pre-v4 shape).

## Write path (`trace.cmd_acknowledge`)

Reuses `status._load_for_write` (schema refusal for too-new/unsupported; workspace-identity gate; in-memory migrate + backup) and `status._finalize` (revision-CAS via `ledger.save`, atomic `atomic_write`, new-violation guard). Outcome/exit per [data-model.md §4](../data-model.md). Concurrent/stale writes raise `StaleLedgerError` (exit `2`) with no lost update.

## Rollback & security

- **Rollback**: the v3→v4 migration inherits the existing pre-migration backup (`ledger.backup_ledger` runs inside `status._load_for_write` before any migrate), so a defective upgrade is recoverable from `.specify/.specops-backup/…` — no new rollback mechanism needed.
- **Security**: `reason` is opaque human text bounded to ≤200 chars; it is never executed, never a path, and carries no secret. The acknowledgement cannot widen scope on its own — it only relabels an already-changed diff path from `unexplained` to `discovered-and-acknowledged`.

## Forward-migration test obligation (Global DoD)

`tests/integration/test_ledger_migration.py` gains a v3→v4 case: a v3 fixture migrates to v4 with `acknowledgements: []` backfilled, existing tasks/cycles/provenance byte-preserved, and remains readable — proving no data loss (SC-006/FR-016).
