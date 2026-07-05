# SpecOps CLI

[![CI](https://github.com/paulo2nd/specops/actions/workflows/ci.yml/badge.svg)](https://github.com/paulo2nd/specops/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/specops-cli.svg)](https://pypi.org/project/specops-cli/)
[![Python](https://img.shields.io/pypi/pyversions/specops-cli.svg)](https://pypi.org/project/specops-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**SpecOps turns [GitHub Speckit](https://github.com/vgrecov/speckit)'s
spec-driven workflow into an enforced, auditable process.** It layers an
agent-guided *atomic development* methodology on top of any Speckit repository —
a physical state ledger, machine-collected evidence, and token-optimized review —
**without replacing or forking a single Speckit file.**

> Speckit gives your agents great artifacts (spec → plan → tasks → implement).
> SpecOps makes sure they actually follow them: state is on disk and
> Git-verifiable, evidence is collected by tooling instead of claimed by the
> agent, and review rejects as cheaply as possible.

## Why SpecOps?

Spec-driven development with AI agents has three recurring failure modes.
SpecOps addresses each one:

| Problem | Without SpecOps | With SpecOps |
|---|---|---|
| **Agents hallucinate progress** | "Done ✅" with no proof | Every task is closed with machine-collected evidence (test output, commit hashes, diffs) recorded in the ledger |
| **State lives in the chat** | Lost on context reset; not auditable | State is a physical `status.yaml` ledger, Git-verifiable and recovery-safe |
| **Reviews are slow and expensive** | Agent reads the whole repo | `/specops-review` rejects cheapest-first (reconcile → lint/test → out-of-plan files) before reading any code |

## What it adds to Speckit

- **📒 Physical state ledger (Repo-as-State).** A structured `status.yaml`
  tracks phase, tasks, evidence, and review cycles. Mutated only through
  `specops` commands — never hand-edited, never held in agent memory.
- **🔬 Automated evidence collection.** `complete-task --auto` runs your test
  command, harvests commits and diffs, and records them as typed evidence. A
  task cannot be `DONE` without proof.
- **🔁 A phase state machine wired into the prompts.** `specops init` injects
  directives into the specify, plan, tasks, and implement prompts so the ledger
  is created and phases advance automatically — the human never runs the
  bookkeeping by hand.
- **✂️ Token-optimized surgical review.** The installed `/specops-review`
  command reviews only in-scope files and stops at the first cheap rejection.
- **📐 Empirical verification & gates.** `specops consistency` and
  `specops reconcile` are exit-code gates you can drop into CI or agent prompts.
- **➕ Additive and reversible.** Everything is delivered through
  marker-delimited blocks. Uninstalling restores your Speckit files
  byte-for-byte.

## Install

```bash
pip install specops-cli
```

Requires Python ≥ 3.10 and Git ≥ 2.30. No network I/O after install.

## Quick Start

```bash
# In a Speckit-initialized repository:
specops init          # inject directives, install /specops-review, create specops.json
```

That's it. From here you drive Speckit as usual (`/speckit.specify`,
`/speckit.plan`, `/speckit.tasks`, `/speckit.implement`) and the injected
directives take care of the ledger and phase transitions. Check state anytime:

```bash
specops status show
```

## How it works

SpecOps rides the Speckit lifecycle. Once `specops init` has run, the injected
directives drive the ledger at each stage seam:

| Speckit stage | What SpecOps does |
|---|---|
| **specify** | Marks the repo as SpecOps-managed (informational; no ledger yet) |
| **plan** | Enforces empirical path verification and the `consistency` gate |
| **tasks** | Creates the ledger (`status init-spec`), advances the phase to `TASKS`, and requires `[SC-xxx]` coverage tags on every task |
| **implement** | Opens `IMPLEMENT`, runs the evidence-backed ledger loop, then opens `REVIEW` |
| **review** | `/specops-review` validates the diff and records `APPROVED` / `REJECTED` |

The phase machine is `SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE`.
If SpecOps is not installed, the Speckit prompts still work standalone — the
directives degrade to no-ops.

## Command reference

### `specops init [--non-interactive]`

Prepares a Speckit repository in one run: validates (or offers to create) a Git
repo, detects Speckit, resolves prompt targets from Speckit's integration
manifests (works with any recorded agent layout — Claude skills, GitHub
Copilot, etc.), creates/merge-preserves `specops.json`, installs
`/specops-review`, and injects the directive blocks into the specify, plan,
tasks, and implement prompts (additive, idempotent, byte-identical restore on
removal). `--non-interactive` declines all prompts (CI-safe).

> **Speckit upgrade note**: a Speckit upgrade may rewrite prompt files and
> remove the injected blocks. Just re-run `specops init` to re-inject.

### `specops status show`

Read-only. Prints ledger state: feature, branch, phase, active task, task counts
(pending / in progress / done / orphaned), and the review-cycle history.

### `specops status init-spec [<name>]`

Creates `<feature_dir>/status.yaml` from the packaged scaffold, syncing task IDs
from `tasks.md`. Usually run for you by the tasks directive.

### `specops status start-task <task-id>`

Marks the task `IN_PROGRESS` and records `started_commit = HEAD`. Enforces the
single-active-task rule.

### `specops status complete-task <task-id> [--auto | --evidence "CLASS:summary"]`

Marks the task `DONE` with exactly one evidence source:

- `--auto`: runs `test_command`; on success, harvests `started_commit..HEAD`
  commits + diff as `TEST_REPORT`/`CODE_DIFF` evidence.
- `--evidence "CLASS:summary"`: caller-supplied, with `CLASS` in
  `CLI_LOG | TEST_REPORT | SCREENSHOT_PATH | CODE_DIFF`.

### `specops status transition-phase <phase> [-r APPROVED|REJECTED]`

Advances the phase one step forward. Two transitions require `-r`:

```bash
specops status transition-phase DONE -r APPROVED      # approved → close the feature
specops status transition-phase IMPLEMENT -r REJECTED # rejected → send back for rework
```

Entering `DONE` requires the latest review cycle to be `APPROVED`.

### `specops reconcile`

Read-only gate. Verifies every ledger commit hash is reachable from `HEAD` and
every `DONE` task has commits and evidence. Exit 1 on any divergence.

```bash
specops reconcile || exit 1   # preflight before review
```

### `specops consistency`

Read-only gate. Verifies every `SC-\d+` in the spec has ≥ 1 task with a matching
`[SC-xxx]` tag, and every `plan.md` path declaration carries a valid action
suffix (`(create)`/`(modify)`/`(remove)`). Exit 1 on violation.

### `specops --version`

Prints the version and exits. Works anywhere.

## Configuration — `specops.json`

| Key | Purpose | Default |
|---|---|---|
| `test_command` | Command run by `complete-task --auto` | `pytest` |
| `lint_command` | Command referenced by the review prompt | `""` |
| `skills_dir` | Directory the review prompt loads skills from | `.specify/skills` |

Unknown keys are preserved on re-init.

## The `/specops-review` command

Installed by `specops init` (the name follows the layout's separator, e.g.
`/specops-review` for Claude skills). Not a CLI command — a packaged prompt that
drives the review agent cheapest-rejection-first:

1. Load skills from `skills_dir`.
2. `specops reconcile` — abort immediately on failure.
3. `lint_command` + `test_command` — reject on failure.
4. `git status --porcelain` — reject any out-of-plan file without reading code.
5. Surgical diff review of in-scope files only.
6. Write `revisions/revision-X.md` and record the `APPROVED`/`REJECTED` outcome.

## Language policy

All SpecOps operational output (CLI messages, injected assets) is in English.
Your prose (`spec.md`, `plan.md`, task descriptions) may be in **any language** —
SpecOps parses only structural tokens (`SC-\d+`, `T\d+`, action suffixes), never
content.

## Supported Speckit layouts

SpecOps resolves prompt targets at runtime from
`.specify/integrations/<agent>.manifest.json`. Any Speckit integration with a
recorded manifest is supported; unknown layouts fail closed. Tested with
Speckit ≥ 0.12 (Claude skills mode, separator `-`).

## Uninstall

Remove the appended block from each prompt file, then delete `specops.json` and
the installed review command. No other files are written; the restore is
byte-identical.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup,
the quality gates, and project principles. SpecOps is at `0.x`; the CLI surface
and ledger format may still change before `1.0` (see [CHANGELOG.md](CHANGELOG.md)).

## License

[MIT](LICENSE) © Paulo Segundo
