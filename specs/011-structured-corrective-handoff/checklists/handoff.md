# Requirements Quality Checklist: Structured Corrective Handoff

**Purpose**: Validate the *requirements* in `spec.md` for completeness, testability, failure semantics, upgrade behavior, and backward compatibility before `/speckit-plan` (roadmap step 2). This is a "unit test for the English", not a test of any implementation.
**Created**: 2026-07-22
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [ ] CHK001 Is the **finding ID scheme** (its format and the deterministic assignment rule that keeps it stable across rounds, re-renders, resumes, and fresh sessions) specified in requirements, rather than only asserted as "assigned deterministically"? [Completeness, Gap, Spec §FR-001, §SC-001]
- [ ] CHK002 Is the enumeration of the stable `status` field values (the fine-grained outcomes behind exit `0`/`1`/`2`) specified, so the no-findings, legacy-degrade, blocked-approval, and each validation-defect states are distinguishable? [Completeness, Gap, Spec §FR-017]
- [x] CHK003 Is an **explicit schema-version field** required in every JSON output (a versioned contract for Features 012–014), not just "stable JSON"? [Completeness, Spec §FR-012]
- [x] CHK004 Are the **canonical ordering/sort keys** that make report, validation, and rendered-Markdown output deterministic defined in requirements? [Completeness, Spec §FR-025, §FR-018, §SC-011]
- [ ] CHK005 Are the required fields of a **Finding** record (ID, severity, rule, location with optional line, action, per-finding closure criteria, per-finding expected evidence) each specified with their presence/optionality? [Completeness, Spec §FR-001, §Key Entities]
- [ ] CHK006 Are the required fields of a **Corrective Handoff** record (authorized corrective paths, originating-cycle binding, contained findings) specified, including the shape when a round has zero findings? [Completeness, Spec §FR-002, §Key Entities]
- [x] CHK007 Is the representation of **"expected evidence"** — the declared per-finding expectation set at creation versus the actual `<CLASS>:<summary>` evidence linked at `FIXED` — specified precisely enough to evaluate the `VERIFIED` precondition? [Completeness, Ambiguity, Spec §FR-001, §FR-005, §FR-006]
- [x] CHK008 Does the spec define the **authoring flow** — which command/lifecycle phase creates the structured findings, and how that relates to the rendered `revision-X.md` (structured-first, Markdown projected) — rather than leaving it implicit? [Completeness, Gap, Spec §FR-013, §FR-006]
- [x] CHK009 Is the roadmap-required ability to **close a corrective handoff** (as distinct from per-finding `VERIFIED`) represented as a requirement, or is handoff-level closure left undefined? [Completeness, Gap, Spec §FR-007, §Feature 011 required outcomes]
- [ ] CHK010 Is a **human-readable vs JSON parity** guarantee stated (both render the same finding chain and remaining-blocking set), not merely that both forms exist? [Completeness, Spec §FR-012]

## Requirement Clarity & Measurability

- [ ] CHK011 Is **"concise action"** bounded with a measurable constraint (length/format), or is it an unquantified adjective? [Clarity, Ambiguity, Spec §FR-001]
- [ ] CHK012 Is the **"rule violated"** field defined — a controlled vocabulary/namespace (e.g., Constitution principle IDs, gate names) versus free-form text — enough to be consistent across findings? [Clarity, Gap, Spec §FR-001]
- [ ] CHK013 Is **"expected evidence is present and its links resolve"** (the mechanical `VERIFIED` precondition) defined as an objectively checkable condition rather than a narrative one? [Measurability, Spec §FR-006, §Clarifications]
- [ ] CHK014 Can **"byte-for-byte identical output"** be objectively verified for the report, JSON, and rendered `revision-X.md` (trailing whitespace / locale ordering pinned)? [Measurability, Spec §FR-018, §FR-013, §SC-008]
- [ ] CHK015 Is **"compatible with prior revision-report consumers"** expressed as an objectively checkable fidelity criterion, rather than an unverifiable compatibility claim? [Measurability, Spec §FR-013, §SC-006]
- [x] CHK016 Is the boundary between the CLI's **deterministic guard** and the reviewer's **closure judgment** for `VERIFIED` stated unambiguously (CLI never semantically judges adequacy; no auto-verify)? [Clarity, Spec §FR-006, §Clarifications]

