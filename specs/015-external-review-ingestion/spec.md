# Feature Specification: External Review Ingestion

**Feature Branch**: `015-external-review-ingestion`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "Add a versioned, stack-neutral input contract (JSON + an optional SARIF adapter) that ingests external review findings into the structured corrective handoff as advisory findings carrying producer and effective-diff-digest provenance and staleness detection, keeping bug-finding judgment with the producer and enforcement with SpecOps."

## Overview

SpecOps deliberately does not perform the bug-finding *judgment* itself: the always-on baseline is the agent's own `/specops-review` (Principle IV), a disciplined single-pass read of the diff against spec/plan/constitution. This feature lets a **stronger or specialized** external source — a multi-agent bug hunt, a static analyzer such as CodeQL or semgrep, or a human reviewer — feed the **same** structured corrective handoff (Feature 011) through a stable, versioned, stack-neutral input contract. The enforcement layer is thereby no longer limited to the built-in review.

SpecOps still never performs the bug-finding and never re-verifies a finding's correctness: it **records** the finding as a snapshot of judgment (like a human's review comment) and **gates** on that snapshot deterministically (Principle II/VI). The producer owns the judgment; SpecOps owns the record and the gate. This closes, on purpose, the boundary the roadmap draws — turning any external reviewer's output into enforceable, auditable handoff state without coupling SpecOps to any specific tool.

## Clarifications

### Session 2026-07-25

- Q: What set of fields determines that a re-imported finding is the *same* existing finding (idempotent, no duplicate) versus a new one? → A: **Content identity, digest-independent** — the tuple (producer, rule, location, concise action). Two imported findings with the same tuple are the same finding; a re-import updates that finding's staleness in place and never creates a duplicate, even after the effective diff has moved. The reviewed-diff digest is *not* part of identity.
- Q: When a document parses correctly but contains one or more individually-defective findings (e.g., a SARIF result with no usable location), what does the import do? → A: **All-or-nothing** — the whole import is rejected as a usage error (exit `2`) that names every defective finding, and no handoff state is created. A per-result defect is *named*, never silently dropped, and never a partial import.
- Q: An imported finding is stale when the current effective diff no longer matches what it was reviewed against; staleness is computed against what? → A: **Per-finding, against that finding's own path** (path granularity) — a finding is stale only when the path it points at has changed since it was reviewed; an unrelated change to another path does not stale it. SpecOps does not track sub-file/hunk precision.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest external findings through a versioned JSON contract (Priority: P1)

A review step (typically a stage of `/specops-review`, but a human may run it directly) has an external reviewer's output as JSON. It imports those findings into the current feature's corrective handoff with a single command. Each imported record becomes a structured finding (Feature 011) with a stable ID, carrying the producer that emitted it and the commit/effective-diff digest it was reviewed against. The findings now live in the same handoff the built-in review uses, reportable and enforceable through the existing surface.

**Why this priority**: This is the core of the feature. Without a stable input contract that lands external findings in the handoff, no external reviewer's judgment can ever become enforceable SpecOps state; every other story refines or hardens this one. It is the minimum viable slice: importing a JSON findings document and seeing the findings in `handoff report`.

**Independent Test**: Against a fixture feature with an open review cycle, import a sample JSON findings document and confirm `handoff report` renders the new findings with their producer and reviewed-digest provenance, each with a stable ID and `advisory` severity — proving external judgment became handoff state without any built-in review having run.

**Acceptance Scenarios**:

1. **Given** an open review cycle and a schema-valid JSON findings document, **When** the findings are imported, **Then** each finding is recorded in the corrective handoff with a stable ID, its declared rule/location/action, `advisory` severity (per Story 3), and its producer and reviewed-diff-digest provenance.
2. **Given** a JSON document that does not conform to the versioned input contract (unknown schema version, missing required field, or malformed structure), **When** import is attempted, **Then** it fails closed as a usage error, names the specific defect, and records no partial handoff state.
3. **Given** the same JSON document imported a second time, **When** import runs again, **Then** it is idempotent — no duplicate findings are created and the handoff state is byte-for-byte identical to the first import.

