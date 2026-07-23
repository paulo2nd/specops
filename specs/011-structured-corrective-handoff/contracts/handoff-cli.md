# Contract: `specops handoff` CLI

New Typer group `handoff_app` under `specops handoff` (mirrors `trace_app`). State-changing
commands route through `status._load_for_write` + `status._finalize` (identity gate + revision-CAS +
atomic write); read commands use `ledger.load_raw` and never mutate. Every `--json` output is
`outcome.render(...)` with a stable `status`, an outcome `class`, and `output_version = 1`.

Exit taxonomy (Principle VI): `0` success · `1` blocking/fail-closed · `2` usage/input error.

## State-changing commands

| Command | Args | Success status (exit 0) | Fail-closed | Usage error (exit 2) |
|---|---|---|---|---|
| `handoff finding add` | `--severity {blocking\|advisory}` `--rule <t>` `--file <p>` `[--line N]` `--action <t>` `--expected-evidence <t>` `--closure <t>` | `finding-recorded` (returns the new `R<round>-F<NN>` id) | — | `bad-args` (missing required / unknown severity / no open review cycle); `duplicate-id-create` |
| `handoff authorize` | `--path <p>` (repeatable) | `handoff-authorized` | — | `bad-args`, `not-a-repo` |
| `handoff finding fix` | `<ID>` `--task <t>` `--commit <sha>` (repeatable) `(--evidence <CLASS:summary> \| --auto)` | `finding-fixed` | — | `unknown-finding`, `unknown-task`, `illegal-transition`, `precondition-unmet` (no commit/evidence) |
| `handoff finding verify` | `<ID>` | `finding-verified` | — | `unknown-finding`, `illegal-transition` (from OPEN / backward), `precondition-unmet` (evidence absent / links unresolved) |
| `handoff close` | — | `handoff-closed`; `handoff-already-closed` (idempotent no-op) | `close-blocked` (names unverified blocking findings) | `not-a-repo` |
| `handoff import` | `[--round N]` | `finding-recorded` (n imported, `advisory`/`OPEN`) | — | `bad-args` (no legacy prose) |

`--auto` on `finding fix` collects the commits since the finding's task started (reusing
`gitops.commits_in_range`, as `status.cmd_complete_task` does) and the task's evidence.

## Read-only commands

| Command | Args | Status | Exit |
|---|---|---|---|
| `handoff report` | `[--json]` | `report-ok` | 0 |
| `handoff validate` | `[--json]` | `validate-ok`; else a defect status | 0 / 1 |

`handoff report` renders (human + JSON parity, CHK010): every handoff, each finding's
`id → severity → rule → file:line → state → task/commit/evidence`, and the **remaining unverified
blocking findings** (the `blocking_approval_check` set). `handoff validate` fails closed (exit 1)
on any defect (`dangling-reference`, `missing-closure`, `contradictory-state`, `duplicate-id`),
one distinct diagnostic each; commit-existence deferred to `specops reconcile` (FR-011).

## Determinism & JSON shape

- Findings emitted in canonical order (round, severity, file codepoint, line, id).
- No wall-clock timestamps in read output; byte-for-byte reproducible for identical inputs (SC-001/SC-008).
- JSON: `{command, outcome, class, status, output_version, ...extra}` via `outcome.render`.

## Approval interaction (not a `handoff` command)

`specops status transition-phase DONE -r APPROVED` (and any `DONE` entry) invokes
`handoff.blocking_approval_check`; a non-empty result fails closed (exit 1, status
`approval-blocked`) naming the unverified blocking findings, **before** the existing Feature 006
cycle-result gate. No handoffs present ⇒ degrade to that gate unchanged (FR-008).
