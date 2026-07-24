# Feature Specification: Review Composition in the Workflow

**Feature Branch**: `016-review-composition-workflow`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "Compose the semantic agent review (`/specops-review`) and the Feature 011 blocking-findings enforcement into the Feature 007 workflow definition, so a workflow-driven run performs the actual code review, records structured findings, and makes the corrective loop and completion gate react to unverified blocking findings — using only Spec Kit native steps and the existing handoff CLI, with the deterministic gate kept as the fail-closed precondition and safe degradation when no findings are produced."

## Clarifications

### Session 2026-07-24

- Q: When a workflow-driven run cannot perform the semantic review (the `specops-review` command/skill is not registered for the active integration), what should the workflow do? → A: Fail closed — a run that cannot perform the review halts and cannot reach the completed state. This preserves the guarantee and prevents the exact gap this feature closes (a passing mechanical gate completing without a review) from silently reappearing.
- Q: When should the composed workflow enforce blocking findings versus complete on the deterministic verdict alone? → A: Always-on with automatic degrade — enforcement is active whenever the review records blocking findings; a run that records none degrades automatically to deterministic-only. Degrade is by *absence of findings*, not a configuration toggle; there is no opt-in or opt-out flag.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A workflow-driven run performs the actual code review (Priority: P1)

A team runs the shipped SpecOps lifecycle workflow end to end. After the implementation step, the workflow does not stop at the mechanical gate suite: it drives the **semantic agent review** over the effective diff, so structured findings are recorded whenever the diff violates the spec, plan, or constitution. The run that finishes therefore reflects a genuine code review, not only that lint/test/drift passed.

**Why this priority**: This is the correctness fix at the heart of the feature. Today a workflow-driven run passes the deterministic gates and reaches completion **without the semantic review ever happening**, so the enforcement added by the corrective-handoff feature gates an empty set. Without this story the feature delivers nothing; every other story refines it.

**Independent Test**: Run the shipped workflow against a fixture feature whose diff contains a real spec/plan non-conformity. Verify that at least one structured finding is recorded during the run (the handoff report is non-empty), attributable to the semantic review step — proving the review executed rather than being skipped.

**Acceptance Scenarios**:

1. **Given** a feature whose effective diff violates a declared requirement, **When** the workflow reaches the review portion of the corrective loop, **Then** the semantic review runs and records at least one structured finding for that non-conformity.
2. **Given** the deterministic gate suite passes (reconcile, gate profiles, working tree, drift), **When** the workflow continues, **Then** the semantic review still runs — a passing mechanical gate does not substitute for the code review.

---

### User Story 2 - An unverified blocking finding cannot fall through to completion (Priority: P1)

When the semantic review records a **blocking** finding, the workflow cannot mark the feature complete while that finding remains unverified. The corrective loop iterates — implement, re-review, verify — and only a run in which every blocking finding is verified (or dismissed) reaches the terminal completed state. A run that exhausts its correction budget with a blocking finding still open halts before completion instead of silently finishing.

**Why this priority**: This is the enforcement half of the feature. Recording findings (Story 1) is inert unless the workflow's loop condition and terminal gate react to them. Both stories together are the minimum viable feature; either alone is incomplete.

**Independent Test**: Run the workflow against a fixture with one blocking finding. Confirm the loop re-iterates while it is unverified and that the terminal transition to the completed state fails closed until the finding is verified; then verify the finding and confirm completion succeeds.

**Acceptance Scenarios**:

1. **Given** an open blocking finding after a review round, **When** the corrective loop evaluates its continuation condition, **Then** it opens another corrective round rather than proceeding to completion.
2. **Given** a blocking finding that remains unverified after the correction budget is exhausted, **When** the workflow reaches the terminal gate, **Then** the run halts (fails closed) and does not reach the completed state.
3. **Given** every blocking finding is verified (advisory findings may remain open), **When** the workflow reaches the terminal gate, **Then** the run completes and records the completion transition.

---

### Story degradation note

The two P1 stories describe the enforcing behavior. When a repository or agent produces **no** structured findings (a legacy repository, or a review that ran and found nothing), the workflow must reproduce the prior deterministic-only behavior instead of blocking on an empty finding set. Degrade is triggered by the absence of findings, not by a configuration choice — there is no flag that disables enforcement while findings are present (FR-015). This degrade path is exercised as Story 3.

### User Story 3 - Repositories that record no findings still complete (Priority: P2)

A repository that does not record structured findings (legacy, or a run where the review produces none) runs the same shipped workflow and completes exactly as it did before this feature — driven by the deterministic gate verdict alone. Composing the semantic review must never make a no-findings run block on an empty set.

**Why this priority**: Backward compatibility and safe degradation (roadmap Rule 5). It protects existing adopters, but the feature's new value lives in Stories 1–2; this story guarantees they cost nothing to those not yet producing findings.

**Independent Test**: Run the workflow against a conformant fixture that records zero findings. Confirm it completes through the deterministic path with no block on an empty finding set and no change in outcome versus the pre-feature workflow.

**Acceptance Scenarios**:

