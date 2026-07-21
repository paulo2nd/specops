# Contract: Plan Topology Declaration & Validation

Defines the plan-side declaration surface and the `context plan-check` validation rules
(FR-002/003/004; SC-004). Reuses the existing plan-parsing conventions in `speckit.py`.

## Declaration surface (in `plan.md`)

Two declarations, both authored in `plan.md` and machine-parsed:

1. **Declared context IDs** — a SpecOps-owned line parsed by the new
   `speckit.parse_plan_context_ids(plan_text) -> list[str]`. Recognized form (single canonical form,
   case-insensitive label):

   ```markdown
   **SpecOps-Contexts**: api, api-auth, config
   ```

   Each ID must satisfy Feature 008's ID regex `^[A-Za-z0-9][A-Za-z0-9._/-]*$`. Duplicates are
   de-duplicated. Absent line while a map is present → `missing_declaration`.

2. **Declared paths** — the existing convention parsed by `speckit.parse_plan_path_action`
   (`speckit.py:105-123`), e.g. `` `src/api/handler.py` (modify) ``. Only the path is used here (to
   find its owning context); the action suffix is validated separately by `specops consistency`.

## Validation rules (`context plan-check`)

Given the parsed declaration + the map:

| # | Rule | Outcome |
|---|---|---|
| 1 | Map absent | `no_map_present`, exit `0`, no requirement imposed (FR-013). |
| 2 | Map present, `context_ids` empty | `missing_declaration`, exit `1` (FR-002). |
| 3 | A declared ID not in the map | `unknown_declared_context`, exit `1`, names the ID (FR-003). |
| 4 | A declared path owned by a context **not** in `context_ids` | `undeclared_owner`, exit `1`, names the path + owning context (FR-004). |
| 5 | A declared path owned by **no** context | recorded in `unowned_paths`, **non-blocking** (still exit `0` unless another rule fails) (FR-004). |
| 6 | Map unresolvable (malformed/schema-invalid/unsupported/ambiguous) | fail closed, exit `1`, defer to `context validate` (FR-017). |
| 7 | All declared IDs exist and every owned declared path is covered | `plan_check_ok`, exit `0`; display the minimal phase-scoped read set for the declared contexts (FR-001). |

**Existence-agnostic (FR-011)**: rules 3–7 never touch the filesystem. A declared path that currently
matches zero files (a create-target) is *not* an error here; filesystem existence is solely the
`context stale` command's concern, and only over the **map's** patterns — never over plan create-targets.

## Success-criteria mapping

| SC | How this contract satisfies it |
|---|---|
| SC-004 | Rules 2/3/4 make missing-declaration, unknown-ID, and undeclared-owner blocking (exit `1`) when a map is present; rule 1 blocks nothing when no map exists. |
| SC-001 | The displayed read set + reason trace are the deterministic Feature 008 resolution (byte-stable). |
| SC-007 | The command is read-only (no ledger/repo mutation). |

## Determinism & output

- `--json` envelope: `command`, `outcome`, `class`, `status`, `output_version: 1`,
  `extra={declared_context_ids, unowned_paths, read_set}`.
- Lists codepoint-ordered; no timestamps.
