# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Stability note**: SpecOps is at `0.x`. The CLI surface, `specops.json`
> schema, `status.yaml` ledger format, and injected directive blocks may change
> in any minor release until `1.0.0`.

## [Unreleased]

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

[Unreleased]: https://github.com/paulo2nd/specops/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/paulo2nd/specops/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/paulo2nd/specops/releases/tag/v0.1.0
