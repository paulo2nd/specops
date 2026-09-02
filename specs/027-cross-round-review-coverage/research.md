# Phase 0 Research: Cross-Round Review Coverage

**Feature**: 027 | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)

All Technical Context unknowns are resolved below. No `NEEDS CLARIFICATION` remains.

---

## R1 — Coverage derivation: per-path union of range tree-diffs

**Decision**. Replace the coarse coverage verdict with a per-path one:

```
target        = product_paths(diff(baseline, HEAD))
reached       = ⋃ over recorded ranges whose BOTH endpoints resolve:
                    product_paths(diff(from, to))
never_reached = sorted(target − reached)
```

`gitops.name_only_diff` runs `git diff --name-only A B` — a **two-dot tree
comparison**, not a commit walk (`gitops.py:343-348`).

> **Caveat found in code review (2026-09-02), and it is load-bearing.** The
> transitivity argument below is about *blob* identity, but `--name-only` does not
> report raw differing paths: git's **rename detection** is on by default and is
> similarity-based, so it is not transitive across nested ranges. Verified directly:
> `git mv a.py b.py` then rewrite `b.py` makes the segment `A..M` report `b.py`
> alone while the wide `A..H` reports `a.py` *and* `b.py` — putting `a.py` in the
> target and in no segment. That is a permanent `never_reached` block on a benign
> rename, and `record-scope` cannot clear it because the chain start still resolves.
> Every coverage diff therefore passes `--no-renames`, funnelled through the single
> `reviewscope.changed_paths` helper. The argument holds only with that flag set.

**Rationale**. Soundness on an intact chain is a transitivity argument on tree
comparison, not an assumption about commit reach: if the rounds chain
`baseline → t₁ → … → tₙ = HEAD` and file `F` differs between `baseline` and
`HEAD`, then `F` must differ across at least one segment (if it were identical
across every segment it would be identical end to end). So an intact chain
yields `never_reached = ∅` — SC-002 holds by construction, not by luck.

> **Corrected during implementation (2026-09-02).** This section originally claimed
> the per-path test *replaces* Feature 025's chain checks. It does not, and the
> existing test `test_unreviewed_commit_after_frontier_blocks` proved it: a path
> reached by an earlier round and then **re-touched** after the last one is still a
> member of the reached set, so the set difference is empty and the change passes
> unreviewed. Feature 027 therefore **adds one branch and removes none.**

The two models are complementary, and each sees exactly what the other cannot:

| Case | Chain checks (025) | `never_reached` (027) |
|---|---|---|
| No range starts at the baseline | blocks (`not has_anchor`) | blocks, and **names** the files |
| Change lands after the last round on a **new** path | blocks (`unreviewed_tail`) | blocks, and names it |
| Already-reached path **re-touched** after the last round | **blocks** — the only check that can | blind (still a set member) |
| Frontier unresolvable, earlier ranges cover everything | **blocks** — the tail cannot be computed | blind (coverage looks complete) |
| A **middle** range a rewrite orphaned | **passes silently** — never checked | **blocks**, and names the files |

The guard runs `never_reached` first (it is the only branch that can name files),
then the three 025 branches unchanged, with their messages byte-identical.

**Cost**. One `git diff` for the target plus one per resolvable recorded range.
The round cap (`review_round_cap`, default 10) bounds this at ~11 subprocess
calls, on a path that already shells out twice. No caching needed; measured
against the existing `assess` this is a constant-factor change, not an order one.

**Alternatives rejected**.

- ~~*Keep the coarse checks and add the per-path one on top.*~~ Originally rejected
  as producing "two overlapping messages for one condition". That reasoning was
  wrong — the conditions do not overlap, they partition (table above) — and this is
  what shipped. The spec's Assumptions reserved the choice as a plan-time call; the
  answer turned out to be **add**, not replace.
- *Commit-walk reach (`git rev-list from..to` then per-commit `--name-only`).*
  Strictly more git calls for an identical answer on chained ranges, and it
  disagrees with `target` (a tree diff) on change-then-revert inside one range.
  Consistency with how `target` is computed matters more than a distinction the
  gate cannot act on.

---

