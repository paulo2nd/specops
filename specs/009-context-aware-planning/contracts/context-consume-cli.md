# Contract: Context-Consumption CLI

Three new **read-only** subcommands under the existing `context` Typer group
(`cli.py:77-82`, `context_app`). Every command returns a `contextmap.CommandResult` rendered by the
existing `_emit_context` bridge (`cli.py:450-461`): `--json` emits
`outcome.render(command, cls, status=…, output_version=contextmap.OUTPUT_VERSION, **extra)`; human
mode prints `human` to stderr when the class is not PASS; then `raise typer.Exit(exit_code)`.

All three are read-only (FR-012): they MUST NOT write the ledger, the map, or any repository file.

## `specops context plan-check`

| Aspect | Contract |
|---|---|
| Purpose | Validate the plan's declared context topology against the map (FR-002/003/004). |
| Args | `--plan PATH` (default `plan.md` of the active feature dir), `--phase TOKEN` (optional; default `plan`), `--json` |
| Reads | `plan.md` (declared context IDs + declared paths), the map. Never the filesystem for path existence (existence-agnostic). |
| Writes | nothing |
| Success `0` | `plan_check_ok` — declared IDs all exist and every declared path is owned by a declared context (or is `unowned`, reported non-blocking); also `no_map_present` (no requirement imposed). |
| Blocking `1` | `missing_declaration` (map present, no IDs declared) · `unknown_declared_context` · `undeclared_owner` · `malformed`/`schema_invalid`/`unsupported_version`/`ambiguous_ownership` (defer to `context validate`) |
| Usage `2` | bad `--phase` (not in `PHASES`), unreadable plan |
| `extra` | `{"declared_context_ids": [...], "unowned_paths": [...], "read_set": {...package...}}` — the resolved minimal phase read set is displayed for the declared contexts. |

## `specops context impact`

| Aspect | Contract |
|---|---|
| Purpose | Report contexts affected by a change, expanded over reverse dependency edges (FR-006). |
| Args | `--path PATH` (repeatable; explicit change set), `--json`. When no `--path` is given, derive the change set from Git. **No `--phase`**: impact is phase-independent (a property of the dependency graph); phase-scoped reads come from `context resolve`/`plan-check`. |
| Reads | the map; Git (`gitops.name_only_diff(repo, baseline, "HEAD")`, `gitops.is_git_repo`, ledger `baseline`) only when deriving. |
| Writes | nothing |
| Success `0` | `impact_ok` — including an **empty** result from a clean tree / empty diff / empty explicit set. |
| Blocking `1` | `unbounded_expansion` (would leave the closed edge set) · invalid/ambiguous/unsupported map (defer to `validate`) |
| Usage `2` | cannot derive the change set from Git (not a Git repo, or no resolvable baseline) |
| `extra` | `{"impact": {changed_paths, unowned_paths, affected:[{context_id, via, reason, gates, risk}], bounded}}` (see [impact-report.md](./impact-report.md)) |

## `specops context stale`

| Aspect | Contract |
|---|---|
| Purpose | Report context-map `match` patterns matching zero Git-tracked files (FR-011). |
| Args | `--json` |
| Reads | the map; Git-tracked file list (`repo.git.ls_files()`). |
| Writes | nothing (never edits the map) |
| Success `0` | `stale_ok` — every pattern still matches ≥1 tracked file; also `no_map_present`. |
| Blocking `1` | `stale_found` (≥1 stale reference) · invalid/ambiguous/unsupported map (defer to `validate`) |
| Usage `2` | not a Git repository |
| `extra` | `{"stale": [{"context_id": "...", "pattern": "..."}]}` codepoint-ordered |

## Cross-command guarantees

- **Determinism (SC-001)**: identical map + inputs (+ pinned Git state) → byte-for-byte identical
  output including reason traces (R12).
- **Read-only (SC-007)**: verified by before/after repository + ledger state comparison in tests.
- **Fail-closed (FR-017)**: on any unresolvable map state, exit `1` with a status that points the user
  to `context validate`; no partial/unreliable impact or read set is emitted.
- **No-map (FR-013)**: `no_map_present` is a supported exit-`0` state for all three commands.
- **JSON envelope (FR-014)**: always carries `command`, `outcome`, `class`, `status`,
  `output_version: 1`, plus the command-specific `extra` keys (guaranteed present, `[]`/`{}` when empty).
