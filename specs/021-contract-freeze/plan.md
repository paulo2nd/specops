# Implementation Plan: Contract Freeze for 1.0

**Branch**: `021-contract-freeze` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-contract-freeze/spec.md`

## Summary

Freeze the seven adopter-facing surfaces (`specops.json`, `status.yaml`, `lane.yaml`,
gate-profile files, JSON output envelopes, exit codes, findings-input contract) for
1.0: publish a stability policy (`docs/stability.md`) that classifies each surface and
states its additive-vs-breaking rule; add schema-level **contract tests** that lock the
frozen shapes and fail on any unversioned break; document the post-1.0
versioning-and-migration obligations; and make one sanctioned additive code change —
give the base command-result envelope a single `output_version` so every `--json`
consumer has one detectable version signal (this also removes today's inconsistency
where `consistency`/`reconcile`/`preflight` omit the version key the report families
carry). Constitution Principle VI is amended in the same change set to document exit
code `2`, which the code already emits. No new capability, no alias removal; the rc tag
is gated on an external release-owner judgment this feature only references.

## Technical Context

**Language/Version**: Python `>=3.10` (`pyproject.toml`; PEP 604 `X | None` and `TypedDict` already used in `records.py`).

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), `packaging` (version compare). **No new runtime dependency** — `output_version` is a plain int constant; the freeze is docs + tests + one additive field.

**Storage**: Repo-as-state files — `.specify/` ledger (`status.yaml`), lane state (`lane.yaml`), gate-profiles (`.specify/specops/gate-profiles.yaml`), project config (`specops.json`). No datastore.

**Testing**: pytest (`tests/unit`, `tests/integration`, `tests/golden`), ruff, mypy — repo thresholds. Reuses the existing enumerated-table contract pattern (`tests/unit/test_outcome_contract.py`) and the golden byte-freeze harness (`tests/golden/harness.py`).

**Target Platform**: CLI (`specops` entrypoint); CI matrix per repo (Linux/macOS/Windows-class paths in golden set).

**Project Type**: Single-project Python CLI library.

**Performance Goals**: N/A — a freeze adds no runtime path; contract tests are pure-function/schema assertions.

**Constraints**: No schema bump (ledger stays v7, findings-input contract stays v1, lane stays v1); no CLI command/option added; No Self-Application (tests use fixtures/golden, never run `specops` on this repo); EN authoritative docs with a PT pointer.

**Scale/Scope**: 7 frozen surfaces; 1 additive code delta (`outcome.OUTPUT_VERSION`); 1 constitution amendment (Principle VI); 2 policy docs; ~7 contract-test additions/extensions; golden re-capture for the 3 families that gain the version key.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.9.2. Evaluated per principle:

| Principle | Verdict | Notes |
|---|---|---|
| I. Speckit Extension, Never Replacement | ✅ Pass | No new command, no orchestration; docs + tests + one additive field. |
| II. Physical State Ledger | ✅ Pass | Ledger behavior unchanged; freeze **pins** schema v7. No new state, no migration. |
| III. Automated Evidence Collection | ✅ Pass | Evidence record shape frozen as-is; no change to producers. |
| IV. Surgical Agent Behavior via Injected Prompts | ✅ Pass | No directive/template change. |
| V. Domain Agnosticism | ✅ Pass | Stability policy is stack-neutral; no domain coupling. |
| VI. Exit Codes as Gates | ⚠️ **Amended (in-scope)** | Principle names only `0`/`1`; the code emits `0`/`1`/`2`. FR-014 amends VI to document exit `2` (infra/data/usage error). This is the feature's sanctioned governance change — see Complexity Tracking. |
| Technical Constraints — Dependencies | ✅ Pass | No new runtime dependency. |
| Dev Workflow — No Self-Application | ✅ Pass | Contract tests exercise fixtures + golden captures; `specops` is never run against this repo. |
| Quality Gates | ✅ Pass | ruff + mypy + full pytest at repo thresholds; new tests included. |

**One sanctioned behavior delta** (FR-012): the base `--json` envelope gains `output_version`. This is **additive** (a new key) and is exactly what the "additive change allowed" rule permits; it changes golden `--json` captures for `consistency`/`reconcile`/`preflight`, which are re-recorded. No happy-path exit code, human output, or command signature changes.

Result: **PASS** — no principle violated. One governance amendment (Principle VI) is a deliberate, in-scope deliverable, tracked below.

**Post-Design re-check (after Phase 1)**: still **PASS**. The design confirmed exactly one code delta (single-sourced `outcome.OUTPUT_VERSION`), one governance amendment (Principle VI), no new runtime dependency, and no schema bump. Research surfaced two items to flag but not fix here (D5 bilingual check does not exist → SC-006 corrected to manual review + dual-language presence; D7 template `schema_version:4` drift → baseline pinned to `CURRENT_SCHEMA=7`, template left as-is). Neither introduces a new violation.

## Project Structure

### Documentation (this feature)

```text
specs/021-contract-freeze/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (policy home, envelope-version approach, amendment level, bilingual reality)
├── data-model.md        # Phase 1 — the frozen-shape inventory for all 7 surfaces (the core deliverable)
├── quickstart.md        # Phase 1 — how to validate the freeze (run tests, inject a break, see it fail)
├── contracts/
│   ├── stability-policy.md      # Structure + content contract for docs/stability.md
│   ├── versioning-policy.md     # Post-1.0 evolution obligations (bump+migration, envelope version, rename discipline)
│   └── frozen-envelope.md       # The base-envelope output_version change contract (before/after)
└── checklists/
    ├── requirements.md          # spec-quality (done)
    └── contracts.md             # requirements-quality (done)
