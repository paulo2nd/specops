# SpecOps command reference

The complete reference for every `specops` command, the `/specops-review`
directive, and how they compose into the review workflow. For an overview,
install instructions, and the quick start, see the [README](../README.md).

> **Binding to a surface?** The exit codes and JSON contracts documented here are
> frozen for 1.0 — see **[docs/stability.md](stability.md)** for the per-surface
> stability policy and the additive-vs-breaking rules.

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

It drives specify → clarify/checklist (human skip gates, each decision recorded
at its gate — pre-ledger decisions are buffered and drained into the ledger at
creation, Feature 022) → plan → **human planning-readiness gate** (no tasks
until approved) → tasks → analyze → a bounded **corrective `do-while` loop** →
a **terminal review gate** that fails closed unless the verdict is `APPROVED`.
Forward-seam phase transitions stay owned by the injected directives; the
workflow never double-issues them, and a fail-closed `specops reconcile`
precondition keeps the ledger authoritative.

Each corrective round also offers **converge** as a recorded optional step
(Feature 022): after a rejected round the workflow asks whether to run
`/speckit.converge` to reconcile the task list with what the codebase still
needs; the run/skip choice is recorded like every optional-step decision, and
a converge run records its appended tasks through `specops status sync-tasks`
(see below).

Each corrective round (Feature 016) runs the deterministic `specops preflight` gate
as a cheap **fail-closed precondition** and then — only when it passes — drives the
**semantic `/specops-review`** so the workflow performs and enforces the *actual*
code review, not just the mechanical gates. The loop re-iterates while the gate is
`REJECTED` **or** any **blocking finding** is still unverified, and completion is
blocked while a blocking finding remains unverified (Feature 011). Enforcement is
always-on: a run whose review records no findings **degrades automatically** to the
prior deterministic-only behavior (no toggle), and a run that cannot perform the
review (the `specops.review` command unavailable) **fails closed** rather than
completing silently.

### The `specops-lite` workflow (lightweight lane)

