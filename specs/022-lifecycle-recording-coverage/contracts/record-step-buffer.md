# Contract: `specops status record-step` — pre-ledger buffering (extended, additive)

**Purpose**: make optional-step decision recording work before the ledger
exists (FR-006/FR-007), generalizing the issue #50 fix at the CLI layer.

## Invocation

```
specops status record-step <step> --decision <run|skip> [--if-absent]
```

`<step>`: `clarify | checklist | analyze | converge` (**`converge` is new**).

**`--if-absent`** (new, additive): record only when the step has **no**
decision yet (in the ledger or the buffer); when one exists, do nothing and
exit 0 reporting the existing decision. This makes skip derivation a single
deterministic, idempotent command — no read surface exposes
`workflow.skipped_steps` (verified: `status show` omits it), so without this
flag a derivation step would have to blind-write and could overwrite an
explicit `run` (violating the parity record). Without the flag, behavior is
unchanged (replace-by-step).

## Behavior

| Ledger state | Behavior |
|---|---|
| Exists | Unchanged: replace-by-step write to `workflow.skipped_steps` via the standard write path. |
| Absent (pre-tasks) | **New**: replace-by-step write to `specs/<feature>/.specops-pending-steps.json` (atomic, `fsutil`); success message notes the decision is buffered. Previously this invocation exited 2 — the error path becomes a success path (additive capability; no frozen test pins the old failure — research R4). |

## Drain (at `init-spec`)

`specops status init-spec` (ledger creation) drains buffered entries into the
new ledger's `workflow.skipped_steps` and **deletes** the buffer file, in the
same operation that syncs `tasks.md`. Unknown buffer `version` → discard with
a stderr note, never fatal. No buffer file → no-op.

## Abandoned-run semantics (clarification Q4)

A buffer whose feature never reaches `init-spec` is inert — read by nothing,
blocking nothing — and is discarded with the feature directory. A fresh run
starts clean; re-records replace prior entries in place.

## Skip derivation (directive-owned, both entry modes)

- **tasks directive** (ledger-creation seam): after `init-spec` →
  `record-step clarify --decision skip --if-absent` and
  `record-step checklist --decision skip --if-absent` (their lifecycle
  window has closed; an existing decision — explicit gate choice or drained
  buffer — is never overwritten).
- **implement directive** (session start): `record-step analyze --decision
  skip --if-absent`.
- Idempotent in both modes by construction of `--if-absent` — no
  decision-existence check is needed in the directive (no read surface
  exposes recorded decisions). Recording never forces a step or blocks on a
  skip (FR-008).

## Exit codes (frozen 0/1/2 contract)

0 on recorded (ledger or buffer) and on the `--if-absent` no-op (existing
decision reported); 1 on validation/precondition failures (unknown step,
invalid decision, unresolvable feature — the existing `SpecopsError`
convention, unchanged); 2 on infrastructure/data errors (corrupt ledger).
Unchanged from today except the pre-ledger success path.
