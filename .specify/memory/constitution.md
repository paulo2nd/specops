<!--
Sync Impact Report
==================
Version change: 1.7.0 → 1.8.0
Rationale (1.8.0, 2026-07-23): Amended during /speckit-implement of
specs/012-gate-profiles-evidence (Gate Profiles and Structured Evidence). Feature
012 replaces the single global lint/test commands with an ordered, context-aware
gate-profile suite executed inside `specops review` (reconcile → [suite] →
working-tree → drift), and the flat `<CLASS>:<summary>` evidence string with
versioned, id-addressable structured evidence records (Ledger v5→v6). Two existing
Principle III/IV directives are broadened (no principle removed or redefined):
Automated Evidence Collection now also records a structured evidence record (a
cache-key-derived id + producer/command/exit-code/timestamp/commit-range/paths/
summary/optional-local-digest) alongside the retained `<CLASS>:<summary>` string;
Token-Optimized Review now runs the selected gate-profile suite (in place of the
fixed lint/test gates), each gate carrying an outcome-taxonomy disposition
(required|optional|skipped|cached|failed|unavailable) and — in `--json` — its
disposition, reason, covered inputs, and supporting evidence id, with the read-only
`specops gate list/validate/report` inspection surface. `specops review` stays
byte-for-byte read-only. MINOR bump: additive guidance on non-removed principles;
the additive/never-destructive intent is preserved. Templates updated in the same
change set: src/specops/templates/directives/implement.md (structured evidence on
complete-task / finding fix), src/specops/templates/review.md (profile suite +
verdict provenance). The delivered CLI (`gate list/validate/report`, `review`
profile suite + `--sarif`) and the Ledger v5→v6 evidence migration are covered by
the feature's own tests, never run against this repository (No Self-Application).

Previous report (1.7.0):
Version change: 1.6.0 → 1.7.0
Rationale (1.7.0, 2026-07-23): Amended during /speckit-implement of
specs/011-structured-corrective-handoff (Structured Corrective Handoff). Feature
011 promotes review findings and correction authorization from free-form
`revisions/revision-X.md` prose to first-class, versioned ledger state (Ledger
v4→v5): structured findings with stable `R<round>-F<NN>` ids, blocking/advisory
severity, per-finding expected evidence + closure criteria, and an
`OPEN→FIXED→VERIFIED` lifecycle, plus a feature-global blocking-approval invariant
(approval is impossible while any blocking finding is unverified). Two existing
Principle IV directives are broadened (no principle removed or redefined):
Token-Optimized Review now authors structured findings via `specops handoff
finding add`, verifies/closes them (`handoff finding verify`/`handoff close`), and
`revisions/revision-X.md` becomes a rendered projection (`handoff render`) in the
compatible `[File]:[Line] - [action]` format; Ledger & Phase Wiring notes that a
corrective round marks a finding `FIXED` via `specops handoff finding fix`. The
delivered CLI (`handoff finding add/fix/verify`, `authorize`, `close`, `validate`,
`report`, `import`, `render`) and the Ledger v4→v5 migration are covered by the
feature's own tests, never run against this repository (No Self-Application). MINOR
bump: additive guidance on non-removed principles; the additive/never-destructive
intent is preserved. Templates updated in the same change set:
src/specops/templates/review.md (structured findings + verify/close/render),
src/specops/templates/directives/implement.md (mark a resolved finding FIXED). The
generic plan/spec/tasks templates under .specify/templates/ remain compatible and
need no change.

Previous report (1.6.0):
Version change: 1.5.0 → 1.6.0
Rationale (1.6.0, 2026-07-21): Amended during /speckit-implement of
specs/010-end-to-end-traceability (End-to-End Traceability). Feature 010 makes
review block **unexplained** effective-diff drift and lets implementation
acknowledge genuine discoveries, both governed by the Principle IV injected
directives. Two existing directives are broadened (no principle removed or
redefined): Token-Optimized Review now also runs a deterministic `drift` gate
inside `specops review` (the review agent rejects when any effective-diff path is
neither planned nor `discovered-and-acknowledged`; SpecOps/Speckit-managed
artifacts under `specs/**`, `.specify/**`, `specops.json` are excluded as
methodology state); Stop-and-Ask / Ledger & Phase Wiring now notes that a genuine
discovered path is cleared once with `specops trace acknowledge <path> --task …
--reason …`. Map-*digest* drift stays a non-blocking warning (010 enforces *path*
drift only). The delivered CLI (`trace classify`/`validate`/`report`/`acknowledge`)
and the Ledger v3→v4 acknowledgement migration are covered by the feature's own
tests, never run against this repository (No Self-Application). MINOR bump:
additive guidance on non-removed principles; the additive/never-destructive intent
is preserved. Templates updated in the same change set:
src/specops/templates/directives/implement.md (discovered-path acknowledgement),
src/specops/templates/review.md (drift gate in the deterministic gates). The
generic plan/spec/tasks templates under .specify/templates/ remain compatible and
need no change.

