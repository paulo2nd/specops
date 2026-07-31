
## SpecOps Analyze Directives (Decision Recording)

### Graceful Degradation

- If this repository is not SpecOps-managed (no `specops.json` at the repository
  root), skip this block entirely — it is a no-op.
- If `specops.json` exists but the `specops` command is not available, or the
  recording command below fails (for example the active feature cannot be
  resolved), stop and ask the human: the run decision could not be recorded.

### Record the Run Decision

- Analyze just ran — that is the human's decision to run it. Record it:
  `specops status record-step analyze --decision run`
- The ledger normally exists by this point (analyze follows tasks); if it does
  not yet, the CLI buffers the decision automatically — no special handling.
- Recording is bookkeeping only: it never re-runs, blocks, or gates the step.
