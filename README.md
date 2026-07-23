# SpecOps CLI

[![CI](https://github.com/paulo2nd/specops/actions/workflows/ci.yml/badge.svg)](https://github.com/paulo2nd/specops/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/speckit-specops.svg)](https://pypi.org/project/speckit-specops/)
[![Python](https://img.shields.io/pypi/pyversions/speckit-specops.svg)](https://pypi.org/project/speckit-specops/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Read this in: **English** | [Português (BR)](README.pt-br.md)

**SpecOps turns [GitHub Spec Kit](https://github.com/github/spec-kit)'s
spec-driven workflow into an enforced, auditable process.** It layers an
agent-guided *atomic development* methodology on top of any Speckit repository —
a physical state ledger, typed evidence with machine collection, and
token-optimized review —
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
| **Agents hallucinate progress** | "Done ✅" with no proof | Every task closes with typed evidence; `--auto` attaches test output, commit hashes, and diffs at the commit boundary |
| **State lives in the chat** | Lost on context reset; not auditable | State is a physical `status.yaml` ledger, Git-verifiable and recovery-safe |
| **Reviews are slow and expensive** | Agent reads the whole repo | `/specops-review` rejects cheapest-first (reconcile → lint/test → working tree/effective diff) before reading any code |

## What it adds to Speckit

- **📒 Physical state ledger (Repo-as-State).** A versioned, structured
  `status.yaml` tracks phase, tasks, evidence, and review cycles. Mutated only
  through `specops` commands — never hand-edited, never held in agent memory.
  State changes are atomic and interruption-safe, guarded by optimistic
  concurrency (a monotonic `revision`) and a workspace-identity check
  (feature / branch / baseline); older ledgers migrate losslessly with a backup.
- **🔬 Automated evidence collection.** `complete-task --auto` runs your test
  command, harvests commits and diffs, and records them as typed evidence. A
  task cannot be `DONE` without proof.
- **🔁 A phase state machine wired into the prompts.** `specops init` injects
  directives into the specify, plan, tasks, and implement prompts so the ledger
  is created and phases advance automatically — the human never runs the
  bookkeeping by hand.
- **✂️ Token-optimized surgical review.** The installed `/specops-review`
  command reviews only effective-diff files and stops at the first cheap rejection.
- **📐 Empirical verification & gates.** `specops consistency` and
  `specops reconcile` are exit-code gates you can drop into CI or agent prompts.
- **➕ Additive and reversible.** Everything is delivered through
  marker-delimited blocks. Removing those blocks restores the affected Speckit
  files byte-for-byte.

## Install

```bash
pip install speckit-specops
```

Installs the `specops` command. Requires Python ≥ 3.10 and Git ≥ 2.30. No
network I/O after install.

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

### `specops extension install | update | disable | enable | remove [--purge] | migrate | status`

Registers SpecOps through Spec Kit's **native extension mechanism** — a
SpecOps-owned `.specify/extensions.yml` hook manifest plus per-integration
command registration — instead of injecting marker blocks into host-owned prompt
files. The Python CLI stays the deterministic engine; the hooks call it.

- `install` — register the lifecycle hooks + `/specops-review` command across
  every installed integration. Touches **zero** host-owned files, is idempotent,
  works offline, and fails closed (leaving the repo unchanged) when the CLI is
  missing/incompatible or the directory is not a Spec Kit repository.
- `update` — re-apply the current directive templates (idempotent).
- `disable` / `enable` — unregister from the host surface (retaining
  configuration and ledgers) / re-register from the retained configuration.
- `remove [--purge]` — unregister, leaving no host-owned file modified;
  `--purge` also deletes `specops.json` and feature ledgers.
- `migrate` — convert a legacy marker-injected installation to native, stripping
  the SpecOps marker blocks (with an automatic pre-edit backup that restores on
  failure) while preserving configuration and every feature ledger.
- `status` — read-only; reports the detected state
  (`absent | native | legacy | native+legacy`) and CLI compatibility.

The legacy `specops init` path above remains fully supported. Requires the
`specops` CLI `>= 0.3.0` (the first release that understands the native manifest
schema).

`install` also additively registers the **`specops` workflow** (below), leaving
Spec Kit's bundled `speckit` workflow untouched.

### The `specops` workflow

`specops extension install` registers an installable, SpecOps-owned workflow that
composes **Spec Kit's own native workflow engine** to run the augmented lifecycle
— SpecOps builds no engine, resume, gate, or loop. Run it with:

```bash
specify workflow run specops
```

It drives specify → clarify/checklist (human skip gates, recorded in the ledger)
→ plan → **human planning-readiness gate** (no tasks until approved) → tasks →
analyze → a bounded **corrective `do-while` loop** (implement → review, repeating
while the deterministic review verdict is `REJECTED`) → a **terminal review gate**
that fails closed unless the verdict is `APPROVED`. Forward-seam phase transitions
stay owned by the injected directives; the workflow never double-issues them, and
a fail-closed `specops reconcile` precondition keeps the ledger authoritative.

### `specops status show`

Read-only. Prints ledger state: feature, branch, phase, active task, task counts
(pending / in progress / done / orphaned), and the review-cycle history. Never
mutates; on a legacy, too-new, unsupported, or malformed ledger it still prints a
best-effort summary plus a one-line diagnostic.

### `specops status init-spec [<name>]`

Creates `<feature_dir>/status.yaml` from the packaged scaffold, syncing task IDs
from `tasks.md`. Usually run for you by the tasks directive.

### `specops status migrate`

Upgrades the active feature's ledger to the current schema. Idempotent
(`already current` when there is nothing to do). A legacy ledger is migrated
losslessly — phases, tasks, evidence, and review cycles are preserved and the
original is backed up under `.specify/.specops-backup/` first. A too-new or
unsupported schema is refused, leaving the ledger untouched. State changes also
migrate automatically on first write, so running this is optional.

### `specops status rebaseline`

Re-anchors the ledger's recorded **branch** and **baseline** to the current
workspace — the explicit escape hatch for when the identity gate refuses a state
change after a deliberate branch rename or history rewrite. It never changes the
bound **feature** identity (if the resolved feature no longer matches, it fails
closed), and it is a normal state change (advances the revision).

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

Read-only gate. Verifies every recorded ledger commit is reachable from `HEAD`
and every `DONE` task has evidence. Intermediate tasks may intentionally have no
commit when commit granularity is per user story. Exit 1 on any divergence.

```bash
specops reconcile || exit 1   # preflight before review
```

### `specops review`

Read-only gate. Runs the deterministic review gates cheapest-first with early
stop: **reconcile → lint → test → working tree/effective diff → drift**. The first
failing gate stops the run and prints its evidence to stderr (exit 1); a full
pass prints a per-gate report to stdout (exit 0) that lists the effective-diff
files — the exact scope the review agent then reads. Ledger parse errors keep
exit 2. Runs from any directory inside the repo, never writes to the ledger or
any repository file, needs no specific ledger phase, and never prompts — safe
as a CI step.

The terminal **drift gate** (Feature 010) rejects the review when any
effective-diff path is `unexplained` — neither declared in `plan.md` nor recorded
via `specops trace acknowledge`. Planned and `discovered-and-acknowledged` paths
pass, and SpecOps/Speckit-managed artifacts (`specs/**`, `.specify/**`,
`specops.json`) are excluded as methodology state. See `specops trace` below.

```bash
specops review                # local: gate-check the current change
```

As a CI gate:

```yaml
# .github/workflows/ci.yml (step)
- run: pip install speckit-specops
- run: specops review
```

As an automated gate inside a Speckit workflow (replaces a human
approve/reject gate; the YAML is yours, no SpecOps coupling):

```yaml
- id: review
  type: shell
  run: specops review
  on_fail: abort
```

### `specops consistency`

Read-only gate. Verifies every `SC-\d+` in the spec has ≥ 1 task with a matching
`[SC-xxx]` tag, and every `plan.md` path declaration carries a valid action
suffix (`(create)`/`(modify)`/`(remove)`). Exit 1 on violation.

### `specops context init | validate | resolve | explain`

The **context map** (`.specify/specops/context-map.yaml`) is a versioned,
stack-neutral description of your repository's contexts — which paths each area
governs, the files an agent should read per lifecycle phase, inter-context
dependencies, gates, and risk. It is read deterministically; the same map and
inputs always produce the same ordered result.

- `specops context init` — scaffold a starter map (idempotent; never overwrites).
- `specops context validate` — check the map; reports every defect in one pass
  (invalid/unsafe pattern, duplicate id, ambiguous ownership, dangling
  dependency, dependency cycle, unsupported version). Exit 1 on any defect.
- `specops context resolve --path <p> | --id <id> [--phase <phase>]` — return the
  governing context and its ordered, phase-specific read set, with a cycle-safe,
  deduplicated expanded read set drawn from dependencies.
- `specops context explain --path <p> | --id <id> [--phase <phase>]` — the ordered
  reason trace: candidates considered, the winner, and which specificity
  dimension decided it.

The map is **consumed** in the lifecycle by three more read-only commands:

- `specops context plan-check [--plan <p>] [--phase <phase>]` — validate a plan's
  declared context topology (a `**SpecOps-Contexts**: …` line) against the map and
  display the minimal phase read set. Blocks (exit `1`) on a missing declaration,
  an unknown declared context, or a declared path owned by an undeclared context;
  an unowned declared path is non-blocking. Existence-agnostic.
- `specops context impact [--path <p> …]` — the contexts affected by a change: the
  owning context plus its transitive **reverse** dependents, each attributed to an
  `ownership`/`dependency`/`policy` edge. Omit `--path` to derive the change set
  from Git (clean tree → empty, exit `0`; not-a-repo / no-baseline → exit `2`).
- `specops context stale` — context-map patterns matching zero **Git-tracked**
  files (moved/removed), with the owning context; never edits the map.

Consuming these also snapshots **context provenance** (resolved context ids + map
digest, or an explicit `{map: none}`/`{map: invalid}` marker) into every task and
review-cycle ledger record (schema v3), and `specops review` surfaces a
non-blocking warning when the map changed since planning.

All commands accept `--json` for a stable, versioned machine surface. Exit codes:
`0` success (including the supported "no map present" and "no matching context"
states), `1` a blocking/unsound map, `2` a usage error. Path matching is
gitignore-style globbing; on overlap the most specific pattern wins (longer
literal prefix → fewer wildcards → more segments), and a genuine tie is reported
as ambiguous ownership. Consumption by planning and review arrives in a later
feature; this ships the deterministic foundation.

### `specops trace classify | validate | report | acknowledge`

**End-to-end traceability** (Feature 010) connects each spec Success Criterion
forward through its tasks, contexts/paths, commits, evidence, and review findings,
and classifies every **effective-diff** path (feature branch vs the ledger
baseline, renames decomposed) into one closed set — so review blocks *unexplained*
drift without rejecting legitimate discoveries.

- `specops trace classify [--path <p> …]` — label each effective-diff path
  `planned` (declared in `plan.md`, or owned by a plan-declared context),
  `discovered-and-acknowledged` (recorded via `acknowledge`), or `unexplained`.
  Omit `--path` to derive the change set from Git (clean tree → empty, exit `0`;
  not-a-repo / no-baseline → exit `2`). Read-only.
- `specops trace validate` — fail closed (exit `1`) on any `unexplained` path or
  trace defect: an uncovered Success Criterion, a completed task without evidence
  (or a user-story-final task without a commit), a dangling reference, or
  contradictory ownership. Commit existence is deferred to `specops reconcile`.
- `specops trace report` — render the full chain (Success Criteria → tasks →
  commits → evidence → findings), with discoveries listed distinctly.
- `specops trace acknowledge <path> --task <id> --reason "<why>"` — record a
  one-time, path-level acknowledgement of a genuine discovery so it stops being
  `unexplained`. Idempotent for an identical record; fails closed (exit `2`) on a
  conflicting or unknown-task acknowledgement; a no-op for an already-planned path.

Acknowledgements live in the ledger (schema **v4**, migrated forward
automatically). All commands accept `--json` for a stable, versioned surface, and
map onto the `0`/`1`/`2` exit-code taxonomy with a `status` field.

### `specops handoff finding … | authorize | close | validate | report | import | render`

**Structured corrective handoffs** (Feature 011) make review findings and
correction authorization first-class, versioned ledger state — so a rejected
review can be resumed from repository state alone and approval is impossible while
any **blocking** finding is unverified.

- `specops handoff finding add --severity <blocking|advisory> --rule "…" --file <p>
  [--line <n>] --action "…" [--expected-evidence "…" --closure "…"]` — record a
  finding with a stable `R<round>-F<NN>` id in the current review round. Blocking
  findings require expected evidence + closure criteria.
- `specops handoff finding fix <id> --task <id> --commit <sha> …
  (--evidence <CLASS>:<summary> | --auto)` — `OPEN → FIXED`, linking the correction.
- `specops handoff finding verify <id>` — `FIXED → VERIFIED` (mechanical
  precondition: evidence present + links resolve; no auto-verify). Illegal
  transitions fail closed (exit `2`).
- `specops handoff finding dismiss <id> --reason "…"` — withdraw a false-positive
  or superseded finding to a terminal `DISMISSED` state (audited reason) so it no
  longer gates approval, without fabricating a fix.
- `specops handoff authorize --path <p> …` — record the round's authorized
  corrective paths (a change outside them surfaces as `unexplained` via `trace`).
- `specops handoff close` — close the handoff once every blocking finding is
  `VERIFIED` (idempotent; exit `1` while any remain).
- `specops handoff validate` — fail closed (exit `1`) on a dangling reference, a
  blocking finding missing closure criteria, a contradictory state, or a duplicate
  id. `specops handoff report` — render every finding and the remaining blocking
  set. Both read-only.
- `specops handoff import [--round <n>]` — import legacy revision prose into
  advisory findings. `specops handoff render --round <n>` — project the structured
  findings to a compatible `revisions/revision-X.md`.

Findings live in the ledger (schema **v5**, migrated forward automatically); the
Markdown revision report is a rendered projection of that authoritative state.
`specops status transition-phase DONE` fails closed while any blocking finding is
unverified; a repository with no structured findings degrades to the prior gate.

### `specops --version`

Prints the version and exits. Works anywhere.

## Configuration — `specops.json`

| Key | Purpose | Default |
|---|---|---|
| `test_command` | Command run by `complete-task --auto` | `pytest` |
| `lint_command` | Lint gate run by `specops review` (empty = skipped) | `""` |
| `skills_dir` | Directory the review prompt loads skills from | `.specify/skills` |

Unknown keys are preserved on re-init.

## The `/specops-review` command

Installed by `specops init` (the name follows the layout's separator, e.g.
`/specops-review` for Claude skills). Not a CLI command — a packaged prompt that
drives the review agent cheapest-rejection-first:

1. Load skills from `skills_dir`.
2. `specops review` — the CLI runs all deterministic gates (reconcile,
   lint, test, working tree); any non-zero exit is an immediate REJECTED
   without reading a single line of code.
3. Surgical review of effective-diff files only.
4. Write `revisions/revision-X.md` and record the `APPROVED`/`REJECTED` outcome.

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
