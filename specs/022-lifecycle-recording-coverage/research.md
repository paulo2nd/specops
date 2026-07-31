# Research: Lifecycle Recording Coverage

**Feature**: 022 | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

All plan-time decisions the spec and roadmap deferred are resolved here. Facts
were verified against the worktree (file:line refs), never assumed.

## R1 — Converge ledger semantics: append via the existing sync, exposed as an explicit CLI

**Decision**: Converge-appended tasks enter the ledger by **append**, reusing
the existing `_sync_tasks` semantics (`src/specops/status.py:105`: new IDs →
`PENDING`, vanished IDs → `orphaned: true` preserved, existing entries —
including completed ones — preserved by ID). The seam is a new **additive** CLI
subcommand `specops status sync-tasks` that performs exactly this sync
explicitly and reports what changed; a `--check` mode validates the recording
path (ledger loadable, `tasks.md` readable) and reports what *would* be
appended without writing.

**Rationale**:
- The ledger already syncs lazily inside `start-task`/`complete-task`
  (`status.py:375`, `status.py:531`) — the merge semantics exist and are
  deterministic; the gap is that nothing records the mutation *at the converge
  seam*, leaving a window where `tasks.md` and the ledger silently disagree.
  An explicit sync at the seam closes that window with zero new merge logic.
- Completed entries must survive (spec Edge Cases) — `_sync_tasks` preserves
  them by ID; determinism scenario (US1-4) holds because sync is a pure
  function of `tasks.md` IDs + prior ledger state.
- `--check` gives the before-mutation fail-closed precondition (R2) a precise,
  diagnostic-rich primitive with the frozen exit contract (0 ok / 2
  infrastructure-or-data error).

**Alternatives considered**:
- **Rebaseline** (`status rebaseline`, `status.py:834`): rejected — it exists
  to re-bind ledger identity after branch renames/history rewrites; using it
  for scope growth would reset provenance and risk completed-entry loss.
- **Lazy sync only** (do nothing, let the next `start-task` pick tasks up):
  rejected — the mutation stays unrecorded until someone starts a task, which
  is exactly the silent-divergence window FR-003 forbids.
- **New bespoke append command with its own merge logic**: rejected — Rule 8 /
  reuse; `_sync_tasks` is already the single owner of merge semantics.

## R2 — Fail-closed before mutation: `sync-tasks --check` as the precondition

**Decision**: A new **`before_converge`** hook (mandatory, `optional: false`)
delivers a converge pre-directive: if the repository is not SpecOps-managed →
explicit no-op, proceed (Rule 5). If managed, run `specops status sync-tasks
--check`; any non-zero exit (or the CLI being absent while `specops.json`
exists) → **stop-and-ask without mutating** — converge does not run. The
existing `specops reconcile` remains the backstop for mutations that bypass
the directive entirely (already true today).

**Rationale**: matches the clarified spec (fail-closed **before mutation**,
exit code as gate) and the existing directive idiom (bare fail-closed
transitions with stop-and-ask). The diagnostic is specific because `--check`
distinguishes: no ledger, corrupt ledger (exit 2), unreadable `tasks.md`.

**Alternatives considered**: post-hoc detection via reconcile only (rejected by
clarification Q3 — divergence would exist until the next check); reusing bare
`specops reconcile` as the precondition (rejected — it validates commit
ancestry, not the recording path; its diagnostics would not name the missing
recording step as FR-003 requires).

## R3 — Recording after converge: sync + non-blocking coverage surface

**Decision**: A new **`after_converge`** hook (mandatory, `optional: false`)
delivers the converge post-directive: the agent first tags every appended task
with `[SC-xxx]` coverage tags (the tagging obligation sits in the directive —
clarification Q2), then runs `specops status sync-tasks` to record the append,
then runs `specops consistency` and **reports** its coverage output without
gating on it — an untagged task surfaces as missing coverage, never blocks
(record, do not validate). Zero-append runs are handled by `sync-tasks`
reporting "no changes" (exit 0).

**Rationale**: keeps the CLI recording-only (FR-004) while the directive owns
the semantic obligation; `specops consistency` already implements SC-coverage
checking (`src/specops/consistency.py`) — no new checker.

## R4 — Pre-ledger recording seam: transparent buffering inside `record-step`

**Decision**: `specops status record-step` becomes **pre-ledger-safe**. When
the feature ledger does not exist yet, the decision `{step, decision, at}` is
written to a feature-scoped buffer file
`specs/<feature>/.specops-pending-steps.json` (atomic write via `fsutil`;
same replace-by-step semantics as the ledger path, `status.py:344`). At ledger
creation, `cmd_init_spec` (`status.py:240`) **drains** the buffer into
`workflow.skipped_steps` and deletes the buffer file. When the ledger already
exists, behavior is unchanged (direct write). Decisions buffered for a run
abandoned before ledger creation are discarded with the feature directory —
inert until then, never blocking (clarification Q4).

**Rationale**:
- The #50 fix deferred workflow recording to after the tasks step because
  `record-step` requires the ledger; buffering generalizes that fix at the
  right layer (the CLI), making recording work in **any** entry mode and at
  the decision's natural moment.
- Feature-scoped file (not a global registry): garbage-collected with the
  feature dir, no cross-feature contamination, deterministic path.
- Ledger schema untouched — stays **v7** (`ledger.py:35`); the buffer is a
  SpecOps-owned transient artifact, not ledger state.

**Alternatives considered**:
- **Earlier ledger creation** (init-spec at specify): rejected — contradicts
  the constitutional seam ("the ledger is created at the tasks stage",
  Principle IV) and reshapes a frozen lifecycle for a bookkeeping need.
