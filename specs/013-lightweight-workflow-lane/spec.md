# Feature Specification: Lightweight Workflow Lane

**Feature Branch**: `013-lightweight-workflow-lane`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "Add a human-confirmed lightweight workflow lane for small reversible changes, with minimal branch-based state, explicit high-risk stop-and-ask gates, retrospective closure evidence, and lossless promotion to the full feature workflow when risk or scope grows."

## Clarifications

### Session 2026-07-24

- Q: Where should the lane's minimal execution state live? → A: A dedicated lightweight lane record (its own file/schema, e.g. `lane.yaml`), NOT `status.yaml`. No full ledger is created during the lane; promotion synthesizes a full `status.yaml` from the lane record plus branch history.
- Q: When a lane is promoted to the full workflow, at which phase does the full `specops` lifecycle resume? → A: At PLAN. The promoted change receives real spec/plan/review; the lane's branch commits are imported as already-existing work and the retrospective seeds context, so nothing is lost and the now-non-trivial change gets full scrutiny before it can reach DONE.
- Q: 'Ambiguous/unconfirmed root cause' is not mechanically detectable from a diff — how is that safety category enforced? → A: Hybrid. SpecOps deterministically flags the five diff-detectable categories (schema/migration, secrets, dependency manifests, public-contract surfaces, destructive operations) AND the lane always presents one explicit human attestation checkpoint for root-cause ambiguity; an "ambiguous" attestation halts (promote/stop). Nothing safety-critical rests solely on mechanical detection.
- Q: How is the lane operated — who drives the `specops lane` CLI, and how is the lane entered? → A: The human NEVER drives the `specops` CLI. The lane is delivered via BOTH a Principle IV **injected directive** and the `specops-lite` **workflow**: the injected directive makes the agent recognize a small/reversible change and PROPOSE the lane through a human-confirmed stop-and-ask (never auto-classifying); on confirmation the agent/workflow engine drives every `specops lane *` command as native `shell`/`command` steps. The human's only interactions are the native stop-and-ask gates — eligibility confirmation, root-cause attestation, and the halt/promote choice. The `specops lane` CLI is an agent/workflow-facing deterministic surface, not a human workflow.

## User Scenarios & Testing *(mandatory)*

<!--
  The lightweight lane is a SECOND SpecOps-provided Spec Kit workflow definition
  (`specops-lite`, installed via `specify workflow add`), composed of native step types only.
  It sits ALONGSIDE the full `specops` lifecycle workflow for changes too small to justify the
  full specify → plan → tasks → implement → review ceremony. It is the "paved road" made
  proportional: less ceremony for small reversible work, the same non-pierceable safety
  core, and every departure from the lane recorded rather than silently taken.

  OPERATING MODEL (see Clarifications — Session 2026-07-24): the human never drives the
  `specops` CLI. A Principle IV injected directive makes the AGENT recognize a small/reversible
  change and PROPOSE the lane (a human-confirmed stop-and-ask, never auto-classifying); on
  confirmation the agent/workflow engine drives every `specops lane *` command as native steps.
  The human's ONLY touchpoints are the native stop-and-ask gates: eligibility confirmation,
  root-cause attestation, and (if something trips) the halt/promote choice. Where "the developer"
  appears below, read it as "the human at a native gate"; where a `specops lane` command appears,
  the agent/engine issues it, not the human.
-->

### User Story 1 - Complete a small reversible change with proportional ceremony (Priority: P1)

