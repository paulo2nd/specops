# Implementation Plan: Stage-Wide Directive Wiring

**Branch**: `003-stage-directive-wiring` | **Date**: 2026-07-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-stage-directive-wiring/spec.md`

## Summary

Extend SpecOps' existing marker-delimited injection so the agent-facing Speckit
prompts carry the ledger and phase commands at the correct stage seams. Today
`specops init` injects only the **plan** and **implement** directives and
installs `/specops-review`. This feature adds a **tasks** directive and a
**specify** directive, augments the **implement** directive with phase
transitions, and de-duplicates the `[SC-xxx]` coverage rule so it lives where
`tasks.md` is generated. No new CLI command and no CLI behavior change are
required (confirmed scope): the ledger is created at the tasks stage via the
existing `specops status init-spec`, and every phase move uses the existing
one-step-forward `specops status transition-phase`.

## Technical Context

**Language/Version**: Python 3.10+ (existing project baseline)

**Primary Dependencies**: Typer, PyYAML, GitPython (no new dependencies)

**Storage**: Files only — packaged directive templates under
`src/specops/templates/directives/`; per-feature `status.yaml` ledger (unchanged)

**Testing**: pytest (unit + integration), reusing existing fixtures in
`tests/integration/test_init.py`, `tests/unit/test_injection.py`, and
`tests/unit/test_speckit.py`

**Target Platform**: OS-independent CLI

**Project Type**: Single Python CLI package (`src/specops/`)

**Performance Goals**: N/A (init is a one-shot local operation)

**Constraints**: Injection MUST stay additive, idempotent, and
byte-identical-reversible; all directive text in English; ledger mutated only
through `specops` commands; injected prompts MUST degrade gracefully when the
`specops` CLI is unavailable at run time.

**Scale/Scope**: 2 new template assets, 1 modified template, 2 modified template,
2 touched source modules (`speckit.py`, `initializer.py`), plus tests. No
schema, no public CLI surface change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| **I. Speckit Extension, Never Replacement** | Reuses `inject_block`/`remove_block` (marker-delimited, in-place update, reversible). Two new blocks appended at EOF of the specify and tasks prompts; no content outside markers touched. | ✅ Pass |
| **II. Physical State Ledger** | Directives instruct the agent to run `init-spec` / `transition-phase` only — never hand-edit `status.yaml`. No new mutation path. | ✅ Pass |
| **III. Automated Evidence Collection** | Unchanged. Implement ledger loop and `--auto` evidence behavior preserved. | ✅ Pass |
| **IV. Surgical Agent Behavior via Injected Prompts** | This feature is delivered exactly as Principle IV mandates — via injected templates. Principle IV was amended (constitution **1.2.0**, 2026-07-05) to add the **Ledger & Phase Wiring** directive category, so phase-transition and ledger-creation wiring is now governed. | ✅ Pass |
| **V. Domain Agnosticism** | Phase names and ledger commands are generic; no tech/framework coupling; no `specops.json` change required. | ✅ Pass |
| **VI. Exit Codes as Gates** | Directives consume existing exit codes. Graceful degradation is guarded in directive prose ("if `specops` is unavailable, skip"), not by swallowing exit codes when present. | ✅ Pass |

**Gate result**: PASS. The governance follow-up (constitution amendment) is
**done** — bumped to 1.2.0 recording the Ledger & Phase Wiring directive.

## Project Structure

### Documentation (this feature)

```text
specs/003-stage-directive-wiring/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── injection-targets.md
│   └── stage-directives.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/specops/
├── templates/
│   └── directives/
│       ├── specify.md      (create)  # new — informational, pre-ledger
│       ├── tasks.md        (create)  # new — SC tags + init-spec + phase walk to TASKS
│       ├── plan.md         (modify)  # SC-tag rule de-duplicated: point to tasks stage
│       └── implement.md    (modify)  # add TASKS→IMPLEMENT (start) + IMPLEMENT→REVIEW (end)
├── speckit.py              (modify)  # resolve_prompt_targets: add specify_path, tasks_path
└── initializer.py          (modify)  # inject two new blocks + echo their status

tests/
├── unit/
│   ├── test_speckit.py     (modify)  # resolve_prompt_targets returns specify/tasks paths
│   └── test_injection.py   (modify)  # new blocks inject/idempotent/reversible
└── integration/
    └── test_init.py        (modify)  # end-to-end: all four stage prompts injected
```

**Structure Decision**: Single-project CLI layout (existing). All feature work
lands in `src/specops/templates/directives/` (assets) plus two source modules
(`speckit.py`, `initializer.py`), mirroring how the current plan/implement
directives are wired. No new module is introduced.

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|------|-----------|-------------------------------------|
| **Constitution MINOR amendment** to record the phase-wiring / ledger-creation directive under Principle IV — **DONE (1.2.0)** | Governance clause requires that when a Principle IV directive changes, the change flows through templates in the same change set; Principle IV enumerated a closed directive set that did not mention phase wiring. Documenting it keeps the constitution the single source of truth. | Not amending would leave a live directive category undocumented, silently widening Principle IV — rejected. |
| **Specify-stage directive is informational-only** (no ledger op) | The ledger does not exist until the tasks stage, so the specify block cannot mutate phase. It exists to satisfy FR-002 and to make the specify stage SpecOps-aware (author prose in any language; structural tokens in English; ledger will be created at tasks). | Dropping the specify block entirely would violate FR-002 and leave the earliest stage blind to SpecOps. Kept, but deliberately thin. If the maintainer prefers zero specify injection, FR-002 should be struck from the spec first. |
| **Tasks directive walks two phase steps** (`SPECIFY→PLAN→TASKS`) after `init-spec` | The ledger is born at `SPECIFY` and `transition-phase` only advances one step; reaching a truthful `TASKS` phase requires two calls. | Making `init-spec` accept an initial phase would be cleaner but is a CLI change, explicitly out of the confirmed scope. Walking the chain in the directive keeps the CLI untouched. |
