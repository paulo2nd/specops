# Data Model: Deterministic Review Gates in the CLI

**Feature**: `specs/004-review-gates-cli` | **Date**: 2026-07-06

No persisted data is introduced. All entities are in-memory for the duration
of one `specops review` run; the ledger and config are read-only inputs.

## GateResult

One evaluated gate.

| Field | Type | Rules |
|---|---|---|
| `name` | str | One of `reconcile`, `lint`, `test`, `working-tree` (canonical order index 0–3) |
| `status` | enum | `PASS` \| `FAIL` \| `SKIPPED` |
| `detail` | list[str] | Evidence lines. PASS: reconcile warnings (may be empty). FAIL: violations / `command`, `exit code`, last-50-lines block with truncation note / dirty-file list / no-diff message. SKIPPED: reason (`lint_command empty`, `test_command empty`) |

**Lifecycle**: created only when its gate is evaluated; gates after a FAIL
are never instantiated (early stop). `SKIPPED` applies only to `lint`/`test`
with an empty configured command.

## GateReport

The ordered outcome of one run.

| Field | Type | Rules |
|---|---|---|
| `results` | list[GateResult] | Fixed order reconcile → lint → test → working-tree; length 1–4 (short on early stop) |
| `passed` | bool | True iff no result has `status == FAIL` |

**Rendering**: one `[gate] <name> ... <status>` line per result followed by
its detail lines. `passed=True` → rendered report returned (stdout, exit 0).
`passed=False` → rendered report becomes the `SpecopsError` message (stderr,
exit 1).

## Read-only inputs (existing entities, unchanged)

| Entity | Source | Fields consumed |
|---|---|---|
| Client config | `specops.json` | `lint_command`, `test_command` |
| Ledger | `status.yaml` | `baseline` (for the effective diff); parse errors keep `LedgerParseError` → exit 2 |
| Worktree | Git | porcelain status; `name_only_diff(baseline, HEAD)` |

**Invariant (FR-007)**: no write path exists from `review.py` to the ledger,
`specops.json`, or any repository file.

## Review prompt template (installed artifact)

`src/specops/templates/review.md` — structural change only: the three gate
steps collapse into one CLI delegation step; sections for skills loading,
surgical diff review, revision report, verdict transition, and active
learning keep their semantics (see
[contracts/review-template.md](./contracts/review-template.md)).
