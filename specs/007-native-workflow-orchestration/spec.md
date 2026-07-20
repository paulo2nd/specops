# Feature Specification: Native Workflow Orchestration

**Feature Branch**: `007-native-workflow-orchestration`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Create a native, resumable Spec Kit workflow for the full SpecOps lifecycle, including requirements quality stages, a human planning readiness gate, deterministic CLI gates, corrective review loops, and ledger reconciliation. Do not implement a separate agent-dispatch abstraction in SpecOps."

## Complement Boundary *(mandatory context)*

SpecOps runs **inside** Spec Kit and is a **complement**, never a replacement. Spec Kit already ships a multi-step, **resumable** workflow engine (`specify workflow resume`) with native step types: `command`, `shell`, `prompt`, `gate` (human approve/reject with `on_reject`, pauses in CI for later resume), `do-while`/`while` (bounded loops via `max_iterations`), `if`/`switch` (branching), and `fan-out`/`fan-in`.

Therefore this feature does **not** build a workflow engine, a resume mechanism, a human gate, a loop, or a branching primitive. SpecOps contributes only what Spec Kit lacks:

1. An installable **workflow definition** that composes Spec Kit's native steps to run the SpecOps-augmented lifecycle.
2. **Ledger reconciliation** that keeps SpecOps's authoritative execution state aligned with what the workflow did.
3. A stable **CLI outcome contract** (exit codes / structured signals) so Spec Kit's native gate/loop/branch steps can drive SpecOps's deterministic state correctly.

## Clarifications

### Session 2026-07-20

- Q: How is the SpecOps workflow packaged relative to Spec Kit's bundled `speckit` workflow? → A: As an **additive, SpecOps-owned** workflow (named `specops`) registered by the SpecOps extension install (Feature 005), leaving the bundled `speckit` workflow **untouched** and invoked as `specify workflow run specops`. This corrects the earlier "extends/evolves the bundled workflow" framing, which would have violated Constitution Principle I (Speckit Extension, Never Replacement); the bundled workflow is used only as a design reference.
- Q: How are the optional quality steps (clarify, checklist, analyze) skipped when not applicable? → A: A **human decides at a native `gate`/`prompt` step, defaulting to run**; the run/skip choice is recorded in the ledger. There is no implicit auto-skip and no config-only toggle.
- Q: What is the remedy when reconciliation cannot align the ledger with the workspace (irreconcilable divergence)? → A: **Fail closed and reuse Feature 006's `rebaseline` escape hatch**; this feature adds **no** new override/repair command.
- Q (checklist review): What is the reconciliation cadence — after every step, or something more precise? → A: Reconciliation runs as a **fail-closed precondition of every state-changing ledger operation** and once immediately **after a `workflow resume`**; it does not run before purely read-only steps (FR-010 refined).
- Q (checklist review): Is the terminal fail-closed gate a deterministic verdict check or a human `gate`? → A: **Deterministic** — a `specops review`/verdict check that fails closed when the verdict is not `APPROVED`. It is **not** a human approve/reject gate (which could approve past a still-failing review); the human decides out-of-band after the halt (FR-019 refined).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and run the SpecOps-augmented lifecycle as one workflow (Priority: P1)

A maintainer using Spec Kit installs SpecOps and gets a ready-to-run lifecycle workflow definition. Running it drives a feature through specify, the requirements-quality stages (clarify, checklist), plan, task generation, cross-artifact analysis, implementation, and review — interleaving SpecOps's deterministic gates at the right points and pausing at a human readiness gate between planning and task generation. The maintainer does not hand-author any workflow wiring, and does not run the individual commands in order manually. Execution, resume, gates, and loops are provided by Spec Kit's engine; SpecOps supplies the definition that composes them.

**Why this priority**: This is the core deliverable and the minimum viable slice. A maintainer receiving a ready, integration-neutral definition that composes the lifecycle commands with SpecOps's deterministic gates — including the enforced readiness gate — already delivers value on its own, before reconciliation, corrective loops, or failure classification are hardened. Crucially, it is the slice that proves SpecOps adds only the definition, not a second orchestrator.

