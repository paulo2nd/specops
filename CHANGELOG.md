# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Stability note**: SpecOps is at `0.x`. The CLI surface, `specops.json`
> schema, `status.yaml` ledger format, and injected directive blocks may change
> in any minor release until `1.0.0`. The surfaces frozen for 1.0 and the
> additive-vs-breaking rules for each are published in
> **[docs/stability.md](docs/stability.md)** (effective from `1.0.0-rc`).

## [Unreleased]

### Added

- **`specops trace link` — surgical commit→task binding ([#62](https://github.com/paulo2nd/specops/issues/62)).**
  `trace validate`'s `missing-link` defect requires each DONE user story to carry
  at least one bound commit, but the only writer of `tasks[].commits` was
  `complete-task`, which harvests the whole `started_commit..HEAD` range and only
  while the task is `IN_PROGRESS`. When commits landed out of task order — or the
  correct binding was known only after a task was `DONE` — no CLI could record it
  and a hand-edit of `status.yaml` was the only route. `trace link --task <T>
  --commit <sha> [--commit …]` writes explicit shas into a specific task's
  `commits`: it runs regardless of task status, is idempotent with union semantics
  (never dropping an existing binding), resolves short shas to full form, and
  requires each sha to be reachable from `HEAD` so a link can never introduce the
  `dangling-reference`/`reconcile` defect it exists to clear. Supplied shas are
  deduplicated and the task's `commits` are stored newest-first in topological
  order, so the `commits[0]` = HEAD-most contract that evidence-range derivation
  relies on holds regardless of `--commit` argument order.
  - `gitops.resolve_commit` — resolve a short sha/ref to its full commit sha.
  - `gitops.sort_commits_newest_first` — dedup + descendant-first topological order,
    tolerating unresolvable (rebased-away/legacy) shas already in the ledger.
- **`trace acknowledge --out-of-feature` — acknowledge tooling paths with no task
  ([#63](https://github.com/paulo2nd/specops/issues/63)).** The drift gate exempts
  only SpecOps/Speckit-managed paths (`.specify/`, `specops.json`, the active
  feature's `specs/<feature>/`); a tooling or methodology path outside that — a
  top-level `skills/`, `agents/`, or `.claude/` file touched to support the
  feature's development — classified as `unexplained` and blocked the review, and
  the existing `trace acknowledge` escape hatch forced a `--task` that no such
  change owns. `--out-of-feature` records a taskless acknowledgement (marked
  `out_of_feature: true`, no `task` key) so the path becomes
  `discovered-and-acknowledged` and the gate passes, while the reason stays audited
  and distinguishable from in-feature discovered scope. The ledger invariant and
  the `dangling-reference` check are relaxed to allow a taskless out-of-feature
  record; `--out-of-feature` cannot be combined with `--task`.

### Changed

- **`revisions/revision-X.md` is now a readable review model ([#64](https://github.com/paulo2nd/specops/issues/64)).**
  `handoff render` previously emitted only bare `<file>:<line> - <action>` lines (or
  `APPROVED`), discarding the severity, finding id, state, evidence, verdict, and
  round/role/range that all already existed in the ledger — leaving the artifact a
  reviewer reads hard to interpret. It now projects a structured model: a
  verdict/round/role/range header, findings grouped by severity with
  id/state/rule/action/expected-evidence/closure/evidence, and *this round's*
  remaining-blocking set (verdict, counts and remaining are all round-scoped, so the
  artifact is never self-contradictory; the feature-global gate stays
  `blocking_approval_check` at the DONE transition). Every interpolated field is
  flattened to a single line so an embedded newline can never inject a parseable
  finding. The 010-compatible flat `<file>:<line> - <action>` lines are retained as a
  trailing appendix, and remain the **only** section `handoff import` parses back into
  findings (the rich header is import-inert by construction), so render → import still
  round-trips. This establishes SpecOps' first rendered-artifact template.

### Fixed

- **`complete-task` no longer discards commits bound via `trace link`.** Task
  completion now unions the harvested `started_commit..HEAD` range with any commits
  already recorded on the task (e.g. an out-of-range ancestor linked via `trace
  link`) instead of overwriting, preserving the harvest's newest-first order.

## [0.10.0] - 2026-08-02

### Added

- **Review round integrity (Feature 025).** The multi-round semantic review is
  now sound: no approval can rest on an incomplete defect hunt, and the loop
  cannot cycle unbounded.
  - **Reviewed scope on the record.** `specops handoff record-scope` records each
    Step-3 round's git-derived reviewed range — an *anchor* round covers
    `baseline..HEAD`, a *corrective* round `prev_to..HEAD` plus open findings'
    files — and prints the exact files to read (replacing the ambiguous
    "working-tree gate list" instruction). The range is derived, never
    reviewer-supplied.
  - **Union-coverage approval guard.** `status transition-phase DONE` fails closed
    unless the union of recorded reviewed ranges covers the whole `baseline..HEAD`
    effective diff, naming any uncovered path. It checks coverage only — never a
    finding's merit (record, do not validate). Ledgers with no reviewed-scope
    records degrade to the prior cycle-result behavior.
  - **Configurable round cap.** `review_round_cap` (`specops.json`, default 10)
    turns an over-long review loop into a Stop-and-Ask halt: SpecOps records a
    `review_halt` marker and asks a human instead of opening another round.
    Resume by raising the cap, approving, or rebaselining.
  - **Ledger v7 → v8** (additive: optional `reviewed_range`/`review_role` on a
    review cycle, `review_halt` on the document; pure version bump, no backfill).
  - **`reviewed_range` endpoints are exempt from `reconcile`** — a rebased-away
    review HEAD never blocks reconciliation (Principle II narrowed; constitution
    v1.12.0). `specops preflight` stays byte-for-byte read-only.

## [0.9.0] - 2026-08-01

Test execution moves entirely to the review gate (Feature 024). A full workflow
run no longer executes the target project's test suite redundantly: from U+2
full-suite runs (U = user stories) down to **1**.

### Changed

- **Tests run only at the review gate — no test at implementation time.**
  `complete-task --auto` now records mechanical commit + `CODE_DIFF` evidence and
  runs **no** test at close.
  - **Why (token cost).** Running the suite at the end of every user story cost
    tokens and wall-clock for no real benefit: the story's code is already written
    and committed *before* the test would run, so a per-story test is purely
    confirmatory on the happy path — and its output, plus any failure-driven fix
    loop, needlessly entered the implement agent's context. Removing it keeps the
    implement loop cheap. The review gate (`specops preflight`) remains the single,
    complete correctness check that nothing bypasses.
  - `test_command` is now consumed **only** by the gate: an unset `test_command`
    no longer blocks `--auto`, and a failing one no longer blocks a task close
    (the gate still fails closed on a failing required gate).
- **The terminal gate reuses the soft gate's result** instead of re-running the
  identical suite over the identical tree. Reuse is keyed by a working-tree digest
  (any change, committed or not — including untracked-file content — invalidates
  it) and limited to the command-executing gates (`lint`/`test`);
  `reconcile`/`working-tree`/`drift` always recompute. The gate-run cache is
  ephemeral and lives **inside the git directory**, so `specops preflight` stays
  byte-for-byte read-only on the committed repo and never dirties the working tree.

### Governance

- Constitution amended to **1.11.0** (Principle III narrowed: `--auto` runs no
  test at close; verification lives at the review gate). Principle IV unchanged.
  The implement directive, `docs/commands.md`, and both READMEs are updated to
  match.

## [0.8.1] - 2026-07-31

### Changed

- Implement directive (Feature 023 follow-up): the context read set is now
  explicitly framed as a starting point, never a ceiling on discovery. The
  session's reads *start from* the union of the resolved packages (default
  scope, not a required reading list), and reads needed to implement a task
  correctly — call sites, tests, configs, any affected surface — are always in
  scope even when outside the union; token economy never outranks correctness.
  Same clarification mirrored in `docs/commands.md`, `README.md`, and
  `README.pt-br.md`. No mechanical change: out-of-set reads already blocked
  nothing, and changed undeclared paths still follow the Feature 010
  `trace acknowledge` flow.

### Fixed

- CHANGELOG: added the missing `[0.8.0]` compare link and repointed
  `[Unreleased]` to compare from `v0.8.0`.

## [0.8.0] - 2026-07-31

Lifecycle Coverage milestone (Features 022 + 023): every Spec Kit lifecycle
command has a defined SpecOps story, and the IMPLEMENT phase consumes the
context map's minimal read set.

Feature 022 — Lifecycle Recording Coverage. Every Spec Kit lifecycle command now
has a defined SpecOps story: converge records its task-list append through a
deterministic CLI seam (or fails closed before mutating), optional-step run/skip
decisions are recorded in both entry modes — including before the ledger exists —
and taskstoissues is verified read-only. All changes additive under the 1.0
contract freeze; the ledger schema stays at v7 (no migration).

### Added (Feature 022)

- **`specops status sync-tasks [--check] [--json]`** (new, additive): explicitly
  records a task-list mutation into the ledger using the same append merge
  `init-spec`/`start-task` already apply — new IDs enter as `PENDING`, vanished
  IDs are preserved as `orphaned`, reappeared IDs are revived (orphaned flag
  cleared), completed entries are untouched; deterministic, idempotent,
  zero-change runs succeed. `--check` validates the recording path without
  writing — a pure dry-run, no backup even on a migratable ledger (the converge
  pre-mutation precondition); `--json` emits
  `{appended, orphaned, revived, unchanged, check}`.
- **Converge directive pair** (`before_converge`/`after_converge` native hooks):
  fail closed **before mutation** via `sync-tasks --check` (stop-and-ask,
  `tasks.md` untouched, specific diagnostic — never silent ledger divergence);
  after converge, tag appended tasks `[SC-xxx]`, record via `sync-tasks`, and
  report `specops consistency` without gating (record, do not validate).
- **Pre-ledger decision buffering in `record-step`**: before the ledger exists a
  run/skip decision is buffered to the feature-scoped
  `specs/<feature>/.specops-pending-steps.json` (atomic, replace-by-step, with
  the recording branch as provenance) and drained into `workflow.skipped_steps`
  at every ledger-creation seam (`init-spec` and lane promotion), which deletes
  the buffer only after the write persists; entries from a different branch or
  with invalid content are discarded with a stderr note. An abandoned run's
  buffer is inert and dies with its feature directory. Generalizes the
  issue-#50 fix at the CLI layer.
- **`record-step --if-absent`** (new, additive): record only when the step has
  no decision yet; otherwise report the existing decision and change nothing —
  the idempotent primitive behind skip derivation, never overwriting an
  explicit choice. **`converge`** joins the recordable step values.
- **Run-decision recording hooks** (`after_clarify`/`after_checklist`/
  `after_analyze`): in slash-command mode each optional step records its own
  run decision; the tasks/implement directives derive `skip` at the next seam
  (`--if-absent`, native-manifest path only) — decision parity across entry
  modes, with no step ever forced and no block on a recorded skip.
- **Workflow converge gate**: the full workflow's corrective round offers
  `/speckit.converge` as a recorded optional step (gate → sticky-run recording
  — a `run` records unconditionally, a `skip` only `--if-absent` — →
  conditional run) before the corrective implement pass.
- **taskstoissues read-only contract**: verified and documented — no hook, no
  directive, ledger byte-identical across install/update; protected by a
  permanent regression test that pins the hook registry to the documented set.

### Changed (Feature 022)

- **`specops` workflow definition**: the clarify/checklist record steps return
  to sit adjacent to their gates (the issue-#50 after-tasks deferral is
  dissolved by pre-ledger buffering), and the `--if-needed` asymmetry between
  the workflow definition (idempotent engine re-runs) and the directives (bare
  fail-closed transitions with stop-and-ask) is documented as a deliberate
  contract in the definition and in docs/commands.md.

---

Feature 023 — Context Read-Set Consumption in IMPLEMENT. Closes the Feature 009
loop: the phase that reads the most now consumes the context map's minimal read
set. Directive-and-documentation change only — no CLI, schema, or frozen-contract
change.

### Added (Feature 023)

- **Implement directive — Context Read Set section**: at session start, before the
  first task, the agent resolves the IMPLEMENT-phase context package for each
  context declared in the plan (`specops context resolve --id <cid> --phase
  implement --json`) and scopes the session's reads to the union of the resolved
  packages (`read_set` + `expanded_read_set`). The read set is guidance plus
  record, never a gate: out-of-set reads block nothing and need no
  acknowledgement; a discovery that changes an undeclared path follows the
  existing Feature 010 `trace acknowledge` flow. Degradation is safe by
  construction — "no map present" is a supported no-op and any non-zero exit of
  the resolution step means the session proceeds without read-set scoping.
  Delivered through both paths (native `after_implement` hook and legacy marker
  block) from the same directive source.

## [0.7.1] - 2026-07-30

### Changed

- **`/specops-review` template**: Step 3 now states explicitly that the surgical diff
  review is a **code review** of the generated code — a mandatory defect hunt
  (correctness, edge cases, regressions, security, test quality) split from the
  spec/plan/constitution conformance pass — and instructs the agent to invoke the host's
  native code-review capability (e.g. Claude Code's `/code-review`) scoped to the
  effective diff when one exists, recording accepted findings as structured findings
  (or importing tool output via `handoff finding import-json`/`import-sarif`). The
  installed skill frontmatter description now announces the code-review role so
  agents surface the skill correctly.

## [0.7.0] - 2026-07-28

Feature 021 — Contract Freeze for 1.0. Declares and tests the stability of every
adopter-facing surface ahead of `1.0.0-rc`, and documents the post-1.0 versioning
and migration obligations.

### Added

- **Stability policy ([docs/stability.md](docs/stability.md))**: classifies all nine
  frozen surfaces (`specops.json`, `status.yaml`, `lane.yaml`, gate-profile files, the
  JSON output envelope, exit codes, the findings-input contract, the context-map file,
  and SARIF output), with an additive-vs-breaking rule for each and the post-1.0
  versioning/migration policy. An FR-003 sweep added the context-map file and SARIF
  output to the originally-scoped seven surfaces.
- **`output_version` on every `--json` envelope**: the base command-result envelope now
  always carries `output_version` (value `1`), so every automation consumer has one
  detectable version signal. This is additive — `consistency` and `reconcile` gain the
  key; all other families are byte-identical.
- **Contract tests** (`tests/unit/test_frozen_*.py`, `test_outcome_contract.py`) that lock
  the frozen shapes and fail on any unversioned breaking change.

### Changed

- **Constitution Principle VI** amended (v1.9.2 → v1.9.3, PATCH) to document exit code `2`
  (infrastructure/data/usage error) alongside `0`/`1` — aligning the governing principle
  with the shipped, now-frozen three-value exit contract. No behavior change.

---

Feature 020 — GitPython Removal. Replaces GitPython with direct `git` plumbing
behind the owned `gitops` seam. Behavior is byte-identical (verified against the
Feature 018 golden-capture harness); no ledger schema bump and no new CLI
command or option.

### Removed

- **Runtime dependencies `gitpython`, `gitdb`, `smmap`**: all git access now uses
  the `git` executable directly. `git` on PATH was already an implicit
  precondition (GitPython required it too), so no new system requirement is
  introduced — the dependency footprint shrinks by three packages, one of which
  (GitPython) is in maintenance mode.

### Added

- **`specops doctor` git-availability check**: the environment domain now reports
  whether a functional `git` is on PATH — `blocking` when absent/nonfunctional,
  `ok` (with the detected version) when present.
- **`specops init` fails closed on missing git**: init validates git availability
  as its first step and exits with a clear diagnostic (exit 1) instead of
  crashing at the `git init` subprocess when `git` is absent.

### Internal (no behavior change)

- `gitops` is now the single git access layer (a `Repository` abstraction over
  `git` plumbing); no other module imports a git library or names a third-party
  repository type. The `git.*` mypy override is removed. The constitution's
  dependency list is amended accordingly (v1.9.2).

Feature 019 — Hardening II: API & State Robustness. Internal hardening with
**zero user-visible change**: byte-identical human/JSON output and exit codes
(golden captures unchanged), no ledger schema bump (v7), no new CLI surface,
no new runtime dependency.

### Fixed

- **Ledger-lock stale-reclaim race (TOCTOU)**: two contenders observing the
  same stale `.lock` could both reclaim it (the slower one deleted the faster
  one's *fresh* lock), double-granting the read-modify-write critical section.
  Reclaim is now serialized through a `<lock>.reclaim` sentinel mutex with the
  staleness re-checked under the mutex, so at most one contender wins and a
  fresh lock is never touched; covered by an amplified concurrency regression
  test that fails on the old implementation. A `.reclaim` sentinel leaked by a
  reclaimer that crashed mid-reclaim is aged out on a bound kept **under**
  `timeout` (not the main lock's 30 s `stale`), so a genuinely stale lock is
  still reclaimed within the acquire deadline instead of spuriously timing out.
  The revision-CAS in `ledger.save` remains the durable lost-update authority.
  (Defect fix; no behavior change on any non-racing path — waiting and timeout
  diagnostics are unchanged.)
- **Scaffold templating on names containing `{{…}}`**: `render_template` now
  substitutes in a single pass that inserts each value literally (never
  re-scanning it), so a branch or feature name that itself contains a `{{…}}`
  sequence is written verbatim instead of being re-substituted or misflagged as
  unfilled template drift (which crashed `init-spec` / `lane start` on an
  otherwise valid name). Drift is judged on the template's own placeholders.

### Internal (no behavior change)

- `status`: the phase-transition and task-completion flows are decomposed into
  named sub-steps, and the Feature 006 DONE cycle gate — previously spelled
  verbatim twice — has exactly one implementation (`_require_approved_cycle`).
- New `specops.records`: `TypedDict` schemas for every ledger record
  (document, tasks, review cycles, handoffs, findings, evidence, provenance)
  giving mypy key-level checking with zero serialization change.
- `handoff`: the mutation loader returns a typed `LoadedLedger` and raises a
  typed refusal converted at one point — the 9 `isinstance` result probes are
  gone. Each command's CLI name has a single spelling (the `@_handoff_command`
  argument, read back in the body via a `ContextVar`), so the decorator's
  not-a-repo refusal and the body's other errors can never drift to different
  labels for the same command.
- `gitops`: single `--name-status` parser/invocation (`parse_name_status`,
  `name_status_diff(rename_aware=…)`); the lane's duplicate parser is deleted;
  the `(human)` ledger sentinel moved out of the generic git layer to
  `ledger.HUMAN_COMMIT` with explicit caller-side filters (every command that
  exempted it still does).
- `fsutil.render_template`: `{{...}}` scaffold rendering now asserts
  placeholder completeness — template drift fails loudly instead of writing
  silent residue (init-spec, lane start, lane-promotion synthesis).
- `gateprofiles`: field knowledge (key set, types, presence, defect wording)
  single-sourced in declarative tables consumed by both the lenient parser and
  the validator.
- `doctor`: shared-read failures convert to execution-error findings via one
  `_error_domain` helper; exceptions are no longer threaded through domain
  argument lists.

## [0.6.0] - 2026-07-27

### Fixed

- **Prompt-file injection is now crash-safe (#25).** `initializer.inject_block`
  and `remove_block` wrote host-owned prompt files with a plain `write_text`,
  so a crash mid-write could truncate them. All three modules that write files
  (`initializer`, `extension`, `ledger`) now share one durable temp-then-rename
  implementation in the new `specops.fsutil`, replacing the two previous
  independent copies; `ledger.atomic_write` remains the public name and
  delegates to it.
- **Broad exception handlers no longer swallow real diagnostics (#26).** A
  corrupted ledger encountered by `context impact` or `gate list` now surfaces
  as the standard exit-2 parse diagnostic instead of silently degrading to
  "no baseline"/an empty selection; the git-degrade paths in trace baseline
  resolution, consistency's history check, and lane's diff collection now
  suppress only the intended git failures, letting genuine bugs propagate.
- **Lane promotion records the ledger path correctly under symlinked roots
  (#27).** The containment check now uses `Path.is_relative_to` on resolved
  paths instead of a string-prefix comparison that failed with symlinks and
  matched partial prefixes (`/repo` vs `/repo2`).
- **Every ledger write crashed on Windows (#37).** `ledger.atomic_write` fsynced
  the temp file through a read-only handle; Windows' `fsync` (`_commit`) rejects
  those with `EBADF`, so any command that writes the ledger, context map, lane
  state, or a handoff revision failed. The write, flush, and fsync now go through
  a single writable handle. Found by the Windows CI leg introduced by #29.
- **Client-command timeouts could hang on Windows (#38).** On timeout,
  `shell._kill_tree` killed only the shell wrapper; a grandchild (e.g. the real
  test process) survived holding the output pipe, blocking the deterministic
  FR-010 timeout until it exited on its own. Windows now uses the tree-kill
  equivalent (`taskkill /T /F`). Also found by the new Windows CI leg.

### Changed

- **`specops lane … --json` now emits the standard output envelope (Feature 018).**
  Lane JSON output gained two top-level fields — `output_version` and `status` —
  bringing it into conformance with the envelope every other command family
  (`context`, `trace`, `handoff`, `gate`, `report`) already emits. Additive only:
  no existing key is removed, renamed, or reordered, and lane human-mode output and
  exit codes are unchanged. This is the single sanctioned behavior change of the
  internal-hardening consolidation; all other command output is byte-identical
  (enforced by the new `tests/golden/` behavior-freeze harness).

### Internal

- **Repo hygiene (#30).** The command reference, `/specops-review` description,
  and review-workflow guide moved from the README to `docs/commands.md`; the
  README (also the PyPI long description) keeps the overview, install, quick
  start, and a new commands-at-a-glance table, and `README.pt-br.md` became a
  short pointer page (ending its manual-sync divergence). PyPI metadata gained
  explicit 3.10–3.14 classifiers, `Development Status :: 4 - Beta`, and project
  URLs. Added a PR checklist template, a bug-report issue form, a pre-commit
  config running the CI lint gate, and dependabot grouping for dev-dependency
  bumps; SECURITY.md now reads "latest `0.x` release".
- **CI/release hardening (#29).** The CI matrix now covers Python 3.10/3.12/3.14
  on Ubuntu plus a Windows leg (the 0.2.1 UTF-8 hotfix was exactly the bug class
  the old Ubuntu-only matrix missed); pushes to PR branches no longer run the
  suite twice, superseded runs are cancelled, pip is cached, and tests run under
  `pytest-xdist` with `coverage.xml` published as an artifact. A new
  package-smoke job builds the sdist/wheel, `twine check`s metadata, and
  exercises the wheel from a clean-venv install, so packaging errors fail CI
  instead of surfacing on PyPI. The release workflow reuses that smoke step and
  refuses to publish when the release tag does not match the `pyproject.toml`
  version.
- **Internal hardening (Feature 018).** Consolidated the infrastructure duplicated
  across Features 008–013 into single definition sites, with no user-visible change
  beyond the lane envelope above: one `outcome.CommandResult` abstraction (trace and
  handoff joined it) and one `cli._emit`; every cross-module private helper promoted
  to a documented public name (zero cross-module private references remain); a single
  ledger-loading path (`ledger.load_raw`) behind `status show`/`report`/`reconcile`,
  so a corrupted ledger yields one identical diagnostic; one evidence-grammar owner
  (`evidence.validate_string`) and one finding factory + line grammar (`findings.py`);
  and a deduplicated test harness (one `git()` helper, shared ledger builders,
  in-process `CliRunner` invocation by default with a subprocess smoke set). No new
  runtime dependencies; ledger schema unchanged (v7).

## [0.5.1] - 2026-07-26

Wave 1 of the **1.0 Readiness** cycle: three defect fixes from the 2026-07-25
code/process review (issues #23, #24, #28). Bug fixes only — no new features, no
migration; the CLI surface, `specops.json` schema, and ledger format are unchanged.

### Fixed

- **Config robustness ([#23]).** `config.create_or_merge` no longer silently
  discards a corrupted `specops.json` and overwrites it with defaults. It now
  reuses `config.load`, so a corrupted file raises `ConfigError` (same contract
  as `load`, honoring the unknown-keys-are-preserved guarantee), and it skips the
  write entirely when the merge produces no change — keeping the user's exact
  bytes and byte-for-byte install idempotence.
- **UTF-8 file reads ([#28]).** Pinned `encoding="utf-8"` on the five remaining
  `read_text()` calls in `config.py` and `speckit.py` that fell back to the
  platform locale, preventing cp1252 divergence on Windows.
- **PEP 440 version comparison in the CLI-compatibility gate ([#24]).** The
  hand-rolled parser truncated pre-release suffixes, so `0.3.0rc1` wrongly
  satisfied a `>= 0.3.0` floor (PEP 440: `0.3.0rc1 < 0.3.0`). Because the floor
  can come from the user's `specops.json` `min_cli_version`, the gate could pass
  when it should block. Replaced the ~25-line custom parser with
  `packaging.version.Version`, giving full PEP 440 semantics (pre-releases,
  epochs, dev builds); an unparseable version now fails closed. Adds `packaging`
  as a runtime dependency (pure Python, zero transitive deps) and a corresponding
  constitution PATCH amendment (1.9.0 → 1.9.1).

[#23]: https://github.com/paulo2nd/specops/issues/23
[#24]: https://github.com/paulo2nd/specops/issues/24
[#28]: https://github.com/paulo2nd/specops/issues/28

## [0.5.0] - 2026-07-25

Adoption milestone (Features 013–017) — and the completion of the SpecOps evolution
roadmap: every numbered feature (005–017) is now merged. Small changes have a
proportional safe lane, the shipped workflow performs and enforces the semantic review,
any external reviewer's findings feed the structured handoff, the deterministic gate is
honestly named `preflight`, and a single read-only diagnostic explains project health.

### Added

- **Diagnostics and Machine Reports (Feature 014).** Two read-only surfaces that turn a
  scattered, expert-only health investigation into a single command.
  - New `specops doctor [--json]` — a read-only diagnostic over ten SpecOps-specific
    domains for the **active feature only** (environment readiness, CLI/extension
    compatibility, integration, legacy artifacts, configuration, feature identity,
    ledger schema + integrity, context-map health, workflow/ledger divergence, preflight
    gate availability). Each finding carries a severity (`ok` / `warning` / `blocking` /
    `execution-error`), a human message, and — when not `ok` — both a stable
    `next_action_code` and human next-action text. The overall verdict is the most severe
    finding; the exit code follows the outcome contract (**0** ok/warning, **1** blocking,
    **2** execution-error). `--json` emits a stable, versioned document
    (`output_version: 1`) that is byte-identical across runs.
  - New `specops report [--json]` — a compact, read-only status of the active feature
    (identity, branch, phase, task counts, active task, review cycles + open blocking
    findings, workflow lane), complementing the human-only `specops status show` with a
    stable machine surface.
  - Both are strictly read-only (mutate nothing), run fully offline, perform no
    telemetry or auto-repair, and never execute `specify` or any gate command — they
    *defer* to native `specify check` / `specify workflow status` by pointing at them,
    which keeps the machine output deterministic. Consumers must tolerate unknown domains
    and `next_action_code` values (additive growth without a version bump).
- **External Review Ingestion (Feature 015).** Any external reviewer — an LLM bug
  hunt, a static analyzer (CodeQL, semgrep), or a human — can now feed the structured
  corrective handoff (Feature 011) through a stable, versioned, stack-neutral input
  contract. SpecOps records the finding as a snapshot and gates deterministically on
  it; it never runs, bundles, or re-verifies the reviewer (Principle IV).
  - New `specops handoff finding` commands: `import-json` (a versioned JSON contract,
    `contract_version: 1`), `import-sarif` (an opt-in **SARIF 2.1.0** input adapter,
    the inverse of the Feature 012 SARIF output adapter), and `promote` (the human,
    audited escalation of an imported finding to `blocking`). All carry the stable
    `--json` outcome contract (exit `0`/`1`/`2`).
  - Every imported finding is recorded **`advisory` regardless of the producer's
    declared severity** — no external producer can block a merge on its own; only a
    human `promote` makes it gate approval, after which the unchanged Feature 011
    blocking-approval invariant applies.
  - Each finding records its **producer** (tool + version) and a **per-path reviewed
    digest**; `handoff report` flags a finding **stale** when the path it points at has
    changed since it was reviewed (path granularity — an unrelated change never stales
    it). Import is **all-or-nothing** (any defect names every problem and writes
    nothing; an empty document is a no-op) and **idempotent** (a re-import refreshes
    staleness in place, never duplicates, never demotes a promotion). Withdrawal reuses
    `handoff finding dismiss`.
  - **Migration required**: ledger schema **v6 → v7** (additive — the new finding
    fields are optional). Pre-v7 ledgers upgrade forward automatically with no data
    loss; a repository that never imports external findings behaves exactly as before.

- **Lightweight Workflow Lane (Feature 013).** A proportional lane for small,
  reversible changes, delivered as a second SpecOps-owned Spec Kit workflow
  (`specops-lite`, installed additively alongside `specops`) plus a new Principle IV
  injected directive that makes the agent **recognize and propose** the lane — the
  human never drives the `specops` CLI and answers only native gates (eligibility, two
  attestations, halt/promote).
  - New `specops lane` commands: `start`, `status`, `check`, `attest`, `close`,
    `promote` — agent/workflow-facing, non-interactive, with the stable `--json`
    outcome contract (exit `0`/`1`/`2`).
  - State lives in a dedicated `lane.yaml` record (its own schema — never
    `status.yaml`); the branch's commit history is the working record.
  - **Hybrid safety core**: four categories detected from the diff (migration, secret,
    dependency, destructive) via a generic non-removable pattern floor (overridable via
    `lane.safety` in `specops.json`); two categories not generically diff-detectable
    (root-cause, public-contract) enforced by always-on human attestation. A trip offers
    only halt or promote — no recordable bypass.
  - **Fail-closed close** runs the deterministic gate-profile suite and records
    structured evidence plus a rendered `retrospective.md`.
  - **Lossless promotion** synthesizes a full ledger at the `PLAN` phase with zero
    commit loss and carries the lane's context (`promoted_from_lane` / `lane_provenance`).

### Changed

- **The shipped `specops` workflow now performs and enforces the semantic review
  (Feature 016).** Previously a workflow-driven run passed the deterministic gates
  and could complete without ever running `/specops-review`, so no structured
  findings were recorded and the Feature 011 blocking-approval invariant gated an
  empty set. The corrective `do-while` loop now:
  - runs the deterministic `specops preflight` gate as a cheap **fail-closed
    precondition** and, only when it passes, drives the **semantic
    `command: specops.review`** step (the actual code review) — keeping the
    mechanical gate first for token discipline;
  - re-iterates while the gate is `REJECTED` **or** any **blocking finding** is
    still unverified (read from the existing `specops handoff report --json`
    `remaining_blocking` set — no CLI change), and cannot reach `DONE` while a
    blocking finding is unverified;
  - **degrades automatically** to the prior deterministic-only behavior when a run
    records no findings (legacy repos included) — enforcement is always-on with no
    opt-in/opt-out flag;
  - **fails closed** if the review cannot be performed (the `specops.review`
    command is unavailable), rather than completing silently.

  Composed from Spec Kit native steps and the existing handoff CLI only (no new
  engine/loop/gate primitive). **No migration required**: no persisted format,
  JSON contract, or CLI surface changed; repositories that record no findings
  behave exactly as before.

- **The deterministic gate `specops review` is renamed to `specops preflight`
  (Feature 017).** The command only ever ran mechanical checks (reconcile → gate-profile
  suite → working tree → drift); calling it "review" misled workflow/directive authors
  into thinking the code review happened there (the exact Feature 016 gap). The new name
  says what it is. **Behavior is byte-for-byte unchanged** — same gates, verdict, exit
  codes, `--json`/`--soft`/`--sarif`, and read-only guarantee.
  - `specops review` is retained as a **deprecated alias**: identical behavior and stdout
    (byte-identical except the `command` value in `--json`, which mirrors the invoked
    name — see below), plus a one-line deprecation notice on **stderr** only. It emits on
    every invocation and cannot be suppressed. **Removal no earlier than the next minor
    release, never in a patch.**
  - In `--json` output the `command` value mirrors the invoked name (`preflight` or
    `review`) — no JSON **key** changed, and no persisted ledger field, phase id, or
    verdict value changed. So a consumer that parses `specops review --json` stdout keeps
    working unchanged unless it asserts on the `command` value itself.
  - The shipped `workflow.yml`, the `/specops-review` directive template, the constitution
    (amended to 1.8.1), and the EN/PT READMEs now name the gate `preflight`. "review"
    stays reserved for the REVIEW phase, the `/specops-review` directive, and the verdict.
  - **Migration**: move CI steps, scripts, and workflow definitions from `specops review`
    to `specops preflight`. The alias keeps existing invocations working until removal.

## [0.4.0] - 2026-07-23

### Added

- **Gate profiles and structured evidence (Feature 012).** Replaces the single global
  `lint_command`/`test_command` pair with an ordered, context-aware **gate profile**
  suite, and the flat `<CLASS>:<summary>` evidence string with versioned, id-addressable
  **structured evidence records**:
  - A new versioned config `.specify/specops/gate-profiles.yaml` declares an ordered
    set of gates, each with a command, a single applicability predicate (`always` /
    context ids / changed-path globs / named-key `risk` — matching Feature 008's
    free-form risk mapping), a `timeout` (seconds; default `600`), a `required` flag
    (default `true`), and failure semantics. Absent — or an empty `profiles` list —
    synthesizes the default `lint`/`test` profile from `specops.json` (never zero
    gates), so an upgraded repository behaves exactly as before until a profile is
    authored.
  - `specops gate list [--json]` shows the deterministically selected suite with a
    machine-readable reason per gate; `specops gate validate [--json]` fails closed
    (exit `1`) with one distinct diagnostic per config defect; `specops gate report
    [--json]` reports the verdict provenance and the ledger's evidence records
    (read-only). No standalone runner — the suite executes inside `specops review`.
  - `specops review` now runs the selected profile suite in place of the fixed
    `lint`/`test` gates (`reconcile → [suite] → working-tree → drift`). Every gate
    carries an outcome-taxonomy disposition (`required` | `optional` | `skipped` |
    `cached` | `failed` | `unavailable`), a per-gate `timeout`, and — in `--json` —
    its disposition, reason, covered commit range/paths, and supporting `evidence_id`.
    A required failure/unavailability blocks; an optional one never does. `review`
    remains byte-for-byte **read-only** on the ledger.
  - Structured evidence records carry a cache-key-derived id (`EV-<hex12>` over
    producer/command/commit-range/paths/context-map-digest), exit code, timezone-aware
    timestamp, commit range, affected paths, summary, and an optional local-artifact
    `sha256` digest (no remote storage). `complete-task` and `handoff finding fix` now
    record a structured evidence record (and a task `evidence_refs` / finding
    `evidence_id`) alongside the retained legacy string. A gate is reported `cached`
    when a matching non-superseded record already exists in the ledger; because
    `specops review` stays read-only and does not itself persist gate-run evidence,
    gate self-caching end-to-end is deferred to a later feature (the cache-key +
    supersession mechanism ships now).
  - Opt-in `--sarif` on `specops review` and `specops gate report` emits a SARIF 2.1.0
    projection of the review findings (blocking → error, advisory → warning); absent by
    default.

  **Migration**: the ledger schema advances **v5 → v6** automatically on the next
  state-changing command. Legacy `<CLASS>:<summary>` evidence strings are back-filled
  into structured records without loss (a malformed string is preserved verbatim); the
  legacy string field is retained. The migration is idempotent and leaves the prior
  valid ledger readable on failure. Pre-v6 ledgers remain readable.

- **Structured corrective handoffs (Feature 011).** Promotes review findings and
  correction authorization from free-form `revisions/revision-X.md` prose to
  first-class, versioned ledger state, adding the `specops handoff` command group:
  - `finding add --severity <blocking|advisory> --rule … --file … [--line …]
    --action … [--expected-evidence … --closure …]` records a structured finding
    with a stable `R<round>-F<NN>` id in the current review round's handoff.
  - `finding fix <id> --task … --commit … (--evidence <CLASS>:<summary> | --auto)`
    moves a finding `OPEN → FIXED`, linking the resolving task, commit(s), and
    evidence; `finding verify <id>` moves it `FIXED → VERIFIED` (mechanical
    precondition; no auto-verify). `finding dismiss <id> --reason "…"` withdraws a
    false-positive or superseded finding to a terminal `DISMISSED` state so it no
    longer gates approval. Illegal transitions fail closed (exit `2`).
  - `authorize --path …` records the round's authorized corrective paths; `close`
    closes the handoff once every blocking finding is `VERIFIED` (idempotent;
    exit `1` while any remain).
  - `validate` fails closed (exit `1`) on a dangling reference, a blocking finding
    missing closure criteria, a contradictory state, or a duplicate id (commit
    existence is deferred to `specops reconcile`). `report` renders every finding
    and the remaining unverified blocking set (human + JSON, `output_version`).
  - `import [--round …]` imports legacy revision prose into advisory findings;
    `render --round …` projects the structured state to a compatible
    `revisions/revision-X.md`.
- **Blocking-approval invariant.** `specops status transition-phase DONE` now fails
  closed while any **blocking** finding is unverified, naming them. A repository
  with no structured findings degrades to the prior cycle-result gate.

- **End-to-end traceability (Feature 010).** Materializes a deterministic trace —
  success criterion → task → contexts/paths → commits → evidence → review findings
  → corrections — from the ledger and context provenance, and classifies every
  effective-diff path, adding four commands under `specops trace`:
  - `classify [--path …]` labels each effective-diff path (feature branch vs the
    ledger baseline, renames decomposed) as `planned` (declared in `plan.md`, or
    owned by a plan-declared context), `discovered-and-acknowledged`, or
    `unexplained`. SpecOps/Speckit-managed artifacts (`specs/**`, `.specify/**`,
    `specops.json`) are excluded as methodology state. Read-only, stable JSON with
    `output_version`.
  - `validate` fails closed (exit `1`) on any `unexplained` diff path or trace
    defect — uncovered success criterion, missing evidence / user-story-final
    commit, dangling reference, or contradictory ownership (commit existence is
    deferred to `specops reconcile`).
  - `report` renders the full chain (human + JSON), surfacing discovered paths
    distinctly with their reason and task.
  - `acknowledge <path> --task <id> --reason <text>` records a one-time,
    path-level acknowledgement so a genuine discovery is not blocked as drift.
    Idempotent for an identical record; fails closed (exit `2`) on a conflicting
    or unknown-task acknowledgement; a no-op for an already-planned path.
- **Review drift gate.** `specops review` now runs a terminal `drift` gate that
  rejects (exit `1`) only when an `unexplained` effective-diff path exists; planned
  and acknowledged paths pass. Map-*digest* drift remains a non-blocking warning.

### Changed

- **Ledger schema v4 → v5.** Adds a nested `handoff` object (authorized paths,
  closure timestamp, structured findings) to review-cycle records. The change is
  additive — a round with no findings has no `handoff` key — and prior ledgers
  migrate forward automatically and remain readable; the migration is covered by
  forward-migration tests. `revisions/revision-X.md` becomes a rendered projection
  of the structured findings (`specops handoff render`), keeping the compatible
  `[File]:[Line] - [action]` line format.
- **Ledger schema v3 → v4.** Adds the top-level `acknowledgements` list. Prior
  ledgers migrate forward automatically (the list is back-filled to `[]`) and
  remain readable; the migration is covered by forward-migration tests.

## [0.3.0] - 2026-07-21

### Added

- **Context-aware planning and impact (Feature 009).** Consumes the context map
  inside the planning, implementation, and review phases, adding three read-only
  commands under `specops context`:
  - `plan-check` validates a plan's declared context topology against the map:
    a plan declares the contexts it touches with a `**SpecOps-Contexts**: …`
    line, and the command blocks (exit `1`) on a missing declaration, an unknown
    declared context id, or a declared path owned by an undeclared context; an
    unowned declared path is reported non-blocking. Existence-agnostic (never
    stats the filesystem) and displays the minimal phase-specific read set.
  - `impact [--path …]` reports the contexts affected by a change — the directly
    owning context plus its transitive **reverse** dependents — each attributed
    to exactly one `ownership`/`dependency`/`policy` edge (the `policy` edge is
    defined and enforced but unpopulated against the current schema). With no
    `--path` the change set is derived from Git (baseline → HEAD); a clean tree
    yields an empty result (exit `0`), while not-a-repo / no-baseline is a usage
    error (exit `2`).
  - `stale` reports context-map patterns that match zero **Git-tracked** files
    (moved/removed), with the owning context, without editing the map;
    `context validate` stays syntactic-only.
- **Ledger v3 — context provenance.** Every task and review-cycle record now
  carries a `context_provenance` object: `{map: present, digest, context_ids,
  output_version}` when a map is present, or an explicit `{map: none}` /
  `{map: invalid}` marker otherwise. A new deterministic `v2 → v3` migration
  back-fills the `{map: none}` marker onto pre-existing records; prior ledgers
  remain readable. `specops review` prepends a **non-blocking** context-map drift
  warning when the recorded digest differs from the current one. All new surfaces
  are deterministic, read-only, and reuse the `0`/`1`/`2` exit-code contract.
- **Native Spec Kit extension** (`specops extension …`). SpecOps can now register
  through Spec Kit's own extension mechanism — a SpecOps-owned
  `.specify/extensions.yml` hook manifest plus per-integration command
  registration — instead of injecting marker blocks into host-owned prompt files:
  - `install` registers the lifecycle hooks + `/specops-review` command across
    every installed integration, touching **zero** host-owned files. Idempotent
    (semantic equivalence), offline-capable, and fail-closed when the CLI is
    missing/incompatible or the directory is not a Spec Kit repository.
  - `migrate` converts a legacy marker-injected installation to native, stripping
    the SpecOps marker blocks with an automatic pre-edit backup that restores all
    touched host files to exact bytes on failure, and preserving `specops.json`
    and every feature ledger.
  - `disable` / `enable` unregister from / re-register to the host surface while
    retaining configuration and ledgers; `remove [--purge]` removes the
    installation (leaving no host-owned file modified) and, with `--purge`, also
    deletes configuration and ledgers; `update` re-applies the current templates;
    `status` reports the detected state (`absent | native | legacy |
    native+legacy`) and CLI compatibility.
- `specops.json` gains `min_cli_version` (default `0.3.0`) recording the CLI
  floor the native extension requires.

### Changed

- The execution ledger schema advances **v2 → v3**. New ledgers are written at
  v3; v1/v2 ledgers migrate automatically on the next state change (backed up
  first) and gain the no-map provenance marker. No manual action is required.

- **Context map core.** A new versioned, stack-neutral repository context map at
  `.specify/specops/context-map.yaml`, with four commands under `specops context`:
  - `init` scaffolds a schema-valid starter map (idempotent, atomic; never
    overwrites an existing map).
  - `validate` checks the map and reports every defect in a single pass — invalid
    path pattern, unsafe path traversal, duplicate context id, ambiguous
    ownership, dangling dependency, dependency cycle, and unsupported schema
    version — each with a distinct diagnostic.
  - `resolve --path|--id [--phase]` returns the governing context and its ordered,
    phase-specific read set (with a `base` fallback) plus a cycle-safe,
    deduplicated, per-edge-attributed expanded read set drawn from dependencies.
  - `explain --path|--id [--phase]` emits an ordered reason trace naming the
    candidates and the deciding specificity dimension.

  Path matching is gitignore-style globbing implemented in the standard library
  (no new dependency); on overlap the most specific pattern wins (literal prefix
  → wildcard count → segment count), and a genuine tie is reported as ambiguous
  ownership. Every command offers a stable, versioned `--json` surface and uses
  the exit-code contract `0`/`1`/`2` (supported "no map present" and "no matching
  context" states stay `0`). Resolution is fully deterministic. Consumption by
  planning and review is deferred to a later feature.
- **Native workflow orchestration.** SpecOps ships an installable, SpecOps-owned
  `specops` workflow that composes Spec Kit's own native workflow engine to run
  the augmented lifecycle — SpecOps builds no engine, resume, gate, or loop:
  - `specops extension install` now additively registers the `specops` workflow
    into `.specify/workflows/specops/workflow.yml` and Spec Kit's
    `workflow-registry.json`, leaving the bundled `speckit` workflow and all
    foreign entries untouched; `remove`/`disable` prune only the SpecOps entry.
    Run it with `specify workflow run specops`.
  - The workflow enforces a **human planning-readiness gate** between plan and
    tasks, offers **human-decided skip gates** for the optional clarify/checklist/
    analyze steps (recorded in the ledger's additive `workflow.skipped_steps`),
    models rejection as a bounded native **`do-while` corrective loop**, and ends
    with a **terminal deterministic review gate** that fails closed unless the
    verdict is `APPROVED`. Forward-seam phase transitions remain owned by the
    injected directives; the workflow never double-issues them.
  - A stable **CLI outcome contract**: `specops review|reconcile|consistency
    --json` emit `{command, outcome, class, …}` distinguishing `pass`,
    `gate-rejection`, and `infra-error` for the workflow's native conditions.
    `review --json --soft` reports a REJECTED verdict without a non-zero exit so
    it can drive the corrective loop. Exit codes are unchanged (0/1/2).
  - **Ledger reconciliation** stays authoritative: `specops reconcile --json`
    reports a diverged dimension (feature/branch/baseline/workflow-state) and the
    `specops status rebaseline` remedy, and runs as a fail-closed precondition of
    the workflow's state-changing transition. A new `--if-needed` flag makes a
    transition to the current phase a no-op-and-continue.
- **Ledger v2 integrity.** The per-feature `status.yaml` ledger is now versioned
  and hardened against upgrades, interruptions, branch changes, and competing
  sessions:
  - An explicit `schema_version` (v1 = a ledger with no version key). Migratable
    older ledgers are upgraded automatically on the first state change — and via
    the new **`specops status migrate`** command — deterministically and
    losslessly (phases, tasks, evidence, and review cycles preserved). A too-new
    schema is refused; the original ledger is backed up under
    `.specify/.specops-backup/` before any migration, recorded in
    `recovery.migrated_from_backup`.
  - **Timezone-aware timestamps** (RFC 3339 UTC) with stable serialization: a
    no-op state change now rewrites nothing (byte-stable, no timestamp churn).
  - **Lost-update protection.** A monotonic `revision` with optimistic
    compare-and-swap on write: a stale write is refused (re-read and retry) and
    concurrent writers cannot clobber one another.
  - **Workspace-identity gate.** State changes are refused (fail closed, naming
    the diverged dimension) when the ledger's feature, branch, or branch-point
    baseline no longer matches the current workspace. After a deliberate branch
    rename or history rewrite, **`specops status rebaseline`** re-anchors the
    branch and baseline to the current workspace (never the feature identity).
    A pre-existing (legacy) invariant defect in an older ledger is tolerated —
    only a violation a command *newly introduces* blocks the write — so an old
    ledger is never permanently locked out.
  - **Interruption safety + recovery metadata.** Atomic writes leave the previous
    valid ledger readable after any interruption; `recovery.last_consistent_*`
    records the last committed state. New `workflow_lane` and `active_artifact`
    metadata track the lane and current-phase artifact.
  - Read-only commands (`status show`, `reconcile`) never mutate and stay
    available on legacy, too-new, unsupported, or malformed ledgers, reporting a
    best-effort diagnostic.
- Constitution amended to v1.4.0 (native extension as primary integration path,
  marker-delimited injection retained as legacy) and to v1.5.0 (Principle IV
  directives extended for context-aware planning/impact — the Feature 009
  behavior above).

### Fixed

- Corrective reviews now resume the placeholder cycle created after a rejection
  instead of appending an extra open cycle and skipping the intended round.
- English and Portuguese documentation now match the effective-diff review
  scope, per-user-story commit semantics, and manual marker-block removal.
- The project link now points to the canonical GitHub Spec Kit repository.

### Notes

- The legacy `specops init` marker-injection path remains fully supported and
  unchanged. Migration is opt-in via `specops extension migrate`.
- These unreleased changes require the `specops` CLI `>= 0.3.0` (the native
  extension's `min_cli_version` floor). All work since `v0.2.1` (Features 005–009)
  is accumulating here and will be cut as a single dated release + tag at the end
  of the roadmap.

## [0.2.1] - 2026-07-14

### Fixed

- Windows: `specops --help` and phase-transition messages no longer crash with
  `UnicodeEncodeError` when stdout/stderr default to cp1252. The CLI now forces
  UTF-8 output at startup so non-ASCII glyphs (e.g. `→`) render everywhere,
  including redirected output. Surfaced by the conda-forge Windows build.
- `specops --version` reported `0.0.0.dev0` for installed builds: the version
  lookup queried the wrong distribution name (`specops-cli` instead of
  `speckit-specops`). It now reports the correct installed version.

## [0.2.0] - 2026-07-06

### Added

- `specops review` — read-only CLI gate running the deterministic review gates
  cheapest-first with early stop: reconcile → lint → test → working
  tree/effective diff. Reports per-gate PASS/FAIL/SKIPPED; a full pass lists
  the effective-diff files (the reviewing agent's surgical scope); first
  failure exits 1 with evidence on stderr (last 50 lines of a failing
  lint/test output); ledger parse errors keep exit 2. Runs from any directory
  inside the repo, snapshots working-tree cleanliness at invocation (tool
  artifacts created by lint/test cannot fail the run), distinguishes an
  unresolvable baseline (shallow clone) from an empty diff, and tolerates
  non-UTF-8 command output. Never mutates the ledger, needs no specific
  phase, never prompts — usable directly as a CI step or a Speckit-workflow
  shell gate.
- `gitops.dirty_files` and `status.read_baseline` helpers backing the new gates.
- Release automation: a GitHub release publishes to PyPI via
  `.github/workflows/release.yml` (PyPI Trusted Publishing, no stored tokens).

- Stage-wide directive wiring: `specops init` now injects directive blocks into
  the **specify** and **tasks** prompts (in addition to plan and implement). The
  tasks directive creates the ledger (`status init-spec`), advances the phase to
  `TASKS`, and carries the authoritative `[SC-xxx]` coverage-tag rule; the
  implement directive opens the `IMPLEMENT` and `REVIEW` phases. The phase state
  machine is now driven end to end by the injected prompts.
- `resolve_prompt_targets` returns `specify_path` and `tasks_path` (best-effort:
  `None` when a partial Speckit layout lacks the prompt).

### Changed

- The installed `/specops-review` prompt delegates its deterministic gate steps
  (formerly agent-orchestrated reconcile, lint/test, and working-tree checks) to
  a single `specops review` invocation; the surgical diff review, revision
  report, and verdict transition are unchanged. Delivered on the next
  `specops init` run.
- The `[SC-xxx]` coverage-tag rule moved from the plan directive to the tasks
  directive (where `tasks.md` is generated); the plan directive now points to it.
- Constitution 1.1.3 → 1.2.0: Principle IV gains the **Ledger & Phase Wiring**
  directive category.

## [0.1.0] - 2026-07-05

### Added

- `specops init` — prepares a Speckit repository: validates/creates a Git repo,
  detects Speckit, resolves prompt targets from integration manifests, creates
  or merge-preserves `specops.json`, installs the `/specops-review` command, and
  injects idempotent SpecOps directive blocks into the plan and implement prompts.
- `specops status init-spec` — creates the `status.yaml` execution ledger from
  the packaged scaffold, syncing task IDs from `tasks.md`.
- `specops status start-task` — marks a task `IN_PROGRESS` and records
  `started_commit`; enforces the single-active-task rule.
- `specops status complete-task` — marks a task `DONE` with machine-collected
  evidence (`--auto`) or a caller-supplied `--evidence` string.
- `specops status transition-phase` — advances the feature phase
  (`SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE`) with review-cycle
  bookkeeping.
- `specops status show` — read-only ledger state report.
- `specops reconcile` — read-only validation that ledger commits are reachable
  from `HEAD` and every `DONE` task has commits and evidence.
- `specops consistency` — read-only validation of SC coverage tags and plan
  path-declaration action suffixes.
- `/specops-review` — packaged, token-optimized review command installed into
  the agent layout by `specops init`.
- Atomic ledger persistence (`tmp` → `fsync` → `os.replace`).
- CI matrix (Python 3.10 and 3.14) running ruff, mypy, and pytest with a
  coverage floor of 85%.

[Unreleased]: https://github.com/paulo2nd/specops/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/paulo2nd/specops/compare/v0.8.1...v0.9.0
[0.8.1]: https://github.com/paulo2nd/specops/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/paulo2nd/specops/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/paulo2nd/specops/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/paulo2nd/specops/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/paulo2nd/specops/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/paulo2nd/specops/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/paulo2nd/specops/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/paulo2nd/specops/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/paulo2nd/specops/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/paulo2nd/specops/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/paulo2nd/specops/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/paulo2nd/specops/releases/tag/v0.1.0
