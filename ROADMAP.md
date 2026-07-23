# SpecOps Evolution Roadmap

This roadmap defines the sequence of Spec Kit features that evolve SpecOps from
an additive workflow guard into a context-aware, auditable execution layer. It
is a planning index, not an execution ledger. The authoritative execution state
for an active feature remains that feature's `specs/NNN-*/status.yaml`.

## Roadmap Rules

1. Implement one numbered feature at a time, in the order defined below unless
   a dependency review explicitly changes the order.
2. Each feature gets its own branch, Spec Kit artifact directory, review cycle,
   pull request, and release note.
3. Do not place implementation paths in this roadmap. Paths must be discovered
   empirically during `/speckit.plan` and carry SpecOps action suffixes.
4. Keep the CLI deterministic. Agent orchestration belongs to Spec Kit workflow
   primitives; repository state, validation, evidence, and verdict transitions
   belong to SpecOps.
5. New behavior must degrade safely when an optional context map, workflow, or
   integration capability is absent.
6. Preserve offline operation after installation and avoid stack-specific
   behavior in the SpecOps core.
7. Update this roadmap only when a feature is merged, split, reordered, or
   removed. In-progress details belong to the feature artifacts.
8. SpecOps is a **complement** to Spec Kit, never a replacement, and never
   reimplements a capability Spec Kit already ships. Spec Kit already provides a
   resumable workflow engine with native step types (`command`, `shell`,
   `prompt`, `gate`, `if`, `switch`, `while`, `do-while`, `fan-out`, `fan-in`),
   the `specify workflow` lifecycle (`run`, `resume`, `status`, `add`, `remove`,
   `catalog`, `step`, …), `specify check`, and the extension/integration/preset
   systems. Any feature that needs orchestration, a human gate, a loop, resume,
   or a status/diagnostic surface MUST compose or extend those primitives and add
   only the deterministic ledger, validation, evidence, reconciliation, and
   verdict layer that Spec Kit lacks — plus workflow *definitions* and CLI
   outcome contracts that plug into the native engine.

## Tracking Model

Roadmap status uses four values:

- `PLANNED`: brief approved, feature artifacts not created.
- `ACTIVE`: feature directory and ledger created; consult its `status.yaml`.
- `MERGED`: reviewed, approved, and merged.
- `SUPERSEDED`: replaced by another numbered feature with an explicit reason.

| ID | Feature | Status | Depends on | Milestone |
|---|---|---|---|---|
| 005 | Native Spec Kit Extension | MERGED | — | Foundation |
| 006 | Ledger v2 Integrity | MERGED | 005 | Foundation |
| 007 | Native Workflow Orchestration | MERGED | 005, 006 | Foundation |
| 008 | Context Map Core | MERGED | 005, 006 | Context Intelligence |
| 009 | Context-Aware Planning and Impact | MERGED | 008 | Context Intelligence |
| 010 | End-to-End Traceability | MERGED | 006, 009 | Auditability |
| 011 | Structured Corrective Handoff | ACTIVE | 006, 010 | Auditability |
| 012 | Gate Profiles and Structured Evidence | PLANNED | 006, 008, 010 | Auditability |
| 013 | Lightweight Workflow Lane | PLANNED | 007, 011, 012 | Adoption |
| 014 | Diagnostics and Machine Reports | PLANNED | 005–013 | Adoption |

## Standard Spec Kit Execution Protocol

This protocol has **two distinct layers**; do not conflate them.

- **Development protocol (how the SpecOps team builds each feature)**: we build
  SpecOps using **plain Spec Kit artifacts only**. We do **not** run SpecOps
  against the SpecOps repository, do not create a SpecOps ledger or `status.yaml`
  here, and do not run `specops` gates on our own commits. Our dev loop is:
  `/speckit.specify → /speckit.clarify → /speckit.checklist → /speckit.plan →
  human approval → /speckit.tasks → /speckit.analyze → /speckit.implement`,
  followed by ordinary PR review and the repository quality gates
  (ruff, mypy, pytest). See the "No Self-Application" constraint.
