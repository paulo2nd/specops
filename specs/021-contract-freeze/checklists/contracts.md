# Contract-Freeze Requirements Quality Checklist: Contract Freeze for 1.0

**Purpose**: Validate the *quality* of the freeze requirements — completeness, clarity, consistency, and measurability of the stability contract — before planning. Release-gate rigor; audience: PR reviewer.
**Created**: 2026-07-28
**Feature**: [spec.md](../spec.md)

**Note**: This checklist tests the requirements themselves ("unit tests for English"), not the implementation. Each item asks whether something is *specified well*, not whether code *works*.

## Requirement Completeness

- [x] CHK001 Are the frozen fields of each persisted format (`specops.json`, `status.yaml`, `lane.yaml`, gate-profile files) enumerated so "frozen shape" is concrete rather than abstract? [Completeness, Gap, Spec §FR-004]
- [x] CHK002 Are the gate-profile files identified specifically enough to freeze — which files and which fields count as the frozen surface? [Completeness, Spec §FR-001]
- [x] CHK003 Is the findings-input contract's frozen shape, and the location/name of its contract-version field, specified? [Completeness, Spec §FR-006]
- [x] CHK004 Are the base command-result envelope's stable/common keys enumerated, rather than referenced only as "stable common keys"? [Completeness, Ambiguity, Spec §FR-004]
- [x] CHK005 Does the spec define *where* "documented per-command envelope extensions" are documented, so an allowed extension field is decidable from a forbidden one? [Gap, Spec §FR-007]
- [x] CHK006 Are increment semantics specified for the base-envelope `output_version` **and** each existing per-report `output_version` individually? [Completeness, Spec §FR-009]
- [x] CHK007 Is the location/home of the published stability policy specified (where it lives, how an adopter discovers it)? [Gap, Spec §FR-001]
- [x] CHK008 Does the spec identify which surfaces are already versioned versus newly versioned, so the frozen-baseline set is complete? [Completeness, Spec §Key Entities]

## Requirement Clarity

- [x] CHK009 Is "additive (non-breaking) change" defined with objective per-surface criteria rather than as a bare label? [Clarity, Spec §FR-002]
- [x] CHK010 Is "breaking change" defined symmetrically and unambiguously against "additive"? [Clarity, Spec §FR-002]
- [x] CHK011 Is "schema-level" locking clarified to distinguish shape/type locking from value locking? [Ambiguity, Spec §FR-004]
- [x] CHK012 Is "frozen shape" defined consistently across persisted files and JSON envelopes (fields, types, ordering, optionality)? [Clarity, Spec §FR-004]
- [x] CHK013 Is "behaviorally equivalent" for the EN/PT documentation tied to an objective check with a pass/fail definition? [Clarity, Spec §FR-011]
- [x] CHK014 Is "the existing migration-test mechanism" identified precisely enough to reuse without ambiguity? [Clarity, Spec §FR-008]
- [x] CHK015 Is the initial value of the newly-added base-envelope `output_version` defined? [Clarity, Gap, Spec §FR-009]

## Requirement Consistency

- [x] CHK016 Are FR-005 and FR-014 consistent on the meaning and ordering of exit codes `1` and `2`? [Consistency, Spec §FR-005, §FR-014]
- [x] CHK017 Is FR-012's "single sanctioned code delta" consistent with FR-009 introducing exactly the base-envelope `output_version` and nothing else? [Consistency, Spec §FR-009, §FR-012]
- [x] CHK018 Are FR-001 ("classify all seven as frozen") and FR-003 (sweep default + "still-evolving") consistent about when "still-evolving" may ever apply? [Consistency, Spec §FR-001, §FR-003]
- [x] CHK019 Is the "no schema bump" posture (SC-007) consistent with adding an envelope `output_version` and pinning ledger v7? [Consistency, Spec §SC-007, §FR-009]
- [x] CHK020 Do the Assumptions and FR-005 use identical exit-code→meaning mappings (no drift between the two statements)? [Consistency, Spec §Assumptions, §FR-005]

