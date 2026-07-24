# Research: Review Composition in the Workflow

All decisions are grounded in the current worktree: the shipped definition
`src/specops/templates/workflows/specops/workflow.yml`, the review directive
`src/specops/templates/review.md`, the CLI (`src/specops/cli.py`), command
registration (`src/specops/extension.py`, `src/specops/speckit.py`), the handoff
surface (`src/specops/handoff.py`), and Feature 007's verified engine findings
(`specs/007-native-workflow-orchestration/research.md`).

## R1 — How the workflow invokes the semantic review

- **Decision**: Add a native `command: specops.review` step inside the corrective
  loop. It resolves to the SpecOps-registered `/specops-review` command file, whose
  manifest id is built as `specops{sep}review` by
  `extension.register_commands()` (`extension.py:181`) using the integration's
  `invoke_separator` (default `.`, `speckit.py:204`) — the same dotted convention the
  existing lifecycle steps use (`command: speckit.specify`). The review command file
  is installed by the same `install()` path that installs the workflow
  (`extension.py:337-338`), so the two are co-present.
- **Rationale**: The review is an integration slash-command (a Principle IV
  directive), exactly the thing a native `command:` step invokes. Feature 007 already
  drives `speckit.*` commands this way (007 R6); `specops.review` is the same shape.
- **Alternatives**: (a) A `shell:` step running `specops review` — rejected: that is
  the *mechanical* gate, not the semantic agent review; it reads no diff and records
  no findings. (b) Relying on the `after_implement` directive to chain into
  `/specops-review` — rejected: that hand-off is prose guidance the engine does not
  execute; its non-execution is exactly the gap this feature closes.
- **Verified**: `extension.register_commands` builds id `specops{sep}review` and
  `install()` calls both `register_commands` and `install_workflow`.

## R2 — The findings-aware loop condition (primary unknown)

- **Decision**: Add a read-only `shell: specops handoff report --json` step
  (`output_format: json`) after the semantic review, and extend the do-while
  condition to:

  ```
  {{ steps.review-soft.output.data.verdict == 'REJECTED'
     or steps.handoff-report.output.data.remaining_blocking }}
  ```

  `handoff report --json` returns `data.remaining_blocking` — the list of unverified
  blocking finding ids (`handoff.py:589-590`, `cmd_report`). An empty list is falsy
  in Jinja2, so plain `or <list>` re-iterates iff blocking findings remain. This
  reuses the **existing** report surface (FR-008) with **no** handoff-CLI change.
- **Rationale**: The mechanical `review --json --soft` verdict is APPROVED whenever
  the code lints/tests/reconciles, even with an open *semantic* blocking finding — so
  the mechanical scalar alone cannot capture findings state; a second, findings-derived
  signal is required. `remaining_blocking` is precisely that signal and already exists.
- **Engine-capability risk & fallback**: Feature 007 verified conditions branch on
  JSON fields via the engine's `evaluate_condition` with `{{ … == '…' }}` (Jinja2
  templating). Compound `or` and list-truthiness are standard Jinja2 and expected to
  hold, but the engine is not installed in this dev environment to re-verify. **Fallback
  if truthiness is sandboxed**: use the explicit form
  `... or (steps.handoff-report.output.data.remaining_blocking | length > 0)`. **Deeper
  fallback if only scalar `==` is supported**: interpose an `if` step that maps a
  non-empty list to a recorded scalar the condition compares with `==`. The
  `test_definition_parses_in_real_speckit_engine` integration test (skipped when the
  engine is absent) is the gate that confirms the chosen form parses.
- **Alternatives**: (a) A new `specops handoff report` scalar field like
  `has_unverified_blocking` — rejected: the spec's non-goal forbids handoff-CLI
  changes, and FR-008 mandates deriving the signal from the existing report. (b)
  Probing ledger phase via a new `status show --json` — rejected: adds surface and
  couples the condition to phase semantics instead of the mandated report.

## R3 — Transition ownership (FR-009, avoid double-drive)

- **Decision**: The composed `command: specops.review` step performs the outcome
  transitions it **already owns** per `review.md` Step 4 — `handoff close` +
  `transition-phase DONE -r APPROVED` on approval, `transition-phase IMPLEMENT -r
  REJECTED` on a blocking finding. This feature adds **no** new transition. The
  workflow's pre-existing `open-corrective-round` (`IMPLEMENT -r REJECTED --if-needed`)
  and `done` (`DONE -r APPROVED --if-needed`) steps stay as idempotent-tolerant safety
  nets (Feature 007 R6). The `open-corrective-round` guard is scoped to the
  **mechanical** reject (`review-soft.verdict == 'REJECTED'`), since the review command
  owns the findings-reject transition.