## R2 — An unresolvable range contributes nothing (FR-004) — and this narrows the Principle II carve-out

**Decision**. Check both endpoints with `gitops.commit_exists` before diffing a
recorded range; an unresolvable range contributes zero reached paths.

Do **not** rely on `name_only_diff` returning `[]` on a non-zero exit
(`gitops.py:346`) — same result, but by accident. FR-004 is a stated contract and
gets an explicit check.

**Consequence, stated plainly.** Constitution Principle II carries a Feature 025
carve-out ending: *"the review coverage guard tolerates an unresolvable endpoint
by re-deriving against the current baseline/HEAD, so SpecOps never blocks on a
benign history rewrite."* Under R1/FR-004 it **does** block — a corrective
round's commits squashed or amended orphan that round's review HEAD, its paths
fall out of `reached`, and approval fails closed naming them.

That is not an oversight; it is the feature. Silently crediting a range the tool
can no longer verify is the exact silent-credit hole User Story 2 exists to close.
But it is a narrowing of a written carve-out and therefore needs a constitution
amendment (MINOR), recorded in Complexity Tracking and landed with the
implementation — the same pattern Feature 025 used when it narrowed Principle II
in the first place.

**The block is one command deep, and that is provable — not hopeful.**
`handoff record-scope` re-anchors over `baseline..HEAD` when the prior range's
`from` no longer resolves (`handoff.py:558-562`). Three facts make that a complete
recovery rather than a lucky one:

1. **Orphaning is always a chain suffix.** A rewrite (rebase, amend, squash) also
   rewrites every descendant, so if round *k*'s `to` is orphaned then every later
   round's endpoints are orphaned too. There is no "orphaned middle, resolvable
   tail" state — which is the state that *would* deadlock, because `derive_range`
   would chain from a still-resolvable later `to` and never re-cover the gap.
2. **So `derive_range` always falls back to ANCHOR.** It chains from the most
   recent earlier recorded `to` (`reviewscope.py:derive_range`); by (1) that
   endpoint is orphaned whenever anything is, so `cmd_record_scope` takes the
   re-anchor branch and records `baseline..HEAD`. One range, full coverage,
   `never_reached` empty.
3. **The round is still open when the block fires.** `_gate_done` sets
   `cycles[-1]["result"] = "APPROVED"` in memory *before* calling the coverage
   guard (`status.py:1179-1182`), but the guard raises, so `finalize` never runs
   and the on-disk cycle still has `result: null`. `cmd_record_scope`'s
   open-round precondition (`handoff.py:552-553`) is therefore still satisfied on
   the retry. No new round is consumed.

**Blast radius.** `record-scope` runs at the start of every Step-3 round, so an
orphaned chain self-heals on the next round without ever reaching the guard. The
block can only fire when the rewrite happens **after** the last `record-scope` and
**before** the approval attempt — an amend or squash immediately before approving.
Narrow, and exactly the moment coverage claims are least trustworthy.

**Scope of the block.** The rebase-onto-new-main case (every endpoint orphaned
*including* the baseline) is already fail-closed today and is unchanged
(`status.py:1120-1126`). What changes is the narrower squash/amend case where the
baseline survives.

**Alternatives rejected**.

- *Report an unresolvable range but don't block on it.* Contradicts US3 acceptance
  scenario 2, which the clarification session accepted. An advisory-only guard is
  the state we are leaving.
- *Re-derive an orphaned range's paths from the reflog / `ORIG_HEAD`.* Non-portable,
  not present in a fresh clone or CI checkout, and it would make coverage depend on
  local machine state — directly against SC-006 (reproducible from ledger + repo).

---

## R3 — Reshape `Assessment`; the derivation stays in `reviewscope`

**Decision**. `reviewscope.assess` returns

```python
@dataclass(frozen=True)
class Assessment:
    has_scope_records: bool
    target_empty: bool
    never_reached: list[str]      # sorted; replaces has_anchor / frontier /
                                  # frontier_resolves / unreviewed_tail
```

