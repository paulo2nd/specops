# Implementation Plan: Review Round Integrity

**Branch**: `025-review-round-integrity` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-review-round-integrity/spec.md`

## Summary

Make the multi-round semantic review sound. Each round that actually performs the
Step-3 code review records the code scope it covered — an anchor round covers the
full `baseline..HEAD`, a corrective round covers `prev_to..HEAD` — as a per-cycle
**reviewed range** derived from git commit identifiers, never self-reported. A
new **union-coverage guard** on the DONE transition blocks approval unless the
recorded reviewed ranges together cover the current `baseline..HEAD` effective
diff (and degrades to today's cycle-result behavior on legacy ledgers with no
scope records). A **configurable round cap** halts the loop and asks a human when
review keeps cycling. The scope-recording command doubles as the authoritative
"here is what to read this round" surface, replacing the ambiguous "files listed
by the working-tree gate" instruction that let a reviewer improvise (and
under-scope) the review — the defect that motivated this feature.

Technical approach: reuse existing seams throughout — `gitops.name_only_diff`
for per-range path sets, `status.read_baseline` for the anchor, the
`review_cycles[]` ledger records (which already carry a per-round `round` and
`context_provenance`) for the new `reviewed_range` field, and `config.load` for
the cap. Two behavioral hooks are added in `status.py`: the union-coverage guard
inside `_gate_done`, and the round-cap halt at the round-opening site in
`cmd_transition_phase`. One additive CLI command records/derives the scope. One
directive template (`review.md`) is rewritten to distinguish anchor vs corrective
rounds and call the new command.

## Technical Context

**Language/Version**: Python ≥3.10 (`pyproject.toml` `requires-python = ">=3.10"`)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), `packaging` (version
compare) — no new runtime dependency is introduced. Git access via the owned
`gitops` seam (direct `git` plumbing; Feature 020).

**Storage**: The `status.yaml` ledger (schema **v7 → v8** this feature). The new
per-round reviewed-scope data is an additive optional field on
`ReviewCycleRecord`; no new file.

**Testing**: pytest, via the repository's fixture harness under `tests/`
(unit + integration). No self-application: SpecOps is never run against this
repository — behavior is validated exclusively through fixtures (Constitution
§ Development Workflow).

**Target Platform**: Any Speckit repository adopting SpecOps (POSIX + Windows
via the twin script sets); the CLI itself is platform-agnostic Python.

**Project Type**: Single-project Python CLI (`src/specops/`).

**Performance Goals**: Coverage evaluation is O(rounds) `git diff --name-only`
calls at approval time — negligible (a handful of rounds per feature). No hot
path.

**Constraints**: `specops preflight` stays byte-for-byte read-only (unchanged by
this feature — the new writes happen through `handoff`/`status` mutating
commands, never through the gate). Feature 021 contract freeze: every schema and
CLI change MUST be additive (new optional ledger field, new subcommand, new
optional config key). Fail-closed on an unresolvable baseline (Principle VI).

**Scale/Scope**: ~6 source modules touched + one template + docs + fixtures;
one ledger migration; one constitution amendment (MINOR, broadening Principle IV).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Speckit Extension, Never Replacement** — PASS. Purely additive: a new
  optional ledger field, a new additive CLI subcommand, a new optional
  `specops.json` key, and a rewrite of a SpecOps-owned directive template. No
  Speckit-owned file is forked or destructively edited.
- **II. Physical State Ledger** — PASS, with a documented exemption. The reviewed
  range is written to `status.yaml` through a CLI command (never hand-edited,
  never held in agent memory) and is **git-derived** (from baseline/HEAD commit
  ids). Its endpoints are **deliberately exempt** from the "every registered
  commit must exist / `reconcile` blocks on divergence" invariant — they are
  historical review HEADs that a legitimate rebase/squash can make unreachable, so
  `reconcile` does not verify them (behavior unchanged) and the coverage guard
  drops any unresolvable range and re-derives against the current baseline/HEAD
  (research R7). The exemption is recorded exactly like the `(human)` sentinel and
  keeps SpecOps a non-blocker on ordinary git history rewrites — the exemption is
  pinned by a regression test.
- **III. Automated Evidence Collection** — PASS. The reviewed scope is collected
  mechanically from git — no agent narration supplies the range values.
- **IV. Surgical Agent Behavior via Injected Prompts** — PASS with a required
  **MINOR constitution amendment**: the Token-Optimized Review directive is
  broadened so the review agent records the round's reviewed scope and approval
  enforces union coverage; the round cap is a new Stop-and-Ask (halt-and-ask a
  human). The guard **records and checks coverage only — it never judges a
  finding's merit** ("record, do not validate"). Delivered by editing
  `src/specops/templates/review.md` in the same change set.
- **V. Domain Agnosticism** — PASS. The round cap enters through `specops.json`
  (`review_round_cap`), like every other client-specific value; no framework
  coupling.
- **VI. Exit Codes as Gates** — PASS. Incomplete coverage and the round-cap halt
  both block with exit 1 (a blocking gate outcome); an unresolvable baseline is a
  fail-closed exit 1 with an explanatory message.
- **Development Workflow / No Self-Application** — PASS. All behavior is verified
  through `tests/` fixtures; no `specops` command is run against this repository.

No principle is violated; **Complexity Tracking is empty** (nothing to justify).
The two governance consequences (schema v7→v8, Principle IV amendment) are
additive and handled in the same change set, consistent with prior features.

## Project Structure

### Documentation (this feature)

```text
specs/025-review-round-integrity/
├── plan.md              # This file
├── research.md          # Phase 0 output — resolved design decisions
├── data-model.md        # Phase 1 output — ledger/record deltas
├── quickstart.md        # Phase 1 output — fixture validation scenarios
├── contracts/           # Phase 1 output — CLI + guard behavior contracts
│   ├── review-scope-cli.md
│   └── approval-and-cap.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/specops/
├── ledger.py            # CURRENT_SCHEMA 7→8 (pure version bump — see research R1)
├── records.py           # ReviewCycleRecord: + optional reviewed_range, review_role;
│                        #   + optional review_halt marker on the ledger document
├── reviewscope.py       # NEW — derive anchor/corrective range, compute union
│                        #   coverage vs baseline..HEAD (pure, unit-testable logic)
├── handoff.py           # cmd_record_scope: stamp the current cycle via reviewscope
├── status.py            # _gate_done: union-coverage guard; cmd_transition_phase:
│                        #   round-cap halt at the round-opening site
├── config.py            # _DEFAULTS: + review_round_cap (default 10)
├── gitops.py            # reuse name_only_diff/commit_exists; add a 2-arg ancestry
│                        #   helper only if research R3 shows it is needed
├── cli.py               # wire the new subcommand + --json output
└── templates/
    └── review.md        # Step 3 rewrite: anchor vs corrective + call scope command

tests/
├── unit/                # reviewscope range derivation + union coverage;
│                        #   config default; frozen-ledger v8 shape
└── integration/         # end-to-end review-round fixtures (quickstart scenarios)

docs (repo root): README.md + README.pt-br.md (parity); .specify/memory/constitution.md
```

**Structure Decision**: Single-project layout (the only option for this CLI). New
pure logic goes in a dedicated `reviewscope.py` (range derivation + coverage math)
so it is unit-testable without the ledger/CLI, mirroring how `evidence.py` and
`trace.py` isolate derivation from the `status.py`/`handoff.py` orchestration and
the `cli.py` surface. The behavioral guards live where the review lifecycle already
lives (`status.py`), and the recording command lives on the existing `handoff`
surface (the review-cycle CLI group).

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)    | —          | —                                    |