For small, reversible changes that don't warrant the full lifecycle, `specops
extension install` also registers a second SpecOps-owned workflow, `specops-lite`.
**You never drive the `specops` CLI for the lane** — an injected Principle IV directive
makes the agent recognize a small/reversible change, *propose* the lane (a human
confirmation, never auto-classifying), and then drive every `specops lane *` command
itself. Your only interactions are native gates: eligibility, two attestations, and —
if something trips — halt or promote.

The lane keeps a dedicated `lane.yaml` record (its own schema, never `status.yaml`);
your ordinary branch commits are the working record. Its non-pierceable safety core is
**hybrid**: four categories are detected from the diff (migration, secret, dependency,
destructive — via a generic, non-removable pattern floor, extensible through
`lane.safety` in `specops.json`), and two that aren't generically diff-detectable
(root-cause, public-contract) are enforced by always-on human attestation. A trip offers
only **halt** or **promote** — there is no recordable bypass.

Closure runs the deterministic gate-profile suite (fail-closed) and records structured
evidence plus a rendered `retrospective.md`. If the change outgrows the lane, **promotion
is lossless**: it synthesizes a full ledger at the `PLAN` phase, preserving every commit
and carrying the lane's context so the change receives full planning and review.

The `specops lane` commands (`start`, `status`, `check`, `attest`, `close`, `promote`)
are agent/workflow-facing, non-interactive, and expose the stable `--json` outcome
contract — they compose as gates, exactly like `specops preflight`.

### `specops status show`

Read-only. Prints ledger state: feature, branch, phase, active task, task counts
(pending / in progress / done / orphaned), and the review-cycle history. Never
mutates; on a legacy, too-new, unsupported, or malformed ledger it still prints a
best-effort summary plus a one-line diagnostic.

### `specops status init-spec [<name>]`

Creates `<feature_dir>/status.yaml` from the packaged scaffold, syncing task IDs
from `tasks.md`. Usually run for you by the tasks directive. Optional-step
decisions recorded before the ledger existed (see `record-step`) are drained
into `workflow.skipped_steps` here and the buffer file is deleted (Feature 022).

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

- `--auto`: harvests `started_commit..HEAD` commits + diff as `CODE_DIFF`
  evidence. It runs **no** test (Feature 024) — test verification lives at the
  review gate (`specops preflight`), not at task close.
- `--evidence "CLASS:summary"`: caller-supplied, with `CLASS` in
  `CLI_LOG | TEST_REPORT | SCREENSHOT_PATH | CODE_DIFF`.

### `specops status transition-phase <phase> [-r APPROVED|REJECTED] [--if-needed]`

Advances the phase one step forward. Two transitions require `-r`:

```bash
specops status transition-phase DONE -r APPROVED      # approved → close the feature
specops status transition-phase IMPLEMENT -r REJECTED # rejected → send back for rework
```

Entering `DONE` requires the latest review cycle to be `APPROVED`.
`--if-needed` makes the command a no-op (exit 0) when the ledger is already in
the target phase — for idempotent workflow steps that may re-run (Feature 007).

The `--if-needed` split is a **deliberate contract** (Feature 022): the
workflow definition uses `--if-needed` because the engine may re-run steps on
resume/re-entry, where an already-reached phase is a no-op, not an error. The
injected directives use **bare fail-closed transitions with stop-and-ask**
instead — in an agent session an unexpected current phase is a question for
the human, never something to silently skip past.

### `specops status record-step <clarify|checklist|analyze|converge> --decision <run|skip> [--if-absent]`

Records the human's run/skip decision for an optional lifecycle step
(Feature 007), so skipped steps are on the record instead of silently absent.
Feature 022 extends it:

- **Pre-ledger buffering**: before the ledger exists the decision is written to
  the feature-scoped buffer `specs/<feature>/.specops-pending-steps.json`
  (atomic, replace-by-step, carrying the recording branch as provenance) and
  drained into `workflow.skipped_steps` at ledger creation (`init-spec`, or
  lane promotion), which deletes the buffer only **after** the ledger write
  persists. At the drain seam, entries recorded on a different branch than the
  one the ledger binds to — and individually invalid entries — are discarded
  with a stderr note, never silently. The buffer lives in a committed
  directory, so it may transiently appear in commits between record and drain —
  harmless; it is removed at drain, and a buffer whose run is abandoned before
  ledger creation is inert and disappears with the feature directory.
- **`--if-absent`**: record only when the step has no decision yet (buffered or
  in the ledger); otherwise report the existing decision and change nothing
  (exit 0). This is how the tasks/implement directives derive `skip` for steps
  whose lifecycle window closed — one idempotent command that never overwrites
  an explicit choice, in both entry modes (workflow-driven and slash-command).
- **`converge`** is a recordable step: the full workflow's corrective round
  offers converge through a gate and records the choice. In slash-command mode
  there is no converge decision point — running converge is recorded through
  its recording path (`status sync-tasks`), and not running it records nothing.

### `specops status sync-tasks [--check] [--json]`

Explicitly records a task-list mutation into the ledger (Feature 022) — the
**converge recording seam**. Applies the same merge `init-spec`/`start-task`
already use: new `tasks.md` IDs enter as `PENDING`, vanished IDs are preserved
as `orphaned: true`, existing entries (including completed ones) are untouched,
and a previously-vanished ID that **reappears** in `tasks.md` is revived (its
`orphaned` flag cleared) so a live task is never left excluded from counts and
gates. Deterministic and idempotent; a zero-change run succeeds with "no
changes".

- `--check`: validate the recording path and report what would change,
  **without writing** — a pure dry-run (it creates no backup even for a
  migratable old-schema ledger) and the converge pre-mutation precondition.
  The converge pre-directive runs it **before** converge touches `tasks.md`
  and stops-and-asks on any non-zero exit, so an unrecorded task-list mutation
  is never silent.
- `--json`: stable object `{appended, orphaned, revived, unchanged, check}`.
- Exit codes: `0` recorded / no changes / check passed; `1` blocking
  precondition (no ledger yet, `tasks.md` missing); `2` infrastructure or data
  error (corrupt ledger). It records state and gates nothing — SC-coverage
  judgment stays with `specops consistency` (record, do not validate).

### Lifecycle coverage: converge and taskstoissues (Feature 022)

Every Spec Kit lifecycle command has a defined SpecOps story:

- **`/speckit.converge`** carries a directive pair: `before_converge` fails
  closed **before mutation** via `specops status sync-tasks --check`
  (stop-and-ask, `tasks.md` untouched), and `after_converge` has the agent tag
  every appended task with `[SC-xxx]` coverage labels, record the append via
  `specops status sync-tasks`, and report `specops consistency` output without
  gating on it — an untagged task surfaces as missing coverage, never blocks.
  On a repository without SpecOps both directives are no-ops.
- **`/speckit.taskstoissues`** is **read-only with respect to ledger state**:
  SpecOps registers no hook and no directive for it, it invokes no `specops`
  command, and its only write surface is the external issue tracker. This
  contract is protected by a permanent regression test
  (`tests/unit/test_taskstoissues_readonly.py`); if the upstream command ever
  mutates repository state, it receives a trivial recording directive.

### `specops reconcile`

Read-only gate. Verifies every recorded ledger commit is reachable from `HEAD`
and every `DONE` task has evidence. Intermediate tasks may intentionally have no
commit when commit granularity is per user story. Exit 1 on any divergence.

```bash
specops reconcile || exit 1   # sanity-check state before the gate
```

### `specops preflight`

> Renamed from `specops review` (Feature 017). `specops review` still works as a
> **deprecated alias** — identical behavior plus a one-line deprecation notice on
> stderr — and will be removed no earlier than the next minor release. Migrate CI and
> workflow steps to `specops preflight`. "review" now names only the REVIEW phase, the
> `/specops-review` directive, and the review-cycle verdict.

Read-only gate. Runs the deterministic gate suite cheapest-first with early
stop: **reconcile → the selected gate-profile suite → working tree/effective diff →
drift**. Since Feature 012 the profile suite replaces the fixed lint/test gates
(with no config it is the default `lint`/`test` profile — see `specops gate` below);
each profile gate carries an outcome disposition (`required`/`optional`/`skipped`/
`cached`/`failed`/`unavailable`), a per-gate timeout, and — in `--json` — its
disposition, reason, covered inputs, and supporting evidence id. A required
failure/unavailability blocks; an optional one does not. The first failing gate
stops the run and prints its evidence to stderr (exit 1); a full
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
specops preflight             # local: gate-check the current change
```

