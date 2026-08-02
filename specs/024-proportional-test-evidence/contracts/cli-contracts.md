# Phase 1 Contracts: Affected CLI Behavior

The SpecOps CLI is the project's external interface. No command is added or renamed; two existing commands change behavior. Contracts below are the observable guarantees tasks and tests must hold to.

## `specops status complete-task <task-id> --auto`

**Change**: closes the task without running any test command.

| Aspect | Contract |
|--------|----------|
| Test execution | MUST NOT invoke `test_command` or any test command. |
| Evidence recorded | MUST record commit hashes + a `CODE_DIFF:<summary>` legacy string and a structured `auto` record (`command="(auto)"`, `exit_code=0`) — mechanically, not agent-narrated. |
| Failure modes | MUST still fail closed when there are no commits since task start ("commit your work first"). MUST NOT fail on test results (there are none). |
| `test_command` unset | No longer an error for `--auto` (it is only consumed by the `test` gate). |
| Exit codes | Unchanged `0`/`1`/`2` contract (Principle VI). |

**Non-regression**: `--evidence` (manual) close path is unchanged.

## `specops preflight` (and deprecated alias `specops review`)

**Change**: persists passing command-gate evidence append-only; reuses it on an identical re-run.

| Aspect | Contract |
|--------|----------|
| Persistence | On a **passing** `lint`/`test` gate execution, MUST append a `gate:<name>@<version>` evidence record, superseding the prior non-superseded record for the same producer. |
| Reuse | When the cache key matches (producer, command, commit range, affected paths, context-map digest, **working-tree digest**), MUST report the gate as `cached` and MUST NOT execute the command. |
| Invalidation | Any working-tree change (committed or uncommitted), commit-range change, command change, or path change MUST force execution (no stale reuse). |
| Cacheable gates | Only `lint` and `test`. `reconcile`, `working-tree`, `drift` MUST always recompute and MUST NOT be served from or written to the cache. |
| Cached correctness | A `cached` result MUST reflect a persisted **passing** record; a non-passing cached record MUST NOT be reported as PASS. |
| Read-only boundary | MUST NOT mutate task, phase, finding, or recovery state, or config. The **only** permitted ledger write is appending gate-run evidence (and flipping `superseded_by` on prior gate records). |
| `--soft` vs hard | Both persist on a passing run. `--soft` keeps exit 0 on REJECTED (unchanged); hard preflight fails closed on REJECTED (unchanged). |
| Determinism | Output is deterministic for identical input ledger state. A fresh run (executes) and a subsequent run (cached) legitimately differ in the gate's `disposition`; repeated cached runs are byte-identical. |
| `gate list` / `gate validate` / `gate report` | Remain **fully** read-only (never execute gates, never write). |

## Internal contracts (not user-facing, but test-visible)

### `specops.evidence.cache_key(...)`
- Gains optional `worktree_digest: str | None = None`.
- With `worktree_digest is None`, returns a dict byte-identical to the pre-feature output → **stable `auto` ids** (no migration).
- With a value, includes `"worktree_digest"` in the key.

### `specops.gitops.worktree_digest(repo) -> str`
- Returns `"sha256:<hex>"` deterministic for identical tree state.
- Differs whenever tracked content, staged content, or untracked files differ.

## Workflow-level guarantee (composed)

For a happy-path run (one corrective-loop iteration, APPROVED) with U user stories:
- `complete-task --auto`: **0** test runs (U closes, diff evidence only).
- `review-soft`: **1** full-suite `test` execution (persisted).
- `terminal-gate`: **0** executions (reused as `cached`, tree unchanged).
- **Total full-suite executions: 1** (was U+2).
