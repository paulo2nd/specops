# Contract: Context Map Schema (v1)

Stored at `.specify/specops/context-map.yaml`. Stack-neutral, versioned (FR-001, R2). Field-level
validation is independent (FR-002). This is the shipped starter template (`context init`) plus the
full grammar.

## Grammar

```yaml
schema_version: 1                 # required integer; !=1 rejected (too_new / unsupported)
created_at: "2026-07-20T00:00:00+00:00"   # optional, written by init; not echoed in resolution
contexts:                         # required list (may be empty -> empty_valid)
  - id: api                       # required, unique, ^[A-Za-z0-9][A-Za-z0-9._/-]*$
    match:                        # required, >=1 gitignore-style glob, relative to repo root
      - "src/api/**"
    reads:                        # optional
      base: ["src/api/**"]        # phase-agnostic fallback
      plan: ["docs/api-design.md", "src/api/**"]   # phase-specific (declaration order preserved)
    ownership: "team-api"         # optional descriptive metadata (NOT a write boundary)
    dependencies: ["config"]      # optional; each MUST be an existing context id
    gates: ["lint-strict"]        # optional; well-formed ids only (not resolved here)
    risk:                         # optional; string-keyed mapping, values opaque this feature
      tier: high
  - id: config
    match: ["src/config/**"]
```

## Validation rules → defect `code`

| Rule | Defect `code` | Class |
|---|---|---|
| `schema_version` absent/non-int/`<1` | `unsupported_schema_version` | version |
| `schema_version > 1` | `unsupported_schema_version` (too_new) | version |
| Root not a mapping / YAML parse fails | (state `malformed`, no per-field code) | parse |
| `id` missing/malformed | `schema_invalid` (field `id`) | schema |
| Two contexts share `id` | `duplicate_context_id` | identity |
| `match` missing/empty/non-list | `schema_invalid` (field `match`) | schema |
| Glob pattern malformed | `invalid_path_pattern` | path |
| Glob escapes repo root (`..`, absolute) | `unsafe_path_traversal` | path (distinct) |
| Two contexts claim same path at equal specificity | `ambiguous_ownership` | topology |
| `dependencies` entry → unknown context id | `dangling_dependency` | dependency |
| Dependency cycle | `dependency_cycle` | dependency |
| `gates` entry not a well-formed identifier | `schema_invalid` (field `gates`) | schema |
| `risk` not a string-keyed mapping | `schema_invalid` (field `risk`) | schema |

Notes:
- Path validation is **syntactic + safety only** — the filesystem is never consulted; a well-formed
  in-repo pattern matching zero files is **valid** (FR-005).
- `validate` reports **all** defects in one pass (R8); each has a stable `code` (SC-002).
- The seven blocking defect classes are exactly: `invalid_path_pattern`, `unsafe_path_traversal`,
  `duplicate_context_id`, `ambiguous_ownership`, `dangling_dependency`, `dependency_cycle`,
  `unsupported_schema_version` (mirrors FR-005 ↔ SC-002, CHK019).

## Versioning & compatibility

- `CURRENT_SCHEMA = 1`, `OLDEST_SUPPORTED = 1`. `migrate_to_current()` is an identity scaffold until a
  v2 exists (R2). An unsupported/too-new version is rejected with a version-specific diagnostic
  rather than partially interpreted (FR-020, SC-010).
