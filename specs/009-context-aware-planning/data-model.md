# Phase 1 — Data Model: Context-Aware Planning and Impact

This feature adds **no new persisted file**. It reuses Feature 008's `Context` model
(`contextmap.py:85-96`) and the Feature 006 ledger, adding: a **map digest**, three in-memory result
shapes (Plan-Check, Impact Report, Stale Report), and a **provenance record** persisted in the ledger
under a new schema version. All entities are stack-neutral (Principle V) and deterministic (R12).

## Entities

### Plan Context Declaration (input)

Parsed from `plan.md`; the input to `context plan-check`.

| Field | Type | Rules |
|---|---|---|
| `context_ids` | `list[str]` | From `speckit.parse_plan_context_ids`. Each must match Feature 008's ID regex `^[A-Za-z0-9][A-Za-z0-9._/-]*$` and exist in the map (FR-003). Empty while a map is present → `missing_declaration` (FR-002). |
| `declared_paths` | `list[(path, action)]` | From `speckit.parse_plan_path_action` (`create`/`modify`/`remove`). Used only to resolve each path's owning context; **existence-agnostic** (never stat'd) (FR-011). |

### Map Digest (new, greenfield — R1)

| Aspect | Definition |
|---|---|
| Function | `contextmap.map_digest(root) -> str \| None` |
| Value | `sha256` hex over the **canonical serialization** of the parsed contexts: each context reduced to fixed key order (`id`, sorted `match`, `reads` with sorted phase keys + codepoint-ordered path lists, sorted `dependencies`, sorted `gates`, `risk` sorted keys), JSON-encoded `sort_keys=True, ensure_ascii=False`, no whitespace. |
| Absent map | `None` → recorded as the no-map marker. |
| Invalid map | The consuming read command fails closed (FR-017); provenance records a `map_invalid` marker (R6). |
| Determinism | Independent of comment/whitespace/key-order in the source file; changes only when the map's *meaning* changes (SC-008). |

### Phase-Scoped Context Package (reused — FR-001)

The minimal ordered read set + reason trace for a phase, **as already produced** by
`contextmap.cmd_resolve(root, path=…|ctx_id=…, phase=<token>)` (`contextmap.py:659-687`). No new
shape. Phase tokens per R9: planning→`plan`, implementation→`implement`, review→`review`
(`specify`/`tasks` also valid); the closed list is `contextmap.PHASES` (`contextmap.py:39`).

### Impact Report (new — R2/R3)

Result of `context impact`. Emitted in `CommandResult.extra["impact"]`.

| Field | Type | Rules |
|---|---|---|
| `changed_paths` | `list[str]` | Explicit `--path` args, else `gitops.name_only_diff(repo, baseline, "HEAD")`. Codepoint-ordered, deduped. |
| `unowned_paths` | `list[str]` | Changed paths matching no context — non-blocking (FR-004). |
| `affected` | `list[AffectedContext]` | One per in-scope context, codepoint-ordered by `context_id`. |
| `bounded` | `bool` | `false` only accompanies the `unbounded_expansion` blocking status (R3). |

`AffectedContext`:

| Field | Type | Rules |
|---|---|---|
| `context_id` | `str` | The in-scope context. |
| `via` | `"ownership" \| "dependency" \| "policy"` | Exactly one closed-set edge type (FR-007). No other value is permissible. |
| `reason` | `str` | Human trace, e.g. `owns src/api/x.py` or `dependency: web -> api`. |
| `gates` | `list[str]` | `Context.gates` (surfaced metadata). |
| `risk` | `dict` | `Context.risk` (surfaced metadata). |

**Reverse-expansion algorithm** (cycle-safe, mirrors `_build_expanded` inverted):