- **Delivered capability (what each feature must give end users)**: the SpecOps
  command behavior described per feature (ledger creation, `specops consistency`,
  `specops reconcile`, `specops review`, the workflow definition, etc.) is what
  the feature ships to adopters. It is proven by that feature's own automated
  tests against fixtures and sample repositories — never by dogfooding on this
  repository.

Apply the steps below with that separation in mind: the `/speckit.*` steps are
our real dev process; every `specops *` behavior is a delivered capability we
build and test, not a gate we run on this repo.

### 1. Start

- Begin from an up-to-date default branch with a clean working tree.
- Create a branch using the repository's numbered feature convention.
- Change the roadmap row from `PLANNED` to `ACTIVE` only in the feature's first
  planning commit.
- Run `/speckit.specify` with the feature brief recorded below.

### 2. Requirements quality

- Run `/speckit.clarify`; no unresolved high-impact ambiguity may reach planning.
- Run `/speckit.checklist` for requirements completeness, testability, failure
  semantics, upgrade behavior, and backward compatibility.
- Keep success criteria observable and independent of implementation choices.

### 3. Planning readiness gate

- Run `/speckit.plan` and verify every path and convention against the current
  repository before declaring it.
- Record migration, compatibility, security, and rollback decisions explicitly.
- Ensure the feature *delivers* a working `specops consistency` for end users,
  covered by the feature's tests — do not run it against this repository.
- Obtain explicit human approval of `spec.md` and `plan.md` before generating
  tasks or implementing code.

### 4. Tasks and analysis

- Run `/speckit.tasks`; every task must carry one or more `[SC-xxx]` tags.
- Run `/speckit.analyze` and resolve all critical cross-artifact findings.
- Track our own development state with plain Spec Kit artifacts (`spec.md`,
  `plan.md`, `tasks.md`). The SpecOps ledger and `status.yaml` are a **delivered
  capability** exercised in the feature's tests, not created for this repository.

### 5. Implementation and review

- Run `/speckit.implement` to build the feature, using the configured commit
  granularity.
- Run all feature-specific tests plus the repository quality gates.
- The deterministic SpecOps review gates, ledger review cycles, and versioned
  corrective handoffs are **delivered capabilities** the feature must implement
  and cover with tests; our own change is reviewed through ordinary PR review,
  not by running `specops review` on this repository.

### 6. Completion

- Merge only after `APPROVED` and after documentation, changelog, migrations,
  and compatibility notes are complete.
- Change the roadmap row from `ACTIVE` to `MERGED` in the completion change.
- Record any newly discovered follow-up as a new numbered feature or as an
  explicit amendment to a future feature; do not silently expand scope.

## Global Definition of Done

Every feature must satisfy all applicable items:

- All success criteria have task coverage and objective evidence.
- The delivered SpecOps commands (`specops consistency`, `specops reconcile`,
  `specops review`, and any new surfaces) pass in the feature's own tests against
  fixtures/sample repositories — not by running them against this repository.
- No capability reimplements something Spec Kit already provides (Rule 8); any
  orchestration, gate, loop, resume, or status surface composes native Spec Kit
  primitives.
- Ruff, mypy, and the complete pytest suite pass at the repository thresholds.
- New CLI surfaces have unit, integration, error-path, and idempotency coverage.
- Persisted formats are versioned and have forward migration tests.
- Read-only commands do not mutate repository or ledger state.
- State-changing commands are atomic, interruption-safe, and fail closed on
  ambiguous repository identity.
- Human-readable output remains concise; automation surfaces have stable JSON.
- English and Portuguese documentation remain behaviorally equivalent.
- The changelog records user-visible behavior and migration requirements.
- No capability requires a particular programming language or application
  architecture unless provided by a documented adapter.

## Feature 005 — Native Spec Kit Extension

### Objective

