
## SpecOps Converge Directives (Record the Append)

### Graceful Degradation

- If this repository is not SpecOps-managed (no `specops.json`) or the `specops`
  command is not available, skip this block — the converge output stands as-is.

### SC Coverage Tags Before Recording

- Before recording, ensure every task converge appended to `tasks.md` carries
  one or more `[SC-xxx]` coverage labels — the same rule the task-generation
  directives impose on generated tasks. Tag them now, while the semantic
  context is fresh; use only SC IDs that exist in the spec's Success Criteria.

### Record the Append

- Record the mutation in the ledger:
  `specops status sync-tasks`
- Zero appended tasks ("no changes") is a supported outcome — treat it as
  success and continue.
- Never hand-edit `status.yaml` or `tasks.md` checkboxes. The ledger is the
  authority; the agent is the executor.

### Report Coverage (never a gate)

- Run `specops consistency` and report its coverage output to the human.
  Record, do not validate: an untagged or uncovered task surfaces as missing
  coverage in that report — do not abort converge on it, and do not judge or
  filter the converge-added work. The human decides what follows from the
  report.