Previous report (1.5.0):
Version change: 1.4.0 → 1.5.0
Rationale (1.5.0, 2026-07-21): Amended during /speckit-implement of
specs/009-context-aware-planning (Context-Aware Planning and Impact). Feature 009
consumes the Feature 008 context map inside the planning, implementation, and
review phases, which are governed by the Principle IV injected directives. Two
existing directives are broadened (no principle removed or redefined): Empirical
Verification now also has agents declare the contexts the work touches and
validate the declared topology with `specops context plan-check` (resolving and
displaying the minimal phase read set); Ledger & Phase Wiring now also snapshots
context provenance (resolved context ids + map digest, or an explicit
`{map: none}`/`{map: invalid}` marker) into task/review ledger records, scopes
review by `specops context impact`, and surfaces a non-blocking map-digest drift
warning. The delivered CLI (`context plan-check`/`impact`/`stale`) and the Ledger
v2→v3 provenance migration are covered by the feature's own tests, never run
against this repository (No Self-Application). MINOR bump: materially expanded
guidance added to a non-removed principle; the additive/never-destructive intent
is preserved. Templates updated in the same change set:
src/specops/templates/directives/plan.md (context declaration + plan-check),
implement.md (automatic provenance note), src/specops/templates/review.md
(impact-scoped review + drift warning). The generic plan/spec/tasks templates
under .specify/templates/ remain compatible and need no change.

Previous report (1.4.0):
Version change: 1.3.0 → 1.4.0
Rationale (1.4.0, 2026-07-19): Amended during /speckit-specify → plan of
specs/005-native-speckit-extension (Native Spec Kit Extension). Feature 005
introduces Spec Kit's native extension mechanism (a SpecOps-owned
.specify/extensions.yml hook manifest + native command registration) as the
PRIMARY integration path, delivering the Principle IV directives with zero
modification of integration-owned files. Principle I's "Integration happens
exclusively by detection and injection … through marker-delimited blocks"
sentence and Principle IV's opening/closing sentences are broadened to name the
native mechanism as primary and marker-delimited injection as the retained
legacy path. Directive CONTENT is unchanged — only the delivery vehicle — so
the injected templates under src/specops/templates/directives/ need no content
change (delivery-mechanism only). The five Principle IV directive bullets are
untouched. Also normalized the review-command spelling to /specops-review (the
integration-separator form). MINOR bump: no principle removed or redefined; the
additive/never-destructive intent is strengthened, and materially expanded
guidance was added to a non-removed principle. Templates requiring updates:
none (plan/spec/tasks templates are generic and remain compatible; directive
content unchanged).

Previous report (1.3.0):
Version change: 1.2.1 → 1.3.0
Rationale (1.3.0, 2026-07-06): Development practice reversal decided by the
maintainer after the 004-review-gates-cli implementation had to remove
self-applied artifacts (commit ca2244b): SpecOps is NO LONGER self-applied
(dogfooded) inside this repository while the tool is being defined. The
Development Workflow & Quality Gates section is rewritten — no specops.json,
ledger, injected directives, or installed review command in this repo;
development state is tracked by plain Speckit artifacts, and specops gate
behavior is validated exclusively through the automated test-suite fixtures.
The plan/review gates no longer require running `specops consistency` /
`specops reconcile` against this repository. Product principles I–VI are
untouched (the injected directives remain product assets for client repos).
MINOR bump per this file's own policy: no principle removed or redefined;
materially rewritten guidance in a non-principle section. Templates updated:
.specify/templates/tasks-template.md (task gate note no longer mentions
ledger-recorded evidence).

Previous report (1.2.1):
Version change: 1.2.0 → 1.2.1
Rationale (1.2.1, 2026-07-05): Factual correction — the PyPI distribution name
`specops-cli` was already taken by an unrelated project, so the package is
published as `speckit-specops` (the `specops` command and `specops` import
package are unchanged). Updated the two package-name references. PATCH bump:
wording/fact only, no principle change. Templates: none.

