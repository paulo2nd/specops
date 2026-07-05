# Feature Specification: CLI Hardening & Developer Experience

**Feature Branch**: `002-cli-hardening-dx`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "CLI hardening + DX improvements: fix review approval flow bug (transition-phase DONE -r APPROVED never works via CLI; gate checks review cycle result before applying -r, possibly add record-review command), add specops status show command (human/agent-readable ledger summary: current phase, active task, task counts, review cycles), add --version flag, atomic ledger writes (write-temp-then-rename), fix evidence validation (reject empty summaries, remove dead _EVIDENCE_RE), refactor business modules to raise exceptions instead of sys.exit (status.py, reconcile.py, consistency.py), numeric feature-dir ordering fallback, remove dead code (duplicate imports, unused vars, imports in loops in consistency.py, private regex usage), and dev tooling: ruff + mypy + pytest-cov + GitHub Actions CI"

## Clarifications

### Session 2026-07-05

- Q: Como tratar `; ` dentro de um summary de evidence (ex.: `CLI_LOG:step one; done`)? → A: Rejeição estrita — todo segmento após `; ` deve ser `CLASS:summary` válido; segmentos sem classe válida invalidam a string inteira.
- Q: Qual formato de saída o `specops status show` deve ter nesta feature? → A: Só texto plano estruturado (uma informação por linha); `--json` fica fora de escopo.
- Q: Quais versões de Python o pipeline de CI deve testar? → A: Piso declarado (3.10) + versão estável mais recente.
- Q: Qual limiar de cobertura de testes deve ser exigido no gate? → A: 85% de statements, bloqueante — CI falha abaixo do limiar.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete the review approval flow via CLI (Priority: P1)

An operator (human or review agent) has finished a review cycle with an
APPROVED verdict and wants to close the feature by transitioning the ledger
from REVIEW to DONE — using only CLI commands, as the project constitution
requires (Principle II: the ledger is never hand-edited).

Today this is impossible: the DONE gate evaluates the latest review cycle's
result **before** the supplied `-r APPROVED` result is applied, so
`specops status transition-phase DONE -r APPROVED` always fails with
"latest review cycle result is 'None'". The only workaround is hand-editing
`status.yaml`, which directly violates the constitution.

**Why this priority**: This is a functional bug that breaks the core state
machine at its final step and forces a constitution violation to work around
it. Every feature managed by SpecOps hits this wall.

**Independent Test**: In a repository with a ledger in REVIEW phase and an
open review cycle, run `specops status transition-phase DONE -r APPROVED` and
verify the phase becomes DONE with the cycle recorded as APPROVED — no manual
file edits at any point.

**Acceptance Scenarios**:

1. **Given** a ledger in REVIEW with an open review cycle (result unset),
   **When** the operator runs `transition-phase DONE -r APPROVED`,
   **Then** the cycle is recorded as APPROVED with a completion date, the
   phase becomes DONE, and the command exits with success.
2. **Given** a ledger in REVIEW with an open review cycle,
   **When** the operator runs `transition-phase DONE` without a result and no
   prior approval exists, **Then** the command fails with a message explaining
   an APPROVED result is required, and the ledger is unchanged.
3. **Given** a ledger in REVIEW with an open review cycle,
   **When** the operator runs `transition-phase DONE -r REJECTED`,
   **Then** the command fails (REJECTED cannot enter DONE), the ledger is
   unchanged, and the message points to the corrective
   `transition-phase IMPLEMENT -r REJECTED` path.
4. **Given** a ledger whose latest review cycle is already APPROVED,
   **When** the operator runs `transition-phase DONE` without a result,
   **Then** the transition succeeds (existing behavior preserved).

---

### User Story 2 - Inspect ledger state at a glance (Priority: P2)

An operator or agent wants to know where a feature stands — current phase,
which task is active, how many tasks are pending/in-progress/done, and the
review-cycle history — without opening and reading the raw ledger file.

