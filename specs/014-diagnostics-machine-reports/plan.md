# Implementation Plan: Diagnostics and Machine Reports

**Branch**: `014-diagnostics-machine-reports` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/014-diagnostics-machine-reports/spec.md`

## Summary

Deliver two read-only CLI surfaces that compose SpecOps's existing read APIs into a
single health/status view:

- **`specops doctor [--json]`** — a read-only diagnostic that inspects every
  SpecOps-specific surface (CLI/extension compatibility, integration resolvability,
  legacy install artifacts, configuration, active-feature identity, ledger schema +
  integrity, context-map health, workflow/ledger divergence, preflight gate
  availability), classifies each finding by severity (`ok` / `warning` / `blocking` /
  `execution-error`), computes an overall verdict, and — for every non-`ok` finding —
  emits a deterministic next action as **both** a stable `next_action_code` enum and
  human-readable text. Exit code maps to the verdict via the existing outcome contract.
- **`specops report [--json]`** — a compact read-only project/feature status report
  (identity, phase, task progress, review/handoff state, workflow lane), reusing the
  read accessors behind `status show`.

The technical approach is **composition, not new logic**: nearly every check reuses an
existing pure-read function (`ledger.*`, `reconcile.*`, `contextmap.validate`,
`gateprofiles.profiles_for`, `handoff.cmd_validate`, `migration.detect_state`,
`compat.check`, `speckit.resolve_feature_dir`, `gitops.*`). The only genuinely new
mechanics are (a) a new `doctor.py` module that orchestrates those reads into a
severity-classified report, (b) a read-only PATH probe (`shutil.which` over
`shlex.split(cmd)[0]`) for gate availability — no existing helper exists — and (c) the
`next_action_code` enum + versioned output schema. Doctor **does not execute** `specify`
or any gate command; it defers to native commands by *pointing* at them (a
`next_action_code`), which also preserves byte-identical determinism.

## Technical Context

**Language/Version**: Python `>=3.10` (per `pyproject.toml`; ruff/mypy target `py310`).

**Primary Dependencies**: Typer (CLI), PyYAML (ledger reads), GitPython (git reads). New
mechanics use **stdlib only** — `shutil.which`, `shlex.split`, `json` — so **no new
runtime dependency** (honors the constitution's dependency constraint).

**Storage**: Read-only over repository files — `specs/NNN-*/status.yaml` (ledger),
`.specify/specops/context-map.yaml`, `.specify/specops/gate-profiles.yaml`,
`specops.json`, `.specify/extensions.yml`, `.specify/feature.json`,
`.specify/integration.json`. The feature persists **no** new state; its only output is
the versioned in-memory report rendered to stdout.

**Testing**: pytest, with `typer.testing.CliRunner` (in-process) and `subprocess`
(real-binary) integration idioms already established; `tests/conftest.py` fixtures
(`fake_speckit_repo`, `ledger_in_review`, `context_map_repo`, `handoff_repo`,
`snapshot_tree`).

**Target Platform**: Cross-platform developer/CI environments; offline after install
(no network, no telemetry — FR-017).

**Project Type**: Single Python CLI package (`src/specops/`).

**Performance Goals**: Diagnostic completes well within an interactive/CLI budget on a
normal repository; all checks are local file + git reads (no execution of gates). No
hard numeric latency target (SC-001 is about single-invocation sufficiency, not speed).

**Constraints**: Strictly read-only (SC-003 byte-for-byte unchanged); deterministic
byte-identical output on unchanged inputs (FR-007/SC-005 — no wall-clock, no embedded
native-command output); stable versioned JSON (FR-006/FR-018); exit codes consistent
with the Feature 007 outcome contract and Principle VI (FR-008); EN/PT parity (FR-016).

**Scale/Scope**: Two commands, one new module, ~9 diagnostic domains, one enum, one
output schema (version 1). Active-feature scope only (FR-012a); no whole-repo scan.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md`. Must pass before Phase 0;
re-checked after Phase 1.*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** | PASS. Doctor **complements** `specify check` / `specify workflow status`, does not reimplement them (FR-011). It adds only the SpecOps-specific delta (ledger/context-map/divergence/gate/legacy/config). No orchestration primitive is built. |
| **II. Physical State Ledger (Repo-as-State)** | PASS. Doctor is **read-only**; it never manipulates the ledger. It *reports on* Principle II divergence by reusing `reconcile.run` / `reconcile.divergence` (the same `is_ancestor` check), never mutating. |
| **III. Automated Evidence Collection** | N/A (no task closure / evidence produced). Doctor consumes existing evidence/ledger state read-only. |
| **IV. Surgical Agent Behavior via Injected Prompts** | PASS (dev-side): declared paths are verified against the worktree (see Project Structure — every reused symbol carries a `file:line`); every spec success criterion maps to planned work. Doctor is a deterministic CLI, not an agent behavior. |
| **V. Domain Agnosticism** | PASS. Stack-neutral: no language/framework assumptions; the gate PATH probe treats commands as opaque shell strings. |
| **VI. Exit Codes as Gates** | PASS. Overall verdict → exit via `outcome.exit_for`: `ok`/`warning` → PASS (0); `blocking` → GATE_REJECTION (1); `execution-error` → INFRA_ERROR (2). No interactive prompts. |
| **Dependencies constraint** | PASS. Stdlib-only additions; no new third-party dependency. |
| **No Self-Application** | PASS. The feature is delivered + tested via fixtures under `tests/`; we do **not** run `specops doctor` against this repository, create a ledger here, or install `/specops-review`. |

