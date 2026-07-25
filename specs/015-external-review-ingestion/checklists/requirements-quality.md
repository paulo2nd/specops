# Requirements Quality Checklist: External Review Ingestion

**Purpose**: Validate the quality, completeness, and testability of the spec's requirements before implementation — with emphasis on the roadmap §2 dimensions: completeness, testability, failure semantics, upgrade behavior, and backward compatibility.
**Created**: 2026-07-25
**Reviewed**: 2026-07-25 (see Review Outcome)
**Feature**: [spec.md](../spec.md)

**Note**: These items test whether the REQUIREMENTS are well-written — not whether ingestion works. Each asks whether something is clearly, completely, and consistently specified.

## Requirement Completeness

- [x] CHK001 Are requirements defined for every ingestion step the feature adds (parse/validate, finding creation, provenance capture, digest capture, staleness evaluation, promotion), or only for the import invocation? [Completeness, Spec §FR-001..§FR-011]
- [x] CHK002 Is the boundary between "external ingestion" and "built-in review" (Feature 016) stated so this spec's scope is unambiguous? [Completeness, Spec §Overview/§Assumptions]
- [x] CHK003 Are requirements defined for what a producer identity must contain and for the name-without-version case? [Completeness, Spec §FR-003/§Edge Cases]
- [x] CHK004 Is the advisory-by-default rule specified as covering *all* import paths (JSON and SARIF), regardless of producer-declared severity? [Completeness, Spec §FR-005/§FR-011/§FR-012]
- [x] CHK005 Are requirements defined for **withdrawing/dismissing or demoting** an imported finding — in particular a *promoted-blocking* finding later judged a false positive — or is that path explicitly delegated to Feature 011's dismissal? [Gap→Resolved, Spec §FR-006/§Edge Cases]
- [x] CHK006 Is the interaction between a re-import and the Feature 011 finding lifecycle (an already-`VERIFIED` or `FIXED` matching finding) specified so re-import does not silently reset lifecycle state? [Completeness, Spec §FR-009/§FR-017]
- [x] CHK007 Are documentation and changelog obligations specified concretely enough to be checkable (which surfaces, which behavior, migration note)? [Completeness, Spec §FR-020]
- [x] CHK008 Is the input *medium* (a file path, stdin, etc.) either specified or explicitly deferred to planning rather than left silently unaddressed? [Completeness, Spec §Assumptions]

## Requirement Clarity & Measurability

- [x] CHK009 Is a finding's **content identity** for dedup/idempotency defined precisely (the exact tuple, and that the reviewed-diff digest is excluded)? [Clarity, Spec §FR-008/§Clarifications]
- [x] CHK010 Is "stale" defined by a concrete, per-finding condition (its own location/target digest no longer matches) rather than a vague "code changed"? [Clarity, Spec §FR-004/§FR-010/§Clarifications]
- [x] CHK011 Is "all-or-nothing import" expressed as an objectively verifiable outcome (zero findings recorded, every defect named, exit `2`)? [Measurability, Spec §FR-013/§SC-007]
- [x] CHK012 Is "advisory by default" measurable as an observable outcome (severity recorded `advisory`, does not block approval) independent of the producer's declared level? [Measurability, Spec §FR-005/§SC-002]
- [x] CHK013 Is "deterministic / byte-for-byte identical handoff state" stated as a checkable equivalence for identical input? [Measurability, Spec §FR-008/§SC-004]
- [x] CHK014 Are the success criteria (SC-001..SC-010) stated as pass/fail thresholds a reviewer can check without knowing the implementation? [Measurability, Spec §SC]
- [x] CHK015 Is the SARIF severity mapping stated concretely enough (every result lands `advisory`; out-of-set levels map to the safe default) to be evaluated deterministically? [Clarity, Spec §FR-012]
- [x] CHK016 Is the SARIF primary-location rule and the no-usable-location outcome specified precisely enough to be reproducible? [Clarity, Spec §FR-012/§Edge Cases]

## Requirement Consistency

- [x] CHK017 Is FR-012 ("a result with no usable location is a per-result defect") consistent with FR-013's all-or-nothing rule (defect aborts the whole import), with no residual "dropped silently" or "partial import" language? [Consistency, Spec §FR-012/§FR-013/§Clarifications]
- [x] CHK018 Do FR-008 (digest-independent identity) and FR-009 (re-import updates staleness in place) agree that a re-import after diff movement never creates a second record? [Consistency, Spec §FR-008/§FR-009/§Edge Cases]
- [x] CHK019 Is the advisory-by-default rule consistent everywhere (JSON FR-005, SARIF FR-011/FR-012, entities, SC-002) with no path that lets an external producer record `blocking` at import? [Consistency, Spec §FR-005/§FR-011]
- [x] CHK020 Are the "record, do not judge/validate" statements (FR-019) consistent with FR-006 requiring a human, audited promotion — i.e., the only path to blocking is human, not producer confidence? [Consistency, Spec §FR-006/§FR-019]
- [x] CHK021 Does each success criterion (SC-001..SC-010) trace to at least one functional requirement without orphan or conflicting claims? [Consistency/Traceability, Spec §SC/§FR]
- [x] CHK022 Is the "compose Feature 011 surface, add no second finding store/lifecycle" constraint stated consistently wherever it is relied on? [Consistency, Spec §FR-002/§FR-017]

