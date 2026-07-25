# CLI Contract: External Review Ingestion (Feature 015)

Extends the Feature 011 `handoff finding` group. All commands reuse `HandoffResult`
(status → class → exit) and the fixed `0/1/2` taxonomy. Every `--json` output
carries `output_version` (= `handoff.OUTPUT_VERSION`). All state-changing commands
route through the atomic + revision-CAS write (`status._finalize`); reads never
mutate (before/after ledger byte-comparison).

## State-changing commands

| Command | Args | Success status (exit 0) | Gate-reject (exit 1) | Usage error (exit 2) |
|---|---|---|---|---|
| `handoff finding import-json` | `--file <path>` (the input document; `-` = stdin) | `findings_imported` (returns count + new ids) | — | `bad_args` (unsupported `contract_version`, missing required field/producer, no open review cycle, unreadable file); all-or-nothing — names **every** defect |
| `handoff finding import-sarif` | `--file <path>` (`-` = stdin) | `findings_imported` | — | `bad_args` (invalid SARIF 2.1.0, a result with no usable location, missing producer/`tool.driver`, no open review cycle) |
| `handoff finding promote` | `<ID>` `--expected-evidence <t>` `--closure <t>` | `finding_promoted` | — | `unknown_finding`; `bad_args` (finding not `advisory`/not imported, missing `--expected-evidence`/`--closure`) |

Notes:
- **Advisory-by-default**: `import-*` always records `advisory`; a producer-declared
  severity is stored for audit but never sets `blocking` (FR-005).
- **All-or-nothing**: a document with any defect (structural *or* a per-result
  no-location) imports **nothing** and names all defects (FR-013). An empty-but-valid
  document is `findings_imported` with count 0 (no-op success, no write).
- **Idempotency**: a matching re-import (equal content identity) creates no
  duplicate; it refreshes `reviewed_digest` only and never overwrites a `promotion`
  (FR-007/FR-009). Re-import output reports `imported: 0, refreshed: N`.
- **Promotion** sets `severity=blocking` + `promotion` + `expected_evidence` +
  `closure_criteria`, so the promoted finding is verifiable and `handoff validate`
  never flags `MISSING_CLOSURE`. Withdrawal/demotion uses the existing
  `handoff finding dismiss <ID> --reason <t>` (no new command).

## Read commands (exit 0; 1 only for a validation defect)

| Command | Args | Behavior |
|---|---|---|
| `handoff report` | `[--json] [--sarif]` | Now renders `producer`, `reviewed_digest`, and a computed `stale` flag (recorded-vs-current digest) per imported finding, in addition to the Feature 011 fields. `remaining_blocking` includes promoted-and-unverified imported findings. Read-only. |
| `handoff validate` | `[--json]` | Unchanged defect classes; updated only to accept the new optional finding fields (never flags their presence/absence). |

## Status → class → exit (additions)

| Status | Class | Exit |
|---|---|---|
| `findings_imported` | PASS | 0 |
| `finding_promoted` | PASS | 0 |
| `bad_args` | INFRA_ERROR (usage) | 2 |
| `unknown_finding` | INFRA_ERROR (usage) | 2 |

Existing Feature 011 statuses (`approval_blocked`, `close_blocked`, `report_ok`,
`validate_ok`, the defect statuses, …) are unchanged and continue to gate.

## Determinism

Identical input document + identical repository state ⇒ byte-identical ledger
state and byte-identical `--json` output (findings sorted by content identity
before id assignment; canonical report order per `handoff._canonical`).
