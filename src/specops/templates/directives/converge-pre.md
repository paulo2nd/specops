
## SpecOps Converge Pre-Directives (Recording-Path Precondition)

### Graceful Degradation

- If this repository is not SpecOps-managed (no `specops.json` at the repository
  root), skip this block entirely and run converge normally — every SpecOps step
  here is a no-op.
- If `specops.json` exists but the `specops` command is not available, the
  recording path is missing: stop and ask the human before converge runs. Do not
  fall back to an unrecorded task-list mutation.

### Fail Closed Before Mutation

- Converge appends tasks to an existing `tasks.md`; on a SpecOps-managed
  repository that mutation must enter the ledger. Validate the recording path
  **before** converge touches `tasks.md`:
  `specops status sync-tasks --check`
- Exit code 0 → the recording path is healthy; proceed with converge.
- Any non-zero exit → stop and ask the human, reporting the diagnostic verbatim.
  Converge does not run and `tasks.md` is not mutated — an unrecorded task-list
  mutation is never silent. (`specops reconcile` remains the independent
  backstop for mutations made outside this directive.)