**Independent Test**: From a clean feature start, install SpecOps and run the shipped workflow; verify it proceeds through the lifecycle steps in order using the integration's registered commands, halts at the human readiness gate before task generation, generates tasks only after that gate is approved, and that no workflow-engine, resume, gate, or loop code was added to SpecOps to make this happen (the definition references only Spec Kit native step types plus SpecOps CLI calls).

**Acceptance Scenarios**:

1. **Given** a feature at the start of its lifecycle, **When** the maintainer runs the shipped SpecOps workflow, **Then** it drives the feature through specify, the applicable quality stages, plan, tasks, analyze, implement, and review as ordered steps using the integration's registered commands.
2. **Given** the definition is being executed, **When** a step runs, **Then** it is a Spec Kit native step type (`command`/`shell`/`gate`/`do-while`/`if`) — SpecOps contributes no engine of its own.
3. **Given** the workflow has completed planning, **When** it reaches the boundary before task generation, **Then** it halts at a Spec Kit `gate` step positioned by the SpecOps definition, and does not generate tasks until approved.
4. **Given** the human approves at the readiness gate, **When** the workflow continues, **Then** task generation proceeds and the SpecOps ledger advances to the task phase through a SpecOps CLI step.

---

### User Story 2 - Keep the SpecOps ledger authoritative and reconciled (Priority: P1)

As the workflow progresses under Spec Kit's engine — including after an interruption when the maintainer resumes with Spec Kit's own resume — SpecOps reconciles its execution ledger with the actual repository and workflow state. The ledger, not the workflow's navigational state, is the authoritative record of execution truth. Reconciliation ensures the ledger never silently drifts from what the workflow did: it advances only for steps that completed, and when the ledger and repository/workflow state cannot be safely reconciled, SpecOps fails closed and reports which dimension diverged instead of guessing or overwriting.

**Why this priority**: The ledger is the single source of execution truth that the rest of the roadmap writes into. If Spec Kit's engine can advance the workflow while the ledger drifts, later features (traceability, gate profiles) would build on corrupt state. Reconciliation is the genuinely SpecOps-specific guarantee — Spec Kit knows nothing about the ledger — so it ships alongside the definition as a second P1.

**Independent Test**: Advance a workflow (including interrupt-and-resume via Spec Kit) and verify the SpecOps ledger reflects exactly the completed steps; then deliberately make the ledger inconsistent with the repository/workflow state and verify reconciliation fails closed with a divergence diagnostic rather than advancing or overwriting.

**Acceptance Scenarios**:

1. **Given** a workflow advancing under Spec Kit's engine, **When** a step completes, **Then** SpecOps reconciles the ledger so it reflects the completed step, and the ledger remains the authoritative phase record.
2. **Given** a workflow resumed via Spec Kit's own resume, **When** SpecOps reconciles, **Then** the ledger is aligned with the actual repository/workflow state without SpecOps having implemented its own resume.
3. **Given** a ledger and a repository/workflow state that cannot be safely reconciled, **When** reconciliation runs, **Then** SpecOps fails closed and reports which dimension diverged.
4. **Given** a step that did not complete successfully, **When** reconciliation runs, **Then** the ledger phase is not advanced for that step.

---

### User Story 3 - Drive a bounded corrective loop from the review outcome (Priority: P2)

A feature reaches review and the SpecOps deterministic review gate rejects it. The shipped definition models correction as Spec Kit's native `do-while` loop: it routes the feature back into implementation and re-review, repeating while the review outcome is a rejection, up to the loop's `max_iterations` bound. Each corrective round is recorded in the SpecOps ledger as a new review cycle. The native `do-while` only bounds the number of iterations — when the bound is exhausted with the review still rejecting, the engine exits the loop and continues to the next step. So the definition places a **terminal deterministic gate** immediately after the loop — a `specops review`/verdict check that fails closed when the verdict is not `APPROVED`: a still-unapproved feature is halted there and can never fall through to completion, and the human decides out-of-band whether to resume correction or stop. SpecOps supplies the loop condition and the terminal gate through the review outcome; it does not build a loop.

**Why this priority**: The lifecycle must model rejection and correction as first-class flow, but it depends on the definition and the reconciliation already existing, so it follows the two P1 stories. Using Spec Kit's `do-while` (with its `max_iterations` cap) keeps SpecOps from reimplementing loop control, while the terminal gate — not the bare loop bound — is what prevents an unresolved rejection from reaching completion.

