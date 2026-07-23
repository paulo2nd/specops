# Quickstart — Structured Corrective Handoff (validation guide)

Proves every Success Criterion against **fixtures** (never by running `specops` on this repo —
No Self-Application). Run under the tooling env: `conda run -n specops …`.

## Prerequisites

- Editable install: `pip install -e ".[dev]"`.
- A fixture feature dir with a Ledger v5 (`status.yaml`) at `REVIEW` with an open review cycle and
  a completed task, seeded via `conftest.py` builders (mirrors the Feature 010 fixture style).

## 1. Record a resumable handoff (US1 · SC-001/SC-002)

```bash
specops handoff finding add --severity blocking --rule "L2" \
  --file src/specops/status.py --line 42 --action "enforce single-active-task guard" \
  --expected-evidence "unit test covering the guard" --closure "test_status_single_active passes"
specops handoff authorize --path src/specops/status.py
specops handoff report --json      # → output_version:1, finding R2-F01 OPEN, remaining-blocking:[R2-F01]
```

Expect: stable id `R2-F01`; re-run `report` → byte-for-byte identical (SC-001). Reload the ledger
in a fresh process and confirm every field (severity, expected_evidence, closure, authorized paths)
round-trips (SC-002).

## 2. Drive the lifecycle & the approval gate (US2 · SC-003/SC-004)

```bash
specops handoff finding fix R2-F01 --task T007 --commit <sha> --evidence "TEST:guard added"
specops handoff finding verify R2-F01           # FIXED → VERIFIED (mechanical precondition ok)
specops handoff close                            # handoff-closed
specops status transition-phase DONE -r APPROVED # now permitted
```

Negative checks (each exit 2, state unchanged): `verify` from `OPEN`; a backward transition; `fix`
with no commit. Approval negative (exit 1, `approval-blocked`): attempt `DONE -r APPROVED` while
`R2-F01` is unverified → blocked, names `R2-F01`. Advisory-only open findings → approval permitted
(0% false-block, SC-003).

## 3. Validate & report (US3 · SC-005)

```bash
specops handoff validate            # exit 0 on a well-formed handoff
```

Against fixtures seeded with each defect, `validate` exits 1 with one diagnostic:
`dangling-reference`, `missing-closure`, `contradictory-state`, `duplicate-id`. Zero false
positives on the clean fixture.

## 4. Render, re-source & migrate (US4 · SC-006/SC-007/SC-009)

```bash
specops handoff report              # human projection = rendered revisions/revision-X.md lines
specops trace report                # findings now resolve to stable ids (R2-F01)
specops handoff import --round 1     # legacy prose → advisory/OPEN structured findings
```

Expect: rendered `revision-X.md` byte-for-byte deterministic and `<file>:<line> - <action>`
compatible (SC-006); a v4→v5 migration fixture upgrades with zero data loss and pre-feature ledgers
read without defects (SC-007); all existing Feature 010 fixtures still pass and structured ledgers
expose finding ids (SC-009).

## 5. Read-only & determinism (SC-008)

Before/after `status.yaml` byte-compare across `report`/`validate`/`trace report` → unchanged
(read-only). Identical inputs → byte-for-byte identical output; `--json` carries `output_version`,
`status`, `class`, and the `0/1/2` exit taxonomy.

## Coverage

`conda run -n specops pytest --cov=specops --cov-fail-under=85` plus `ruff check` and `mypy`.
See [contracts/](./contracts/) and [data-model.md](./data-model.md) for field- and exit-level
detail.
