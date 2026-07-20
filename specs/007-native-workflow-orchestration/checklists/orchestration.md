# Requirements Quality Checklist: Native Workflow Orchestration

**Purpose**: Validate the *quality* of the requirements in spec.md — completeness, clarity, testability, failure semantics, upgrade behavior, backward compatibility, and complement-boundary integrity — before planning. These are "unit tests for the requirements writing," not tests of the implementation.
**Created**: 2026-07-20
**Feature**: [spec.md](../spec.md)
**Focus (per ROADMAP protocol §2)**: completeness · testability · failure semantics · upgrade behavior · backward compatibility. Depth: release gate (Foundation). Audience: pre-plan reviewer.

## Requirement Completeness

- [ ] CHK001 Are requirements defined for how the `specops` workflow is installed/registered, distinct from how it is invoked? [Completeness, Spec §FR-001/§FR-001a]
- [ ] CHK002 Is the ledger representation of a "skipped" optional step specified (which field/value records run vs skip)? [Gap, Spec §FR-006]
- [ ] CHK003 Are the contents of the "which dimension diverged" divergence diagnostic specified (what a human/caller actually learns)? [Gap, Spec §FR-012]
- [ ] CHK004 Are the *distinguishable outcome signals* the CLI contract must expose enumerated, independent of their concrete exit-code values? [Completeness, Spec §FR-021]
- [ ] CHK005 Is the position of each deterministic SpecOps gate (`review`, `consistency`) within the lifecycle explicitly specified, or only that they are "interleaved at the appropriate points"? [Clarity/Gap, Spec §FR-005]
- [ ] CHK006 Are requirements defined for adopting a feature started under the bundled `speckit` workflow (or manually) into the `specops` workflow? [Gap, Upgrade]

## Requirement Clarity & Measurability

- [x] CHK007 Is the reconciliation cadence precise — is "between steps" defined as after every step, before every state-changing step, or only at phase seams? [Ambiguity, Spec §FR-010] — RESOLVED: fail-closed precondition of every state-changing op + once after resume.
- [ ] CHK008 Is "cannot be safely reconciled" defined by an enumerated set of divergence dimensions, and is it stated whether 007 adds any dimension beyond Feature 006's identity checks? [Clarity, Spec §FR-012/§FR-014]
- [ ] CHK009 Is "offline" given an objective criterion (e.g., no network dependency after install)? [Measurability, Spec §FR-007]
- [ ] CHK010 Is the corrective-loop bound value specified or explicitly delegated to the native `max_iterations` default, so it is unambiguous? [Clarity, Spec §FR-015]
- [ ] CHK011 Can "0 workflow-engine/resume/gate/loop mechanisms implemented in SpecOps" be objectively verified, and does the requirement imply the verification method? [Measurability, Spec §SC-002]
- [x] CHK012 Is the terminal fail-closed gate's nature decided (deterministic `review` step vs native human `gate`), or does FR-019 permit either without a decision? [Ambiguity, Spec §FR-019] — RESOLVED: deterministic verdict check, fails closed if ≠ APPROVED; not a human gate.

## Requirement Consistency

- [ ] CHK013 Are the complement-boundary claims (no engine/resume/gate/loop) consistent across the Complement Boundary section, §FR-002, §FR-025, and §SC-002? [Consistency]
- [ ] CHK014 Do the packaging requirements (additive `specops` workflow, bundled untouched) align across §FR-001a, the Packaging assumption, Key Entities, and the Clarifications session? [Consistency, Spec §FR-001a]
- [ ] CHK015 Is the failure taxonomy (gate rejection / execution failure / infrastructure error) used consistently across §US4, §FR-021–§FR-024, and §SC-006? [Consistency]
- [ ] CHK016 Are "run", "workflow", "definition", and "engine" used consistently and distinctly, without drift between the navigational workflow state and the authoritative ledger? [Consistency, Terminology, Spec §FR-009]

## Complement-Boundary Integrity

