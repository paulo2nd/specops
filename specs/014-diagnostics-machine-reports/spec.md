# Feature Specification: Diagnostics and Machine Reports

**Feature Branch**: `014-diagnostics-machine-reports`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "Add a read-only SpecOps doctor and status reporting surface with stable JSON. Diagnose extension and integration compatibility, legacy artifacts, configuration, feature identity, ledger and context-map health, workflow drift, and gate availability, with severity-classified findings and deterministic next-action guidance."

## Overview

Today, when a SpecOps workflow cannot safely continue, the reason is scattered across
several surfaces: the ledger (`status.yaml`), the context map, the installed
extension, the active feature identity, and the preflight gate suite. A user — or a
CI job — has to inspect each surface by hand and infer what is wrong and what to do
next. There is no single read-only command that answers "is this repository healthy,
and if not, why, and what is the next safe action?"

This feature adds that command: **`specops doctor`**. It inspects every
SpecOps-specific surface, classifies what it finds by severity (`ok`, `warning`,
`blocking`, `execution-error`), and recommends a deterministic next action for each
problem — **without mutating any repository or ledger state**. It also adds a compact,
read-only **status report** of the active project/feature for humans and automation.

`specops doctor` is a **complement**, not a replacement, for Spec Kit's own
diagnostics. Spec Kit already ships `specify check` (engine/integration health) and
`specify workflow status` (workflow execution state). SpecOps does not re-check what
those already report; `doctor` defers to them for engine and integration health and
adds only the SpecOps-specific diagnostics they cannot know about: ledger schema
integrity, context-map health, workflow/ledger divergence, active-feature identity,
legacy installation artifacts, and gate (preflight profile) availability.

