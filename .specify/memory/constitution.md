<!--
Sync Impact Report
==================
Version change: 1.1.1 → 1.1.2
Rationale (1.1.2, 2026-07-05): Task transition line generalized from the
legacy `task-XX` scheme to Speckit's own task identifiers
(`<task-id> done (<commit-sha7>), starting <next-task-id>`), resolving the
CHK012 conflict found by the pre-plan checklist. PATCH bump: clarification.

Rationale (1.1.1, 2026-07-05): Provenance rewording — reference scripts and
methodology are now vendored locally under .specs/reference/; all mentions
of the originating external project were removed (the projects are distinct
and must have no link). PATCH bump: wording only.

Rationale (1.1.0, 2026-07-05): Amended during /speckit-specify of
specs/001-specops-cli. (a) English established as the canonical language for
all product artifacts; Portuguese strings translated — `(criar)`/`(alterar)`
→ `(create)`/`(modify)`, task transition line now ends with
`starting task-(XX+1)`. (b) Principle I expanded: `specops init` runs after
Speckit's own init, may offer to initialize Git when absent, installs the
`/specops.review` agent command (renamed from `/speckit.review`), and adjusts
Speckit's existing agent prompts via marker-delimited directive blocks —
additive marked injection is permitted; destructive replacement remains
forbidden. MINOR bump: materially expanded guidance, no principle removed.
Templates: no template changes required by this amendment.

Previous report (1.0.0):
Version change: 1.0.0 (initial draft) → 1.0.0 (re-ratified same day)
Rationale: The initial draft framed the principles as generic agent conduct
rules. It was superseded on the same day, before any dependent artifact
(plan, spec, tasks) consumed it, to center the constitution on the product
identity: SpecOps is a complement installed ON TOP of GitHub Speckit that
brings Speckit the advantages defined in .specs/objective.md. Because no
downstream artifact ever referenced the draft, the version is re-issued as
1.0.0 instead of bumping to 2.0.0.

Modified principles (draft → final):
  - I. Repo-as-State → I. Speckit Extension, Never Replacement (new anchor)
  - II. Atomic, Evidence-Backed Task Completion → III. Automated Evidence
    Collection (product capability framing; dev-side testing discipline
    moved to Development Workflow & Quality Gates)
  - III. Operational Silence, IV. Empirical Verification, V. Stop-and-Ask
    Gates, VI. Token-Optimized Review → merged into IV. Surgical Agent
    Behavior via Injected Prompts (they are advantages SpecOps injects into
    the client's Speckit, not standalone repo rules)
  - VII. Domain Agnosticism → V. Domain Agnosticism
  - (new) VI. Exit Codes as Gates — promoted from Technical Constraints
Added sections: none beyond the above
Removed sections: none

Templates requiring updates:
  - ✅ .specify/templates/tasks-template.md — principle reference updated
    (was "Principle II", now points to Development Workflow & Quality Gates)
  - ✅ .specify/templates/plan-template.md — Constitution Check gate is
    generic; compatible as-is
  - ✅ .specify/templates/spec-template.md — no change needed
  - ✅ .specify/templates/checklist-template.md — no change needed

Follow-up TODOs: none.
-->

# SpecOps Constitution

SpecOps (`specops-cli`) is a complement installed on top of GitHub Speckit.
Its sole mission is to bring to any Speckit repository the advantages of the
agent-guided atomic development methodology defined in `.specs/objective.md`:
Repo-as-State, physical status control, atomic commits with evidence,
operational silence, and token-optimized review. Every principle below
exists to protect that mission.

## Core Principles

### I. Speckit Extension, Never Replacement (NON-NEGOTIABLE)

Every SpecOps capability MUST be delivered as an additive layer over the
Speckit lifecycle (specify → plan → tasks → implement → review). SpecOps
MUST NOT fork, replace, or destructively modify Speckit's files, commands,
or workflow. Integration happens exclusively by detection and injection:
`specops init` runs after Speckit's own initialization, validates that a Git
repository exists (offering to initialize one when absent), detects the
client's Speckit folder, generates `specops.json`, installs the
`/specops.review` agent command and the `status.yaml` ledger scaffold, and
adjusts Speckit's existing agent prompts exclusively through marker-delimited
SpecOps directive blocks that are updated in place on re-runs — never
duplicated, never touching content outside the markers. It MUST leave the
environment fully prepared in a single run. A feature that requires the
client to abandon or patch Speckit itself beyond marked blocks is out of
scope by definition.

**Rationale**: the product's entire value proposition is extending Speckit;
anything that competes with it destroys that proposition.

### II. Physical State Ledger (Repo-as-State)

SpecOps MUST control the physical state of execution inside the repository
through the structured ledger `status.yaml`, manipulated exclusively by CLI
commands (`specops status init-spec | start-task | complete-task |
transition-phase`) — never by hand-editing and never held in agent memory or
chat context. Every commit hash registered in the ledger MUST exist in the
Git tree of the active branch; `specops reconcile` verifies this and MUST
block execution (exit code 1) on any divergence.

**Rationale**: agents hallucinate state; a Git-verifiable ledger is what
makes progress auditable and recovery deterministic — the core advantage
SpecOps adds to Speckit's file-based artifacts.

### III. Automated Evidence Collection

Closing a task MUST NOT depend on agent narration. `specops status
complete-task --auto` MUST orchestrate the collection of technical evidence
mechanically: run the client's `test_command`, harvest commit hashes and the
`CODE_DIFF` via Git, and record the evidence string in `status.yaml` in the
`<CLASS>:<summary>` format (including the `TEST_REPORT`). Evidence is
machine-collected at close time so that review can consume it without
re-deriving context.

**Rationale**: evidence gathered by tooling is trustworthy and cheap;
evidence claimed by an agent is neither.

### IV. Surgical Agent Behavior via Injected Prompts

The behavioral advantages SpecOps brings to Speckit MUST be imposed on
agents through the prompts it installs and the marker-delimited directive
blocks it injects into Speckit's existing prompts (starting with
`/specops.review`), not left to convention. The injected directives are:

