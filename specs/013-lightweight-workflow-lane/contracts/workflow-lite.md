# Contract: `specops-lite` workflow definition

`.specify/workflows/specops-lite/workflow.yml` — a second SpecOps-owned Spec Kit workflow,
installed additively alongside `specops` (never modifying the bundled `speckit` workflow or the
`specops` workflow). Composed of **native step types only** (`gate`, `prompt`, `shell`,
`command`, `if`) — SpecOps adds no engine, loop, or resume (Roadmap Rule 8; mirrors the note in
the existing `specops/workflow.yml`). SpecOps contributes only the `specops lane *` shell steps.

## Operating model (FR-022/FR-023) — agent-driven, human only at gates

- **Entry**: the injected lite-lane directive (`templates/directives/lite.md`) makes the agent
  recognize a small/reversible change and *propose* the lane via the `eligibility-gate` below.
  The human confirms at that gate; the agent then runs this workflow. The human never issues a
  `specops` command.
- **Who drives what**: every `specops lane *` step is a native `shell`/`command` step executed by
  the agent/workflow engine. The human meets ONLY native `gate`/`prompt` steps — eligibility
  confirmation, root-cause attestation, and (on a trip) the halt/promote choice.
- **No auto-entry**: recognition never auto-classifies; `lane-start` runs only after the human
  confirms the `eligibility-gate` (spec non-goal).

## Registration (delivered by generalized `extension.install_workflow`)

- Template source: `src/specops/templates/workflows/specops-lite/workflow.yml`.
- Installed to: `.specify/workflows/specops-lite/workflow.yml`.
- Registry: upsert key `specops-lite` in `.specify/workflows/workflow-registry.json`, preserving
  every foreign entry and the `specops`/`speckit` entries. Idempotent (content-hash compare).
- `extension remove` unregisters both `specops` and `specops-lite`.

## Step contract (structural — validated statically like the full workflow)

| Step (id) | Type | Purpose / SpecOps command |
|-----------|------|---------------------------|
| `eligibility-gate` | gate | present the versioned eligibility checklist; options `[confirm, cancel]`; `on_reject: abort`. |
| `lane-start` | shell | `specops lane start --answers … --json` — writes `lane.yaml`; fail-closed on ineligible. |
| `work` | command | `speckit.implement` (or the human's own edits) — commits are the working record (FR-005). |
| `safety-check` | shell | `specops lane check --json` (`output_format: json`) — flags diff-detectable categories. |
| `root-cause-attest` | prompt | always-on (FR-007 hybrid): "root cause confirmed or ambiguous?" → `specops lane attest --root-cause …`. |
| `stop-and-ask` | if / gate | when `safety-check` flags a category **or** attestation is `ambiguous`: gate with options `[halt, promote]` **only** (no bypass, FR-008). |
| `promote` | shell (guarded) | on `promote` choice: `specops lane promote --reason … --json` → hands off to the `specops` workflow at PLAN. |
| `close` | shell (guarded) | on a clean pass: `specops lane close --json` — fail-closed preflight + retrospective + evidence. |

## Behavioral guarantees the definition must encode

- **G-1** (FR-008 non-pierceable): the `stop-and-ask` gate exposes exactly `halt` and `promote`.
  There is no option, input, or downstream shell step that records a reason and continues the
  lane past a detected category or an `ambiguous` attestation.
- **G-2** (FR-009 no gate bypass): the `close` path always invokes `specops lane close`, which
  runs the applicable `preflight` gate-profile suite; there is no lane branch that reaches a
  completed state without it.
- **G-3** (FR-010 no independent review cycle): the definition contains **no** `specops.review`
  semantic-review step and opens no review cycle — the lane's scrutiny is eligibility + safety
  core + deterministic gates only.
- **G-4** (FR-005 minimal state): between `lane-start` and terminal, the workflow performs no
  `status.yaml` phase transitions; the only SpecOps state writes are to `lane.yaml`.
- **G-5** (degrade safely, FR-019): steps that consume optional capabilities (context map, etc.)
  tolerate absence; `lane check`/`close`/`promote` function with no context map present.

## Non-CI note

As with the full `specops` workflow, the end-to-end run interacts with a live integration
(`command` steps need an agent) and is **not CI-reproducible**. The YAML *structure* is validated
statically; the composed CLI primitives (`lane start/check/attest/close/promote`) are
unit/integration-tested independently.