Deliver SpecOps through native Spec Kit extension and hook mechanisms while
retaining the Python CLI as the deterministic engine and preserving a documented
legacy initialization path.

### Required outcomes

- Install, update, disable, enable, and remove SpecOps through native extension
  lifecycle commands.
- Register lifecycle hooks without modifying integration-managed prompt files.
- Support every compatible installed integration through Spec Kit's own command
  registration mechanism.
- Detect supported and legacy installations and provide a non-destructive
  migration path.
- Preserve offline use after the extension and CLI artifacts are installed.
- Make repeated installation and migration idempotent.

### Explicit non-goals

- No ledger schema redesign.
- No context map.
- No autonomous agent dispatch.
- No removal of the legacy initialization path until a later major release.

### Acceptance gate

A clean Spec Kit repository can install, use, update, and remove SpecOps without
leaving modified integration-managed files, while a legacy repository can
migrate without losing configuration or feature ledgers.

### `/speckit.specify` brief

> Package SpecOps as a native Spec Kit extension with lifecycle hooks,
> integration-neutral command registration, idempotent install/update/remove,
> and a safe migration path from marker-injected legacy installations. Keep the
> Python CLI as the deterministic execution engine and preserve offline use.

## Feature 006 — Ledger v2 Integrity

### Objective

Version and harden the execution ledger so it remains correct under upgrades,
interruptions, branch changes, and competing sessions.

### Required outcomes

- Add an explicit ledger schema version and deterministic migrations.
- Use timezone-aware timestamps with stable serialization.
- Reject state-changing operations when feature, branch, baseline, or active
  workspace identity is inconsistent.
- Add locking or compare-and-swap semantics to prevent lost updates.
- Formalize invariants for phases, tasks, recovery, and review cycles.
- Add active artifact, workflow lane, and ledger revision metadata.
- Preserve read compatibility with supported v1 ledgers.

### Explicit non-goals

- Evidence remains compatible with its current representation until Feature 012.
- No new agent orchestration.
- No context routing.

### Acceptance gate

Migration tests cover every supported prior ledger shape; concurrent or stale
writes fail without data loss; interrupted atomic writes leave the previous
valid ledger readable.

### `/speckit.specify` brief

> Introduce a versioned Ledger v2 with migrations, timezone-aware timestamps,
> workspace identity validation, concurrency protection, explicit invariants,
> and richer recovery metadata. Preserve supported v1 ledgers and guarantee
> atomic, interruption-safe state changes.

## Feature 007 — Native Workflow Orchestration

### Objective

Ship an installable **workflow definition** that composes Spec Kit's native
workflow engine to run the SpecOps-augmented lifecycle, plus the ledger
reconciliation and CLI outcome contract that keep SpecOps's deterministic state
authoritative. SpecOps builds **no** orchestrator: Spec Kit already provides the
resumable engine, human gate, bounded loop, and branching (Rule 8).

### Required outcomes

- Deliver a workflow *definition* that composes Spec Kit native steps
  (`command`, `shell`, `gate`, `do-while`, `if`/`switch`) to run specify,
  clarify, checklist, plan, tasks, analyze, implement, and review, interleaving
  the deterministic SpecOps gates at the right points.
- Position the human readiness gate between planning and task generation using
  Spec Kit's native `gate` step — not a SpecOps-built gate.
- Model rejection and corrective review as Spec Kit's native `do-while` loop,
  bounded by its `max_iterations`, conditioned on the SpecOps review outcome.
- Provide ledger reconciliation that aligns the SpecOps ledger with the actual
  repository/workflow state between steps and after a Spec Kit `workflow resume`;
  fail closed on irreconcilable divergence.
- Provide a stable CLI outcome contract (exit codes / signals) so native gate/
  loop/branch steps can distinguish gate rejection, execution failure, and
  infrastructure error.
- Avoid a separate integration-specific agent command dispatcher in SpecOps, and
  avoid reimplementing the engine, resume, gate, or loop.

### Explicit non-goals

