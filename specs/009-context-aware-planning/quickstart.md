# Quickstart & Validation: Context-Aware Planning and Impact

A run-and-validate guide proving Feature 009 end-to-end. Per the constitution, all behavior is
exercised against **fixtures/sample repositories** under `tests/`, never by running `specops` against
this repository. Implementation code belongs in `tasks.md`/implementation — this is a validation guide.

## Prerequisites

- `pip install -e .` (exposes the `specops` entrypoint; Python ≥ 3.10)
- A **sample** Spec Kit repository with a Feature 008 context map at
  `.specify/specops/context-map.yaml` and an initialized SpecOps ledger (Feature 006).

## Author a dependency-graph map (sample repo)

```yaml
# .specify/specops/context-map.yaml  (illustrative fixture)
schema_version: 1
contexts:
  - id: api
    match: ["src/api/**"]
    reads: {base: ["src/api"], plan: ["src/api", "docs/api.md"]}
    dependencies: []
    gates: ["contract-tests"]
    risk: {tier: high}
  - id: web
    match: ["src/web/**"]
    reads: {base: ["src/web"]}
    dependencies: ["api"]     # web depends on api  => a change to api affects web
    gates: []
    risk: {}
```

## Flow

```bash
# 1. Phase-scoped minimal reads (reuses Feature 008 resolve; R9 phase tokens)
specops context resolve --id api --phase plan --json      # minimal plan read set for `api`

# 2. Plan-topology check (plan.md declares: **SpecOps-Contexts**: api  + `src/api/x.py` (modify))
specops context plan-check --json                          # plan_check_ok, exit 0

# 3. Impact of a change to api — reverse expansion pulls in web
specops context impact --path src/api/handler.py --json    # affected: api(ownership), web(dependency)

# 4. Impact from Git (no --path): derives baseline->HEAD diff
specops context impact --json

# 5. Stale detection after moving/removing a declared path's files
specops context stale --json                               # stale_found lists (context_id, pattern)
```

## Success-criteria validation (via fixtures)

| SC | Validation |
|---|---|
| **SC-001** | Run `plan-check`/`impact`/`stale --json` twice on a fixed fixture; assert byte-for-byte identical output incl. reason traces. |
| **SC-002** | For a multi-context fixture, assert every `affected[].via` ∈ `{ownership, dependency, policy}` and no context lacks a `via`. |
| **SC-003** | Fixture with a catch-all owner → assert `unbounded_expansion` (exit `1`), not a repo-wide read; normal fixture → `bounded: true`. |
| **SC-004** | Plans that (a) omit `SpecOps-Contexts`, (b) name an unknown ID, (c) leave a path owned by an undeclared context → each exit `1` with the matching status; no-map fixture → exit `0`. |
| **SC-005** | Fixture where a declared pattern's files are removed/moved → `stale_found` names the right `(context_id, pattern)`; all-matching fixture → `stale_ok`; assert independence from untracked/gitignored files. |
| **SC-006** | Close a task + record a review cycle on a map fixture → assert `context_provenance.map == present` with `digest` + `context_ids`; no-map fixture → `{map: none}`; migrate a v1/v2 ledger → readable, records backfilled `{map: none}`. |
| **SC-007** | Snapshot repo + ledger before/after each read-only command → assert unchanged; assert exit codes ∈ `{0,1,2}` with a populated `status`. |
| **SC-008** | Record plan-time provenance, change the map, run review → assert a **non-blocking** digest-drift warning (exit `0`) and that both digests are recoverable from provenance. |

## Degenerate & fail-closed checks

- `context impact` with a clean tree / empty diff → `impact_ok`, empty `affected`, exit `0`.
- `context impact` outside a Git repo or with no resolvable baseline → `usage_error`, exit `2`.
- Any command on a malformed/ambiguous/unsupported-version map → exit `1`, status defers to
  `context validate`.
- Every command on a repo with no map → exit `0` (`no_map_present`).

## Quality gates

```bash
ruff check .
mypy src/specops
pytest            # includes --cov=specops --cov-fail-under=85
```
