# Data Model: External Review Ingestion (Phase 1)

Imported findings are **Feature 011 findings** (same record, same `OPEN → FIXED →
VERIFIED`/`DISMISSED` lifecycle, same `R<round>-F<NN>` id) with additive fields.
No parallel store and no new lifecycle (FR-002/FR-017). Ledger schema **v6 → v7**.

## Ledger location

Unchanged nesting: `status.yaml → review_cycles[] → handoff → findings[]`
(`handoff._ensure_handoff`). Ingestion writes into the **current round's** handoff
(`handoff._current_cycle`); an import with no open review cycle fails closed
(FR-014), matching `cmd_finding_add`.

## Finding record — additive fields (v7)

Existing v6 finding fields are unchanged
(`id, severity, rule, file, line, action, expected_evidence, closure_criteria,
state, task, commits, evidence, evidence_id, fixed_at, verified_at`). Imported
findings add:

| Field | Type | Meaning | Rules |
|---|---|---|---|
| `imported` | object \| absent | Provenance marker; present ⇒ this finding was ingested (not authored by the built-in review). | `{ "contract_version": 1, "source_format": "json"｜"sarif" }`. Absent on non-imported findings. |
| `producer` | object | The emitting tool/human. | `{ "name": <str, required>, "version": <str> }`. Missing `name` ⇒ import defect (FR-003). Missing version ⇒ `version: "unspecified"`. |
| `reviewed_digest` | object | Per-location digest the finding was reviewed against (FR-004). | `{ "path": <norm path>, "commit": <sha｜null>, "blob": <git blob sha｜null> }`. `blob` null ⇒ path absent at reviewed commit (treated stale at report). Refreshed in place on a matching re-import (FR-009). |
| `promotion` | object \| absent | Audited advisory→blocking escalation (FR-006). | Present ⇒ `{ "at": <rfc3339 utc> }`. Absent ⇒ never promoted. Never removed by re-import (FR-007). |

**Severity of an imported finding**: always `advisory` at import (FR-005),
regardless of any producer-declared level. Becomes `blocking` **only** via
`cmd_finding_promote`, which simultaneously sets `expected_evidence` +
`closure_criteria` (Feature 011 requires them for a blocking finding).

## Content identity (idempotency key) — R1

`identity(f) = (producer.name, rule, file, line, action)` — digest-independent.
Used to (a) collapse within-document duplicates and (b) match a re-import to an
existing finding. Equal identity ⇒ update in place (refresh `reviewed_digest`
only); new identity ⇒ append with `handoff._next_id`.

## Computed (not stored) — R8

| View field | Source | Notes |
|---|---|---|
| `stale` | `reviewed_digest.blob != blob_sha(HEAD, file)` | Recomputed read-only at `handoff report`; never persisted (FR-016). `true` when the path changed or no longer exists at HEAD. |
| `current_digest` | `blob_sha(HEAD, file)` | Surfaced beside `reviewed_digest` so recorded-vs-current is visible (FR-010). |

## Entities

- **Findings Input Contract (v1)**: versioned JSON document; top-level
  `contract_version` + `findings[]`; each finding declares
  `rule, file, line?, action, severity?, producer`. See
  `contracts/findings-input.schema.json`.
- **Imported Finding**: the v7 finding record above.
- **Producer / Source**: `producer` object; recorded as-declared (never
  authenticated — Principle II/IV, FR-019).
- **Reviewed-Diff Digest**: `reviewed_digest` object; per-location baseline.
- **Promotion (Triage) Record**: `promotion` object; the sole path to `blocking`;
  durable across re-imports.
- **Staleness Flag**: computed `stale`; reported, never stored.

## State & transitions (unchanged from Feature 011)

```
import      → OPEN (advisory, imported)
promote     → OPEN (blocking, +promotion +closure +expected_evidence)   [FR-006]
fix         → FIXED     (task+commit+evidence)          [Feature 011]
verify      → VERIFIED  (mechanical precondition)       [Feature 011]
dismiss     → DISMISSED (audited reason; withdrawal)    [Feature 011, resolves CHK005]
re-import (matching identity) → no state change except reviewed_digest refresh [FR-009]
```

`blocking_approval_check` (feature-global) already treats `VERIFIED`/`DISMISSED`
as resolved, so a promoted imported finding gates `APPROVED`/`DONE` until verified
or dismissed — no change to the invariant, only new inputs to it.

## Validation (FR-013, all-or-nothing)

Import collects **all** defects before any write:

| Defect | Cause | Result |
|---|---|---|
| `unsupported-contract-version` | `contract_version` unknown/missing | exit 2, no write |
| `missing-field` | required `rule`/`file`/`action`/`producer.name` absent | exit 2, no write |
| `invalid-sarif` | not SARIF 2.1.0 / unparseable | exit 2, no write |
| `no-location` (SARIF) | result with no usable physical location | exit 2, no write (named, not dropped) |
| *(empty but valid)* | `findings: []` | exit 0, no-op |

Structural integrity of already-stored findings continues to be checked by
`ledger.finding_structural_defects` / `handoff validate`, updated only to accept
the new optional fields (never flag them).

## Migration v6 → v7 (FR-015)

Additive: `CURRENT_SCHEMA = 7`; `migrate_to_current` bumps the version (no
backfill — absence of the new fields means "not an imported finding"). Forward
test: a v6 ledger with pre-existing findings upgrades with zero data loss and its
cycle/handoff records stay semantically identical.
