# Requirements Quality Checklist: Review Composition in the Workflow

**Purpose**: Validate the quality, completeness, and testability of the spec's requirements before implementation — with emphasis on the roadmap §2 dimensions: completeness, testability, failure semantics, upgrade behavior, and backward compatibility.
**Created**: 2026-07-24
**Feature**: [spec.md](../spec.md)

**Note**: These items test whether the REQUIREMENTS are well-written — not whether the workflow works. Each asks whether something is clearly, completely, and consistently specified.

## Requirement Completeness

- [ ] CHK001 Are the requirements complete for every step the composed loop adds (semantic review, findings-report read, guard), or only for the review invocation? [Completeness, Spec §FR-001/§FR-003]
- [ ] CHK002 Is the boundary between "the review ran and found nothing" and "the review could not run" fully specified so both are distinguishable in requirements? [Completeness, Spec §FR-006/§FR-016]
- [ ] CHK003 Are requirements defined for what happens to advisory findings recorded by the semantic review (do they influence the loop or completion at all)? [Completeness, Gap]
- [ ] CHK004 Does the spec state which component owns the completion decision when both the semantic review's own transition and the workflow's terminal steps could fire? [Completeness, Spec §FR-009]
- [ ] CHK005 Are requirements present for the observability of *why* the loop re-iterates when the mechanical gate is green but a blocking finding is open? [Gap]
- [ ] CHK006 Is the interaction between the correction budget and the added review step specified (does the review count against the same bound)? [Completeness, Spec §FR-010, Edge Case]
- [ ] CHK007 Are documentation and changelog obligations specified concretely enough to be checkable (which surfaces, which behavior described)? [Completeness, Spec §FR-013/§FR-014]

## Requirement Clarity & Measurability

- [ ] CHK008 Is "unverified blocking finding" defined precisely enough (state values, dismissal) to evaluate the loop and terminal conditions unambiguously? [Clarity, Spec §FR-003/§FR-004]
- [ ] CHK009 Is "the deterministic gate passes" stated as a precise precondition (which gate outcome permits the semantic review to run)? [Clarity, Spec §FR-002]
- [ ] CHK010 Is "degrade to the prior deterministic-only behavior" quantified as an observable equivalence rather than a vague intent? [Measurability, Spec §FR-006/§SC-004]
- [ ] CHK011 Is "cannot reach the completed state" expressed as an objectively verifiable outcome (halt/exit/phase never DONE)? [Measurability, Spec §SC-002/§SC-008]
- [ ] CHK012 Are the success criteria stated as pass/fail thresholds a reviewer can check without knowing the implementation? [Measurability, Spec §SC-001..§SC-009]
- [ ] CHK013 Is "the semantic review cannot be performed" defined by a concrete condition (command unregistered/unavailable) rather than an open-ended set? [Clarity, Spec §FR-016]
- [ ] CHK014 Is "no configuration path disables enforcement" measurable against a defined configuration surface? [Measurability, Spec §SC-009/§FR-015]

## Failure & Exception Semantics

- [ ] CHK015 Are requirements defined for the correction-budget-exhausted-with-open-blocking case, and is the required outcome (halt, no completion) unambiguous? [Coverage, Spec §SC-002, Edge Case]
- [ ] CHK016 Is the fail-closed requirement on an un-runnable review stated strongly enough to forbid treating it as a no-findings degrade? [Failure Semantics, Spec §FR-016/§FR-006]
- [ ] CHK017 Are requirements defined for reconciliation divergence (findings present but no active review cycle) during a composed run? [Coverage, Spec Edge Cases]
- [ ] CHK018 Is the behavior specified when a blocking finding is dismissed as a false positive versus verified (both must stop gating)? [Coverage, Spec Edge Cases]
- [ ] CHK019 Are requirements defined for a persistently failing mechanical gate (loop exhausts, never completes) so it is not conflated with the findings path? [Coverage, Spec Edge Cases/§FR-002]
- [ ] CHK020 Does the spec require that an un-runnable review never silently completes, with a stated detection point (validation/install SHOULD)? [Failure Semantics, Spec §FR-016]