Flags: `--json` emits the stable outcome envelope; `--soft` (with `--json`)
always exits 0 so the JSON verdict — not the exit code — drives a workflow
do-while loop (Feature 007); `--sarif` emits a SARIF 2.1.0 projection of the
review findings and exits 0 (read-only export, Feature 012).

As a CI gate:

```yaml
# .github/workflows/ci.yml (step)
- run: pip install speckit-specops
- run: specops preflight
```

As an automated gate inside a Speckit workflow (replaces a human
approve/reject gate; the YAML is yours, no SpecOps coupling):

```yaml
- id: preflight
  type: shell
  run: specops preflight
  on_fail: abort
```

### `specops consistency`

Read-only gate. Verifies every `SC-\d+` in the spec has ≥ 1 task with a matching
`[SC-xxx]` tag, and every `plan.md` path declaration carries a valid action
suffix (`(create)`/`(modify)`/`(remove)`). Exit 1 on violation.

### `specops doctor [--json]`

Read-only diagnostic (Feature 014). Inspects every SpecOps-specific surface for the
**active feature only** and reports a per-domain, severity-classified result with a
deterministic next action. Ten domains: environment readiness, CLI/extension
compatibility, integration, legacy artifacts, configuration, feature identity, ledger
schema + integrity, context-map health, workflow/ledger divergence, and preflight gate
availability. It mutates nothing, runs fully offline, and never executes `specify` or a
gate command — it *defers* to the native `specify check` / `specify workflow status` by
pointing at them.

The environment domain also reports **git availability**: SpecOps invokes the `git`
executable directly (no bundled git library), so a missing or nonfunctional `git` on
PATH is a `blocking` finding; when present, the finding is `ok` and shows the detected
version. `specops init` performs the same check as its first step and fails closed with
a clear diagnostic when `git` is unavailable.

Each finding carries a severity (`ok` / `warning` / `blocking` / `execution-error`), a
human message, and — when not `ok` — both a stable `next_action_code` and human text.
The overall verdict is the most severe finding; the exit code follows the outcome
contract: **0** (ok/warning), **1** (blocking), **2** (execution-error). `--json` emits
a stable, versioned document (`output_version: 1`; consumers must tolerate unknown
domains and codes).

```bash
specops doctor            # human-readable health report
specops doctor --json     # stable JSON for CI (gate on the exit code)
```

### `specops report [--json]`

