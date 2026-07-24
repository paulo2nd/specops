# Implementation Plan: Gate Rename & Vocabulary Pass

**Branch**: `017-gate-rename-vocabulary` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/017-gate-rename-vocabulary/spec.md`

## Summary

Rename the deterministic gate command `specops review → specops preflight` and keep
`specops review` as a behavior-identical **deprecated alias** that emits exactly one
stderr line per invocation. The command label in the outcome JSON mirrors the invoked
name (invoke `preflight` → `"command":"preflight"`; invoke `review` → `"command":"review"`),
so existing stdout-parsing consumers see byte-stable output while new consumers get the
honest name. Update the living surfaces that name the gate — the injected directive
template (`src/specops/templates/review.md`), the shipped workflow definition
(`.../templates/workflows/specops/workflow.yml`), the constitution (a PATCH naming
amendment), and the EN/PT READMEs — leaving the semantic `command: specops.review`
directive, the `REVIEW` phase, and the `APPROVED/REJECTED` verdict untouched. Perform a
**conservative** vocabulary sweep: the gate is the only rename; every other overloaded
term found is documented, not renamed (Clarification 2026-07-24 Q1). No behavior change,
no breaking removal, no persisted-key change.

The technical approach is a Typer twin-registration: extract the current `review()` body
into a shared implementation parameterized by the invoked command name, register it under
`preflight` (canonical) and `review` (deprecated alias that first writes the notice to
stderr). Everything else is text propagation and test re-pointing.

## Technical Context

**Language/Version**: Python ≥ 3.10 (repo `requires-python = ">=3.10"`; CI matrix includes 3.10/3.13/3.14).

**Primary Dependencies**: Typer (CLI), Click (underlying command model), GitPython (`git`), pytest / CliRunner. No new dependency is introduced.

**Storage**: N/A. This feature changes **no** persisted state — no ledger schema, no `status.yaml`, no JSON key (FR-011).

**Testing**: pytest with Typer `CliRunner`. `CliRunner` here captures `stdout`/`stderr` separately (existing `test_review_cli.py` asserts `result.stderr`), which is exactly what makes FR-003 (notice on stderr, stdout byte-stable) directly testable.

**Target Platform**: Cross-platform CLI (Linux/macOS/Windows); UTF-8 output is already forced at import (`cli._force_utf8_output`).

**Project Type**: Single-project Python CLI + installable Spec Kit extension assets (directive/workflow templates).

**Performance Goals**: N/A — pure naming; the gate suite's runtime is unchanged.

**Constraints**: Offline after install; deterministic output; stdout byte-identical for the `review` alias vs the pre-rename command (FR-003); exit codes unchanged (FR-001/FR-005, Principle VI).

**Scale/Scope**: Small. One CLI command pair, one directive template, one workflow YAML, the constitution, two READMEs, the changelog, and the affected test modules. ~1 new command, 1 alias, 1 notice string, ~4 doc/template files, ~3 test files touched, plus a sweep catalogue in `research.md`.

**Tooling note (dev only)**: run `ruff`, `mypy`, and `pytest` under `conda run -n specops …` (base env has a numpy stub that aborts mypy). This is our development gate, not a delivered capability (roadmap "No Self-Application").

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.8.0. This feature is naming hygiene; it strengthens the principles rather than straining them.

| Principle | Verdict | Notes |
|---|---|---|
| I. Speckit Extension, Never Replacement | ✅ Pass | No orchestration added; composes the same native steps. The alias is a CLI convenience, not a new engine/gate/loop. |
| II. Physical State Ledger (Repo-as-State) | ✅ Pass | Zero persisted-state change (FR-011): no ledger field, phase id, verdict value, or JSON key renamed. |
| III. Automated Evidence Collection | ✅ Pass | Evidence records and gate profiles are untouched; the gate's behavior is byte-identical. |
| IV. Surgical Agent Behavior via Injected Prompts | ✅ Pass — **directly advances** | The whole point: an honestly-named primitive (`preflight`) stops the injected directive/workflow author from believing the gate performs the review (the Feature 016 miscomposition). Directive template updated in the same change set (Governance amendment rule). |
| V. Domain Agnosticism | ✅ Pass | Naming only; stack-neutral, no domain coupling. |
| VI. Exit Codes as Gates | ✅ Pass | Exit codes preserved for both names (FR-001/FR-005); `--soft`/hard modes intact so the workflow's loop and terminal gate keep their semantics. |

**Roadmap boundaries**: "record, don't validate" and the "minimal non-pierceable core" are unaffected — no gate is added, removed, or made pierceable.

**Governance obligation (triggered)**: Updating the constitution's gate references (FR-009) is an amendment. Per the Governance section it MUST bump the version, update the Sync Impact Report comment, and propagate to templates in the same change set. This is a **PATCH** bump (1.8.0 → 1.8.1): wording/naming clarification, no principle removed or redefined. Propagation targets are already in scope (directive template + workflow.yml).

**Result**: PASS. No violation; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/017-gate-rename-vocabulary/
├── plan.md              # This file
├── spec.md              # Feature spec (+ Clarifications)
├── research.md          # Phase 0 — decisions + the conservative sweep catalogue
├── data-model.md        # Phase 1 — the (non-persisted) command/alias/notice entities
├── quickstart.md        # Phase 1 — runnable validation scenarios
├── contracts/
│   └── preflight-command.md   # CLI contract for `specops preflight` + `review` alias
└── checklists/
    └── requirements.md  # Spec quality checklist (already validated 16/16)
```

