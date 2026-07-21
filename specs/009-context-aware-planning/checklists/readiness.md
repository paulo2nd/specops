# Planning Readiness Checklist: Context-Aware Planning and Impact

**Purpose**: Validate that the requirements in spec.md are complete, unambiguous, measurable, and consistent before `/speckit-plan` — with emphasis on the roadmap's Feature 009 gate criteria: requirements completeness, testability, failure semantics, upgrade behavior, and backward compatibility, plus this feature's central risks: **explainable, bounded impact expansion** and **plan-vs-ledger consistency**.
**Created**: 2026-07-21
**Feature**: [spec.md](../spec.md)

**Note**: These are "unit tests for the requirements." Each item questions whether the spec is *written* correctly, not whether the eventual implementation *works*. Check an item only when the underlying requirement is present, clear, and testable in the spec.

## Requirement Completeness

- [x] CHK001 Is the plan-side declaration surface for context IDs and planned paths defined concretely enough to test FR-002/FR-003/FR-004, or is its deferral to `/speckit-plan` explicitly bounded so the requirement stays verifiable? [Completeness, Gap, Spec §FR-002, §Assumptions]
- [x] CHK002 Is the behavior specified for a declared path that matches **no** context at all (unowned), as distinct from a path owned by an *undeclared* context? [Gap, Spec §FR-004]
- [x] CHK003 Is the traversal **direction** of "declared dependents" in `context impact` specified (reverse edges — contexts that depend *on* the changed context — vs the forward expansion Feature 008 resolution performs)? [Ambiguity, Spec §FR-006, §US2]
- [x] CHK004 Is the shape of the ledger provenance record defined (list of resolved context IDs + map digest + explicit no-map marker), including its ledger schema-version implications under Feature 006? [Completeness, Gap, Spec §FR-009, §FR-010]
- [x] CHK005 Is the set of lifecycle phases for which a "minimal phase-specific read set" is resolved enumerated as a closed list (planning, implementation, review) and tied to Feature 008's authoritative phase names? [Completeness, Consistency, Spec §FR-001]
- [x] CHK006 Are the metadata fields surfaced by `context impact` (contracts, tests, gates, risks) defined by reference to Feature 008's context schema, so their shape is not re-invented here? [Completeness, Spec §FR-006, §Assumptions]
- [x] CHK007 Is the "map digest" definition/derivation stated as reused-from-Feature-008 and required to be computed identically at plan time and review time (so a comparison is meaningful)? [Completeness, Spec §FR-009, §SC-008, §Assumptions]
- [x] CHK008 Is an error/diagnostic object shape defined for JSON mode (stable error identifier + message) for every new blocking outcome, so failures are machine-actionable? [Gap, Spec §FR-014, §FR-016]
- [x] CHK009 Is the behavior of the new stale-detection command specified with respect to non-tracked, gitignored, or symlinked files when deciding "no longer matches any file"? [Gap, Spec §FR-011]

## Requirement Clarity & Measurability

- [x] CHK010 Is "minimal read set" defined objectively (e.g., exactly the Feature 008-resolved package with nothing added), so SC's "minimal/reasoned scope" is testable rather than subjective? [Measurability, Spec §FR-001, §SC-002]
- [x] CHK011 Is "explained" given a closed enumeration of edge types — ownership, dependency, policy — and is "policy edge" defined (mapped to Feature 008 gate/policy metadata)? [Clarity, Spec §FR-007, §SC-002]
- [x] CHK012 Is the objective trigger for "would-be unbounded / unexplained expansion" defined, so FR-008's "reports the condition instead of reading the whole repository" is decidable? [Ambiguity, Spec §FR-008, §SC-003]
- [x] CHK013 Is the ordering rule for `context impact` output (affected contexts, dependents, metadata) specified, so byte-for-byte determinism is verifiable? [Clarity, Spec §FR-015, §SC-001]
- [x] CHK014 Is the non-blocking digest-drift outcome represented as a specific, stable status token in human and JSON output (not only described in prose)? [Clarity, Spec §Clarifications Q1, §SC-008]
- [x] CHK015 Is "stale reference" defined precisely (owning context + the declared pattern that now matches zero files), so the reported object is testable? [Clarity, Spec §FR-011, §Key Entities/Stale Reference]

## Requirement Consistency

