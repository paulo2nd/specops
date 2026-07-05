# Contract: Stage Directive Content

Defines the required instruction points each directive block MUST convey. Exact
prose is finalized during implementation; these are the mandatory semantics. All
text in English (FR-010). Every block opens with the graceful-degradation guard.

## Common guard (all four blocks)

> If the `specops` command is not available in this environment, skip the
> SpecOps steps in this block and complete the stage normally.

## `specify.md` (block_id: `specify`) — NEW, informational

MUST convey:
- SpecOps is active on this repository; the execution ledger will be created
  during the tasks stage (not now).
- Language policy: author spec prose in any language; keep structural tokens
  (`SC-\d+`, `T\d+`, action suffixes) parseable.
- No ledger command is run at this stage.

MUST NOT: instruct any `status`/`transition-phase` call (no ledger yet).

## `tasks.md` (block_id: `tasks`) — NEW

MUST convey, in order:
1. **Coverage tags (authoritative)**: every generated `tasks.md` task line
   carries one or more `[SC-xxx]` tags using only Success Criteria IDs present in
   `spec.md`; do not invent IDs; multiple IDs comma-separated inside one bracket.
2. **Create the ledger**: after `tasks.md` is finalized, run
   `specops status init-spec`. If it reports the ledger already exists, treat
   that as success and continue (do not abort the stage).
3. **Make the phase truthful**: bring the ledger to the `TASKS` phase by running
   `specops status transition-phase PLAN` then
   `specops status transition-phase TASKS`. If a transition reports an unexpected
   current phase, stop and surface it rather than forcing further writes.

MUST NOT: hand-edit `status.yaml` or `tasks.md` checkboxes.

## `plan.md` (block_id: `plan`) — MODIFY

MUST keep: empirical path verification, action suffixes, `specops consistency`
gate, stop-and-ask conditions (all existing).

MUST change: replace the full "SC Coverage Tags" paragraph with a one-line
pointer — coverage tags are authored during the tasks stage; the plan stage only
ensures each Success Criterion is coverable. No conflicting restatement (FR-009).

## `implement.md` (block_id: `implement`) — MODIFY

MUST keep: operational silence, the ledger loop (`start-task` / `complete-task`
with per-user-story commit granularity), skills load, reconcile preflight,
stop-and-ask gates (all existing).

MUST add:
1. **At session start, before the first `start-task`**: run
   `specops status transition-phase IMPLEMENT` to move the ledger from `TASKS`
   to `IMPLEMENT`. If already in `IMPLEMENT`, continue.
2. **After the final task is `DONE`**: run
   `specops status transition-phase REVIEW` to open the review cycle, so
   `/specops-review` has an open cycle to record into. Then hand off to review.

## Behavioral acceptance (maps to spec)

| Contract point | Spec ref |
|---|---|
| tasks block creates ledger post-`tasks.md` | US1, FR-004, SC-002 |
| "already exists" is non-blocking | US1-S2, FR-012 |
| tasks block walks phase to TASKS | US2-S1, FR-005 |
| implement start → IMPLEMENT | US2, FR-005 |
| implement end → REVIEW (opens cycle) | US2-S2, FR-006 |
| tags authored in tasks stage | US3, FR-003, SC-003 |
| plan/tasks non-conflicting | FR-009 |
| guard clause on every block | FR-008, SC-006 |
| all four blocks idempotent/reversible | FR-007, SC-005, SC-007 |
