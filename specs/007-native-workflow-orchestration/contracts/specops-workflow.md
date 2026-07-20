# Contract: The `specops` Workflow Definition

The shipped `.specify/workflows/specops/workflow.yml`. Composed **only** of Spec Kit native step
types — SpecOps adds none (FR-002). Below is the normative step graph (illustrative YAML; exact IDs
finalized in implementation). This is a *contract on structure*, not an implementation.

## Step graph (normative order)

```text
1.  specify            command  → speckit.specify
2.  clarify-gate       gate     → "Run clarify? [run/skip]" (default run); record via specops status
3.  clarify            command  → speckit.clarify            (skipped if gate=skip)
4.  checklist-gate     gate     → "Run checklist? [run/skip]" (default run); record
5.  checklist          command  → speckit.checklist          (skipped if gate=skip)
6.  plan               command  → speckit.plan
7.  reconcile-pre      shell    → specops reconcile --json   (fail-closed precondition)
8.  readiness-gate     gate     → "Approve spec+plan before tasks?" (approve/reject; on_reject: abort)   [FR-004]
9.  tasks              command  → speckit.tasks
10. analyze-gate       gate     → "Run analyze? [run/skip]" (default run); record
11. analyze            command  → speckit.analyze            (skipped if gate=skip)
12. ledger-init        shell    → specops status init-spec / transition to TASKS   (via CLI only)  [FR-008]
13. corrective-loop    do-while:
      body:
        a. reconcile-pre   shell → specops reconcile --json          (precondition of state change)  [FR-010]
        b. implement       command → speckit.implement
        c. review          shell → specops review --json             (deterministic gate)
        d. record-verdict  shell → specops status transition-phase … (-r APPROVED | -r REJECTED)     [FR-017]
      condition: review.verdict == "REJECTED"
      max_iterations: <native default>                                                               [FR-015]
14. terminal-gate      shell    → specops review --json ; fail closed if verdict != APPROVED         [FR-019]
15. done               shell    → specops status transition-phase REVIEW→DONE -r APPROVED
```

## Contract rules

- **C1 (native only)**: every step `type` ∈ {command, shell, gate, do-while, if, switch}. No custom
  SpecOps step type. — FR-002/025, SC-002.
- **C2 (integration-neutral)**: lifecycle `command` steps use `{{ inputs.integration }}` / `auto`; no
  integration-specific dispatch in SpecOps. — FR-003.
- **C3 (readiness gate)**: step 8 is a human `gate` between `plan` (6) and `tasks` (9) with
  `on_reject: abort` (or return); `tasks` is unreachable until approved. — FR-004/007/008.
- **C4 (optional skip)**: each optional step (clarify/checklist/analyze) is preceded by a `gate`
  defaulting to run; the choice is recorded in the ledger `workflow.skipped_steps`. — FR-006.
- **C5 (state ownership)**: only `shell → specops status …` steps mutate the ledger; `command` steps
  never do. — FR-008/009.
- **C6 (reconcile precondition)**: a `specops reconcile` shell step precedes every state-changing
  `status` step and runs once after resume. — FR-010.
- **C7 (corrective loop)**: a single `do-while` conditioned on `review.verdict == REJECTED`, bounded
  by native `max_iterations`; each REJECTED round is a new review cycle. — FR-015/016/017.
- **C8 (terminal gate)**: a deterministic `specops review` step after the loop that fails closed on
  verdict ≠ APPROVED; NOT a human gate. — FR-019.
- **C9 (completion)**: `DONE` is reached only via the terminal APPROVED path. — FR-020, SC-008.

## Tested by

`tests/unit/test_workflow_definition.py` (validates the shipped YAML against Spec Kit's
`validate_workflow`, and asserts C1–C9 structurally) and
`tests/integration/test_workflow_orchestration.py` (drives the graph end-to-end).