- [ ] CHK017 Does every requirement that names a native primitive (gate, do-while, resume, branching) attribute ownership to Spec Kit rather than SpecOps? [Consistency, Spec §FR-002]
- [ ] CHK018 Is the line between "SpecOps composes/positions a primitive" and "SpecOps implements a primitive" stated unambiguously for each of gate, loop, and resume? [Clarity, Spec §FR-002/§FR-015/§FR-019]
- [ ] CHK019 Is the non-modification constraint on Spec Kit-owned assets (the bundled `speckit` workflow) stated as a testable requirement, not only an assumption? [Traceability, Spec §FR-001a]

## Failure Semantics & Recovery

- [ ] CHK020 Are requirements defined distinguishing a hard step crash (engine aborts) from a structured outcome the definition can branch on? [Coverage, Spec §FR-021/§US4]
- [ ] CHK021 Are recovery requirements specified for resuming after an execution failure (retry/resume) without recording a rejection or advancing the ledger? [Recovery, Spec §FR-023]
- [ ] CHK022 Is the guarantee that an unresolved rejection cannot fall through to completion after the loop bound stated as a testable requirement (terminal gate), not only narrative prose? [Measurability, Spec §FR-019/§SC-005]
- [ ] CHK023 Are requirements defined for an interrupted single step so no duplicate phase advance occurs on resume? [Edge Case, Spec §Edge Cases]
- [ ] CHK024 Is each failure class explicitly mapped to its remedy (correct / retry / fix environment)? [Completeness, Spec §FR-022/§FR-023]

## Upgrade Behavior & Backward Compatibility

- [ ] CHK025 Is it a stated requirement that installing the `specops` workflow does not alter or disable existing users' bundled `speckit` workflow runs? [Backward Compatibility, Spec §FR-001a]
- [ ] CHK026 Are requirements defined for behavior when no SpecOps ledger yet exists (greenfield) versus an existing ledger? [Coverage, Spec §Edge Cases]
- [ ] CHK027 Is the reliance on Feature 006 (`rebaseline`, identity/CAS) stated as an explicit dependency with a defined behavior if that capability is absent or older? [Dependency, Spec §FR-012/§FR-014]

## Acceptance Criteria Quality

- [ ] CHK028 Do all success criteria (SC-001..SC-008) express an objective threshold (percentage/count) rather than a subjective judgment? [Measurability, Spec §Success Criteria]
- [ ] CHK029 Is each success criterion traceable to at least one functional requirement and user story? [Traceability, Spec §Success Criteria]
- [ ] CHK030 Is "0 hand-authored workflow wiring required" (SC-001) defined precisely enough to be objectively verifiable? [Clarity, Spec §SC-001]

## Dependencies, Assumptions & Conflicts

- [ ] CHK031 Are the assumptions (engine ownership, native loop bound, 006 concurrency, offline) validated or flagged as risks, rather than asserted as fact? [Assumption, Spec §Assumptions]
- [ ] CHK032 Is the out-of-scope list (lightweight lane, context map, finding schema, gate profiles) free of conflict with any in-scope requirement? [Conflict, Spec §FR-027]
- [ ] CHK033 Does the spec avoid a conflicting account of who owns the corrective-loop bound (native `max_iterations`) versus the completion guarantee (SpecOps terminal gate)? [Conflict, Spec §FR-015/§FR-019]

## Notes

- These items test whether the **requirements are well-written** (complete, clear, consistent, measurable), not whether code works. Check `[x]` when the spec satisfies the item; an unchecked item marks a requirements-quality gap to resolve (or consciously defer) before `/speckit-plan`.
- Highest-risk gaps to weigh before planning: CHK002, CHK003, CHK004 (unspecified persisted/contract shapes), CHK007 (reconciliation cadence), CHK012 (terminal-gate nature), CHK006/CHK026 (mid-flight adoption & greenfield). Several are legitimately plan-level; mark those as deferred rather than blocking.