**Rationale**. `assess` has exactly one caller — `status._gate_review_coverage`
(`status.py:1127`) — so the four coarse fields are internal and can go. Feature
021 froze *adopter-facing* contracts (CLI surface, JSON envelopes, ledger schema);
`reviewscope` is an internal module and `Assessment` is not in the freeze.
Keeping dead fields would leave two coverage models in the codebase, which is how
the silent-credit hole survived 025.

`product_paths`, `derive_range`, `has_any_scope`, `DerivedRange` are unchanged.

**Alternatives rejected**. A parallel `assess_paths()` beside the old `assess()` —
two models, one caller, guaranteed drift.

---

## R4 — The three emitted sets (FR-001)

**Decision**. `handoff record-scope` gains three additive JSON keys and three
labelled human blocks. `scope_paths` and its meaning are untouched.

| Key | Contents |
|---|---|
| `scope_paths` | **unchanged** — the round's priority set |
| `baseline_paths` | full `product_paths(diff(baseline, HEAD))` |
| `not_reverified_paths` | `baseline_paths − scope_paths` |
| `never_reached_paths` | `Assessment.never_reached` (FR-003) |

On an anchor round `scope_paths == baseline_paths`, so `not_reverified_paths` is
empty and the human output prints only the priority block (spec AS-2: no second
reading obligation implied).

**Rationale**. Additive optional keys are an additive change under the stability
policy (`specs/021-contract-freeze/contracts/stability-policy.md:27`), so
`handoff.OUTPUT_VERSION` stays `1`. Feature 026 added keys the same way. The
derived sets are emitted, never persisted (spec Assumptions) — a stored copy is a
second coverage record able to disagree with the derivation.

**Alternatives rejected**. A new `handoff coverage` command (Q1 option C) — a new
frozen surface for data that belongs where the reviewer already is. Rejected in
clarification.

---

## R5 — Widened managed-path exclusion for coverage only (FR-005a)

**Decision**. `reviewscope.product_paths` drops any path under `specs/` in
addition to what `trace.is_managed` drops. `trace.is_managed` itself is untouched,
so the drift gate keeps its current exclusion.

**Rationale**. `is_managed` narrows the spec-directory exclusion to the *active*
feature name (`trace.py:93`), resolved at evaluation time. Feature 026 shipped
`specops feature rename` and persists no rename history, so after a rename the old
`specs/<old>/` paths are non-managed and land in `never_reached` — approval blocked
on methodology prose. A Spec Kit feature directory is never product code, so the
narrowing was always more specific than review coverage needs.

This also retires the same latent false block in today's `frontier..HEAD` tail
check, which is subsumed by R1 — no separate fix.

**Known limit (accepted)**. The prefix `specs/` is hardcoded, matching
`is_managed`'s existing hardcode. A repository whose Spec Kit directory is
relocated via `SPECIFY_FEATURE_DIRECTORY` outside `specs/` keeps the current
narrow behavior. Widening both to the resolved directory is a separate change with
its own blast radius (the drift gate); it is not this feature's job.

**Alternatives rejected**. Persisting rename history in the ledger (Q2 option B) —
a new field, a migration, and a second identity record to keep in sync, for a
problem a prefix check solves. Rejected in clarification.

---

## R6 — Message bound (FR-007 / SC-004)

**Decision**. The blocked-approval message states the total and names at most the
first 10 paths, in the derivation's sorted order:

```
Cannot enter DONE: 37 product path(s) changed since the baseline have never been
reviewed by any recorded round: a.py, b.py, … (10 shown of 37). Run
'specops handoff record-scope' to re-anchor the review scope over them.
```

**This is consistent with local precedent, not a departure from it** (an earlier
draft of this file said otherwise). Every unbounded `', '.join(...)` in a message
today joins an *identifier* list that is small by construction — finding ids
(`handoff.py:629`, `doctor.py:421`), phase names, SC ids. The one place the
codebase renders a **path** list for a human already truncates it:
`status.py:634` builds the `CODE_DIFF` summary as
`f"{len(files)} files ...: {', '.join(files[:5])}"` — count first, then a bounded
sample. R6 applies exactly that shape to a list that can reach hundreds of entries
on a rebaselined feature.

`SpecopsError` carries no structured payload, so the complete set reaches consumers
through `never_reached_paths` in the `record-scope` JSON (R4).

