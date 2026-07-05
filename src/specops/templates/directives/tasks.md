
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

### Make the Phase Truthful

- The ledger is created at the `SPECIFY` phase. Bring it to `TASKS`:
  1. `specops status transition-phase PLAN`
  2. `specops status transition-phase TASKS`
- If a transition reports an unexpected current phase, stop and signal the human
  rather than forcing further writes.
