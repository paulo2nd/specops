# Contract: Ledger v4 → v5 (Findings & Handoffs)

## Placement

Each corrective handoff is nested on its review-cycle record:

```yaml
review_cycles:
  - round: 2
    started_at: "2026-07-22T14:03:00+00:00"
    result: null
    context_provenance: { ... }        # Feature 009 — unchanged
    handoff:                            # NEW (v5) — present once ≥1 finding recorded
      authorized_paths: ["src/specops/handoff.py"]
      closed_at: null
      findings:
        - id: "R2-F01"
          severity: "blocking"
          rule: "L2 single-active-task"
          file: "src/specops/status.py"
          line: 42
          action: "enforce single-active-task guard"
          expected_evidence: "unit test covering the guard"
          closure_criteria: "test_status_single_active passes"
          state: "OPEN"
          task: null
          commits: []
          evidence: null
          fixed_at: null
          verified_at: null
```

A round with zero findings has **no** `handoff` key (R4). Pre-v5 cycles have no `handoff` key and
read unchanged.

## Migration (`ledger.migrate_to_current`)

- `CURRENT_SCHEMA` 4 → **5**.
- **Additive, no backfill**: pre-v5 ledgers gain nothing on findings — absence of `handoff` = zero
  structured findings. Migration preserves every existing task/cycle/evidence/acknowledgement/
  provenance field verbatim (idempotent when already v5).
- Read-compat: v1–v4 ledgers load without error; absent finding/handoff state is a supported prior
  shape, never a defect (FR-019, CHK031/CHK032).

## Invariants (`ledger.validate_invariants`, fail closed on a state-changing write)

- Every finding `severity ∈ {blocking, advisory}` and `state ∈ {OPEN, FIXED, VERIFIED}`.
- Finding `id` unique within the feature.
- No `blocking` finding lacks `closure_criteria`/`expected_evidence` (also an FR-010 defect).
- `FIXED`/`VERIFIED` findings carry the correction links their state requires.
- Exempt: absent handoffs and orphaned records (mirrors the acknowledgement-shape check).

## Concurrency, atomicity, idempotency

- All writes go through `status._load_for_write` → `status._finalize` → `ledger.save`
  (short-lived lock + revision compare-and-swap + atomic tmp→fsync→`os.replace`). A concurrent or
  stale write fails closed with no lost update (FR-002); an interrupted write leaves the prior
  valid ledger readable (CHK025).
- `finding add` id assignment is deterministic (`R<round>-F<NN>`, append order); a colliding id at
  creation is `duplicate-id-create` (exit 2).
- `handoff close` re-close is an idempotent no-op (`handoff-already-closed`, exit 0).

## Forward-migration test obligation (SC-007)

Upgrade a v4 fixture (acknowledgements + provenance + review_cycles) to v5 with zero data loss;
assert absent-field reads never fail and never surface as defects.
