# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Stability note**: SpecOps is at `0.x`. The CLI surface, `specops.json`
> schema, `status.yaml` ledger format, and injected directive blocks may change
> in any minor release until `1.0.0`.

## [Unreleased]

### Added

- `specops review` — read-only CLI gate running the deterministic review gates
  cheapest-first with early stop: reconcile → lint → test → working
  tree/effective diff. Reports per-gate PASS/FAIL/SKIPPED; first failure exits 1
  with evidence on stderr (last 50 lines of a failing lint/test output); ledger
  parse errors keep exit 2. Never mutates the ledger, needs no specific phase,
  never prompts — usable directly as a CI step or a Speckit-workflow shell gate.
- `gitops.dirty_files` and `status.read_baseline` helpers backing the new gates.

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

[Unreleased]: https://github.com/paulo2nd/specops/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/paulo2nd/specops/releases/tag/v0.1.0
