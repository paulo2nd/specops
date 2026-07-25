# Implementation Plan: External Review Ingestion

**Branch**: `015-external-review-ingestion` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/015-external-review-ingestion/spec.md`

## Summary

Deliver a versioned, stack-neutral **findings input contract** (JSON) plus an optional **SARIF 2.1.0 input adapter** that ingest an external reviewer's output into the existing Feature 011 corrective handoff as **`advisory`** findings carrying **producer** and **reviewed-diff-digest** provenance, with **per-finding staleness** detection and **human, audited promotion** to `blocking`. SpecOps records the external judgment as a ledger snapshot and gates deterministically on the human-owned triage/verification; it never runs, bundles, or re-verifies the reviewer (Principle IV, FR-019).

The technical approach composes existing subsystems and adds **no new orchestration**: a new pure `ingestion.py` module (parse/validate/map/identity/digest — no I/O), three thin state-changing commands added to `handoff.py` (reusing its atomic CAS write path), a one-line ledger schema bump v6 → v7 with an additive forward migration, a small `gitops.blob_sha` helper for per-location digests, and CLI wiring under the existing `handoff finding` group. The report gains producer + read-time staleness columns.

## Technical Context

**Language/Version**: Python 3.10+ (`pyproject.toml` `target-version = py310`, mypy `python_version = 3.10`)

**Primary Dependencies**: `typer` (CLI), `pyyaml` (ledger), `gitpython` (diff/blob digests). **No new runtime dependency** — SARIF is parsed as plain JSON via the stdlib `json`, mirroring the dependency-free Feature 012 SARIF *output* adapter (`sarif.py`). Digests use stdlib `hashlib` / git's own blob hashing.

**Storage**: The Feature 006 ledger `specs/NNN-*/status.yaml`, schema **v6 → v7** (additive). Imported findings are nested under `review_cycles[].handoff.findings[]` exactly like Feature 011 findings — no parallel store.

**Testing**: `pytest` — unit (`tests/unit/`), integration (`tests/integration/`), fixtures (`tests/fixtures/`). Forward-migration test modeled on `tests/unit/test_ledger_v6_migration.py`.

**Target Platform**: Local developer/CI environment; offline after install (roadmap Rule 6).

**Project Type**: Single-project Python CLI (`src/specops/`).

**Performance Goals**: Not latency-bound. Determinism is the hard requirement: identical input + repo state ⇒ byte-identical ledger state (FR-008), consistent with Features 008–011.

**Constraints**: Deterministic, idempotent, all-or-nothing, fail-closed (exit 0/1/2), read-only read paths, stack-neutral (no language-specific parser), EN/PT doc parity.

**Scale/Scope**: One new pure module, ~3 new CLI commands, 1 schema bump + migration, 1 git helper, 1 JSON-schema contract, report augmentation, and their tests. No changes to the Feature 011 finding lifecycle, approval gate, or the SARIF output adapter's behavior.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** | **PASS** — adds no Spec Kit primitive. Ingestion is a deterministic ledger/CLI capability invoked by the `/specops-review` directive/workflow; no engine, gate, loop, or resume is built. |
| **II. Physical State Ledger (Repo-as-State)** | **PASS** — imported findings, provenance, and promotion are ledger state written through the existing atomic + revision-CAS path (`status._load_for_write`/`_finalize`). A rejected review with imported findings is resumable from the repo alone (FR-002, FR-020-equivalent via Feature 011). |
| **III. Automated Evidence Collection** | **PASS** — a promoted-and-fixed imported finding links the same structured evidence record as any Feature 011 finding (`evidence.build_record`); no new evidence representation. |
| **IV. Surgical Agent Behavior via Injected Prompts** | **PASS** — SpecOps records the finding as a snapshot and never judges/re-verifies it (FR-019); advisory-by-default (FR-005) keeps bug-finding judgment with the producer and escalation with a human (FR-006). Ingestion is engine plumbing invoked by the directive, not a daily human command. |
| **V. Domain Agnosticism** | **PASS** — the input contract is stack-neutral JSON; SARIF is an optional adapter; findings derive only from paths, rule/action text, severity, and producer identity. No language/framework parser (FR-022-equivalent). |
| **VI. Exit Codes as Gates** | **PASS** — reuses the fixed `0/1/2` taxonomy via `HandoffResult`/`outcome`; all-or-nothing malformed input fails closed at exit `2` (FR-013, FR-018). |

**Result: PASS, no violations.** Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/015-external-review-ingestion/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (identity, digest, all-or-nothing, promotion, SARIF)
├── data-model.md        # Phase 1 — ledger v7 finding fields, entities, states
├── quickstart.md        # Phase 1 — runnable validation scenarios
├── contracts/
│   ├── findings-input.schema.json   # The versioned JSON input contract (v1)
│   └── ingestion-cli.md             # CLI command/exit/status contract
├── checklists/
│   ├── requirements.md              # spec-quality (16/16)
│   └── requirements-quality.md      # requirements-quality (41/41)
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/specops/
├── ingestion.py     # NEW — pure: parse/validate JSON + SARIF, content identity,
│                    #        severity mapping, primary-location rule, per-location
│                    #        digest + staleness compare. No ledger I/O. INPUT_CONTRACT_VERSION=1.
├── handoff.py       # EDIT — add cmd_finding_import_json / import_sarif / promote;
│                    #        extend finding record (producer, reviewed_digest, imported,
│                    #        promotion) + _finding_view/report staleness (read-time).
├── sarif.py         # UNCHANGED behavior — input adapter reuses its version + severity map (inverse).
├── ledger.py        # EDIT — CURRENT_SCHEMA 6→7; additive migrate_to_current; tolerate new
│                    #        optional finding fields in finding_structural_defects.
├── gitops.py        # EDIT — add blob_sha(repo, rev, path) for per-location digests.
└── cli.py           # EDIT — register import-json / import-sarif / promote under finding_app.

tests/
├── unit/
│   ├── test_ingestion.py            # NEW — pure parse/identity/digest/severity/location
│   └── test_ledger_v7_migration.py  # NEW — v6→v7 forward migration, no data loss
└── integration/
    └── test_handoff_ingestion_cli.py # NEW — import-json/import-sarif/promote exit/status/--json,
                                       #        all-or-nothing, idempotency, staleness, degrade
```

**Structure Decision**: Single project (Option 1). The pure/parse logic is isolated in a new `ingestion.py` (mirroring `sarif.py`'s pure-projection separation), so all ledger mutation stays in `handoff.py` behind its existing atomic-write preamble. This keeps the new surface testable without a repo (pure unit tests) and confines state changes to the audited Feature 011 write path.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.
