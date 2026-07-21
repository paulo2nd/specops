# Contract: Impact Report (reverse edges, closed edge set, bounded expansion)

Defines the JSON shape and semantics of `context impact` (FR-006/007/008; SC-002/003). Ordering is
Unicode-codepoint; no timestamps; `output_version: 1`.

## Edge model

Impact answers **"which contexts are affected by this change"** — the **reverse** of Feature 008
forward resolution. `X depends on Y` (declared in `Y`'s... no — declared in `X.dependencies`) means a
change to **Y** affects **X**. The reverse-adjacency index is built from every context's
`dependencies` list (`contextmap.py:93`) and walked cycle-safe (see [data-model.md](./data-model.md)).

Every context in the output is attributed to **exactly one** member of the **closed set**:

| `via` | Meaning | Realizable today? |
|---|---|---|
| `ownership` | Context directly owns a changed path (a `match` hit). | Yes |
| `dependency` | Reached by a declared reverse dependency edge. | Yes |
| `policy` | Reached by a declared gate/policy edge. | **Enforced but empty** — Feature 008 models `gates` as per-context ID lists, not cross-context edges (R2). No `policy` edge pulls another context into scope until a future schema field exists. |

No `via` value outside this set may appear, and no context may appear without a `via` (SC-002).

## JSON shape (`--json`, under `extra.impact`)

```json
{
  "command": "context impact",
  "outcome": "ok",
  "class": "pass",
  "status": "impact_ok",
  "output_version": 1,
  "impact": {
    "changed_paths": ["src/api/handler.py"],
    "unowned_paths": [],
    "affected": [
      {
        "context_id": "api",
        "via": "ownership",
        "reason": "owns src/api/handler.py",
        "gates": ["contract-tests"],
        "risk": {"tier": "high"}
      },
      {
        "context_id": "web",
        "via": "dependency",
        "reason": "dependency: web -> api",
        "gates": [],
        "risk": {}
      }
    ],
    "bounded": true
  }
}
```

## Rules

1. **Direct ownership first** — each changed path resolves to at most one owner via
   `_candidates_for_path` (most-specific-wins). Zero candidates → the path is added to
   `unowned_paths` (non-blocking, FR-004), never fabricated into an owner.
2. **Reverse transitive expansion** — from each owner, walk reverse edges to collect dependents; a
   context already present as `ownership` is not downgraded to `dependency`.
3. **Cycle-safe** — each context visited at most once (`seen` guard); a dependency cycle terminates
   and every visited context still carries a `via` (matches Feature 008 cycle handling).
4. **Bounded by construction** — expansion only follows the closed edge set; `bounded` is `true` in
   every success. It is `false` only alongside the blocking `unbounded_expansion` status, emitted when
   an owner is a catch-all/near-root pattern that would drag in effectively the whole map, or a
   whole-map closure is requested (R3). In that case the command exits `1` and names the offending
   path/pattern instead of reading the repository wide (SC-003).
5. **Metadata surfacing** — `gates` (`Context.gates`) and `risk` (`Context.risk`) are surfaced for
   each in-scope context; surfacing metadata never itself adds a context to scope (that requires an
   edge).
6. **Determinism** — `affected` codepoint-ordered by `context_id`; `changed_paths`/`unowned_paths`
   codepoint-ordered and deduped; identical inputs → identical bytes (SC-001).
7. **Empty & degenerate** — empty explicit set or clean-tree/empty diff → `affected: []`,
   `impact_ok`, exit `0`. Cannot derive from Git → `usage_error`, exit `2` (see
   [context-consume-cli.md](./context-consume-cli.md)).
