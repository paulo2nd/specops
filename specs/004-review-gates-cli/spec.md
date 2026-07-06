# Feature Specification: Deterministic Review Gates in the CLI (`specops review`)

**Feature Branch**: `004-review-gates-cli`

**Created**: 2026-07-06

**Status**: Draft

**Input**: User description: "Move the deterministic review gates from the installed /specops-review prompt template into the CLI as a new `specops review` command. Today, steps 2-4 of templates/review.md (reconcile gate, lint/test pre-filter, working-tree/effective-diff check) are shell commands orchestrated by the AI agent reading the prompt — meaning gate enforcement depends on prompt fidelity and every rejection costs agent tokens. The new command runs these gates in pure Python, cheapest-first with early stop. The installed review.md template collapses steps 2-4 into a single instruction. The command must be usable standalone as a CI gate. Design stays forward-compatible with a future headless AI dispatch phase, which is out of scope."

## Clarifications

### Session 2026-07-06

- Q: How does the reconcile gate treat warnings (non-violations)? → A: Warnings are printed in the report (stdout) and the gate passes — same semantics as standalone `specops reconcile`.
- Q: How much of a failing lint/test command's output goes into the gate report? → A: The last 50 lines of combined output, with a note of the total size omitted.
- Q: Does the command impose a timeout on client lint/test commands? → A: No timeout in this feature — client commands are client-owned and CI pipelines impose their own limits.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One command runs all deterministic review gates (Priority: P1)

A reviewer — human at a terminal, an AI agent inside a session, or a CI job —
runs `specops review` in a SpecOps-initialized repository. The command
executes the deterministic review gates in cheapest-first order (reconcile →
lint → test → working-tree/effective-diff), stops at the first failure, and
reports which gate failed and why. If every gate passes, it prints a pass
report. The outcome is communicated through the exit code so any caller can
act on it mechanically.

**Why this priority**: This is the feature. Gate enforcement moves from
"the agent hopefully follows the prompt" to "the tooling physically runs the
checks" — closing the gap between SpecOps' promise (evidence collected by
tooling, not claimed by the agent) and the current review flow, where the
agent orchestrates the gates itself.

**Independent Test**: In a fixture repository with a known gate violation
(e.g., a ledger commit missing from Git history, a failing test, or a dirty
working tree), run `specops review` and observe a rejection naming that gate
with its evidence and a non-zero exit. Fix the violation, rerun, and observe
the next gate being evaluated (or a pass report when all gates hold).

**Acceptance Scenarios**:

1. **Given** a repository where the ledger references a commit absent from
   the current branch history, **When** `specops review` runs, **Then** it
   reports the reconcile gate as failed with the reconcile violations, exits
   with the failure code, and does not evaluate any later gate.
2. **Given** a repository where reconcile passes but the configured lint
   command fails, **When** `specops review` runs, **Then** it reports the
   lint gate as failed with the command's exit code and the last 50 lines
   of its output, and does not run the test gate.
3. **Given** a repository where reconcile and lint pass but the configured
   test command fails, **When** `specops review` runs, **Then** it reports
   the test gate as failed with the command's exit code and the last 50
   lines of its output.
4. **Given** a repository with uncommitted changes, **When** `specops review`
   reaches the working-tree gate, **Then** it rejects with the list of dirty
   files.
5. **Given** a clean repository whose current branch has no effective diff
   against the ledger baseline, **When** `specops review` reaches the
   working-tree gate, **Then** it rejects with "no effective diff — nothing
   to review".
6. **Given** a repository where all gates pass, **When** `specops review`
   runs, **Then** it prints a per-gate pass report and exits with the
   success code.
7. **Given** any gate failure, **When** the command exits, **Then** the
   ledger (`status.yaml`) is byte-identical to its state before the run —
   a gate rejection is not a review verdict.

---

### User Story 2 - The installed review prompt delegates gates to the command (Priority: P2)