- No SpecOps-built workflow engine, resume mechanism, human gate, loop, or
  branching primitive — all are Spec Kit's.
- No lightweight lane.
- No context map.
- No parallel multi-agent fan-out until state ownership is proven safe.

### Acceptance gate

Running the shipped definition under Spec Kit's engine can pause, resume (via
`specify workflow resume`), reject, correct, approve, and recover after
interruption, while SpecOps reconciliation keeps the ledger authoritative and
never lets it diverge silently — and no orchestration primitive is implemented
inside SpecOps.

### `/speckit.specify` brief

> Ship a SpecOps lifecycle workflow *definition* that composes Spec Kit's native
> engine (command/shell/gate/do-while/if) to run the augmented lifecycle with
> deterministic SpecOps gates interleaved, plus ledger reconciliation and a
> stable CLI outcome contract that keep the ledger authoritative. Build no
> engine, resume, gate, or loop inside SpecOps, and no separate agent-dispatch
> abstraction — compose Spec Kit's primitives.

## Feature 008 — Context Map Core

### Objective

Introduce a generic, versioned context map that describes repository contexts,
ownership, phase-specific reading sets, dependencies, gates, and risk metadata.

### Required outcomes

- Define a stack-neutral schema under the SpecOps namespace in `.specify`.
- Separate context matching, reading guidance, topology, dependencies, gates,
  and policy metadata into independently validated fields.
- Provide `context init`, `context validate`, `context resolve`, and
  `context explain` commands.
- Resolve contexts from explicit IDs and repository paths deterministically.
- Detect invalid paths, duplicates, ambiguous ownership, dependency cycles,
  unsafe path traversal, and unsupported schema versions.
- Treat a missing context map as a supported, explicitly reported state.
- Provide stable JSON output for every read-only context command.

### Explicit non-goals

- No semantic source-code dependency parser in the core.
- No automatic edits based on agent inference.
- No planning or review integration until Feature 009.

### Acceptance gate

The same map and inputs always produce the same ordered context package and
reason trace; invalid or ambiguous maps fail before any workflow state changes.

### `/speckit.specify` brief

> Add a generic, versioned SpecOps context map with deterministic path and ID
> resolution, phase-specific read sets, ownership, dependencies, gates, and risk
> metadata. Provide init, validate, resolve, explain, and JSON interfaces while
> keeping the core stack-neutral and safe when no map exists.

## Feature 009 — Context-Aware Planning and Impact

### Objective

Use the context map to minimize agent reads, verify planned topology, and expand
review scope only when declared dependencies justify it.

### Required outcomes

- Resolve and display the minimum context package at each lifecycle phase.
- Require plans to declare context IDs when a map is present.
- Validate planned paths against context ownership without assuming ownership is
  an exclusive write-permission boundary.
- Add `context impact` for changed paths, directly affected contexts, declared
  dependents, contracts, tests, gates, and risks.
- Store the resolved context IDs and map digest in task/review ledger records.
- Detect moved or removed paths that leave the context map stale.
- Make every expanded review file explainable by a dependency or policy edge.

### Explicit non-goals

- No language-specific graph engine in the core.
- No hard rejection solely because a file was not predicted during planning.
- No scope-drift acknowledgement model until Feature 010.

### Acceptance gate

Planning and review produce deterministic, reasoned read scopes; topology drift
is detected; dependency expansion never degenerates into an unexplained
repository-wide read.

### `/speckit.specify` brief

> Integrate the SpecOps context map into planning, implementation, and review.
> Resolve minimal phase-specific reads, validate declared topology, calculate
> explainable impact through declared dependencies, snapshot context provenance
> in the ledger, and detect stale map entries after moves or removals.

## Feature 010 — End-to-End Traceability

### Objective

Create a deterministic trace from requirements through tasks, planned contexts
and paths, commits, evidence, review findings, and corrective work.

### Required outcomes

- Model trace links from success criteria to tasks, paths/contexts, commits,
  evidence, findings, and corrections.
