
## SpecOps Checklist Directives (Decision Recording)

### Graceful Degradation

- If this repository is not SpecOps-managed (no `specops.json` at the repository
  root), skip this block entirely — it is a no-op.
- If `specops.json` exists but the `specops` command is not available, or the
  recording command below fails (for example the active feature cannot be
  resolved), stop and ask the human: the run decision could not be recorded.

### Record the Run Decision

- Checklist just ran — that is the human's decision to run it. Record it:
  `specops status record-step checklist --decision run`
  A run always records `run` — even over a previously derived `skip` (the
  step demonstrably ran; the record must say so). In a workflow-driven run
  the gate records the same decision — the duplicate is a harmless
  identical replace, and the gate remains the only recorder of `skip`.
- Before the ledger exists the CLI buffers the decision automatically and the
  ledger receives it at creation — no special handling is needed here.
- Recording is bookkeeping only: it never re-runs, blocks, or gates the step.
