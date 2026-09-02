# Feature Specification: Cross-Round Review Coverage

**Feature Branch**: `027-cross-round-review-coverage`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Make multi-round review accumulate coverage: `handoff record-scope` emits the full `baseline..HEAD` set alongside the corrective priority set marked as not yet re-verified, the ledger derives from recorded ranges which baseline product paths no round has ever read, and APPROVED fails closed while that never-read set is non-empty — degrading to today's behavior on ledgers with no reviewed-scope records, and never prescribing how a reviewer spends its context."

## Overview

Feature 025 gave the semantic review loop a recorded, git-derived scope per
round: an **anchor** round covers `baseline..HEAD`, a **corrective** round covers
`prev_to..HEAD` plus the files of still-open findings. That narrowing is correct
as a **priority** — a corrective round should look hardest at what just changed —
and unsafe as a **boundary**.

Two distinct problems follow from treating it as a boundary:

1. **The reviewer cannot see past the narrowing.** From round 2 onward the tool
   prints only the delta, and the review directive instructs the reviewer not to
   look elsewhere. A defect sitting in a baseline file that round 1 did not
   catch is structurally out of view for every round that follows. The more
   rounds a feature needs — i.e. the more troubled it is — the more confident the
   process looks while its visible surface shrinks. This is not hypothetical: an
   adopter running an out-of-band full-feature review found two blocking defects
   in one feature inside this blind spot, and a cross-tenant data leak in
   another after four rounds, one of which ended APPROVED
   ([#76](https://github.com/paulo2nd/specops/issues/76)).

2. **The coverage guard credits rounds it can no longer verify.** Today's
   approval guard asks two coarse questions: does *some* recorded range start at
   the current baseline, and is `frontier..HEAD` empty. Everything between the
   anchor and the frontier is assumed covered without being checked. When a
   recorded range's endpoints no longer resolve — history rewritten during a
   corrective round, a shallow clone, a feature rebaselined onto a new starting
   commit — the paths that range was supposed to account for are silently
   credited anyway. The verdict is all-or-nothing and names no file, so an
   adopter who hits it is told to "run an anchor round over the whole feature"
   with no indication of what is actually missing.

This feature makes coverage **accumulate and be named**. The reviewer always
receives the full `baseline..HEAD` set alongside the round's priority set, marked
as not yet re-verified this round, so declining to read part of it becomes the
reviewer's recorded decision rather than the tool's silent one. The ledger derives
which baseline product paths have been reached by *some* recorded round and which
have never been reached by any, from commit ranges only. Approval fails closed
while that never-reached set is non-empty, and names every path in it.

It stays strictly on the **record, do not validate** side: it records and reports
what was covered, it never judges a finding's merit and never mandates a re-read.

> **Correction to the roadmap.** The roadmap entry for Feature 027 claimed the
> `record-scope` full-set emission "shipped ahead of this feature in `0.12.0` as the
> additive half". Verified against `main` @ `c64cb73`: it did not, and the roadmap
> entry has been corrected. `handoff
> record-scope` still emits only `scope_paths`, and `templates/review.md` still tells
> a corrective round "Do not re-hunt unchanged, already-reviewed code". That emission
> is therefore in scope here, as User Story 1.

## Clarifications

### Session 2026-09-02

- Q: Where is the never-reached set reported, besides the blocked approval? → A: Folded into `handoff record-scope` output as a third labelled subset (human + JSON); no new command or report surface.
- Q: A feature rename leaves `specs/<old-name>/` paths outside the active-feature exclusion, blocking approval on methodology prose. How is that handled? → A: For coverage derivation only, treat every `specs/*/` path as managed — no ledger field, no rename history.
- Q: How large a never-reached list does the blocked-approval message print? → A: First 10 paths plus the total count; the full set stays in the machine-readable output.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A corrective round can see the whole feature (Priority: P1)

A reviewer runs a corrective round. `specops handoff record-scope` still leads with
the round's priority set (`prev_to..HEAD` plus the files of still-open findings),
but it now also presents the full `baseline..HEAD` product set, clearly marked as
not yet re-verified this round. The review directive states the tradeoff in the
open: the priority set is where the defects are most likely to be, the rest of the
baseline is unverified this round, and if the reviewer declines to look at part of
it for context-budget reasons, that is the reviewer's call to make and to record —
not a decision the tool makes silently on its behalf.

**Why this priority**: this is the slice that would have prevented the reported
failures. Both blocking defects the adopter found, and the cross-tenant leak
before them, were in files the tool had stopped printing. Nothing else in this
feature puts a file in front of a reviewer that was not there before; this does,
and it delivers value standalone, with no ledger or gate change.

**Independent Test**: on a fixture with an anchor round recorded and a corrective
round open after a fix touching one file, run `handoff record-scope`; assert the
output contains both the priority set (the fix plus open-finding files) and the
full `baseline..HEAD` product set, that the two are distinguishable in both the
human and JSON output, and that the not-yet-re-verified portion is labelled as
such.

**Acceptance Scenarios**:

1. **Given** a corrective round whose priority set is 13 files while
   `baseline..HEAD` touches 40 product files, **When** `handoff record-scope`
   runs, **Then** it presents both sets — the 13 as this round's priority and the
   remaining baseline paths as not yet re-verified this round — and the recorded
   `reviewed_range` is unchanged from today's derivation.
2. **Given** an anchor round, **When** `handoff record-scope` runs, **Then** the
   priority set and the full baseline set are the same set and the output does
   not imply a second, separate reading obligation.
3. **Given** a corrective round, **When** the review directive scopes the round,
   **Then** it states that the baseline set outside the priority set is unverified
   this round, and that declining to read part of it is a reviewer decision to be
   recorded — replacing today's instruction that re-reviewing already-reviewed
   code is out of scope.
4. **Given** any round, **When** `handoff record-scope` runs, **Then** both sets
   are derived from commit ranges and never from reviewer-supplied input, and
   neither set is persisted as a self-reported claim of what was read.

---

### User Story 2 - The ledger names what no round has ever reached (Priority: P2)

Across a feature's review history, SpecOps derives — from the recorded ranges and
git alone — which product paths changed since the baseline have been reached by at
least one round, and which have never been reached by any. The never-reached set
is reported by name, so a reviewer or an adopter can see exactly where the review
history has holes instead of being told the coverage is merely "incomplete".

**Why this priority**: it converts today's all-or-nothing, unnamed coverage verdict
into a per-path one, and it closes the silent-credit hole — a round whose recorded
range no longer resolves stops being counted as covering anything. Independently
valuable as a report even before it gates anything: the set is reported through
`handoff record-scope`, which already computes the full baseline set for User Story
1, so the reviewer sees the history's holes at the moment it can act on them. No new
command is introduced.

**Independent Test**: on a fixture with several recorded rounds, assert
`handoff record-scope` reports an empty never-reached subset for an intact chain; then invalidate a middle round's
recorded range (rewritten endpoints) and assert the paths that range alone
accounted for appear in the never-reached set by name; then move the baseline and
assert the paths changed only in the newly-included span appear.

**Acceptance Scenarios**:

1. **Given** a review history whose recorded ranges all resolve and chain from the
   current baseline to HEAD, **When** coverage is derived, **Then** the
   never-reached set is empty.
2. **Given** a recorded range whose endpoints no longer resolve in this clone,
   **When** coverage is derived, **Then** that range contributes no coverage and
   any baseline product path not reached by another round is listed by name as
   never reached.
3. **Given** a feature whose baseline was moved to an earlier commit after its
   rounds were recorded, **When** coverage is derived, **Then** the product paths
   changed in the newly-included span are listed as never reached.
4. **Given** coverage derivation, **When** it runs, **Then** it reads only recorded
   ranges and git history — never a reviewer's account of what it read, and never a
   path-similarity or file-name heuristic.
5. **Given** a non-empty never-reached set, **When** `handoff record-scope` runs,
   **Then** those paths are reported as a third labelled subset, distinct from the
   round's priority set and from the not-yet-re-verified remainder, in both the
   human and the machine-readable output.
6. **Given** SpecOps-managed methodology artifacts changed since the baseline
   (`.specify/`, `specops.json`, the active feature's `specs/<feature>/`), **When**
   coverage is derived, **Then** they are excluded from both the reached and the
   never-reached sets.

---

### User Story 3 - Approval fails closed on an unreached baseline path (Priority: P3)

A feature reaches an APPROVED-eligible state. If any product path changed since the
baseline has never been reached by a recorded round, approval is blocked and the
message names those paths and the command that resolves them. A ledger carrying no
reviewed-scope records at all keeps the pre-025 behavior — this never blocks a
feature retroactively.

**Why this priority**: it is the enforcement that makes User Story 2's derivation
binding. It ships third because the derivation and the reviewer-visible full set
carry value on their own, and because turning a report into a gate is the change
most likely to need the other two in place first.

**Independent Test**: drive a REJECTED → REJECTED → APPROVED sequence on a fixture
where no round ever reached a given baseline-changed file; assert approval fails
closed and names that file. Re-run the same sequence with an anchor round covering
it; assert approval succeeds. Re-run with a ledger carrying no reviewed-scope
records; assert it closes through the prior behavior.

**Acceptance Scenarios**:

1. **Given** a REJECTED → REJECTED → APPROVED sequence in which no recorded round
   ever reached baseline-changed file F, **When** approval is attempted with all
   blocking findings verified, **Then** it fails closed, names F, and the phase
   does not transition to DONE.
2. **Given** the same sequence with an additional anchor round whose range reaches
   F, **When** approval is attempted, **Then** it succeeds.
3. **Given** a ledger with no reviewed-scope records on any round, **When**
   approval is attempted, **Then** it closes through the prior cycle-result
   behavior and is not blocked by this guard.
4. **Given** a feature whose baseline commit cannot be resolved while
   reviewed-scope records exist, **When** approval is attempted, **Then** it fails
   closed rather than silently passing.
5. **Given** a feature with no product change since the baseline, **When**
   approval is attempted, **Then** no coverage is required and approval proceeds.
6. **Given** a blocked approval, **When** the reviewer reads the message, **Then**
   it names the unreached paths and the command that records coverage for them —
   not a generic instruction to review the whole feature again.

---

### Edge Cases

- **A round is gate-rejected and never reaches the code review.** It records no
  scope; coverage is derived from the rounds that did, and a later round's range
  reaching back across the gap covers it.
- **The corrective round's `prev_to` was rewritten away.** `record-scope` already
  re-anchors over `baseline..HEAD` rather than failing; the derivation must agree
  with that fallback and not double-count the abandoned range.
- **The active feature was renamed since the baseline.** The rename moves
  `specs/<old>/` to `specs/<new>/`; both directories are excluded from coverage by
  FR-005a, so neither the deletions nor the additions can block approval.
- **A path was added and then deleted between the baseline and HEAD.** It is
  absent from the effective `baseline..HEAD` diff, so it is neither required nor
  reported.
- **A round's range resolves but is empty of product changes** (only managed
  artifacts moved). It contributes no reached paths and is not treated as a
  coverage failure.
- **The never-reached set is large** (a rebaselined feature). The blocked-approval
  message lists the first 10 paths and the total count; the full set is available in
  the machine-readable output.
- **Approval is blocked on coverage while the review round cap is reached.** This is
  not a deadlock: `handoff record-scope` operates on the round already open and
  re-anchors over `baseline..HEAD` when the prior range is unresolvable, so the
  coverage hole closes without consuming a new round. The cap's Stop-and-Ask halt is
  unchanged.
- **Approval is attempted in a shallow clone.** Ranges cannot resolve; with
  reviewed-scope records present this fails closed, consistent with the existing
  baseline-unresolvable rule.
- **Both the priority set and the full baseline set are empty on an anchor
  round.** Today's "nothing to review" outcome is preserved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `specops handoff record-scope` MUST emit, in addition to the round's
  priority set, the full `baseline..HEAD` product-path set, with the portion
  outside the priority set marked as not yet re-verified this round, and the
  never-reached set (FR-003) as a third labelled subset. All three MUST be
  distinguishable in the human output and carried as distinct keys in the
  machine-readable output.
- **FR-001a**: No new command or report surface is introduced for coverage; the
  never-reached set is reported through `handoff record-scope` and named in the
  blocked-approval message (FR-007), and nowhere else.
- **FR-002**: The emitted sets MUST NOT change what `record-scope` persists: the
  round's recorded `reviewed_range` and `review_role` continue to be derived
  exactly as today. The full-set emission is presentation, not a coverage claim.
- **FR-003**: SpecOps MUST derive, from the recorded reviewed ranges and git
  history alone, the set of product paths changed since the baseline that have been
  reached by at least one recorded round and the complementary set reached by none.
- **FR-004**: A recorded range whose endpoints do not resolve in the current
  repository MUST contribute no coverage; its paths fall to the never-reached set
  rather than being credited.
- **FR-005**: Coverage derivation MUST exclude SpecOps/Spec Kit-managed artifacts
  from both sets, reusing the existing managed-path exclusion rather than adding a
  second definition.
- **FR-005a**: For coverage derivation, the exclusion MUST cover **every**
  `specs/<any-feature>/` path, not only the active feature's — a Spec Kit feature
  directory is a methodology artifact by construction and can never be product code.
  This keeps a `specs feature rename` (Feature 026) from parking the old directory's
  paths in the never-reached set. The exclusion used by other consumers (the drift
  gate) is unchanged.
- **FR-006**: Coverage derivation MUST NOT use path-similarity, file-name, or
  directory heuristics; reach is a property of commit ranges only.
- **FR-007**: Approval MUST fail closed while the never-reached set is non-empty,
  and the failure MUST name the unreached paths and the command that records
  coverage for them. The human message MUST list at most the first 10 paths and
  MUST state the total count; the machine-readable output MUST carry the full set.
- **FR-008**: A ledger with no reviewed-scope records on any round MUST degrade to
  the prior cycle-result approval behavior; this guard MUST NOT retroactively block
  an in-flight or legacy feature.
- **FR-009**: When reviewed-scope records exist but the baseline cannot be
  resolved, approval MUST fail closed.
- **FR-010**: The coverage evaluation MUST remain derived state — computed from the
  recorded ranges and the current repository at evaluation time, never persisted as
  a coverage claim that could go stale.
- **FR-011**: The approval guard MUST NOT judge the merit, correctness, or reason
  of any finding, and MUST NOT require any path to be re-read; it evaluates only
  whether each baseline product path was reached by some recorded round.
- **FR-012**: The review directive (`templates/review.md`, Step 3) MUST state the
  tradeoff explicitly: the priority set is the round's focus, the remainder of the
  baseline set is unverified this round, and a decision to not read part of it is
  the reviewer's to record. It MUST NOT instruct the reviewer that already-reviewed
  code is out of scope.
- **FR-013**: This feature MUST NOT change the review round cap, the finding
  lifecycle, or the deterministic `preflight` gate suite.
- **FR-014**: All adopter-facing behavior changes MUST be reflected equivalently in
  the English and Portuguese documentation, and every directive change MUST be made
  in the SpecOps templates so client repositories receive it on the next extension
  install/update.

### Key Entities

- **Priority set**: the paths a round is asked to look at hardest — for an anchor
  round the full `baseline..HEAD` product diff, for a corrective round
  `prev_to..HEAD` plus the files of still-open findings. Emitted, and unchanged
  from today.
- **Not-yet-re-verified set**: the baseline product paths outside this round's
  priority set. Emitted so the reviewer can see past the narrowing; never a
  recorded obligation.
- **Reached path**: a product path changed since the baseline that appears in the
  effective diff of at least one recorded, still-resolvable reviewed range.
- **Never-reached set**: the baseline product paths that are not reached paths.
  Derived at evaluation time, never persisted; consumed by the approval guard and
  reported by name in the `handoff record-scope` output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On every corrective round, the reviewer receives 100% of the
  `baseline..HEAD` product paths — the priority set plus the not-yet-re-verified
  remainder — with zero baseline paths withheld from the output.
- **SC-002**: The never-reached set is empty in 100% of review histories whose
  recorded ranges resolve and chain from the current baseline to HEAD (no false
  block on an intact history).
- **SC-003**: A recorded range whose endpoints no longer resolve is credited with
  zero reached paths in 100% of cases.
- **SC-004**: An approval attempt with a non-empty never-reached set is blocked in
  100% of cases; the message states the total unreached count and names at most the
  first 10 paths, and the machine-readable output carries 100% of them.
- **SC-005**: 0 features carrying no reviewed-scope records are blocked by this
  guard.
- **SC-006**: Coverage results are 100% reproducible from the ledger plus the git
  repository — running the derivation twice on unchanged inputs yields an identical
  set, and no reviewer-supplied input can alter it.
- **SC-007**: The `preflight` gate suite, the round cap, and the finding lifecycle
  produce byte-identical behavior before and after this feature.

## Assumptions

- **"Reached" means commit reach, not comprehension.** A path is reached when a
  recorded round's range covers a commit touching it — that is what a range can
  prove. The feature does not, and cannot, assert that a reviewer understood the
  file. Guarding against a reviewer that read a file and missed a defect is User
  Story 1's job (keep the file visible every round), not the gate's.
- **The per-path guard replaces today's coarse checks rather than stacking on
  them.** Today's `has_anchor` and `frontier..HEAD`-empty conditions are both
  special cases of a non-empty never-reached set; expressing them per-path yields
  the same fail-closed outcomes with the failing files named. Whether they are
  literally removed or retained as fast paths is a plan-time call; the observable
  contract is the per-path one.
- **The full baseline set is emitted, not stored.** Persisting it would create a
  second coverage record capable of disagreeing with the derivation, which is the
  class of bug Feature 025 avoided by deriving from ranges.
- **A reviewer's decision to skip part of the baseline is recorded as review
  prose or a finding**, through the surfaces that already exist; this feature adds
  no self-reported coverage field, because a field the reviewer fills is exactly
  the input FR-006 and SC-006 exclude from the derivation.
- **The existing managed-path exclusion and effective-diff derivation are reused**
  rather than reimplemented; the change is to what is compared, not how a diff is
  computed. The one behavioral change is FR-005a's widened exclusion, which also
  retires the same latent false block in today's `frontier..HEAD` tail check — that
  check is subsumed by the per-path guard, so no separate fix is needed.
- **Ledger schema is expected to stay at its current version.** Coverage is derived
  from records that already exist (`reviewed_range`, `review_role`); no new
  persisted field is anticipated. If planning proves one is needed, it ships with a
  forward migration.
- **Landing this feature is expected to narrow the Principle IV review directive**
  (the corrective round's "do not re-hunt" instruction becomes a priority, not a
  boundary); the constitution amendment is handled at implement time.
- **Dependencies**: Feature 025 (reviewed-scope records and the approval guard this
  revises) and Feature 026 (the supported correction path an adopter takes when an
  approval is blocked by an unreached file), both MERGED.

## Out of Scope

- **No re-reading mandate.** The feature records and reports what was covered; it
  never prescribes how a reviewer spends its context budget.
- **No change to the round cap, the finding lifecycle, or the deterministic gate
  suite.**
- **No path-similarity heuristics.** Coverage stays derived from commit reach.
- **No self-reported coverage input.** No CLI flag, ledger field, or directive
  instruction lets a reviewer declare a path read.
