# Quickstart / Validation Guide: Diagnostics and Machine Reports

Runnable scenarios that prove `specops doctor` and `specops report` behave per spec. These
run against **fixtures**, never against this repository (No Self-Application). They map to
the acceptance scenarios and success criteria.

## Prerequisites

```bash
conda run -n specops pip install -e .        # editable install of the CLI
conda run -n specops ruff check . && conda run -n specops mypy src
```

Fixtures reused from `tests/conftest.py`: `fake_speckit_repo`, `ledger_in_review`,
`context_map_repo`, `handoff_repo`, plus `snapshot_tree` and `write_profiles`/`write_map`.

## Scenario 1 — Healthy repo → verdict `ok`, exit 0 (US1 AC1, SC-002)

Set up a fixture whose active feature ledger is at the current schema, in-tree, with a
valid (or absent) context map and resolvable gate commands.

```bash
specops doctor --json
```

Expect: exit `0`; JSON `verdict == "ok"`, `class == "pass"`; `domains[]` contains **all**
ten domain ids (SC-002); every domain `severity == "ok"`.

## Scenario 2 — Ledger commit missing from git tree → `blocking`, exit 1 (US1 AC2, D7)

Record a commit sha in the ledger that is not an ancestor of HEAD.

```bash
specops doctor --json; echo "exit=$?"
```

Expect: exit `1`; `verdict == "blocking"`; the `workflow_divergence` domain has a
`blocking` finding naming the missing commit with `next_action_code ==
"reconcile_repository"`.

## Scenario 3 — No active feature → `ok`, exit 0 (US1 AC3, FR-010)

Fixture with a Spec Kit repo but no `.specify/feature.json` and no ledger.

```bash
specops doctor --json; echo "exit=$?"
```

Expect: exit `0`; `verdict == "ok"`; `feature_identity` domain has an `ok` finding,
`next_action_code == "start_or_select_feature"`.

## Scenario 4 — Unreadable ledger → `execution-error`, exit 2 (US2 AC3, FR-015)

Corrupt the active feature's `status.yaml` (invalid YAML).

```bash
specops doctor --json; echo "exit=$?"
```

Expect: exit `2`; `verdict == "execution-error"`; the `ledger` domain reports
`execution-error` (never silently `ok`); no domain omitted.

## Scenario 5 — Read-only + deterministic (SC-003, SC-005)

```bash
before=$(mktemp); after=$(mktemp)
# snapshot tree, run twice, snapshot again (mirrors tests/integration/test_gate_readonly_determinism.py)
specops doctor --json > out1.json
specops doctor --json > out2.json
diff out1.json out2.json           # MUST be identical (byte-for-byte)
```

Expect: `out1.json == out2.json`; `snapshot_tree` before == after (nothing mutated).

## Scenario 6 — Too-new vs migratable ledger schema (D6, CHK030)

- Set ledger `schema_version: 99` → expect `ledger` domain `blocking`, exit 1,
  `next_action_code == "ledger_schema_unsupported"`.
- Set ledger `schema_version: 5` (supported prior) → expect `ledger` domain `warning`,
  exit 0, `next_action_code == "run_status_migrate"`.

## Scenario 7 — Unavailable gate command → gate-availability `warning` (D5, FR-015a)

Write a gate profile whose command is an executable not on PATH.

```bash
specops doctor --json
```

Expect: `gate_availability` domain `warning` naming the profile + missing executable;
overall verdict `warning` (if nothing worse); exit `0`. Confirm no command was executed
(the fixture command, if run, would leave a side effect — assert it did not).

## Scenario 8 — Invalid context map → `blocking` (edge cases)

Use `context_map_repo` with a dependency cycle or unsafe path traversal.

Expect: `context_map` domain `blocking` (reusing `contextmap.validate` diagnostics),
`next_action_code == "fix_context_map"`.

## Scenario 9 — Unverified blocking handoff finding → `blocking` (FR + Feature 011)

Use `handoff_repo` with an OPEN blocking finding.

Expect: the ledger/handoff-health surface reports `blocking` with
`next_action_code == "verify_blocking_findings"` — consistent with the Feature 011
approval invariant.

## Scenario 10 — Compact status report (US3, FR-014)

```bash
specops report            # human
specops report --json      # machine
```

Expect (mid-feature fixture like `ledger_in_review`): correct `active_feature`, `branch`,
`phase`, `tasks{...}` counts, `active_task`, `review{cycles, blocking_open}`,
`workflow_lane`; JSON byte-identical across runs; no mutation.

## Definition of validation done

- Scenarios 1–10 pass under `pytest`.
- `ruff`, `mypy`, and the full suite pass at repo thresholds.
- EN/PT docs for `doctor`/`report` are behaviorally equivalent (FR-016/SC-008).
