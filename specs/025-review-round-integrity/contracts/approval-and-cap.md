# Contract — Union-coverage approval guard & round cap

Two behavioral guards added to the existing approval path
(`specops status transition-phase DONE`) and the round-opening path
(`transition-phase IMPLEMENT -r REJECTED`). No new command; both hook existing
`status.py` control flow.

## A. Union-coverage guard (approval)

**Where**: inside `_gate_done` (`status.py:936-967`), **after** the Feature 011
blocking-findings gate and the Feature 006 cycle-result gate.

**Rule** — coverage is judged by **commit reach, not path names**
(`reviewscope.assess`): the rounds chain (anchor `from` = baseline; corrective
`from` = prior `to`), so they jointly cover `baseline..frontier` (the last
recorded `to`). Full coverage ⟺ an anchor exists AND `frontier..HEAD` has no
product change:

```
a = reviewscope.assess(repo, baseline, HEAD, review_cycles, feature)
if not has_any_scope(cycles):          return              # legacy → prior behavior
if baseline unresolvable:              raise (fail closed)  # Principle VI
if a.target_empty:                     return              # nothing changed since baseline
if not a.has_anchor:                   raise               # no full baseline..HEAD hunt
if not a.frontier_resolves:            raise               # last review HEAD rewritten → re-record
if a.unreviewed_tail:                  raise               # commits after the last review
```

- `has_any_scope == False` (legacy / no scope recorded) → **no-op**; approval
  proceeds on the prior cycle-result behavior (FR-008 / SC-005).
- **Robust both ways** (the two defects a naive path-set union had): a pruned
  *intermediate* review HEAD is never re-diffed (no false block on a benign
  rewrite — R7), and a commit landing on an already-reviewed file *after* the last
  review is caught by the `frontier..HEAD` tail (no false pass on unreviewed code).
- The guard reads only `reviewed_range` endpoints and git diffs — it **never**
  inspects a finding's merit (FR-004). Only product paths count (managed
  methodology artifacts excluded), so a `status.yaml` write can neither pollute
  nor block. When the *frontier* itself was rewritten away, the guard asks for a
  fresh `handoff record-scope` (which re-anchors) rather than hard-failing.

**Ordering rationale**: coverage is evaluated only on an otherwise-approvable
review (all blocking findings verified, cycle result APPROVED), so the message a
user sees is specifically about scope, not tangled with findings state.

| Code | Condition |
|------|-----------|
| 0 | Coverage complete (anchor + no unreviewed tail), or no scope records → degrade, or nothing changed since baseline. |
| 1 | No anchor, unresolvable frontier, unreviewed tail, or unresolvable baseline while scope records exist. |
| 2 | Corrupt ledger / infrastructure error. |

## B. Round cap (halt-and-ask)

**Where**: in `cmd_transition_phase` on the REVIEW→IMPLEMENT `-r REJECTED`
transition, at the round-opening site (`_close_rejected_review`,
`status.py:903-914`), **before** appending the next-round placeholder.

**Rule**:

```
cap = review_round_cap from config (default 10, isinstance-int & >0 guarded)
# opening round N+1 would exceed the cap:
if len(cycles) >= cap:
    record review_halt = {at_round: len(cycles), cap, recorded_at: now}
    persist the halt marker; DO NOT stamp the round or open round N+1
    raise SpecopsError(  # exit 1
        "Review round cap reached (<cap> rounds). SpecOps halted and is asking "
        "for a human decision: raise 'review_round_cap' to allow another round, "
        "resolve the open findings and approve if coverage is complete, or "
        "rebaseline. No verdict was fabricated."
    )
```

- The current round is **left OPEN** — never stamped `REJECTED`. Stamping it would
  make the offered "approve" remedy structurally impossible (`_require_approved_cycle`
  demands an APPROVED cycle), so the halt records only `review_halt` and refuses to
  open round N+1; the phase stays REVIEW.
- `review_halt` is audit state, distinct from any verdict; it does not itself gate
  later transitions. The human resumes by raising the cap (re-read from live config
  each attempt), resolving findings + approving, or rebaselining.
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