Version change: 1.1.3 → 1.2.0
Rationale (1.2.0, 2026-07-05): Principle IV expanded with a new directive
category — **Ledger & Phase Wiring**. SpecOps now injects directives into every
phase-bearing Speckit stage (specify, plan, tasks, implement), not only plan and
implement, so the execution ledger is created and the phase state machine is
advanced through the SpecOps CLI at each stage seam (closing the gaps where the
human had to run `status init-spec` and `transition-phase` manually). The review
cycle is opened at implement completion so `/specops-review` has an open cycle to
record into. Injected directives degrade to no-ops where SpecOps is not
initialized. MINOR bump: new directive added under an existing principle; no
principle removed or redefined. Templates requiring updates (delivered by
feature 003-stage-directive-wiring): src/specops/templates/directives/specify.md
(new), tasks.md (new), plan.md (SC-tag rule → pointer), implement.md (phase
transitions added).

Version change: 1.1.2 → 1.1.3
Rationale (1.1.3, 2026-07-05): Commit granularity clarified: the preferred
unit is the user story, not the task. Principle III updated to reflect that
`complete-task --auto` is used for the final task of a user story after a
single US-level commit; intermediate tasks within a user story are closed with
`--evidence` (no commit required). Ledger invariant L1 relaxed: evidence is
required for DONE tasks; non-empty commits[] is no longer required (commits
are validated only when present). PATCH bump: clarification of existing intent.
Templates requiring updates: implement.md directive (updated).

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

SpecOps (`speckit-specops`) is a complement installed on top of GitHub Speckit.
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
or workflow. Integration happens exclusively by detection and registration
through Spec Kit's own extension surfaces — never by forking or destructively
editing Speckit's files. In a single run, SpecOps: runs after Speckit's own
initialization, validates that a Git repository exists (offering to initialize
one when absent), detects the client's Speckit folder, generates
`specops.json`, and registers the `/specops-review` command, its lifecycle
directives, and the `status.yaml` ledger scaffold. The primary delivery path
is Spec Kit's native extension mechanism — a SpecOps-owned
`.specify/extensions.yml` hook manifest plus native command registration —
which modifies no integration-owned file. Marker-delimited directive-block
injection into Speckit's existing agent prompts is retained as a supported
legacy path; when used, blocks are additive, updated in place on re-runs,
never duplicated, and never touch content outside the markers. Both paths MUST
leave the environment fully prepared in a single run. A feature that requires
the client to abandon or patch Speckit itself — beyond SpecOps-owned
registration surfaces and retained marker blocks — is out of scope by
definition.

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
`<CLASS>:<summary>` format (including the `TEST_REPORT`). Since Feature 012
(Ledger v6) SpecOps ALSO records a **structured evidence record** alongside that
string — a cache-key-derived id plus producer, command, exit code, timezone-aware
timestamp, commit range, affected paths, summary, and an optional local-artifact
digest — so evidence is machine-checkable and id-addressable; the legacy string is
retained for compatibility. Evidence is machine-collected at close time so that
review can consume it without re-deriving context. The preferred commit granularity is one commit per user
story (not per task); intermediate tasks within a user story are closed with
`--evidence` (without a commit), and the user story's final task is closed
with `--auto` after a single user-story-level commit.

**Rationale**: evidence gathered by tooling is trustworthy and cheap;
evidence claimed by an agent is neither.

### IV. Surgical Agent Behavior via Injected Prompts

The behavioral advantages SpecOps brings to Speckit MUST be imposed on
agents through the commands and lifecycle directives SpecOps registers via
Spec Kit's native extension mechanism — or, on the retained legacy path, the
marker-delimited directive blocks it injects into Speckit's existing prompts —
starting with `/specops-review`, not left to convention. The directives are
delivered as native lifecycle-hook prompt bodies (or legacy marker blocks),
sourced identically from the SpecOps templates. The directives are:

- **Operational Silence (§6)**: during `/speckit.implement`, agents act 100%
  silently in chat; on task transition they print exclusively
  `<task-id> done (<commit-sha7>), starting <next-task-id>` (Speckit task
  identifiers, e.g., `T001 done (a1b2c3d), starting T002`) and continue.
- **Empirical Verification (§17.4)**: agents MUST NOT declare paths or code
  conventions in `plan.md` from memory; declared paths carry action suffixes
  (`(create)`, `(modify)`, etc.) and are validated against the worktree by
  `specops consistency`, which also checks that every success criterion of
  the spec is covered by at least one task. When a context map is present,
  agents also declare the contexts the work touches (`**SpecOps-Contexts**: …`)
  and validate the declared topology with `specops context plan-check` (a
  supported no-op when no map exists); the minimal phase-specific read set is
  resolved and displayed rather than read wholesale.