A SpecOps user re-runs `specops init` in their Speckit repository. The
installed `/specops-review` prompt no longer instructs the agent to
orchestrate four separate gate checks; it instructs the agent to run
`specops review` once and, on a non-zero exit, report the command's output
and stop with REJECTED. The agent-driven parts of review (surgical diff
reading, revision report, verdict transition) are unchanged.

**Why this priority**: Delivers the methodology change to every client
repository (the templates are the delivery vehicle). It removes the
possibility of an agent skipping a gate and cuts the token cost of the
common early-rejection path, but it depends on User Story 1 existing.

**Independent Test**: Run `specops init` in a fixture Speckit repository and
inspect the installed review command file: the four gate steps are replaced
by a single instruction referencing `specops review`; the surgical review
and revision report steps remain intact.

**Acceptance Scenarios**:

1. **Given** a Speckit repository, **When** `specops init` installs or
   refreshes the review command, **Then** the installed prompt contains a
   single gate instruction ("run `specops review`; non-zero exit →
   REJECTED, report its output, stop") in place of the previous reconcile,
   lint/test, and working-tree steps.
2. **Given** an agent following the updated prompt in a repository with a
   failing gate, **When** it runs the gate instruction, **Then** the review
   session stops at REJECTED without the agent reading any code.

---

### User Story 3 - Standalone CI gate (Priority: P3)

A maintainer adds `specops review` to a CI pipeline (or to a Speckit
workflow as a shell step). The command runs without any interactive prompt,
in any ledger phase, and its exit code alone gates the pipeline.

**Why this priority**: Extends the same gate to automation contexts. Valuable
but not required for the in-session review flow to benefit.

**Independent Test**: Run `specops review` non-interactively (no TTY) in a
repository whose ledger phase is not REVIEW; observe that it evaluates the
gates normally and never prompts.

**Acceptance Scenarios**:

1. **Given** a repository in any ledger phase (e.g., IMPLEMENT), **When**
   `specops review` runs, **Then** the gates are evaluated — there is no
   REVIEW-phase precondition.
2. **Given** a non-interactive environment, **When** `specops review` runs,
   **Then** it completes without requesting input.

---

### Edge Cases

- `specops.json` absent or unparseable → configuration error with guidance
  to run `specops init` first; no gate is evaluated.
- Ledger (`status.yaml`) absent → error stating SpecOps state is not
  initialized for the active feature; corrupt ledger → the existing ledger
  parse error and its dedicated exit code.
- `lint_command` empty → lint gate is reported as SKIPPED and the run
  continues (existing config semantics: lint is optional).
- `test_command` empty → test gate is reported as SKIPPED and the run
  continues (documented in the pass report so a silent no-test pass is
  visible).
- Configured lint/test command references a program that cannot be started →
  treated as a gate failure (the gate cannot attest quality), reported with
  the underlying reason.
- Not inside a Git repository → error before any gate runs.
- Ledger `baseline` commit missing from local history → surfaced by the
  reconcile gate (existing reconcile semantics).
- Both lint and test would fail → only the lint failure is reported
  (cheapest-first early stop is intentional).
- Very long lint/test output → only the last 50 lines are echoed in the
  report, with the total size noted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `specops review` command that
  evaluates the deterministic review gates in this fixed order: reconcile,
  lint, test, working tree/effective diff.
- **FR-002**: The command MUST stop at the first failing gate (early stop)
  and MUST NOT evaluate later gates after a failure.
- **FR-003**: The reconcile gate MUST apply the existing reconcile
  validation semantics in-process (not by spawning a separate `specops`
  process) and fail the gate when any violation is found, reporting the
  violations. Reconcile warnings are echoed in the report (stdout) and do
  NOT fail the gate — identical to standalone `specops reconcile`.
- **FR-004**: The lint and test gates MUST execute the client's
  `lint_command` and `test_command` from `specops.json`; a non-zero exit
  fails the gate, reporting the command, its exit code, and the last 50
  lines of its combined output (noting the total size when truncated). An
  empty command marks its gate SKIPPED.
- **FR-005**: The working-tree gate MUST fail when uncommitted changes exist
  (reporting the file list) or when there is no effective diff between the
  ledger baseline and the current HEAD (reporting "nothing to review").
- **FR-006**: On all gates passing (or skipped), the command MUST print a
  per-gate report (PASS/SKIPPED per gate) and exit 0; on any gate failure it
  MUST exit 1. Ledger parse failures keep their existing dedicated exit
  code (2). No other exit codes are introduced.
- **FR-007**: The command MUST NOT mutate the ledger or any repository file
  under any outcome — gate evaluation is read-only; a gate rejection is not
  a review verdict and leaves any open review cycle untouched.
- **FR-008**: The command MUST run without interactive prompts in all
  outcomes and MUST NOT require the ledger phase to be REVIEW.
- **FR-009**: Failures MUST be reported through the existing error contract:
  business errors raised as the established error hierarchy, mapped to exit
  codes and streams by the single CLI-boundary mapper (violation details to
  stderr, reports to stdout, consistent with `reconcile`/`consistency`).
- **FR-010**: The installed review prompt template MUST be updated so its
  gate steps collapse into a single instruction: run `specops review`; on
  non-zero exit report the command output and stop with REJECTED. The
  surgical diff review, revision report, verdict transition, and active
  learning sections of the template MUST remain functionally unchanged.
- **FR-011**: `specops init` (first run and re-run) MUST deliver the updated
  review prompt to client repositories through the existing install
  mechanism, preserving the existing uninstall/restore guarantees.
- **FR-012**: The command's user-facing output MUST be in English,
  consistent with the rest of the CLI.

### Key Entities

- **Gate**: a named deterministic check (reconcile, lint, test,
  working-tree) with an outcome of PASS, FAIL, or SKIPPED, an ordering
  position, and failure evidence (violations, exit code + output tail, or
  file list).
- **Gate report**: the ordered collection of gate outcomes for one run,
  rendered to the user and summarized by the process exit code.
- **Review prompt template**: the installed `/specops-review` instruction
  file whose gate section now delegates to the command.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can determine whether a change is gate-clean with a
  single command invocation, and identify the failing gate and its evidence
  from the output alone, without opening any other file.
- **SC-002**: In a repository with a failing deterministic gate, a review
  session following the installed prompt reaches REJECTED with zero source
  files read by the agent.
- **SC-003**: The gate portion of a review session requires exactly one
  agent-issued command instead of the previous four, and no gate can be
  omitted by the agent.
- **SC-004**: A CI pipeline can adopt the command as a quality gate using
  only its exit code — 100% of gate outcomes are distinguishable as
  pass/fail without parsing output.
- **SC-005**: After `specops init` on an existing client repository, the
  refreshed review prompt contains the collapsed gate instruction, with no
  manual edit required.
- **SC-006**: All pre-existing CLI behaviors (messages, exit codes, streams)
  outside the review flow remain byte-identical.

## Assumptions

- The ledger's recorded `baseline` commit (captured at `status init-spec`)
  is the diff baseline for "effective diff" — the same notion the current
  template and reconcile warnings already use.
- An empty `test_command` is treated like an empty `lint_command` (gate
  SKIPPED, visibly reported) rather than an error; the shipped default
  config already sets `test_command`, so an empty value is a deliberate
  client choice.
- Gate evaluation requires an initialized SpecOps state (config + ledger);
  running the command in a repository without them is an error, not a
  silent pass — a CI job must fail loudly when misconfigured.
- The future headless AI dispatch phase (agent invocation after gates pass,
  verdict file, ledger transition by the CLI) is explicitly out of scope;
  this feature must simply not preclude it (the command remains the natural
  place to add a post-gates step).
- Cheapest-first gate order is fixed and not user-configurable in this
  feature.
- No timeout is imposed on client lint/test commands: they are client-owned
  (Principle V) and automation contexts (CI) already bound job duration; a
  hung command is the client's own hung tooling, surfaced by the caller's
  limits.
