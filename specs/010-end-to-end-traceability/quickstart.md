# Quickstart — End-to-End Traceability (validation guide)

This proves every Success Criterion against **fixtures**, never by running `specops` on this repository (No Self-Application). Commands are illustrative; the authoritative behavior lives in `tests/unit/test_trace.py` and `tests/integration/test_trace_cli.py`.

## Prerequisites

- `pip install -e .` (exposes the `specops` entrypoint).
- A fixture sample repo: a Git repo with `specs/<feat>/{spec.md,plan.md,tasks.md,status.yaml}`, optional `.specify/specops/context-map.yaml`, and optional `specs/<feat>/revisions/revision-1.md`.

## 1. Classify effective-diff paths  → SC-001, SC-002, SC-008

```bash
specops trace classify --json
```
Expect every changed path in exactly one class with an attribution; identical inputs → byte-identical output. In a no-map fixture, `planned` derives from plan paths only; in a map fixture, ownership contributes.

## 2. Block only unexplained drift  → SC-003

```bash
specops review          # runs reconcile→lint→test→working-tree→drift
```
Expect PASS when every path is `planned`/`discovered-and-acknowledged`; the `drift` gate FAILs (exit 1) listing only `unexplained` paths. A `planned` or acknowledged path never FAILs.

## 3. Acknowledge a discovery once  → SC-004

```bash
specops trace acknowledge src/discovered.py --task T007 --reason "config moved during T007"
specops trace classify              # src/discovered.py now discovered-and-acknowledged
specops trace acknowledge src/discovered.py --task T007 --reason "config moved during T007"  # idempotent, exit 0
specops trace acknowledge src/discovered.py --task T009 --reason "other"                       # ACK_CONFLICT, exit 2
specops trace acknowledge src/discovered.py --task T404 --reason "x"                           # ACK_UNKNOWN_TASK, exit 2
```

## 4. Report the full trace  → SC-006

```bash
specops trace report --json
```
Expect every completed SC to resolve to task→contexts/paths→commits→evidence→findings/corrections, and a Discoveries section listing acknowledged paths with reason+task.

## 5. Validate the trace  → SC-005, SC-006

```bash
specops trace validate
```
Complete fixture → exit 0. Seeded-defect fixtures each produce one distinct diagnostic at exit 1: `uncovered-sc`, `missing-link` (DONE task w/o evidence; user-story-final task w/o commit), `dangling-reference`, `contradictory-ownership`. No false positives on the complete fixture.

## 6. Migration & read-only  → SC-006, SC-007

```bash
# v3 → v4 migration backfills acknowledgements: [] with no data loss (test_ledger_migration.py)
# before/after state comparison confirms classify/report/validate never mutate ledger or repo
```

## Degenerate cases

- Clean tree / empty diff → empty classification, exit 0.
- Not a Git repo / no resolvable baseline → exit 2 with a clear message (never a silent empty result).
- Pre-v4 ledger → loads and traces; discovered paths are `unexplained` until acknowledged.