Read-only compact status of the active feature (Feature 014): identity, branch, phase,
task counts (pending / in progress / done / orphaned / total), active task, review
cycles + open blocking findings, and workflow lane. Complements the human-only
`specops status show` by adding a stable machine surface; mutates nothing. Exit **0**
normally (a missing active feature yields null fields), **2** on an unreadable ledger.

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
review-cycle ledger record (schema v3), and `specops preflight` surfaces a
non-blocking warning when the map changed since planning.

The read set is also consumed at **implement time** (Feature 023): the implement
directive resolves the IMPLEMENT-phase context package for each context declared
in the plan (`specops context resolve --id <cid> --phase implement --json`) at
session start and seeds the agent's reads with the union of the resolved
packages. The read set is guidance plus record — never a gate, and never a
ceiling on discovery: an out-of-set read blocks nothing, reads needed to
implement a task correctly are always in scope even when outside the union,
and a discovery that changes an undeclared path follows the
existing `specops trace acknowledge` flow; this step records nothing by itself.
Without a map the step is a supported no-op; any non-zero exit of the resolution
step means the session proceeds without read-set scoping.

All commands accept `--json` for a stable, versioned machine surface. Exit codes:
`0` success (including the supported "no map present" and "no matching context"
states), `1` a blocking/unsound map, `2` a usage error. Path matching is
gitignore-style globbing; on overlap the most specific pattern wins (longer
literal prefix → fewer wildcards → more segments), and a genuine tie is reported
as ambiguous ownership. Consumption by planning and review arrives in a later
feature; this ships the deterministic foundation.

### `specops trace classify | validate | report | acknowledge | link`

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
  Use `--out-of-feature` (no `--task`) instead for a tooling/methodology path that
  belongs to no task — a skill, agent, or `.claude/` file touched to support the
  feature's development. The record is marked `out_of_feature` (carries no task) so
  audits can tell tooling changes apart from in-feature discovered scope; the drift
  gate treats it as `discovered-and-acknowledged` all the same.
- `specops trace link --task <id> --commit <sha> [--commit <sha> …]` — bind
  explicit commit shas to a task's `commits`, clearing a `missing-link` (user story
  with no commit) that `complete-task`'s range harvest could not record — commits
  made out of task order, or a binding known only after the task was `DONE`. Runs
  regardless of task status; idempotent with union semantics (never drops an
  existing binding); resolves short shas to full form; fails closed (exit `2`) on an
  unknown task or a sha not reachable from `HEAD` (so it can never create a
  `dangling-reference`). Replaces the former hand-edit of `status.yaml`.

Acknowledgements and links live in the ledger (schema **v4**, migrated forward
automatically). All commands accept `--json` for a stable, versioned surface, and
map onto the `0`/`1`/`2` exit-code taxonomy with a `status` field.

### `specops gate list | validate | report` (Feature 012)