## Requirement Consistency

- [x] CHK017 Is the **severity label** (`blocking`/`advisory`) and the **gate class** term used consistently, so "blocking finding" always means a finding whose severity is `blocking`? [Consistency, Spec §FR-003, §FR-007]
- [ ] CHK018 Is the exit-code taxonomy internally consistent across all commands — every blocking condition (validation defect, blocked approval) maps to `1` and every usage condition (illegal transition, bad/unknown input) to `2`, with no overlap? [Consistency, Spec §FR-004, §FR-010, §FR-017]
- [ ] CHK019 Is a **`VERIFIED`-without-evidence** state handled coherently across the two surfaces that mention it — the transition guard rejecting it (exit `2`) and validation reporting it as a contradictory state (exit `1`) — without contradiction? [Consistency, Spec §FR-006, §FR-010, §SC-004]
- [x] CHK020 Is the **approval-block scope** (all unverified blocking findings across every round/handoff, feature-global) stated consistently with the carry-forward edge case, rather than ambiguously scoped to the latest round? [Consistency, Spec §FR-007, §Edge Cases]
- [ ] CHK021 Is **duplicate-finding-ID** handling consistent between creation-time rejection (usage error, exit `2`) and validation detection (defect, exit `1`)? [Consistency, Spec §FR-010, §Edge Cases]
- [x] CHK022 Is the responsibility split between **handoff validation** (surfaces a dangling commit reference) and **`specops reconcile`** (authoritative commit existence) stated without contradiction? [Consistency, Spec §FR-011]

## Failure Semantics & Exit-Code Coverage

- [x] CHK023 Is every **illegal lifecycle transition** (skip `OPEN→VERIFIED`, any backward move, precondition violation) required to fail closed (exit `2`) and leave the prior finding state unchanged, recording nothing? [Failure Semantics, Spec §FR-004, §SC-004]
- [x] CHK024 Is **concurrent transition** of the same finding required to be guarded by Feature 006's lock/compare-and-swap so a stale write fails closed without a lost update? [Failure Semantics, Spec §FR-002, §Edge Cases]
- [ ] CHK025 Are requirements defined for a **partially-written/interrupted** handoff or transition leaving the previous valid ledger readable (atomic, interruption-safe)? [Failure Semantics, Spec §FR-002]
- [x] CHK026 Is an **unrecognized severity** required to be a usage error (exit `2`) against the closed `blocking`/`advisory` set? [Failure Semantics, Spec §FR-003]
- [x] CHK027 Is the **exit code for a `VERIFIED` precondition failure** (expected evidence absent or links unresolved) explicitly specified in the requirement itself (FR-006), not only inferable from SC-004? [Failure Semantics, Gap, Spec §FR-006, §SC-004]
- [x] CHK028 Is a **blocked-approval** failure required to name the specific unverified blocking findings (actionable diagnostic), not merely refuse? [Failure Semantics, Spec §FR-007, §SC-003]

## Upgrade Behavior & Backward Compatibility

- [x] CHK029 Is an explicit **ledger schema-version increment** (v4 → v5) required for the new finding/handoff/lifecycle fields, not just described as "additive"? [Upgrade, Spec §FR-019, §Assumptions]
- [x] CHK030 Is a **forward-migration test obligation** for pre-feature ledgers stated as a requirement (per Global Definition of Done)? [Upgrade, Spec §FR-019, §SC-007]
- [x] CHK031 Are requirements clear that pre-feature records lacking finding/handoff fields are a **supported prior shape**, read without error and never reported as defects? [Backward Compatibility, Spec §FR-019, §Edge Cases]
- [x] CHK032 Is the interaction with the **existing Feature 006 `review_cycles` records** specified, so adding finding/handoff state preserves v4 read compatibility and does not invalidate prior cycle records? [Backward Compatibility, Gap, Spec §FR-019]
- [x] CHK033 Is the **Feature 010 trace re-sourcing** requirement precise — resolve findings to stable IDs from structured state when present, fall back to `revision-X.md` parsing otherwise, with no regression to the 010 report contract? [Backward Compatibility, Spec §FR-015, §SC-009]
- [x] CHK034 Is **legacy revision-prose import** required to preserve every line's location and action text with zero loss, and never to block reads? [Backward Compatibility, Spec §FR-014, §SC-007]