- **Token-Optimized Review (§18)**: the review agent loads the Spec's
  required Skills from the client's skills directory, runs `specops
  reconcile` and aborts immediately on failure, rejects changes outside
  `plan.md` via `git status --porcelain` without reading any code, and emits
  non-conformities as **structured findings** in the ledger via `specops handoff
  finding add` (Feature 011) — each carrying a stable `R<round>-F<NN>` id,
  `blocking`/`advisory` severity, the rule, the `file[:line]` location, a concise
  action, and per-finding expected evidence + closure criteria; `revisions/
  revision-X.md` is then a **rendered projection** of that authoritative state
  (`specops handoff render`), in the compatible `[File]:[Line] - [action]` format,
  never hand-authored. The review agent verifies a corrected finding with `specops
  handoff finding verify` and closes the round with `specops handoff close`;
  approval (`status transition-phase DONE`) is impossible while any **blocking**
  finding is unverified. `specops review` also runs a deterministic **drift gate**
  (Feature 010): it rejects when any effective-diff path is `unexplained` — neither
  declared in `plan.md` nor recorded via `specops trace acknowledge` — while
  planned and `discovered-and-acknowledged` paths pass, and SpecOps/Speckit-managed
  artifacts (`specs/**`, `.specify/**`, `specops.json`) are excluded as
  methodology state. Map-*digest* drift remains a non-blocking warning. Since
  Feature 012 the mechanical verification step of `specops review` runs the selected
  **gate-profile suite** (`.specify/specops/gate-profiles.yaml`, or the synthesized
  default `lint`/`test` profile) in place of the fixed lint/test gates — each gate
  carrying an outcome-taxonomy disposition (`required`|`optional`|`skipped`|`cached`|
  `failed`|`unavailable`) and, in `--json`, its disposition, reason, covered inputs,
  and supporting evidence id; a required failure/unavailability blocks, an optional
  one does not. `specops review` stays byte-for-byte read-only; the read-only
  `specops gate list`/`validate`/`report` surfaces inspect the profiles, selection,
  and evidence.
- **Stop-and-Ask Gates (§8.2)**: agents halt and ask the human on persisted
  schema changes (migrations), secrets, public contract breaks, or technical
  ambiguities.
- **Ledger & Phase Wiring**: during a corrective round the implement agent marks a
  resolved finding `FIXED` with `specops handoff finding fix <id> --task … --commit
  … (--evidence … | --auto)` (Feature 011), linking the correction to its task,
  commit(s), and evidence before review re-verifies it. SpecOps injects directives
  into every phase-bearing
  Speckit stage (specify, plan, tasks, implement) — not only plan and implement —
  so the execution ledger is created and the phase state machine
  (SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE) is advanced exclusively
  through the SpecOps CLI (`status init-spec`, `status transition-phase`) at each
  stage seam, never left to the human to trigger manually. The ledger is created
  at the tasks stage (after `tasks.md` exists), and the review cycle is opened at
  implement completion so `/specops-review` has an open cycle to record into.
  When a context map is present, closing a task or opening a review cycle also
  snapshots the resolved context ids and the context-map digest into the ledger
  record (or an explicit `{map: none}`/`{map: invalid}` marker), the review
  agent scopes its diff review by `specops context impact`, and a map-digest
  drift between planning and review is surfaced as a **non-blocking** warning.
  Where SpecOps is not initialized, the injected directives degrade to no-ops and
  the underlying Speckit prompt still works standalone.

Any change to these directives MUST be made in the SpecOps templates so all
client repositories receive it on the next `specops extension install` /
`update` (or `specops init` on the legacy path).

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

- **Packaging**: Python package published to PyPI as `speckit-specops`,
  installable via `pip` (including `pip install -e .` for development), exposing
  the `specops` entrypoint with functional `--help`.
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

SpecOps is developed under the plain Speckit lifecycle. The tool MUST NOT be
self-applied inside this repository while it is being defined: no
`specops.json` at the repository root, no `status.yaml` ledger under
`specs/*`, no `specops init` against this repository's own Speckit assets,
and no installed `/specops-review` command. Development state is tracked by
Speckit artifacts (`tasks.md` checkboxes). The stage directives under
`src/specops/templates/directives/` are product assets for client
repositories and MUST NOT be executed against this repository.

1. **Plan gate**: plans are checked manually against Principle IV's
   Empirical Verification directive — declared paths verified against the
   worktree, and every spec success criterion coverable by the planned work.
2. **Task gate**: every task is closed only with passing automated tests —
   no strict TDD required, but no task is complete without tests.
3. **Review gate**: reviews run lint and the full test suite before any code
   is read, following the token-optimized order of Principle IV. SpecOps'
   own gate behavior (reconcile, consistency, review) is validated
   exclusively through the automated test-suite fixtures under `tests/`,
   never by running `specops` commands against this repository.
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

**Version**: 1.8.0 | **Ratified**: 2026-07-05 | **Last Amended**: 2026-07-23
