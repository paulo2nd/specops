# Contract: Finding Lifecycle & Blocking-Approval Invariant

## States

`OPEN` → `FIXED` → `VERIFIED`. Monotonic; no skips, no backward moves.

## Transition preconditions (fail ⇒ exit 2, state unchanged, nothing recorded)

| From → To | Precondition | On failure |
|---|---|---|
| `OPEN → FIXED` | `--task` resolves to a known ledger task; **≥1 commit**; actual `<CLASS>:<summary>` evidence present (`--evidence` or `--auto`) | `unknown-task` / `precondition-unmet` / `illegal-transition` |
| `FIXED → VERIFIED` | actual `evidence` present **and** task/commit links resolve (mechanical guard); recorded during a review pass | `precondition-unmet` / `illegal-transition` |
| `OPEN → VERIFIED` | — always illegal (must pass through `FIXED`) | `illegal-transition` |
| `X → (earlier)` | — always illegal | `illegal-transition` |

**No auto-verify**: satisfying the `VERIFIED` precondition never transitions a finding by itself;
the reviewer's `handoff finding verify` call is the closure judgment (Principle IV). The CLI
enforces only the mechanical guard (Principle II) — it never judges evidence adequacy.

## Two-surface coherence (guard vs audit)

- **Transition guard** (this contract) makes an invalid state *unreachable* via the CLI → exit 2.
- **`handoff validate`** (audit backstop) reports such a state only if a ledger was hand-corrupted
  or externally written → exit 1.

They never contradict: disjoint entry paths (live CLI vs external corruption).

## Blocking-approval invariant (feature-global)

`blocking_approval_check(data)` → ids of every `blocking` finding across **all** cycles' handoffs
with `state != VERIFIED`.

| Condition | Outcome |
|---|---|
| set is empty | approval permitted; every handoff is *closable* |
| set is non-empty | `APPROVED` recording and `DONE` entry fail closed (exit 1, `approval-blocked`), naming the ids |
| no handoffs present | empty by construction ⇒ degrade to Feature 006 cycle-result gate (FR-008) |

Advisory findings are **never** in the set (0% false-block, SC-003). Wired into
`status.cmd_transition_phase` at the DONE/APPROVED gate, before the existing Feature 006 check.

## Handoff close (FR-023)

`handoff close`: if any `blocking` finding in the current round's handoff is unverified →
`close-blocked` (exit 1, naming them). Else stamp `closed_at` (recorded, auditable) →
`handoff-closed`; a re-close is `handoff-already-closed` (exit 0, idempotent). The approval
invariant keys on **closability** (finding state), not on `closed_at`, preserving fresh-session
resumability (FR-020).