Read-only inspection of the **gate-profile suite** and **structured evidence**. Gate
profiles live in a versioned `.specify/specops/gate-profiles.yaml` (a sibling of the
context map): an ordered list of gates, each with a `command`, a single applicability
predicate (`always` / `contexts` / `paths` globs / named-key `risk`, matching the
context map's free-form risk mapping), a `timeout` (seconds; default `600`), a
`required` flag (default `true`), and failure semantics. When the file is absent — or
its `profiles` list is empty — SpecOps synthesizes the default `lint`/`test` profile
from `specops.json`, so an upgraded repository behaves exactly as before until a
profile is authored (never zero gates).

```yaml
# .specify/specops/gate-profiles.yaml
output_version: 1
profiles:
  - name: unit-tests
    command: "pytest -q"
    applies: { always: true }
    timeout: 600
    required: true
  - name: schema-guard
    command: "scripts/check-migrations.sh"
    applies: { paths: ["migrations/**"], risk: { persisted: true } }
    timeout: 120
```

- `specops gate list [--json]` — the deterministically selected suite for the current
  effective diff, with a machine-readable reason per gate.
- `specops gate validate [--json]` — fails closed (exit `1`) with one distinct
  diagnostic per config defect (duplicate name, empty command, bad timeout, unparseable
  predicate, dangling reference, unsupported version).
- `specops gate report [--json] [--sarif]` — the verdict provenance (each gate's
  disposition/reason/inputs/evidence id) plus the ledger's structured evidence records.

The suite runs inside `specops preflight` (there is no standalone runner). Every gate run
and every task/finding evidence link is recorded as a **structured evidence record** —
a cache-key-derived id (`EV-<hex12>`), producer, command, exit code, timestamp, commit
range, affected paths, summary, and an optional local-artifact `sha256` digest — stored
in the `status.yaml` ledger (schema **v6**, migrated forward automatically),
alongside the retained legacy
`<CLASS>:<summary>` string. A gate whose full cache key still matches a prior record is
`cached` (not re-run). Opt-in `--sarif` on `preflight`/`gate report` emits a SARIF 2.1.0
projection of the review findings.

The ledger migrates **v5 → v6** automatically on the next state-changing command:
legacy evidence strings are back-filled into structured records without loss (idempotent;
prior valid ledger preserved on failure).

### `specops handoff record-scope | finding … | authorize | close | validate | report | import | render`

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
- `specops handoff record-scope [--json]` — record this review round's git-derived
  reviewed scope and print the files to read (Feature 025; see below). Takes no range
  argument — the scope is derived, never reviewer-supplied.
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
  findings to `revisions/revision-X.md` as a readable model (verdict/round/role/range
  header, findings grouped by severity with id/state/rule/action/evidence, and the
  remaining-blocking set) with the 010-compatible `[File]:[Line] - [action]` flat lines
  kept as a trailing appendix (the only import-parseable section).

Findings live in the ledger (schema **v5**, migrated forward automatically); the
Markdown revision report is a rendered projection of that authoritative state.
`specops status transition-phase DONE` fails closed while any blocking finding is
unverified; a repository with no structured findings degrades to the prior gate.

### `specops handoff finding import-json | import-sarif | promote`

**External review ingestion** (Feature 015) lets a stronger or specialized external
reviewer — a multi-agent bug hunt, a static analyzer (CodeQL, semgrep), or a human —
feed the **same** corrective handoff through a stable, versioned, stack-neutral input
contract. SpecOps **records** the external judgment as a snapshot and **gates**
deterministically on it (Principle II/VI); it never runs, bundles, or re-verifies the
reviewer (Principle IV).

- `specops handoff finding import-json --file <path|->` — import findings from a
  versioned JSON contract (`contract_version: 1`; see
  [`findings-input.schema.json`](../specs/015-external-review-ingestion/contracts/findings-input.schema.json)).
- `specops handoff finding import-sarif --file <path|->` — import findings from a
  **SARIF 2.1.0** document (opt-in; the inverse of the Feature 012 SARIF *output*
  adapter). Its `tool.driver` name/version becomes the finding's producer.
- `specops handoff finding promote <id> --closure "…" --expected-evidence "…"` —
  the **human, audited** escalation of an imported finding to `blocking`.

Every imported finding lands **`advisory` regardless of any producer-declared
severity** — no external producer can block a merge on its own. Each records its
**producer** (tool + version) and a **per-path reviewed digest**; `specops handoff
report` flags a finding **stale** when the path it points at has changed since it was
reviewed (path granularity — an unrelated change never stales it). Import is
**all-or-nothing** (any defect names every problem and writes nothing; an empty
document is a no-op) and **idempotent** (a re-import refreshes staleness in place,
never duplicates, and never demotes a promotion). Withdrawal reuses `handoff finding
dismiss`. Promotion attaches the closure criteria + expected evidence a blocking
finding needs, so the finding is verifiable through the unchanged Feature 011
lifecycle. Ledger schema **v7**, migrated forward automatically.

### Review round integrity (Feature 025)

Hardens the multi-round semantic review so no approval can rest on an incomplete
defect hunt and the loop cannot cycle unbounded — all **recording, never judging a
finding's merit**.

- **`specops handoff record-scope [--json]`** — run it at the start of Step 3 (once
  the gates pass). It records the round's reviewed range in the ledger, derived from
  git: an **anchor** round (the first to reach Step 3) covers the full
  `baseline..HEAD`; a **corrective** round covers `prev_to..HEAD` plus the files of
  any still-open findings. It prints the exact files to read — replacing the older,
  ambiguous "read the working-tree gate list" instruction. Idempotent per round; if
  the prior round's HEAD was rewritten (rebase/squash) it re-anchors over the full
  diff rather than failing. `--json` adds `round`, `review_role`, `reviewed_range`,
  and `scope_paths` to the outcome envelope.
- **Coverage guard** — `specops status transition-phase DONE -r APPROVED` fails
  closed (exit `1`) unless the recorded rounds cover the whole feature, judged by
  commit reach: an anchor from the current baseline **and** no product change after
  the last reviewed HEAD (`frontier..HEAD`). It reports the specific reason (no
  anchor, an unresolvable frontier → re-run `record-scope`, or the unreviewed tail
  paths). Only product paths count — a `status.yaml` bookkeeping write can neither
  pollute nor block. A ledger with no reviewed-scope records (legacy) degrades to the
  prior cycle-result gate. `reviewed_range` endpoints are exempt from `reconcile` (a
  rebased-away review HEAD never blocks it).
- **Round cap** — `review_round_cap` in `specops.json` (default `10`) bounds the
  loop. When rejecting a round would exceed it, `transition-phase IMPLEMENT -r
  REJECTED` halts and asks a human instead of opening another round: it records a
  `review_halt` marker, leaves the round open (no fabricated verdict), and exits
  `1`. Resume by raising the cap, resolving the open findings and approving, or
  rebaselining (which clears stale reviewed-scope records).

Ledger schema **v8**, migrated forward automatically.

### `specops --version`

Prints the version and exits. Works anywhere.

## The `/specops-review` command

Installed by `specops init` (the name follows the layout's separator, e.g.
`/specops-review` for Claude skills). Not a CLI command — a packaged prompt that
drives the review agent cheapest-rejection-first:

1. Load skills from `skills_dir`.
2. `specops preflight` — the CLI runs all deterministic gates (reconcile, the
   selected gate-profile suite — the default `lint`/`test` profile when no
   `gate-profiles.yaml` exists — working tree, drift); any non-zero exit is an
   immediate REJECTED without reading a single line of code.
3. Surgical review of effective-diff files only.
4. Write `revisions/revision-X.md` and record the `APPROVED`/`REJECTED` outcome.

## Review workflow: where agent and tool findings fit

Two audiences use the CLI. **Workflows/agents** drive the *state* transitions
(`handoff finding add|fix|verify|close`, `status transition-phase`, …); **humans**
read the *visibility* surfaces (`handoff report`, `trace report`, `status show`, …)
and make the decisions (approve/reject, escalate/dismiss). You rarely type the
state commands by hand — the injected directives do, on your behalf.

Know which command reviews and which enforces:

- **`specops preflight`** (the deterministic gate; formerly `specops review`, now a
  deprecated alias — Feature 017) runs reconcile, the gate-profile suite, the
  working-tree and drift gates, and returns a verdict. It is a **mechanical gate**, not a code review — it does not
  read your code for bugs. Its honest name is the point: an author composing a
  workflow no longer mistakes it for the review step.
- **`/specops-review`** (the injected review directive) is where a real code review
  happens: it orchestrates the **agent's own** review — a disciplined, scoped read
  of the diff against the spec's Success Criteria, the plan, and the Constitution —
  and records the non-conformities as structured findings. This is the always-on
  baseline reviewer.
- **`specops handoff …`** records and **enforces** those findings: approval is
  impossible while any blocking finding is unverified.

A stronger or specialized reviewer — a multi-agent bug hunt (e.g. an LLM code
review), a static analyzer, or a human — is a **source of findings**, not the gate.
During the `REVIEW` phase the `/specops-review` directive orchestrates the flow
below (you can also run it by hand when not using the workflow):

1. `specops preflight` — the deterministic gate suite. Reject early; do not read code
   until it passes.
2. Review the diff — the built-in `/specops-review` agent read, and/or a stronger
   external reviewer.
3. Record each non-conformity as a structured finding (`specops handoff finding
   add …`). Findings from an **automated** reviewer are best recorded as `advisory`
   and **escalated to `blocking` by a human** — an LLM's confidence is not a merge
   gate. (Roadmap Feature 015 adds a bulk `import-json`/SARIF ingestion so any
   tool's findings feed the handoff directly, invoked by the directive.)
4. Triage: `dismiss` false positives (with a reason); fix the real ones, then
   `finding fix` → `finding verify` → `handoff close`.
5. `specops status transition-phase DONE -r APPROVED`.

**When the full flow is worth it — and when it is overhead.** The handoff's value
is proportional to **stakes, hands, and sessions**, not to code quality: it pays
off when a review spans multiple people/agents or sessions, when a less-experienced
team is learning the shape of the process, or when someone will later audit *why* a
change was approved. For a small, reversible, single-session change it is mostly
ceremony — a lighter proportional lane is planned (roadmap Feature 013). Use the
full flow deliberately, not reflexively.