- [x] CHK016 Are FR-002 (missing context declaration is blocking) and FR-005 (an unpredicted discovered file is NOT blocking) explicitly reconciled so they cannot be read as contradictory? [Conflict, Spec §FR-002, §FR-005]
- [x] CHK017 Is each new blocking condition (missing required declaration, unknown declared ID, undeclared owner, invalid/ambiguous map) mapped to exit `1` consistently with Feature 008's `0`/`1`/`2` taxonomy and `status` field? [Consistency, Spec §FR-016, §FR-017]
- [x] CHK018 Is terminology for the declaration input consistent ("context declaration", "declared context IDs", "declared topology", "planned paths") across FRs, User Stories, and Key Entities? [Consistency, Spec §FR-002, §Key Entities]
- [x] CHK019 Does SC-006's provenance claim ("explicit empty/no-map marker") match FR-009 and US3 Scenario 3 (no lingering "omit cleanly" wording that implies field absence)? [Consistency, Spec §FR-009, §SC-006, §US3]
- [x] CHK020 Is the phrase "ownership is not a write-permission boundary" applied consistently wherever ownership validation is described (FR-004, Edge Cases), so review scope and declaration checks use the same meaning? [Consistency, Spec §FR-004, §Edge Cases]

## Failure Semantics & Fail-Closed Behavior

- [x] CHK021 Is the fail-closed deferral to `context validate` (on invalid/ambiguous/unsupported map) specified for **each** consuming surface — planning display, `context impact`, and stale detection — not only in the abstract? [Coverage, Spec §FR-017]
- [x] CHK022 Is behavior specified when `context impact` must derive its default change set but Git is unavailable, the repo has no baseline, or the working tree is clean? [Gap, Exception Flow, Spec §FR-006, §Clarifications Q3]
- [x] CHK023 Are atomicity/concurrency guarantees for writing provenance into the ledger stated (inherited from Feature 006), so an interrupted provenance write cannot corrupt a record? [Gap, Spec §FR-009, §FR-012]
- [x] CHK024 Is it specified that read-only consuming commands leave repository and ledger state byte-identical (before/after), including when they fail closed? [Coverage, Spec §FR-012, §SC-007]

## Backward Compatibility & Upgrade

- [x] CHK025 Is forward behavior specified when a pre-feature ledger (without provenance) is read and then written — does it gain provenance on next write, and does the ledger schema version bump deterministically? [Upgrade, Gap, Spec §FR-018]
- [x] CHK026 Is a non-regression requirement stated that Feature 008's `context validate`, `resolve`, and `explain` behavior is unchanged by this feature? [Backward Compatibility, Spec §FR-011, §Clarifications Q2]
- [x] CHK027 Is it required that consumers of existing task/review records tolerate the newly added provenance fields (additive, non-breaking record shape)? [Backward Compatibility, Spec §FR-009, §FR-018]

## Scenario Coverage

- [x] CHK028 Are requirements for the primary flow (declare topology → resolve/display minimal reads → validate) complete, clear, and testable end to end? [Coverage, Primary, Spec §US1, §FR-001–FR-004]
- [x] CHK029 Are requirements for the map-absent alternate flow defined for **every** new surface (no declaration required, provenance marker, impact/stale behavior)? [Coverage, Alternate, Spec §FR-013, §US1 Scenario 4]
- [x] CHK030 Is the recovery/resume scenario specified — a fresh session reconstructing which contexts and map digest a task/review targeted from ledger provenance alone? [Coverage, Recovery, Spec §FR-010, §US3]
- [x] CHK031 Are exception flows (unknown declared ID, undeclared owner, invalid map) each backed by a distinct, testable requirement rather than a single generic "fails closed"? [Coverage, Exception, Spec §FR-003, §FR-004, §FR-017]

## Edge Case Coverage

- [x] CHK032 Is the interaction between a declared path that is valid-but-matches-zero-files (valid per Feature 008) and stale detection / topology validation defined, so the two do not disagree? [Edge Case, Ambiguity, Spec §FR-004, §FR-011]
- [x] CHK033 Are the enumerated edge cases (empty change set, dependency cycle during impact, moved-not-removed paths, ambiguous/absent owner) each traceable to a functional requirement or success criterion? [Coverage, Traceability, Spec §Edge Cases]

## Dependencies & Assumptions

- [x] CHK034 Is the assumption that a deterministic map digest is already emitted by Feature 008 validated (i.e., a real 008 output), rather than presumed? [Assumption, Spec §Assumptions]
- [x] CHK035 Is the dependency on Feature 006's versioned, concurrency-safe ledger for provenance storage stated as a precondition with an explicit schema-extension path? [Dependency, Spec §Assumptions, §FR-009]
- [x] CHK036 Is the deferral of scope-drift acknowledgement to Feature 010 stated clearly enough that FR-005's "reported but not blocking" is unambiguous and does not silently require an unbuilt capability? [Assumption, Spec §FR-005, §Complement Boundary]

## Notes

- Items are intentionally unchecked: this is a pre-plan gate. Resolve or consciously accept each item (and encode the decision back into `spec.md` via `/speckit-clarify` where it changes requirements) before `/speckit-plan`.
- Highest-leverage items for this feature: CHK003 (dependent traversal direction), CHK011–CHK012 (explainability/bounded expansion — the acceptance-gate risk), CHK016 (declaration-blocking vs discovered-file-non-blocking), and CHK025 (ledger upgrade behavior).
