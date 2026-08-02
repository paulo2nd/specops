# Quickstart — Validating Review Round Integrity

These are **fixture-driven** validation scenarios. Per the Constitution
(No Self-Application), SpecOps is never run against this repository — every
scenario runs against a throwaway fixture repo built by the `tests/` harness.
Run with `conda run -n specops pytest` (the project mypy/ruff/pytest env).

Prerequisites: a fixture git repo with a SpecOps ledger at `status.yaml`, a
recorded `baseline`, and the CLI installed editable (`pip install -e .`).

## Scenario 1 — Anchor round records the full hunt (US1)

1. Build a fixture: baseline `B`, then commit feature work across ~5 files to
   `HEAD₁`. Enter REVIEW so cycle 1 is open.
2. Run `specops handoff record-scope --json`.
3. **Expect**: `review_role = "anchor"`, `reviewed_range = "B..HEAD₁"`,
   `scope_paths` = the full `name_only_diff(B, HEAD₁)` (all 5 files). Cycle 1 in
   the ledger now carries `reviewed_range`/`review_role`.

## Scenario 2 — Approval blocked without full coverage (US1 / SC-002)

1. From a clean fixture, open cycle 1 but record scope over only a **partial**
   delta (simulate a corrective-first round: record scope, then add a later
   commit `HEAD₂` touching a new file that no scoped range covers).
2. Add and verify all blocking findings (so the Feature 011 gate would pass).
3. Run `specops status transition-phase DONE -r APPROVED`.
4. **Expect**: exit 1, message naming the uncovered path(s); phase stays REVIEW;
   `status.yaml` unchanged (no DONE).

## Scenario 3 — Reject-at-gates, then anchor, then corrective → approve (US1)

1. Round 1: make `preflight` fail (e.g. a lint error) → `transition-phase
   IMPLEMENT -r REJECTED`. Cycle 1 has **no** `reviewed_range` (Step 3 never ran).
2. Round 2 (gates now pass): `record-scope` → `anchor`, `B..HEAD₂`. Add a
   blocking finding → REJECTED. Cycle 2 carries the anchor range **despite** the
   REJECTED verdict.
3. Round 3: implementer fixes (→ `HEAD₃`), marks the finding FIXED; reviewer
   `record-scope` → `corrective`, `HEAD₂..HEAD₃`; verifies the finding;
   `handoff close`.
4. `transition-phase DONE -r APPROVED`.
5. **Expect**: approval succeeds — `union(B..HEAD₂, HEAD₂..HEAD₃)` covers
   `B..HEAD₃`. The gate-rejected round 1 contributed no scope and did not block.

## Scenario 4 — Corrective round is scoped, not a re-hunt (US2 / SC-003)

1. Continue from an anchor round over files {a,b,c,d,e}. Fix touches only `c`
   (→ `HEAD₃`).
2. Round-3 `record-scope --json`.
3. **Expect**: `review_role = "corrective"`, `reviewed_range = "HEAD₂..HEAD₃"`,
   `scope_paths` = {`c`} (plus any prior non-terminal finding's file), and the
   untouched {a,b,d,e} are **absent** from `scope_paths`.

## Scenario 5 — Round cap halts and asks (US3 / SC-004)

1. Fixture `specops.json` sets `review_round_cap: 3` (or rely on the default and
   drive 10 rounds).
2. Drive REVIEW→IMPLEMENT `-r REJECTED` until round 3 is open and round 4 would open.
3. **Expect**: exit 1, a human-directed halt message; `status.yaml` records
   `review_halt {at_round: 3, cap: 3, recorded_at: …}`; round 3 is **left open**
   (`result: null` — no verdict fabricated); **no** round 4 cycle was appended.
   Because the round stays open, the human can resolve findings and approve
   directly (Scenario 8), raise the cap, or rebaseline.

## Scenario 6 — Legacy ledger degrades (US1 / SC-005)

1. Build a v7 fixture ledger with a completed review cycle carrying **no**
   `reviewed_range` (pre-feature shape). Migrate it (`status` write path bumps to
   v8) — the cycle still has no scope record.
2. With all blocking findings verified and the cycle result APPROVED, run
   `transition-phase DONE -r APPROVED`.
3. **Expect**: approval succeeds via the prior cycle-result path; the coverage
   guard is a no-op because `has_scope_records == False`. No retroactive block.

## Scenario 7 — Unresolvable baseline fails closed (Edge Case / Principle VI)

1. Fixture where scope records exist but the baseline commit is unreachable
   (simulated shallow clone / rewritten history: `commit_exists(baseline)` false).
2. Run `transition-phase DONE -r APPROVED`.
3. **Expect**: exit 1 with the shallow-clone/rewritten-history explanation — never
   a silent approval.

## Scenario 8 — Resume after a round-cap halt (Edge Case / research R8)

1. Continue from Scenario 5's halted fixture (`review_halt` recorded at the cap;
   round 3 REJECTED; no round 4).
2. Raise `review_round_cap` in the fixture `specops.json` (e.g. 3 → 5) and re-run
   `transition-phase IMPLEMENT -r REJECTED`.
3. **Expect**: round 4 opens normally (no halt); the historical `review_halt`
   record is retained (not auto-cleared). Separately, with coverage complete and
   blocking findings verified, `transition-phase DONE -r APPROVED` succeeds despite
   the retained marker.

## Coverage → Success Criteria map

| Scenario | Requirements / SC |
|----------|-------------------|
| 1 | FR-001, FR-002 (anchor), SC-006 |
| 2 | FR-003, SC-001, SC-002 |
| 3 | FR-001..FR-003 (union across rounds), the motivating defect |
| 4 | FR-005, SC-003 |
| 5 | FR-006, FR-007, SC-004 |
| 6 | FR-008, FR-009, SC-005 |
| 7 | FR-003 fail-closed, Principle VI |
| 8 | FR-006 resume (research R8), no fabricated verdict |