## Consistency

- [ ] CHK021 Is FR-002 (mechanical gate first, review only if it passes) consistent with FR-003 (loop reacts to blocking findings) without a contradiction about when the review runs? [Consistency, Spec §FR-002/§FR-003]
- [ ] CHK022 Do FR-009 (no duplicated/re-owned transitions) and FR-004/FR-005 (terminal fail-closed) agree on who performs the completion transition? [Consistency, Spec §FR-009/§FR-004]
- [ ] CHK023 Are the clarifications (fail-closed; always-on/auto-degrade) reflected consistently across FRs, edge cases, success criteria, and assumptions with no residual "opt-out" language? [Consistency, Spec §Clarifications]
- [ ] CHK024 Is the "compose native steps + existing handoff CLI only" constraint stated consistently everywhere it is relied on (FR-007, FR-008, non-goals)? [Consistency, Spec §FR-007/§FR-008]
- [ ] CHK025 Do the success criteria (SC-001..SC-009) each trace to at least one functional requirement without orphan or conflicting claims? [Consistency/Traceability, Spec §SC/§FR]

## Backward Compatibility & Upgrade Behavior

- [ ] CHK026 Are requirements explicit that a legacy repo with no handoff state completes unchanged (no error on absent findings state)? [Backward Compatibility, Spec §FR-006/§SC-004, User Story 3]
- [ ] CHK027 Does the spec require the pre-feature outcome to be preserved for zero-finding runs, stated as an equivalence a reviewer can verify? [Upgrade Behavior, Spec §SC-004]
- [ ] CHK028 Is it specified that no persisted format or existing JSON/CLI contract changes (so downstream features 011–015 are unaffected)? [Backward Compatibility, Spec §FR-008, Non-goals]
- [ ] CHK029 Are resume/interruption requirements defined so a composed run re-derives findings-aware conditions from persisted state, not memory? [Coverage, Spec §FR-011]

## Testability & Acceptance Evidence

- [ ] CHK030 Given the semantic review needs a live agent, does the spec define how enforcement is demonstrated without a CI-reproducible end-to-end run? [Testability, Spec §Assumptions]
- [ ] CHK031 Are the acceptance scenarios for Stories 1–2 written so they can be evidenced by fixture-seeded handoff state and structural checks? [Testability, Spec §User Scenarios]
- [ ] CHK032 Is each measurable outcome (SC-001..SC-009) associated with an observable signal (report contents, exit/halt, ledger phase) rather than internal behavior? [Measurability/Testability, Spec §SC]

## Dependencies, Assumptions & Ambiguities

- [ ] CHK033 Is the assumption that `specops-review` is a registered native command (drivable as a `command:` step) stated and flagged for validation? [Assumption, Spec §Assumptions]
- [ ] CHK034 Is the dependency on the existing `handoff report` remaining-blocking projection documented as the sole findings signal? [Dependency, Spec §FR-008]
- [ ] CHK035 Is the deferral of external-reviewer ingestion (Feature 015) and the gate rename (Feature 017) stated so this spec's scope boundary is unambiguous? [Assumption/Scope, Spec §Assumptions, Non-goals]
- [ ] CHK036 Are any residual ambiguities about the exact loop-condition expression explicitly deferred to planning rather than left implicit in the requirements? [Ambiguity, Spec §Assumptions]

## Notes

- Check items off as the spec is confirmed to satisfy each: `[x]`.
- An unchecked item means the spec (not the code) needs a clarification or addition before implementation.
- Failure-semantics items (CHK015–CHK020) and backward-compat items (CHK026–CHK029) are the roadmap §2 gating dimensions for this feature — prioritize resolving those.