**Independent Test**: Force the SpecOps review gate to reject and verify the shipped definition loops back to implementation and re-review via Spec Kit's `do-while`, records a new ledger review cycle each round, and — if rejections persist until the loop bound is exhausted — is halted by the terminal fail-closed gate (not left to fall through) for a human decision; then verify a passing review outcome exits the loop and carries the feature to completion.

**Acceptance Scenarios**:

1. **Given** a rejected SpecOps review, **When** the definition's loop iterates, **Then** it routes back to implementation and re-review and records a new, strictly increasing review cycle in the ledger.
2. **Given** the loop re-enters review, **When** the review gate runs again, **Then** it produces a fresh outcome rather than reusing the prior rejected verdict.
3. **Given** the native loop reaches its `max_iterations` bound with the review still rejecting, **When** the loop exits and control passes to the next step, **Then** the terminal fail-closed gate halts the run for a human decision and the feature does not fall through to completion — SpecOps did not implement the bound, only the terminal gate.
4. **Given** a passing review outcome, **When** the loop condition is evaluated, **Then** the loop exits and the feature proceeds to completion; no path completes while the review is open or rejected.

---

### User Story 4 - Classify outcomes through a stable CLI contract (Priority: P2)

Three fundamentally different interruptions can occur during a run: a deterministic gate or human review deliberately rejects the work; a lifecycle step (an agent-run command) fails to execute; or the surrounding infrastructure fails (a required integration or SpecOps command is unavailable, an environment error). SpecOps's CLI steps expose a documented, stable outcome contract (distinct exit codes / structured signals) so the definition's native `gate`/`if`/`switch`/`do-while` conditions can branch each class to its own next action — correct, retry, or fix the environment — and so an execution or infrastructure failure is never recorded as a review rejection and never advances the ledger.

**Why this priority**: Conflating these failure modes sends operators to the wrong remedy and can corrupt the audit trail. But this refines the behavior of the paths defined in the earlier stories and is expressed through exit-code contracts rather than new orchestration, so it is P2.

**Independent Test**: Inject each class in turn — a deterministic gate rejection, a failed lifecycle step, and an unavailable-command infrastructure error — and verify SpecOps's CLI outcome contract reports each distinctly, that the native definition branches each to a distinct next action, and that in the execution-failure and infrastructure-error cases the ledger is not advanced and no review rejection is recorded.

**Acceptance Scenarios**:

1. **Given** a deterministic gate or human review rejects the work, **When** the CLI reports its outcome, **Then** it is signalled as a rejection that the definition routes into the corrective loop (User Story 3).
2. **Given** a lifecycle step fails to execute, **When** the failure surfaces, **Then** it is signalled as an execution failure distinct from a rejection, the ledger phase is not advanced, and the recommended next action is to retry the step (re-run or `specify workflow resume`) — not to record a review rejection.
3. **Given** a required integration or SpecOps command is unavailable, **When** the outcome is reported, **Then** it is signalled as an infrastructure/capability error, distinct from both rejection and execution failure, before any state mutation.
4. **Given** any execution failure or infrastructure error, **When** it occurs, **Then** it is never recorded as a review rejection and never advances the ledger's phase.

---

### Edge Cases

- **Optional quality step not applicable**: The clarify, checklist, or analyze stages are not needed for a feature. At each such step the definition presents a native `gate`/`prompt` (defaulting to run); if the human chooses to skip, the choice is recorded in the ledger and the run proceeds without failing — no implicit auto-skip.
- **Integration does not provide a required command**: The installed integration lacks a command the definition references. The run surfaces a missing-capability infrastructure error (via the CLI contract) before mutating state, rather than crashing or partially advancing.
- **Reject at the readiness gate**: The human rejects at the Spec Kit `gate` positioned before task generation. Per the gate's `on_reject`, the run does not generate tasks; it returns or aborts, and never proceeds to task generation on a rejected gate.
- **No initialized ledger / feature not started**: The workflow runs where no SpecOps ledger yet exists. The specify step establishes the feature (or the run reports that initialization is required) before reconciliation is meaningful.
- **Concurrent workflow runs on the same feature**: Two runs target the same feature at once. At most one advances the ledger; the other is rejected by the Feature 006 ledger identity and concurrency protection, so the two cannot double-advance or interleave state.
- **Ledger advanced out of band**: A maintainer advanced the ledger with a direct SpecOps command between steps. On the next reconciliation the ledger's current phase is taken as authoritative rather than the workflow's last-known navigational position.
- **Interruption during a single step**: A step is interrupted mid-execution. Spec Kit's resume re-enters that step; because the ledger phase was not advanced for an incomplete step, reconciliation keeps the feature at the correct phase and no duplicate advance occurs.

