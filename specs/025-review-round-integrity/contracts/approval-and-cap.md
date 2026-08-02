# Contract — Union-coverage approval guard & round cap

Two behavioral guards added to the existing approval path
(`specops status transition-phase DONE`) and the round-opening path
(`transition-phase IMPLEMENT -r REJECTED`). No new command; both hook existing
`status.py` control flow.

## A. Union-coverage guard (approval)

**Where**: inside `_gate_done` (`status.py:936-967`), **after** the Feature 011
blocking-findings gate and the Feature 006 cycle-result gate.

**Rule**:

```
cov = reviewscope.coverage(repo, baseline, HEAD, review_cycles)
if cov.has_scope_records and cov.missing_paths:
    raise SpecopsError(
        "Cannot enter DONE: the review did not cover the whole feature. "
        "Uncovered path(s): <missing>. Run an anchor review round over the "
        "full baseline..HEAD before approving."
    )
```

- `has_scope_records == False` (legacy / no scope recorded) → **no-op**; approval
  proceeds on the prior cycle-result behavior (FR-008 / SC-005).
- Baseline unresolvable while `has_scope_records` → **fail closed** (exit 1),
  never silent pass (Principle VI).
- The guard reads only `reviewed_range` endpoints and git diffs — it **never**
  inspects a finding's merit (FR-004). A stored range whose endpoint no longer
  resolves (rebase/squash) is dropped, not an error: `reviewed_range` endpoints
  are exempt from the `reconcile` registered-commit invariant (research R7), so
  the guard re-derives against the current baseline/HEAD and, if that leaves paths
  uncovered, asks for a fresh anchor round rather than hard-failing.

**Ordering rationale**: coverage is evaluated only on an otherwise-approvable
review (all blocking findings verified, cycle result APPROVED), so the message a
user sees is specifically about scope, not tangled with findings state.

| Code | Condition |
|------|-----------|
| 0 | Coverage complete (or no scope records → degrade) and all prior gates pass. |
| 1 | `has_scope_records and missing_paths`; or baseline unresolvable with scope records. |
| 2 | Corrupt ledger / infrastructure error. |

## B. Round cap (halt-and-ask)

**Where**: in `cmd_transition_phase` on the REVIEW→IMPLEMENT `-r REJECTED`
transition, at the round-opening site (`_close_rejected_review`,
`status.py:903-914`), **before** appending the next-round placeholder.

**Rule**:

```
cap = review_round_cap from config (default 10, isinstance-int & >0 guarded)
# round N just got REJECTED; opening round N+1 would exceed the cap:
if len(cycles) >= cap:
    record review_halt = {at_round: len(cycles), cap, recorded_at: now}
    persist the round-N REJECTED verdict + the halt marker
    raise SpecopsError(  # exit 1
        "Review round cap reached (<cap> rounds). SpecOps halted and is asking "
        "for a human decision: rebaseline, approve, or abandon. No verdict was "
        "fabricated."
    )
```

- The just-finished round's `REJECTED` result IS recorded; only the **opening of
  the next round** is refused.
- `review_halt` is audit state, distinct from any verdict; it does not itself gate
  later transitions once a human intervenes.
- The cap counts **all** rounds (gate-rejected and reviewed alike) — total churn
  is what is bounded.

| Code | Condition |
|------|-----------|
| 0 | Under the cap: round N+1 opens normally. |
| 1 | Opening round N+1 would exceed the cap → halt recorded, human asked. |
| 2 | Corrupt ledger / infrastructure error. |

### Resume after a halt (research R8)

The halt is not a dead end. The cap is re-read from `specops.json` on **every**
round-opening attempt, so a human resumes by any of:

- **Raise the cap** — set a higher `review_round_cap`; the next
  `transition-phase IMPLEMENT -r REJECTED` opens round N+1 normally.
- **Approve** — if coverage is complete and all blocking findings are verified,
  `transition-phase DONE -r APPROVED` succeeds; the halt marker does not block it.
- **Rebaseline** — `specops rebaseline` re-anchors the feature.

The `review_halt` record is never auto-cleared (it stays for audit). No bypass
verb is added — raising the config value is the auditable lever, consistent with
the non-pierceable core (no silent override).

## Interaction

The two guards are independent: A bounds *what* must be reviewed before approval;
B bounds *how many times* the loop may run. A feature can hit B (too many rounds)
without ever reaching A (approval), and can be blocked by A (incomplete coverage)
well under the cap. Neither guard judges a finding's merit (Principle IV /
"record, do not validate").