A human asks their agent for a small, reversible change (a typo fix, a copy tweak, a small
non-contract-breaking refactor, a config default). Guided by the injected lightweight-lane
directive, the agent recognizes the change as a lane candidate and proposes the lightweight
lane instead of the full specify → plan → tasks → implement → review lifecycle. The human
confirms eligibility at a native gate (explicit, human-answered criteria — SpecOps never
auto-classifies); the agent then does the work on a branch using ordinary commits as the working
record and drives the `specops lane` lifecycle end-to-end. At closure the agent's `specops lane
close` step runs the applicable deterministic gate profiles and produces a concise retrospective
plus evidence. The change lands with materially less process than a full feature, the human
touched only the eligibility (and root-cause attestation) gate, and it is still auditable.

**Why this priority**: This is the reason the feature exists — a proportional lane so
small work is not forced through full-feature ceremony (the adoption thesis), driven by the
agent so the human is not conducting a CLI. It is the minimum viable slice: without it there is
no lane. Every other story protects or extends this one.

**Independent Test**: Run the `specops-lite` workflow against a fixture repository for a small
change; confirm eligibility at the gate; let the agent/engine drive the lane through one or more
commits to closure. Verify the run completes without creating spec/plan/tasks phase artifacts or
opening an independent review cycle, that no human-issued `specops` command was required, and
that a closure retrospective plus deterministic gate evidence is produced.

**Acceptance Scenarios**:

1. **Given** a repository with a small reversible change as branch commits and no high-risk
   category touched, **When** the human confirms eligibility and the agent/engine drives the
   `specops-lite` lane, **Then** the lane completes without generating spec.md, plan.md, or
   tasks.md and without opening a review cycle, and records a lane closure.
2. **Given** a lane in progress, **When** execution state is inspected, **Then** the working
   record is the branch's own commit history (no per-task ledger entries are required during the
   lane), and SpecOps holds a single minimal lane record.
3. **Given** a completed lane, **When** the closure evidence is inspected, **Then** it contains
   the retrospective and the deterministic gate-profile results for the change.
4. **Given** the lane runs end-to-end, **When** the human's interactions are tallied, **Then**
   the human issued no `specops` CLI command — only native gate answers (eligibility, root-cause
   attestation, and any halt/promote choice).

---

### User Story 2 - The non-pierceable safety core still halts high-risk work (Priority: P1)

While working in the lightweight lane, the developer (or agent) makes a change that
touches a safety-critical category: a persisted-schema/data migration, a secret, a public
contract break, a dependency change, a destructive or irreversible action, or a fix on an
ambiguous/unconfirmed root cause. The lane STOPS and asks a human. This checkpoint is part
of SpecOps's minimal non-pierceable core: it cannot be satisfied by recording a bypass
reason — the human must decide to halt, or to promote to the full workflow. The lane never
silently absorbs safety-critical work.

**Why this priority**: A lighter lane is only acceptable if it never lets safety-critical
work slip through with reduced scrutiny. This is the guarantee that makes proportional
ceremony safe; it is co-equal P1 with the lane itself.

**Independent Test**: In a fixture repository, introduce a change in each of the five
diff-detectable high-risk categories one at a time inside the lane and confirm each triggers a
stop-and-ask that halts and offers halt-or-promote; separately confirm the lane always presents
the root-cause attestation checkpoint and that an "ambiguous" answer halts the same way — with
no record-a-reason path allowing the lane to continue past any of them unchanged.

**Acceptance Scenarios**:

1. **Given** a lane in progress, **When** a change touches any of the five diff-detectable
   high-risk categories, **Then** SpecOps deterministically flags it and the lane halts at a
   stop-and-ask checkpoint, not proceeding to closure until a human resolves it.
2. **Given** a lane reaching a stop-and-ask, **When** the human is offered options, **Then** the
   offered resolutions are halt or promote to the full workflow — never a "record reason and
   continue in the lane" bypass.
3. **Given** a change whose root cause is not mechanically detectable, **When** the lane presents
   its always-on root-cause attestation checkpoint and the human answers "ambiguous", **Then**
   the lane halts exactly as a detected category does.
4. **Given** the same high-risk detection, **When** the deterministic gate profiles are
   applicable, **Then** they are still executed (the lane grants no gate-profile bypass).

---

### User Story 3 - Lossless promotion to the full feature workflow (Priority: P1)

Partway through the lightweight lane, the change turns out to be bigger or riskier than
expected (a stop-and-ask fired, or scope grew). The human chooses **promote** at the native
halt/promote gate, and the agent runs the promotion (`specops lane promote`). Promotion
preserves every commit already made on the branch and the context gathered so far, synthesizing
the full feature ledger and handing off to the `specops` lifecycle so the change now receives
full planning, review, and audit — with no lost commits and no lost history.

**Why this priority**: The acceptance gate requires that scope/risk expansion is "detected
and promoted without losing audit history." Promotion is what makes entering the lane safe:
choosing the lane is never a trap, because the escape hatch is lossless. P1.

**Independent Test**: In a fixture repository, start a lane with several commits, trigger
promotion, and verify the full feature ledger is created at the PLAN phase, all pre-promotion
commits remain reachable on the branch, the recorded lane context carries over, and the full
`specops` workflow can continue from the promoted state.

**Acceptance Scenarios**:

1. **Given** a lane branch with N commits, **When** the human chooses promote and the agent runs
   `specops lane promote`, **Then** all N commits remain reachable on the branch after promotion
   (zero commit loss).
2. **Given** a promoted lane, **When** the full feature ledger is inspected, **Then** it exists,
   is positioned at the PLAN phase, and carries the lane's recorded context (eligibility answers,
   stop-and-ask decisions, evidence gathered) rather than starting empty.
3. **Given** a stop-and-ask checkpoint that offered halt-or-promote, **When** the human
   chooses promote, **Then** promotion runs the same lossless path as a scope-driven
   promotion.

---

### User Story 4 - Concise retrospective and evidence at closure (Priority: P2)

When a lane closes normally, SpecOps produces a concise retrospective artifact (what changed
and why, the eligibility basis, any stop-and-ask decisions) and attaches the deterministic
gate-profile evidence for the change. A reviewer or auditor can later understand a
lightweight change and see that its applicable gates passed, without the change having gone
through full-feature artifacts.

**Why this priority**: Auditability of the lighter lane. It extends US1's closure into a
durable, inspectable record. Independent of the lane mechanics themselves, so P2.

**Independent Test**: Close a lane and inspect the produced retrospective and evidence;
confirm both are present, machine-readable where applicable, and reference the change's
commits and gate-profile outcomes.

**Acceptance Scenarios**:

1. **Given** a normally closed lane, **When** its closure record is inspected, **Then** a
   retrospective artifact and structured gate evidence are present and reference the change's
   commits.
2. **Given** a lane where an optional gate was skipped or unavailable, **When** closure
   records evidence, **Then** each gate's disposition and reason are captured (consistent
   with the existing gate-profile evidence taxonomy).

---

### User Story 5 - Bundle adjacent reversible changes under human supervision (Priority: P3)

A developer has several small, adjacent, reversible changes that naturally belong together.
Under explicit human supervision they bundle them into a single lightweight-lane pass rather
than opening a lane per change, keeping ceremony proportional while the safety core still
evaluates the combined change set.

**Why this priority**: A convenience that reduces overhead for clustered small work. Valuable
but not required for the lane to deliver its core value; the safety core and promotion must
already exist for bundling to be safe. P3.

**Independent Test**: In a fixture repository, bundle two adjacent reversible changes in one
lane pass, confirm the human confirmation is required for the bundle, the safety core
evaluates the combined set, and closure produces one retrospective covering the bundle.

**Acceptance Scenarios**:

1. **Given** two adjacent reversible changes, **When** the developer bundles them into one
   lane with explicit confirmation, **Then** the lane treats them as a single closable unit
   and the safety core evaluates the combined change set.
2. **Given** a bundle where one change trips a high-risk category, **When** the safety core
   evaluates it, **Then** the whole bundle halts at the stop-and-ask checkpoint (the bundle
   is not partially completed around the risky change).

---

### Edge Cases

- **Ineligible from the start**: the developer tries to use the lane but the change already
  touches a high-risk category (e.g., a migration). The eligibility confirmation surfaces
  this and the lane is not entered; the developer is directed to the full workflow.
- **Risk appears only at closure**: a high-risk category is first detected at the closure
  gate rather than mid-lane. Closure does not complete; the developer is offered
  halt-or-promote, same as a mid-lane trip.
- **Gate profile unavailable**: an applicable deterministic gate cannot run (tool missing).
  Its disposition is recorded per the existing taxonomy; a *required* gate that cannot run
  blocks closure (no silent pass), consistent with the full lane.
- **No workflow engine / no context map present**: the lane degrades safely — the SpecOps CLI
  pieces (eligibility, safety-core check, closure, promotion) still function, and any optional
  capability that is absent is treated as absent, not as a failure.
- **Promotion of an empty lane**: promoting a lane with zero commits still produces a valid
  full feature ledger and loses nothing (there is nothing to lose).
- **Abandoned lane**: a lane started but never closed leaves the branch and its minimal lane
  record intact; it can be resumed, closed, or promoted later without corruption.
- **Reversibility disputed**: the developer asserts a change is reversible but it is not
  (touches a high-risk category). The safety core, not the developer's assertion, governs —
  the stop-and-ask fires regardless of the eligibility answer.

## Requirements *(mandatory)*

### Functional Requirements

**Lane definition and composition**

- **FR-001**: SpecOps MUST provide the lightweight lane as a Spec Kit workflow definition
  installed via the native workflow mechanism (`specify workflow add`), composed of native
  step types (`gate`, `prompt`, `shell`, `command`, `if`, …) only. SpecOps MUST NOT build a
  separate lane orchestrator, engine, loop, or resume mechanism (Roadmap Rule 8; Principle I).
- **FR-002**: The lane MUST coexist with the full `specops` lifecycle workflow without
  altering or replacing it; a repository MAY run either.

**Operating model & agent recognition (Principle IV)**

- **FR-022**: The human MUST NOT be required to invoke any `specops` CLI command to run the
  lane. Every `specops lane *` command MUST be issued by the agent or the workflow engine as
  native `shell`/`command` steps; the human's only interactions MUST be native stop-and-ask
  `gate`/`prompt` steps (eligibility confirmation, root-cause attestation, and the halt/promote
  choice). The `specops lane` CLI is an agent/workflow-facing deterministic surface.
- **FR-023**: SpecOps MUST deliver a Principle IV **injected directive** (a product template,
  installed via the extension mechanism like the existing lifecycle directives) that makes the
  agent (a) recognize when a requested change is a lightweight-lane candidate and (b) PROPOSE the
  lane to the human through a confirmation gate before proceeding — it MUST NOT auto-classify or
  auto-enter the lane. On human confirmation the agent drives the `specops-lite` workflow. The
  directive MUST degrade to a no-op when SpecOps is not initialized (Roadmap Rule 5), leaving the
  underlying Speckit prompt working standalone.

**Eligibility (human-confirmed, never auto-classified)**

- **FR-003**: Entering the lane MUST require an explicit human confirmation of eligibility
  against documented criteria (small, reversible, no high-risk category touched). SpecOps MUST
  NOT automatically classify a change as lightweight without that confirmation.
- **FR-004**: The eligibility criteria presented to the human MUST be explicit and
  deterministic (the same criteria for the same context), so the confirmation is a decision
  against a stable checklist, not an open-ended judgment.

**Minimal branch-based state**

- **FR-005**: The lane's working execution record MUST be the branch's own Git commit history
  until closure; the lane MUST NOT require per-task ledger entries or phase transitions during
  the work.
- **FR-006**: SpecOps MUST record a single minimal lane record in a dedicated lightweight
  store (its own file/schema, e.g. `lane.yaml`), separate from and NOT reusing the full
  `status.yaml` ledger, and MUST NOT create a full `status.yaml` while the lane is open. The
  lane record (lane opened → resolved: closed or promoted) captures the eligibility
  confirmation, any stop-and-ask decisions, and the closure/promotion outcome, so the lighter
  lane is still auditable.

**Non-pierceable safety core (stop-and-ask)**

- **FR-007**: The lane MUST halt and ask a human (a stop-and-ask checkpoint) when a change
  touches any of the safety-critical categories: persisted-schema/data migration, secrets,
  public-contract break, dependency change, destructive/irreversible action, or a fix on an
  ambiguous/unconfirmed root cause. Enforcement is **hybrid**: SpecOps MUST deterministically
  flag the five diff-detectable categories (schema/migration, secrets, dependency manifests,
  public-contract surfaces, destructive operations) from the change, AND the lane MUST always
  present one explicit human attestation checkpoint for root-cause ambiguity — which cannot be
  detected from a diff. An "ambiguous" attestation halts exactly as a detected category does. No
  safety-critical category may rest solely on mechanical detection.
- **FR-008**: These stop-and-ask checkpoints MUST NOT be satisfiable by recording a bypass
  reason. The only resolutions offered MUST be halt or promote to the full workflow — the
  checkpoint is part of the minimal non-pierceable core, not the recordable paved road.
- **FR-009**: The lane MUST NOT grant any bypass for applicable deterministic gate profiles;
  gate profiles that apply to the change MUST still run (Roadmap non-goal; Principle IV).
- **FR-010**: The lane MUST NOT include a formal independent review cycle; the semantic review
  cycle and its structured findings belong to the full workflow, and the lane's scrutiny is
  the eligibility confirmation plus the safety core plus the deterministic gates.

**Closure: retrospective + evidence**

- **FR-011**: On normal closure the lane MUST run the applicable deterministic gate profiles
  and MUST record their outcomes using the existing structured gate-evidence taxonomy
  (disposition, reason, covered inputs, evidence id).
- **FR-012**: On normal closure the lane MUST produce a concise retrospective artifact
  summarizing the change, the eligibility basis, and any stop-and-ask decisions, referencing
  the change's commits.
- **FR-013**: Closure MUST fail closed when a *required* gate profile fails or cannot run (no
  silent completion), consistent with the full lane's fail-closed behavior.

**Lossless promotion**

- **FR-014**: SpecOps MUST support promoting an in-progress or closable lane to the full
  feature workflow such that every commit already on the branch remains reachable after
  promotion (zero commit loss).
- **FR-015**: Promotion MUST synthesize the full feature ledger (`status.yaml`) from the
  dedicated lane record plus the branch history, carrying over the lane's recorded context
  (eligibility answers, stop-and-ask decisions, gathered evidence) so the full workflow
  continues from the promoted state rather than starting empty. The synthesized ledger MUST
  resume the full `specops` lifecycle at the **PLAN** phase: the lane's branch commits are
  imported as already-existing work, and the promoted change then flows through
  plan → tasks → implement → review before it can reach DONE, so a change that outgrew the lane
  receives full planning and review scrutiny.
- **FR-016**: A stop-and-ask "promote" resolution and a scope-driven "promote" MUST use the
  same lossless promotion path (one promotion mechanism, two triggers).

**Bundling**

- **FR-017**: The lane MUST permit bundling adjacent reversible changes into a single pass only
  under explicit human confirmation, and the safety core MUST evaluate the combined change set
  (a high-risk category in any bundled change halts the whole bundle).

**Cross-cutting (constitution / roadmap invariants)**

- **FR-018**: Every SpecOps CLI action added for the lane MUST return exit code 0 on success
  and non-zero on blocking failure, with no interactive prompts, so each composes as a gate
  (Principle VI). Human interaction is expressed through native workflow `gate`/`prompt` steps,
  not CLI prompts.
- **FR-019**: The lane and its CLI pieces MUST degrade safely when an optional context map,
  workflow engine, or integration capability is absent, and MUST preserve offline operation
  after installation (Roadmap Rules 5–6).
- **FR-020**: The lane MUST remain domain-agnostic — all client-specific behavior (test/lint
  commands, gate profiles, skills dir) enters through existing configuration, never
  stack-specific logic in the lane (Principle V).
- **FR-021**: Lane-related commands and the workflow definition MUST use the post-017
  vocabulary — the deterministic gate is `specops preflight`; "review" refers to the phase, the
  `/specops-review` directive, and the verdict, and MUST NOT be used to name any lane gate.

### Key Entities *(include if feature involves data)*

- **Lane record**: the single minimal record SpecOps keeps for a lightweight-lane pass, held in
  a dedicated lightweight store (its own file/schema, e.g. `lane.yaml`) — never the full
  `status.yaml`. Captures the eligibility confirmation and its criteria basis, any stop-and-ask
  decisions and their resolutions, and the terminal outcome (closed or promoted). Its working
  detail is the branch commit history, not a per-task ledger. On promotion it is the source from
  which the full `status.yaml` is synthesized.
- **Eligibility criteria**: the explicit, deterministic checklist a human confirms to enter the
  lane (small, reversible, no high-risk category). Distinct from the safety core, which
  re-checks continuously during the lane.
- **Stop-and-ask checkpoint**: a non-pierceable halt tied to a safety-critical category,
  resolvable only by halt or promote. Not recordable as a bypass.
- **Retrospective artifact**: the concise closure summary of a lightweight change (what/why,
  eligibility basis, stop-and-ask decisions, commit references).
- **Closure evidence**: the structured deterministic gate-profile results for the change,
  recorded in the existing gate-evidence taxonomy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A small reversible change can be completed through the lane with strictly fewer
  required process artifacts than the full workflow — zero of {spec.md, plan.md, tasks.md} and
  no opened review cycle are required for a lane change, versus all of them in the full
  lifecycle.
- **SC-002**: 100% of changes touching any of the five diff-detectable safety-critical
  categories are flagged and halt the lane; the always-on root-cause attestation checkpoint is
  presented on 100% of lane passes and an "ambiguous" answer halts in 100% of cases; 0% of any
  safety-critical trigger can proceed to lane closure by recording a bypass reason.
- **SC-003**: Promotion preserves 100% of pre-promotion branch commits (zero commit loss) and
  results in a full feature ledger populated with the lane's recorded context in 100% of
  promotions.
- **SC-004**: 100% of normally closed lanes produce both a retrospective artifact and
  deterministic gate evidence for the change.
- **SC-005**: 100% of applicable required gate profiles are executed at closure; a required gate
  failure or unavailability blocks closure in 100% of cases (no silent pass).
- **SC-006**: The lane and its CLI pieces operate fully offline after installation and produce
  no failure solely due to an absent optional context map, workflow engine, or integration in
  100% of such cases (safe degrade).
- **SC-007**: A user unfamiliar with the lane can complete a small change end-to-end without
  consulting the full-lifecycle documentation, in a single sitting.
- **SC-008**: Across a full lane run (recognition → eligibility → work → closure or promotion),
  the human issues **zero** `specops` CLI commands — 100% of `specops lane *` invocations are
  agent/engine-issued and 100% of human interactions are native gate/prompt answers.

## Assumptions

<!--
  These are informed defaults chosen where the roadmap brief left detail open. They are the
  most likely intended reading given the Design Philosophy, the constitution, and the existing
  full `specops` workflow. Any of them is a fair target for /speckit-clarify.
-->

- **Delivery shape**: The lane ships as (a) a second workflow definition (working name
  `specops-lite`) under `src/specops/templates/workflows/`, installed alongside the full
  `specops` workflow via the native workflow mechanism — mirroring how Feature 016's full
  workflow is delivered — and (b) a Principle IV injected directive template under
  `src/specops/templates/directives/` that makes the agent recognize and propose the lane
  (FR-023), installed via the same extension mechanism as the existing lifecycle directives.
  SpecOps adds the eligibility, safety-core, closure, and promotion CLI primitives plus the lane
  record; the orchestration is native Spec Kit steps and the agent is guided by the directive.
  Adding a new Principle IV directive is a MINOR constitution amendment made during
  `/speckit-implement`, following the established pattern (the directive list under Principle IV
  is extended, no principle removed or redefined).
- **Ledger state model** *(resolved in Clarifications — Session 2026-07-24)*: "Minimal
  branch-based state" means the lane keeps a *single* lane record (open → resolved) in a
  dedicated lightweight store (its own file/schema, e.g. `lane.yaml`), NOT the full `status.yaml`
  ledger, and no `status.yaml` is created while the lane is open. The branch's commit history is
  the authoritative record of the work itself; promotion synthesizes a full `status.yaml` from
  the lane record plus that history.
- **Safety-core detection** *(resolved in Clarifications — Session 2026-07-24)*: Enforcement is
  hybrid. The five diff-detectable categories (migrations, secrets, dependency manifests,
  public-contract surfaces, destructive operations) are flagged deterministically from the change
  via paths/patterns; the one non-detectable category (ambiguous/unconfirmed root cause) is
  enforced by an always-on human attestation checkpoint. Both are surfaced to native
  `gate`/`prompt` steps and the human makes the halt-or-promote call. SpecOps records the
  decision but does not judge whether a given category truly applies beyond its deterministic
  signal — "record, do not validate" applies to the paved road, while the safety categories
  themselves are the non-pierceable core.
- **Promotion target** *(resolved in Clarifications — Session 2026-07-24)*: Promotion synthesizes
  the full feature ledger and hands the change to the full `specops` workflow **at the PLAN
  phase**, preserving the branch and its commits as existing work. A promoted change thus receives
  full planning and review before DONE; the spec-level guarantees are losslessness, populated
  context, and full downstream scrutiny.
- **"Reversible" definition**: Reversibility is anchored to the safety core — a change is
  ineligible/blocked if it touches any of the six categories, regardless of the developer's
  assertion. There is no separate size threshold (line/file counts) enforced by SpecOps; size is
  a human judgment at eligibility confirmation.
- **Retrospective format**: The retrospective is a concise structured artifact (human- and
  machine-readable) associated with the lane record, not a full-feature `revisions/` projection.
  Exact serialization is a plan-time detail.
- **Reuse over new surfaces**: Closure gate execution reuses the existing `specops preflight`
  gate-profile suite and the Feature 012 structured-evidence taxonomy rather than introducing a
  parallel evidence format.
- **Development discipline**: Per the No-Self-Application constraint, all lane behavior is proven
  by this feature's own tests against fixtures; the lane is never run against the SpecOps
  repository itself.