## Requirements *(mandatory)*

### Functional Requirements

#### Workflow definition (composed from Spec Kit primitives)

- **FR-001**: SpecOps MUST ship an installable, **SpecOps-owned** lifecycle workflow **definition** (named `specops`, invoked as `specify workflow run specops`) that composes Spec Kit's native step types (`command`, `shell`, `gate`, `do-while`, `if`/`switch`) to run the SpecOps-augmented lifecycle across specify, clarify, checklist, plan, tasks, analyze, implement, and review.
- **FR-001a**: The `specops` workflow MUST be delivered **additively** by the SpecOps extension install (Feature 005) and MUST NOT modify, replace, or remove Spec Kit's bundled `speckit` workflow or any other integration-owned asset (Constitution Principle I); the bundled workflow may be used only as a design reference.
- **FR-002**: SpecOps MUST NOT implement a workflow engine, a resume mechanism, a human gate, a loop, or a branching primitive; all such primitives MUST be Spec Kit's, referenced by the definition.
- **FR-003**: The definition MUST invoke each lifecycle step through the installed integration's own registered command mechanism, and MUST NOT introduce a separate integration-specific agent-command dispatch abstraction inside SpecOps.
- **FR-004**: The definition MUST position a Spec Kit `gate` step as the human readiness gate between planning and task generation, and MUST NOT allow task generation until that gate is approved.
- **FR-005**: The definition MUST interleave SpecOps deterministic gates (`review`, `consistency`) as steps at the appropriate lifecycle points, driven by their CLI outcome.
- **FR-006**: The optional quality/analysis steps (clarify, checklist, analyze) MUST be skippable by an explicit **human decision** at a native `gate`/`prompt` step that **defaults to running** the step; the run/skip choice MUST be recorded in the ledger, and a skipped step MUST let the run proceed without failing. Skipping MUST NOT be implicit (no silent auto-skip and no config-only toggle).
- **FR-007**: The shipped definition MUST run offline after installation, relying on Spec Kit's engine, the local SpecOps CLI, and locally registered integration commands.

#### Ledger reconciliation & state ownership

- **FR-008**: All deterministic state transitions (phase advances, task and review-cycle records) MUST be performed by SpecOps CLI directives invoked as workflow steps; Spec Kit's engine MUST NOT write SpecOps ledger state.
- **FR-009**: The SpecOps ledger MUST remain the single authoritative source of execution state; Spec Kit's workflow state is navigational only.
- **FR-010**: SpecOps MUST run reconciliation as a **fail-closed precondition of every state-changing ledger operation** and **once immediately after a Spec Kit `workflow resume`**, aligning the ledger with the actual repository/workflow state before it is mutated so the two never silently diverge. Reconciliation need not run before purely read-only steps.
- **FR-011**: SpecOps MUST NOT advance the ledger phase for a step that did not complete successfully.
- **FR-012**: When the ledger and the repository/workflow state cannot be safely reconciled, reconciliation MUST fail closed — refuse to advance and report which dimension diverged — rather than guessing or overwriting ledger state. The remedy for an irreconcilable divergence MUST be Feature 006's existing `rebaseline` escape hatch; this feature MUST NOT add a new reconciliation override or repair command.
- **FR-013**: When the ledger has been advanced out of band, reconciliation MUST treat the ledger's current phase as authoritative rather than the workflow's last-known navigational position.
- **FR-014**: Reconciliation MUST rely on the Feature 006 ledger identity and concurrency protection so that concurrent runs against the same feature cannot double-advance or interleave state; SpecOps MUST NOT add a separate locking scheme.

