# CLI Contract: `specops`

**Plan**: [../plan.md](../plan.md) | **Data model**: [../data-model.md](../data-model.md)

Global contract: all output in English; exit `0` success, `1` blocking validation
failure, `2` unexpected error (R9). Every command except `init` verifies Git presence
first and fails `1` within 1 s when absent (FR-002, SC-008). No command performs
network I/O. Every `status` subcommand re-syncs the ledger task list from `tasks.md`
before acting (FR-008a).

## `specops init [--non-interactive]`

Prepares a Speckit repository (FR-001…007, FR-017).

| Step | Behavior | Failure |
|---|---|---|
| 1. Git check | If not a repo: offer `git init` (interactive); `--non-interactive` declines by default | declined → exit 1 |
| 2. Speckit check | `.specify/templates/` must exist (R1) | absent → exit 1, "initialize Speckit first" |
| 3. Prompt targets | Resolve from `.specify/integration.json` + per-integration manifests (R2), for EVERY installed integration | missing manifest/entry/file → exit 1 naming it, nothing written |
| 4. `specops.json` | Create from template, or merge-preserve existing (R10) | — |
| 5. Agent command | Install `review.md` per integration at the path derived from the plan-prompt pattern (`speckit{sep}plan` → `specops{sep}review`; here `.claude/skills/specops-review/SKILL.md`, frontmatter-wrapped in skills mode); command name `specops{sep}review` | — |
| 6. Injection | Append/update marker blocks in each integration's plan and implement prompts | corrupted markers → exit 1, no write |

Output: summary of created/updated/unchanged items. Idempotent (SC-005, SC-010).

## `specops status init-spec [<name>]`

Creates `<feature_dir>/status.yaml` from the packaged scaffold with `{{feature-name}}`,
baseline and dates filled (R10); syncs tasks from `tasks.md` when present. `<name>` is
optional: default is the active feature directory (R1); when provided, it must
resolve to `specs/<name>` AND match the active feature directory, else exit 1. Fails
`1` if the ledger already exists.

## `specops status start-task <task-id>`

Marks `<task-id>` IN_PROGRESS, records `started_commit = HEAD`, sets
`recovery.active_task`. Failures (exit 1): id not in `tasks.md`; another task already
IN_PROGRESS (R5); task already DONE.

## `specops status complete-task <task-id> [--auto | --evidence "<CLASS>:<summary>"]`

Marks DONE. Exactly one evidence source is required (FR-009a):

- `--auto`: run `test_command` (missing/failing → exit 1, stays IN_PROGRESS);
  harvest `started_commit..HEAD` commits + name-only diff (empty range → exit 1);
  record `TEST_REPORT:…; CODE_DIFF:…` (R7).
- `--evidence`: caller-supplied string; must match `^[A-Z_]+:.+` with class in
  `CLI_LOG|TEST_REPORT|SCREENSHOT_PATH|CODE_DIFF`.
- Neither flag → exit 1. Task not IN_PROGRESS → exit 1.

## `specops status transition-phase <phase> [-r <result>]`

Validates against the phase machine (data-model). `REVIEW → IMPLEMENT` requires
`-r REJECTED` and appends a review cycle; entering REVIEW opens a cycle; `DONE`
requires latest cycle APPROVED. Invalid phase/jump → exit 1, ledger untouched
(FR-008b).

## `specops reconcile`

Read-only. Exit 0 when every `tasks[].commits[]` hash is an ancestor of HEAD and
every DONE task has commits + evidence; exit 1 listing each divergent entry
(`<task-id>: <reason>`), including `orphaned` flags. `(human)` commit values are
exempt (R11). Warns (not fails) on `branch` mismatch and on a `baseline` absent from
local history (reference behavior preserved).

## `specops consistency`

Read-only, against the active feature dir. Exit 1 listing all violations:

1. Every `SC-\d+` in the spec's Success Criteria has ≥1 task with a matching
   coverage tag; every tag references an existing SC (R6).
2. Every path declaration in `plan.md` carries an action suffix; `(modify)` path
   must exist in the worktree; `(create)` parent must exist; `(remove)` must exist
   locally or in Git history; missing suffix → warning (FR-012).

Violation line format: `consistency: <file>:<line> - <rule and short action>`.

## Installed agent command: `/specops-review` (name follows the integration's invoke separator)

Not a CLI command — the packaged `review.md` prompt (FR-013). Mandatory order: load
skills from `skills_dir` → run `specops reconcile` (abort on ≠0) → `lint_command` +
`test_command` must pass → `git status --porcelain` scope check vs plan paths
(out-of-scope ⇒ REJECTED without reading contents; empty diff ⇒ REJECTED) → surgical
diff review → emit `revisions/revision-X.md` findings as
`[File]:[Line] - [rule violated and short action]`.
