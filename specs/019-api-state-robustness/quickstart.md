# Quickstart: Validating Hardening II — API & State Robustness

**Feature**: 019-api-state-robustness | **Date**: 2026-07-27

How to prove the feature's promises hold. All commands run from the repository root in
the `specops` conda environment (`conda run -n specops …`); nothing here runs `specops`
against this repository (No Self-Application — everything goes through `tests/`
fixtures or static analysis).

## Prerequisites

```bash
conda run -n specops pip install -e .
```

## 1. Zero behavior change (SC-001, SC-007)

The existing suite is the capture set — every CLI scenario asserts on exact output and
exit codes:

```bash
conda run -n specops python -m pytest              # full suite, ≥85% coverage floor
conda run -n specops ruff check src tests
```

Expected: everything green with **no test expectation edited** for output reasons
(tests may only change where they referenced renamed/deleted internals —
`lane._parse_name_status`, the doctor `state_error` parameters, the handoff tuple).
Ledger byte-stability is already asserted by the existing save/no-op tests; the
`test_records_typing.py` parity test (below) guards the typed shapes against drift.

## 2. The lock race (FR-001/FR-002, SC-002)

```bash
conda run -n specops python -m pytest tests/unit/test_ledger_lock.py -v
```

Expected: the single-winner race test passes across its amplification loop
(see [contracts/lock-protocol.md](./contracts/lock-protocol.md) §Regression test).
One-time falsification check during implementation: revert only the reclaim arm of
`_LedgerLock.__enter__` to `unlink+continue` and re-run — the token assertion must
fail; restore and re-run green.

## 3. Typed records (FR-005/FR-006, SC-005)

```bash
conda run -n specops mypy src
```

Expected: clean, with the pre-existing `git.*` override as the only suppression (no
new overrides, no new `# type: ignore`).

Seeded-typo probe (manual, not committed):

```bash
# In status.py's completion flow, temporarily change task["status"] to task["staus"]
conda run -n specops mypy src   # MUST fail with a TypedDict key error
git checkout -- src/specops/status.py
```

Shape parity (committed): `tests/unit/test_records_typing.py` asserts the TypedDict
key sets match the dicts `findings.new_finding` / `evidence.build_record` / the
`status.yaml` template actually produce — the serialization guard.

## 4. Single-implementation scans (SC-003, SC-004)

Each must return the stated count:

```bash
# One --name-status parse loop (gitops only; lane's copy deleted)
grep -rn "name-status\|name_status" src/specops/ | grep -v gitops.py | grep "split"   # → 0 hits

# No (human) sentinel in the generic git layer
grep -n "(human)" src/specops/gitops.py                                               # → 0 hits

# No class-probing at handoff loader call sites (baseline: 9)
grep -c "isinstance(loaded, HandoffResult)" src/specops/handoff.py                    # → 0

# One DONE cycle gate (the two verbatim blocks are gone)
grep -c "no review cycles recorded" src/specops/status.py                             # → 1

# No exceptions threaded as doctor domain arguments
grep -n "state_error" src/specops/doctor.py | grep "_domain_"                         # → 0 hits
```

## 5. Template drift fails loudly (FR-010, SC-006)

```bash
conda run -n specops python -m pytest tests/unit -k "render_template or template_drift" -v
```

Expected: the drift test (template with a novel `{{new-placeholder}}`) asserts a
`SpecopsError` naming the placeholder — never a written file containing `{{`.

## 6. Gate-profile table parity (FR-011)

```bash
conda run -n specops python -m pytest tests/unit -k gateprofile -v
```

Expected: existing lenient-parse and validate tests pass unchanged (same fallbacks,
same defect messages) — proving the table refactor moved knowledge without changing
it.

## 7. Full gate, in order (the acceptance gate)

```bash
conda run -n specops ruff check src tests \
  && conda run -n specops mypy src \
  && conda run -n specops python -m pytest
```

All green + the §4 scans at their stated counts = the feature's acceptance gate
(spec: suite green, byte-identical behavior, race covered, mypy typed, single
implementations).
