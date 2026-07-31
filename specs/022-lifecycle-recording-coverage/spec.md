# Feature Specification: Lifecycle Recording Coverage

**Feature Branch**: `022-lifecycle-recording-coverage`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Define the SpecOps story for every lifecycle command: a converge directive with deterministic ledger append/rebaseline semantics and SC coverage tags, a verified read-only taskstoissues, and optional-step decision recording that works in both workflow-driven and slash-command runs including before the ledger exists — every decision recorded, no optional step made mandatory, fail closed on unrecorded task-list mutation, degrade to no-ops without SpecOps, and stay additive under the 1.0 contract freeze." (ROADMAP Feature 022, Lifecycle Coverage cycle)

## Clarifications

### Session 2026-07-31

- Q: O suporte a converge cobre apenas o uso standalone ou o workflow completo também ganha um passo de converge? → A: Standalone + passo no workflow — o workflow lane completo ganha um gate opcional de converge (run/skip) cuja decisão é registrada como as dos demais passos opcionais.
- Q: Quando o converge produz uma tarefa sem tag [SC-xxx], qual o comportamento do registro? → A: A diretiva exige que o agente tagueie antes de registrar; o caminho CLI registra como estiver — tarefa sem tag entra no ledger e aparece na checagem de consistência existente como cobertura faltante, sem bloquear (record, don't validate).
- Q: Onde acontece o fail-closed do converge sem caminho de registro? → A: Antes da mutação — precondição CLI determinística (exit code como gate) antes de mutar tasks.md; falha → stop-and-ask sem mutar; reconcile existente segue como backstop.
- Q: O que acontece com decisões pré-ledger de um run abandonado antes de tasks? → A: Descartadas com segurança — o ledger registra features que existem; um run novo começa limpo, sem registros órfãos que bloqueiem ou contaminem.
- Q: Como a verificação read-only do taskstoissues é sustentada? → A: Teste automatizado permanente na suíte — regressão em fixture verificando ledger byte-idêntico após o caminho taskstoissues, protegendo o contrato contra drift futuro.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Converge-appended tasks enter the ledger, or converge fails closed (Priority: P1)

A team runs `/speckit.converge` mid-feature to reconcile the task list with
what the codebase actually still needs: converge appends new tasks to an
existing `tasks.md`. Today that command has no SpecOps story — no directive,
no hook, undefined ledger behavior — so on a SpecOps-managed repository the
appended tasks silently diverge from the ledger: the physical state says one
thing, the task list another. With this feature, converge has a defined
recording story: appended tasks enter the ledger through a deterministic,
tool-owned path, carry success-criteria coverage tags, and then flow through
the normal task start/complete loop with reconciliation staying green. If the
recording path is unavailable, converge on a SpecOps-managed repository fails
closed with a specific diagnostic — divergence is never silent.

**Why this priority**: this is the data-integrity core of the feature. An
unrecorded task-list mutation breaks the ledger's claim to be the physical
state of record — every downstream surface (reconcile, traceability, review
evidence) inherits the lie. Nothing else in this feature matters if the
ledger can silently drift.

**Independent Test**: on a SpecOps-managed fixture with an active feature,
append tasks via the converge path and verify they enter the ledger with
coverage tags and complete the normal start/complete loop with
reconciliation green; then exercise converge with the recording path
unavailable and verify a specific, fail-closed diagnostic.

**Acceptance Scenarios**:

1. **Given** a SpecOps-managed repository with an active feature and an
   existing task list, **When** converge appends tasks, **Then** the appended
   tasks enter the ledger through a deterministic tool-owned path, carrying
   success-criteria coverage tags.
2. **Given** converge-appended tasks recorded in the ledger, **When** they are
   started and completed through the normal loop, **Then** the existing
   reconciliation gate stays green and the ledger matches the task list by
   construction of the recording path.
3. **Given** a SpecOps-managed repository where the recording path is
   unavailable or bypassed, **When** converge would mutate the task list,
   **Then** the operation fails closed with a specific diagnostic naming what
   was missing — the ledger is never left silently divergent.
4. **Given** the same converge input applied twice to the same state, **When**
   the recording path runs, **Then** the ledger outcome is deterministic —
   same tasks, same identities, no duplicate entries.

---

### User Story 2 - Optional-step decisions are recorded in every entry mode (Priority: P2)

A human decides whether to run or skip the optional lifecycle steps —
clarify, checklist, analyze. Today those decisions are recorded only when the
lifecycle runs workflow-driven, and even there through a seam that had to be
deferred because the decisions happen before the ledger exists (issue #50).
A team that runs the same lifecycle through slash commands gets no record at
all: an auditor cannot tell a deliberate skip from an overlooked step. With
this feature, run/skip decisions for all three optional steps are recorded in
**both** entry modes — workflow-driven and slash-command — through a
recording seam that works before the ledger exists. Recording is mandatory;
the step is not: a skip is a first-class recorded decision, and no entry mode
ever forces an optional step to run or blocks on a recorded skip.

**Why this priority**: decision parity is the feature's audit-trail promise —
the ledger should tell the same story regardless of how the lifecycle was
driven. It is second because no data is corrupted when a decision goes
unrecorded (unlike User Story 1); the record is merely incomplete.

**Independent Test**: on a SpecOps-managed fixture, drive one full lifecycle
workflow-driven and one via slash commands, in each mode choosing to skip
every optional step; verify both ledgers record all three decisions and both
runs complete without obstruction.

**Acceptance Scenarios**:

1. **Given** a workflow-driven run, **When** the human decides run or skip
   for clarify, checklist, and analyze, **Then** each decision is recorded in
   the ledger even though the decisions occur before the ledger exists.
2. **Given** a slash-command run of the same lifecycle, **When** the human
   makes the same decisions, **Then** the same three decisions end up
   recorded in the ledger — parity with the workflow-driven record.
3. **Given** a human who skips every optional step in either entry mode,
   **When** the lifecycle runs to completion, **Then** every skip is recorded
   as a first-class decision and the run completes without any block, retry,
   or forced execution of an optional step.
4. **Given** any entry mode, **When** an optional step's decision is
   recorded, **Then** recording never converts the step into a required one —
   record, do not validate.

---

### User Story 3 - taskstoissues has a verified, documented ledger story (Priority: P3)

A team runs `/speckit.taskstoissues` to publish the task list as tracker
issues. Today its relationship to the ledger is undefined — users cannot know
whether it is safe on a SpecOps-managed repository. With this feature, the
command is verified and documented as read-only with respect to ledger state;
if verification finds it is not read-only, it receives a trivial directive
that defines its recording story instead.

**Why this priority**: closing the last coverage gap makes "every lifecycle
command has a defined SpecOps story" true, but the command most likely
touches nothing — the work is verification and documentation, with the
directive only as a contingency.

**Independent Test**: on a SpecOps-managed fixture, run the taskstoissues
path and verify ledger state is unchanged afterward; verify the documentation
states the read-only contract.

**Acceptance Scenarios**:

1. **Given** a SpecOps-managed repository with an active feature, **When**
   taskstoissues runs, **Then** ledger state is unchanged — verified
   read-only.
2. **Given** the published documentation, **When** a user looks up
   taskstoissues, **Then** its ledger contract (read-only, or its trivial
   directive) is explicitly stated.

---

### Edge Cases

- **Converge on a repository without SpecOps initialized**: every new
  directive is a no-op (Rule 5) — converge behaves exactly as stock Spec Kit,
  no diagnostic, no failure.
- **Converge when some existing tasks are already completed**: recording must
  not disturb completed ledger entries; whether appended tasks extend the
  ledger in place or trigger a rebaseline is the append-vs-rebaseline
  decision made in this feature's plan — either way, prior completion records
  survive.
- **Converge appends zero tasks** (codebase already satisfies the spec): the
  recording path handles the empty append without error and the ledger is
  unchanged.
- **Appended task arrives without a coverage tag** (directive not followed):
  the recording path records it as given; the untagged task surfaces through
  the existing coverage/consistency reporting as missing coverage — visible,
  never blocking.
- **Decision recorded more than once for the same step** (e.g. a resumed
  workflow re-fires a recording step): repeated recording follows the
  existing idempotent re-run semantics — no duplicate or conflicting decision
  entries.
- **Optional-step decision in a repository that never reaches ledger
  creation** (run abandoned before tasks): pending decisions are **discarded
  safely** — the ledger records features that exist; a fresh run starts clean,
  with no orphaned partial records that block or contaminate it.
- **Lite-lane runs**: the lite lane has no clarify/checklist/analyze steps —
  decision-recording parity applies to the full lane's two entry modes; the
  lite lane is unchanged.
- **taskstoissues turns out not to be read-only**: the contingency directive
  path activates — its recording story is defined trivially rather than
  leaving the mutation undefined.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Converge MUST have a defined SpecOps recording story (directive
  and/or hook) under which tasks appended to an existing task list enter the
  ledger through a deterministic, tool-owned path; whether appended tasks
  extend the existing ledger baseline or trigger a rebaseline is decided in
  this feature's plan.
- **FR-001a**: The full workflow lane MUST offer converge as an optional step
  — a native run/skip gate in the corrective region of the workflow — whose
  decision is recorded through the same optional-step recording mechanism as
  clarify, checklist, and analyze; a converge decision point exists only where
  the workflow presents one (in slash-command mode, running converge is
  recorded through its recording path, and not running it records nothing).
- **FR-002**: Converge-appended tasks MUST carry success-criteria coverage
  tags and MUST reconcile cleanly: ledger↔task-list alignment holds by
  construction of the recording path (no new checker is introduced), the
  existing reconciliation gate (`specops reconcile`) remains green, coverage
  is reported by the existing consistency surface (`specops consistency`),
  and the appended tasks flow through the normal task start/complete loop. The tagging obligation sits in
  the directive (the agent tags each appended task before recording); the
  tool-owned recording path records tasks as given — an untagged task enters
  the ledger and surfaces through the existing coverage/consistency reporting
  as missing coverage, without blocking (record, do not validate).
- **FR-003**: On a SpecOps-managed repository, converge without the recording
  path MUST fail closed with a specific diagnostic naming the missing
  recording step — an unrecorded task-list mutation is never silent. The
  fail-closed happens **before mutation**: the directive runs a deterministic
  tool-owned precondition (exit code as gate) before converge touches the
  task list; on failure the run stops and asks without mutating, and the
  existing reconciliation check remains the backstop for any mutation that
  bypasses the directive entirely.
- **FR-004**: The converge recording path MUST record, not validate: it MUST
  NOT classify, judge, or filter the work converge appends.
- **FR-005**: `/speckit.taskstoissues` MUST be verified read-only with
  respect to ledger state and documented as such; if verification proves it
  is not read-only, it MUST receive a trivial directive defining its
  recording story. The verification is a permanent automated regression test
  in the suite (ledger state byte-identical on a fixture after the
  taskstoissues path), not a one-time analysis.
- **FR-006**: Run/skip decisions for the optional steps (clarify, checklist,
  analyze) MUST be recorded in the ledger in both entry modes —
  workflow-driven and slash-command.
- **FR-007**: The optional-step recording seam MUST work when decisions occur
  before the ledger exists — via buffering, earlier ledger creation, or
  retroactive recording at ledger initialization (mechanism decided in this
  feature's plan, building on the issue #50 fix). Whatever the mechanism,
  decisions pending when a run is abandoned before ledger creation are
  discarded safely (see Edge Cases) — the seam never persists orphaned state
  that a later run must honor or clean up.
- **FR-008**: Recording MUST never make an optional step mandatory: a skip is
  a first-class recorded decision, and no entry mode may force an optional
  step to run or block on a recorded skip.
- **FR-009**: The `--if-needed` asymmetry — idempotent engine re-runs in the
  workflow definition versus bare fail-closed transitions with stop-and-ask
  in the directives — MUST be documented as a deliberate contract.
- **FR-010**: All new behavior MUST degrade safely: on a repository without
  SpecOps initialized, every new directive is a no-op (Rule 5), and stock
  Spec Kit behavior is unchanged.
- **FR-011**: All changes MUST stay additive under the Feature 021 contract
  freeze — existing commands, fields, formats, and exit codes unchanged; if
  the plan requires a ledger schema change, it MUST ship with a migration per
  the post-1.0 versioning policy.
- **FR-012**: New directive/hook behavior MUST be delivered through the
  product templates so client repositories receive it on extension
  install/update (Principle IV); SpecOps MUST NOT reimplement converge or
  taskstoissues themselves (Rule 8) — only the recording, validation, and
  ledger layer.
- **FR-013**: English and Portuguese documentation MUST be updated
  equivalently in the same change.

### Key Entities

- **Converge-appended task record**: a ledger entry created for a task that
  converge appended to an existing task list — carries the task identity, its
  success-criteria coverage tags, and enters the same start/complete
  lifecycle as originally generated tasks.
- **Optional-step decision record**: the ledger record of a human run/skip
  decision for clarify, checklist, or analyze — identical in meaning
  regardless of which entry mode produced it.
- **Recording seam**: the mechanism that lets a decision made before the
  ledger exists still end up recorded in it (buffered, earlier creation, or
  retroactive — a plan-time choice); generalizes the issue #50 fix.
- **Entry mode**: how a lifecycle is driven — workflow-driven (the engine
  runs commands and native gates) or slash-command (a human invokes each
  lifecycle command directly); the ledger record must not reveal which one
  was used for optional-step decisions.
- **Converge directive**: the product-owned prompt asset that imposes the
  recording behavior on agents in client repositories; delivered through the
  extension mechanism like every other directive.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a SpecOps-managed fixture, 100% of converge-appended tasks
  enter the ledger and complete the normal start/complete loop with the
  existing reconciliation gate green; on the directive-followed path, 100%
  carry success-criteria coverage tags, and an untagged task is reported as
  missing coverage without blocking.
- **SC-002**: Converge on a SpecOps-managed fixture without the recording
  path produces a failure with a specific diagnostic in 100% of attempts —
  zero runs end with silent ledger divergence.
- **SC-003**: A full lifecycle run in either entry mode leaves all three
  cross-mode optional-step decisions (clarify, checklist, analyze) recorded
  in the ledger — the converge decision is additionally recorded where the
  workflow presents its gate (FR-001a) — including a run where the human
  skips every optional step, which completes with zero blocks, forced steps,
  or extra required actions.
- **SC-004**: taskstoissues on a SpecOps-managed fixture leaves ledger state
  byte-identical, verified by a permanent automated regression test in the
  suite, and its ledger contract is stated in the published documentation.
- **SC-005**: On a repository without SpecOps initialized, converge,
  taskstoissues, and the optional steps behave exactly as stock Spec Kit —
  zero new prompts, warnings, failures, or required actions.
- **SC-006**: No existing command, output field, format, or exit code changes
  shape; if a ledger schema change ships, existing ledgers migrate without
  data loss.
- **SC-007**: English and Portuguese documentation describe the new behavior
  equivalently in the same release.

## Assumptions

- The append-vs-rebaseline semantics for converge-appended tasks is a
  plan-time decision (per the roadmap); the spec constrains only its
  observable outcomes: deterministic, tagged, reconcile-green, prior
  completion records intact.
- The pre-ledger recording seam mechanism (buffered decisions, earlier ledger
  creation, or retroactive recording at ledger initialization) is a plan-time
  decision building on the issue #50 fix, which is already merged and defines
  the deferred-recording pattern this feature generalizes.
- Decision-recording parity concerns the full workflow lane's two entry
  modes; the lite lane has no clarify/checklist/analyze steps and is out of
  scope.
- No issue-tracker integration beyond what taskstoissues already does; no
  reimplementation of converge or taskstoissues (Rule 8) — SpecOps adds only
  the recording, validation, and ledger layer.
- No automatic classification or judgment of converge-added work — record,
  do not validate (Design Philosophy).
- The acceptance fixture strategy follows the established pattern: behavior
  is validated through the automated test-suite fixtures, never by running
  the tool against this repository (No Self-Application).
- Issues #51 (implement directive findings discovery) and #52 (commands.md
  review-summary drift) are independent defect fixes outside this feature's
  scope; #51 is already merged alongside the #50 fix.
