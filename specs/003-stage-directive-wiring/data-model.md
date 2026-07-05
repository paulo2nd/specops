# Phase 1 Data Model: Stage-Wide Directive Wiring

This feature adds no persisted schema. The "entities" are the injection targets,
the directive assets, and the phase mapping the directives drive. All are
in-memory or file assets.

## Entity: Prompt-target record

Returned per integration by `speckit.resolve_prompt_targets()`.

| Field | Type | Before | After |
|---|---|---|---|
| `integration` | str | ✓ | ✓ |
| `separator` | str | ✓ | ✓ |
| `plan_path` | Path | ✓ | ✓ |
| `implement_path` | Path | ✓ | ✓ |
| `specify_path` | Path \| None | — | **added** |
| `tasks_path` | Path \| None | — | **added** |

**Resolution rule**: each new path is located with the best-effort helper
`_find_optional_prompt_file(root, files, agent, sep, role)` using
`role="specify"` and `role="tasks"`. Best-effort: it returns a `Path` when the
manifest lists the entry and the file exists, otherwise `None` — a missing
specify/tasks prompt is skipped, not an error. `plan_path`/`implement_path`
remain fail-closed (`ManifestResolutionError`). This keeps partial Speckit
layouts working (graceful degradation, FR-008/SC-006).

## Entity: Stage directive asset

Packaged templates under `src/specops/templates/directives/`.

| Asset | State | `block_id` | Purpose |
|---|---|---|---|
| `specify.md` | create | `specify` | Informational: SpecOps active; language policy; ledger created at tasks. No ledger op. |
| `tasks.md` | create | `tasks` | `[SC-xxx]` tag rule (authoritative) + `init-spec` + walk phase to `TASKS`. |
| `plan.md` | modify | `plan` | Existing content minus the full SC-tag paragraph (replaced by a pointer). |
| `implement.md` | modify | `implement` | Existing ledger loop + `transition-phase IMPLEMENT` (start) + `transition-phase REVIEW` (end). |

**Injection invariants** (unchanged, enforced by `inject_block`/`remove_block`):
- Additive: appended at EOF when absent; content outside markers untouched.
- Idempotent: re-run yields `unchanged` when byte-identical.
- Reversible: `remove_block` restores byte-identical pre-injection state.

## Entity: Phase state machine (reference, unchanged)

`PHASES = [SPECIFY, PLAN, TASKS, IMPLEMENT, REVIEW, DONE]`. Transitions are
single-step-forward, with the sole exception `REVIEW → IMPLEMENT (-r REJECTED)`.
Entering `REVIEW` opens a review cycle.

### Stage → ledger action mapping (what the directives drive)

| Ledger phase before | Stage prompt seam | Directive-issued command(s) | Ledger phase after |
|---|---|---|---|
| (none) | specify | — | (none) |
| (none) | plan | — | (none) |
| (none) | tasks: after `tasks.md` | `init-spec` | `SPECIFY` |
| `SPECIFY` | tasks (cont.) | `transition-phase PLAN` → `transition-phase TASKS` | `TASKS` |
| `TASKS` | implement start | `transition-phase IMPLEMENT` | `IMPLEMENT` |
| `IMPLEMENT` | implement end | `transition-phase REVIEW` | `REVIEW` (cycle opened) |
| `REVIEW` | `/specops-review` | `transition-phase DONE -r APPROVED` / `IMPLEMENT -r REJECTED` | `DONE` / `IMPLEMENT` |

**Guard clause on every directive**: if the `specops` CLI is unavailable at run
time, the block is skipped and the stage completes normally (FR-008).

## Validation rules surfaced (not new code, but the directives must honor them)

- `init-spec` fails if the ledger already exists → the tasks directive MUST treat
  "already exists" as success (idempotent re-run), not as a stage-blocking error
  (FR-012, US1 scenario 2).
- `transition-phase` fails on a non-adjacent target → the tasks directive MUST
  issue the steps in order and MUST fail safe (surface, not corrupt) if the
  current phase is unexpected (edge case: out-of-order stages).
