# Phase 1 Data Model: Test Execution Only at the Review Gate

This feature changes how one existing structure is **produced** and **keyed**, and adds one **ephemeral store** outside the ledger. The committed ledger (`status.yaml`, schema **v7**) is unchanged and unwritten by review.

## Store: Gate-run cache (new, ephemeral)

A YAML file at `<git-dir>/specops/gate-cache/<feature>.yaml` holding a list of gate-run records (each an evidence-shaped `EvidenceRecord`). It lives **inside the git directory**, so it never appears in the working tree, `git status`, `git diff`, `worktree_digest`, or the tests' `snapshot_tree` (which excludes `.git`). It is created lazily on the first passing command-gate run and is safe to delete (a cold cache just re-executes). Not committed, not cross-clone.

## Entity: Gate-run cache record (activated)

An `EvidenceRecord` (`specops.records.EvidenceRecord`) produced by a command-executing gate, stored in the gate-run cache above. The shape is unchanged from Feature 012; what changes is that review now **records** it (in the cache, not the ledger) and its cache key gains a working-tree dimension.

| Field | Source | Notes for this feature |
|-------|--------|------------------------|
| `id` | `derive_id(cache_key)` | Now derived from a key that **includes `worktree_digest`** for gate records. |
| `producer` | `f"gate:{name}@{cli_version}"` | Only `gate:lint@…` and `gate:test@…` are ever persisted (R5). |
| `command` | gate command | The client `lint_command` / `test_command`. |
| `exit_code` | run result | **Only `0` is persisted** (R3). |
| `timestamp` | close time | Timezone-aware, as today. |
| `commit_range` | `f"{baseline}..{head}"` | As computed in `profile_gates`. |
| `affected_paths` | effective diff | As computed in `profile_gates`. |
| `superseded_by` | `append_record(supersede=True)` | Set on the prior same-producer record when a new run is persisted. |

**Lifecycle**: execute (pass) → `append_record(cache_records, rec, supersede=True)` → prior `gate:<name>@…` record for the same producer gets `superseded_by = rec.id`; the new record is the live one; the cache file is rewritten. On a later identical run, `_cached_record` finds the live record by id → `cached` disposition, **no execution, no cache write** (idempotent by id).

**Invariants**:
- INV-1: At most one non-superseded record per `producer` at any time.
- INV-2: A persisted gate record always has `exit_code == 0`.
- INV-3: A gate record's `id` changes iff its cache key changes (command, commit range, affected paths, context-map digest, or **working-tree digest**).

## Value object: Cache key (extended)

`evidence.cache_key(...)` gains an **optional** `worktree_digest: str | None = None` parameter.

- When `worktree_digest is None` (all `auto`/legacy callers): the returned dict is **byte-identical to today** — the key is omitted, so `derive_id` yields the same id. No migration, no id churn for task evidence. (INV-4)
- When provided (gate records): the dict includes `"worktree_digest": "<sha256:…>"`, so any tree change yields a new id.

```
cache_key(producer, command, commit_range, affected_paths, context_map_digest,
          subject=None, worktree_digest=None)
  → { producer, command, commit_range, affected_paths(sorted),
      context_map_digest, subject,
      **({"worktree_digest": worktree_digest} if worktree_digest is not None else {}) }
```

## Value object: Working-tree digest (new)

`gitops.worktree_digest(repo) -> str`:

```
"sha256:" + sha256( <git diff HEAD bytes> + b"\0" + "\n".join(sorted(<porcelain -uall lines>)).encode() )
```

- Captures tracked modifications (`git diff HEAD`) **and** untracked/added files (porcelain `-uall`).
- Deterministic for identical tree state; differs on any committed or uncommitted change.
- Clean tree → stable digest of the empty diff + empty status.

## Entity: Development-phase completion evidence (changed)

The `auto` record and legacy string written by `complete-task --auto` (`status.py::_auto_evidence` / `_record_completion`).

| Aspect | Before | After |
|--------|--------|-------|
| Test run at close | runs `test_command`, fails close on non-zero | **none** |
| Legacy string | `TEST_REPORT:…; CODE_DIFF:…` | `CODE_DIFF:<n files across m commits: …>` |
| Structured `auto` record `command` | the test command | `"(auto)"` |
| `exit_code` | `0` (after a passing test) | `0` (no test) |
| Commit harvesting | yes | yes (unchanged) |
| "no commits yet" guard | yes | yes (unchanged) |

**Note**: `CODE_DIFF` is a valid `EVIDENCE_CLASSES` member, so the reduced string passes `validate_string`. No grammar change.

## State transition impact (workflow)

Unchanged phase machine (`SPECIFY → … → REVIEW → DONE`). The only behavioral delta:

- `review-soft` (preflight `--soft`): executes `lint`/`test`, records the passing runs in the git-dir cache (ledger + tree untouched).
- `terminal-gate` (hard preflight): recomputes the cache key (same tree → same `worktree_digest` → same id) → **reuses** the cached records as `cached`; executes only if the corrective loop changed the tree (new commit or uncommitted edit → new digest).
