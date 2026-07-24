# Data Model: Review Composition in the Workflow

This feature introduces **no persisted-schema change**. It adds no fields to the
Ledger v6, the handoff findings, the context map, or `specops.json`, and it changes
no JSON output contract. The "model" here is the **workflow-definition structure**
(the steps and condition added to `workflow.yml`) and the **existing read-only data**
it consumes. Persisted state is owned by prior features and is only *read* (via CLI)
or *transitioned* (by the review directive that already owns the transition).

## Consumed state (read-only, existing)

### Mechanical verdict — `specops review --json --soft`

- Source: `outcome.render("review", …)` → `data.verdict ∈ {APPROVED, REJECTED}`
  (`cli.py:239-288`). `--soft` forces exit 0 so the verdict drives the loop.
- Used by: the corrective-loop condition and the `if` guard on the semantic-review
  step (`review-soft.output.data.verdict`).
- Feature 016 change: none to the command; new *consumers* only.

### Remaining unverified blocking set — `specops handoff report --json`

- Source: `handoff.cmd_report` → `data.remaining_blocking: list[str]` (the unverified
  blocking finding ids) plus `data.findings` (`handoff.py:568-590`). Read-only;
  byte-for-byte non-mutating.
- Used by: the corrective-loop condition (`handoff-report.output.data.remaining_blocking`).
- Empty list ⇒ no unverified blocking findings ⇒ **auto-degrade** to the mechanical
  path (FR-006). Legacy repo / no handoff block ⇒ also empty ⇒ degrade.
- Feature 016 change: none to the command; new *consumer* only (FR-008).

### Finding lifecycle (unchanged, Feature 011)

- A finding has a stable id `R<round>-F<NN>`, `severity ∈ {blocking, advisory}`, and a
  state `OPEN → FIXED → VERIFIED` (or `DISMISSED`). Only **blocking** findings not yet
  `VERIFIED`/`DISMISSED` appear in `remaining_blocking`.
- Feature 016 does **not** add, remove, or reinterpret any finding state (non-goal).

## Transitioned state (owned elsewhere)

### Phase transitions — owned by the `/specops-review` directive

- On approval: `handoff close` + `status transition-phase DONE -r APPROVED`
  (fails closed while any blocking finding is unverified — Feature 011).
- On a blocking finding: `status transition-phase IMPLEMENT -r REJECTED`.
- Feature 016 composes the review step but **does not** issue these transitions
  itself (FR-009). The workflow's own `open-corrective-round` and `done` steps remain
  `--if-needed` idempotent-tolerant safety nets from Feature 007.

## Workflow-definition structure (the actual deliverable)

Additions/edits to `workflow.yml` (see `contracts/workflow-corrective-loop.md` for the
authoritative step contract):

| Element | Kind | Status | Purpose |
|---|---|---|---|
| `review-soft` | shell (`specops review --json --soft`) | existing | Mechanical fail-closed precondition; loop driver (FR-002) |
| `semantic-review` | command (`specops.review`) | **new** | Perform the actual code review; record findings; owned outcome transition (FR-001, FR-009) |
| guard on `semantic-review` | if (`review-soft…verdict != 'REJECTED'`) | **new** | Run the review only when the mechanical gate passes (FR-002) |
| `handoff-report` | shell (`specops handoff report --json`) | **new** | Expose `remaining_blocking` to the condition (FR-003, FR-008) |
| `corrective-loop.condition` | do-while condition | **edit** | Re-iterate while mechanical `REJECTED` **or** `remaining_blocking` non-empty (FR-003) |
| `open-corrective-round` | shell (`transition IMPLEMENT -r REJECTED --if-needed`) | existing | Mechanical-reject corrective round only (FR-009) |
| `terminal-gate` | shell (`specops review`, hard) | existing | Mechanical fail-closed guard before completion (FR-002) |
| `done` | shell (`transition DONE -r APPROVED --if-needed`) | existing | Idempotent completion; blocking-unverified fails closed via the transition (FR-004/FR-005) |

### Invariants

- **INV-1 (native only)**: every step uses a Spec Kit native type (`command`, `shell`,
  `if`, `do-while`); no SpecOps-authored primitive (Rule 8 / FR-007).
- **INV-2 (mechanical-first)**: `review-soft` precedes `semantic-review` in the body,
  and `semantic-review` is guarded by the mechanical pass (FR-002).
- **INV-3 (bounded)**: `corrective-loop.max_iterations` is unchanged from Feature 007
  (FR-010).
- **INV-4 (no new transitions)**: the only workflow-issued transitions remain the
  Feature-007 `open-corrective-round` and `done`, both `--if-needed` (FR-009).
- **INV-5 (fail-closed on unavailable review)**: `semantic-review` is a hard
  `command:` step; an unresolvable command aborts the run (FR-016).
- **INV-6 (auto-degrade)**: no configuration field gates enforcement; degrade is
  triggered solely by an empty `remaining_blocking` (FR-006/FR-015).
- **INV-7 (read-only inspection)**: `review-soft` and `handoff-report` do not mutate
  the ledger (existing read-only guarantees preserved).
