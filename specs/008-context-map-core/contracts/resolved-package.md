# Contract: Resolved Context Package & Reason Trace (v1)

The stable, versioned JSON shapes downstream (Feature 009) consumes. Fixed key sets → stable shape
(SC-006). Deterministic for a fixed map + inputs (SC-001). `output_version: 1`.

## Resolved Context Package (`context resolve --json`)

```json
{
  "command": "resolve",
  "outcome": "ok",
  "class": "pass",
  "status": "resolved",
  "output_version": 1,
  "package": {
    "context_id": "api-auth",
    "phase": "implement",
    "read_set": ["src/api/auth/**"],
    "read_set_source": "base",
    "dependencies": ["crypto", "config"],
    "expanded_read_set": [
      {"path": "src/api/auth/**", "via": "api-auth"},
      {"path": "src/crypto/**",   "via": "api-auth->crypto"},
      {"path": "src/config/**",   "via": "api-auth->config"}
    ],
    "gates": ["lint-strict"],
    "risk": {"tier": "high"}
  }
}
```

- `read_set_source` ∈ `phase` | `base` | `empty` — states which fallback produced `read_set`
  (FR-009, SC-012).
- `expanded_read_set` is **deduplicated** (first occurrence kept), **deterministically ordered**
  (dependency-declaration order, depth-first, cycle-safe), and every entry carries `via` attribution
  to its originating edge (FR-012a, SC-011).
- No timestamps appear (determinism, R11).

### No-match

```json
{ "command": "resolve", "outcome": "ok", "class": "pass",
  "status": "no_matching_context", "output_version": 1 }
```

### Absent map

```json
{ "command": "resolve", "outcome": "ok", "class": "pass",
  "status": "no_map_present", "output_version": 1 }
```

## Reason Trace (`context explain --json`)

```json
{
  "command": "explain",
  "outcome": "ok",
  "class": "pass",
  "status": "resolved",
  "output_version": 1,
  "trace": {
    "input": {"path": "src/api/auth/login.py"},
    "candidates": [
      {"context_id": "api-auth", "pattern": "src/api/auth/**",
       "specificity": {"literal_prefix": 12, "wildcards": 1, "segments": 3}},
      {"context_id": "api", "pattern": "src/api/**",
       "specificity": {"literal_prefix": 7, "wildcards": 1, "segments": 2}}
    ],
    "selected": {"context_id": "api-auth", "deciding_dimension": "literal_prefix"},
    "read_set_source": "base",
    "dependency_edges": [
      {"from": "api-auth", "to": "crypto"},
      {"from": "api-auth", "to": "config"}
    ],
    "gates": ["lint-strict"]
  }
}
```

- `candidates` are listed in comparator order (most specific first).
- `selected.deciding_dimension` ∈ `literal_prefix` | `wildcards` | `segments` | `only_candidate` |
  `ambiguous` — reconstructs *why* this context won (FR-011, SC-014). `ambiguous` only appears when a
  tie was detected (which is a validation error; `explain` on an invalid map fails closed, exit 1).
- The trace is sufficient to reconstruct the decision without re-running resolution (FR-011).

## Stability guarantee

The Resolved Package and Reason Trace share the same stability contract as any SpecOps `--json`
output: guaranteed keys are always present, optional keys omitted (never `null`), and `output_version`
bumps only on a breaking change (CHK021, CHK031).
