# Contract: `specops status sync-tasks` (new, additive)

**Purpose**: explicit, deterministic recording of task-list mutations into the
ledger at the converge seam (FR-001/FR-002/FR-003). Reuses `_sync_tasks`
merge semantics verbatim — this command adds no merge logic of its own.

## Invocation

```
specops status sync-tasks [--check] [--json]
```

## Behavior

| Mode | Effect |
|---|---|
| (default) | Load ledger + `tasks.md` for the active feature; apply `_sync_tasks` (new IDs → `PENDING`, vanished IDs → `orphaned: true`, existing entries preserved by ID); save through the standard ledger write path (lock + revision check). Report appended / orphaned / unchanged counts. Zero-change runs succeed with "no changes". |
| `--check` | Validate the recording path **without writing**: active feature resolvable, ledger present and loadable, `tasks.md` readable. Report what would be appended/orphaned. This is the converge pre-mutation precondition (FR-003). |

## Exit codes (frozen 0/1/2 contract)

| Code | Meaning | Example diagnostics (specific, FR-003) |
|---|---|---|
| 0 | Recorded (or `--check` passed; zero-change included) | `sync-tasks: 3 appended, 0 orphaned` / `sync-tasks --check: ok (3 would append)` |
| 2 | Recording path unavailable / infrastructure error | `No ledger found for feature '…' — run 'specops status init-spec' first`; `Ledger parse error: …`; `tasks.md not found under '…'` |

No exit-1 outcome: sync-tasks records state, it gates nothing (record, do not
validate — FR-004). SC-coverage reporting is `specops consistency`'s job.

## Output

Human-readable lines by default; `--json` emits a stable additive object:

```json
{ "appended": ["T042"], "orphaned": [], "unchanged": 41, "check": false }
```

## Determinism (US1-4)

Pure function of (`tasks.md` task IDs, prior ledger `tasks[]`): same input →
identical ledger outcome; re-running is idempotent (no duplicates, completed
entries never disturbed).

## Freeze compliance

New subcommand — strictly additive. No existing command, flag, output, or
exit code changes shape.
