# Implementation Plan: Lightweight Workflow Lane

**Branch**: `013-lightweight-workflow-lane` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-lightweight-workflow-lane/spec.md`

## Summary

Add a proportional, human-confirmed **lightweight lane** for small reversible changes that
runs with materially less ceremony than the full `specops` lifecycle while preserving the
non-pierceable safety core. **Operating model (Principle IV):** the human never drives the
`specops` CLI — an injected lightweight-lane **directive** makes the agent recognize a
small/reversible change and *propose* the lane through a human-confirmed gate (never
auto-classifying); on confirmation the agent/workflow engine drives every `specops lane *`
command as native steps, and the human meets only the stop-and-ask gates (eligibility,
root-cause attestation, halt/promote). The lane is delivered as a **second Spec Kit workflow
definition** (`specops-lite`, installed additively alongside the existing `specops` workflow)
composed of native step types only, **plus that Principle IV directive**; SpecOps adds a small
deterministic CLI surface (a `specops lane` sub-app, agent/workflow-facing) plus a dedicated
lightweight record (`lane.yaml`, its own schema — never the full `status.yaml`, per the Session
2026-07-24 clarification). The lane's working state is the
branch's Git commit history; SpecOps keeps one minimal `lane.yaml` (open → resolved). Safety
enforcement is **hybrid**: four diff-detectable categories are flagged deterministically from
the effective diff, and two always-on human attestation checkpoints cover the categories that are
not reliably diff-detectable (ambiguous root cause, public-contract break — analysis C1).
Closure runs the existing `specops preflight` gate-profile suite and records a concise
retrospective plus Feature 012 structured evidence. **Promotion** synthesizes a full
`status.yaml` positioned at the **PLAN** phase from the lane record plus branch history, so a
change that outgrows the lane loses no commits or context and receives full downstream scrutiny.
No new runtime dependencies; every heavy primitive (gate suite, evidence, git effective-diff,
ledger creation, workflow install) already exists and is composed, not reimplemented.

## Technical Context

**Language/Version**: Python ≥ 3.10 (`pyproject.toml`, `requires-python = ">=3.10"`)

**Primary Dependencies**: Typer (CLI), PyYAML (records), GitPython (evidence/diff) — **no new
runtime dependency** (Constitution Technical Constraints). Composes existing modules:
`review` (preflight suite), `gateprofiles`, `evidence`, `gitops`, `ledger`, `status`,
`outcome`, `config`, `extension`.

**Storage**: Files. New per-feature `specs/<feature>/lane.yaml` (dedicated lite record).
Reuses `status.yaml` (synthesized on promotion), `specops.json`, and
`.specify/specops/gate-profiles.yaml`. Workflow definition installed at
`.specify/workflows/specops-lite/workflow.yml` and registered in `workflow-registry.json`.

**Testing**: pytest (`tests/unit`, `tests/integration`, fixtures in `tests/fixtures`,
shared `tests/conftest.py`). Coverage per the repo quality gates (ruff, mypy, pytest under
`conda run -n specops`).

**Target Platform**: Cross-platform CLI; offline after installation (Roadmap Rule 6).

**Project Type**: Single-project CLI (`src/specops/`).

**Performance Goals**: Not latency-critical. The safety-core `lane check` is a pure
effective-diff scan (deterministic, sub-second on normal diffs); closure cost equals a
`specops preflight` run (dominated by the client's configured gate commands).

**Constraints**: Domain-agnostic (Principle V) — safety-core detection uses generic,
built-in path/pattern heuristics with optional `specops.json` override, never stack-specific
logic. Read-only where mandated (`lane status`, `lane check`, `preflight` at closure remain
read-only against the repository; only `lane start`/`attest`/`close`/`promote` mutate the lane
record). Exit codes 0/1/2 via the `outcome` contract (Principle VI); no interactive CLI prompts
(human interaction lives in native workflow `gate`/`prompt` steps).

**Scale/Scope**: One lane per feature branch; a single `lane.yaml` record with a small,
bounded set of decisions (eligibility, stop-and-ask attestations, closure/promotion outcome).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against SpecOps Constitution v1.8.1:

- **I. Speckit Extension, Never Replacement (NON-NEGOTIABLE)** — PASS. The lane is a *second*
  SpecOps-owned workflow definition installed additively via the native workflow mechanism
  (generalizing `extension.install_workflow`); it never forks, replaces, or edits the bundled
  `speckit` workflow or the existing `specops` workflow. No integration-owned file is modified.
- **II. Physical State Ledger (Repo-as-State)** — PASS. Lane state lives only in `lane.yaml`,
  mutated exclusively by `specops lane *` commands (never hand-edited, never in agent memory).
  Commit hashes recorded in the lane record and used at promotion are verified reachable via
  `gitops.is_ancestor`/`commit_exists`, extending the reconcile invariant to the lane.
- **III. Automated Evidence Collection** — PASS. Closure gathers evidence mechanically by
  running the existing gate-profile suite and recording Feature 012 structured evidence; the
  retrospective references commits harvested from Git, not agent narration.
- **IV. Surgical Agent Behavior via Injected Prompts** — PASS. The lane's behavior is imposed
  through the SpecOps-owned workflow definition (native `gate`/`prompt`/`shell`/`command`
  steps) **and a new injected lite-lane directive** (`templates/directives/lite.md`) that makes
  the agent recognize and *propose* the lane and then drive its CLI — so the human never
  conducts `specops` (FR-022/FR-023). This is exactly the Principle IV mechanism (directives +
  workflow), consistent with how Feature 007/016 deliver the full workflow. Stop-and-ask
  checkpoints are native gates; no free-form convention. **Expected constitution amendment**:
  adding this directive extends the Principle IV directive list — a MINOR amendment authored
  during `/speckit-implement` (no principle removed or redefined), following the established
  Sync-Impact-Report pattern.
- **V. Domain Agnosticism** — PASS (with care). Safety-core detection ships generic built-in
  heuristics (path globs / diff patterns) plus optional `specops.json` overrides; no coupling
  to any stack, linter, or framework. See Complexity Tracking for the justification of the
  built-in heuristic set.
- **VI. Exit Codes as Gates** — PASS. Every new `specops lane` command returns `0` on success,
  `1` on a blocking result (ineligible, safety trip, failed closure gate), `2` on infra/usage
  error, with `--json` via `outcome.render`; each composes as a gate in the workflow.

**Development discipline (No Self-Application)** — All lane behavior is proven by this feature's
own tests against fixtures; the lane is never run against this repository, no `lane.yaml` is
created here.

**Result**: No violations. Proceed to Phase 0. (Re-checked post-design — see end of plan.)

## Project Structure

### Documentation (this feature)

```text
specs/013-lightweight-workflow-lane/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (lane.yaml schema, entities, transitions)
├── quickstart.md        # Phase 1 output (end-to-end validation guide)
├── contracts/           # Phase 1 output
│   ├── cli-lane.md            # `specops lane` command contract (args, exit codes, --json)
│   ├── lane-record.schema.md  # lane.yaml structure + invariants
│   └── workflow-lite.md       # specops-lite workflow.yml step contract
├── checklists/
│   └── requirements.md  # Spec quality checklist (already present)
└── spec.md              # Feature specification
```

### Source Code (repository root)

```text
src/specops/
├── cli.py                 # (modify) register a `lane` Typer sub-app: start|status|check|attest|close|promote
├── lane.py                # (create) lane record I/O + lifecycle: eligibility, close, promote-synthesis
├── safety.py              # (create) hybrid safety-core: diff-detectable category detection + attestation model
├── ledger.py              # (modify) minor: promotion provenance on the synthesized ledger (workflow_lane marker)
├── status.py              # (reuse/modify) synthesize a full ledger at PLAN from a lane record (promotion)
├── review.py              # (reuse) preflight gate suite invoked at closure — no behavior change
├── gateprofiles.py        # (reuse) profile selection/suite for closure gates
├── evidence.py            # (reuse) structured evidence records for closure
├── gitops.py              # (reuse) effective_diff_status / commits_in_range / is_ancestor
├── outcome.py             # (reuse) stable --json outcome + exit-code contract
├── config.py              # (reuse/modify) optional `lane` overrides for safety-core patterns (generic defaults)
├── extension.py           # (modify) register `specops-lite` workflow + inject the lite-lane directive
├── initializer.py         # (modify) inject the lite-lane directive on the legacy path (parity with other directives)
└── templates/
    ├── lane.yaml                              # (create) lane record scaffold
    ├── directives/
    │   └── lite.md                            # (create) Principle IV directive: recognize + propose the lane (FR-023)
    └── workflows/
        └── specops-lite/
            └── workflow.yml                   # (create) lightweight lane workflow definition

