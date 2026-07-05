# Feature Specification: SpecOps CLI — Speckit Companion for Agent-Guided Atomic Development

**Feature Branch**: `001-specops-cli`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "Create the specification based on objective.md. Everything must be in English, including translating existing Portuguese artifacts. SpecOps has an init that runs after Speckit's init and prepares the repository for SpecOps, installing new files and adjusting Speckit's files. There will be /specops commands that run inside agents as well as SpecOps commands called from the terminal. SpecOps requires Git to be initialized in the directory and must validate this."

## Clarifications

### Session 2026-07-05

- Q: Where does the state ledger (`status.yaml`) reside? → A: Inside the active Speckit
  feature directory (e.g., `specs/001-x/status.yaml`), auto-detected from Speckit's
  configuration — not in a parallel `.specify/specs/<name>/` structure.
- Q: How does the ledger obtain its task list? → A: Every ledger command idempotently
  re-synchronizes the ledger with the feature's Speckit task list (`tasks.md`): newly
  discovered tasks enter as pending, and task identifiers not present in the task list
  are rejected. The ledger never diverges from its source.
- Q: Which Speckit prompt files receive directive blocks at initialization? → A: The
  implementation prompt (Operational Silence, ledger transitions, Stop-and-Ask gates)
  and the planning prompt (Empirical Verification, consistency gate). Each directive is
  injected at the lifecycle stage where it acts; other prompts are left untouched.
- Q: What values does the phase transition command accept? → A: A fixed phase set
  aligned to the Speckit lifecycle (SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW →
  DONE), validated by the CLI with ordered transitions — unknown phases or
  out-of-order jumps fail with a clear error.
- Q: What is the contract of task completion without automatic mode? → A: The caller
  must supply the `<CLASS>:<summary>` evidence string explicitly; completion without
  evidence fails. No task is ever marked done without evidence, in any mode.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prepare a Speckit Repository for SpecOps (Priority: P1)

A developer has just initialized Speckit in their project repository. They run a single
SpecOps initialization command from the terminal. SpecOps verifies the environment is
valid (Git repository present, Speckit structure present), generates the client
configuration file, installs the new SpecOps agent command, and adjusts Speckit's
existing agent prompt files by injecting clearly marked SpecOps directive blocks. When
the command finishes, the repository is fully prepared to operate under the SpecOps
methodology with no manual edits.

**Why this priority**: Initialization is the gateway to every other capability. Without
a prepared repository, no ledger, evidence, or review behavior exists. It is also the
capability the product is named after: a complement installed on top of Speckit.

**Independent Test**: Can be fully tested by running the initialization command in a
fresh repository that already contains Speckit, then verifying the configuration file
exists, the agent command is installed, the Speckit prompts contain the marked directive
blocks, and re-running the command produces no duplicates.

**Acceptance Scenarios**:

1. **Given** a Git repository with Speckit initialized, **When** the developer runs the
   SpecOps initialization command, **Then** the client configuration file is created at
   the repository root, the SpecOps review agent command is installed, and Speckit's
   existing agent prompts contain marked SpecOps directive blocks.
2. **Given** a directory that is not a Git repository, **When** the developer runs the
   initialization command, **Then** SpecOps informs the user that Git is required and
   offers to initialize a Git repository; if the user declines, initialization aborts
   with a clear error and a failure exit code.
3. **Given** a Git repository without Speckit, **When** the developer runs the
   initialization command, **Then** initialization aborts with a clear message
   instructing the user to initialize Speckit first.
4. **Given** a repository already initialized by SpecOps, **When** the developer runs
   the initialization command again, **Then** existing marked directive blocks are
   updated in place, no content is duplicated, and user edits outside the marked blocks
   are preserved.

---

### User Story 2 - Control Task Execution State Through the Ledger (Priority: P2)

While implementing a feature under the Speckit lifecycle, a developer (or an agent
acting on their behalf) records the physical state of execution in a structured ledger
file inside the repository: creating the ledger for a new spec, marking a task as in
progress, completing a task, and transitioning spec phases. When completing a task in
automatic mode, SpecOps runs the client's configured test command, harvests the commit
identifiers and code diff from the repository history, and records a structured evidence
entry — so completion never depends on an agent's narration.

**Why this priority**: The state ledger is the core advantage SpecOps brings to Speckit.
Every downstream capability (reconciliation, review) consumes it.

**Independent Test**: Can be fully tested by creating a ledger for a sample spec,
starting and completing a task with automatic evidence collection, and verifying the
ledger reflects each transition with the recorded evidence.

**Acceptance Scenarios**:

1. **Given** a prepared repository, **When** the user creates a ledger for a named spec,
   **Then** a spec workspace is created containing an initialized ledger file.
2. **Given** an initialized ledger, **When** the user starts a task, **Then** the task is
   marked as in progress and recorded as the recovery point.
3. **Given** a task in progress, **When** the user completes it in automatic mode,
   **Then** SpecOps runs the client's test command, collects the commit identifiers and
   diff from repository history, and records an evidence entry in the
   `<CLASS>:<summary>` format before marking the task as done.
4. **Given** a task in progress, **When** the client's test command fails during
   automatic completion, **Then** the task is NOT marked as done and the failure is
   reported with a failure exit code.
5. **Given** a directory that is not a Git repository, **When** any ledger command runs,
   **Then** it aborts with a clear English error message and a failure exit code.

---

### User Story 3 - Reconcile the Ledger Against Repository History (Priority: P3)

Before reviewing or continuing work, a developer or agent runs the reconciliation
command to verify that every commit recorded in the ledger actually exists in the
history of the active branch. If any recorded commit is missing or inconsistent, the
command blocks further progress by failing.

**Why this priority**: Reconciliation is what makes the ledger trustworthy. It is the
first gate of the review flow and protects against fabricated or lost state.

**Independent Test**: Can be fully tested by recording valid commits in a ledger and
confirming success, then recording a nonexistent commit and confirming the command
fails.

**Acceptance Scenarios**:

1. **Given** a ledger whose recorded commits all exist in the active branch history,
   **When** reconciliation runs, **Then** it succeeds with a success exit code.
2. **Given** a ledger referencing a commit absent from the active branch, **When**
   reconciliation runs, **Then** it fails with a failure exit code and identifies the
   divergent entries.

---

### User Story 4 - Validate Spec/Plan Consistency (Priority: P4)

Before a technical plan is accepted, a developer or agent runs the consistency command.
It reads the business specification and the technical plan of the active spec and
verifies that (a) every success criterion in the specification is covered by at least
one planned task, and (b) every file path declared in the plan carries a valid action
suffix — `(create)`, `(modify)`, etc. — and is consistent with the actual repository
working tree (paths marked for modification must exist; paths marked for creation must
not falsely claim existing structures).

**Why this priority**: This gate mechanically detects hallucinated plans — the most
common failure mode of agent-produced planning — before implementation starts.

**Independent Test**: Can be fully tested with a sample spec/plan pair: a compliant pair
passes; removing task coverage for a criterion or declaring a nonexistent path with a
modification suffix makes it fail.

**Acceptance Scenarios**:

1. **Given** a plan covering all success criteria with correctly suffixed, verifiable
   paths, **When** the consistency command runs, **Then** it succeeds with a success
   exit code.
2. **Given** a specification with a success criterion not covered by any task, **When**
   the consistency command runs, **Then** it fails and names the uncovered criterion.
3. **Given** a plan declaring a path with a modification suffix that does not exist in
   the working tree, **When** the consistency command runs, **Then** it fails and names
   the offending path.

---

### User Story 5 - Token-Optimized Review Inside the Agent (Priority: P5)

A reviewer invokes the SpecOps review command inside their coding agent. The injected
review prompt directs the agent to: load the skills required by the active spec from the
client's configured skills directory; run reconciliation first and abort immediately if
it fails; inspect the set of changed files and reject on the spot — without reading any
file contents — if changes exist outside the scope declared in the plan; and only then
review code, emitting each non-conformity to a revision report file in the short format
`[File]:[Line] - [rule violated and short action]`.

**Why this priority**: Review is the last stage of the lifecycle and depends on all
prior capabilities; it delivers the token-efficiency advantage but cannot function
without the ledger and reconciliation.

**Independent Test**: Can be fully tested by invoking the review command in an agent
against a prepared repository: a run with out-of-plan changes is rejected before any
file content is read; a compliant run produces a revision report in the short format.

**Acceptance Scenarios**:

1. **Given** a prepared repository with a failing reconciliation, **When** the review
   command runs in the agent, **Then** the review aborts immediately without reading any
   code.
2. **Given** changed files outside the scope declared in the plan, **When** the review
   command runs, **Then** the review rejects the submission based on file metadata alone,
   without reading file contents.
3. **Given** a compliant change set with rule violations in the code, **When** the
   review command runs, **Then** each non-conformity is written to the revision report
   in the format `[File]:[Line] - [rule violated and short action]`.

---

### Edge Cases

- Directory is not a Git repository: initialization offers to create one; every other
  command aborts with a clear English error and a failure exit code.
