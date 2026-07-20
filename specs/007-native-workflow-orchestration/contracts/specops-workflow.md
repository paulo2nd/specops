# Contract: The `specops` Workflow Definition

The shipped `.specify/workflows/specops/workflow.yml`. Composed **only** of Spec Kit native step
types — SpecOps adds none (FR-002). Below is the normative step graph (illustrative YAML; exact IDs
finalized in implementation). This is a *contract on structure*, not an implementation.

## Step graph (normative order)

As implemented in `src/specops/templates/workflows/specops/workflow.yml` (16 top-level steps;
the corrective loop nests its body). IDs match the shipped file.

```text
specify              command  → speckit.specify
clarify-gate         gate     → "Run clarify? [run/skip]"; clarify-record shell → specops status record-step
clarify              if       → then: speckit.clarify        (choice == 'run')
checklist-gate       gate     → "Run checklist? [run/skip]"; checklist-record shell → specops status record-step
checklist            if       → then: speckit.checklist      (choice == 'run')
plan                 command  → speckit.plan
readiness-gate       gate     → "Approve spec.md and plan.md before generating tasks?" (on_reject: abort)  [FR-004]
tasks                command  → speckit.tasks   (its after_tasks Principle IV directive creates the ledger + transitions — not re-issued)  [FR-008]
analyze-gate         gate     → "Run analyze? [run/skip]"; analyze-record shell → specops status record-step
analyze              if       → then: speckit.analyze        (choice == 'run')
corrective-loop      do-while  condition: steps.review-soft.output.data.verdict == 'REJECTED'; max_iterations: 3  [FR-015]
      body:
        reconcile-pre-impl  shell → specops reconcile --json                         (fail-closed precondition)  [FR-010]
        implement           command → speckit.implement
        review-soft         shell → specops review --json --soft  (output_format: json; exit 0 so the loop can branch on verdict)
        corrective-round    if (verdict == 'REJECTED') → specops status transition-phase IMPLEMENT -r REJECTED --if-needed  [FR-017]
terminal-gate        shell    → specops review           (HARD: exit ≠ 0 if verdict != APPROVED → aborts, never reaches done)  [FR-019]
done                 shell    → specops status transition-phase DONE -r APPROVED --if-needed
```

**Soft vs hard review (implementation discovery)**: a non-zero shell exit FAILS the step and aborts
the run, so the **in-loop** review is `--soft` (always exit 0; verdict in the JSON) to *drive* the
`do-while`, while the **terminal** review is hard (`specops review`) to *fail closed*. The verdict is
consumed via `output_format: json` (exposed under `output.data`).

**Ownership note (analyze C1)**: forward-seam ledger creation and `SPECIFY→…→REVIEW` transitions are
owned by the injected Principle IV directives that fire on the lifecycle `command` steps; the workflow
does **not** re-issue them. The workflow owns only the corrective `REVIEW→IMPLEMENT -r REJECTED` round,
the terminal gate, the final `REVIEW→DONE`, and the additive skip records. Every workflow-issued
`specops status` call is idempotent-tolerant (`--if-needed`: no-op-and-continue if already in state).

## Contract rules

- **C1 (native only)**: every step `type` ∈ {command, shell, gate, do-while, if, switch}. No custom
  SpecOps step type. — FR-002/025, SC-002.
- **C2 (integration-neutral)**: lifecycle `command` steps use `{{ inputs.integration }}` / `auto`; no
  integration-specific dispatch in SpecOps. — FR-003.
- **C3 (readiness gate)**: step 8 is a human `gate` between `plan` (6) and `tasks` (9) with
  `on_reject: abort` (or return); `tasks` is unreachable until approved. — FR-004/007/008.
- **C4 (optional skip)**: each optional step (clarify/checklist/analyze) is preceded by a `gate`
  defaulting to run; the choice is recorded in the ledger `workflow.skipped_steps`. — FR-006.
- **C5 (state ownership)**: the ledger is mutated only via SpecOps CLI — either the injected Principle
  IV directives that fire on the lifecycle `command` steps (sole owner of forward-seam creation +
  transitions) or the workflow's own `shell → specops status …` steps (corrective round, final DONE,
  skip records). The workflow never duplicates a directive-owned transition, and its `specops status`
  calls are idempotent-tolerant. The Spec Kit engine never writes the ledger. — FR-008/009, analyze C1.
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