## Acceptance Criteria Quality (Measurability)

- [x] CHK021 Is SC-003 objectively measurable for every frozen surface (a breaking change fails ≥1 test **and** names the surface)? [Measurability, Spec §SC-003]
- [x] CHK022 Is SC-004's "zero false failures" bounded by a defined, enumerable set of additive/versioned change cases? [Measurability, Spec §SC-004]
- [x] CHK023 Is SC-001's "zero observable-but-unclassified surfaces" backed by a defined enumeration of what counts as an observable surface? [Measurability, Spec §SC-001]
- [x] CHK024 Are SC-009 and SC-010 stated as objectively countable outcomes (codes named = codes locked; report version fields changed = 0)? [Measurability, Spec §SC-009, §SC-010]
- [x] CHK025 Is the atomicity requirement — the constitution amendment landing "in the same change set" — objectively observable? [Measurability, Spec §FR-014]

## Scenario & Edge-Case Coverage

- [x] CHK026 Are requirements defined for a permitted additive change **after** the freeze that must pass the contract tests? [Coverage, Spec §FR-007]
- [x] CHK027 Are requirements defined for a sweep-discovered surface outside the named seven (classification + frozen-by-default)? [Coverage, Spec §FR-003]
- [x] CHK028 Are requirements defined for a deprecated alias still inside its window during the freeze (must not be removed)? [Coverage, Spec §FR-012]
- [x] CHK029 Are requirements defined for the rc-criterion-not-met-at-merge case (freeze lands, rc tag waits)? [Coverage, Spec §FR-013]
- [x] CHK030 Are requirements defined for an already-versioned persisted format (pin current version, state the forward bump-plus-migration obligation)? [Coverage, Spec §FR-008]
- [x] CHK031 Are requirements defined for a JSON envelope carrying per-command extra fields (lock stable keys while allowing documented extensions)? [Coverage, Spec §FR-007]

## Governance, Dependencies & Assumptions

- [x] CHK032 Is the Principle VI amendment scope bounded (documents exit `2` only; no principle redefinition) with its SemVer level stated? [Clarity, Spec §FR-014, §Assumptions]
- [x] CHK033 Are the No-Self-Application constraints reflected in how the contract tests obtain evidence (fixtures/test artifacts only, never running `specops` on this repo)? [Consistency, Spec §Assumptions]
- [x] CHK034 Is the assumption that the release owner declares the real-usage criterion documented as out-of-band from this feature's code and tests? [Assumption, Spec §FR-013]
- [x] CHK035 Is the Feature 017 alias/deprecation-window dependency documented with its exact terms (remove no earlier than next MINOR, never in a patch)? [Dependency, Spec §FR-010]
- [x] CHK036 Is the dependency on the existing ledger migration-test mechanism documented as present and reused rather than built here? [Dependency, Spec §FR-008, §Assumptions]

## Notes

- Check items off as the spec is confirmed to satisfy each requirements-quality question: `[x]`.
- An unchecked item flags a spec gap/ambiguity to resolve (or consciously accept) **before** `/speckit-plan`, not an implementation defect.
- Highest-risk clusters for this feature: **enumeration completeness** (CHK001–CHK008 — "frozen shape" is only a real contract if the fields are named) and **additive-vs-breaking clarity** (CHK009–CHK011 — the whole freeze hinges on that distinction being objective).
- **Verified 2026-07-28 (pre-implement)**: all 36 items confirmed satisfied against `spec.md`, `plan.md`, `data-model.md` (full field enumeration of all 7 surfaces), `contracts/` (stability + versioning + frozen-envelope), and the resolved clarifications + `/speckit-analyze` pass (100% FR/SC coverage, 0 critical/high). CHK001–008 closed by `data-model.md`; CHK009–011 by the clarifications + stability-policy per-surface rules; CHK013 by the SC-006 correction (objective = dual-language presence, equivalence manual).