- Git repository exists but has no commits yet: ledger commands that only write state
  still work; evidence collection and reconciliation report a clear error when history
  is required and absent.
- Speckit structure is missing or unrecognized: initialization aborts with guidance to
  run Speckit's initialization first.
- Initialization is re-run after a Speckit upgrade replaced prompt files: marked
  directive blocks are re-injected; nothing is duplicated.
- A user manually edited content inside a marked directive block: re-initialization
  overwrites the block content (blocks are owned by SpecOps); edits outside blocks are
  preserved.
- Completing a task that was never started, or that is already done: the command fails
  with a clear message and does not corrupt the ledger.
- The client's test command fails or is not configured during automatic completion: the
  task remains in progress and the failure is reported.
- The client configuration file is missing when a command needs it: the command aborts
  and instructs the user to run initialization.
- Legacy Portuguese terms exist in ported artifacts: all product output, templates,
  ledger values, and injected prompts are in English (see Assumptions for the canonical
  translations).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The initialization command MUST verify the target directory is a Git
  repository; when it is not, it MUST offer to initialize one and MUST abort with a
  clear error and failure exit code if the user declines.
- **FR-002**: Every SpecOps command other than initialization MUST verify a Git
  repository is present and MUST abort with a clear English error message and a failure
  exit code when it is not.
- **FR-003**: The initialization command MUST detect the Speckit structure in the
  repository and MUST abort with guidance to initialize Speckit first when it is absent
  — SpecOps prepares a repository only after Speckit's own initialization.
- **FR-004**: The initialization command MUST generate a client configuration file at
  the repository root declaring, at minimum: the client's test command, the client's
  lint command, and the client's skills directory.
- **FR-005**: The initialization command MUST install the SpecOps review agent command
  (`/specops.review`) so it is invocable inside the client's coding agent. In this
  release, the review command is the only SpecOps agent command.
- **FR-006**: The initialization command MUST adjust exactly two of Speckit's existing
  agent prompt files by injecting SpecOps directive blocks delimited by explicit
  begin/end markers, each directive at the lifecycle stage where it acts:
  - the **implementation prompt** receives Operational Silence (including the exact
    task transition line `task-XX done (<commit-sha7>), starting task-(XX+1)`), ledger
    state transitions at task boundaries, and Stop-and-Ask gates (persisted schema
    changes, secrets, public contract breaks, technical ambiguities);
  - the **planning prompt** receives Empirical Verification of declared paths and
    conventions (action suffixes proven against the working tree) and the consistency
    gate. Other Speckit prompt files MUST be left untouched.
- **FR-007**: The initialization command MUST be idempotent: re-running it updates
  marked directive blocks in place, never duplicates content, and preserves user content
  outside the marked blocks.
- **FR-008**: SpecOps MUST provide terminal commands to manipulate the state ledger
  exclusively: initialize the ledger inside the active Speckit feature directory
  (auto-detected from Speckit's configuration), mark a task as in progress (recording
  it as the recovery point), mark a task as done, and transition spec phases. The
  ledger MUST NOT require hand-editing for any supported transition.
- **FR-008a**: Every ledger command MUST idempotently synchronize the ledger with the
  feature's Speckit task list before acting: tasks newly discovered in the task list
  are added as pending, and commands referencing task identifiers absent from the task
  list MUST fail with a clear error. The ledger never diverges from its source.
- **FR-008b**: Phase transitions MUST be validated against a fixed phase set aligned to
  the Speckit lifecycle (SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE) with
  ordered progression; an unknown phase name or an out-of-order jump MUST fail with a
  clear error and leave the ledger unchanged.
- **FR-009**: Automatic task completion MUST run the client's configured test command
  and MUST refuse to mark the task as done when the test command fails or is not
  configured.
- **FR-009a**: Task completion without automatic mode MUST require the caller to
  supply the `<CLASS>:<summary>` evidence string explicitly and MUST fail when it is
  absent. No completion path — automatic or manual — may mark a task as done without
  a recorded evidence entry.
- **FR-010**: Automatic task completion MUST harvest the task's commit identifiers and
  code diff from repository history and record an evidence entry in the ledger using the
  `<CLASS>:<summary>` format, covering both the test report and the code diff.
- **FR-011**: The reconciliation command MUST verify that every commit recorded in the
  ledger exists in the history of the active branch, succeeding (exit code 0) when
  consistent and failing (exit code 1) while identifying divergent entries otherwise.
- **FR-012**: The consistency command MUST parse the active spec's business
  specification and technical plan and MUST fail (exit code 1) when any success
  criterion lacks covering tasks or when any declared path's action suffix —
  `(create)`, `(modify)`, and related forms — contradicts the repository working tree.
