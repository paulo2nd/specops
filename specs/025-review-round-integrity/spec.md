# Feature Specification: Review Round Integrity

**Feature Branch**: `025-review-round-integrity`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Harden the multi-round semantic review so approval requires a recorded anchor round covering the full baseline..HEAD defect hunt, corrective rounds are scoped to prev_to..HEAD (full file context for regression) plus FIXED-finding verification, each round's reviewed range is derived deterministically from commit ranges (no self-reporting), a union-coverage guard fails approval closed when no anchor pass exists, and a configurable round cap halts and asks a human — all recording, never judging a finding's merit, and degrading to today's behavior on legacy ledgers."

## Overview

The semantic review (`/specops-review`, Step 3) runs in rounds. A round only
reaches the code review after the deterministic gates (Step 2) pass, and a
review that finds blocking non-conformities sends the feature back to IMPLEMENT
for a corrective round. Two structural gaps exist in that loop today:

1. **No approval is anchored to a complete defect hunt.** When one or more early
   rounds are rejected *at the gates* (lint/test/reconcile/drift), they never
   reach the code review. When a round finally passes the gates, nothing in the
   process records what code scope that review actually covered, and nothing
   requires that scope to be the whole feature. A reviewer's natural incremental
   instinct — "review what changed since the last round" — can therefore approve
   a small delta while the full `baseline..HEAD` change set never received a
   single complete review. The approval says less than it appears to.

2. **The loop is unbounded.** Rounds increment without limit. Because a semantic
   reviewer is non-deterministic, re-reviewing the same unchanged code across
   rounds can keep surfacing a shifting set of findings, so the loop can fail to
   converge with nothing to stop it.

This feature closes both gaps deterministically, and strictly on the **record,
do not validate** side of SpecOps: it records what scope each review round
covered, blocks approval when the recorded coverage is incomplete, and halts to
ask a human when the loop runs too long — it never judges whether any finding is
legitimate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Approval requires a complete defect hunt on record (Priority: P1)

A feature goes through several review rounds — some rejected at the gates before
the code review, some rejected with findings — and finally reaches an
APPROVED-eligible state. Approval must be blocked unless the review history
records at least one round whose reviewed scope covered the **full effective
diff since the ledger baseline**, either alone or as the union of the rounds'
recorded scopes. The scope each round covered is derived by SpecOps from commit
ranges, not declared by the reviewer.

**Why this priority**: this is the correctness fix. Without it a SpecOps
APPROVED verdict does not guarantee the feature ever received a complete review —
the exact failure that motivated this feature. It is the minimum viable slice:
recording reviewed scope plus the approval guard, delivered together, already
restore the integrity of the verdict.

**Independent Test**: drive a review through a rejected-at-gates round, then a
rejected-with-findings round, then a passing corrective round on a fixture;
assert that approval is blocked while no recorded round covered the full
`baseline..HEAD`, and permitted once the recorded coverage (single round or
union) spans it.

**Acceptance Scenarios**:

1. **Given** a feature whose only completed review round covered a partial
   delta (not the full `baseline..HEAD`), **When** approval is attempted,
   **Then** it fails closed with a message naming the uncovered paths, and the
   phase does not transition to DONE.
2. **Given** a review history where one anchor round covered the full
   `baseline..HEAD` and a later corrective round covered only the changed delta,
   **When** approval is attempted with all blocking findings verified, **Then**
   the union of recorded scopes spans `baseline..HEAD` and approval succeeds.
3. **Given** a completed review round, **When** its reviewed scope is recorded,
   **Then** the recorded range is derived from the ledger baseline and the
   round's HEAD commit — never from reviewer-supplied input.
4. **Given** a legacy ledger with no reviewed-scope records at all, **When**
   approval is attempted, **Then** the feature degrades to the prior
   cycle-result behavior (no retroactive block).

---

### User Story 2 - Corrective rounds are scoped, not re-hunts (Priority: P2)

After a rejected round, the implementer fixes the findings and a corrective
round runs. That round reviews the change since the previous round's review
(the fixes) in full file context so a fix that regresses previously-clean code
is caught, and verifies each finding the implementer marked FIXED. It does not
re-hunt the entire feature from scratch — code already reviewed clean and
untouched since is out of scope for the corrective round.

**Why this priority**: this bounds the work of each corrective round and, more
importantly, stops a non-deterministic reviewer from re-rolling findings over
the whole unchanged surface every round — the practical driver of a
non-converging loop. It is independently valuable: even without the P1 guard,
scoping corrective rounds reduces wasted review and loop churn.

