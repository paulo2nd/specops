
## SpecOps Task-Generation Directives

### Graceful Degradation

- If the `specops` command is not available in this environment, skip the SpecOps
  steps in this block and generate `tasks.md` normally.

### SC Coverage Tags

- Every generated task line in `tasks.md` MUST carry one or more `[SC-xxx]`
  labels declaring which spec Success Criteria the task covers.
  Example: `- [ ] T005 [SC-003,SC-007] Implement reconcile.py`
- A task may cover more than one SC; separate IDs with commas inside the brackets.
- Use only SC IDs that exist in the spec's Success Criteria section — never
  invent IDs.

### Create the Ledger

- After `tasks.md` is finalized, create the execution ledger:
  `specops status init-spec`
- If it reports the ledger already exists, treat that as success and continue —
  do NOT abort the stage.
- Never hand-edit `status.yaml` or `tasks.md` checkboxes. The ledger is the
  authority; the agent is the executor.

### Record Skipped Optional Steps (Feature 022)

- This derivation requires the native extension manifest: if
  `.specify/extensions.yml` does not exist, skip this section (on the legacy
  marker-block path the run decisions are not recorded, so a skip must not be
  derived from their absence).
- After `init-spec` succeeds — which also drains any decisions buffered before
  the ledger existed — derive the skip decisions for the optional steps whose
  lifecycle window has closed (clarify and checklist precede tasks):
  1. `specops status record-step clarify --decision skip --if-absent`
  2. `specops status record-step checklist --decision skip --if-absent`
- `--if-absent` never overwrites an explicit decision (a gate choice or an
  earlier recording); when one exists the command reports it and changes
  nothing. Recording never makes an optional step mandatory and never blocks
  on a skip.

### Make the Phase Truthful

- The ledger is created at the `SPECIFY` phase. Bring it to `TASKS`:
  1. `specops status transition-phase PLAN`
  2. `specops status transition-phase TASKS`
- If a transition reports an unexpected current phase, stop and signal the human
  rather than forcing further writes.
