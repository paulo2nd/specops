# Contract: StructuredEvidence record (ledger `evidence[]`, v6)

Immutable, versioned, id-addressable. Written only through the CLI, atomically
(FR-006). Id derived from the cache key (FR-009, R4).

## Shape

```json
{
  "id": "EV-9f2c1a7b3e04",
  "producer": "gate:unit-tests@0.3.0",
  "command": "pytest -q",
  "exit_code": 0,
  "timestamp": "2026-07-23T14:05:11+00:00",
  "commit_range": "a1b2c3d..e4f5a6b",
  "affected_paths": ["src/x.py", "tests/test_x.py"],
  "summary": "TEST_REPORT: 643 passed",
  "artifact_digest": "sha256:6b86b273ff34…",
  "superseded_by": null
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | `EV-<hex12>` | `sha256(canonical_json(cache_key))[:12]`; unique; deterministic. |
| `producer` | string | `gate:<name>@<cli-version>` or `auto`. |
| `command` | string | Exact command (or `(migrated)` for a back-filled record). |
| `exit_code` | int | Process exit; timeout ⇒ synthetic non-zero, `summary` notes `timeout`. |
| `timestamp` | string | ISO-8601, zone-aware (Feature 006 `to_aware`). |
| `commit_range` | string | `baseline..HEAD` or single sha. |
| `affected_paths` | [string] | Sorted; `[]` when unknown (e.g. migrated), reported explicitly. |
| `summary` | string | Concise human summary. |
| `artifact_digest` | string? | `sha256:<hex>` of a local artifact; **omitted** when none (never remote). |
| `superseded_by` | string\|null | Newer `EV-id` that replaced this on a cache-key change; else null. |

## Cache key (identity + reuse)

```json
cache_key = {
  "producer": "...", "command": "...",
  "commit_range": "...", "affected_paths": [sorted],
  "context_map_digest": "<contextmap.map_digest or null>"
}
```

- **`cached`** iff a non-superseded record with the same `id` exists (all key fields
  matched) → command not re-run (FR-009).
- Any key field differs ⇒ different `id` ⇒ fresh run ⇒ new record appended; the prior
  record's `superseded_by` is set. Volatile fields (`timestamp`, `exit_code`,
  `summary`, `artifact_digest`) are **excluded** from the key/id.

## Migration (v5 → v6, zero-loss — FR-007)

Each legacy task `evidence` string `<CLASS>:<summary>[; …]` (classes `CLI_LOG |
TEST_REPORT | SCREENSHOT_PATH | CODE_DIFF`) → structured record(s) with
`producer="auto"`, `command="(migrated)"`, `exit_code=0`, `timestamp = completed_at ||
updated_at`, `commit_range` from `task.commits`, `affected_paths=[]`, `summary` = the
original `CLASS:summary`. The legacy string is **retained**; `task.evidence_refs` is
set. Idempotent; absent `evidence` list ⇒ explicit `[]`.

## Determinism

Serialization + ordering are byte-for-byte reproducible from identical recorded state
(FR-018). `evidence[]` sorted by `producer`, then `timestamp`, then `commit_range`
(FR-021).
</content>
