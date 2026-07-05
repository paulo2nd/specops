# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Stability note**: SpecOps is at `0.x`. The CLI surface, `specops.json`
> schema, `status.yaml` ledger format, and injected directive blocks may change
> in any minor release until `1.0.0`.

## [Unreleased]

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