### Source Code (repository root)

Empirically verified paths this feature touches (living surfaces only):

```text
src/specops/
├── cli.py                       # add `preflight` command; make `review` a deprecated
│                                #   alias; extract shared impl; mirror invoked name into
│                                #   outcome.render(<name>, …); update line ~284 comment
├── outcome.py                   # UNCHANGED behavior — render() already takes `command`
│                                #   as a parameter; the CLI passes the invoked name (FR-004)
├── review.py                    # internal module — OPTIONAL docstring/comment refresh only
│                                #   (module name is an internal identifier: out of scope, FR-012)
├── gateprofiles.py, shell.py    # OPTIONAL internal-comment refresh (not user-facing)
└── templates/
    ├── review.md                # /specops-review DIRECTIVE: change "Run `specops review`"
    │                            #   → "Run `specops preflight`" (the gate it calls); the
    │                            #   directive itself stays named review (reserved term)
    └── workflows/specops/workflow.yml
                                 # rename the TWO `shell: specops review` steps
                                 #   (review-soft, terminal-gate) → `specops preflight`;
                                 #   update the header comment block; DO NOT touch
                                 #   `command: specops.review` (the semantic directive)

.specify/memory/constitution.md  # PATCH amendment 1.8.0→1.8.1: gate refs → preflight;
                                 #   Sync Impact Report; reserve "review" for phase/directive/verdict

README.md / README.pt-br.md      # gate refs → `specops preflight`; document the `review`
                                 #   deprecated alias; keep EN/PT behaviorally equivalent (FR-010)

CHANGELOG.md                     # NEW entry only (rename + alias + window + "behavior
                                 #   unchanged"); historical entries stay as shipped

tests/
├── unit/test_workflow_definition.py     # update terminal-gate/review-soft run-string
│                                        #   assertions to `specops preflight`; KEEP the
│                                        #   semantic `command == "specops.review"` assertion
├── unit/test_outcome_contract.py        # add a `preflight` render case (render stays generic)
└── integration/test_review_cli.py       # re-point behavior assertions to `preflight`
                                         #   (no stderr notice); ADD an alias test class:
                                         #   review == preflight on stdout/exit + exactly one
                                         #   stderr line. Consider renaming file → test_preflight_cli.py
```

**Explicitly OUT of scope (frozen history — do NOT edit)**: everything under
`specs/004-…`, `specs/007-…`, `specs/011-…`, `specs/012-…`, `specs/016-…`. These are
completed-feature artifacts that record what shipped under the old name; rewriting them
would falsify history (roadmap Rule 7). `ROADMAP.md` protocol/DoD example references
(`specops review` at lines 128/178/194) are left as-is; the Feature 017 section already
explains the rename.

**Structure Decision**: Single-project layout (existing). No new modules or packages;
the change is concentrated in `cli.py` plus text propagation across the four living
surfaces above and their tests.

## Complexity Tracking

No constitution violations — table intentionally empty.