---

### User Story 2 - Ingest findings from a SARIF-emitting tool (Priority: P2)

A team runs a SARIF-emitting tool (CodeQL, semgrep, or an LLM reviewer that exports SARIF) and wants its results in the handoff without writing a converter. An optional SARIF **input** adapter — the complement of the Feature 012 SARIF *output* adapter — reads a SARIF document and maps each result into the same structured finding, preserving rule, location, and severity mapping, and recording the producing tool (name + version) as the finding's producer.

**Why this priority**: SARIF is the lingua franca of static analyzers and many LLM reviewers, so a SARIF path materially broadens what can feed the handoff. It is P2 because it is a second producer format layered on the P1 JSON contract — valuable and independently testable, but not required to prove the core ingestion path.

**Independent Test**: Import a sample SARIF document from a distinct producer against a fixture handoff and confirm each SARIF result becomes a structured finding whose rule, location, and severity round-trip correctly and whose producer records the tool name and version from the SARIF `tool.driver`.

**Acceptance Scenarios**:

1. **Given** a schema-valid SARIF 2.1.0 document, **When** it is imported through the SARIF adapter, **Then** each result becomes a structured finding preserving its rule, location, and severity mapping (all imported `advisory` per Story 3), carrying the tool's name and version as producer.
2. **Given** a SARIF document that is not valid SARIF 2.1.0, **When** import is attempted, **Then** it fails closed as a usage error naming the defect and records no partial state.
3. **Given** the JSON contract and the SARIF adapter each importing findings for the same feature, **When** both have run, **Then** both sets coexist in the handoff, each finding attributed to its own producer.

---

### User Story 3 - External findings are advisory until a human escalates them (Priority: P1)

Every imported finding lands as `advisory` by default, regardless of the severity the producer declared. An automated reviewer's confidence does not unilaterally block a merge. Promotion of an imported finding to `blocking` is an explicit, audited triage step performed by a human; only after that promotion — and the normal Feature 011 verification — does the finding gate approval.

**Why this priority**: This is the safety invariant that makes ingestion trustworthy and is inseparable from Story 1: without it, any external producer could block delivery on an unverified, possibly-wrong finding. It must ship with the core import path, so it is P1 alongside Story 1.

**Independent Test**: Import findings whose producer declared high/`error` severity and confirm every one is recorded `advisory` and does not block approval; then explicitly promote one to `blocking` and confirm the Feature 011 blocking-approval invariant now gates on it until it is verified.

**Acceptance Scenarios**:

1. **Given** an imported finding whose producer declared a blocking-equivalent severity, **When** it is recorded, **Then** its SpecOps severity is `advisory` and it does not block approval.
2. **Given** an imported `advisory` finding, **When** a human runs the explicit promotion (triage) step, **Then** the finding becomes `blocking`, the promotion is recorded auditably as handoff state, and the finding then gates approval until it is verified per Feature 011.
3. **Given** no promotion has occurred, **When** the review cycle is evaluated for approval, **Then** the imported advisory findings are reported but do not block, exactly like any other advisory finding.

---

### User Story 4 - A stale imported finding is flagged, never silently trusted (Priority: P2)

Each imported finding records the commit / effective-diff digest it was reviewed against. When the current effective diff no longer matches that reviewed range — the code moved on after the external tool ran — the finding is reported as **stale**. A stale finding is surfaced as such in the report; it is never silently treated as if it still described the current diff, and (if promoted) its staleness is visible to the human deciding whether it still applies.

**Why this priority**: Staleness is what keeps an asynchronous external review honest — external tools run out-of-band and the code moves. It reuses the Feature 009/010 digest-drift pattern, so it is a bounded addition (P2) that hardens the core rather than expanding it.

**Independent Test**: Import a finding against a recorded digest, then advance the effective diff so the digest no longer matches, and confirm `handoff report` flags that finding `stale` while a finding whose digest still matches is not flagged.

**Acceptance Scenarios**:

