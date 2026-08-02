# Contract — Reviewed-scope recording command

**Status**: proposed (Phase 1). Additive CLI surface under the existing
`handoff` group (Feature 021 freeze: adding a subcommand is additive).

## Command

```
specops handoff record-scope [--json]
```

Working name; the final verb is fixed here as `handoff record-scope`. Invoked by
the `/specops-review` directive at the **start of Step 3**, after the gates pass
and before reading code.

## Behavior

1. Resolve repo (`gitops.find_repo`), the active feature dir
   (`.specify/feature.json`), and load the ledger for write (`status.load_for_write`).
2. Require an **open review cycle** (`_current_cycle`); error if none (the review
   phase has not been entered). Reuse the `handoff`-surface "no open cycle"
   error shape.
3. Derive the range (never from user input — no positional/range arguments exist):
   - `to = gitops.head_sha(repo)`.
   - If **no earlier cycle** carries `reviewed_range` → `from = read_baseline`,
     `review_role = "anchor"`.
   - Else → `from =` most recent earlier cycle's `reviewed_range.to`,
     `review_role = "corrective"`.
4. Fail closed (exit 1) when `from` is empty/unresolvable
   (`not gitops.commit_exists(repo, from)`) or the baseline is missing — with the
   same explanatory wording family as `_working_tree_gate` (shallow clone /
   rewritten history / missing baseline).
5. Stamp `reviewed_range` and `review_role` on the **current** cycle
   (idempotent: re-running overwrites the current cycle's record with a range
   recomputed to the current HEAD; never appends a second record).
6. Print the **scoped file list** the reviewer must read:
   - `anchor` → every path in `name_only_diff(baseline, HEAD)` (the full hunt).
   - `corrective` → every path in `name_only_diff(from, HEAD)` (review in full
     file context) **plus** the `file` of each finding in a non-terminal state
     from prior rounds (regression surface), de-duplicated.
   - In both roles the list is **product paths only**: SpecOps/Speckit-managed
     artifacts (`.specify/**`, `specops.json`, the active `specs/<feature>/**`) are
     excluded, reusing the drift gate's `trace.is_managed` filter. The ledger
     rewrites `status.yaml` every round, so without this the reviewer's list — and
     the coverage guard — would be polluted by (and could block on) methodology
     bookkeeping rather than code.
7. Persist via `status.finalize` (revision-CAS + atomic write).

## Output

Human (default): the role, the range, and the newline-listed scoped paths, e.g.

```
review scope: anchor round 1 — 40 file(s) over 53199654..a1b2c3d
src/...
...
```

`--json` (additive to the frozen envelope; older consumers ignore new keys):

```json
{
  "command": "handoff record-scope",
  "outcome": "recorded",
  "class": "...",
  "output_version": 1,
  "round": 1,
  "review_role": "anchor",
  "reviewed_range": "53199654..a1b2c3d",
  "scope_paths": ["src/...", "..."]
}
```

## Exit codes (Principle VI)

| Code | Condition |
|------|-----------|
| 0 | Scope recorded and printed. |
| 1 | No open review cycle; unresolvable baseline/`from`; empty effective diff. |
| 2 | Corrupt/unparseable ledger, or other infrastructure/usage error. |

## Read-only guarantee unaffected

This command **mutates the ledger** (like other `handoff` mutators) and is NOT
part of `specops preflight`. The preflight/gate read-only contract (Feature
004/012/024) is untouched.

## Directive integration (`templates/review.md`, Step 3)

The rewritten Step 3 calls this command immediately after the gates pass, reads
exactly the printed scope, and — on a corrective round — verifies each FIXED
finding and reviews the delta in full file context, explicitly **not** re-hunting
unchanged already-reviewed code.