## Scenario & Edge-Case Coverage

- [x] CHK035 Is the **zero-findings review** case (no handoff created; approval unblocked by this feature) specified as a supported non-error? [Coverage, Spec §FR-007, §Edge Cases]
- [x] CHK036 Are **advisory-only open findings** required never to block approval (0% false-block), while still retained and reported? [Coverage, Spec §FR-003, §FR-008, §SC-003]
- [x] CHK037 Is the **legacy / no-structured-findings degrade** to Feature 006's existing gate specified so an upgraded repository is not retroactively blocked (roadmap Rule 5), while explicit `validate`/transition commands stay strict? [Coverage, Spec §FR-008, §Edge Cases]
- [x] CHK038 Is **finding carry-forward across review rounds** (verified findings stay `VERIFIED`, `FIXED`-but-unverified are re-examined, recurrences get new IDs) expressed as a functional requirement, not only in Edge Cases? [Coverage, Gap, Spec §FR-004, §Edge Cases]
- [x] CHK039 Is a correction touching a path **outside the authorized corrective paths** required to surface through Feature 010's drift classification rather than a new gate in this feature? [Coverage, Spec §FR-009, §Edge Cases]
- [x] CHK040 Is a **`VERIFIED` finding whose fix commit is absent** from the branch required to be reported as a dangling reference (deferring authoritative existence to reconcile)? [Coverage, Spec §FR-011, §Edge Cases]

## Dependencies, Assumptions & Traceability

- [x] CHK041 Is every outcome-producing functional requirement traceable to at least one measurable Success Criterion (FR-013 rendering → SC-006; FR-023 close → SC-010; FR-024 carry-forward → SC-011; exclusions FR-021/FR-022 and the doc-parity FR-026 are appropriately not SC-mapped)? [Traceability, Spec §Functional Requirements, §Success Criteria]
- [x] CHK042 Is the **English/Portuguese behavioral-equivalence** obligation expressed as a requirement, not only an assumption? [Coverage, Spec §FR-026]
- [ ] CHK043 Are the load-bearing dependencies (Feature 006 ledger + concurrency, Feature 010 finding↔path↔cycle linkage and drift, the `<CLASS>:<summary>` evidence format, reconcile ownership) each marked as validated dependencies rather than unverified premises? [Assumption, Spec §Assumptions]
- [x] CHK044 Are the roadmap non-goals — **no product-code modification, no issue-tracker integration, no parallel correction ownership** — expressed as enforceable requirements (ownership serialized by Feature 006 concurrency), not just narrative exclusions? [Traceability, Spec §FR-021]

## Notes

- Check items off as the spec is amended: `[x]`. Unchecked items are candidate gaps/ambiguities to resolve before planning, not implementation defects.
- ≥80% of items carry a `[Spec §…]`, `[Gap]`, `[Ambiguity]`, `[Conflict]`, or `[Assumption]` traceability marker.
- **Current state: 29/44 items passing.** Amendments (2026-07-22) closed the requirement-level gaps: **CHK008** authoring flow (FR-013), **CHK009** handoff close (FR-023), **CHK007** declared-expected vs actual-linked evidence (FR-001/005/006), **CHK004** canonical ordering (FR-025), **CHK020/CHK038** feature-global carry-forward (FR-024), **CHK027** `VERIFIED`-precondition exit code (FR-006), **CHK032** `review_cycles` compat (FR-019), **CHK042** EN/PT parity as a requirement (FR-026), **CHK041** FR↔SC traceability (SC-010/SC-011 added).
- **Remaining 15 open items are intentionally deferred to `/speckit-plan`** — they are concrete formats/wording, not missing requirements: finding-ID scheme (CHK001), `status` value enumeration (CHK002), field-optionality edges (CHK005/CHK006), JSON/human parity wording (CHK010), "concise action" bounding & rule vocabulary (CHK011/CHK012), determinism whitespace/locale pinning (CHK013/CHK014/CHK015), exit-code overlap audit (CHK018), `VERIFIED`-without-evidence two-surface coherence (CHK019), duplicate-ID creation-vs-validation exit (CHK021), interrupted-write atomicity (CHK025), and load-bearing-deps-as-validated (CHK043).