```

### Source Code (repository root)

```text
src/specops/
├── outcome.py           # CHANGE: add OUTPUT_VERSION=1; render() always emits it (single-source the envelope version)
├── cli.py               # CHANGE: _emit() and standalone render() call sites stop passing output_version (render owns it)
├── trace.py             # touch: drop redundant module OUTPUT_VERSION passing (envelope version now single-sourced)
├── handoff.py           # touch: same
├── contextmap.py        # touch: same for the CLI envelope; KEEP provenance output_version (ledger state, separate)
├── gateprofiles.py      # touch: same for the CLI envelope; KEEP file-schema output_version (persisted format, separate)
├── errors.py            # read-only reference (exit-code taxonomy: SpecopsError→1, LedgerParseError→2, StaleLedgerError→1)
├── config.py            # read-only reference (specops.json keys; no version field — additive-only + preserve-unknown)
├── records.py / ledger.py   # read-only reference (ledger v7 frozen baseline)
└── lane.py / ingestion.py / sarif.py   # read-only reference (lane v1, findings-input v1 frozen baselines)

docs/
├── stability.md         # NEW — the published stability + versioning policy (EN, authoritative)
└── commands.md          # touch: cross-link the stability policy

tests/
├── unit/
│   ├── test_outcome_contract.py     # EXTEND — assert OUTPUT_VERSION present + value; single-source check
│   ├── test_frozen_config.py        # NEW — specops.json frozen key set (config.py)
│   ├── test_frozen_ledger.py        # NEW — status.yaml v7 frozen field tables + CURRENT_SCHEMA pin
│   ├── test_frozen_lane.py          # NEW — lane.yaml v1 frozen field tables
│   ├── test_frozen_gateprofiles.py  # NEW/EXTEND — gate-profile file schema + output_version pin
│   ├── test_frozen_ingestion.py     # NEW/EXTEND — findings-input contract_version + schema pin
│   └── test_frozen_envelope.py      # NEW — base envelope keys {command,outcome,class,output_version} + additive tolerance
├── golden/
│   ├── captures/…                   # RE-RECORD affected families (consistency/reconcile/preflight gain output_version)
│   └── harness.py                   # reuse; add scenarios if a frozen surface lacks a golden
└── fixtures/                        # NEW fixtures: gate-profiles + findings-input samples (none exist yet)

.specify/memory/constitution.md      # CHANGE: amend Principle VI (document exit 2); bump version; update Sync Impact Report
CHANGELOG.md                         # CHANGE: record the freeze; link docs/stability.md
README.md / README.pt-br.md          # CHANGE: EN section + PT pointer to the stability policy
```

**Structure Decision**: Single-project layout (unchanged). The stability policy is a new adopter-facing document under `docs/` (discoverable from README + CHANGELOG); the frozen-shape *evidence* lives in enumerated-table contract tests under `tests/unit/` mirroring the existing `test_outcome_contract.py`, plus golden byte-freeze for CLI JSON. Prior per-feature contract docs (`specs/012/…gate-profiles.config.md`, `specs/015/…findings-input.schema.json`, `specs/018/…cli-output.md`) are **referenced** by the policy, not duplicated.

## Complexity Tracking

Only one item requires justification — the Principle VI amendment (a constitutional change).

| Change | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|-------------------------------------|
| Amend constitution Principle VI to document exit code `2` (FR-014) | The frozen exit-code contract locks `0`/`1`/`2` (the code's real behavior since evidence/ledger errors shipped), but Principle VI still names only `0`/`1`. Freezing a contract the governing principle contradicts is incoherent — the principle and the test must agree. | *Leaving VI at 0/1* rejected: the freeze would then contradict its own governing document, and a reviewer citing VI would "correctly" reject the exit-2 test. *Collapsing code to 0/1* rejected: a breaking change to shipped behavior — the opposite of a freeze. |
| Base-envelope `output_version` field (FR-009) | Adopters need one machine-detectable version signal on every `--json` output; today it is present on some families and absent on others. | *No code change / document heterogeneity* rejected in clarification Q2: leaves `consistency`/`reconcile`/`preflight` consumers with no version signal and freezes an inconsistency into 1.0. Not a constitution violation — additive and single-sourced — listed here only because it is the feature's sole code delta. |

**Amendment SemVer level — DECIDED (human-approved 2026-07-28): PATCH (1.9.2 → 1.9.3).** It aligns the principle's wording to already-shipped behavior (a clarification); no principle is added, removed, or redefined, and VI's intent (exit codes as composable gates) is unchanged. (MINOR was the considered alternative, not taken.)
