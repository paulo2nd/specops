# Quickstart: Lifecycle Recording Coverage — validation guide

**Feature**: 022 | **Plan**: [plan.md](plan.md) | **Contracts**: [contracts/](contracts/)

All validation runs through the automated test suite on fixtures — never
against this repository (No Self-Application).

## Prerequisites

```bash
conda run -n specops pip install -e .
```

## Run the feature's tests

```bash
conda run -n specops pytest tests/unit/test_status.py tests/unit/test_cli.py \
  tests/unit/test_record_step_buffer.py tests/unit/test_converge_directive.py \
  tests/unit/test_workflow_definition.py tests/unit/test_extension.py \
  tests/unit/test_taskstoissues_readonly.py -q
```

Full gates before any commit:

```bash
conda run -n specops ruff check src tests
conda run -n specops mypy src
conda run -n specops pytest -q
```

## Scenario validation map (spec → proof)

| Spec item | Proof |
|---|---|
| US1-1/2 — converge append with SC tags, reconcile green | `test_status.py`: fixture ledger + `tasks.md` gains tasks → `sync-tasks` appends `PENDING` entries; start/complete loop + `reconcile` fixture stays green ([sync-tasks contract](contracts/sync-tasks-cli.md)) |
| US1-3 — fail closed, specific diagnostic, no mutation | `test_cli.py`: `sync-tasks --check` exits 2 with the specific message on missing/corrupt ledger; `test_converge_directive.py`: pre-directive orders `--check` **before** converge and stops-and-asks on non-zero |
| US1-4 — determinism / idempotency | `test_status.py`: double `sync-tasks` on identical input → identical ledger, no duplicates, completed entries untouched |
| US2-1/2 — decision parity incl. pre-ledger | `test_record_step_buffer.py`: `record-step` pre-ledger → buffer file; `init-spec` drains into `workflow.skipped_steps` and deletes the buffer; post-drain records go direct ([buffer contract](contracts/record-step-buffer.md)) |
| US2-3 — all-skip run, zero obstruction | `test_record_step_buffer.py` + directive-content asserts: skip derivation records without prompting; `test_workflow_definition.py`: gates offer `skip` and no step is required |
| US2-4 — record ≠ validate | directive-content asserts: recording failure → stop-and-ask, never forced step; untagged task → consistency **report**, no gate |
| US3 — taskstoissues read-only | `test_taskstoissues_readonly.py`: no taskstoissues hooks in built manifest; hook registry == documented set; fixture ledger byte-identical across install/update |
| Edge: zero-append converge | `test_status.py`: `sync-tasks` on unchanged `tasks.md` → "no changes", exit 0 |
| Edge: abandoned pre-ledger run | `test_record_step_buffer.py`: stale buffer w/o `init-spec` is inert; fresh feature dir unaffected |
| Edge: lite lane unchanged | `test_workflow_definition.py`: specops-lite definition untouched |
| FR-001a — workflow converge gate | `test_workflow_definition.py`: corrective round contains gate → record → conditional `speckit.converge` ([hooks/workflow contract](contracts/hooks-and-workflow.md)) |
| FR-009 — `--if-needed` asymmetry documented | `test_workflow_definition.py` comment assert + docs check in review |
| SC-005 — unmanaged repos unchanged | directive-content asserts: every new directive opens with the Rule-5 no-op clause |
| SC-007 — EN/PT doc parity | `docs/commands.md`, `README.md`, `README.pt-br.md` updated in the same PR (review gate) |

## Manual smoke (optional, on a throwaway fixture repo — never here)

1. `specify init` a scratch repo → `specops init` → run lifecycle to tasks.
2. Append a task line to `tasks.md` by hand (simulating converge) →
   `specops status sync-tasks` → inspect `status.yaml` (`tasks[]` gained a
   `PENDING` entry) → `specops reconcile` green.
3. Delete `status.yaml` of a fresh feature → `specops status record-step
   clarify --decision skip` → see `.specops-pending-steps.json` → `specops
   status init-spec` → decision in `workflow.skipped_steps`, buffer gone.