#### Corrective review loop (native `do-while`)

- **FR-015**: The definition MUST model review rejection as a bounded corrective loop using Spec Kit's native `do-while` (with its `max_iterations` cap); SpecOps MUST NOT implement loop control.
- **FR-016**: The loop condition MUST be driven by the SpecOps review outcome (its CLI contract), so a passing review exits the loop and a rejection repeats implementation and re-review.
- **FR-017**: Each corrective round MUST be recorded in the ledger as a new, strictly increasing review cycle, consistent with the existing review-cycle representation.
- **FR-018**: On re-entering review after corrections, the review gate MUST produce a fresh outcome rather than reusing a prior rejected verdict.
- **FR-019**: Because the native `do-while` exits and continues to the next step when its `max_iterations` bound is exhausted (it does not pause on its own), the definition MUST place a **terminal deterministic gate** — a `specops review`/verdict-check step — immediately after the corrective loop. This gate MUST fail closed (non-zero exit, halting the run) whenever the latest review verdict is not `APPROVED`, so a still-rejecting feature cannot fall through to completion. The terminal gate MUST NOT be a human approve/reject `gate` (which could approve past a still-failing deterministic review); the human decides out-of-band after the halt whether to resume correction or stop.
- **FR-020**: The workflow MUST reach completion only after a passing review outcome; no path may complete while a review is open or rejected.

#### Failure classification (CLI outcome contract)

- **FR-021**: SpecOps CLI commands used as workflow steps MUST expose a documented, stable outcome contract (distinct exit codes / structured signals) distinguishing gate/human rejection, lifecycle-step execution failure, and infrastructure/capability error.
- **FR-022**: The definition MUST use that contract with Spec Kit's native `gate`/`if`/`switch`/`do-while` conditions so each class leads to its own next action: correct the work, retry the step, or fix the environment.
- **FR-023**: An execution failure or infrastructure error MUST NOT be recorded as a review rejection and MUST NOT advance the ledger phase.
- **FR-024**: A required integration or SpecOps command that is unavailable MUST surface as an infrastructure/capability error before any state mutation, rather than causing a crash or a partial advance.

#### Scope boundaries

- **FR-025**: This feature MUST NOT reimplement any capability Spec Kit already provides (workflow engine, resume, gate, loop, branching, or the lifecycle commands themselves); SpecOps contributes only the definition, the deterministic gate CLIs, reconciliation, and the outcome contract.
- **FR-026**: The workflow MUST run lifecycle steps sequentially; this feature MUST NOT introduce parallel multi-agent fan-out.
- **FR-027**: This feature MUST NOT introduce a lightweight workflow lane, a context map, or a structured corrective-handoff finding schema; the corrective loop MUST reuse the existing review-cycle representation.

### Key Entities

- **SpecOps Lifecycle Workflow Definition**: The installable, SpecOps-owned `specops` workflow (delivered additively by the Feature 005 extension install, `specify workflow run specops`) that composes Spec Kit's native steps to run the augmented lifecycle; ships the wiring, not an engine, and never modifies the bundled `speckit` workflow.
- **SpecOps Deterministic Gate Steps**: The `review` and `consistency` CLI commands invoked as steps whose outcome drives Spec Kit's native gate/loop/branch steps.
- **Ledger Reconciliation**: The SpecOps mechanism that aligns the authoritative ledger with the repository/workflow state before every state-changing operation and once after a Spec Kit resume, failing closed on irreconcilable divergence.
- **CLI Outcome Contract**: The documented exit-code / signal vocabulary distinguishing gate rejection, execution failure, and infrastructure/capability error.
- **Corrective Loop (native)**: Spec Kit's `do-while`, bounded by `max_iterations`, conditioned on the SpecOps review outcome, with each round recorded as a ledger review cycle. Because the native loop exits and continues when its bound is exhausted, it is paired with a **terminal deterministic gate** (a `specops review`/verdict check positioned by the SpecOps definition) that fails closed when the verdict is not `APPROVED`, halting a still-rejecting feature instead of letting it complete; the human decides out-of-band after the halt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can install SpecOps and drive a feature from specification through an approved review by running the shipped workflow, with SpecOps's deterministic gates interleaved and the readiness gate enforced, and 0 hand-authored workflow wiring required, in 100% of standard runs.
- **SC-002**: 0 workflow-engine, resume, gate, loop, or branching mechanisms are implemented in SpecOps; 100% of orchestration primitives used by the shipped definition are Spec Kit native step types plus SpecOps CLI calls.
- **SC-003**: In 100% of runs, task generation does not occur until the human planning-readiness gate has been approved.
- **SC-004**: When the ledger and repository/workflow state cannot be reconciled, reconciliation fails closed with a divergence diagnostic in 100% of such cases; 0 cases silently advance or overwrite past the divergence.
- **SC-005**: A review rejection results in a bounded corrective loop that terminates in either an approval or a human-decision halt at the terminal gate in 100% of rejection scenarios; the loop runs unbounded in 0 cases, and 0 runs fall through to completion with the review still rejecting after the loop bound is exhausted.
- **SC-006**: Each interruption is classified via the CLI outcome contract as exactly one of gate/human rejection, execution failure, or infrastructure error; 0 execution or infrastructure failures are recorded as review rejections or advance the ledger phase.
- **SC-007**: 100% of ledger mutations during a run are attributable to a SpecOps CLI directive; 0 ledger mutations are written by Spec Kit's workflow engine.
- **SC-008**: The workflow reaches completion only after a passing review outcome in 100% of runs; 0 runs reach completion with an open or rejected review.

