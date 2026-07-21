# Contract: `specops context` CLI

Four subcommands under a new `context` Typer sub-app (wired in `cli.py`, mirroring the existing
`status`/`extension` sub-apps). All are read-only except `init`. Exit codes and `status` follow
[data-model.md](../data-model.md) (R4). Every command accepts `--json` for the stable machine surface
(FR-015); human output is concise (FR-019).

## `context init`

Create the starter map when absent; idempotent (FR-003, SC-009).

| Aspect | Contract |
|---|---|
| Args | `--json` (optional) |
| Writes | `.specify/specops/context-map.yaml` **only if absent**, atomically (reuses `ledger.atomic_write`) |
| Absent → created | exit 0, `status: created`, reports the path written |
| Already exists | exit 0, `status: already_exists`, **no mutation** |
| No `.specify/` (not a Spec Kit repo) | exit 2, `status: usage_error` |

## `context validate`

Validate schema + all structural rules in one pass (R8). Exit per state table.

| Aspect | Contract |
|---|---|
| Args | `--json` |
| Absent map | exit 0, `status: no_map_present` |
| Valid (`valid`/`empty_valid`) | exit 0, reports context count + `schema_version` |
| Malformed / schema-invalid / ambiguous / unsupported-version | exit 1, `diagnostics: [{code, message, context_id?, field?}, …]` (ALL defects) |
| Defect `code`s | `invalid_path_pattern`, `unsafe_path_traversal`, `duplicate_context_id`, `ambiguous_ownership`, `dangling_dependency`, `dependency_cycle`, `unsupported_schema_version` |

## `context resolve`

Resolve a path or ID to a Resolved Context Package (FR-006, R10).

| Aspect | Contract |
|---|---|
| Args | exactly one of `--path <p>` \| `--id <id>`; optional `--phase <phase>`; `--json` |
| Both `--path` and `--id`, or neither | exit 2, `status: usage_error` |
| Absent map | exit 0, `status: no_map_present` |
| Invalid/ambiguous/malformed/bad-version map | exit 1 (fail-closed before any package), diagnostics |
| Path/ID matches exactly one context | exit 0, `status: resolved`, `package: {…}` (see resolved-package.md) |
| Path matches none / unknown `--id` | exit 0, `status: no_matching_context` |

## `context explain`

Same selectors as `resolve`; emits the Reason Trace (FR-010/FR-011, R7).

| Aspect | Contract |
|---|---|
| Args | exactly one of `--path`\|`--id`; optional `--phase`; `--json` |
| Resolvable | exit 0, `status: resolved`, `trace: {…}` (candidates, selected+deciding_dimension, read_set_source, dependency_edges, gates) |
| No match | exit 0, `status: no_matching_context` (trace lists the candidates considered = none) |
| Invalid map / usage error | exit 1 / exit 2 as per `resolve` |

## JSON envelope (all commands)

Extends `outcome.render` (`command`, `outcome`, `class`) with:

```json
{
  "command": "resolve",
  "outcome": "ok",
  "class": "pass",
  "status": "resolved",
  "output_version": 1,
  "package": { "...": "..." }
}
```

`output_version` starts at `1`; a breaking shape change bumps it (CHK031). Optional keys are omitted,
never `null` (matches existing `outcome.render` behavior).
