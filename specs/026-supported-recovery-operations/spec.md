# Feature Specification: Supported Recovery Operations

**Feature Branch**: `026-supported-recovery-operations`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "Add the ledger's supported correction path: an append-only `status amend-task` that records a corrected evidence entry and its reason on an already-DONE task without reopening it, a `feature use` command plus automatic repointing by `init-spec` so the active-feature pointer is never edited by hand, and a `feature rename` that carries a renumbering across directory, branch, artifacts, and ledger identity — all recording, never validating, and never mutating or deleting a prior evidence entry."

## Overview

The ledger's authority rests on one rule: its state is written by SpecOps
commands, never by hand. Two states an interrupted or misrouted session routinely
leaves behind have **no legal move** under that rule, so the only way forward is
to break it.

1. **A task closed with wrong or missing evidence cannot be corrected.** Once a
   task is `DONE`, `start-task` refuses to reopen it and `complete-task` refuses
   to write to it (#74). This is not an exotic state — it is the expected residue
   of exactly the failure the ledger exists to survive: a session terminated
   mid-flight after closing tasks without real evidence. A recovery session that
   has reconstructed the truth has nowhere to put it. The workaround found in the
   field was `trace link`, which happens to accept `DONE` tasks, so commits could
   be re-bound while the evidence gap stayed open.

2. **The active-feature pointer can only be repointed by hand.** `.specify/feature.json`
   selects the feature every command answers about, and no command changes it
   (#75). Starting a new feature, or renumbering one because a colleague's merge
   took the number, means editing the file directly — and renumbering means
   hand-moving a directory, three artifacts, a branch reference and a ledger that
   is explicitly not hand-editable. The field workaround was to delete the ledger
   and re-run `init-spec`, destroying the record.

Both push the operator toward hand-editing the very files the ledger exists to
make trustworthy. This feature closes both with auditable commands that **record**
the correction rather than laundering it: an amendment makes a task's history
richer, never quieter, and a repoint or a rename is a stated operation with a
stated outcome instead of a silent file edit.

The whole feature sits on the *record, do not validate* side of SpecOps
(Principle IV): it never judges whether an amendment's reason is good, never
infers what an interrupted session meant to record, and never removes or rewrites
anything already written.

## Clarifications

### Session 2026-08-31

- Q: After an amendment, which evidence value is the task's *current* one for downstream consumers? → A: The latest amendment becomes the current evidence; the original and every prior amendment are retained in history and rendered as superseded.
- Q: Does `feature rename` rewrite references inside the moved artifacts? → A: It rewrites only the structured identity header SpecOps owns (`**Feature Branch**` in `spec.md`), and reports — without changing — every other occurrence of the old name found in the moved artifacts.
- Q: Does `amend-task` target a specific prior evidence record or the task as a whole? → A: Task-level — the amendment supersedes whatever the task's current evidence is (all of it, if several records are current) and becomes the single current value. No evidence id is accepted.
- Q: Do the injected agent directives teach `amend-task`, or is it operator-only? → A: The directives name it as a recovery move — an agent may use it to correct a record left by a previous session, never to revise a close it made itself in the current run.
- Q: Should `feature use` refuse to repoint away from a feature with unfinished work? → A: No — warn and proceed: repoint, and report the outgoing feature's unfinished state (active task, open review round) as part of the success output.

**Scope decision (2026-08-31, post-clarification)**: investigation of the Spec Kit
side found that Spec Kit resolves the active feature from `SPECIFY_FEATURE_DIRECTORY`
**before** the pointer file, while SpecOps reads the pointer file only. The resulting
divergence is the same silent-wrong-feature failure US2 exists to close, arriving
through a different door, and it would make `feature use` report success while having
no effect on the Spec Kit side. Closing it was folded into US2 (FR-009a, FR-010a,
FR-014a) rather than deferred.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Correct the evidence on an already-closed task (Priority: P1)

A session closed tasks `T027`–`T029` with placeholder evidence and no commits,
then died. The recovery session re-runs the gates, has the real commits in hand,
and needs to put the verified truth on those tasks. It runs
`specops status amend-task T027 --evidence "TEST_REPORT: …" --reason "original
close recorded no gate run; session terminated mid-flight"`. The task stays
`DONE`; the ledger now carries **both** the original claim and the later
verification, each with its own timestamp and the amendment's reason alongside —
the verified value is what every downstream surface reads, the original claim is
retained as superseded history.

**Why this priority**: this is the gap with no workaround at all and the one that
silently degrades every downstream artifact — evidence reports, traceability, and
the review's ability to trust what it reads. It is independently valuable: shipped
alone, the ledger gains its correction path.

**Independent Test**: on a fixture with a `DONE` task carrying known-wrong
evidence, run `amend-task` with corrected evidence and a reason; assert the task
is still `DONE`, the original evidence record is present, unmodified and marked
superseded, the new record is current and marked as an amendment carrying its
reason, and `reconcile` accepts the resulting ledger.

**Acceptance Scenarios**:

1. **Given** a task in `DONE` with recorded evidence, **When** the operator runs
   `amend-task` with new evidence and a reason, **Then** the command succeeds, the
   task remains `DONE`, the amended value becomes the task's current evidence, and
   the prior record is retained and marked superseded — both readable with their
   timestamps and the amendment's reason.
2. **Given** a task in `DONE`, **When** the operator amends it twice, **Then**
   all three records (original plus two amendments) are retained in order, the
   second amendment is current, and the first amendment is marked superseded — an
   amendment never erases an earlier amendment.
3. **Given** a task that is `PENDING` or `IN_PROGRESS`, **When** the operator runs
   `amend-task` on it, **Then** the command refuses with a non-zero exit and names
   the supported command for that state (`start-task` / `complete-task`).
4. **Given** an `amend-task` invocation with no `--reason`, or with evidence that
   does not match the evidence grammar, **When** it runs, **Then** it refuses with
   a non-zero exit and writes nothing.
5. **Given** an amended task, **When** a review finding is later closed with
   automatic evidence inherited from that task, **Then** the finding's evidence
   record carries the amendment provenance rather than presenting the corrected
   value as ordinary close-time evidence.
6. **Given** an amended task, **When** the ledger's evidence is reported or shown,
   **Then** the current value is the amendment and is labelled as one — the output
   never presents the corrected value as if it had been recorded at close time —
   and the superseded records remain reachable.

---

### User Story 2 - Point at the feature actually under work (Priority: P2)

The operator finishes `025-x`, authors `specs/026-y/spec.md` on a new branch, and
runs `specops feature use specs/026-y`. Every subsequent command answers about
`026-y`. When they then run `status init-spec`, it initializes the feature it was
pointed at *and* leaves the pointer on it, so the common "new feature" path needs
no separate step and no hand edit. Because Spec Kit consults an environment override
before the pointer file, SpecOps consults it too — the two can never disagree about
which feature is active, and a repoint that the override would neutralize is refused
rather than reported as done.

**Why this priority**: the failure this removes is silent and reports success —
`consistency` answering `ok` about a finished feature while the one under work is
unvalidated. The defect half (naming the feature in the output) shipped in
`0.12.0`; this story removes the cause rather than the symptom. It ranks below
US1 because a hand edit of `feature.json` is at least *possible* today, where
amendment is not.

**Independent Test**: on a fixture with the pointer on feature A, run
`feature use` against feature B and assert every pointer-reading command resolves
B; separately, initialize a fresh feature C with `init-spec` and assert the
pointer moved to C and `consistency` validates C with no hand edit; and with an
environment override set to A, assert SpecOps resolves A and refuses a repoint to B.

**Acceptance Scenarios**:

1. **Given** the pointer on a finished feature, **When** the operator runs
   `feature use` against an existing feature directory holding its specification
   artifact, **Then** the pointer is repointed and the command reports the old and
   the new resolved directory.
2. **Given** a target directory that does not exist, is outside the specs
   directory, or holds no specification artifact, **When** `feature use` runs,
   **Then** it refuses with a non-zero exit, names the reason, and leaves the
   pointer untouched.
3. **Given** a feature directory that exists and holds a specification but no
   plan or task artifacts yet, **When** `feature use` runs, **Then** it succeeds
   (this is the normal pre-planning state) and reports which expected artifacts
   are not yet present.
4. **Given** a feature directory with no ledger, **When** `status init-spec` runs
   against it, **Then** the ledger is created and the pointer resolves to that
   feature afterwards without any hand edit.
5. **Given** a pointer that is already on the target, **When** `feature use` runs,
   **Then** it succeeds as a no-op and says so (idempotent).
6. **Given** the current feature has a task in progress or an open review round,
   **When** the operator repoints away from it, **Then** the repoint succeeds and the
   output names the unfinished work left behind on the outgoing feature.
7. **Given** an environment override naming feature A, **When** any SpecOps command
   resolves the active feature, **Then** it resolves A — the same feature Spec Kit
   resolves from the identical repository state.
8. **Given** an environment override naming feature A, **When** the operator runs
   `feature use` against feature B, **Then** the command refuses with a non-zero
   exit, names the override as the reason, and leaves the pointer untouched.

---

### User Story 3 - Renumber a feature without demolishing its ledger (Priority: P3)

A colleague's merge takes the number this feature reserved, so `026-y` must become
`027-y`. The operator runs `specops feature rename specs/026-y specs/027-y`. The
directory moves, the ledger's own identity (feature name, and the branch reference
when the operator supplies the new branch name) is updated in place, the
specification's feature-branch header is rewritten to the new name, and the pointer
follows — with the ledger's history, evidence, and review record fully intact. Every
other mention of the old name still sitting in the artifacts is listed in the output
so the operator can decide about each one; the command never rewrites prose it does
not own.

**Why this priority**: the rarest of the three and the one with a (bad) workaround
today — delete the ledger and re-init, which throws away the audit trail the tool
exists to keep. Valuable independently: it converts a destructive improvisation
into a recorded operation.

**Independent Test**: on a fixture feature with a populated ledger (tasks, evidence,
review cycles), rename it and assert the directory moved, the pointer follows, the
ledger's identity fields and the specification's feature-branch header match the new
name, every prior record is byte-preserved, remaining old-name occurrences in the
artifacts are reported and left unmodified, and `reconcile` plus `consistency` both
pass against the renamed feature.

**Acceptance Scenarios**:

1. **Given** a feature with a populated ledger, **When** it is renamed, **Then**
   the new directory holds every artifact, the specification's feature-branch header
   names the new feature, and the ledger's task, evidence, acknowledgement and
   review-cycle records are unchanged.
2. **Given** artifacts that mention the old feature name in their prose (a plan
   citing the old directory path, a task list quoting the old branch), **When** the
   rename runs, **Then** each occurrence is reported with its file and location, the
   prose is left exactly as written, and the rename succeeds.
3. **Given** a rename whose target directory already exists, **When** it runs,
   **Then** it refuses with a non-zero exit and changes nothing.
4. **Given** a rename where the operator also renamed the Git branch, **When**
   they supply the new branch name to the command, **Then** the ledger's branch
   reference is updated and the ledger's identity check passes on the current
   branch.
5. **Given** a rename where the operator has **not** renamed the Git branch,
   **When** the rename runs without a branch name, **Then** the branch reference
   is left as recorded and the command states that the branch reference was not
   changed.
6. **Given** an environment override naming the feature about to be renamed,
   **When** the rename runs, **Then** it refuses with a non-zero exit, names the
   override, and changes nothing — the override would otherwise be left pointing at
   a directory that no longer exists.
7. **Given** any rename, **When** it fails partway (target unwritable, ledger
   unwritable), **Then** the feature is left in exactly its pre-rename state — no
   half-moved directory and no pointer aimed at nothing.

---

### Edge Cases

- **Amending a task whose original evidence is a legacy flat string** (recorded
  before structured evidence existed): the original string's content is preserved
  verbatim as a retained superseded record before the current value moves to the
  amendment, so no original wording is lost.
- **Amending a task carrying several current evidence records** (an original close
  whose legacy string expanded into multiple records on migration): all of them are
  superseded together by the single amendment, so the task never ends up with a
  mixed current/stale set.
- **Amending with evidence identical to what is already recorded**: recorded as an
  amendment anyway with its reason, since the operator's assertion that a
  correction occurred is itself the record; it is never silently dropped as a
  duplicate.
- **Amending a task that is `DONE` but orphaned** (removed from the task list):
  permitted — an orphaned task's record is exactly the kind of residue that needs
  correcting.
- **An environment override pointing at a directory that does not exist**: reported
  as an unresolvable override with its source named, never silently ignored in favour
  of the pointer file — silently falling back is how the two tools drift apart.
- **`feature use` run when the outgoing feature has no ledger at all** (it was never
  initialized): nothing can be unfinished, so the repoint reports no outgoing-state
  warning and succeeds silently on that axis.
- **`feature use` against a directory whose ledger names a different feature**:
  permitted and reported; SpecOps records the pointer move and lets `consistency`
  and `reconcile` report the mismatch, rather than pre-judging it.
- **`feature use` or `feature rename` run outside a repository, or with a
  malformed pointer file**: refuses with the infrastructure/usage exit code and a
  reason, never a stack trace, never a silent zero.
- **Renaming a feature that is the active pointer target vs. one that is not**:
  in the first case the pointer follows; in the second it is left alone and the
  command says so.
- **Renaming to a name that only differs in its numeric prefix vs. a full rename**:
  both are the same operation — no special case for renumbering.
- **A ledger written by an older schema is amended**: it migrates forward on the
  write like any other state change, and the amendment lands on the migrated
  ledger with no loss.

## Requirements *(mandatory)*

### Functional Requirements

**Amendment (US1)**

- **FR-001**: The system MUST provide a command that records corrected evidence,
  with a mandatory reason, against a task already in `DONE`.
- **FR-002**: The amendment MUST be **append-only** with respect to the evidence
  *history*: it MUST NOT alter the content, reason, or timestamp of any evidence
  record already attached to the task, MUST NOT remove one or render it unreadable,
  and MUST NOT change the task's status, completion timestamp, or recorded commits.
  Marking a prior record superseded (FR-002a) is the sole permitted change to it.
- **FR-002a**: The most recent amendment MUST become the task's **current**
  evidence for every downstream consumer, and the records it displaces MUST be
  retained and marked as superseded — readable in full, with their original
  content and timestamps intact. Displacing a record MUST NOT alter its content.
- **FR-002b**: Amendment MUST operate at the **task** level: it supersedes every
  evidence record currently attached to the task — all of them, when the task
  carries several — and leaves exactly one current record afterwards. The command
  MUST NOT accept an evidence identifier to narrow the correction to one record.
- **FR-003**: The system MUST NOT provide any path that returns a `DONE` task to
  `IN_PROGRESS` or `PENDING`.
- **FR-004**: An amendment record MUST carry, at minimum: the corrected evidence,
  the operator-supplied reason, its own timestamp, and an unambiguous marker
  distinguishing it from evidence recorded at close time.
- **FR-005**: The system MUST refuse to amend a task that is not `DONE`, that is
  unknown, or that is invoked without a reason or with evidence violating the
  evidence grammar — refusing before any write.
- **FR-006**: Surfaces that present a task's evidence MUST render the current
  value as an amendment when it is one — never as an original close — and MUST make
  the superseded records reachable, so the ledger reads as "claimed X, later
  verified Y" rather than as a task that simply recorded Y.
- **FR-006a**: When an existing surface **inherits** a task's evidence rather than
  being given its own — closing a review finding with automatic evidence takes the
  task's recorded string — and that inherited value is an amendment, the inheriting
  record MUST carry the amendment provenance. An amended value MUST NOT become
  unmarked evidence by passing through another record.
- **FR-007**: The system MUST NOT evaluate, score, or gate on the content of an
  amendment's reason.
- **FR-008**: `reconcile` MUST accept an amended ledger — an amendment MUST NOT
  introduce a state the integrity check rejects.

**Active-feature pointer (US2)**

- **FR-009**: The system MUST provide a command that repoints the active feature
  to a named feature directory.
- **FR-009a**: The system MUST resolve the active feature using the **same
  precedence Spec Kit uses**: an explicit environment override first, then the
  pointer file. SpecOps and Spec Kit MUST NOT be able to resolve different features
  from the same repository state.
- **FR-010**: Repointing MUST validate that the target directory exists, lies
  within the repository's specs directory, and carries a specification artifact;
  it MUST refuse otherwise, leaving the pointer untouched.
- **FR-010a**: Repointing MUST refuse when an environment override is in effect and
  names a directory other than the requested target, because writing the pointer
  would have no effect on resolution. The refusal MUST name the override as the
  reason and state how to clear it. It MUST NOT report success on a repoint that
  cannot take effect.
- **FR-011**: Repointing MUST report the previously resolved directory and the
  newly resolved directory, and MUST be idempotent when the target is already
  active.
- **FR-012**: Repointing MUST report — without failing — which of the expected
  downstream artifacts (plan, tasks, ledger) are not yet present at the target.
- **FR-012a**: When the outgoing feature has unfinished work — a task in progress
  or an open review round — repointing MUST report that state as part of its
  success output. It MUST NOT refuse, MUST NOT require an override, and MUST NOT
  judge whether leaving that work is appropriate.
- **FR-013**: Feature initialization MUST leave the active pointer resolving to
  the feature it initialized.
- **FR-014**: The ledger summary command MUST echo the **resolved feature
  directory**, completing the resolved-feature echo already shipped for the two
  gate commands.
- **FR-014a**: When neither an override nor the pointer file resolves a feature and
  the system falls back to inferring one, that inference MUST be reported as an
  inference wherever the resolved feature is echoed. The fallback MUST NOT be
  removed (existing repositories depend on it) and MUST NOT be silent.

**Renaming (US3)**

- **FR-015**: The system MUST provide a command that renames a feature, moving the
  feature directory and its artifacts to the new name.
- **FR-016**: The rename MUST carry the feature's ledger identity to the new name,
  preserving every existing record (tasks, evidence, acknowledgements, review
  cycles, revision history) unchanged.
- **FR-016a**: The rename MUST update the structured identity header that SpecOps
  owns in the specification artifact (the feature-branch header) to the new name,
  and MUST NOT rewrite any other artifact prose.
- **FR-016b**: The rename MUST report every remaining occurrence of the old feature
  name or old branch name found in the moved artifacts — with file and location —
  as informational output, leaving each unchanged for the operator to judge. A
  remaining occurrence MUST NOT fail the rename.
- **FR-017**: The rename MUST update the ledger's branch reference when the
  operator supplies the new branch name, and MUST leave it unchanged — stating so
  — when they do not.
- **FR-018**: The rename MUST repoint the active feature when the renamed feature
  was the active one, and MUST leave the pointer untouched otherwise, stating
  which happened.
- **FR-019**: The rename MUST refuse when the target name already exists, when the
  source is not a feature directory, or when the target lies outside the specs
  directory — changing nothing.
- **FR-019a**: The rename MUST refuse when an environment override names the source
  directory, because completing it would leave the override — which outranks the
  pointer file — aimed at a directory that no longer exists. The refusal MUST name
  the override and state how to clear it. This is FR-010a's guarantee applied to the
  operation that can *invalidate* an override rather than be overridden by one.
- **FR-020**: A rename that cannot complete MUST leave the feature in its
  pre-rename state; it MUST NOT leave a partially moved directory or a pointer
  aimed at a non-existent directory.

**Cross-cutting**

- **FR-021**: Every command introduced here MUST exit non-zero with a stated
  reason on every precondition failure, within the frozen closed exit-code set —
  no refusal may exit zero (the #72 invariant).
- **FR-022**: Any persisted-format change required by the amendment record MUST be
  additive and MUST ship with a forward migration, so ledgers written before this
  feature keep loading and keep their meaning.
- **FR-023**: The system MUST NOT infer or reconstruct what an interrupted session
  intended to record; every correction is explicitly supplied by the operator.
- **FR-024**: The new commands MUST be documented in the command reference and in
  both the English and Portuguese user-facing documentation, equivalently.
- **FR-025**: The injected agent directives MUST present amendment as a **recovery**
  move: available to correct a record left by a previous session, and explicitly not
  a way to revise a close made in the current run. The directives MUST state that
  restriction, not merely omit the use.
- **FR-026**: The system MUST NOT enforce FR-025 mechanically — it MUST NOT infer
  which session closed a task or refuse an amendment on that basis. The restriction
  is instructional; the ledger's defence is that every amendment is recorded with
  its reason (Principle IV: record, do not validate).

### Key Entities

- **Evidence amendment**: an appended record correcting the evidence of an
  already-closed task. Carries the corrected evidence, the operator's reason, its
  own timestamp, and its amendment marker. It becomes the task's single current
  evidence and displaces every previously current record into superseded history —
  their content is never altered or removed.
- **Active-feature pointer**: the repository-level selection of which feature every
  command answers about. Currently readable-only; this feature makes it writable
  through commands and readable in command output.
- **Feature identity**: the feature's name as it appears in its directory name, in
  its ledger, and in the branch the ledger records. A rename is the operation that
  moves all three together.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A task closed with wrong evidence can be corrected without any hand
  edit of the ledger and without reopening the task — the number of recovery
  paths that require editing `status.yaml` by hand drops to zero.
- **SC-002**: After any number of amendments, 100% of the evidence records
  previously attached to a task are still present with their original content and
  timestamps; zero records are removed or rewritten, and exactly one is current.
- **SC-003**: Every surface that renders an amended task's evidence identifies the
  amendment as an amendment — zero amended closes are presented as original ones.
- **SC-004**: No amended evidence value reaches any record or output without its
  amendment provenance — including values inherited by another record rather than
  supplied directly.
- **SC-005**: A newly initialized feature is validated by the consistency check
  with zero hand edits of the active-feature pointer.
- **SC-006**: 100% of repoints that leave unfinished work behind say so in their
  output; zero such repoints are silent, and zero are refused.
- **SC-007**: For any repository state, SpecOps and Spec Kit resolve the same active
  feature in 100% of cases; zero repoints report success without taking effect.
- **SC-008**: A renamed feature retains 100% of its prior ledger records and passes
  both the integrity check and the consistency check under its new name; 100% of the
  old-name occurrences remaining in its artifacts are reported, and 0% of artifact
  prose is rewritten by the command.
- **SC-009**: 100% of the refusal paths of the new commands exit non-zero with a
  stated reason; zero refusals exit zero.
- **SC-010**: Every injected directive that mentions amendment states the
  recovery-only restriction; zero directives present it as a routine corrective step.
- **SC-011**: 100% of ledgers written before this feature load, migrate, and behave
  identically afterwards on every pre-existing command.

## Assumptions

- **SpecOps does not perform Git write operations.** Its Git access is read-only
  today (ancestry, diffs, status), and this feature keeps it that way: `feature
  rename` records the branch name the operator supplies but never renames a Git
  branch itself. Renaming the branch stays the operator's action, taken with Git.
- **Amendment covers evidence, not commits.** Commit attribution on a closed task
  already has a supported path (`trace link`, which accepts `DONE` tasks); this
  feature does not duplicate it.
- **`DONE` is terminal by design.** Amendment-only is deliberately chosen over
  reopening so a bad close cannot be quietly laundered into a good one. This is a
  scope boundary, not a limitation to be relaxed later without an explicit decision.
- **Spec Kit has no rename or renumber concept**, so nothing here duplicates or
  conflicts with it: Spec Kit re-resolves the feature from the pointer on every run
  and derives the branch label from the feature directory's basename, which means a
  rename that moves the directory and the pointer together is transparent to it.
- **A specification artifact is the minimum evidence of a feature directory.**
  `feature use` requires it and reports (without failing) the absence of the
  plan/tasks/ledger artifacts, because pointing at a feature *before* planning it
  is the normal flow this command exists to support.
- **The amendment record reuses the existing structured-evidence record shape**,
  extended additively with its reason and amendment marker, rather than
  introducing a parallel correction store — the ledger already has an append-only,
  id-addressable evidence history.
- **No change to the deterministic gate suite or the review loop** is in scope;
  the commands here are recovery operations, not gates. The directive templates do
  change, but only to *describe* amendment as a recovery move — no step is added to
  any workflow, and no gate consults an amendment.
- **The recovery-only restriction on amendment is instructional, not enforced.**
  SpecOps has no notion of "which session" closed a task and will not acquire one;
  the restriction lives in the directives, and the audit trail — every amendment
  carrying its reason — is what makes a misuse visible rather than prevented.
- **No automatic recovery.** No command scans for suspicious closes, proposes
  amendments, or repairs a pointer on its own.