## Assumptions

- **Engine ownership (complement principle)**: Spec Kit owns the workflow engine, resume, gate, loop, and branching primitives (`specify_cli.workflows`: `command`/`shell`/`gate`/`do-while`/`while`/`if`/`switch`/`fan-out`/`fan-in`). SpecOps composes them and builds none. This is the primary constraint reshaping this feature away from "build an orchestrator."
- **Packaging (additive, SpecOps-owned)**: This feature ships a **new SpecOps-owned** workflow named `specops`, delivered by the Feature 005 extension install and invoked as `specify workflow run specops`. It does **not** modify or replace Spec Kit's bundled `speckit` workflow (specify → plan → tasks → implement with abort-on-reject gates), which is used only as a design reference — consistent with Constitution Principle I (Speckit Extension, Never Replacement). SpecOps builds no parallel engine; the `specops` workflow composes Spec Kit's native steps.
- **Ledger authority & concurrency**: The SpecOps ledger and the identity/compare-and-swap concurrency machinery from Feature 006 remain the source of execution truth and the concurrency guard. Reconciliation reads and writes the ledger only through SpecOps CLI directives.
- **Corrective representation reused**: The corrective loop reuses the existing ledger review-cycle representation (a REVIEW → IMPLEMENT rejection round recorded as a strictly increasing review cycle). A structured finding/authorization schema is deferred to Feature 011.
- **Loop bound is native, terminal gate is SpecOps**: The corrective loop's iteration bound is Spec Kit's `do-while` `max_iterations` (verified: on reaching the bound with the condition still truthy, the engine exits the loop and continues to the next step — it does not pause or abort on its own). The fail-safe "halt for a human instead of completing" therefore comes from a SpecOps-positioned terminal fail-closed gate after the loop, not from the bound itself.
- **Readiness-gate behavior is native**: The gate's approve/reject and `on_reject` behavior are Spec Kit's; SpecOps only positions the gate before task generation and never auto-proceeds on rejection.
- **Sequential execution**: Lifecycle steps run one at a time; no parallel multi-agent fan-out is introduced (explicit non-goal), pending proof that state ownership is safe under fan-out.
- **Offline operation**: After installation, the workflow runs offline via Spec Kit's engine, the local SpecOps CLI, and locally registered integration commands.
- **Development note**: Per project constraint, SpecOps itself is developed with plain Spec Kit artifacts (not by running SpecOps on this repository). This spec describes the capability SpecOps delivers to end users, not the SpecOps team's own development loop.
- **Out of scope (deferred to later roadmap features)**: no lightweight workflow lane (Feature 013), no context map or context routing (Features 008–009), no structured corrective-handoff schema (Feature 011), no gate profiles or structured-evidence redesign (Feature 012). This feature is confined to a native, composed workflow definition plus ledger reconciliation and the CLI outcome contract.
