# Requirements Quality Checklist: Gate Profiles and Structured Evidence

**Purpose**: Validate the *requirements* in `spec.md` for completeness, clarity,
consistency, testability, failure semantics, upgrade behavior, and backward
compatibility (roadmap Requirements-quality step) — before task generation. These are
"unit tests for the English": each item tests whether a requirement is well-written,
not whether the eventual code works.

**Created**: 2026-07-23
**Feature**: [spec.md](../spec.md)
**Triaged**: 2026-07-23 — all 35 items resolved (spec revised where a gap existed;
otherwise verified already-satisfied and marked with the governing requirement).

## Requirement Completeness

- [x] CHK001 - Default `timeout` value for the synthesized default profile — RESOLVED: FR-001 defines a documented constant default (600s in design). [Spec §FR-001/FR-005]
- [x] CHK002 - Default required-status classification — RESOLVED: FR-001 defaults required-status to `required`. [Spec §FR-001]
- [x] CHK003 - Present-but-empty profile list (`profiles: []`) — RESOLVED: FR-005 now treats an empty list like an absent file (synthesize default; never zero gates). [Spec §FR-005]
- [x] CHK004 - Evidence `commit_range` when no baseline — RESOLVED: FR-006 now specifies `baseline..HEAD` or a single commit sha when no baseline exists. [Spec §FR-006]
- [x] CHK005 - Malformed legacy `evidence` string during migration — RESOLVED: FR-007 requires verbatim preservation as an opaque record. [Spec §FR-007]
- [x] CHK006 - Migration failure / rollback semantics — RESOLVED: FR-007 requires the prior valid ledger to remain readable (atomic, no partial state). [Spec §FR-007/FR-019]
- [x] CHK007 - Does an optional gate produce evidence + participate in caching — SATISFIED: FR-006 records "every gate result"; FR-009 caching is not restricted by required-status. [Spec §FR-006/FR-009]
- [x] CHK008 - Consumers of existing `lint`/`test` gate names — RESOLVED: FR-005 now requires the default profile to preserve the `lint`/`test` names (no regression until a custom profile is authored). [Spec §FR-005/FR-011]
- [x] CHK009 - SARIF version pinned — RESOLVED: FR-013 pins SARIF 2.1.0 and the severity mapping. [Spec §FR-013]

## Requirement Clarity & Measurability

- [x] CHK010 - Unit of `timeout` — RESOLVED: FR-001 states a positive integer of seconds. [Spec §FR-001/FR-010]
- [x] CHK011 - "version" component of `producer` — RESOLVED: FR-006 now states "plus the SpecOps CLI version". [Spec §FR-006]
- [x] CHK012 - Artifact-digest determinism — RESOLVED: FR-006 requires a "deterministic content digest"; FR-019 makes a later change detectable. [Spec §FR-006/FR-019]
- [x] CHK013 - How `unavailable` is detected vs `failed` — SATISFIED: FR-008 defines `unavailable` = missing command/absent tool, distinct from `failed` = ran and did not satisfy required status; the detection mechanism is an implementation detail. [Spec §FR-008]
- [x] CHK014 - Reason values enumerated for testability — RESOLVED: FR-003 now defines a closed reason set (`always`/`matched-context`/`matched-gate-ref`/`matched-path`/`matched-risk-key`/`out-of-scope`), also removing the stale `risk-threshold` example. [Spec §FR-003]
- [x] CHK015 - Risk named-key value-optional case — SATISFIED: FR-002 states "contains the named key (optionally equal to a declared value)". [Spec §FR-002]
- [x] CHK016 - Canonical sort keys tie-break — SATISFIED: FR-021 fully specifies the chains (gates: declared order → name; evidence: producer → timestamp → commit range). [Spec §FR-021]

## Requirement Consistency

