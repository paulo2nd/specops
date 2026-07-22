# Contract — `specops trace` CLI

Four subcommands under a new `trace` Typer group. Read commands are read-only (verified by before/after ledger+repo state comparison, SC-007). Every JSON payload carries `status` and `output_version: 1`. Exit taxonomy is the fixed `0/1/2` (Principle VI); see [data-model.md §8](../data-model.md).

## `specops trace classify [--path P]... [--json]`

Classify every effective-diff path.

- **Input**: optional repeatable `--path` (bypasses Git derivation); otherwise the effective diff `baseline..HEAD` (`--no-renames`).
- **Output (human)**: one line per path — `<class>  <path>  (<attribution>)` — sorted by codepoint, grouped by class.
- **Output (`--json`)**: `{command, outcome, class, status, output_version, paths:[{path,change,class,attribution}], counts:{planned,discovered_and_acknowledged,unexplained}}`.
- **Exit**: `0` always for classification itself (it is descriptive, not a gate); `2` on not-a-repo / unresolvable baseline / bad args. *(The blocking judgment is the `drift` gate / `trace validate`, not `classify`.)*

## `specops trace validate [--json]`

Fail closed on any trace defect **or** any unexplained effective-diff path (the acceptance-gate command).

- **Output (human)**: `trace: <kind> - <detail>` lines (empty on success).
- **Output (`--json`)**: `{…, status, output_version, defects:[{kind,detail,ref}], unexplained:[path...]}`.
- **Exit**: `0` complete + no unexplained; `1` any defect or unexplained path (`DRIFT_BLOCKED`/`TRACE_INCOMPLETE`); `2` usage.

## `specops trace report [--json]`

Render the full trace graph.

- **Output (human)**: per success criterion, its chain (tasks → contexts/paths → commits → evidence → findings/corrections), then a **Discoveries** section (each `discovered-and-acknowledged` path with reason + task).
- **Output (`--json`)**: the graph object + `output_version`.
- **Exit**: `0`; `2` usage. (Reporting never blocks.)

## `specops trace acknowledge <path> --task <id> --reason <text> [--json]`

Record a one-time path-level acknowledgement (the only state-changing command).

- **Preconditions**: resolvable feature ledger; passes workspace-identity gate (`status._load_for_write`); migrates v3→v4 in memory if needed.
- **Effect / Exit** (see [data-model.md §4](../data-model.md)): `ACK_RECORDED`/`ACK_IDEMPOTENT`/`ACK_ALREADY_PLANNED` → `0`; `ACK_CONFLICT`/`ACK_UNKNOWN_TASK` → `2`. Write is atomic + revision-CAS; concurrent/stale write fails closed (`StaleLedgerError`).
- **Output (`--json`)**: `{command:"trace acknowledge", outcome, class, status, output_version, path, task}`.

## Determinism & read-only guarantees

- Identical (ledger, map, diff, plan, acknowledgements) ⇒ byte-for-byte identical output for `classify`/`validate`/`report` (SC-001); codepoint ordering, canonical JSON, no timestamps emitted.
- `classify`/`validate`/`report` never write; `acknowledge` writes only the ledger through `ledger.save`.
