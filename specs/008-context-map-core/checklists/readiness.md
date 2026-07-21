# Planning Readiness Checklist: Context Map Core

**Purpose**: Validate that the requirements in spec.md are complete, unambiguous, measurable, and consistent before `/speckit-plan` — with emphasis on the roadmap's Feature 008 gate criteria: requirements completeness, testability, failure semantics, upgrade behavior, and backward compatibility, plus determinism as the feature's central risk.
**Created**: 2026-07-20
**Feature**: [spec.md](../spec.md)

**Note**: These are "unit tests for the requirements." Each item questions whether the spec is *written* correctly, not whether the eventual implementation *works*. Check an item only when the underlying requirement is present, clear, and testable in the spec.

## Requirement Completeness

- [x] CHK001 Is a context-ID format/uniqueness rule specified (allowed characters, length, case sensitivity), beyond "stable unique ID"? [Completeness, Gap, Spec §Key Entities/Context]
- [x] CHK002 Is the set of valid lifecycle phase names that read sets may key on enumerated as an authoritative, closed list (specify/plan/tasks/implement/review)? [Completeness, Spec §Assumptions/Phases, §FR-009]
- [x] CHK003 Is `context resolve` behavior specified when given an explicit context ID that does not exist in the map (as distinct from a path that matches no context)? [Gap, Spec §FR-006, §FR-018]
- [x] CHK004 Is the CLI input contract for `resolve`/`explain` defined when both a path and an ID are supplied, or when neither is? [Gap, Spec §FR-006, §FR-010]
- [x] CHK005 Are validation rules specified for dependency edges that reference a non-existent context ID (dangling dependency), distinct from cycle detection? [Gap, Spec §FR-005, §FR-012]
- [x] CHK006 Are validation rules specified for gate/policy references (e.g., must a referenced gate identifier resolve, or is any string accepted)? [Gap, Spec §FR-002(e)]
- [x] CHK007 Is the structure and allowed value space of risk metadata defined, or is it explicitly free-form for this feature? [Completeness, Spec §FR-002(f)]
- [x] CHK008 Does the spec define whether `context validate` reports all defects in one pass or stops at the first, given a map with multiple independent defects? [Gap, Spec §FR-005]
- [x] CHK009 Is the exit-code contract enumerated for every outcome of every command — including "no matching context", "absent map", and "malformed map" — not only validate's 0/1? [Gap, Consistency, Spec §FR-004, §FR-013, §FR-018, Constitution §VI]
- [x] CHK010 Is an error/diagnostic object shape defined for JSON mode (stable error identifier + message), so failures are machine-actionable? [Gap, Spec §FR-015, §FR-019]

## Requirement Clarity & Measurability

- [x] CHK011 Is glob "specificity" defined as a *total* order — specifically, how "fewer wildcards" and "longer literal prefix" are prioritized when they disagree? [Ambiguity, Spec §FR-008]
- [x] CHK012 Is the ordering rule for a phase read set explicitly specified (what "ordered read set" is ordered by), so determinism is testable? [Clarity, Spec §FR-006, §SC-001]
- [x] CHK013 Is the ordering rule for the deduplicated expanded (transitive) read set specified (e.g., by edge order then path), rather than only asserted "deterministically ordered"? [Clarity, Spec §FR-012a, §SC-011]
- [x] CHK014 Is "stable JSON shape" defined with concrete criteria (guaranteed field presence, key ordering, null vs omitted handling)? [Clarity, Spec §FR-015, §SC-006]
- [x] CHK015 Is the supported schema-version range (or the single supported version) stated, so "unsupported version" is objectively decidable for both newer and older maps? [Clarity, Spec §FR-020, §SC-010]
- [x] CHK016 When `resolve` accepts either a path or an ID, is the disambiguation rule specified for an argument that could be read as both? [Ambiguity, Spec §FR-006]
- [x] CHK017 Is "no matching context" defined as a specific, stable outcome token in both human and JSON output, rather than described only in prose? [Clarity, Spec §FR-018, §SC-005]

## Requirement Consistency