tests/
├── unit/
│   ├── test_lane.py         # (create) lane record schema, lifecycle transitions, promotion synthesis
│   ├── test_safety.py       # (create) each diff-detectable category + attestation gating
│   └── test_extension_lite.py  # (create) additive install of the second workflow, registry preservation
├── integration/
│   └── test_lane_flow.py    # (create) start → work → safety trip → promote; start → close (retrospective+evidence)
├── unit/
│   └── test_lite_directive.py  # (create) directive installed/updated/no-op'd like other directives (FR-023)
└── fixtures/
    └── lane/                # (create) fixture repos/diffs exercising eligibility, each safety category, promotion
```

**Structure Decision**: Single-project CLI layout, matching the existing `src/specops/`
one-concern-per-module convention (cf. `trace.py`, `handoff.py`, `gateprofiles.py`). The
feature adds two new modules — `lane.py` (record + lifecycle) and `safety.py` (hybrid
safety-core) — plus a new workflow template and its installer generalization. Everything else
is reuse. No new top-level packages or runtime dependencies.

## Complexity Tracking

> Only rows that need justification against a simpler rejected alternative.

| Decision | Why needed | Simpler alternative rejected because |
|----------|------------|--------------------------------------|
| Built-in generic safety-core heuristics (path/pattern set) in `safety.py` | The non-pierceable core must flag the four diff-detectable categories out of the box, or SC-002 cannot hold for a zero-config repo | "Client must configure all detection patterns" rejected: it would let a repo silently disable the safety core by omitting config, piercing the non-pierceable core (Principle I/Design Philosophy). Heuristics stay generic + overridable, so Principle V holds. The two non-diff-detectable categories (root-cause, public-contract) are attested, not detected (analysis C1). |
| New `lane.py` + `safety.py` modules (vs. folding into `status.py`) | Lane state is a *distinct* record (`lane.yaml`) with its own schema and lifecycle; safety detection is reused by both `lane check` and closure | Folding into `status.py` rejected: it would couple the lite record to the full-ledger module and blur the Q1 "dedicated record, not status.yaml" boundary. One-concern-per-module matches the existing codebase. |

## Post-Design Constitution Re-Check

Re-evaluated after Phase 0/1 (research.md, data-model.md, contracts/, quickstart.md):

- **I** — The design installs a *second* SpecOps-owned workflow additively (R1) and touches no
  integration-owned file; `extension remove` cleans up both. PASS.
- **II** — `lane.yaml` is mutated only by `specops lane *` (INV-5), and every recorded commit is
  reachability-checked (INV-4 / P-1). PASS.
- **III** — Closure evidence is machine-collected by reusing the preflight suite + Feature 012
  records (R6 / C-2); the retrospective references harvested commits, not narration. PASS.
- **IV** — Behavior is delivered through the `specops-lite` workflow template (native steps),
  the new injected lite-lane directive (recognize + propose, FR-023), and the composable `lane`
  CLI the agent/engine drives (FR-022); stop-and-ask are native gates with no bypass (G-1 /
  INV-3). The directive addition is a planned MINOR Principle IV amendment. PASS.
- **V** — Safety-core heuristics are generic and `specops.json`-overridable (R5); no stack
  coupling. The one justified built-in (the non-removable detection floor) is in Complexity
  Tracking. PASS.
- **VI** — Every `lane` command maps to `outcome.render` with 0/1/2 exit codes and no
  interactive prompts (contracts/cli-lane.md). PASS.

**No new violations introduced by the design.** No new runtime dependencies. Ledger schema
unchanged (additive promotion-provenance keys only). Ready for `/speckit-tasks`.

*Agent-context update*: skipped deliberately — this repository does not self-apply SpecOps
(No Self-Application), and no `update-agent-context` script is present; the design artifacts are
the durable context for `/speckit-tasks`.