```text
by_id        = {ctx.id: ctx for ctx in contexts}
dependents   = {}                     # reverse adjacency
for ctx in contexts:
    for dep in ctx.dependencies:      # ctx depends on dep
        dependents.setdefault(dep, []).append(ctx.id)   # dep -> [dependents]

affected = {}                         # context_id -> via
for path in changed_paths:
    owner = most_specific_candidate(path)         # _candidates_for_path
    if owner is None: unowned_paths.add(path); continue
    affected[owner.id] = "ownership"

# cycle-safe reverse DFS
seen = set()
for start in list(affected):                       # direct owners
    stack = [start]
    while stack:
        cid = stack.pop()
        if cid in seen: continue                    # cycle guard
        seen.add(cid)
        for dependent in sorted(dependents.get(cid, [])):   # codepoint order
            if dependent not in affected:
                affected[dependent] = "dependency"
            stack.append(dependent)
# policy edges: none in current schema (R2) — enforced-empty
# unbounded guard: if any owner is a catch-all near-root pattern -> unbounded_expansion (R3)
```

### Context Provenance Record (new — R5/R6, persisted)

Stored as `context_provenance` on every task record and every review-cycle record (Ledger v3).

| Variant | Shape | When |
|---|---|---|
| No map | `{"map": "none"}` | No `.specify/specops/context-map.yaml` present. |
| Invalid map | `{"map": "invalid"}` | Map present but unresolvable at close time (does not block the op). |
| Present | `{"map": "present", "digest": "<sha256>", "context_ids": ["…"], "output_version": 1}` | Resolvable map; `context_ids` = the contexts that directly **own** the record's effective changed paths (not the reverse-dependent expansion), codepoint-ordered. |

Backfill: `migrate_to_current` writes `{"map": "none"}` onto records migrated from v1/v2 (FR-018).

### Stale Reference (new — R8)

Result element of `context stale`, in `CommandResult.extra["stale"]`.

| Field | Type | Rules |
|---|---|---|
| `context_id` | `str` | Owning context of the stale pattern. |
| `pattern` | `str` | A `match` pattern matching **zero Git-tracked files**. |

Ordering: codepoint by `(context_id, pattern)`. Empty list → `stale_ok` (exit `0`). Non-empty →
`stale_found`. Symlinks matched by their own path entry, never followed.

## Status → class → exit mapping (additions)

Extends `contextmap._CLASS_FOR_STATUS` (`contextmap.py:64-77`); classes/exits from `outcome.py`.

| New `status` | Class | Exit | Meaning |
|---|---|---|---|
| `plan_check_ok` | PASS | 0 | Declared topology valid (may include non-blocking `unowned_paths`). |
| `missing_declaration` | GATE_REJECTION | 1 | Map present, plan declares no context IDs (FR-002). |
| `unknown_declared_context` | GATE_REJECTION | 1 | A declared ID is absent from the map (FR-003). |
| `undeclared_owner` | GATE_REJECTION | 1 | A declared path is owned by an undeclared context (FR-004). |
| `impact_ok` | PASS | 0 | Impact computed (incl. empty diff / clean tree). |
| `unbounded_expansion` | GATE_REJECTION | 1 | Expansion would leave the closed edge set (R3). |
| `stale_ok` | PASS | 0 | No stale references. |
| `stale_found` | GATE_REJECTION | 1 | One or more stale references reported. |
| `usage_error` | INFRA_ERROR | 2 | Bad selectors, or `impact` cannot derive from Git (no repo / no baseline) (R7). |

Reused fail-closed map states (FR-017): `malformed`, `schema_invalid`, `unsupported_version`,
`ambiguous_ownership` → GATE_REJECTION (1). `no_map_present` → PASS (0) for every command (FR-013);
for `plan-check` it additionally suppresses the declaration requirement.

> **Note on `stale_found` / `undeclared_owner` as exit 1**: these are *blocking* in the sense that the
> command signals a problem the maintainer must address, consistent with Principle VI gates. They are
> distinct from FR-005's "discovered file" (non-blocking) and from digest-drift (non-blocking warning,
> emitted by the review directive, not by these commands).

## Determinism inputs (R12)

- Canonical serialization for the digest; Unicode-codepoint ordering for every list.
- No timestamps in any command output; `output_version: 1` on JSON envelopes (`contextmap.OUTPUT_VERSION`).
- `impact`/`stale` depend only on the parsed map + the Git tracked/diff set at the pinned commit range.