**Why this priority**: Every SpecOps session starts with "where are we?".
Today the only answer is reading raw YAML, which is error-prone for humans
and token-expensive for agents. A summary command is the single biggest
day-to-day usability gain.

**Independent Test**: In a repository with a populated ledger, run
`specops status show` and verify the output presents phase, active task,
task counts, and review cycles accurately; run `specops --version` and verify
the installed version is printed.

**Acceptance Scenarios**:

1. **Given** a ledger with mixed task states and one review cycle,
   **When** the operator runs `specops status show`,
   **Then** the output shows the feature name, current phase, active task
   (or "none"), counts of PENDING / IN_PROGRESS / DONE / orphaned tasks, and
   each review cycle's round and result.
2. **Given** no ledger exists for the active feature,
   **When** the operator runs `specops status show`,
   **Then** the command fails with the standard "ledger not found" guidance
   (pointing to `init-spec`).
3. **Given** any repository state,
   **When** the operator runs `specops --version`,
   **Then** the installed package version is printed and the command exits
   with success.

---

### User Story 3 - Trust the ledger under failure and bad input (Priority: P3)

An operator relies on the ledger as the single source of truth. A crash or
interruption mid-write must never corrupt it, and malformed evidence strings
must never be accepted into it.

**Why this priority**: The ledger is the product's core asset (Principle II).
Corruption or garbage evidence silently undermines every downstream gate
(reconcile, review). Lower than P1/P2 only because the failure window is
narrow in practice.

**Independent Test**: Simulate an interrupted ledger write and verify the
previous ledger content remains intact and parseable; submit evidence strings
with empty summaries or unknown classes and verify they are rejected.

**Acceptance Scenarios**:

1. **Given** a valid ledger on disk, **When** a ledger update is interrupted
   before completion, **Then** the ledger file still contains the previous
   valid content (never a partial write).
2. **Given** an operator completing a task, **When** they supply evidence with
   an empty summary (e.g. `CLI_LOG:`), **Then** the command rejects it with
   the expected-format message and the task stays IN_PROGRESS.
3. **Given** an operator completing a task, **When** they supply a multi-part
   evidence string where any part has an unknown class or empty summary,
   **Then** the whole string is rejected.
4. **Given** feature directories `specs/9-foo` and `specs/10-bar` and no
   explicit active-feature pointer, **When** any command resolves the active
   feature, **Then** the highest-numbered directory (`10-bar`) is selected
   (numeric, not lexicographic, ordering).

---

### User Story 4 - Consistent failure behavior across the CLI (Priority: P4)

A maintainer (or a tool embedding SpecOps) needs every command to fail the
same way: business logic reports failures as structured errors, and only the
CLI boundary translates them into exit codes and stderr messages.

**Why this priority**: Today business modules terminate the process directly
from deep inside the logic, which makes the modules unusable as a library,
makes tests assert on process exit instead of behavior, and has already let
inconsistencies accumulate (duplicate exit helpers that nothing uses). This
is internal quality work that de-risks every future feature.

**Independent Test**: Exercise each business operation directly (not via the
CLI) and verify failures surface as catchable errors; run the full CLI suite
and verify every documented exit code (0 success / 1 blocking failure /
2 unexpected error) is preserved exactly.

**Acceptance Scenarios**:

1. **Given** any failing precondition (missing ledger, unknown task, invalid
   transition), **When** the operation is invoked programmatically,
   **Then** it raises a structured error carrying the user-facing message —
   it does not terminate the calling process.
2. **Given** the same failing precondition, **When** the operation is invoked
   via the CLI, **Then** the exit code and stderr message are identical to
   the current documented behavior (no regression).
3. **Given** the refactored codebase, **When** static inspection runs,
   **Then** no dead code remains from the previous structure (unused
   validation regex, duplicate imports, unused variables, imports inside
   loops, cross-module use of private symbols).

---

### User Story 5 - Automated quality gates for the project itself (Priority: P5)

A maintainer wants every change to SpecOps to be automatically linted,
type-checked, and tested with coverage measurement — locally and on every
push/pull request — so that regressions and dead code are caught by machines,
not by review.