- **Rationale**: Feature 007 settled that Principle IV directives are the sole owner
  of forward-seam transitions and workflow `status` steps are idempotent-tolerant
  (007 R6, analyze finding C1). The `/specops-review` directive is such a directive;
  composing it as a step keeps ownership where it already is.
- **Verified**: `review.md` Step 4 executes `transition-phase DONE`/`IMPLEMENT`;
  `status.cmd_transition_phase` requires `-r REJECTED` for REVIEW→IMPLEMENT and
  `transition-phase DONE` fails closed while a blocking finding is unverified (011).

## R4 — Fail closed when the review cannot run (FR-016)

- **Decision**: Invoke the semantic review as a **hard** `command:` step (no
  error-tolerance wrapper). If the `specops.review` command is unresolvable for the
  active integration, the engine aborts the run (execution failure) — the run cannot
  reach the terminal `done` step. This is the fail-closed behavior chosen in the
  2026-07-24 clarification (Q1). To surface it early (the clarification's SHOULD), add
  an integration test asserting the **co-installation invariant**: `install()` writes
  the review command file wherever it writes the workflow, so a workflow-present repo
  always has the review command.
- **Rationale**: The engine treats a hard command crash as an abort recoverable via
  `specify workflow resume` (007 R2), which is the correct fail-closed posture; an
  un-runnable review must never be mistaken for a clean review.
- **Distinction from degrade (R5)**: "cannot run" (command unresolvable → abort) is
  *not* "ran and found nothing" (empty `remaining_blocking` → complete). The two paths
  are structurally different: the former never reaches `handoff report`.
- **Note on the implement directive's "Graceful Degradation"**: that clause skips
  SpecOps steps when the `specops` CLI is absent in a *non-SpecOps* repo. The workflow
  only exists in SpecOps repos, so the review command is present; the hard step is the
  correct guarantee for the residual partial-install case.

## R5 — Automatic degrade with no configuration flag (FR-006, FR-015)

- **Decision**: Degrade is by **absence of findings**, not a toggle. A run whose
  semantic review records no blocking findings (or a legacy repo with no handoff
  state) yields `remaining_blocking == []`, so the do-while condition is driven purely
  by the mechanical verdict — identical to the pre-feature behavior. No opt-in/opt-out
  setting is added anywhere (FR-015).
- **Rationale**: Matches roadmap Rule 5 (degrade safely when a capability is absent)
  and the clarification's "always-on, auto-degrade" answer; keeps the surface minimal.
- **Verified**: `cmd_report` returns `remaining_blocking: []` when there are no
  findings (`handoff.py`), and a legacy repo with no `handoff` block reports an empty
  set — both falsy, so neither blocks.

## R6 — Ordering: mechanical gate first (FR-002, token discipline)

- **Decision**: Keep `review-soft` (`specops review --json --soft`) as the first
  review step in the loop body; guard the `command: specops.review` step with
  `if review-soft.output.data.verdict != 'REJECTED'` so the token-expensive semantic
  review runs **only** when the cheap mechanical gate passes. On a mechanical reject
  the loop opens a corrective round via the existing `open-corrective-round` step and
  skips the semantic review that round (Story 4).
- **Rationale**: Principle IV §18 mandates rejecting as early as possible before
  reading code; the review directive itself does mechanical-first internally, and the
  workflow mirrors that at the step level so a mechanical failure never spends review
  tokens.
- **Alternatives**: Run the semantic review unconditionally each round — rejected:
  wastes tokens on rounds that fail mechanically and contradicts FR-002.

## R7 — Verification strategy (non-CI-reproducible review)

- **Decision**: Two layers. (1) **Structural unit tests** over the parsed
  `workflow.yml` (extending `tests/unit/test_workflow_definition.py`): the loop body
  contains `review-soft` then a guarded `specops.review` command step and a
  `handoff report --json` step; the loop condition references both `REJECTED` and
  `remaining_blocking`; only native step types are used; the terminal gate is the hard
  `specops review`; no duplicate ids; ordering `corrective-loop < terminal-gate < done`.
  (2) **Integration tests** (`tests/integration/test_workflow_orchestration.py`): the
  co-installation invariant (R4); no new forward-transition/init-spec steps beyond the
  corrective round (extends the existing `test_workflow_has_no_forward_transition…`);
  and the degrade shape (a repo with no findings has an empty `remaining_blocking`, so
  read-only report + terminal gate leave the ledger unmutated).
- **Rationale**: Spec assumption — `command:` steps need a live agent and are not
  CI-reproducible; the end-to-end enforcement is proven by the composed CLI primitives'
  own unit/integration tests plus the engine-parse structural check, consistent with
  the Feature 007 verification note already in the shipped `workflow.yml` comments.
- **Alternatives**: A live-integration end-to-end acceptance run — retained as a
  manual `quickstart.md` scenario, not a CI gate.
