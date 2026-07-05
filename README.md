# SpecOps CLI

`specops` is a pip-installable companion that layers the agent-guided atomic
development methodology on top of [GitHub Speckit](https://github.com/vgrecov/speckit).
It adds a physical state ledger, machine-collected evidence, and surgical review
to any Speckit repository — without replacing or forking Speckit's files.

## Install

```bash
pip install -e .          # development (editable)
pip install specops-cli   # from PyPI (once published)
```

Requires Python ≥ 3.10, Git ≥ 2.30. No network I/O after install.

## Quick Start

```bash
# In a Speckit-initialized repository
specops init              # inject directives, install /specops-review, create specops.json
specops status init-spec  # create the execution ledger (status.yaml)
```

## Commands

### `specops init [--non-interactive]`

Prepares a Speckit repository for SpecOps in one run:

1. Validates (or offers to create) a Git repository.
2. Detects Speckit (`.specify/templates/` must exist).
3. Resolves prompt targets from Speckit's integration manifests — works with
   any of Speckit's 40+ agent layouts (Claude skills, GitHub Copilot, etc.).
4. Creates or merge-preserves `specops.json`.
5. Installs `/specops-review` agent command at the layout-derived path
   (e.g., `.claude/skills/specops-review/SKILL.md`).
6. Injects SpecOps directive blocks into each integration's plan and implement
   prompts — additive, idempotent, byte-identical restore on removal.

`--non-interactive`: declines all interactive prompts (CI-safe).

**Speckit upgrade note**: a Speckit upgrade may rewrite prompt files, removing
the injected blocks. Re-run `specops init` to re-inject.

**Uninstall**: remove the appended block lines from each prompt file and delete
`specops.json` and the installed review command. No other files are written.

### `specops.json` keys

| Key | Purpose | Default |
|---|---|---|
| `test_command` | Command run by `complete-task --auto` | `pytest` |
| `lint_command` | Command referenced by the review prompt | `""` |
| `skills_dir` | Directory the review prompt loads skills from | `.specify/skills` |

Unknown keys are preserved on re-init.

### `specops status init-spec [<name>]`

Creates `<feature_dir>/status.yaml` from the packaged scaffold.
`<name>` is optional; when provided, it must match the active feature directory.
Fails if the ledger already exists.

### `specops status start-task <task-id>`

Marks the task `IN_PROGRESS` and records `started_commit = HEAD`.
Fails if another task is already `IN_PROGRESS` (single-active-task rule).

### `specops status complete-task <task-id> [--auto | --evidence "CLASS:summary"]`

Marks the task `DONE`. Exactly one evidence source required:

- `--auto`: runs `test_command`; on success, harvests `started_commit..HEAD`
  commits + name-only diff as `TEST_REPORT`/`CODE_DIFF` evidence.
- `--evidence`: caller-supplied string — must match `<CLASS>:<summary>`
  with class in `CLI_LOG | TEST_REPORT | SCREENSHOT_PATH | CODE_DIFF`.

Fails if `test_command` exits non-zero (`--auto`) or evidence is invalid.

### `specops status transition-phase <phase> [-r <result>]`

Advances the feature phase: `SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE`.

One exception: `REVIEW → IMPLEMENT` is allowed with `-r REJECTED` (corrective
round — opens a new `review_cycles[]` entry).
Entering `DONE` requires the latest review cycle result to be `APPROVED`.

### `specops reconcile`

Read-only. Validates every `tasks[].commits[]` hash is reachable from `HEAD`,
and every `DONE` task has commits and evidence. `(human)` commit values are
exempt. Lists each divergence as `<task-id>: <reason>` → exit 1. Exit 0 when
clean.

Use as a preflight gate before code review:
```bash
specops reconcile || exit 1
```

### `specops consistency`

Read-only. Validates against the active feature directory:

1. Every `SC-\d+` in `spec.md` Success Criteria has ≥ 1 task with a matching
   `[SC-xxx]` coverage tag; every tag references an existing SC.
2. Every path declaration in `plan.md` has an action suffix:
   - `(modify)` — file must exist in the worktree.
   - `(create)` — parent directory must exist.
   - `(remove)` — must exist locally or in Git history.

Violations: `consistency: <file>:<line> - <rule and short action>` → exit 1.

Use as a planning gate before handing off the plan.

## Installed agent command: `/specops-review`

(Command name follows the integration's invoke separator — e.g., `/specops-review`
for the Claude skills layout with separator `-`.)

Not a CLI command — a packaged prompt installed by `specops init`. It directs
the review agent through the cheapest-rejection-first order:

1. Load skills from `skills_dir`.
2. `specops reconcile` — abort immediately on failure.
3. `lint_command` + `test_command` — reject on failure.
4. `git status --porcelain` — reject any out-of-plan file without reading code.
   Empty diff → reject immediately.
5. Surgical diff review of in-scope files only.
6. Write `revisions/revision-X.md` (max existing X + 1) with findings in
   `[File]:[Line] - [rule violated and short action]` format.

### Scenario F (manual validation)

Invoke `/specops-review` in the agent with:
- A seeded ledger divergence — it aborts before reading any code.
- An out-of-plan changed file — it rejects from `git status --porcelain` alone.
- A compliant diff — it writes `revisions/revision-1.md` with `[File]:[Line]` findings.

Scenario F is validated manually (agent-in-the-loop) — not covered by `pytest`.

## Language policy

All SpecOps operational output (CLI messages, assets, tokens) is in English.
Client-authored prose (spec.md, plan.md, task descriptions) may be in any language.
SpecOps parses only structural tokens (`SC-\d+`, `T\d+`, action suffixes) —
never prose content.

## Supported Speckit layouts

SpecOps resolves prompt targets at runtime from `.specify/integrations/<agent>.manifest.json`.
Any Speckit integration with a recorded manifest is supported. Unknown layouts fail closed.

Tested with Speckit ≥ 0.12 (Claude skills mode, separator `-`).