**Result**: No violations. Complexity Tracking is empty (below).

## Project Structure

### Documentation (this feature)

```text
specs/014-diagnostics-machine-reports/
├── spec.md
├── plan.md                # this file
├── research.md            # Phase 0 — decisions incl. resolved checklist gaps
├── data-model.md          # Phase 1 — report/domain/finding entities + enums
├── quickstart.md          # Phase 1 — runnable validation scenarios
├── contracts/
│   ├── doctor-cli.md       # `specops doctor` command + exit-code contract
│   ├── report-cli.md       # `specops report` command contract
│   └── doctor-output.schema.json   # versioned machine-readable output schema
└── checklists/
    ├── requirements.md
    └── requirements-quality.md
```

### Source Code (repository root) — verified against the worktree

```text
src/specops/
├── cli.py                 # ADD top-level `@app.command("doctor")` + `@app.command("report")`
│                          #   (siblings of reconcile/consistency/preflight/review, cli.py:155-338);
│                          #   ADD `_emit_doctor` renderer modeled on `_emit_trace` (cli.py:674-685)
├── doctor.py              # NEW — orchestrates read-only domain checks → DoctorResult;
│                          #   OUTPUT_VERSION, Severity/verdict maps, next_action_code enum,
│                          #   report() for the compact status surface
├── outcome.py             # REUSE render()/exit_for()/CommandResult (no change)
├── ledger.py              # REUSE classify/diagnostic_line/refusal_message/load_raw/
│                          #   validate_identity/validate_invariants/finding_structural_defects
├── reconcile.py           # REUSE run()/divergence() (pure reads)
├── contextmap.py          # REUSE validate()/map_digest(); review.digest_drift_warning()
├── gateprofiles.py        # REUSE profiles_for()/validate() (enumerate .command strings)
├── handoff.py             # REUSE cmd_validate()/blocking_approval_check() (read-only)
├── lane.py                # REUSE exists()/load() (read-only)
├── migration.py           # REUSE detect_state() (ABSENT/NATIVE/LEGACY/NATIVE_AND_LEGACY)
├── compat.py              # REUSE installed_version()/check() (CLI/extension version)
├── extension.py           # REUSE read_manifest()/semantically_equal() (drift, read-only)
├── speckit.py             # REUSE resolve_feature_dir()/has_speckit()/resolve_prompt_targets()
├── config.py              # REUSE load() (parseability = validity)
├── status.py              # REUSE read accessors behind cmd_show() for `report`
└── gitops.py              # REUSE find_repo()/is_git_repo()/is_ancestor()

tests/
├── unit/
│   ├── test_doctor.py             # NEW — domain checks + severity/verdict + next_action_code
│   └── test_doctor_report.py      # NEW — compact report field mapping
└── integration/
    ├── test_doctor_cli.py         # NEW — CLI exit codes, --json schema, fixtures per verdict
    ├── test_doctor_readonly_determinism.py  # NEW — snapshot_tree + byte-identical (SC-003/005)
    └── test_report_cli.py         # NEW — `specops report` human + --json
```

**Structure Decision**: Single-project layout (Option 1). One new module `doctor.py`
holds all orchestration and the output schema constants; the CLI layer stays thin
(command + `_emit_doctor`), matching the established read-only-command idiom
(`trace`/`gate`/`handoff`). `report` reuses the `status.cmd_show` read path; to avoid
duplicating the counting recipe, the compact-status computation is factored into a
shared read-only helper consumed by both `report` (new, human + `--json`) and — with no
behavior change — left available to `status show`.

### Command naming decision (resolves the clarify-deferred item)

- `specops doctor` — top-level, sibling to `reconcile`/`preflight`; does **not** collide
  with the `status` verb group nor the existing `extension status` / `lane status`
  subcommands (verified in `cli.py`).
- `specops report` — top-level compact status report ("Machine Reports"), chosen over
  overloading the state-changing `status` group (the constraint recorded in the spec's
  Assumptions and Clarifications).

## Complexity Tracking

> No Constitution Check violations — this table is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 — Research

See [research.md](./research.md). It resolves the checklist-flagged spec gaps
(human-output mode, domain-result-vs-findings surface, schema forward-compat rules), the
FR-011 "defer without wrapping" determinism decision, the gate-availability probe
approach, and the exit-code mapping — with no remaining NEEDS CLARIFICATION.

## Phase 1 — Design & Contracts

Artifacts: [data-model.md](./data-model.md), [contracts/](./contracts/),
[quickstart.md](./quickstart.md). The data model fixes the report/domain/finding
entities, the `Severity` and `next_action_code` enums, and the versioned output schema;
the contracts pin the two CLI commands and the JSON shape; the quickstart gives runnable
per-verdict validation scenarios against fixtures.

**Agent context update**: no `update-agent-context` script is present for this
integration; `CLAUDE.md` is left unchanged (no new always-on convention is introduced by
this feature).
