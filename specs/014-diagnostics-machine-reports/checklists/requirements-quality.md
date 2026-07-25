# Requirements Quality Checklist: Diagnostics and Machine Reports

**Purpose**: Validate that the requirements for the read-only diagnostic (`specops doctor`) and status-report surface are complete, clear, consistent, and measurable — with particular rigor on failure semantics, upgrade behavior, and backward compatibility (per the roadmap's requirements-quality gate).
**Created**: 2026-07-25
**Feature**: [spec.md](../spec.md)

**Note**: These are "unit tests for the requirements" — each item interrogates the written spec, not the eventual implementation. An item passes when the spec answers it unambiguously and testably.

## Requirement Completeness

- [x] CHK001 - Are requirements defined for every diagnostic domain the feature claims to cover (CLI/extension compatibility, integration health, legacy artifacts, configuration, feature identity, ledger schema, context-map health, workflow/ledger divergence, gate availability)? [Completeness, Spec §FR-003]
- [x] CHK002 - Is the machine-readable output's required content (per-domain result, per-finding severity, message, next-action code + text, overall verdict, schema version) fully enumerated? [Completeness, Spec §FR-006/§FR-004/§FR-018]
- [x] CHK003 - Are the required fields of the compact status report (identity, phase, task progress, review/handoff state, workflow lane) each specified for both human and machine forms? [Completeness, Spec §FR-014]
- [x] CHK004 - Does the spec state requirements for the human-readable output mode, or only the machine-readable mode? [Gap, Spec §FR-006]
- [x] CHK005 - Are requirements defined for how the `next_action_code` enum values are enumerated/documented, not just that one exists? [Completeness, Spec §FR-004]
- [x] CHK006 - Is it specified whether a report includes findings for domains that evaluate to `ok`, or only non-`ok` domains? [Gap, Spec §FR-013]

## Requirement Clarity & Measurability

- [x] CHK007 - Is each severity level (`ok`, `warning`, `blocking`, `execution-error`) defined with objective criteria for when it applies, rather than left to interpretation? [Clarity, Spec §FR-002]
- [x] CHK008 - Is "byte-identical output across repeated runs" defined precisely enough to be objectively verified (stable ordering, excluded volatile fields)? [Measurability, Spec §FR-007/§SC-005]
- [x] CHK009 - Is "the SpecOps-specific delta" (what `doctor` adds beyond `specify check` / `specify workflow status`) defined concretely enough to draw the boundary? [Clarity, Spec §FR-011]
- [x] CHK010 - Is "ambiguous repository or active-feature identity" defined with specific conditions that trigger the fail-closed `blocking` finding? [Clarity, Spec §FR-012]
- [x] CHK011 - Is "workflow/ledger divergence" defined in terms of what is compared (ledger commits vs Git tree vs workflow state) precisely enough to be testable? [Clarity, Spec §FR-003(h)]
- [x] CHK012 - Can "supported, explicitly-reported state" for a missing context map be objectively distinguished from an error state? [Measurability, Spec §FR-009]
- [x] CHK013 - Are the success criteria expressed as measurable outcomes independent of implementation (e.g., SC-002 100%-domain coverage, SC-005 byte-identical)? [Measurability, Spec §SC-001..§SC-008]

## Requirement Consistency

- [x] CHK014 - Is the severity → overall-verdict → exit-code mapping internally consistent across FR-005, FR-008, and the acceptance scenarios? [Consistency, Spec §FR-005/§FR-008]
- [x] CHK015 - Is the `ok`/informational treatment consistent between "missing context map" (FR-009) and "no active feature" (FR-010) and their acceptance scenarios? [Consistency, Spec §FR-009/§FR-010/§US1]
- [x] CHK016 - Do the clarifications (Session 2026-07-25) and the functional requirements they touch (FR-004, FR-010, FR-012a, FR-015a) agree with no residual contradictory text? [Consistency, Spec §Clarifications]
- [x] CHK017 - Is the term "preflight" used consistently for the gate suite across all requirements (no leftover "review" for the deterministic gate)? [Consistency, Spec §FR-015a, Feature 017]
- [x] CHK018 - Are the read-only guarantees stated consistently for both `doctor` (FR-001) and the status report (FR-014), with no command exempted? [Consistency, Spec §FR-001/§FR-014]

## Failure Semantics

- [x] CHK019 - Are the conditions distinguishing `execution-error` (diagnostic could not run) from `blocking` (a real defect found) specified unambiguously? [Clarity, Spec §FR-008/§FR-015]
- [x] CHK020 - Is the required behavior specified for every enumerated failure input: unreadable ledger, unsupported/too-new ledger schema, invalid context map, ledger commit absent from Git tree, unresolvable gate command? [Completeness, Spec §Edge Cases/§FR-015/§FR-015a]
- [x] CHK021 - Is it required that a domain which cannot be evaluated is never silently reported as `ok` or omitted? [Coverage, Spec §FR-015]
- [x] CHK022 - Is the fail-closed behavior on ambiguous identity specified as `blocking` (never a best-guess proceed)? [Failure Semantics, Spec §FR-012]
- [x] CHK023 - Are requirements defined for the "multiple problems at once" case (report all findings; verdict = most severe; never stop at first)? [Coverage, Spec §FR-013/§Edge Cases]
- [x] CHK024 - Is the not-a-Spec-Kit-repo / SpecOps-not-installed case specified to produce a named finding rather than an unhandled crash? [Edge Case, Spec §Edge Cases]

## Upgrade & Versioning Behavior

- [x] CHK025 - Is it required that the machine-readable output carries an explicit schema/version identifier so consumers can detect format changes? [Completeness, Spec §FR-018]
- [x] CHK026 - Is the versioning relationship between the output schema and the `next_action_code` enum specified (are codes versioned with the schema)? [Clarity, Spec §Clarifications/§FR-004]
- [x] CHK027 - Are requirements defined for how a consumer should detect and adapt to a future output-format change (forward-compatibility expectation)? [Gap, Spec §FR-018]
- [x] CHK028 - Is it specified whether adding a new diagnostic domain or a new `next_action_code` value is a compatible change or requires a version bump? [Gap, Spec §FR-018]

## Backward Compatibility

- [x] CHK029 - Are requirements defined for reading prior ledger schema versions (v1 read compatibility through the current version) when diagnosing ledger schema health? [Compatibility, Spec §FR-003(f), Feature 006]
- [x] CHK030 - Is the expected behavior specified when the ledger is at a *supported prior* version versus an *unsupported/too-new* version (compatible read vs `blocking`)? [Clarity, Spec §Edge Cases/§FR-003(f)]
- [x] CHK031 - Do the requirements confirm the diagnostic reuses existing read paths (ledger, context map, traceability, handoff, gate profiles) without redefining those persisted formats? [Consistency, Spec §Assumptions]
- [x] CHK032 - Is compatibility with the Feature 007 CLI outcome contract and Principle VI exit-code semantics stated as a binding requirement rather than an aspiration? [Consistency, Spec §FR-008]

## Determinism, Acceptance Criteria & Testability

- [x] CHK033 - Is determinism required against explicitly identified volatile inputs (no wall-clock, no environment ordering) in both the payload and the next-action text? [Measurability, Spec §FR-004/§FR-007]
- [x] CHK034 - Is it required that the three exit-code classes (success, blocking, execution-error) are mutually distinguishable by exit code alone, with acceptance coverage? [Acceptance Criteria, Spec §FR-008/§US2/§SC-004]
- [x] CHK035 - Does each user story include an Independent Test that exercises the requirement without prescribing implementation? [Acceptance Criteria, Spec §US1/§US2/§US3]
- [x] CHK036 - Is the read-only guarantee expressed as an objectively checkable outcome (repository/ledger/context-map byte-for-byte unchanged) rather than a qualitative claim? [Measurability, Spec §SC-003/§US1]

## Non-Functional Requirements

- [x] CHK037 - Are the offline / no-telemetry / no-auto-repair constraints stated as binding requirements, not just non-goals? [Completeness, Spec §FR-017]
- [x] CHK038 - Is the EN/PT behavioral-equivalence requirement specified with a testable meaning (same domains, severities, next-action codes)? [Clarity, Spec §FR-016/§SC-008]
- [x] CHK039 - Is the gate-availability probe explicitly required to be side-effect-free (resolve on PATH, never execute)? [Non-Functional, Spec §FR-015a]

## Dependencies & Assumptions

- [x] CHK040 - Is the assumption that `specify check` and `specify workflow status` are available for deference documented, with defined behavior when they are absent (degrade path)? [Assumption, Spec §Assumptions/§FR-011, Roadmap Rule 5]
- [x] CHK041 - Is the deferred status-report command name recorded as an open decision with a stated constraint (must not overload the `specops status` verb group)? [Assumption, Spec §Assumptions]
- [x] CHK042 - Is the assumption that exit-code numeric values reuse the Feature 007 contract (rather than new codes) documented and traceable? [Assumption, Spec §Assumptions/§FR-008]
- [x] CHK043 - Is the active-feature scoping dependency (`.specify/feature.json` as the single source of the active feature) documented as an assumption/dependency? [Dependency, Spec §FR-012a]

## Ambiguities & Conflicts

- [x] CHK044 - Is a requirement & acceptance-criteria ID scheme established and used consistently for traceability (FR-###, SC-###, clarification bullets)? [Traceability]
- [x] CHK045 - Does "compact" (status report) avoid being an unquantified adjective, or is its meaning made concrete via the enumerated required fields? [Ambiguity, Spec §FR-014]
- [x] CHK046 - Is there any residual conflict between "report a result for each domain" (FR-013/SC-002) and only surfacing non-`ok` findings, that a reader could interpret two ways? [Conflict, Spec §FR-013/§SC-002]

## Notes

- Check items off as the spec is confirmed to answer them: `[x]`
- Unchecked items are requirement-writing gaps to resolve before `/speckit-plan`, not implementation tasks.
- Highest-leverage clusters for this feature: **Failure Semantics**, **Upgrade & Versioning**, and **Backward Compatibility** — the auditability guarantees the roadmap's Definition of Done calls out (versioned formats + forward-migration tests, read-only commands, fail-closed on ambiguity).