1. **Given** an imported finding whose recorded reviewed-diff digest matches the current effective diff, **When** the handoff is reported, **Then** the finding is not flagged stale.
2. **Given** an imported finding whose recorded reviewed-diff digest no longer matches the current effective diff, **When** the handoff is reported, **Then** the finding is flagged `stale` with its recorded vs. current digest visible.
3. **Given** a stale imported finding, **When** approval is evaluated, **Then** the finding's staleness is reported and (only if a human promoted it to blocking) it still participates in the gate, never silently trusted as current.

---

### Edge Cases

- **No open review cycle**: importing findings requires a handoff bound to a review cycle round (Feature 011 FR-002); an import attempted with no open review cycle MUST fail closed as a usage error, creating no state.
- **Empty findings document**: a schema-valid document containing zero findings is a supported no-op success (exit `0`), not an error — it creates no findings and mutates no state.
- **Duplicate finding within one import**: two results with equal content identity — (producer, rule, location, action) — in a single input document collapse to one finding deterministically, never two.
- **Re-import after the diff moved**: because content identity is digest-independent, re-importing the same document is idempotent — a matching finding is updated in place, and its per-location staleness is re-evaluated, so a previously-fresh finding may now report `stale` without a second record being created.
- **Producer omitted or unversioned**: the input contract requires a producer identity; a missing producer is a usage error. A producer that supplies a name but no version records the name with an explicit "unspecified version" marker rather than failing.
- **Promoted finding then re-imported**: a re-import MUST NOT silently demote a human-promoted finding back to `advisory`; the human triage decision is authoritative handoff state and survives re-import (idempotent import does not overwrite promotion). Deliberately reversing an escalation, or dismissing an imported finding as a false positive, is done through Feature 011's existing dismissal/withdrawal path (FR-006), not a new mechanism here.
- **SARIF result with no location / multiple locations**: a SARIF result carrying several locations maps deterministically by the defined primary-location rule so ingestion stays reproducible; a result with **no usable location at all** is a per-result defect that aborts the whole import (all-or-nothing, FR-013), named rather than silently dropped.
- **Legacy handoff without ingestion state**: a pre-feature ledger with no imported findings reads without error; the new provenance/staleness fields are additive and their absence is never a defect (roadmap Rule 5).
- **Severity outside the mapping**: a producer/SARIF severity level outside the recognized set maps to `advisory` (the safe default) and is reported, never rejected — no external input is trusted to raise severity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SpecOps MUST provide a **versioned, stack-neutral findings input contract** — a documented JSON schema carrying an explicit schema-version field — and a command (`specops handoff finding import-json`) that consumes a conforming document and creates structured findings (Feature 011) in the current feature's corrective handoff. The contract MUST NOT couple SpecOps to any specific producer, language, or tool.
- **FR-002**: Ingestion MUST create each finding through the **existing Feature 011 handoff surface** (structured ledger state, written atomically and interruption-safely under Feature 006 concurrency control), reusing the existing finding record shape (stable ID, rule, location, concise action, severity, lifecycle state). The feature MUST NOT introduce a parallel finding store or a second finding lifecycle.
- **FR-003**: Each imported finding MUST record its **producer/source** — the emitting tool's name and version (or a human/producer identifier) — as auditable handoff state, so every finding is attributable to what produced it. A missing producer identity is a usage error; a producer name without a version is recorded with an explicit unspecified-version marker.
- **FR-004**: Each imported finding MUST record a **per-path content digest** of the finding's **own location** (the path it points at), captured at import — the content of that path at the commit the producer names, or at the current effective diff when the producer supplies none — together with that commit reference. The digest is scoped to the finding's own path (not one feature-wide digest), so staleness (FR-010) is evaluated per finding. This reuses the Feature 009/010 **digest-drift pattern** (a digest stored at record time and re-compared later); it is a distinct per-path representation and MUST NOT be conflated with the feature-wide 009/010 map/effective-diff digests.
- **FR-005**: Every imported finding MUST be recorded as **`advisory` by default**, irrespective of any severity the producer declared. No external producer may cause a finding to be recorded `blocking` at import time.
- **FR-006**: Promotion of an imported finding from `advisory` to `blocking` MUST be an **explicit, audited triage step** (a distinct command action), recorded as handoff state (capturing that a promotion occurred and its provenance). Only after promotion does the finding participate in the Feature 011 blocking-approval invariant. SpecOps MUST NOT auto-promote based on producer confidence or declared severity. Withdrawing an escalation (demoting a promoted finding) or dismissing an imported finding judged a false positive MUST **reuse Feature 011's existing dismissal/withdrawal path**; this feature adds no separate lifecycle or withdrawal mechanism for imported findings (consistent with FR-017).
- **FR-007**: The promotion decision MUST be **authoritative and durable**: a re-import of the same findings MUST NOT demote a human-promoted finding back to `advisory`, nor otherwise overwrite the human triage decision.
- **FR-008**: Ingestion MUST be **deterministic**: identical input (same document, same repository state) MUST produce byte-for-byte identical handoff state — deterministic finding identity, ID assignment, ordering, and serialization — consistent with Feature 011 FR-018 and Features 008–010. A finding's **content identity** is the tuple **(producer, rule, location, concise action)** and MUST NOT include the reviewed-diff digest (FR-004) or any promotion/staleness state; this identity is what makes re-import idempotent across diff movement (FR-009).
- **FR-009**: Re-importing the **same** findings MUST be **idempotent**: two incoming findings match an existing finding when their content identity (FR-008) is equal, and a matching re-import MUST NOT create a duplicate. A re-import MUST leave handoff state unchanged **except** for a re-evaluated staleness comparison (FR-010), and it MUST never overwrite a promotion (FR-007). Because identity is digest-independent, re-importing after the effective diff has moved updates the matched finding's staleness **in place** rather than creating a second record. Duplicate results within a single input document (equal content identity) MUST collapse to one finding deterministically.
- **FR-010**: SpecOps MUST detect and report **staleness per finding**: when the current content digest of an imported finding's **own path** no longer matches that finding's recorded per-path digest (FR-004), the finding MUST be reported as `stale`, surfacing the recorded vs. current digest. Staleness is evaluated per finding at **path granularity**: a change to another path in the feature's effective diff MUST NOT stale a finding whose own path is unchanged (a change *within* the finding's own path does stale it — SpecOps does not track sub-file/hunk precision). A path that no longer exists is stale. A stale finding MUST NEVER be silently trusted as describing the current diff; a stale promoted-blocking finding still participates in the gate but its staleness is reported. SpecOps adds no new drift gate (it reuses the 009/010 drift *pattern*, per FR-004).
- **FR-011**: SpecOps MUST provide an **optional SARIF input adapter** (complementing the Feature 012 SARIF *output* adapter) that ingests a schema-valid **SARIF 2.1.0** document, mapping each result into a structured finding — preserving rule, location, and severity mapping — and recording the SARIF `tool.driver` name and version as the producer. The SARIF path MUST be opt-in and its absence MUST never be reported as a defect; SARIF-imported findings are `advisory` by default like all imports (FR-005).
- **FR-012**: The SARIF severity mapping MUST be deterministic and MUST NOT let external input raise SpecOps severity: every SARIF result is imported `advisory` (FR-005), and any level outside the recognized set maps to the safe `advisory` default and is reported, never rejected. A SARIF result's location MUST map by a defined primary-location rule; a result with no usable location is a **per-result defect** that MUST be named and, per the all-or-nothing rule (FR-013), MUST abort the whole import — never silently dropped and never a partial import.
- **FR-013**: Import MUST be **all-or-nothing** and **fail closed** as a usage error (exit `2`) on any defect — whether structural (unknown/unsupported schema version, missing required field, invalid SARIF, missing producer) or an **individually-defective finding** within an otherwise-valid document (e.g., a finding with no usable location, FR-012). The error MUST name **every** defective finding, and the import MUST record **no partial handoff state**: a document either imports in full or not at all. A schema-valid document with zero findings is a supported no-op success (exit `0`).
- **FR-014**: Importing MUST require an **open review cycle round** to bind the handoff to (Feature 011 FR-002); an import with no open review cycle MUST fail closed as a usage error creating no state. SpecOps MUST fail closed on ambiguous repository/feature identity (Global Definition of Done), never importing against an unresolved feature.
- **FR-015**: Ingestion, promotion, and staleness state MUST be a **versioned, additive** extension of the Feature 006 / Feature 011 ledger: adding the producer, reviewed-digest, and promotion fields MUST increment the ledger schema version and be covered by a forward-migration test that upgrades a pre-feature ledger (findings lacking these fields) without data loss; reads of prior ledger shapes MUST NOT fail or be reported as defects.
- **FR-016**: All ingestion **read** paths (report rendering of imported findings, staleness reporting) MUST be read-only and MUST NOT mutate repository or ledger state, verifiable by before/after comparison. Only import, promotion, and the normal Feature 011 transitions change state.
- **FR-017**: The imported findings MUST flow through the **existing Feature 011 reporting and enforcement** unchanged: `handoff report` (human + JSON) renders imported findings with their producer, reviewed-digest, and staleness; the blocking-approval invariant gates only on promoted-and-unverified blocking findings; the finding lifecycle (`OPEN → FIXED → VERIFIED`) is unchanged. This feature MUST NOT redefine the finding lifecycle, the approval gate, or verification.
- **FR-018**: Every ingestion command MUST expose SpecOps's **fixed exit-code taxonomy** — `0` success (including the supported empty-document and legacy states), `1` blocking/fail-closed, `2` usage/input error — with the fine-grained outcome carried in a stable `status` field, and every JSON output MUST embed an explicit schema-version/`output_version` field (consistent with Feature 011 FR-012/FR-017).
- **FR-019**: SpecOps MUST NOT **run, bundle, or require** any specific reviewer, and MUST NOT **judge, re-verify, or calibrate** the correctness or confidence of imported findings — that judgment stays with the producer and the human (Principle IV). SpecOps records the finding as a snapshot and gates deterministically on the human-owned triage and verification (Principle II/VI).
- **FR-020**: The English and Portuguese documentation for the input contract, the SARIF adapter, the import/promotion commands, provenance, and staleness MUST remain **behaviorally equivalent** (Global Definition of Done), and the changelog MUST record the new ingestion surface and any migration requirement.

