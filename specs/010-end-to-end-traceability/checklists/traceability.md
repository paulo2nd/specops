# Requirements Quality Checklist: End-to-End Traceability

**Purpose**: Validate the *requirements* in `spec.md` for completeness, testability, failure semantics, upgrade behavior, and backward compatibility before `/speckit-plan` (roadmap step 2). This is a "unit test for the English", not a test of any implementation.
**Created**: 2026-07-21
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [x] CHK001 Are the boundaries of the **effective diff** (net change vs intermediate churn, and how renames/mode-only/copy changes are counted) explicitly defined in requirements, rather than only deferred to Feature 009? [Completeness, Gap, Spec §FR-002]
- [x] CHK002 Is the resolution of "**baseline**" (merge-base, ledger-recorded baseline, or configured ref) specified in-spec rather than left implicit in an assumption? [Completeness, Gap, Spec §FR-002, §Assumptions]
- [x] CHK003 Are requirements defined for how a **deleted/removed** path and a **renamed** path are each assigned a path class? [Completeness, Coverage, Spec §Edge Cases, §FR-003]
- [ ] CHK004 Is the enumeration of the stable `status` field values (the fine-grained outcomes behind exit `0`/`1`/`2`) specified, so empty-diff, no-map, and all-explained success states are distinguishable? [Completeness, Gap, Spec §FR-014]
- [x] CHK005 Is a **versioned JSON schema** for the trace report and classification output required (mirroring the Feature 008/009 JSON contract), or only "stable JSON"? [Completeness, Gap, Spec §FR-011, §FR-014]
- [ ] CHK006 Are the required fields of an **Acknowledgement Record** (path, reason, task, map digest) each specified with their presence/optionality when no map exists? [Completeness, Spec §FR-017, §Key Entities]
- [ ] CHK007 Are requirements defined for the **canonical ordering/sort keys** used to make report and classification output deterministic? [Completeness, Gap, Spec §FR-015, §SC-001]
- [ ] CHK008 Does the spec state which lifecycle phase(s)/command the **review drift gate** runs in, and whether it is invoked automatically via the review directive or only on demand? [Completeness, Gap, Spec §FR-004]
- [ ] CHK009 Are requirements present for a **human-readable vs JSON** parity guarantee (both render the same chain), not just that both exist? [Completeness, Spec §FR-011]

## Requirement Clarity & Measurability

- [ ] CHK010 Is "**concise reason**" for an acknowledgement bounded with a measurable constraint (length/format), or is it an unquantified adjective? [Clarity, Ambiguity, Spec §FR-005]
- [ ] CHK011 Is the meaning of "a task **associates** a path with a context" (via the Feature 009 provenance snapshot) defined precisely enough to evaluate contradictory ownership? [Clarity, Spec §FR-009]
- [ ] CHK012 Is "**contradictory ownership**" defined unambiguously — including what distinguishes it from Feature 009's plan-time undeclared-owner check? [Clarity, Spec §FR-009]
- [ ] CHK013 Can "byte-for-byte identical output" be objectively verified for both human and JSON renderings (e.g., is trailing whitespace/locale ordering pinned)? [Measurability, Spec §FR-015, §SC-001]
- [ ] CHK014 Is the "**complete machine-checkable trace**" acceptance property expressed as an objectively checkable per-SC and per-path condition rather than a narrative goal? [Measurability, Spec §SC-006]
- [ ] CHK015 Is the distinction between the two missing-link sub-cases (uncovered SC vs completed-task-without-evidence / final-task-without-commit) stated clearly enough to produce distinct diagnostics? [Clarity, Spec §FR-009, §Clarifications]

## Requirement Consistency

- [x] CHK016 When a path is simultaneously plan-declared **and** carries an acknowledgement, is the class **precedence** unambiguous (single class per FR-003)? [Consistency, Spec §FR-003, §FR-007]
- [ ] CHK017 Is the exit-code taxonomy internally consistent across all commands — every named blocking condition maps to `1` and every usage condition to `2` with no overlap? [Consistency, Spec §FR-004, §FR-009, §FR-014]
- [ ] CHK018 Do the FR-level "completed success criterion" definition and every SC/Edge-Case reference to "completed" use the same mechanical ledger-derived meaning after the clarification? [Consistency, Spec §FR-001, §FR-009, §SC-006, §Clarifications]
- [ ] CHK019 Are the "planned" definition in FR-003 and the "planned = plan-declared or owned-by-declared-context" phrasing consistent with Feature 009's ownership-is-not-write-permission stance? [Consistency, Spec §FR-003, §Assumptions]
- [ ] CHK020 Is the commit-existence responsibility split between trace validation (surfaces dangling ref) and `specops reconcile` (authoritative) stated without contradiction? [Consistency, Spec §FR-010]

