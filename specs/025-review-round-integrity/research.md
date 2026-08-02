# Phase 0 Research — Review Round Integrity

All design unknowns are resolved below against the current code. No
`[NEEDS CLARIFICATION]` remains. File:line anchors are from `main` at planning
time and may shift during implementation.

## R1 — Schema bump: v7 → v8, additive, no back-fill

**Decision**: Bump `CURRENT_SCHEMA = 7 → 8` (`ledger.py:35`). Add the new
reviewed-scope data as **optional** fields; write **no** back-fill helper.

**Rationale**: `migrate_to_current` (`ledger.py:215-260`) is a single idempotent
forward pass; Feature 015's v6→v7 was a *pure version bump with no back-fill*
because its new finding fields were additive-optional (`ledger.py:60-62`). The
reviewed-scope field is the same shape of change: a pre-v8 cycle simply lacks it.
A legacy ledger migrated v7→v8 gains no scope records, which is exactly the
degradation FR-008 requires — the coverage guard treats "no scope records" as
"fall back to the prior cycle-result behavior." Under the Feature 021 freeze a new
optional ledger field is additive by policy (stability-policy.md:16), so no
freeze exception is needed.

**Alternatives considered**: *Back-fill legacy cycles by re-deriving ranges from
`context_provenance`* — rejected: `context_provenance` stores context ids + map
digest, not commit ids, so a range cannot be reconstructed from it, and a
fabricated range would violate "record, do not validate." *No version bump (rely
on optionality alone)* — rejected: the frozen-ledger test pins the version; a
deliberate bump documents the schema evolution consistently with v3–v7.

## R2 — When and how the reviewed range is recorded

