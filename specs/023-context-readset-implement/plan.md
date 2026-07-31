# Implementation Plan: Context Read-Set Consumption in IMPLEMENT

**Branch**: `023-context-readset-implement` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/023-context-readset-implement/spec.md`

## Summary

Close the Feature 009 loop by making the IMPLEMENT phase — the phase that reads
the most — consume the context map's minimal read set. This is a
**directive-and-documentation feature**: the implement directive
(`src/specops/templates/directives/implement.md`, the single source for both
the native extension hook and the legacy marker-block path) gains a
**Context Read Set** section instructing the agent, at session start before the
first task, to resolve the IMPLEMENT-phase context package for each context
declared in `plan.md` (`specops context resolve --id <cid> --phase implement`)
and scope its reads to the union of the resolved packages. Out-of-set
discoveries flow through the existing Feature 010 acknowledgement
(`specops trace acknowledge`); with no map the resolution step reports "no map
present" (exit 0) and the session proceeds exactly as today; any non-zero exit
of the step is treated as "proceed without scoping" — the read set is guidance
plus record, never a gate. **No CLI code, schema, or contract changes**: the
plan proves the existing `context resolve` surface sufficient (research.md
R1/R3), so the `status start-task` surfacing option is declined.

## Technical Context

**Language/Version**: Python 3.11+ (existing package; no change)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), `packaging` — unchanged; no new dependencies

**Storage**: none — no ledger schema change (context provenance snapshotting already exists, ledger stays at v7); the only "storage" touched is directive/doc text in the repo

**Testing**: pytest (`conda run -n specops pytest`), following the established directive-test pattern (`tests/unit/test_lite_directive.py`) and the consumption-layer fixture (`context_map_repo` in `tests/unit/test_contextmap_consume.py`)

**Target Platform**: anywhere the CLI runs (macOS/Linux/Windows); directive text is platform-neutral

**Project Type**: CLI tool + prompt-template product assets (this feature touches only template assets, docs, and tests)

**Performance Goals**: N/A — no runtime code changes; the directive adds at most a handful of read-only CLI invocations per implement session (one `resolve` per declared context)

**Constraints**: Feature 021 contract freeze — zero changes to frozen CLI surfaces, exit codes, or machine-output shapes; `specops context resolve` is used strictly as-is. Rule 5 safe degradation: unmapped repositories must behave byte-identically to today.

**Scale/Scope**: 1 directive template modified, 3 documentation files, 1 new test file + 1 extended test file; no `src/specops/*.py` module changes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Evaluation | Result |
|-----------|------------|--------|
| I. Speckit Extension, Never Replacement | Adds a section to the SpecOps-owned implement directive delivered through the existing extension mechanism (native hook prompt sourced from `directives/implement.md`; legacy marker-block inject from the same file). No Speckit file forked or modified; no wiring changes. | PASS |
| II. Physical State Ledger | No ledger change. The read set is resolved from the context map, not stored; acknowledgements already write through the existing `trace acknowledge` CLI. | PASS |
| III. Automated Evidence Collection | Untouched — no change to task close, evidence records, or commit granularity. | PASS |
| IV. Surgical Agent Behavior via Injected Prompts | This feature **is** a Principle IV change and follows its rule: the behavior change is made in the SpecOps templates (`directives/implement.md`) so every client repository receives it on the next `extension install`/`update` (or `init` on the legacy path). Both delivery paths source the identical text. | PASS |
| V. Domain Agnosticism | Directive text references only SpecOps' own stack-neutral surfaces (`context resolve`, `trace acknowledge`); no technology or client coupling. | PASS |
| VI. Exit Codes as Gates | No exit-code change. The directive *consumes* the existing codes: exit 0 "no map present" → proceed; any non-zero on the resolution step → proceed without scoping (never halt). No command gains a new outcome. | PASS |
| Dev Workflow (No Self-Application) | Behavior validated exclusively through test fixtures (`context_map_repo`, tmp-path injects); no `specops` command is run against this repository. | PASS |

**Post-design re-check (after Phase 1)**: PASS — the design introduced no new
surface, dependency, or ledger change; Complexity Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/023-context-readset-implement/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── implement-directive.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

**SpecOps-Contexts**: n/a — this repository does not self-apply SpecOps (no
context map here; the declaration below is the plain path/action list required
by the Empirical Verification directive).

```text
src/specops/templates/directives/
└── implement.md                        (modify)  # add "Context Read Set (Feature 023)" section

docs/
└── commands.md                         (modify)  # context consumption section: implement-time consumption

README.md                               (modify)  # context row/feature description mentions implement-time consumption
README.pt-br.md                         (modify)  # equivalent Portuguese update (same PR, full parity)

tests/unit/
├── test_implement_directive.py         (create)  # native hook + legacy inject + directive content (pattern: test_lite_directive.py)
└── test_contextmap_consume.py          (modify)  # acceptance-gate coverage: per-task reads ⊆ union of declared-context IMPLEMENT packages; degradation statuses
```

**Structure Decision**: single existing project (`src/specops/` + `tests/`);
this feature adds no modules and no directories. The only product-asset change
is the implement directive template; everything else is documentation and
tests.

## Complexity Tracking

No Constitution Check violations — table intentionally empty.