- [x] CHK018 Are "invalid path pattern" and "unsafe path traversal" defined so they do not overlap ambiguously — is traversal a subclass of invalid, or a separate defect class with its own diagnostic? [Conflict, Spec §FR-005, §Clarifications]
- [x] CHK019 Do the defect classes in FR-005 and the fixtures asserted in SC-002 enumerate exactly the same set (no class in one and missing from the other)? [Consistency, Spec §FR-005, §SC-002]
- [x] CHK020 Is terminology consistent for a context's match declaration ("match rule", "glob pattern", "path pattern", "context rule") across FRs, Edge Cases, and Key Entities? [Consistency, Spec §FR-008, §Key Entities]
- [x] CHK021 Does the Reason Trace carry the same "stable/versioned shape" guarantee as the JSON output, or is its stability under-specified relative to FR-015? [Consistency, Gap, Spec §FR-011, §FR-015]

## Failure Semantics & Fail-Closed Behavior

- [x] CHK022 Is the fail-closed guarantee (no resolution emitted from an invalid/ambiguous map) stated to hold for a *partially* valid map, not only a wholly invalid one? [Coverage, Spec §FR-017, §SC-003]
- [x] CHK023 Is `context init` required to be atomic — leaving no partial map file if writing is interrupted or fails? [Gap, Exception Flow, Spec §FR-003, §FR-016]
- [x] CHK024 Are the read-only guarantees (validate/resolve/explain never mutate state) asserted to hold even on the error/failure paths, not just success paths? [Coverage, Spec §FR-016, §FR-013]
- [x] CHK025 Is a dependency cycle required to be reported deterministically (same participating IDs, same order) rather than merely "detected"? [Clarity, Spec §FR-012, §SC-008]

## Determinism & Testability

- [x] CHK026 Are all determinism-affecting inputs the resolver must be invariant to enumerated (filesystem ordering, locale, environment, and timezone/clock)? [Coverage, Spec §FR-007, §SC-001]
- [x] CHK027 Is every success criterion objectively measurable without inspecting implementation internals (e.g., "byte-for-byte identical", "distinct diagnostic per class")? [Measurability, Spec §SC-001..SC-012]
- [x] CHK028 Does each functional requirement that ships observable behavior have at least one corresponding measurable success criterion (FR→SC coverage)? [Traceability, Spec §Requirements, §Success Criteria]
- [x] CHK029 Is the "empty-but-valid map" outcome specified distinctly enough to be asserted separately from both "absent map" and "no matching context"? [Coverage, Spec §FR-014, §SC-005, §Edge Cases]

## Upgrade & Backward Compatibility

- [x] CHK030 Does the spec state whether schema migration is actually required for this first version (only one schema exists yet) or whether only the version field + rejection of unsupported versions is in scope? [Scope, Clarity, Spec §FR-020]
- [x] CHK031 Is a compatibility guarantee stated for the JSON output contract across SpecOps releases (what may change without a version bump vs. what constitutes a breaking change)? [Gap, Spec §FR-015]
- [x] CHK032 Is the reuse of Feature 006's versioning/serialization/migration discipline stated as a validated dependency rather than an untested assumption? [Assumption, Spec §Dependencies, §FR-020]

## Dependencies & Assumptions

- [x] CHK033 Is the SpecOps namespace/location for the map (`.specify/specops/…`) explicitly marked as an open decision for planning rather than an implied requirement? [Assumption, Spec §Assumptions/Namespace, §FR-001]
- [x] CHK034 Are the non-goal boundaries (no source parsing, no gate execution, no planning/review integration) stated clearly enough that a reviewer can reject scope creep against them? [Completeness, Spec §Complement Boundary, §Assumptions]

## Notes

- Focus areas (roadmap step 2): requirements completeness, testability, failure semantics, upgrade behavior, backward compatibility — plus determinism (feature's central risk).
- Depth: formal planning-readiness gate. Audience: spec author + planning reviewer.
- Items marked `[Gap]`/`[Ambiguity]`/`[Conflict]`/`[Assumption]` indicate the requirement is currently missing, under-specified, potentially contradictory, or an unvalidated assumption — resolve or consciously defer each before `/speckit-plan`.
- Unchecked items are candidate inputs to a second `/speckit-clarify` pass or to explicit resolution during planning.