**Independent Test**: on a fixture with an anchor round already recorded, run a
corrective round after a fix that touches one previously-clean file; assert the
corrective round's recorded scope is the delta since the last review (which
includes the touched file in full context) and excludes untouched
already-reviewed files.

**Acceptance Scenarios**:

1. **Given** an anchor round covered the full feature and a corrective round
   follows a fix touching file F, **When** the corrective round's scope is
   derived, **Then** it is the change range since the previous round's review,
   and F is reviewed in full file context (not diff-hunk only).
2. **Given** a corrective round, **When** the review directive scopes the round,
   **Then** it instructs verifying each FIXED finding and reviewing the delta —
   and explicitly does not instruct re-reviewing unchanged, already-reviewed
   code.

---

### User Story 3 - The review loop is bounded (Priority: P3)

A feature's review keeps cycling — corrective round after corrective round —
past a configured limit. On crossing the limit, SpecOps halts and asks the
human to intervene rather than continuing to loop; the halt is recorded as
ledger state, and it is not a judgment on any finding.

**Why this priority**: it is the backstop for the residual non-termination risk
that survives even correct scoping, because the reviewer is non-deterministic.
It is independently valuable and testable regardless of P1/P2.

**Independent Test**: on a fixture, advance the review past the configured round
cap; assert SpecOps halts with a human-directed message and records the halt,
and that no automatic approval or rejection is fabricated.

**Acceptance Scenarios**:

1. **Given** a configured round cap of N, **When** an (N+1)th round would open,
   **Then** SpecOps halts and asks the human, recording the halt in the ledger.
2. **Given** the round cap is not configured, **When** the review runs, **Then**
   a documented default cap applies.
3. **Given** a halt-and-ask state, **When** it is recorded, **Then** it carries
   no verdict on any finding's merit — it only reflects that the loop bound was
   reached.

---

### Edge Cases

- **Baseline unresolvable** (shallow clone / rewritten history): reviewed-scope
  derivation and the coverage guard fail closed with an explanatory message, per
  the existing working-tree-gate precedent — never silently pass.
- **Baseline moved between rounds** (e.g. a rebase changed the ledger baseline):
  the coverage guard evaluates against the current baseline; a prior round whose
  recorded range no longer connects to the current baseline does not count
  toward coverage, so a fresh anchor round is required.
- **A corrective round changes nothing** (empty delta): it contributes no new
  coverage; approval still depends on an existing anchor round covering the
  whole feature.
- **First round already covers the whole feature and is clean**: a single anchor
  round satisfies the coverage guard with no corrective round needed.
- **Legacy in-flight review** (round history predates this feature, no
  reviewed-scope records): degrades to the prior cycle-result approval path; the
  new guard does not retroactively block it.
- **Resuming after a round-cap halt**: the halt stops the loop and asks a human;
  it is not a dead end. The human resumes by raising the configured cap (the next
  round opens normally), by approving when coverage is complete, or by
  rebaselining. The cap is re-evaluated from the current configuration on each
  round-opening attempt; the recorded halt is kept for audit and never fabricates
  a verdict.
- **Rebased-away review HEAD**: a reviewed-range endpoint made unreachable by a
  rebase/squash never fails `reconcile` (those endpoints are exempt from the
  registered-commit invariant). A rewritten *intermediate* review HEAD does not
  block approval (it is never re-examined); a rewritten *last-reviewed* HEAD, or a
  corrective round whose prior endpoint was rewritten, prompts a quick re-record —
  `record-scope` re-anchors over the full `baseline..HEAD`. SpecOps does not
  hard-block on ordinary history rewrites.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SpecOps MUST record, per completed semantic-review round, the code
  scope that round reviewed as a **reviewed range** derived deterministically
  from commit identifiers — the ledger baseline and the round's HEAD commit — and
  never from reviewer-supplied input.
- **FR-002**: The reviewed range of an **anchor round** MUST be the full
  effective diff from the ledger baseline to that round's HEAD
  (`baseline..HEAD`); the reviewed range of a **corrective round** MUST be the
  change from the previous recorded review's HEAD to the current HEAD
  (`prev_to..HEAD`).
- **FR-003**: SpecOps MUST block approval (the transition to DONE / APPROVED)
  unless the union of recorded reviewed ranges covers the full `baseline..HEAD`
  effective diff; the block MUST identify the uncovered paths and MUST fail
  closed (never silently approve) when coverage cannot be determined.