1. **Given** a run that records zero structured findings, **When** the loop condition and terminal gate evaluate, **Then** completion is decided solely by the deterministic gate verdict, identical to the pre-feature behavior.
2. **Given** a repository with no corrective-handoff state at all, **When** the workflow runs, **Then** no step errors on missing findings state and the run completes normally.

---

### User Story 4 - The mechanical gate stays a fail-closed precondition (Priority: P2)

The deterministic gate suite remains the cheap, fail-closed precondition: the workflow rejects early on a mechanical failure (reconcile, gate profiles, working tree, drift) and runs the token-expensive semantic review only once those pass. The two are ordered, not merged.

**Why this priority**: Preserves the token discipline the review directive is built around (reject before reading code) and keeps the deterministic gate's guarantees. It refines Stories 1–2 rather than standing alone.

**Independent Test**: Run the workflow against a fixture that fails a mechanical gate. Confirm the deterministic gate rejects and the semantic review is **not** driven for that round; then fix the mechanical failure and confirm the semantic review runs on the next round.

**Acceptance Scenarios**:

1. **Given** a mechanical gate fails (e.g., drift or a required gate-profile failure), **When** the round evaluates, **Then** the deterministic gate rejects first and the semantic review does not run that round.
2. **Given** all mechanical gates pass, **When** the round continues, **Then** the semantic review runs.

---

### Edge Cases

- **Loop budget exhausted with a blocking finding open**: the terminal gate must fail closed (halt before completion), never fall through to the completed state (covered by Story 2 scenario 2).
- **A blocking finding is dismissed as a false positive**: a verified-or-dismissed blocking finding no longer gates; the run may complete (dismissal is the existing withdrawal path, not a new mechanism).
- **Advisory findings only**: advisory findings never block; a run with only advisory findings completes via the deterministic path.
- **Mechanical gate keeps failing every round**: the loop exhausts its bounded iterations and the terminal gate halts; the run never completes on unresolved mechanical failure (unchanged from the prior workflow).
- **Semantic review records findings but the loop condition reads only the deterministic verdict**: this is the pre-feature bug and must not persist — the continuation condition must observe the blocking-findings state, not only the gate verdict.
- **Findings state present but no active review cycle** (reconciliation divergence): the workflow must fail closed on irreconcilable state rather than complete, consistent with the existing reconcile precondition.
- **Zero-finding run in a repo that *does* support findings**: treated identically to the legacy degrade path — no block on an empty set.
- **Semantic review step cannot run** (the `specops-review` command/skill is not registered for the active integration, so the review cannot be performed): the workflow fails closed — it halts and cannot reach the completed state (Clarification 2026-07-24 Q1). This is distinct from the no-findings degrade path: degrade applies only when the review *ran and recorded none*, never when the review *could not run*.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The shipped lifecycle workflow's corrective loop MUST invoke the semantic review (the registered `/specops-review` directive, or an equivalent review step that reads the effective diff and records structured findings) — not only the deterministic mechanical gate.
- **FR-002**: The deterministic gate suite (reconcile, gate profiles, working tree, drift) MUST remain the fail-closed precondition of each corrective round: it is evaluated first, and the semantic review runs only when it passes.
- **FR-003**: The corrective loop's continuation condition MUST react to unverified blocking findings — a round that leaves any blocking finding unverified MUST open another corrective round (bounded by the existing iteration limit), independent of the mechanical gate verdict.
- **FR-004**: The terminal completion gate MUST fail closed while any blocking finding is unverified, so a feature with an open blocking finding cannot reach the completed state — including when the correction budget is exhausted.
- **FR-005**: The completed-state transition MUST NOT be reachable by a human approval or a passing mechanical gate alone while a blocking finding is unverified.
- **FR-006**: When a run records **no** structured findings (legacy repo or a genuinely clean review that *ran*), the workflow MUST degrade to the prior deterministic-only behavior: completion is decided by the deterministic gate verdict and no step blocks on an empty finding set. This degrade is automatic — triggered by the absence of findings, not by any configuration flag (see FR-015); it MUST NOT be reached when the review could not run (FR-016).
- **FR-007**: The workflow MUST compose Spec Kit native step types only (command / shell / gate / do-while / if) plus the existing corrective-handoff CLI. It MUST NOT introduce any new engine, loop, gate, or resume primitive inside SpecOps.
- **FR-008**: The findings-aware conditions MUST be derived from the existing corrective-handoff reporting surface (the machine-readable handoff report that already exposes the remaining unverified blocking set). The feature MUST NOT add new state to, or change the lifecycle of, the corrective-handoff findings.
- **FR-009**: Forward-seam ledger phase transitions MUST remain owned by the injected lifecycle directives; this feature composes the review step and the findings-aware conditions and MUST NOT duplicate or re-own those transitions.
- **FR-010**: The corrective loop MUST remain bounded by the existing maximum-iteration limit; composing the semantic review MUST NOT remove or weaken that bound.
- **FR-011**: A rejected or interrupted run MUST be resumable from repository state alone (via the native workflow resume), with the findings-aware conditions re-derived from persisted handoff state rather than in-memory context.
- **FR-012**: The updated workflow definition MUST pass validation against the Spec Kit workflow engine (step structure, references, and step-type usage) so it installs and runs unchanged.
- **FR-013**: The change set MUST keep the review directive template, the workflow definition, and the EN/PT documentation behaviorally equivalent where they describe the workflow's review-and-enforce behavior.
- **FR-014**: The feature MUST document, in user-facing docs and the changelog, that a workflow-driven run now performs and enforces the semantic review, and that findings enforcement is always-on with automatic degrade to deterministic-only when a review records no findings.
- **FR-015**: Findings enforcement MUST be always-on with no opt-in or opt-out configuration flag: it is active whenever the review records blocking findings, and it degrades to deterministic-only solely by the absence of findings (FR-006). The feature MUST NOT introduce a configuration knob that disables findings enforcement while findings are present.
- **FR-016**: When the semantic review step cannot be performed (the `specops-review` command/skill is not registered/available for the active integration), the workflow MUST fail closed: it MUST NOT reach the completed state, and it MUST NOT treat an un-runnable review as a no-findings degrade (FR-006). Where feasible, this unavailability SHOULD be surfaced as early as possible (e.g., at workflow validation or extension install), but the runtime guarantee is that a run which cannot review cannot complete.