- Validate missing links, dangling references, and contradictory ownership.
- Classify changed paths as `planned`, `discovered-and-acknowledged`, or
  `unexplained`.
- Allow a discovered path to be acknowledged once with a concise reason and
  task association.
- Block review only for unexplained effective-diff paths, not legitimate
  discoveries.
- Add human-readable and JSON trace reports.

### Explicit non-goals

- No structured corrective authorization rules until Feature 011.
- No test-result artifact redesign until Feature 012.

### Acceptance gate

Every effective-diff path and every completed success criterion has a complete,
machine-checkable trace or an explicit blocking diagnostic.

### `/speckit.specify` brief

> Build deterministic end-to-end traceability from success criteria through
> tasks, contexts and paths, commits, evidence, review findings, and corrections.
> Introduce planned, discovered-and-acknowledged, and unexplained path classes so
> review blocks unexplained drift without rejecting legitimate discoveries.

## Feature 011 — Structured Corrective Handoff

### Objective

Make review findings and correction authorization first-class, versioned state
instead of relying on loosely formatted revision prose.

### Required outcomes

- Give each finding a stable ID, severity, rule, location, and concise action.
- Record authorized corrective paths, expected evidence, and closure criteria.
- Track finding state through `OPEN`, `FIXED`, and `VERIFIED` transitions.
- Link corrections to tasks, commits, evidence, and the originating review cycle.
- Add CLI commands to create, validate, report, and close corrective handoffs.
- Render compatible Markdown revision reports from structured state.
- Prevent approval while blocking findings remain unverified.

### Explicit non-goals

- Review findings do not automatically modify product code.
- No issue-tracker integration.
- No parallel correction ownership.

### Acceptance gate

A rejected review can be resumed by a fresh session using only repository state,
and approval is impossible until all blocking findings have verified evidence.

### `/speckit.specify` brief

> Introduce structured corrective handoffs with stable finding IDs, severity,
> authorized paths, expected evidence, closure criteria, lifecycle states, and
> trace links. Keep Markdown revision reports as a rendered human interface and
> prevent approval while blocking findings remain unverified.

## Feature 012 — Gate Profiles and Structured Evidence

### Objective

Replace single global lint/test commands and opaque evidence strings with
context-aware gate profiles and verifiable evidence records.

### Required outcomes

- Define ordered gate profiles with commands, applicability, timeout, required
  status, and failure semantics.
- Select profiles from explicit configuration, context, risk, and changed paths.
- Store evidence as versioned objects containing producer, command, exit code,
  timestamp, commit range, affected paths, summary, and optional artifact digest.
- Preserve migration from current evidence strings.
- Add stable JSON reports and an optional SARIF adapter for review findings.
- Distinguish required, optional, skipped, cached, failed, and unavailable gates.
- Make cache reuse conditional on command, inputs, context-map digest, and commit.

### Explicit non-goals

- SpecOps does not interpret test-framework-specific result formats in the core.
- No remote artifact storage.
- No overlap with Spec Kit's native `gate` step or capability system: SpecOps
  gate *profiles* are deterministic verification command suites invoked as native
  `shell`/`command` steps that produce evidence — a distinct concept from Spec
  Kit's human `gate` (Rule 8).

### Acceptance gate

Every review verdict identifies exactly which gates ran, why they applied, what
inputs they covered, and which immutable evidence records support the result.

### `/speckit.specify` brief

> Add ordered, context-aware gate profiles and migrate evidence from summary
> strings to versioned records with command, result, timestamp, commit range,
> paths, provenance, and digests. Provide stable JSON reporting, safe caching,
> migration compatibility, and optional SARIF output.

## Feature 013 — Lightweight Workflow Lane

### Objective

Provide a proportional workflow for small, reversible changes without weakening
the safety gates required for high-impact work.

### Required outcomes

- Define explicit eligibility and promotion criteria for the lightweight lane.
- Use branch history as the minimal execution state until closure.
- Require stop-and-ask gates for persistence, security, public contracts,
  dependency changes, destructive actions, and ambiguous root cause.