**Why this priority**: The dead code and the P1 bug both shipped because no
automated gate existed to catch them. Tooling is the cheapest permanent fix,
but it delivers value only after the code it checks is in shape — hence last.

**Independent Test**: Introduce a lint violation, a type error, and a failing
test in separate throwaway changes; verify each one is flagged locally by a
single command and blocks the CI pipeline.

**Acceptance Scenarios**:

1. **Given** the configured project, **When** a maintainer runs the standard
   check command(s) locally, **Then** lint, type, and test+coverage results
   are produced with a clear pass/fail outcome.
2. **Given** a pull request with a lint violation, type error, or test
   failure, **When** CI runs, **Then** the pipeline fails and blocks merge.
3. **Given** the clean codebase at feature completion, **When** the full gate
   runs, **Then** all checks pass and test coverage of the source package is
   reported at or above the agreed threshold.

---

### Edge Cases

- `transition-phase DONE -r APPROVED` issued when the latest cycle is already
  closed as REJECTED (corrective placeholder open): the result applies to the
  open placeholder cycle, not the closed one.
- `transition-phase DONE -r <arbitrary text>` (neither APPROVED nor
  REJECTED): rejected with the expected-values message; ledger unchanged.
- A valid result supplied on a transition that does not consume it
  (e.g. `transition-phase PLAN -r APPROVED`): silently ignored — the
  transition proceeds as if no result were given (current behavior kept).
- `status show` on a ledger created before this feature (no `review_cycles`
  key, tasks list empty): renders with zero counts instead of crashing.
- Interrupted write leaves a stale temporary file behind: subsequent ledger
  operations succeed and overwrite/ignore it.
- Evidence string containing the separator inside a summary
  (e.g. `CLI_LOG:step one; done`): rejected — `; ` is always a part
  separator, and every resulting part must be a valid `<CLASS>:<summary>`;
  a part without a recognized class invalidates the whole string.
- Feature directories with non-numeric prefixes (e.g. `specs/archive/`)
  during numeric-ordering fallback: ignored, as today.
- `specops --version` run outside a Git repository: still succeeds (version
  lookup has no repository dependency).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST apply a review result supplied with the DONE
  transition to the currently open review cycle **before** evaluating the
  DONE entry gate, so that `transition-phase DONE -r APPROVED` succeeds from
  REVIEW in a single command.
- **FR-002**: The system MUST reject a DONE transition whose supplied result
  is not APPROVED, and MUST reject result values other than APPROVED or
  REJECTED on any transition, leaving the ledger unmodified in both cases.
- **FR-003**: The system MUST record the applied review result and its
  completion date on the review cycle as part of the same ledger update that
  advances the phase (one atomic state change, never a half-applied pair).
- **FR-004**: The system MUST provide a read-only `status show` command that
  reports: feature name, current phase, active task (or none), task counts by
  status (including orphaned), and every review cycle with round, dates, and
  result — as structured plain text (one fact per line). It MUST NOT modify
  the ledger.
- **FR-005**: The system MUST expose the installed package version via a
  `--version` option on the root command, functional in any directory.
- **FR-006**: Every ledger write MUST be atomic at the filesystem level: an
  interruption at any point leaves either the previous complete content or
  the new complete content on disk, never a partial file.
- **FR-007**: Evidence validation MUST reject any evidence part with an empty
  summary or an unrecognized class, for both single-part and multi-part
  strings; the documented grammar `<CLASS>:<summary>[; ...]` is the single
  source of truth and MUST be enforced by one validation path (no dead
  alternates).
- **FR-008**: Active-feature fallback resolution MUST order candidate spec
  directories by numeric prefix value, selecting the highest.
- **FR-009**: Business operations (ledger commands, reconcile, consistency)
  MUST report failures as structured errors carrying the user-facing message;
  only the CLI entry layer maps errors to exit codes and stderr output.
- **FR-010**: All documented exit-code semantics MUST be preserved exactly:
  0 success, 1 blocking failure, 2 unexpected/parse error — verified by the
  existing test suite continuing to pass (adapted only in how it asserts).