### Key Entities *(include if feature involves data)*

- **Corrective loop**: the bounded iterate-until-clean segment of the shipped workflow. This feature extends its body to include the semantic review and its continuation condition to include unverified blocking findings.
- **Deterministic gate verdict**: the pass/reject outcome of the mechanical gate suite; retained as the fail-closed precondition ordered before the semantic review.
- **Structured finding**: an existing corrective-handoff record with a severity (blocking / advisory) and a lifecycle state (open → fixed → verified, or dismissed). This feature consumes the *remaining unverified blocking* projection of these records; it does not alter them.
- **Terminal completion gate**: the final workflow guard before the completed-state transition; extended to fail closed on unverified blocking findings in addition to a non-approved mechanical verdict.
- **Findings-aware condition**: a workflow condition (loop continuation and terminal guard) evaluated from the machine-readable handoff report's remaining-blocking set.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a run over a feature with a real non-conformity, the semantic review executes and at least one structured finding is recorded — measured as a non-empty handoff report where the pre-feature workflow recorded none (100% of such fixture runs record the finding).
- **SC-002**: A run with an unverified blocking finding cannot reach the completed state: across all such fixture runs, the terminal gate halts before completion 100% of the time, with zero completions while a blocking finding is unverified.
- **SC-003**: Once every blocking finding is verified (or dismissed), the workflow completes: 100% of such fixture runs reach the completed state.
- **SC-004**: A run that records zero findings completes through the deterministic path with an outcome identical to the pre-feature workflow in 100% of degrade-path fixture runs, with zero blocks attributable to an empty finding set.
- **SC-005**: For every round, the deterministic gate is evaluated before the semantic review; in fixture runs that fail a mechanical gate, the semantic review is not driven that round in 100% of cases.
- **SC-006**: The updated workflow definition validates against the workflow engine and installs unchanged (zero validation errors), and no existing consumer of the corrective-handoff CLI or the workflow steps breaks (zero regressions in the existing test suites).
- **SC-007**: EN and PT documentation describing the workflow's review-and-enforce behavior are behaviorally equivalent (no divergence in described outcomes), verified by review.
- **SC-008**: In fixture runs where the semantic review cannot be performed (review command unavailable), the workflow halts before completion 100% of the time — zero completions — and is never recorded as a no-findings degrade.
- **SC-009**: No configuration path exists by which findings enforcement is disabled while blocking findings are present: across the configuration surface, zero settings can suppress enforcement of an unverified blocking finding.

## Assumptions

- The semantic review is delivered by the existing `/specops-review` directive template and the corrective-handoff CLI it already calls; this feature composes them and does not redefine either (Feature 011 owns the finding lifecycle).
- `specops-review` is already registered as a native command (per-integration skill), so the workflow can drive it as a native `command:` step; the exact step placement, condition expression, and the handoff-report field read by the findings-aware conditions are plan-level wiring, not spec decisions.
- The machine-readable handoff report already exposes the remaining unverified blocking set; the findings-aware conditions read that projection rather than introducing new reporting.
- The deterministic gate retains its current soft (verdict-in-output, always-zero-exit) and hard (non-zero-on-non-approval) invocation modes used by the loop and the terminal gate respectively.
- Command-type review steps require a live integration/agent and are not fully CI-reproducible; end-to-end enforcement is validated against fixtures and the workflow-engine structural checks, with the composed CLI primitives covered by unit/integration tests — consistent with the existing workflow's verification note.
- This feature composes the **built-in** review only; ingesting findings from external reviewers is a separate, later feature and is out of scope here.
- The gate is referred to by its current name in this feature; a later feature renames it, and this feature does not depend on that rename.
- "Effective diff" and path classification (planned / acknowledged / unexplained) behave as already defined by the traceability feature; this feature does not change them.
