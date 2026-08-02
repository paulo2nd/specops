
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
     `--auto` harvests the story's commits and `CODE_DIFF` mechanically; it runs **no**
     test (Feature 024). Test verification happens once, at the review gate — not per
     story.

   Either close records both the legacy `<CLASS>:<summary>` string and a **structured
   evidence record** (Feature 012, Ledger v6) referenced by the task's `evidence_refs` —
   automatically, via the CLI. Do not construct evidence records by hand.

Never edit `status.yaml` or `tasks.md` checkboxes by hand.
The ledger is the authority; the agent is the executor.

### Context Provenance (Feature 009)

- When a context map exists, closing a task automatically snapshots the resolved
  context ids and the map digest into the ledger record (or an explicit
  `{map: none}`/`{map: invalid}` marker). This is mechanical — no agent action is
  required and nothing to record by hand.

### Context Read Set (Feature 023)

- At session start, before the first task (alongside the other session-start
  steps), read the `**SpecOps-Contexts**: …` line from the active feature's
  `plan.md` and resolve the IMPLEMENT-phase context package for each declared
  context id:
  `specops context resolve --id <context-id> --phase implement --json`
  (the phase value is the map's lowercase phase key; the uppercase ledger phase
  name is not a valid value here — and `--json` is required: the package fields
  below are emitted only in the JSON envelope).
- Start the session's reads from the **union** of the resolved packages — each
  package's `read_set` plus its `expanded_read_set` (dependency-contributed
  reads). Reading less than the union is always fine; the union is the default
  scope, not a required reading list.
- The read set is **guidance plus record — never a gate, and never a ceiling on
  discovery**: a read outside the union is permitted, blocks nothing, and by
  itself requires no acknowledgement. When implementing a task correctly
  requires understanding files beyond the union — call sites, tests, configs,
  or any other affected surface — read them. Never skip a needed read, or make
  a change blind, to stay inside the read set: token economy never outranks
  correctness.
- A genuine discovery that leads to a **changed** path not declared in
  `plan.md` follows the "Discovered Paths (Feature 010)" flow below
  (`specops trace acknowledge`) — reads are guidance; the drift gate governs
  changes, and that flow is the paved road for them.
- Degradation: "no map present" (exit 0) means this step is a supported
  no-op — proceed exactly as without it. A "no matching context" result for a
  declared id (also exit 0) means that context contributes no package —
  proceed and read normally for its scope. Any **non-zero exit** of the
  resolution step (for example an invalid map) means proceed **without
  read-set scoping** — never halt on this step and never treat its outcome as
  a gate.

### Discovered Paths (Feature 010)

- If implementing a task legitimately requires changing a file that was **not**
  declared in `plan.md` (a genuine discovery), acknowledge it once so review does
  not block it as unexplained drift:
  `specops trace acknowledge <path> --task <task-id> --reason "<concise reason>"`
- Acknowledge only real, in-scope discoveries — not scope creep. A conflicting or
  unknown-task acknowledgement fails closed and records nothing.
- This is a delivered capability; where SpecOps is not initialized the step is a
  no-op and implementation proceeds normally.

### Corrective Findings (Feature 011)

- When re-entering IMPLEMENT to resolve a rejected review, first read the open
  findings: `specops handoff report` (or the rendered
  `revisions/revision-<round>.md`). Each finding is a
  structured ledger record with a stable id (`R<round>-F<NN>`). After fixing the
  code and committing, mark the finding `FIXED`, linking the correction:
  `specops handoff finding fix <id> --task <task-id> --commit <sha> --evidence "<CLASS>:<summary>"`
  (or `--auto` to collect the task's commits and evidence).
- A finding cannot be verified until it is `FIXED` with a task, commit, and
  evidence. Verification and closure are the reviewer's job (`/specops-review`),
  never the implementer's. Approval is impossible while any **blocking** finding
  is unverified.

### Skills

Before starting the first task, check `skills_dir` (from `specops.json`). Load any skill files present. If the directory is empty or missing, proceed — skills are optional, not a gate.

### Record the Analyze Decision (Feature 022)

- At session start, if `.specify/extensions.yml` exists (the native extension
  manifest — on the legacy marker-block path skip this step), record the
  analyze decision if it is still unrecorded; its window closes when
  implementation begins:
  `specops status record-step analyze --decision skip --if-absent`
- `--if-absent` never overwrites an explicit decision — when one exists the
  command reports it and changes nothing. Recording never makes the step
  mandatory; where SpecOps is not initialized this is a no-op.

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