- **Retroactive artifact inspection at init-spec** (infer decisions from
  spec.md sections / checklist files): rejected — fragile (analyze leaves no
  reliable artifact) and cannot distinguish "skipped" from "not yet run".
- **Global buffer under `.specify/specops/`**: rejected — stale entries for
  abandoned features would accumulate outside any feature's lifecycle.

**Contract-freeze note**: today `record-step` before the ledger exists fails
(exit 2). Turning that failure into buffered success is an **additive
capability** (an error path becomes a success path; no successful behavior
changes shape). No frozen contract test pins the pre-ledger failure
(verified: `tests/unit/test_frozen_*` do not exercise `record-step`); the #50
ordering test (`tests/unit/test_workflow_definition.py:81`) exists to enforce
the workaround and is superseded by this feature (updated, not deleted — it
inverts to assert recording sits at the gates).

## R5 — Slash-command parity: record-on-run hooks + derive-skip at the next seam

**Decision**: two complementary mechanisms, both writing through
`record-step`:

1. **Run decisions** — three new native hooks, `after_clarify`,
   `after_checklist`, `after_analyze` (mandatory, `optional: false`), each
   delivering a minimal directive: if SpecOps-managed, run
   `specops status record-step <step> --decision run` (buffered
   transparently pre-ledger per R4); otherwise no-op (Rule 5).
2. **Skip decisions** — derived at the next mandatory seam, in both modes,
   via the additive `record-step … --decision skip --if-absent` flag (records
   only when the step has no decision in buffer or ledger; otherwise a
   reported no-op — added by analysis remediation U1, since no read surface
   exposes recorded decisions and a blind write could overwrite an explicit
   `run`): the **tasks** directive (ledger-creation seam) derives
   `clarify`/`checklist` (both precede tasks in the lifecycle, so absence at
   this seam **is** the skip); the **implement** directive derives `analyze`
   at session start (its window closes when implementation begins).

In workflow-driven runs the native gates keep recording explicit choices
(existing `record-step` shell steps) — the derived defaults are no-ops there
by construction of `--if-absent`.
With buffering available, the workflow's record steps **move back adjacent to
their gates** (undoing the #50 deferral at the workflow layer).

**Rationale**: Spec Kit's command skills already honor
`hooks.before_/after_<command>` for clarify/checklist/analyze (verified in
`.claude/skills/speckit-clarify/SKILL.md` et al.), so registration is purely
additive in `_HOOK_SPECS` (`src/specops/extension.py:46`). Derivation at the
next seam is deterministic and mode-independent — parity without ever
prompting the human or forcing a step (FR-008).

**Alternatives considered**: asking the human for skip confirmation at the
tasks seam (rejected — obstructs; spec forbids forcing decisions);
recording skip only in workflow mode (rejected — breaks parity, the feature's
point).

## R6 — Workflow converge step: optional gate inside the corrective round

**Decision**: In `src/specops/templates/workflows/specops/workflow.yml`, the
corrective-round branch (`corrective-round` if-step) gains, after
`open-corrective-round`: a native gate `converge-gate` ("Run
/speckit.converge to reconcile the task list before the corrective round?",
options `[run, skip]`), a `converge-record` shell step (`specops status
record-step converge --decision {{ steps.converge-gate.output.choice }}`),
and an `if` step running `command: speckit.converge` on `run`. The
`_OPTIONAL_STEPS` tuple gains `"converge"` (additive value; `skipped_steps`
entry shape unchanged, ledger stays v7).

**Rationale**: the clarified placement (Q1: corrective region) is where
converge earns its keep — after a REJECTED review reveals gaps, before the
corrective implement round. The ledger necessarily exists there, so no
buffering interplay. Gate-per-round is bounded by the existing
`max_iterations: 3`. In slash-command mode there is no converge decision
point, by design (spec FR-001a): running converge records through R1/R3;
not running it records nothing.

**Alternatives considered**: a single pre-loop converge gate (rejected — before
any review has run there is nothing to reconcile against); making converge a
required round step (rejected — spec forbids making optional steps
mandatory).

## R7 — taskstoissues: verified read-only, protected by a regression test

**Decision**: `/speckit.taskstoissues` registers **no** SpecOps hook and gets
**no** directive. Verification is a permanent automated regression test
(clarification Q5): (a) a fixture `extension install` produces a manifest with
no `before_/after_taskstoissues` entries and the hook registry equals the
documented set exactly (guarding against accidental future additions);
(b) a fixture ledger is byte-identical across the SpecOps surfaces involved
(install/update touch no ledger). The read-only contract is stated in
`docs/commands.md` and both READMEs.

**Rationale**: the skill's write surface is external only (GitHub issues via
MCP; verified `.claude/skills/speckit-taskstoissues/SKILL.md` — it reads
`tasks.md`, never edits repo files), and it invokes no `specops` command, so
ledger state cannot change. The trivial-directive contingency (spec FR-005)
is therefore not activated.

## R8 — `--if-needed` asymmetry: documented as a deliberate contract

**Decision**: document — in `docs/commands.md` (transition-phase section) and
as a comment block in `workflow.yml` — that the workflow definition uses
`transition-phase … --if-needed` (idempotent engine re-runs after
resume/re-entry) while the injected directives use bare fail-closed
transitions with stop-and-ask (an unexpected phase in an agent session is a
human question, not a no-op). No behavior change.

## Constitution touchpoint (anticipated amendment)

Adding recording directives for converge/clarify/checklist/analyze broadens
Principle IV's **Ledger & Phase Wiring** directive ("directives into every
phase-bearing Speckit stage") to the auxiliary and optional lifecycle
commands. Precedent (Features 010–013): a MINOR constitution amendment lands
during `/speckit-implement` in the same change set as the template updates.
