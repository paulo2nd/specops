# Contract: gate report JSON (`specops gate report --json`, `specops review --json`)

Stable, `output_version`-stamped provenance of a verification verdict (FR-011/FR-012).
Composes the Feature 007 `outcome.py` envelope — the `review --json` object keeps its
`command`/`outcome`/`class`/`verdict` keys and enriches each gate.

## `specops review --json` (enriched)

```json
{
  "command": "review",
  "outcome": "blocked",
  "class": "gate-rejection",
  "verdict": "REJECTED",
  "output_version": 1,
  "gates": [
    { "name": "reconcile",   "status": "PASS", "disposition": null },
    { "name": "unit-tests",  "status": "PASS", "disposition": "cached",
      "reason": "always", "commit_range": "a1b2c3d..e4f5a6b",
      "affected_paths": ["src/x.py"], "evidence_id": "EV-9f2c1a7b3e04" },
    { "name": "schema-guard","status": "FAIL", "disposition": "failed",
      "reason": "matched path migrations/**", "commit_range": "a1b2c3d..e4f5a6b",
      "affected_paths": ["migrations/001.sql"], "evidence_id": "EV-1b77…" },
    { "name": "lint",        "status": "SKIPPED", "disposition": "skipped",
      "reason": "out-of-scope" }
  ]
}
```

## `specops gate report --json` (full provenance)

```json
{
  "command": "gate-report",
  "output_version": 1,
  "selection": [
    { "name": "unit-tests", "selected": true,  "reason": "always" },
    { "name": "schema-guard","selected": true, "reason": "matched path migrations/**" },
    { "name": "docs-check",  "selected": false, "reason": "out-of-scope" }
  ],
  "gates": [ /* per-gate objects as above, with disposition + evidence_id */ ],
  "evidence": [ /* StructuredEvidence records — see evidence-record.json.md */ ]
}
```

## Disposition values (FR-008)

`required | optional | skipped | cached | failed | unavailable`. Exactly one per
profile gate; `null` for the non-profile gates (`reconcile`, `working-tree`, `drift`).
`unavailable` (missing command/tool) is distinct from `failed`. Blocking mapping per
research R8 (a required `failed`/`unavailable` ⇒ `passed=false`; `optional` never
blocks).

## Guarantees

- `output_version` present on every object (versioned contract for Features 013–014).
- Byte-for-byte identical for identical recorded ledger + config + branch (FR-018).
- Gates ordered by declared order then name; `evidence[]` by producer/timestamp/
  commit_range (FR-021).
- Read-only (FR-015).
</content>