- **FR-011**: The codebase MUST be free of the identified dead code: unused
  validation regex, duplicate imports, unused variables/computations, imports
  inside loops, and cross-module usage of private symbols (shared parsing
  helpers get a public home).
- **FR-012**: The project MUST provide automated lint and static type
  checks and test execution with coverage measurement, runnable locally via
  documented command(s), with all current source passing cleanly.
- **FR-013**: A continuous-integration pipeline MUST run the lint, type, and
  test gates on every push and pull request, failing the pipeline when any
  gate fails — including when statement coverage of the source package falls
  below the 85% threshold.
- **FR-014**: All new CLI output (including `status show` and version output)
  MUST be in English, consistent with the existing language policy.

### Key Entities

- **Review Cycle**: one round of review for a feature; carries round number,
  start/completion dates, and result (APPROVED / REJECTED / unset). The DONE
  gate reads it; transitions write it.
- **Ledger (`status.yaml`)**: the per-feature execution state file — phase,
  tasks with statuses and evidence, review cycles, recovery pointers. All
  mutations flow through CLI commands and must be crash-safe.
- **Evidence String**: proof attached to a completed task, in the grammar
  `<CLASS>:<summary>[; <CLASS>:<summary>]` with a fixed class vocabulary and
  mandatory non-empty summaries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A feature can be driven through its entire lifecycle
  (SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE, including an approved
  review) using only CLI commands — zero manual edits of the ledger file.
- **SC-002**: An operator can answer "what phase, which task, how many done"
  for any feature with a single command in under 1 second, without opening
  any file.
- **SC-003**: The installed version is discoverable with a single command in
  under 1 second.
- **SC-004**: Under write interruption at any point, the ledger on disk
  always parses and reflects a complete before-or-after state (0 corrupted
  outcomes across simulated interruption tests).
- **SC-005**: 100% of malformed evidence strings (empty summary, unknown
  class, malformed part in a multi-part string) are rejected at submission.
- **SC-006**: All previously documented CLI exit codes and failure messages
  are preserved: the adapted existing test suite passes with 0 behavioral
  regressions.
- **SC-007**: Every push and pull request automatically receives lint, type,
  and test verdicts; a seeded violation of each kind blocks the pipeline.
- **SC-008**: Statement coverage of the source package is measured on every
  test run; runs below 85% fail the gate, and the threshold is met at
  feature completion.

## Assumptions

- Fixing the result-application order on `transition-phase DONE -r APPROVED`
  (plus recording the result on the open cycle) is sufficient to close the
  approval-flow gap; a separate `record-review` command is **not** introduced.
  The two-command surface (`DONE -r APPROVED` to approve-and-close,
  `IMPLEMENT -r REJECTED` for the corrective round) covers both review
  outcomes. This keeps the CLI surface minimal; a dedicated command can be
  specified later if agents need to record results without transitioning.
- `status show` output is human-readable plain text, stable enough for agents
  to consume; a machine-readable format (e.g. JSON flag) is out of scope for
  this feature.
- Valid result values are exactly APPROVED and REJECTED (case-insensitive on
  input, stored uppercase). Free-text results, which the current help text
  hints at ("APPROVED|REJECTED|note"), are dropped as never-functional.
- Tooling choices follow current Python community defaults: Ruff (lint),
  mypy (types), pytest-cov (coverage), GitHub Actions (CI). These are
  development-time dependencies only; the runtime dependency set
  (Typer, PyYAML, GitPython) is unchanged, per the constitution's
  dependency constraint.
- The coverage threshold is set at 85% statement coverage; Scenario-F-style
  agent-in-the-loop behavior remains out of pytest scope, as documented.
- The internal error-handling refactor is behavior-preserving by definition;
  the existing test suite (adapted to assert on errors instead of process
  exits where applicable) plus the integration tests define "no regression".
- CI tests exactly two Python versions: the supported floor (3.10) and the
  latest stable release.
