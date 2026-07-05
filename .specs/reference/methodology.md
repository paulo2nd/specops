# Methodology Reference — Agent-Guided Atomic Development

This document is the local, self-contained source for the methodology sections cited
by [objective.md](../objective.md), the project constitution, and the feature specs.
The section numbering (§) is preserved so existing citations resolve here. The scripts
in this directory (`manage-status.py`, `reconcile-status.py`,
`scope-tasks-consistency.py`) are the reference implementations of the automation this
methodology relies on; `status-template.yaml`, `tasks-template.md`, and
`revision-template.md` are the reference artifact shapes.

---

## §6 Operational Silence

- The default mode of every session is **silent**: no intermediate progress updates
  during reading, implementation, testing, review, or git operations.
- Chat is permitted only on these events:
  - a blocker or ambiguity requiring explicit human action;
  - mandatory reviewer confirmation after `Decision=APPROVED` to decide on opening
    the PR;
  - session closure or role handoff;
  - a direct answer to an explicit human question.
- Except when answering an explicit human question, each session emits at most **one**
  closing message.
- **Implementer — intra-task silence and task transitions**: within a task, the
  implementer stays fully silent — progress narration (reading files, installing
  dependencies, incremental edits, running tests, lint fixes, reversible
  implementation decisions) is forbidden. When switching tasks, a **single factual
  line** is allowed in the format `task-XX done (<commit-sha7>), starting task-(XX+1)`
  — no summary of what was done, no list of touched files, no preamble. The transition
  line is **not** a human gate: the implementer immediately continues to the next
  `PENDING` task within the same session. Stopping between tasks is only permitted for
  a blocker or ambiguity.
- Blocker, ambiguity, or PR-confirmation messages must be objective, without social
  preamble and without narrating internal deliberation. Operational silence strictly
  forbids passive narration of work in progress (e.g., "I am creating method X",
  "I installed package Y"); it must NEVER be used as a justification to suppress
  questions. Whenever there is any business indefinition or an architectural/technical
  decision with trade-offs, the AI MUST halt execution and ask a direct, focused
  question — the message is as long as the human needs to decide, not an arbitrary
  limit.
- Session closure remains a dense technical summary, maximum 5 lines.
- Evidence lives in versioned artifacts, not in chat. Chat must not duplicate long
  narrative already recorded in the ledger, revision files, or planning artifacts.

## §7 Evidence Classes

The technical trail in the state ledger (`status.yaml`) uses these types:

- `CLI_LOG`: terminal output or logs.
- `TEST_REPORT`: automated test results.
- `SCREENSHOT_PATH`: path to screen captures.
- `CODE_DIFF`: technical explanation of a complex change.

### Format

- Record evidence as a single entry in the format `<CLASS>:<short summary>`.
- When there are multiple pieces of evidence, separate them with `;`.
- Example: `CLI_LOG:json.load ok; CODE_DIFF:kickoff-reads.json §read_scope_policy`.

**Atomic Evidence**: record immediately after each sub-task completes; never
accumulate for the end.

**Automated Technical Trail**: the AI is strictly forbidden from editing the state
ledger manually with file-writing tools. Every task status update (start/complete),
phase transition, or evidence addition must be executed exclusively through the CLI
automation, which also optimizes token consumption.

## §8.2 Stop-and-Ask Gates

The agent MUST block and ask the human before proceeding when the decision involves:

1. **Database migration** (any change to persisted schema).
2. **Auth, session, token, permission, crypto, secrets.**
3. **Breaking a public contract** consumed by another process (endpoint
   request/response, event payload, persisted format). The decision to break is
   always human.
4. **Adding, removing, or major-bumping a dependency.**
5. **Root-cause ambiguity**: the symptom admits two or more plausible causes with
   different fixes.

**Golden Rule**: if the decision is hard to revert without a rebase or without
coordinating with another system, **ask**. If a local revert solves it, decide and
continue.

## §11.1 Plan Consistency Gate

Applies at the planning → implementation handoff. The consistency validator runs as
the **first** closing action; a non-zero exit code blocks the handoff until the
planning artifacts are corrected. The gate mechanically validates:

- (a) presence of the required parseable headers in the planning artifacts;
- (b) coverage of every success criterion by at least one task in the backlog;
- (c) task references in dependency lists resolving to existing tasks;
- (d) **empirical existence of the declared paths**: paths suffixed `(modify)` whose
  file does not exist in the current worktree **block**; paths suffixed `(create)`
  whose parent folder does not exist **block**; paths suffixed `(remove)` whose file
  exists neither locally nor in recent Git history **block**. Accepted suffixes:
  `(create)`, `(modify)`, `(remove)`, and the mixed forms `(create OR extend)` /
  `(create OR modify)`. A missing suffix produces a warning (gradual transition for
  legacy artifacts).

This gate is the automation of the declarative empirical-verification rule in §17.4.
Downstream roles do not need to re-run it; it is the planner's responsibility at the
transition.

## §17.4 Empirical Verification of the Repo Before Declaring

Directed at any agent declaring paths, conventions, or patterns in versioned
artifacts:

1. **No declaration without verification against the current repo.** Before writing
   any file/folder path, project name, naming convention, reusable pattern, or stack
   assumption into a planning artifact, the agent MUST empirically confirm the current
   state of the branch via `ls`, `find`, `grep`, file reads, or equivalent tooling.
2. **Personal memory does not replace verification.** Even if the agent remembers a
   path, convention, or pattern, verification against the current branch state is
   mandatory before each declaration — renames, refactors, and removals may have
   invalidated the memory.
3. **Planning reference docs are not a source of paths.** Strategic documents, ADRs,
   and issues are aspirational/design input. They do NOT replace verification against
   the repo. Copying paths verbatim from them violates this rule.
4. **Framework conventions do not hold by default.** Conventions the agent knows from
   training only hold if confirmed in the current repo. Repos may have policies that
   deviate from the framework default.
5. **Accepted concrete verification per declaration class:**
   - **Path for `(modify)`**: file existence check or a read returning content.
   - **Path for `(create)`**: parent-folder existence confirmed; listing shows at
     least one sibling file with an equivalent pattern/naming.
   - **Path for `(remove)`**: local existence at planning time, or validation via
     recent Git history if already deleted during implementation.
   - **Naming convention**: a search confirms the proposed suffix/prefix is the
     pattern in use, not an invention.
   - **Reusable pattern**: a search locates the existing pattern before proposing a
     new one.
   - **Stack/project convention**: direct read of the relevant configuration file.
6. **Blocking mechanical gate.** The consistency validator (§11.1) automates the path
   checks; conventions/patterns/stack remain the agent's declarative responsibility
   under this section.
7. **Under ambiguity, stop and ask.** If verification reveals a divergent pattern, a
   nonexistent project, or an ambiguous convention (e.g., two coexisting patterns),
   the agent MUST stop and surface the alternatives in chat before declaring in the
   artifact.

## §18 Token-Efficient Review Process

To keep architectural and quality rigor without inflating context or blowing the API
token budget, the reviewer role operates under surgical reading constraints.

### §18.1 Mechanical Pre-Filters (Token Cost: Zero)

1. **Linter and test dependency:** the AI reviewer must not read files to check
   style, LOC limits, or wiring rules. The client's lint command and local test run
   must pass in full *before* the reviewer starts its analysis. If the build or the
   local linter is failing, the review is cancelled automatically at zero token cost.
2. **Rejection by metadata (scope check):** the reviewer must first run a fast
   terminal command (e.g., `git status --porcelain`) to map the modified files. If
   any file changed outside the planned scope of the task, the review must be aborted
   and marked `Decision=REJECTED` immediately, without reading the code content.

### §18.2 Surgical Reading (Diff-First)

1. **Focus on the Git diff:** the reviewer bases its analysis exclusively on the
   branch's `git diff` against the baseline, compared with the acceptance criteria.
2. **No whole-file loading:** the reviewer is forbidden from loading complete
   production files into context. To understand surrounding context, it loads only
   the minimal necessary neighboring lines.

### §18.3 Synthetic Response (Token-Saving Output)

1. **No verbosity:** long justifications, narrated deliberation, and praise of
   approved code are forbidden.
2. **Short error format:** on rejection, the reviewer marks `Decision=REJECTED` in
   the revision file and lists non-conformities objectively, at most 2 lines per item,
   in the format: `[File]:[Line] - [rule violated and short corrective action]`.