- [x] CHK017 - Required-status vs failure semantics — RESOLVED: FR-001 states required-status *determines* failure semantics (one setting). [Spec §FR-001/FR-004]
- [x] CHK018 - Versioning terminology — RESOLVED: FR-012/SC-009 use `output_version` (JSON), distinguished from ledger `schema_version` and config `output_version`. [Spec §FR-012]
- [x] CHK019 - Order applies to the selected subset — RESOLVED: FR-004 now says "declared relative order … applies to the selected subset". [Spec §FR-004]
- [x] CHK020 - Determinism scoped to recorded state — RESOLVED: FR-017 scopes byte-for-byte determinism to recorded state, not client-command re-execution. [Spec §FR-017/FR-018]
- [x] CHK021 - `name` vs `gate_ref` identity — SATISFIED: FR-002 honors a context's `gates` list as an implicit context-id match "for the gates it names" (the gate `name` is the `gate_ref` target). [Spec §FR-002]

## Failure Semantics & Exit Codes

- [x] CHK022 - Exit-code per failure class — SATISFIED: FR-016 maps `0`/`1`/`2`, with `1` covering a required-gate failure or `unavailable` and any validation defect, `2` usage/input error; timeout → `failed` → required → exit `1`. [Spec §FR-016]
- [x] CHK023 - Required `unavailable` blocks, optional does not — SATISFIED: FR-016 ("a required-gate failure or `unavailable`") + FR-001/FR-004 (optional never blocks). [Spec §FR-008/FR-016]
- [x] CHK024 - Timeout failure semantics at requirement level — SATISFIED: FR-010 fully specifies terminate + `failed` + timeout reason, deterministic, no wall-clock in recorded output. [Spec §FR-010]
- [x] CHK025 - Concurrent evidence write — SATISFIED: FR-006 states writes are "guarded by Feature 006's concurrency control" (a requirement, not only an edge note). [Spec §FR-006]

## Upgrade & Backward Compatibility

- [x] CHK026 - Pre-feature ledgers readable, absent fields explicit — SATISFIED: FR-007 + SC-005 (100% of pre-feature ledgers remain readable) + SC-007 give a testable acceptance condition. [Spec §FR-007]
- [x] CHK027 - Migration idempotency — RESOLVED: FR-007 now requires the migration to be idempotent (re-running yields byte-identical state). [Spec §FR-007]
- [x] CHK028 - Legacy string retained alongside record — RESOLVED: FR-007 now requires retaining (never replacing) the legacy string field for Feature 010/011 rendering. [Spec §FR-006/FR-007]
- [x] CHK029 - No-context-map degrade — SATISFIED: FR-002 + the "No context map present" edge case + Assumptions state the degrade (context/risk match nothing; `always`/path still select), per roadmap Rule 5. [Spec §FR-002/§Edge Cases]

## Scenario & Edge-Case Coverage

- [x] CHK030 - Empty changed-path set — SATISFIED: the "Empty changed-path set" edge case specifies path-scoped gates `skipped`, global gates still run. [Spec §Edge Cases]
- [x] CHK031 - Artifact-digest-of-changed-content — SATISFIED: FR-019 + the "Artifact digest references content that changed" edge case cover detectability without remote storage. [Spec §FR-019/§Edge Cases]
- [x] CHK032 - Cache-invalidation vectors individually — SATISFIED: FR-009 "if any one differs, the cache MUST NOT be reused" (each vector individually). [Spec §FR-009]

## Dependencies & Assumptions

- [x] CHK033 - Ledger v5 assumption stated — SATISFIED: Assumptions state "the Feature 006 ledger (currently schema v5 after Feature 011)". [Spec §Assumptions]
- [x] CHK034 - Feature 009 `context impact` dependency documented — SATISFIED: FR-002 + Assumptions document composing Feature 008 contexts/risk and Feature 009 changed-path/impact resolution. [Spec §FR-002/§Assumptions]
- [x] CHK035 - Boundary vs Spec Kit native human `gate` — SATISFIED: FR-020 states the profile is a verification-command suite distinct from the native human `gate`, with no overlap/duplication. [Spec §FR-020]

## Notes

- All 35 items resolved: 18 required a spec revision (applied across FR-001/003/004/005/006/007/012/013/014/017 + SC-009); 17 were verified already-satisfied and annotated with the governing requirement.
- Items intentionally test requirement *quality*, not behavior; none should be read as "verify the gate runs".
</content>
