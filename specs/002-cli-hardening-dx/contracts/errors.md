# Errors Contract — SpecopsError hierarchy ↔ exit codes

**Feature**: `specs/002-cli-hardening-dx` | **Date**: 2026-07-05

## Hierarchy

```
SpecopsError(Exception)          # message: str, exit_code: int = 1
├── LedgerParseError             # exit_code = 2
├── ConfigError                  # existing class re-parented (exit_code = 1)
└── ManifestResolutionError      # existing class re-parented (exit_code = 1)
```

- `message` is the exact user-facing text (no prefix added by the raiser).
- `exit_code` is a class attribute; instances may not override it arbitrarily —
  the vocabulary of exits stays {1, 2}.

## Raising rules (business modules)

`src/specops/status.py`, `src/specops/reconcile.py`,
`src/specops/consistency.py`, `src/specops/speckit.py`, `src/specops/config.py`:

- MUST raise `SpecopsError` (or subclass) for every failure currently exiting
  1 or 2 — same message text.
- MUST NOT import `typer`, call `sys.exit`, or print to stdout/stderr.
- Success output is **returned** (rendered text or result data), not printed.
- `reconcile`/`consistency` return `(warnings: list[str], violations:
  list[str])`; a non-empty violations list is mapped to exit 1 by the CLI
  layer after printing (violations → stderr, warnings → stdout), preserving
  today's output streams.

Out of scope: `initializer.py` keeps direct Typer usage (interactive confirm)
— it is the CLI-adjacent layer for `specops init`.

## Mapping rule (CLI boundary — the only mapper)

`src/specops/cli.py` wraps every command body:

```
try:    <business call>; echo returned output; exit 0
except SpecopsError as e:  echo e.message → stderr; raise typer.Exit(e.exit_code)
```

- Exactly one implementation of this wrapper (decorator or helper), used by
  all commands.
- The legacy `exit_ok`/`exit_fail`/`exit_error` helpers are removed.

## Compatibility guarantees

- Every (message, exit code, stream) triple observable today remains
  byte-identical (FR-010 / SC-006).
- Unit tests assert `pytest.raises(SpecopsError)` and message content;
  integration tests assert process-level exit codes through the Typer runner.