**Alternatives rejected**. Unbounded (Q3 option B), count-only (Q3 option C) — both
rejected in clarification.

---

## R7 — Directive change (FR-012)

**Decision**. Rewrite the corrective-round bullet in
`src/specops/templates/review.md` (Step 3). The current text ends:

> Do **not** re-hunt unchanged, already-reviewed code: it is out of scope for a
> corrective round and only invites re-flagging clean code.

It becomes: the priority set is where to look hardest; the rest of the baseline
set is printed and is **unverified this round**; declining to read part of it for
context-budget reasons is the reviewer's decision **to record**, not the tool's to
make silently. The "Read exactly the files it lists. Do not review anything
outside them." line stays — `record-scope` now lists everything.

**Rationale**. Principle IV requires behavioral change to arrive through the
registered directives, and Governance requires the amendment and the template edit
in the same change set. This is the slice that would have prevented the reported
failures — the gate cannot catch a file a reviewer was shown and misread.

**Note.** The roadmap claimed this emission shipped in `0.12.0`; verified against
`main` @ `c64cb73` it did not (`cmd_record_scope` emits `scope_paths` alone;
`review.md:47` still carries the old text). `ROADMAP.md` was corrected on
2026-09-02.

---

## R8 — No schema change

**Decision**. Ledger stays at `schema_version: 9`. No migration.

**Rationale**. Coverage derives from `reviewed_range` / `review_role`, both added
by Feature 025 at v8 (`records.py:98-102`). FR-010 forbids persisting the
evaluation, and FR-001a forbids a new surface, so nothing new is written. The
`_reviewed_scope_violations` structural validator (`ledger.py:433`) is unchanged.

---

## Constitution deltas landing with this feature

**Two amendments, not one.** Governance requires a Principle IV directive change to
propagate to `src/specops/templates/` **in the same change set**. The two directive
changes land in two different commits (one per user story, per the repository's
convention), so they are two amendments — deferring both to the end would put the
US1 template edit in a commit with no matching constitution change.

| # | Lands with | Principle | Delta | Version |
|---|---|---|---|---|
| 1 | **US1** (with the `templates/review.md` rewrite) | IV — Surgical Agent Behavior | The Token-Optimized Review **emission** clause (constitution lines 523-525) describes a corrective round as `prev_to..HEAD` plus open findings' files. That is no longer all `record-scope` emits: it becomes the stated *priority* alongside the full baseline set. | `1.12.0 → 1.13.0` MINOR (materially expanded guidance) |
| 2 | **US3** (with the gate rewrite) | II — Physical State Ledger | The Feature 025 carve-out's "never blocks on a benign history rewrite" is narrowed: an unresolvable `reviewed_range` no longer counts as coverage, so approval blocks until one `record-scope` re-anchors (R2). `reconcile` still does not verify these endpoints — that half is unchanged. | `1.13.0 → 1.14.0` MINOR (narrowed, not removed) |
| 2 | **US3** (same change set) | IV — Surgical Agent Behavior | The **coverage** clause — approval "fails closed unless the union of recorded scopes covers `baseline..HEAD`" — becomes the per-path never-reached test. | folded into `1.14.0` |

Each bump is MINOR under Governance versioning: guidance is broadened or narrowed,
never removed or redefined.

### Drafted amendment text (Principle II)

The Feature 025 carve-out currently ends:

> […] the review coverage guard tolerates an unresolvable endpoint by re-deriving
> against the current baseline/HEAD, so SpecOps never blocks on a benign history
> rewrite.

Replace the final clause:

> […] `reconcile` does not verify these endpoints and never blocks on a benign
> history rewrite. The review coverage guard, however, credits a round only with
> what it can still verify (Feature 027): an unresolvable endpoint contributes no
> coverage, so approval fails closed naming the product paths left unaccounted
> for. Recovery is one `specops handoff record-scope` on the round already open,
> which re-anchors over `baseline..HEAD` without consuming a review round — a
> rewrite costs a re-scope, never a re-review.

The `reconcile` exemption is untouched; only the guard's tolerance narrows.
Principle IV's corrective-round directive is amended per R7 in the same change set.