- Permit bundling adjacent reversible changes under human supervision.
- Generate a concise retrospective artifact and evidence at closure.
- Promote to the full feature workflow without losing commits or context.
- Integrate with native Spec Kit workflow primitives rather than duplicating a
  separate orchestrator.

### Explicit non-goals

- No automatic classification of a change as lightweight without confirmation.
- No formal independent review cycle inside the lightweight lane.
- No bypass for applicable deterministic gate profiles.
- No SpecOps-built lane orchestrator: the lane is a Spec Kit workflow definition
  (installed via `specify workflow add`) using native `gate`/`prompt` steps for
  the stop-and-ask checkpoints; SpecOps adds only the eligibility/promotion
  logic, retrospective evidence, and ledger state (Rule 8).

### Acceptance gate

A small change can be completed with materially less ceremony, while any risk or
scope expansion that exceeds the lane is detected and promoted without losing
audit history.

### `/speckit.specify` brief

> Add a human-confirmed lightweight workflow lane for small reversible changes,
> with minimal branch-based state, explicit high-risk stop-and-ask gates,
> retrospective closure evidence, and lossless promotion to the full feature
> workflow when risk or scope grows.

## Feature 014 — Diagnostics and Machine Reports

### Objective

Provide one diagnostic surface that explains installation health, workflow
state, ledger integrity, context health, gate readiness, and the next safe action.

### Required outcomes

- Add `specops doctor` and `specops doctor --json`.
- Diagnose CLI/extension compatibility, integration health, legacy installation
  artifacts, configuration, active feature identity, ledger schema, context-map
  validity, workflow/ledger divergence, and gate availability.
- Separate `ok`, `warning`, `blocking`, and `execution-error` findings.
- Recommend deterministic next actions without mutating state.
- Add a compact project/feature status report for humans and automation.
- Guarantee read-only operation and stable machine-readable schemas.

### Explicit non-goals

- No automatic repair in the first version.
- No telemetry transmission.
- No hosted dashboard.
- No re-checking of what `specify check` and `specify workflow status` already
  report; `specops doctor` complements them, adding only SpecOps-specific
  diagnostics (ledger schema, context-map health, workflow/ledger divergence) and
  deferring to the native commands for engine and integration health (Rule 8).

### Acceptance gate

A user or CI job can identify why a workflow cannot safely continue and obtain a
specific next action from a single read-only command.

### `/speckit.specify` brief

> Add a read-only SpecOps doctor and status reporting surface with stable JSON.
> Diagnose extension and integration compatibility, legacy artifacts,
> configuration, feature identity, ledger and context-map health, workflow drift,
> and gate availability, with severity-classified findings and deterministic
> next-action guidance.

## Dependency and Replanning Policy

- A feature may be split when `/speckit.clarify` or `/speckit.plan` proves that
  it cannot remain independently testable or reviewable.
- A split receives the next available feature number; the original row records
  the replacement IDs and becomes `SUPERSEDED` only if no part remains.
- Reordering requires updating dependency columns and documenting the reason in
  the first affected feature's `research.md`.
- New requirements discovered during implementation do not enter the active
  feature unless they are necessary to satisfy an existing success criterion.
- Security or data-integrity defects may interrupt the roadmap through a
  dedicated fix branch, but fixes are never added as roadmap features.

## Release Milestones

### Foundation complete

Features 005–007 are merged. SpecOps installs natively, owns a versioned and
concurrency-safe ledger, and can run the full lifecycle through a resumable
workflow.

### Context Intelligence complete

Features 008–009 are merged. Agents receive deterministic minimal context and
review impact is explainable through repository-owned metadata.

### Auditability complete

Features 010–012 are merged. Requirements, changes, evidence, findings, and
corrections form a verifiable trace backed by context-aware gate profiles.

### Adoption complete

Features 013–014 are merged. Small changes have a proportional safe lane, and a
single diagnostic interface explains project health and next actions.
