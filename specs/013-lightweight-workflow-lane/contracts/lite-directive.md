# Contract: lite-lane injected directive (`templates/directives/lite.md`)

A Principle IV product directive that makes the agent recognize and *propose* the lightweight
lane, so SpecOps is driven by the agent rather than by a human operating the CLI (FR-022/FR-023).
Delivered as a template installed via the extension mechanism, exactly like the existing
lifecycle directives (`specify.md`, `plan.md`, `tasks.md`, `implement.md`, `review.md`).

## Delivery

- **Source**: `src/specops/templates/directives/lite.md`.
- **Native path**: injected as a lifecycle-hook prompt body at the lifecycle-entry seam (specify
  stage / pre-lifecycle) by `extension.py`, alongside the other directives; `extension remove`
  removes it.
- **Legacy path**: injected as a marker-delimited block by `initializer.py`, additively and
  idempotently, for parity with the other directives.

## Required behavior the directive MUST instruct

- **B-1 (recognize)**: assess whether the requested change is a lightweight-lane candidate —
  small and reversible, no safety-critical category apparent at first read.
- **B-2 (propose, never auto-classify)**: when it looks like a candidate, PROPOSE the
  `specops-lite` lane to the human and obtain explicit confirmation *before* entering it. The
  directive MUST NOT let the agent auto-enter the lane or record eligibility without the human
  (spec non-goal; Design Philosophy "record, do not silently decide").
- **B-3 (drive, don't delegate to the human)**: on confirmation, the agent runs the
  `specops-lite` workflow and issues the `specops lane *` commands itself; it MUST NOT ask the
  human to run any `specops` command.
- **B-4 (defer to the safety core)**: the directive does not itself judge the safety categories —
  it relies on `specops lane check` (diff-detectable) plus the always-on root-cause attestation
  gate. A change that trips the core is halted/promoted via the native gate, not rationalized by
  the agent.
- **B-5 (escalate on growth)**: if the change outgrows "small/reversible" mid-work, the agent
  proposes promotion (the native halt/promote gate) rather than silently continuing.

## Degradation & non-conflict

- **D-1 (no-op without SpecOps)**: when SpecOps is not initialized, the directive degrades to a
  no-op and the underlying Speckit prompt works standalone (Roadmap Rule 5) — asserted in
  `tests/unit/test_lite_directive.py`.
- **D-2 (no full-lane interference)**: the directive only *proposes* the lite lane for candidate
  changes; it never blocks or alters the full `specify → … → review` lifecycle for changes the
  human takes through the full workflow.

## Constitution note

Adding this directive extends the Principle IV directive list — a MINOR amendment authored during
`/speckit-implement` (Sync Impact Report updated, version bumped, no principle removed or
redefined), per the pattern established by Features 009–012.
