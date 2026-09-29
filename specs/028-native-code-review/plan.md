# Implementation Plan: Native Code Review in `/specops-review`

**Branch**: `028-native-code-review` | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-native-code-review/spec.md`

## Summary

Step 3a of `templates/review.md` currently mentions a native reviewer as a conditional
example. This feature turns it into a `{{native_review}}` placeholder, rendered per
installed integration from a small built-in map plus an optional `specops.json`
override.

- **Integration with a native reviewer:** Step 3a names the exact command and how to
  invoke it, and makes invoking it mandatory. It adds the subagent rule and tells the
  reviewer to record an advisory `native-review-not-run` finding when the native
  reviewer does not run. That finding goes through the existing `handoff finding add`
  command.
- **Integration without one:** Step 3a states the absence and keeps today's manual
  review.

Both install paths (`specops init` and `specops extension install|update|enable`)
already loop over the per-integration install targets. They call one shared render
function, so an update rewrites every installed review command.

Nothing else moves: no ledger change, no new command, no gate change, and no new key
in `specops.json`'s written defaults.

**Built-in map (research R1)**: only `claude` → `/code-review` through the Skill tool,
at effort `high`, targeting the round's `reviewed_range`. Built-in entries must meet
three conditions: shipped with the tool, invocable by the agent in-session, and
targetable to the round's range. Of the 44 Spec Kit integrations, only Claude Code
meets all three today. Qwen and Amp fail on the target, Codex, opencode, goose and
Junie need a shell-out, Copilot (VS Code) is UI-only, and Gemini's reviewer is an
extension. Any of them can be enabled per project through `native_review.<id>.command`.

## Technical Context

**Language/Version**: Python 3.10+ (`requires-python`, `target-version = py310`)

**Primary Dependencies**: Typer, PyYAML, `packaging`. **No new dependency.**

**Storage**: none new. The ledger stays at `schema_version: 9`. `specops.json` is read, never rewritten, for this feature.

**Testing**: pytest under `conda run -n specops`; ruff + mypy in the same env

**Target Platform**: any Spec Kit repository (macOS/Linux/Windows CI)

**Project Type**: single Python CLI package (`src/specops/`)

**Performance Goals**: N/A (string rendering at install time)

**Constraints**:
- The `specops.json` freeze (Feature 021) allows a new optional key only. `native_review` is read when present and is **not** added to `config._DEFAULTS`, so `test_frozen_config.py` stays unchanged.
- An install must not write anything when it is rejected. All review contents are rendered, which also validates them, before the first file write.
- Both install paths must source the directive identically (Principle IV).
- The feature is never self-applied to this repository.

**Scale/Scope**: one new ~80-line module, one template edit, two call-site edits, tests, and docs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Speckit Extension, Never Replacement | ✅ Only SpecOps-owned review command files change. The integration id comes from Spec Kit's own `integration.json` and manifests, through the existing `review_command_targets`/`resolve_prompt_targets`. No Spec Kit file is touched. |
| II. Physical State Ledger | ✅ No ledger change. The `native-review-not-run` signal is an ordinary advisory finding in the existing finding model. |
| III. Automated Evidence Collection | ✅ Not affected. By the user's decision, SpecOps does not verify that the native reviewer ran (spec Assumptions). |
| IV. Surgical Agent Behavior via Injected Prompts | ✅ This is squarely a Principle IV change. The behavior is imposed through the registered `/specops-review` text, and both install paths render it identically through one function. |
| V. Domain Agnosticism | ✅ The map covers host agent integrations, not client technology. Project-specific overrides go through `specops.json`, the sanctioned channel. |
| VI. Exit Codes as Gates | ✅ An invalid `native_review` block raises `ConfigError` (a `SpecopsError`), which `_handle_errors` maps to exit 1 (`SpecopsError.exit_code`). That is the same code an unparseable `specops.json` gets today, so all `specops.json` errors share one code. Nothing exits 0 on refusal. |
| Dev workflow | ✅ Tests are fixture-based under `tests/`. Nothing runs against this repository. |

No violations. Complexity Tracking is not needed.

**Post-design re-check (after Phase 1)**: Still passing.
- The design adds one module and one placeholder, and persists nothing.
- Declared `(modify)` paths were verified against the worktree. `nativereview.py` and `test_nativereview.py` do not exist yet, which matches their `(create)` suffix.
- Every SC maps to a quickstart scenario: SC-001 → #1, SC-002 → #2, SC-003 → research R1 plus the map-keys assertion in T008, SC-004 → #6, SC-005 → §1 full suite.

## Project Structure

### Documentation (this feature)

```text
specs/028-native-code-review/
├── plan.md              # This file
├── research.md          # Phase 0: native reviewer per integration, design decisions
├── data-model.md        # Phase 1: map entry + native_review config shape
├── quickstart.md        # Phase 1: validation scenarios
├── contracts/
│   ├── native-review-config.md   # specops.json `native_review` block
│   └── review-step-3a.md         # rendered Step 3a text, per variant
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/specops/
├── nativereview.py            (create)  built-in map, config validation, Step 3a render
├── templates/review.md        (modify)  Step 3a native paragraph → {{native_review}}; Step 4 gains the native-review-not-run example
├── initializer.py             (modify)  init path renders review content per target integration
└── extension.py               (modify)  register_commands renders per target, all before any write

tests/
├── unit/test_nativereview.py              (create)  map, overrides, validation, render variants
├── unit/test_review.py                    (modify)  template assertions read the rendered text / placeholder
├── unit/test_refusal_exit_contract.py     (modify)  only if its raw-template read breaks on the placeholder
└── integration/test_extension_lifecycle.py (modify) multi-integration install renders each copy; update rewrites; invalid config writes nothing

README.md, README.pt-br.md     (modify)  `native_review` row in the specops.json table
docs/commands.md               (modify)  review command: native reviewer per integration
CHANGELOG.md                   (modify)  [Unreleased] entry
ROADMAP.md                     (modify)  Feature 028 entry (ACTIVE)
```

**Structure Decision**: This is a single CLI package. The map and rendering live in one
new module, `nativereview.py`, which follows the repo's pattern of one small module
per concern (compare `sarif.py` and `outcome.py`). The two install call sites import
it. `config.py` keeps its current scope, so no helper is added there beyond what the
module needs.

## Complexity Tracking

Not applicable.