- **FR-004**: The approval guard MUST NOT judge the merit, correctness, or
  reason of any finding — it evaluates only whether the reviewed-scope coverage
  is complete (record, do not validate; Principle IV / Principle II).
- **FR-005**: The review directive (`templates/review.md`, Step 3) MUST
  distinguish the anchor round (review the full effective diff) from a
  corrective round (verify each FIXED finding and review `prev_to..HEAD` in full
  file context to catch fix-introduced regressions), and MUST state that
  re-reviewing unchanged, already-reviewed code is out of scope for a corrective
  round.
- **FR-006**: SpecOps MUST enforce a configurable maximum review-round count;
  when the count would be exceeded, it MUST halt and ask the human (the
  non-pierceable core — halt, do not record a bypass) and MUST record the halt
  as ledger state, distinct from any APPROVED/REJECTED verdict.
- **FR-007**: The round cap MUST have a documented default applied when the
  client has not configured one, and MUST be configurable through the existing
  client configuration surface (Principle V — generic logic plus client
  configuration).
- **FR-008**: A repository or ledger with no reviewed-scope records (legacy or
  in-flight before this feature) MUST degrade to the prior cycle-result approval
  behavior; the new guard MUST NOT retroactively block it.
- **FR-009**: Any ledger schema change introduced by this feature MUST ship a
  forward migration that upgrades existing ledgers without loss and keeps the
  read path working for records written before the change.
- **FR-010**: All adopter-facing behavior changes MUST be reflected equivalently
  in the English and Portuguese documentation, and any change to the review
  directive MUST be made in the SpecOps templates so client repositories receive
  it on the next extension install/update (Principle IV).

### Key Entities

- **Reviewed-scope record**: the per-round record of what a review round
  covered — the round identifier, its role (anchor or corrective), and the
  derived commit range (`from`..`to`) it reviewed. Attached to the review round
  in the ledger.
- **Coverage evaluation**: the derived judgment of whether the union of a
  feature's reviewed-scope records spans the full `baseline..HEAD` effective
  diff; consumed by the approval guard. Not persisted state — computed from the
  records and the current baseline.
- **Round-cap halt state**: the recorded fact that the review loop reached its
  configured bound and handed control to a human; distinct from a review
  verdict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any feature approved through the semantic review, the recorded
  reviewed-scope coverage spans 100% of the `baseline..HEAD` effective-diff
  paths — no approved feature has an uncovered path.
- **SC-002**: An attempt to approve a feature whose recorded review coverage is
  incomplete is blocked in 100% of cases, with the uncovered paths reported.
- **SC-003**: A corrective round's recorded reviewed scope contains only the
  paths changed since the previous recorded review (plus their full-file review
  context), and never the untouched already-reviewed remainder of the feature.
- **SC-004**: A review that would exceed the configured round cap halts and
  requests human intervention in 100% of cases, with zero fabricated
  approve/reject verdicts.
- **SC-005**: Every existing ledger without reviewed-scope records continues to
  reach a review verdict through the prior path — 0 legacy features are
  retroactively blocked by the new guard.
- **SC-006**: Reviewed-scope records are 100% derived from commit identifiers;
  no code path accepts a reviewer-supplied scope.

## Assumptions

- The ledger baseline recorded for a feature is the authoritative starting point
  of its effective diff (as the existing working-tree and drift gates already
  assume); reviewed-scope coverage is evaluated against it.
- A completed review round has an identifiable HEAD commit at the time its
  verdict is recorded, from which its reviewed range is derived — consistent with
  the implementer committing per user story before review.
- The default round cap is a small number chosen in the plan (assumption: 10) to
  allow normal corrective cycles while bounding a runaway loop; the exact default
  and its configuration key are finalized during planning.
- "Full file context" for a corrective round means reviewing the changed files
  sufficiently to detect regressions introduced by a fix, not merely the diff
  hunks; it does not widen the recorded reviewed range beyond `prev_to..HEAD`
  (the fixes already live inside that range).
- This feature hardens the semantic review loop only; it introduces no change to
  the deterministic `preflight` gate suite, and it reuses the existing
  baseline-relative effective-diff derivation rather than adding a new engine.
- Landing this feature is expected to broaden the Principle IV Token-Optimized
  Review directive and bump the ledger schema with a migration; the constitution
  amendment and schema version are handled at plan/implement time.
