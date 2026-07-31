# Contract: hook registrations, directives, and workflow changes

**Purpose**: the agent-facing delivery of Feature 022 (Principle IV — all
behavior ships through templates).

## New hook registrations (`extension.py` `_HOOK_SPECS`, additive)

| Stem | Hook point | optional | Directive obligation (summary) |
|---|---|---|---|
| `converge-pre` | `before_converge` | `false` | Not SpecOps-managed → explicit no-op (Rule 5). Managed → `specops status sync-tasks --check`; non-zero exit or CLI absent → **stop-and-ask, converge does not run** (fail closed before mutation, FR-003). |
| `converge` | `after_converge` | `false` | Tag every appended task with `[SC-xxx]` in `tasks.md` (tagging obligation, clarification Q2) → `specops status sync-tasks` → `specops consistency`, **reporting** coverage output without gating (untagged surfaces as missing coverage, never blocks). Rule-5 no-op when unmanaged. |
| `clarify` | `after_clarify` | `false` | Managed → `specops status record-step clarify --decision run` (buffers pre-ledger). Rule-5 no-op otherwise. |
| `checklist` | `after_checklist` | `false` | Same, step `checklist`. |
| `analyze` | `after_analyze` | `false` | Same, step `analyze`. |

**No entry for `taskstoissues`** — contract by absence, guarded by
regression test (research R7): manifest contains no
`before_/after_taskstoissues` SpecOps entries; hook registry equals exactly
the documented set; fixture ledger byte-identical across install/update.

## Modified directives

- **`tasks.md`** (after_tasks, ledger-creation seam): after `init-spec` —
  which now drains the pre-ledger buffer — run `specops status record-step
  clarify --decision skip --if-absent` and the same for `checklist` (skip
  derivation, both entry modes; `--if-absent` never overwrites an explicit
  decision).
- **`implement.md`** (after_implement): at session start, run
  `specops status record-step analyze --decision skip --if-absent`.

## Workflow changes (`workflows/specops/workflow.yml`)

1. **Record steps return to their gates**: `clarify-record` /
   `checklist-record` move back adjacent to `clarify-gate` /
   `checklist-gate` (the #50 deferral is dissolved by buffering;
   `analyze-record` already sits at its gate). The
   `test_record_steps_run_after_the_ledger_exists` test inverts to pin the
   new adjacency.
2. **Converge gate in the corrective round** (clarification Q1, research R6) —
   inside the `corrective-round` if-branch, after `open-corrective-round`:

   ```yaml
   - id: converge-gate
     type: gate
     message: "Run /speckit.converge to reconcile the task list before the corrective round?"
     options: [run, skip]
   - id: converge-record
     type: shell
     run: "specops status record-step converge --decision {{ steps.converge-gate.output.choice }}"
   - id: converge-run
     type: if
     condition: "{{ steps.converge-gate.output.choice == 'run' }}"
     then:
       - id: converge
         command: speckit.converge
         integration: "{{ inputs.integration }}"
         input:
           args: "{{ inputs.spec }}"
   ```

   The ledger always exists here (post-tasks) — no buffering interplay.
   Bounded by the existing `max_iterations: 3`.
3. **`--if-needed` asymmetry comment** (FR-009): a comment block stating the
   deliberate contract — workflow definition uses idempotent
   `--if-needed` transitions (engine re-runs/resume); directives use bare
   fail-closed transitions with stop-and-ask (an unexpected phase in an agent
   session is a human question). Mirrored in `docs/commands.md`.

## Degradation matrix (Rule 5 / FR-010, SC-005)

| Repository state | converge-pre | converge | clarify/checklist/analyze | taskstoissues |
|---|---|---|---|---|
| SpecOps not initialized (no `specops.json`) | no-op, converge proceeds as stock Spec Kit | no-op | no-op | untouched (never hooked) |
| Managed, CLI absent | **stop-and-ask** (recording path unavailable = fail closed) | n/a (pre blocked) | prompt still works standalone; recording step reports and stops-and-asks | untouched |
| Managed, feature unresolvable (`.specify/feature.json` missing/stale → `record-step` exit 2) | **stop-and-ask** | **stop-and-ask** | **stop-and-ask** (recording is mandatory; distinct from the unmanaged no-op above) | untouched |
| Managed, healthy | `--check` gate → proceed | tag → sync → report | record (buffer or ledger) | untouched |
