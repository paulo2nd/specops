
## SpecOps Implementation Directives

### Graceful Degradation

- If the `specops` command is not available in this environment, skip the SpecOps
  steps in this block and implement the tasks normally.

### Operational Silence (§6)

- Do NOT narrate progress inside a task — act silently.
- On task transition, output exactly one line, then continue immediately:
  `<task-id> done (<commit-sha7>), starting <next-task-id>`
  Example: `T003 done (a1b2c3d), starting T004`
- No other chat output during implementation.

### Ledger Loop

The preferred commit granularity is **one commit per user story**, not per task.
Work through all tasks in a user story first, then commit once.

For each task:
1. `specops status start-task <task-id>`
2. Implement the task.
3. Close the task:
   - **If this is NOT the final task of the user story**: close with evidence but no commit:
     `specops status complete-task <task-id> --evidence "CLI_LOG:<one-line summary>"`
   - **If this IS the final task of the user story**: commit all accumulated work first, then:
     `specops status complete-task <task-id> --auto`

Never edit `status.yaml` or `tasks.md` checkboxes by hand.
The ledger is the authority; the agent is the executor.

### Skills

Before starting the first task, check `skills_dir` (from `specops.json`). Load any skill files present. If the directory is empty or missing, proceed — skills are optional, not a gate.

### Reconcile Preflight

Before starting the first task of a session:
- Run `specops reconcile`
- Exit code ≠ 0 → stop immediately and signal the human.
  Do not proceed until the divergence is resolved.

### Phase Transitions

- At session start, before the first `start-task`, advance the ledger to the
  IMPLEMENT phase: `specops status transition-phase IMPLEMENT`. If the ledger is
  already in IMPLEMENT, continue.
- After the final task of the feature is DONE, open the review cycle:
  `specops status transition-phase REVIEW`. Then hand off to `/specops-review`.

### Stop-and-Ask Gates (§8.2)

Halt and ask the human before proceeding when any of the following applies:
- A persisted schema change (migration) is required.
- The task touches secrets, authentication, or cryptographic material.
- A public API contract would be broken.
- A dependency needs to be added, removed, or bumped by a major version.
- The root cause of a failing test or error is genuinely ambiguous.
