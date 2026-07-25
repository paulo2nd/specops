# Quickstart: External Review Ingestion

Validation scenarios that prove the feature end-to-end against fixtures. These are
delivered-capability checks run in the feature's own tests — **not** run against
this repository (roadmap "No Self-Application"). Detailed field/exit semantics live
in [contracts/ingestion-cli.md](./contracts/ingestion-cli.md) and
[data-model.md](./data-model.md).

## Prerequisites

- A fixture repo with an active feature and an **open review cycle** (a
  `review_cycles[]` round in `status.yaml`) — reuse the Feature 011 handoff
  fixtures in `tests/fixtures/` / `tests/conftest.py`.
- `specops` CLI available (`conda run -n specops specops …` per repo tooling).

## Scenario 1 — Ingest via the JSON contract (P1, SC-001)

```bash
# sample.json conforms to contracts/findings-input.schema.json (contract_version 1)
specops handoff finding import-json --file sample.json
specops handoff report --json
```

Expected: `findings_imported` (exit 0); `handoff report --json` lists each finding
as `advisory`, `state: OPEN`, with `producer` and `reviewed_digest` populated and a
stable `R<round>-F<NN>` id. No built-in review ran.

## Scenario 2 — Advisory-by-default + audited promotion (P1, SC-002/SC-003)

```bash
# A finding whose producer declared "error"/"critical" still lands advisory:
specops handoff report --json          # severity == "advisory" for every imported finding
# Human triage escalates one to blocking (must supply closure + expected evidence):
specops handoff finding promote R1-F01 --closure "guard added + test" --expected-evidence "TEST:covers null path"
# Approval is now blocked until it is verified:
specops status transition-phase DONE -r APPROVED   # exit 1, approval-blocked (names R1-F01)
```

Expected: zero imported findings are `blocking` before promotion; after promotion
the blocking-approval invariant gates `DONE`; verifying (Feature 011 `fix`+`verify`)
or `dismiss` unblocks it.

## Scenario 3 — SARIF adapter, two distinct producers (P2, SC-005/SC-008 — roadmap gate)

```bash
specops handoff finding import-sarif --file codeql.sarif   # tool.driver → producer
specops handoff report --json
```

Expected: each SARIF result becomes an `advisory` finding preserving rule / primary
location / (informational) severity, with `producer.name/version` from
`tool.driver`. Combined with Scenario 1, **two distinct producers** (JSON + SARIF)
coexist in the same handoff, each attributed — the roadmap acceptance gate. SARIF
is opt-in; its absence is never a defect.

## Scenario 4 — All-or-nothing on a defective document (SC-007)

```bash
specops handoff finding import-sarif --file has-one-locationless-result.sarif; echo "exit=$?"
specops handoff report --json   # unchanged — zero findings written
```

Expected: exit `2`, the error names the defective result(s), and the ledger is
byte-identical to before (no partial import). An empty-but-valid document instead
exits `0` as a no-op.

## Scenario 5 — Determinism, idempotency, staleness (SC-004/SC-006)

```bash
specops handoff finding import-json --file sample.json    # first import
L1=$(specops handoff report --json)
specops handoff finding import-json --file sample.json    # re-import (same doc)
L2=$(specops handoff report --json)
# ... make a commit that changes a file one finding points at ...
specops handoff report --json    # that finding now shows stale:true; others stale:false
```

Expected: `L1 == L2` (no duplicate findings; byte-identical) except read-time
`stale`/`current_digest`; a promoted finding is **not** demoted by re-import; after
the commit, only the finding whose own `file` changed reports `stale: true`.

## Scenario 6 — Backward compatibility / degrade (SC-009)

```bash
# A v6 ledger (findings without producer/digest/promotion) upgrades cleanly:
specops handoff report --json     # reads without error; existing findings unaffected
specops handoff validate          # exit 0 — new optional fields never flagged
```

Expected: v6 → v7 forward migration loses no data; a repository that never imports
external findings behaves exactly as before (Feature 011 report/lifecycle/approval
unchanged).

## Cross-checks

- **Read-only**: `handoff report`/`validate` leave `status.yaml` byte-identical
  (before/after comparison) (FR-016).
- **Exit codes**: `0` success/no-op, `1` blocking (approval blocked / validate
  defect), `2` usage (malformed input / unknown finding) (FR-018).
- **EN/PT docs**: README + README.pt-br + CHANGELOG describe the same contract,
  commands, and exit codes (FR-020).
