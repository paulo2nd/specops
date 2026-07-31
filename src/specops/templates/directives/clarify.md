
## SpecOps Clarify Directives (Decision Recording)

### Graceful Degradation

- If this repository is not SpecOps-managed (no `specops.json` at the repository
  root), skip this block entirely — it is a no-op.
- If `specops.json` exists but the `specops` command is not available, or the
  recording command below fails (for example the active feature cannot be
  resolved), stop and ask the human: the run decision could not be recorded.

### Record the Run Decision

- Clarify just ran — that is the human's decision to run it. Record it:
  `specops status record-step clarify --decision run`
- Before the ledger exists the CLI buffers the decision automatically and the
  ledger receives it at creation — no special handling is needed here.
- Recording is bookkeeping only: it never re-runs, blocks, or gates the step.