**Decision**: A new command **`specops handoff record-scope`** (final name in
contracts) is invoked by the review directive **at the start of Step 3**, once the
gates have passed and the code review is about to happen. It derives the range
from git and stamps it on the **current open review cycle** (`_current_cycle`,
`handoff.py:187-190`). It is idempotent per round (re-running recomputes to the
current HEAD and overwrites that cycle's record, never appends a second).

**Rationale**: The signal we need is "this round actually performed the Step-3
code review" — only such rounds should count toward coverage. That signal cannot
be `handoff close`: `cmd_close` (`handoff.py:487-510`) is *blocked* while any
blocking finding is unverified, so a REJECTED-with-findings round — which **did**
perform a full Step-3 hunt — never reaches a successful close. Recording must
therefore happen independently of the verdict. The start of Step 3 is the precise
point: gates have passed (so this is a real review round, not a gate rejection —
gate-rejected rounds stop at Step 2 and never call the command), the tree is
clean (the implementer commits per story, Principle III), and `HEAD` is the
review target. Recording here also lets the command **emit the scoped file list**
the reviewer must read, replacing the ambiguous "files listed by the working-tree
gate" text that let the reviewer improvise scope.

**Alternatives considered**: *Stamp inside `_close_rejected_review` /`_gate_done`
(at verdict time)* — rejected: fires on gate-rejected rounds too (no Step 3
happened) and, for `handoff close`, never fires on rejected rounds at all.
*Require the reviewer to pass the range explicitly* — rejected: violates "no
self-reporting" (FR-001/SC-006); the range must be git-derived.

## R3 — Anchor vs corrective derivation, and the union-coverage check

**Decision**: The recording command classifies the round and derives its range:

- **Anchor** when no earlier cycle carries a `reviewed_range` → `from = baseline`
  (`status.read_baseline`), `to = HEAD` (`gitops.head_sha`).
- **Corrective** otherwise → `from =` the most recent earlier cycle's recorded
  `reviewed_range.to`, `to = HEAD`.

The range is stored as the existing `"<from>..<to>"` convention (evidence
`commit_range`, `status.py:661`, `review.py:237`). The union-coverage guard
(`reviewscope.coverage`, pure) computes:

```
target  = set(gitops.name_only_diff(repo, baseline, HEAD))          # current
covered = ∪ over recorded ranges r where both endpoints resolve:
              set(gitops.name_only_diff(repo, r.from, r.to))
missing = target − covered
```

Approval is blocked iff `missing` is non-empty (and at least one scope record
exists — see R5). The guard reports `missing` in the error.

**Rationale**: For a linear history the union of consecutive diffs
(`baseline..HEAD₁ ∪ HEAD₁..HEAD₂ ∪ …`) covers `baseline..HEADₙ`: any path in the
target differs between baseline and HEAD, hence was touched in at least one
sub-range. A path touched then reverted nets out of the target and needs no
coverage. Evaluating against the **current** baseline/HEAD (not stored snapshots)
makes the guard correct after a rebase: a stored range whose endpoint no longer
`commit_exists` (`gitops.commit_exists`, `gitops.py:203`) is dropped from the
union, so a moved baseline drops the old anchor and leaves `missing` non-empty →
a fresh anchor round is required (spec Edge Case). No new gitops primitive is
needed — `name_only_diff` + `commit_exists` suffice; a 2-arg ancestry helper is
**not** required for the path-set cover approach.

**Alternatives considered**: *Store the derived path set per round instead of the
commit range* — rejected: paths are re-derivable from the range and storing them
duplicates state that could drift from git (Principle II favors the
git-verifiable id). *Require range-endpoint chaining (each corrective `from` ==
prior `to`) as the coverage proof* — rejected: brittle under rebase/rewrite; the
path-set cover against the current baseline is the robust invariant.

## R4 — Round cap: halt-and-ask, recorded, configurable

**Decision**: Add `review_round_cap` to `config._DEFAULTS` (`config.py:12-17`),
default **10**, read with an `isinstance(int)`/`> 0` guard at the consumer
(mirroring `lane_safety_overrides`, `config.py:60`). Enforce it in
`cmd_transition_phase` at the round-opening site: `_close_rejected_review`
(`status.py:903-914`) appends the next-round placeholder as `len(cycles)+1`;
before appending, if opening the next round would exceed the cap, **do not open
it** — record a `review_halt` marker on the ledger document and raise
`SpecopsError` (exit 1) with a human-directed message. The round-N REJECTED
verdict for the just-finished round is still recorded (the halt replaces only the
*opening of round N+1*).

**Rationale**: This is the non-pierceable-core "halt and ask a human" pattern
(Constitution Principle IV Stop-and-Ask; ROADMAP philosophy) — SpecOps stops
rather than recording a bypass. Exit 1 stops the corrective loop (Principle VI).
Recording the halt as ledger state (distinct from any APPROVED/REJECTED verdict)
satisfies FR-006 and keeps the stop auditable. The cap counts **all** rounds
(including gate-rejected ones) because total churn is what must be bounded.

**Alternatives considered**: *Warn only (non-blocking)* — rejected: a warning does
not stop a non-deterministic loop; the spec requires a halt. *Cap by consecutive
no-new-findings rounds* — rejected: more complex and not what the spec asks; a
simple total-round bound is the intended backstop, with the human as the escape
valve.

## R5 — Legacy / degradation and the guard's interaction with the existing gate

**Decision**: The union-coverage guard runs inside `_gate_done`
(`status.py:936-967`), **after** the existing Feature 011 blocking-findings gate
and the Feature 006 cycle-result gate, and only when **at least one** cycle
carries a `reviewed_range`. When no cycle has a scope record (legacy ledger, or a
review conducted by an older CLI), the guard is a no-op and approval falls through
to today's behavior (FR-008/SC-005).

**Rationale**: Ordering after the findings gate preserves the cheapest-existing
checks and means coverage is only evaluated on an otherwise-approvable review.
Gating on "≥1 scope record exists" is the degradation switch: presence of the new
data opts a feature into the new guarantee; absence preserves the old contract.
An unresolvable baseline while scope records *do* exist is a fail-closed error
(exit 1), never a silent pass (Principle VI; mirrors `_working_tree_gate`
`review.py:274`).

**Alternatives considered**: *Always enforce (block legacy in-flight reviews)* —
rejected: retroactively blocks features mid-review that predate the field
(violates FR-008). *A separate `specops` gate command instead of hooking
`_gate_done`* — rejected: approval already funnels through `transition-phase
DONE`; adding a parallel gate the workflow must remember to call reintroduces the
"forgot to run the real check" failure mode this feature exists to remove.

## R6 — Directive rewrite (`templates/review.md`, Step 3)

**Decision**: Rewrite Step 3 to (1) call `specops handoff record-scope` right
after the gates pass, (2) read exactly the scope it prints — the **full**
`baseline..HEAD` on an anchor round, `prev_to..HEAD` in **full file context** plus
each FIXED finding's file on a corrective round — and (3) state explicitly that a
corrective round does **not** re-hunt unchanged, already-reviewed code. Replace
the current line 46 ("Read only the files listed by the working-tree gate … that
list is the effective diff against the ledger baseline") which is the ambiguous
source of the original defect.

**Rationale**: The directive is the delivery vehicle (Principle IV); the guard
enforces coverage, but the directive is what makes the reviewer *read* the right
scope in the first place and stop anchoring on the previous round. This is a
SpecOps-template change propagated to clients on `extension install`/`update`.

**Alternatives considered**: *Guard only, leave the directive as-is* — rejected:
the guard would block under-scoped approvals but the reviewer would still improvise
scope every round and thrash against the guard; fixing the instruction is the
cheaper, root-cause half.

## R7 — `reviewed_range` endpoints are exempt from the reconcile invariant (K1)

**Decision**: The commit ids stored in a cycle's `reviewed_range` are **not**
subject to Principle II's "every commit hash registered in the ledger MUST exist
in the Git tree; `reconcile` blocks on divergence" invariant. `reconcile` does
**not** verify reviewed-range endpoints (it verifies task commits and the baseline
ancestry as today, unchanged), and the coverage guard tolerates an unresolvable
endpoint by dropping that range from the union (R3/R5). This exemption is recorded
explicitly — the same way `HUMAN_COMMIT = "(human)"` (`ledger.py:52`) is a
documented, deliberately-unverified commit-ish — so the design stays honest about
which registered ids are reconcile-verified and which are not.

**Rationale**: A `reviewed_range` endpoint is a **historical review HEAD**, not a
work commit. Rebase, squash-merge, or history rewrite legitimately makes an old
review HEAD unreachable while the feature itself is fine. SpecOps is a control
layer that must **not become a blocker** — the paved road you can leave (ROADMAP
Design Philosophy). Making `reconcile` fail on a rebased-away review HEAD would
punish a normal git operation and hurt adoption, for no integrity gain: the
coverage guard already re-derives everything against the **current** baseline/HEAD,
so a dropped stale range simply forces a fresh anchor round (the correct, non-
blocking outcome) rather than a hard reconcile failure. The exemption therefore
*strengthens* Principle II's intent (auditable, recoverable state) instead of
diluting it — the verified set stays exactly the work commits whose existence
actually matters.

**Amendment scope (N1)**: recording the exemption only in Principle II's
*rationale* is insufficient — the principle's **normative** sentence ("every
commit hash registered in the ledger MUST exist … `reconcile` MUST block on
divergence") would still literally cover reviewed-range endpoints. The T027
amendment therefore **narrows the normative wording**: the invariant is scoped to
work/task commits and the baseline, with an explicit carve-out for reviewed-range
endpoints (the same shape of carve-out the `(human)` sentinel already relies on).
This keeps the amended constitution self-consistent rather than contradicting its
own MUST.

**Alternatives considered**: *Extend `reconcile` to verify reviewed-range
endpoints* — rejected: turns a benign rebase into a blocking failure, contradicts
the non-blocking design goal, and adds no real guarantee. *Store no commit ids at
all (store derived path sets)* — rejected in R3 (paths are re-derivable; storing
them duplicates state and loses the git-verifiable anchor).

## R8 — Resume after a round-cap halt (U1)

**Decision**: The `review_halt` marker is audit-only and does **not** itself gate
transitions. A human resumes by any of: **raising** `review_round_cap` in
`specops.json` (the next REVIEW→IMPLEMENT then opens the next round normally),
**approving** (if coverage is complete and blocking findings are verified, DONE is
reachable regardless of the halt), or **rebaselining** (`specops rebaseline`,
which re-anchors the feature). The cap check is re-evaluated on each round-opening
attempt against the *current* config, so simply lifting the cap unblocks the loop;
the historical `review_halt` record remains for audit.

**Rationale**: FR-006 requires the halt to stop the loop and hand control to a
human without fabricating a verdict — it must not become a dead end. Re-evaluating
the cap from live config (rather than latching a permanent block) keeps the human
in control with the lightest possible mechanism and no new command.

**Alternatives considered**: *A dedicated `specops review resume`/`--force`
command* — rejected as unnecessary surface: raising the config value is the
existing, auditable lever; adding a bypass verb invites exactly the silent-override
the non-pierceable core forbids.

## Resolved governance consequences

- **Constitution**: MINOR amendment broadening Principle IV (Token-Optimized
  Review records reviewed scope; approval enforces union coverage; round cap is a
  Stop-and-Ask). The amendment ALSO records the R7 exemption in Principle II's
  rationale (reviewed-range endpoints are deliberately unverified by `reconcile`,
  like the `(human)` sentinel). Updated in the same change set with
  `templates/review.md`.
- **Ledger**: v7 → v8, additive optional field, forward migration = version bump.
- **Reconcile**: unchanged behavior; the exemption is pinned by a regression test
  (reconcile stays green when a reviewed-range endpoint is unresolvable).
- **Docs**: README.md + README.pt-br.md updated at parity.
- **No new dependency**; `preflight` read-only contract untouched.