Consistent with SpecOps's design philosophy, `doctor` **records and reports** the
health of the repository; it does not judge whether a recorded deviation was a good
idea (that is the team's governance). It surfaces the facts and the next safe action;
the human decides.

## Clarifications

### Session 2026-07-25

- Q: How should each finding's "next action" be represented in the machine-readable output? → A: **Both** — a stable machine-actionable `next_action_code` (a documented enum) **and** human-readable next-action text per finding. Automation branches on the code; the text is for humans. The code set is versioned with the output schema.
- Q: What ledger/feature scope does `specops doctor` inspect? → A: **Active feature only** — the feature `.specify/feature.json` points to. Other `specs/NNN-*/status.yaml` ledgers are not inspected; whole-repo auditing is out of scope for this feature.
- Q: How does `doctor` determine preflight gate availability? → A: **Read-only PATH probe** — resolve each configured profile command on PATH (locate it; never execute it) in addition to validating the profile configuration. An unresolvable command is reported as a gate-availability `warning`. Probing is side-effect-free and does not run the gate.
- Q: What severity should "no active SpecOps feature" carry? → A: **`ok` / informational** — a valid resting state (consistent with the missing-context-map treatment in FR-009); the overall verdict stays `ok` and the exit code is success. The next-action text still explains how to start or select a feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnose why a workflow cannot safely continue (Priority: P1)

A user (or a fresh agent session resuming a feature) runs a single read-only command
and learns, in one place, everything SpecOps knows about the repository's health: is
the extension installed and compatible, is there an active feature, is its ledger at a
readable schema version and internally consistent, does the ledger agree with the
actual Git tree and workflow state, is the context map valid, and are the preflight
gate profiles available to run. Each problem is classified by severity and paired with
a specific, deterministic next action. The user does not have to inspect five separate
surfaces to understand what is blocking them.

**Why this priority**: This is the feature's core value — a single diagnostic surface
that turns a scattered, expert-only investigation into one command any user or CI job
can run. Without it, none of the other stories matter.

**Independent Test**: Point the command at a repository with a known-broken surface
(e.g., a ledger at an unsupported schema version, or a ledger commit hash absent from
the Git tree) and confirm the command reports exactly one `blocking` finding naming
that surface, a correct next action, and a non-`ok` overall verdict — while leaving the
repository byte-for-byte unchanged.

**Acceptance Scenarios**:

1. **Given** a healthy repository with a valid active feature, ledger, and context
   map, **When** the user runs the diagnostic command, **Then** every diagnostic
   domain reports `ok`, the overall verdict is `ok`, and the command exits successfully.
2. **Given** a repository whose active feature ledger references a commit hash that
   does not exist in the active branch's Git tree, **When** the user runs the
   diagnostic command, **Then** the workflow/ledger-divergence domain reports a
   `blocking` finding that names the missing commit and recommends a deterministic next
   action, and the overall verdict is `blocking`.
3. **Given** a repository with no SpecOps active feature at all, **When** the user runs
   the diagnostic command, **Then** the command reports this as an explicitly-named,
   supported `ok`/informational state (not a crash, not a `warning`), the overall verdict
   remains `ok`, and a next action explains how to start or select a feature.
4. **Given** any repository state, **When** the diagnostic command completes, **Then**
   the repository, ledger, and context map are byte-for-byte identical to before the
   command ran.

---

### User Story 2 - Stable machine-readable diagnostics for CI (Priority: P1)

A CI job runs the diagnostic command with a machine-readable output flag and gets a
stable, versioned document describing every diagnostic domain, each finding's severity
and next action, and an overall verdict. The job branches on the process exit code:
proceed when the verdict is `ok` (or only `warning`), fail the pipeline when a
`blocking` finding is present, and distinguish that from an `execution-error` (the
diagnostic itself could not run) so an infrastructure failure is never mistaken for a
clean repository.

**Why this priority**: The auditability/enterprise thesis depends on CI being able to
gate on SpecOps health deterministically. A human-only report cannot do that. This
story is what makes `doctor` usable as an automated safety check.

**Independent Test**: Run the command with the machine-readable flag against fixtures
in each overall verdict class and confirm the emitted document validates against the
published schema, is byte-identical across repeated runs on unchanged inputs, and that
the process exit code maps deterministically to the overall verdict.

**Acceptance Scenarios**:

1. **Given** a healthy repository, **When** the command runs with the machine-readable
   flag, **Then** it emits a schema-valid document with overall verdict `ok` and an
   exit code reserved for success.
2. **Given** a repository with at least one `blocking` finding, **When** the command
   runs with the machine-readable flag, **Then** the overall verdict is `blocking` and
   the exit code is distinct from both the success code and the execution-error code.
3. **Given** the diagnostic cannot complete because a required input cannot be read
   (e.g., an unreadable ledger file), **When** the command runs with the
   machine-readable flag, **Then** the overall verdict is `execution-error`, the exit
   code is the one reserved for execution errors, and no domain is silently reported as
   `ok`.
4. **Given** the same repository state, **When** the command is run twice with the
   machine-readable flag, **Then** the two documents are byte-identical (deterministic,
   stable ordering, no wall-clock or environment noise in the payload).

---

### User Story 3 - Compact project/feature status report (Priority: P2)

A user wants a quick, read-only summary of where the active feature stands — its
identity, current phase, task progress, review/handoff state, and workflow lane —
without running any state-changing ledger command and without wading through the full
diagnostic output. The same summary is available in a stable machine-readable form for
automation and status dashboards.

**Why this priority**: Valuable and frequently wanted, but secondary to the diagnostic:
a status summary answers "where am I?" while the diagnostic answers the more urgent
"why can't I safely continue?" It reuses much of the same read layer, so it is cheap to
add once Story 1 exists.

**Independent Test**: Run the status report against a repository mid-feature and
confirm it reports the correct feature identity, phase, and progress counts read
directly from the ledger, in both human and machine-readable form, without mutating the
ledger.

**Acceptance Scenarios**:

1. **Given** a repository with an active feature partway through its tasks, **When** the
   user runs the status report, **Then** it shows the feature identity, current phase,
   completed-vs-total task counts, and review/handoff state read from the ledger.
2. **Given** the same repository, **When** the user runs the status report with the
   machine-readable flag, **Then** it emits a schema-valid, deterministic document
   carrying the same facts.
3. **Given** any repository, **When** the status report runs, **Then** it mutates no
   repository or ledger state.

---

### Edge Cases

- **No SpecOps installed / not a Spec Kit repository**: reported as an explicit,
  named state with guidance, never a stack trace or an unhandled error.
- **Legacy (marker-injected) installation present**: detected and reported as a
  `warning` with a next action pointing at the documented migration path (Feature 005),
  not silently ignored.
- **Extension present but incompatible version** (CLI/extension or integration version
  mismatch): reported as `blocking` or `warning` per the mismatch, deferring to
  `specify check` for the underlying engine/integration health rather than re-deriving
  it.
- **Ledger at an unsupported (too-new or unrecognized) schema version**: reported as
  `blocking` — the diagnostic must not attempt to read a schema it does not understand
  as if it were healthy.
- **Ledger references a commit absent from the active branch** (Principle II
  divergence): reported as `blocking` in the workflow/ledger-divergence domain.
- **Context map absent**: reported as a supported `ok`/informational state (a missing
  map is legitimate, per Feature 008), never as an error.
- **Context map present but invalid** (bad schema version, dependency cycle, duplicate
  or ambiguous ownership, unsafe path traversal): reported as `blocking`/`warning`
  reusing the Feature 008 validation classes, without re-implementing that validation.
- **Preflight gate profile references an unavailable command** (a configured tool is
  not on PATH): reported as a `warning` about gate availability, so the user learns
  before a preflight run fails mid-gate.
- **Multiple problems at once**: every finding is reported; the overall verdict is the
  most severe finding present, and the command never stops at the first problem.
- **Ambiguous repository/feature identity** (e.g., the active-feature pointer and the
  branch disagree): reported as `blocking`; the diagnostic fails closed on identity
  ambiguity rather than guessing which feature is active.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SpecOps MUST provide a read-only diagnostic command that inspects all
  SpecOps-specific surfaces and produces a single consolidated result. The command
  MUST NOT mutate any repository, ledger, context-map, or configuration state under any
  input.
- **FR-002**: The diagnostic MUST classify every finding into exactly one of four
  severities: `ok`, `warning`, `blocking`, `execution-error`.
- **FR-003**: The diagnostic MUST inspect, at minimum, these domains and report a
  per-domain result: (a) environment readiness — the working directory is a Git
  repository and a Spec Kit repository (this domain hosts the "not a Spec Kit repo /
  SpecOps not installed" state); (b) SpecOps CLI/extension presence and version
  compatibility; (c) integration health; (d) legacy (marker-injected) installation
  artifacts; (e) SpecOps configuration validity; (f) active-feature identity;
  (g) ledger schema version and internal integrity; (h) context-map validity;
  (i) workflow/ledger divergence (ledger vs. actual Git tree and workflow state);
  (j) preflight gate (profile) availability.
- **FR-004**: For every non-`ok` finding, the diagnostic MUST provide a deterministic,
  specific next action that tells the user what to do to resolve it, represented as
  **both** a stable machine-actionable `next_action_code` (drawn from a documented,
  versioned enum) and human-readable next-action text. Automation MUST be able to branch
  on the code without parsing the text. Neither the code nor the text MUST depend on
  wall-clock time, environment ordering, or non-deterministic input.
- **FR-005**: The diagnostic MUST compute an overall verdict equal to the most severe
  finding present across all domains, using the ordering
  `ok` < `warning` < `blocking` < `execution-error`.
- **FR-006**: The diagnostic MUST offer a machine-readable output mode that emits a
  versioned, schema-stable document containing every domain result, each finding's
  severity, message, and next action, and the overall verdict.
- **FR-007**: The machine-readable output MUST be deterministic: identical repository
  state MUST produce byte-identical output across repeated runs (stable key ordering,
  no embedded wall-clock timestamps or environment-specific noise in the payload).
- **FR-008**: The command's process exit code MUST map deterministically to the overall
  verdict so it can gate a CI pipeline: a success code when the verdict is `ok` or
  `warning`, a distinct blocking code when a `blocking` finding is present, and a
  distinct execution-error code when the diagnostic itself could not complete. The exit
  codes MUST be consistent with the SpecOps CLI outcome contract established for the
  workflow (Feature 007) and the gate semantics of Principle VI.
- **FR-009**: The diagnostic MUST treat a missing context map as a supported,
  explicitly-reported state (no worse than `ok`/informational), never as an error
  (Feature 008 compatibility).
- **FR-010**: The diagnostic MUST treat "no active SpecOps feature" as a supported,
  explicitly-named `ok`/informational state (consistent with the missing-context-map
  treatment in FR-009) — never a `warning`, error, or crash — with a next action
  explaining how to start or select a feature. The overall verdict is unaffected.
- **FR-011**: The diagnostic MUST NOT re-check what Spec Kit's native `specify check`
  and `specify workflow status` already report. For engine and integration health it
  MUST defer to those native commands and report only the SpecOps-specific delta.
- **FR-012**: The diagnostic MUST fail closed on ambiguous repository or active-feature
  identity, reporting a `blocking` finding rather than guessing which feature is active.
- **FR-012a**: The diagnostic MUST scope its ledger, feature-identity, and
  workflow/ledger-divergence inspection to the **active feature only** (the one
  identified by `.specify/feature.json`). It MUST NOT inspect other features'
  `specs/NNN-*/status.yaml` ledgers; whole-repository, all-feature auditing is out of
  scope for this feature.
- **FR-013**: The diagnostic MUST report every finding it discovers in a single run; it
  MUST NOT stop at the first problem, so a user sees the full health picture at once.
- **FR-014**: SpecOps MUST provide a compact, read-only status report of the active
  project/feature — identity, current phase, task progress, review/handoff state, and
  workflow lane — in both a concise human-readable form and a stable machine-readable
  form. This report MUST mutate no state.
- **FR-015**: When a domain cannot be evaluated because a required input is unreadable
  or malformed, that domain MUST be reported with an `execution-error` (or `blocking`,
  as appropriate) finding — never silently reported as `ok` or omitted.
- **FR-015a**: The gate-availability domain MUST determine availability by resolving each
  configured preflight profile command on the executable search path (PATH) — a
  read-only lookup that locates the command but MUST NOT execute it — in addition to
  validating the profile configuration. A command that cannot be resolved MUST be
  reported as a gate-availability `warning`. This probe MUST remain side-effect-free and
  MUST NOT run any gate.
- **FR-016**: The diagnostic and status commands MUST produce behaviorally equivalent
  results and guidance regardless of the human language of the documentation (EN/PT
  parity); user-visible strings MUST be documented in both languages.
- **FR-017**: The diagnostic MUST NOT perform any automatic repair, MUST NOT transmit
  any telemetry, and MUST NOT require network access; it operates fully offline against
  local repository state.
- **FR-018**: The machine-readable output document MUST carry an explicit schema/version
  identifier so consumers can detect and adapt to format changes over time.

### Key Entities

- **Diagnostic Report**: The consolidated result of one `doctor` run. Carries a schema
  version, an ordered set of domain results, and an overall verdict. Read-only; a
  snapshot, never persisted as authoritative state.
- **Diagnostic Domain**: One inspected surface (e.g., ledger schema, context-map health,
  workflow/ledger divergence, gate availability). Has an identifier and one or more
  findings.
- **Finding**: A single diagnosed fact. Carries a severity (`ok` / `warning` /
  `blocking` / `execution-error`), a human-readable message, and — when not `ok` — a
  deterministic next action expressed as both a stable `next_action_code` (versioned
  enum) and human-readable text.
- **Overall Verdict**: The most severe severity present across all findings; drives the
  process exit code.
- **Status Report**: A compact read-only summary of the active feature — identity,
  phase, task progress, review/handoff state, workflow lane — in human and
  machine-readable forms.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user or CI job can determine why a workflow cannot safely continue, and
  obtain a specific next action, from a single read-only command invocation — with no
  additional commands required to understand the blocking cause.
- **SC-002**: The diagnostic inspects 100% of the listed domains (environment readiness,
  CLI/extension compatibility, integration health, legacy artifacts, configuration,
  feature identity, ledger schema, context-map health, workflow/ledger divergence, gate
  availability) in every run and reports a result for each.
- **SC-003**: Running the diagnostic or status command leaves the repository, ledger,
  and context map byte-for-byte unchanged in 100% of runs across all fixtures.
- **SC-004**: For every fixture with a known-broken surface, the overall verdict and the
  process exit code match the expected severity class, and the three classes (success,
  blocking, execution-error) are mutually distinguishable by exit code alone.
- **SC-005**: The machine-readable output is byte-identical across repeated runs on
  unchanged inputs in 100% of cases, and validates against the published schema.
- **SC-006**: Every non-`ok` finding in the test corpus carries a deterministic next
  action; no finding above `ok` is emitted without one.
- **SC-007**: The diagnostic reports every simultaneously-present problem in a single
  run (a multi-problem fixture yields all expected findings, not just the first).
- **SC-008**: EN and PT documentation of the diagnostic and status output are
  behaviorally equivalent (same domains, severities, and next actions).

## Assumptions

- **Diagnostic command name**: The diagnostic surface is delivered as `specops doctor`
  (with a machine-readable flag), per the roadmap brief. The compact status report is a
  distinct read-only surface; its exact command name is left to planning, but it MUST NOT
  collide with or overload the existing state-changing `specops status` verb group
  (`init-spec` / `start-task` / `complete-task` / `transition-phase`).
- **Exit-code mapping**: The default mapping is success (`ok`/`warning`) → success code;
  `blocking` present → the blocking exit code; diagnostic could not run →
  execution-error exit code. The precise numeric values reuse the Feature 007 CLI
  outcome contract and Principle VI conventions rather than inventing new ones. A
  `warning` does not fail CI by default; teams that want to gate on warnings can inspect
  the machine-readable verdict.
- **Vocabulary**: The deterministic gate suite is referred to as **preflight**
  (Feature 017 rename), and gate-availability diagnostics report on preflight profiles.
- **Deference to native commands**: `specify check` and `specify workflow status` are
  assumed available for engine/integration/workflow-execution health; `doctor` layers
  the SpecOps-specific delta on top and does not duplicate them (Rule 8).
- **Read-only guarantees**: The diagnostic reuses the existing read paths for the
  ledger (Feature 006), context map (Feature 008/009), traceability (Feature 010),
  handoff (Feature 011), and gate profiles (Feature 012); it introduces no new persisted
  format beyond its own versioned output document.
- **Offline**: All diagnostics operate on local repository state; no network calls,
  telemetry, or hosted dashboard are in scope (explicit roadmap non-goals).
- **No auto-repair**: This first version diagnoses and recommends; it never mutates or
  repairs. Automatic repair is out of scope.