## Failure & Exception Semantics

- [x] CHK023 Are requirements defined for each structural defect class (unknown/unsupported schema version, missing required field, invalid SARIF, missing producer) with a named, fail-closed outcome? [Failure Semantics, Spec §FR-013]
- [x] CHK024 Is the no-open-review-cycle case specified as a fail-closed usage error that creates no state? [Coverage, Spec §FR-014/§Edge Cases]
- [x] CHK025 Is the empty-but-valid document specified as a supported no-op success (exit `0`, no mutation), distinct from a defect? [Coverage, Spec §FR-013/§Edge Cases]
- [x] CHK026 Is ambiguous repository/feature identity required to fail closed before any import occurs? [Failure Semantics, Spec §FR-014]
- [x] CHK027 Is the interruption/atomicity requirement stated so a partial write cannot leave a half-imported handoff? [Failure Semantics, Spec §FR-002/§FR-013]
- [x] CHK028 Is a stale promoted-blocking finding's behavior specified (still gates, staleness reported, never silently trusted) rather than left implicit? [Coverage, Spec §FR-010/§User Story 4]

## Backward Compatibility & Upgrade Behavior

- [x] CHK029 Are requirements explicit that a pre-feature ledger with no ingestion state reads without error and its absence is never a defect? [Backward Compatibility, Spec §FR-015/§Edge Cases]
- [x] CHK030 Is the ledger schema-version increment plus a forward-migration test (findings lacking producer/digest/promotion fields upgrade without loss) required? [Upgrade Behavior, Spec §FR-015]
- [x] CHK031 Is it specified that imported findings flow through the existing Feature 011 report/lifecycle/approval **unchanged** (no redefinition of lifecycle or gate)? [Backward Compatibility, Spec §FR-017]
- [x] CHK032 Is the additive relationship to the Feature 012 SARIF *output* adapter stated so the input adapter reuses (not redefines) the version and mapping? [Consistency/Upgrade, Spec §FR-011/§Assumptions]

## Security & Trust Boundary

- [x] CHK033 Is it specified that producer identity and declared severity are recorded **as-declared** (provenance), never trusted to raise severity or authenticity — consistent with record-not-validate? [Trust Boundary, Spec §FR-005/§FR-012/§FR-019]
- [x] CHK034 Is the human triage promotion required to be **audited** (who/that a promotion occurred captured as state) so an escalation to blocking is attributable? [Coverage, Spec §FR-006]
- [x] CHK035 Is the read-only guarantee for ingestion read paths (report rendering, staleness reporting) stated and verifiable by before/after comparison? [Coverage, Spec §FR-016]

## Testability & Acceptance Evidence

- [x] CHK036 Does the spec require demonstrating **two distinct producers** (a JSON sample and a SARIF sample) as the roadmap acceptance gate, with observable provenance? [Testability, Spec §SC-005]
- [x] CHK037 Are the acceptance scenarios written so each can be evidenced by fixtures (report contents, exit code, ledger state) rather than internal behavior? [Testability, Spec §User Scenarios/§SC]
- [x] CHK038 Is the staleness outcome associated with an observable signal (report flags `stale`, recorded vs current digest visible) rather than an internal check? [Measurability/Testability, Spec §FR-010/§SC-006]

## Dependencies, Assumptions & Ambiguities

- [x] CHK039 Is the dependency on the Feature 009/010 effective-diff **digest representation** stated (staleness reuses it; no new drift gate)? [Dependency, Spec §FR-004/§FR-010/§Assumptions]
- [x] CHK040 Are plan-level deferrals (exact input-contract field names, promotion command spelling, SARIF primary-location rule, ledger field layout) explicitly named as deferred rather than left implicit? [Assumption, Spec §Assumptions]
- [x] CHK041 Is the orthogonality to Feature 017 (`review → preflight` rename) stated so this spec does not depend on it? [Assumption/Scope, Spec §Assumptions]

## Review Outcome (2026-07-25)

**41/41 — PASS** (one gap surfaced and resolved in the same pass).

- **CHK005 (Withdrawal / demotion of a promoted imported finding)** — **Resolved (2026-07-25).** The initial pass found the spec specified promotion (`advisory → blocking`, FR-006) and its durability across re-imports (FR-007) but was silent on *withdrawing* an escalation or dismissing an imported finding judged a false positive. Because redefining the finding lifecycle is a non-goal (FR-017), the consistent fix was to **delegate to Feature 011's existing dismissal/withdrawal path**. FR-006 and the "Promoted finding then re-imported" edge case were amended with an explicit delegation sentence; no new lifecycle is introduced.

## Notes

- Check items off as the spec is confirmed to satisfy each: `[x]`.
- An unchecked item means the spec (not the code) needs a clarification or addition before implementation.
- Failure-semantics items (CHK023–CHK028) and backward-compat items (CHK029–CHK032) are the roadmap §2 gating dimensions for this feature — all satisfied.
- Plan-level wiring items (CHK008, CHK016, CHK040) are satisfied by an **explicit deferral** in the spec's Assumptions, not by an in-spec decision.