### Key Entities *(include if feature involves data)*

- **Findings Input Contract**: The versioned, documented, stack-neutral JSON schema that external producers emit and `handoff finding import-json` consumes; carries an explicit schema-version and, per finding, the rule, location, concise action, declared severity, and producer, from which SpecOps creates Feature 011 findings.
- **Producer / Source**: The recorded identity (tool name + version, or human/producer identifier) of what emitted an imported finding; auditable provenance attached to each finding so every finding is attributable.
- **Reviewed-Diff Digest**: The per-path content digest (plus commit reference) an imported finding was reviewed against; the basis for path-granular staleness comparison against the current state. A distinct per-path representation that reuses the Feature 009/010 digest-drift *pattern*, not the feature-wide 009/010 digests.
- **Imported Finding**: A Feature 011 structured finding created by ingestion — same ID/severity/lifecycle shape — additionally carrying producer, reviewed-diff digest, and (once triaged) a promotion record; `advisory` at import. Its **content identity** for dedup/idempotency is the digest-independent tuple (producer, rule, location, concise action).
- **Promotion (Triage) Record**: The auditable handoff state recording that a human escalated an imported `advisory` finding to `blocking`; authoritative and durable across re-imports, and the sole path by which an external finding gates approval.
- **Staleness Flag**: The reported condition that an imported finding's recorded reviewed-diff digest no longer matches the current effective diff — surfaced in the report, never a silent trust of an out-of-date finding.
- **SARIF Input Adapter**: The optional, opt-in mapping from SARIF 2.1.0 results into imported findings (rule, primary location, severity mapping, `tool.driver` producer); the ingestion complement of the Feature 012 SARIF output adapter.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A schema-valid JSON findings document from an external producer imports into the corrective handoff so that 100% of its findings appear in `handoff report` with their producer and reviewed-diff-digest provenance and a stable ID — with no built-in review having run.
- **SC-002**: Every imported finding is recorded `advisory` regardless of the producer's declared severity: across all import fixtures, zero findings are recorded `blocking` at import time, and zero imported findings block approval before an explicit human promotion.
- **SC-003**: A human promotion of an imported finding to `blocking` causes the Feature 011 blocking-approval invariant to gate on it until it is verified: 100% of promoted-and-unverified fixtures block approval, and 100% resume to approvable once verified.
- **SC-004**: Ingestion is deterministic and idempotent: re-importing an identical document produces byte-for-byte identical handoff state (zero duplicate findings) across all fixtures, and a human-promoted finding is never demoted by a re-import.
- **SC-005**: Findings from at least **two distinct producers** — a JSON-contract sample and a SARIF 2.1.0 sample — both import into the handoff as `advisory` findings carrying their producer and diff-digest provenance (the roadmap acceptance gate), demonstrated on fixtures for each producer.
- **SC-006**: A finding whose reviewed-diff digest no longer matches the current effective diff is flagged `stale` in 100% of drift fixtures, and a finding whose digest still matches is never flagged — no stale finding is silently trusted as current.
- **SC-007**: Malformed input fails closed as a usage error naming the defect and leaves handoff state unchanged in 100% of negative fixtures — covering both structural defects (unknown schema version, missing required field, invalid SARIF, missing producer) and an otherwise-valid document containing an individually-defective finding, where all-or-nothing import records zero findings and names every defect; an empty valid document is a no-op success that mutates nothing.
- **SC-008**: The SARIF input adapter is strictly opt-in — absent by default, its absence never a defect — and round-trips each SARIF result's rule, primary location, and severity mapping into an imported finding across the SARIF fixtures.
- **SC-009**: A pre-feature ledger (findings lacking producer/digest/promotion fields) upgrades without data loss and reads without error in the forward-migration test; the existing Feature 011 report, lifecycle, and approval gate pass unchanged (zero regressions) for both imported and built-in findings.
- **SC-010**: EN and PT documentation for the ingestion surface are behaviorally equivalent (no divergence in described contract, commands, exit codes, or semantics), verified by review, and the changelog records the surface and migration.