- **FR-013**: The installed review agent command MUST direct the reviewing agent to,
  in order: load the skills required by the active spec from the configured skills
  directory; run reconciliation and abort immediately on failure; reject change sets
  containing files outside the plan's declared scope using file status metadata alone,
  without reading file contents; and emit each non-conformity to a numbered revision
  report file in the format `[File]:[Line] - [rule violated and short action]`.
- **FR-014**: All user-facing output, templates, injected prompts, configuration keys,
  ledger field names, and evidence values MUST be in English. Artifacts ported from the
  original methodology MUST be translated (see Assumptions for canonical translations).
- **FR-015**: SpecOps MUST remain agnostic to the client's technology stack and business
  rules; all client-specific behavior MUST enter exclusively through the client
  configuration file.
- **FR-016**: Every validation command (reconciliation, consistency) MUST run
  non-interactively and communicate outcomes through exit codes (0 success, 1 blocking
  failure) so they can gate automated and agent-driven workflows. Initialization is the
  only command permitted to prompt the user (for the Git initialization offer), and it
  MUST support a non-interactive mode that declines by default.

### Key Entities

- **State Ledger**: A structured file inside each spec workspace holding the physical
  execution state — tasks with statuses (pending, in progress, done), phase
  transitions, recovery point, recorded commit identifiers, and evidence entries. The
  task list is mirrored from the feature's Speckit task list on every command; the
  ledger is the single source of truth for execution progress, never for task
  definitions.
- **Client Configuration**: A file at the client repository root declaring the client's
  test command, lint command, and skills directory. The only channel for
  client-specific behavior.
- **Evidence Entry**: A structured record attached to a completed task in the
  `<CLASS>:<summary>` format, carrying the machine-collected test report and code diff
  references (commit identifiers).
- **Directive Block**: A marker-delimited region SpecOps injects into Speckit's agent
  prompt files, owned and updated by SpecOps across re-initializations.
- **Review Agent Command**: The `/specops.review` prompt installed into the client's
  agent, encoding the token-optimized review order.
- **Revision Report**: A numbered file produced by review runs listing non-conformities
  in the short single-line format.
- **Spec Workspace**: The active Speckit feature directory (e.g., `specs/001-x/`),
  auto-detected from Speckit's configuration, where SpecOps places the ledger and
  related execution artifacts alongside Speckit's own spec artifacts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can take a repository from "Speckit just initialized" to
  "fully prepared for SpecOps" with a single command in under 1 minute, with zero manual
  file edits.
- **SC-002**: 100% of tasks completed in automatic mode carry a machine-collected
  evidence entry (test report and code diff references); zero completions rely on
  agent-narrated evidence.
- **SC-003**: Reconciliation detects 100% of seeded ledger/history divergences (missing
  or fabricated commits) in verification testing, with zero false passes.
- **SC-004**: Change sets containing out-of-plan files are rejected by the review flow
  using file metadata only — zero file contents are read before rejection.
- **SC-005**: Re-running initialization on an already-prepared repository produces zero
  duplicated blocks and zero losses of user content outside marked blocks.
- **SC-006**: The same SpecOps installation prepares and operates repositories of at
  least two different technology stacks with no changes beyond their client
  configuration files.
- **SC-007**: 100% of user-facing output, installed templates, and injected prompt
  content is in English; no Portuguese strings remain in any product artifact.
- **SC-008**: Running any non-initialization command outside a Git repository fails
  within 1 second with an actionable English error message.

## Assumptions

- English is the canonical language for all product artifacts. Legacy Portuguese terms
  from the original methodology are translated as follows: action suffixes `(criar)` →
  `(create)`, `(alterar)` → `(modify)`; the task transition line
  `task-XX done (<commit-sha7>), iniciando task-(XX+1)` →
  `task-XX done (<commit-sha7>), starting task-(XX+1)`.
- Speckit is always initialized before SpecOps; SpecOps initialization is a second step
  that layers on top of an existing Speckit setup and never replaces it.
- In this release, `/specops.review` is the only agent-side command; ledger,
  reconciliation, and consistency operations are terminal commands that agents invoke
  through the directives injected into Speckit's prompts.
- Injected directive blocks are owned by SpecOps: their content may be overwritten on
  re-initialization, and explicit markers make them safe to update after Speckit
  upgrades.
- The Git-presence offer during initialization is interactive by design; all other
  commands are non-interactive so they can serve as automation gates.
- The evidence classification set for the `<CLASS>:<summary>` format follows the
  original methodology's classes; the exact class vocabulary is defined during planning
  from the ported scripts.
