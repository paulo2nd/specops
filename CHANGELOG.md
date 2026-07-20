# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Stability note**: SpecOps is at `0.x`. The CLI surface, `specops.json`
> schema, `status.yaml` ledger format, and injected directive blocks may change
> in any minor release until `1.0.0`.

## [Unreleased]

### Fixed

- Corrective reviews now resume the placeholder cycle created after a rejection
  instead of appending an extra open cycle and skipping the intended round.
- English and Portuguese documentation now match the effective-diff review
  scope, per-user-story commit semantics, and manual marker-block removal.
- The project link now points to the canonical GitHub Spec Kit repository.

## [0.3.0] - 2026-07-19

### Added

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

- Constitution amended to v1.4.0: Principles I and IV now name the native
  extension mechanism as the primary integration path, with marker-delimited
  injection retained as the supported legacy path.

### Notes

- The legacy `specops init` marker-injection path remains fully supported and
  unchanged. Migration is opt-in via `specops extension migrate`.
- Requires the `specops` CLI `>= 0.3.0`.

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