## Assumptions

- The corrective handoff, finding record, lifecycle (`OPEN → FIXED → VERIFIED`), blocking-approval invariant, `handoff report`, and `handoff validate` are delivered by Feature 011 and are consumed here unchanged; this feature adds ingestion, provenance, promotion, and staleness on top and does not redefine the lifecycle or the gate.
- Staleness reuses the Feature 009/010 digest-drift **pattern** (a digest stored at record time, re-compared later) rather than introducing a new drift gate; the per-path content digest itself is a distinct representation from the feature-wide 009/010 map/effective-diff digests. The concrete per-path digest mechanism (e.g., git blob hash) is a plan-level choice.
- The SARIF **output** adapter (Feature 012) fixes the SARIF version (2.1.0) and the severity mapping (`blocking → error`, `advisory → warning`); the input adapter is its inverse and reuses that mapping, with all imports landing `advisory` regardless.
- Ingestion is **engine plumbing invoked by the review directive / workflow** (a step of `/specops-review`), not a daily hand-typed human command; a human MAY run it directly, and the exact workflow step placement is plan-level wiring, not a spec decision.
- The precise input-contract field names, the promotion command's spelling, the SARIF primary-location rule, and the ledger field layout are plan-level decisions; the spec fixes the behavior (versioned, stack-neutral, advisory-by-default, provenance-carrying, staleness-detecting, deterministic, idempotent), not the wire format.
- This feature ingests findings from **external** producers only; composing the **built-in** review into the workflow is Feature 016 (already merged), and this feature does not change it.
- The gate is referred to by its current name where relevant; the Feature 017 rename (`review → preflight`) is orthogonal and this feature does not depend on it.
