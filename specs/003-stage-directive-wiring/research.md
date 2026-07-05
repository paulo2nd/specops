# Phase 0 Research: Stage-Wide Directive Wiring

All technical unknowns were resolved by reading the existing implementation.
No external research was required — the feature reuses established mechanisms.

## R1 — How does injection work, and is it reusable for new stages?

**Decision**: Reuse `initializer.inject_block()` / `remove_block()` unchanged for
the new specify and tasks blocks.

**Rationale**: `inject_block(file_path, block_id, content)` already:
- appends a marker-delimited block (`<!-- SPECOPS:BEGIN <id> vN -->` …
  `<!-- SPECOPS:END <id> -->`) at EOF when absent (returns `created`),
- replaces content in place when present (`updated`),
- returns `unchanged` when byte-identical,
- never touches bytes outside the markers.

`remove_block()` deletes the block plus its preceding blank separator, restoring
a byte-identical pre-injection state. This directly satisfies FR-007 and SC-005
for any number of blocks, so no change to the injection engine is needed.

**Alternatives considered**: A dedicated multi-block injector — rejected as
redundant; the current function is per-`block_id` and composes fine.

## R2 — Can prompt-target resolution locate the specify and tasks prompts?

**Decision**: Extend `speckit.resolve_prompt_targets()` to also resolve
`specify_path` and `tasks_path` via the existing `_find_prompt_file(root, files,
agent, sep, role)` helper, called with `role="specify"` and `role="tasks"`.

**Rationale**: `_find_prompt_file` is already role-generic — it matches manifest
entries containing the stem `speckit{sep}{role}`. The Claude skills manifest
lists all stage prompts (verified: `.claude/skills/speckit-specify/SKILL.md`,
`.claude/skills/speckit-tasks/SKILL.md` exist and are manifest-listed). Only the
returned dict needs two more keys.

**Alternatives considered**: Deriving paths by string-substituting the plan path
(like `derive_review_path`) — rejected; manifest lookup is the project's
fail-closed convention and avoids guessing wrapper layouts.

## R3 — Where is the ledger created, and what phase does it start in?

**Decision**: The tasks directive instructs `specops status init-spec` after
`tasks.md` is finalized. `init-spec` does **not** require `tasks.md` but syncs
task IDs from it when present, so running it post-`tasks.md` yields a ledger
pre-populated with `PENDING` tasks — exactly what the implement loop needs.

**Rationale**: `cmd_init_spec` reads `tasks.md` via `_read_tasks_md` and calls
`_sync_tasks` only `if tasks_text`. The ledger template
(`templates/status.yaml`) sets `current_phase: "SPECIFY"`. `cmd_start_task` also
re-syncs tasks, so even a race is self-healing. This confirms the confirmed
scope: no CLI change.

**Alternatives considered**: Creating the ledger at the specify stage (phase
`SPECIFY`) — rejected by the requester because it needs `init-spec` to work
before `tasks.md` and to re-sync later (a CLI change).

## R4 — What transitions does `transition-phase` allow?

**Decision**: Phase directives must issue **single-step forward** transitions
only. `cmd_transition_phase` accepts `target_idx == current_idx + 1` plus the
one exception `REVIEW → IMPLEMENT` with `-r REJECTED`. `PHASES = [SPECIFY, PLAN,
TASKS, IMPLEMENT, REVIEW, DONE]`.

**Consequence for wiring** (ledger born at `SPECIFY`, created at tasks stage):

| Stage prompt | Ledger action(s) at the seam |
|---|---|
| specify | none (no ledger yet) — informational block only |
| plan | none (no ledger yet) |
| tasks | `init-spec`; then `transition-phase PLAN`; then `transition-phase TASKS` |
| implement (start) | `transition-phase IMPLEMENT` |
| implement (end) | `transition-phase REVIEW` (opens the review cycle) |
| review (`/specops-review`) | `transition-phase DONE -r APPROVED` **or** `IMPLEMENT -r REJECTED` (already wired) |

**Rationale**: Walking `SPECIFY→PLAN→TASKS` in the tasks directive keeps the
phase truthful without a CLI change. Entering `REVIEW` auto-opens a cycle
(`review_cycles.append(...)`), which is precisely what `/specops-review` needs to
record its result into — closing gap (c).

**Alternatives considered**: A single "jump to phase X" command — rejected;
would require changing `cmd_transition_phase` (out of scope) and would weaken the
state-machine guardrails.

## R5 — How is graceful degradation guaranteed (FR-008 / SC-006)?

**Decision**: Two layers. (1) Structural: if SpecOps was never initialized, no
block is injected, so the Speckit prompt is pristine and works standalone. (2)
Runtime prose: each injected block is prefixed with a guard — "If the `specops`
command is unavailable, skip the SpecOps steps in this block and complete the
stage normally." This covers the edge case where the block exists but the CLI is
absent from `PATH` at run time.

**Rationale**: The agent executes the prose; an explicit skip clause prevents a
hard failure without depending on shell semantics. Aligns with Principle VI
(don't swallow exit codes when the command *is* present).

**Alternatives considered**: A CLI "is-initialized" probe injected into every
block — rejected as heavier than a one-line guard and still agent-executed.

## R6 — De-duplicating the `[SC-xxx]` rule (gap d, FR-009)

**Decision**: Make the **tasks** directive the authoritative home of the
"every task line carries `[SC-xxx]`" rule (that is where `tasks.md` is
generated). The **plan** directive keeps its path-verification, consistency
gate, and stop-and-ask content, and its SC-tag paragraph is trimmed to a
one-line pointer ("Coverage tags are authored during the tasks stage; see the
tasks directive") so the two prompts do not restate conflicting instructions.

**Rationale**: Rule lives where it is applied; `specops consistency` then
enforces something the generating stage was actually told to do (SC-003).
Trimming rather than deleting keeps plan authors aware the requirement exists.

**Alternatives considered**: Duplicating the full rule verbatim in both — rejected
by FR-009 (avoid conflicting/competing instructions across prompts).
