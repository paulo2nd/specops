# Contract: `specops status migrate`

New subcommand under the `status` Typer group (`src/specops/cli.py`), backed by
`status.cmd_migrate` → `ledger.migrate_to_current` + `ledger.save`. Provides an explicit, opt-in way
to migrate a feature ledger to the current schema (FR-008b). Auto-migration on first write covers the
implicit path; this command covers CI/pre-flight/deliberate migration.

## Synopsis

```text
specops status migrate
```

No arguments. Operates on the active feature (`.specify/feature.json`).

## Behavior

| Precondition | Outcome | stdout | Exit |
|---|---|---|---|
| Ledger absent | Refuse | — ("Ledger not found. Run 'specops status init-spec' first." on stderr) | 1 |
| Not a Git repo | Refuse | — (stderr message) | 1 |
| Classified `current` | No-op (does NOT rewrite the file; FR-008) | `status migrate: already current` | 0 |
| Classified `migratable` | Back up original (FR-008a), migrate, atomic write | `status migrate: migrated (v1 → v2)` | 0 |
| Classified `too_new` | Refuse, no write (FR-005) | — (stderr message) | 1 |
| Classified `unsupported` | Refuse, no write (FR-006) | — (stderr message) | 1 |
| Unparseable YAML | Refuse | — (stderr message) | 2 |

## Guarantees

- **Idempotent**: running `migrate` twice yields the same result; the second run reports
  `already current` and does not rewrite the ledger (FR-008, SC-005).
- **Lossless**: every phase, task, evidence entry, and review cycle is preserved (FR-004, SC-001).
- **Backed up**: on a real migration, the pre-migration ledger is retained under
  `.specify/.specops-backup/` and referenced by `recovery.migrated_from_backup` (FR-008a).
- **Atomic & interruption-safe**: the write goes through the same tmp→fsync→`os.replace` +
  revision-CAS path as every other state change (FR-022); an interruption leaves the original
  ledger intact.
- **Non-destructive on refusal**: too-new/unsupported/absent leave the ledger untouched.

## Wiring

```python
# cli.py — under status_app
@status_app.command("migrate")
@_handle_errors
def status_migrate() -> None:
    """Migrate the active feature's ledger to the current schema."""
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(status.cmd_migrate(root))
```

`cmd_migrate` reuses the same `ledger.load` / classify / `ledger.save` primitives as the auto-trigger
path, so explicit and implicit migration are guaranteed to produce identical results.
