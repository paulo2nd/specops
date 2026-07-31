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
| (default) | Load ledger + `tasks.md` for the active feature; apply `_sync_tasks` (new IDs → `PENDING`, vanished IDs → `orphaned: true`, reappeared IDs **revived** — orphaned flag cleared, existing entries preserved by ID); save through the standard ledger write path (lock + revision check). Report appended / orphaned / revived / unchanged. Zero-change runs succeed with "no changes". A task entry without an `id` key fails cleanly (`LedgerParseError`, exit 2), never a traceback. |
| `--check` | Validate the recording path **without writing** — a pure dry-run that creates no backup even for a migratable ledger: active feature resolvable, ledger present and loadable, `tasks.md` readable. Report what would change. This is the converge pre-mutation precondition (FR-003). |

## Exit codes (frozen 0/1/2 contract — implemented mapping)

| Code | Meaning | Example diagnostics (specific, FR-003) |
|---|---|---|
| 0 | Recorded (or `--check` passed; zero-change included) | `sync-tasks: 3 appended, 0 orphaned` / `sync-tasks --check: ok — would record …` |
| 1 | Blocking precondition — recording path not ready (existing `SpecopsError` convention) | `Ledger not found: … Run 'specops status init-spec' first.`; `tasks.md not found in …` |
| 2 | Infrastructure / data error | `Cannot parse ledger …` (corrupt YAML / invalid structure) |

sync-tasks itself gates nothing on content (record, do not validate — FR-004):
exit 1 marks a missing precondition, never a judgment on the tasks. SC-coverage
reporting is `specops consistency`'s job. For the directive, ANY non-zero exit
of `--check` → stop-and-ask.

## Output

Human-readable lines by default; `--json` emits a stable additive object:

```json
{ "appended": ["T042"], "orphaned": [], "revived": [], "unchanged": 41, "check": false }
```

## Determinism (US1-4)

Pure function of (`tasks.md` task IDs, prior ledger `tasks[]`): same input →
identical ledger outcome; re-running is idempotent (no duplicates, completed
entries never disturbed).

## Freeze compliance

New subcommand — strictly additive. No existing command, flag, output, or
exit code changes shape.