## Failure Semantics & Exit-Code Coverage

- [ ] CHK021 Are requirements defined for the **not-a-Git-repo / no-resolvable-baseline** failure (exit `2`, never a silent empty result) for every Git-deriving command? [Coverage, Spec §FR-014, §Edge Cases]
- [ ] CHK022 Are **conflicting acknowledgement** and **non-existent task** failures each specified to leave prior state unchanged and record nothing (fail-closed, atomic)? [Failure Semantics, Spec §FR-006, §FR-007]
- [ ] CHK023 Is the behavior specified when a linked **finding's `[File]` token matches no effective-diff path** (stale/misaligned finding)? [Edge Case, Gap, Spec §FR-018]
- [ ] CHK024 Are requirements defined for behavior when the **underlying context map is invalid/ambiguous/unsupported** during a trace command (fail closed, defer to `context validate`)? [Failure Semantics, Gap, Spec §FR-013, §FR-009]
- [x] CHK025 Is **concurrent-acknowledgement** safety (lock/compare-and-swap from Feature 006) required so two sessions cannot lose or corrupt an acknowledgement write? [Coverage, Gap, Spec §FR-005, §FR-017]
- [ ] CHK026 Are requirements defined for a partially-written/interrupted acknowledgement leaving the prior valid ledger readable? [Failure Semantics, Spec §FR-005]

## Upgrade Behavior & Backward Compatibility

- [x] CHK027 Is an explicit **ledger schema version bump** (or additive-field versioning) required for the new trace/acknowledgement fields, not just described as "additive"? [Upgrade, Gap, Spec §FR-017]
- [x] CHK028 Is a **forward-migration test obligation** for pre-feature ledgers stated as a requirement (per Global Definition of Done), and is the expected read behavior of absent fields specified? [Backward Compatibility, Spec §FR-016, §SC-007]
- [ ] CHK029 Are requirements clear that pre-feature records lacking trace/acknowledgement fields are a **supported prior shape** and never reported as defects by validation? [Backward Compatibility, Spec §FR-016, §Edge Cases]
- [ ] CHK030 Is the interaction with **Feature 009 provenance fields** (their presence/absence) specified so a v009 ledger without provenance still traces without error? [Backward Compatibility, Gap, Spec §FR-016]

## Scenario & Edge-Case Coverage

- [ ] CHK031 Are **empty-diff / clean-tree** requirements specified as a supported non-error with zero paths in every class? [Coverage, Spec §FR-004, §Edge Cases]
- [ ] CHK032 Are **no-context-map** requirements specified across all four read commands (classification falls back to plan paths; ownership check inapplicable)? [Coverage, Spec §FR-013, §SC-008]
- [ ] CHK033 Is the scenario where an **acknowledged path leaves and later re-enters** the diff covered, consistent with the path-level binding clarification? [Coverage, Spec §FR-005, §Clarifications, §Edge Cases]
- [ ] CHK034 Are requirements defined for an SC whose tasks are complete but whose **commit/evidence chain is broken** (distinct from an uncovered SC)? [Coverage, Spec §FR-009, §Edge Cases]
- [x] CHK035 Is **symlink handling** in effective-diff classification addressed (matched by own path, not followed), consistent with Feature 009 stale detection? [Coverage, Gap, Spec §FR-002]

## Dependencies, Assumptions & Traceability

- [ ] CHK036 Is every functional requirement traceable to at least one measurable Success Criterion (e.g., is FR-011 report parity and FR-002 effective-diff covered by an SC)? [Traceability, Gap, Spec §FR-002, §FR-011, §Success Criteria]
- [ ] CHK037 Is the **English/Portuguese behavioral-equivalence** obligation expressed as a requirement, not only an assumption? [Coverage, Gap, Spec §Assumptions]
- [ ] CHK038 Are the load-bearing assumptions (baseline derivation, provenance availability, evidence format, reconcile ownership) each marked as validated dependencies rather than unverified premises? [Assumption, Spec §Assumptions]

## Notes

- Check items off as the spec is amended: `[x]`. Unchecked items are candidate gaps/ambiguities to resolve before planning, not implementation defects.
- ≥80% of items carry a `[Spec §…]`, `[Gap]`, `[Ambiguity]`, `[Conflict]`, or `[Assumption]` traceability marker.
- High-value gaps most worth resolving pre-plan: CHK001/CHK002 (effective-diff & baseline definition), CHK004 (`status` enumeration), CHK005/CHK027 (versioned JSON + ledger schema version), CHK016 (class precedence), CHK025 (concurrent-acknowledgement safety).