- **Operational Silence (§6)**: during `/speckit.implement`, agents act 100%
  silently in chat; on task transition they print exclusively
  `<task-id> done (<commit-sha7>), starting <next-task-id>` (Speckit task
  identifiers, e.g., `T001 done (a1b2c3d), starting T002`) and continue.
- **Empirical Verification (§17.4)**: agents MUST NOT declare paths or code
  conventions in `plan.md` from memory; declared paths carry action suffixes
  (`(create)`, `(modify)`, etc.) and are validated against the worktree by
  `specops consistency`, which also checks that every success criterion of
  the spec is covered by at least one task.
- **Token-Optimized Review (§18)**: the review agent loads the Spec's
  required Skills from the client's skills directory, runs `specops
  reconcile` and aborts immediately on failure, rejects changes outside
  `plan.md` via `git status --porcelain` without reading any code, and emits
  non-conformities to `revisions/revision-X.md` in the short format
  `[File]:[Line] - [rule violated and short action]`.
- **Stop-and-Ask Gates (§8.2)**: agents halt and ask the human on persisted
  schema changes (migrations), secrets, public contract breaks, or technical
  ambiguities.

Any change to these directives MUST be made in the SpecOps templates so all
client repositories receive it on the next `specops init`.

**Rationale**: templates are the delivery vehicle of the methodology; if a
directive lives only in documentation, Speckit users never receive it.

### V. Domain Agnosticism

The CLI MUST remain agnostic to specific technologies, frameworks, and
business rules (no coupling to .NET, CQRS, RLS, or any client linter). All
client-specific behavior enters exclusively through `specops.json`
(`test_command`, `lint_command`, `skills_dir`) at the client repository
root. A feature that cannot be expressed as generic logic plus client
configuration does not belong in SpecOps.

**Rationale**: SpecOps packages a methodology, not a stack; portability to
any Speckit repository is a core requirement.

### VI. Exit Codes as Gates

Every SpecOps validation command (`specops reconcile`, `specops
consistency`) MUST return exit code 0 on success and 1 on blocking failure,
with no interactive prompts, so that any command can serve as a gate inside
injected prompts, CI pipelines, and agent workflows.

**Rationale**: the injected prompts (Principle IV) can only enforce behavior
if the underlying commands are mechanically composable.

## Technical Constraints

- **Packaging**: Python package `specops-cli`, installable via `pip`
  (including `pip install -e .` for development), exposing the `specops`
  entrypoint with functional `--help`.
- **Dependencies**: limited to Typer (CLI), PyYAML (ledger), and GitPython
  (evidence collection). New runtime dependencies require justification in
  the plan's Complexity Tracking section.
- **Structure**: modules live under `src/specops/` (`cli.py`, `status.py`,
  `reconcile.py`, `consistency.py`) with scaffold assets in
  `src/specops/templates/` (`review.md`, `status.yaml`).
- **Provenance**: `status.py`, `reconcile.py`, and `consistency.py` are
  ports of the local reference scripts in `.specs/reference/`
  (`manage-status.py`, `reconcile-status.py`, `scope-tasks-consistency.py`)
  with all domain coupling removed (Principle V). The methodology itself is
  documented locally in `.specs/reference/methodology.md`; SpecOps has no
  dependency on, or reference to, any external project.

## Development Workflow & Quality Gates

Development of SpecOps itself follows the same methodology it packages
(dogfooding), under the Speckit lifecycle:

1. **Plan gate**: `specops consistency` MUST pass before a plan is accepted
   (once available; until then, plans are checked manually against
   Principle IV's Empirical Verification directive).
2. **Task gate**: every task is closed only with passing automated tests and
   evidence recorded in the ledger — no strict TDD required, but no task is
   `DONE` without tests.
3. **Review gate**: `specops reconcile` MUST pass before review begins;
   review follows the token-optimized order of Principle IV.
4. **Human gates**: Stop-and-Ask conditions interrupt any phase at any time.

Every `plan.md` MUST include a Constitution Check section evaluating the
work against these principles; violations MUST be either resolved or
explicitly justified in Complexity Tracking before implementation starts.

## Governance

This constitution supersedes all other practices in this repository. When
guidance conflicts, the constitution wins.

- **Amendments**: any change to this file MUST update the Sync Impact Report
  comment, bump the version, and propagate required changes to the templates
  under `.specify/templates/` — and, when a Principle IV directive changes,
  to the injected templates under `src/specops/templates/` — in the same
  change set.
- **Versioning**: semantic versioning — MAJOR for backward-incompatible
  removals or redefinitions of principles; MINOR for new principles or
  materially expanded guidance; PATCH for clarifications and wording.
- **Compliance review**: all reviews (human or agent) MUST verify compliance
  with the Core Principles; added complexity MUST be justified against a
  rejected simpler alternative.

**Version**: 1.1.2 | **Ratified**: 2026-07-05 | **Last Amended**: 2026-07-05
