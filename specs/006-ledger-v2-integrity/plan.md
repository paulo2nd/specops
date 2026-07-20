# Implementation Plan: Ledger v2 Integrity

**Branch**: `006-ledger-v2-integrity` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-ledger-v2-integrity/spec.md`

## Summary

Version and harden the per-feature execution ledger (`specs/<feature>/status.yaml`) so it stays correct under upgrades, interruptions, branch changes, and competing sessions. The feature adds an explicit `schema_version`, deterministic v1→v2 migration with a retained pre-migration backup, timezone-aware and stably-serialized timestamps, a monotonic `revision` marker with optimistic compare-and-swap on write, workspace-identity validation (feature / branch / branch-point baseline) as a hard pre-write gate, formalized phase/task/recovery/review invariants, and richer recovery + workflow-lane + active-artifact metadata. Read-only inspection stays non-mutating for every ledger state, including too-new, unsupported-older, and malformed ledgers.

**Technical approach**: Introduce a new `src/specops/ledger.py` module that owns v2 schema constants, version classification, the ordered migration engine, timezone helpers, invariant validation, workspace-identity validation, and a concurrency-safe load/save cycle (revision CAS + short-lived lock + the existing atomic tmp→fsync→`os.replace` write). `status.py` command bodies are rewired to route every load/save through `ledger.py`, apply the identity + migration + invariant gate before mutating, and expose a new `specops status migrate` command. The `status.yaml` template gains the new fields. No new runtime dependency is added — locking and timestamps use the standard library; git ancestry reuses `gitops.is_ancestor`.

## Technical Context

**Language/Version**: Python 3.10+ (`requires-python = ">=3.10"`, ruff/mypy target `py310`)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger serialization), GitPython (identity/ancestry) — all already present; **no new dependency**. Locking via stdlib (`os.open` O_CREAT|O_EXCL); timestamps via stdlib `datetime` (timezone-aware).

**Storage**: Per-feature YAML ledger at `specs/<feature>/status.yaml`; pre-migration backups under `.specify/.specops-backup/` (reusing the Feature 005 namespaced backup convention).

**Testing**: pytest with `--cov-fail-under=85`; unit tests under `tests/unit/`, integration under `tests/integration/`. Shared fixtures in `tests/conftest.py` (`tmp_git_repo`, `read_ledger`).

**Target Platform**: Cross-platform CLI (Linux/macOS/Windows); offline after install. Windows UTF-8 output already forced in `cli.py`.

**Project Type**: Single-project CLI library (`src/specops/` + `tests/`).

**Performance Goals**: Ledger operations are interactive CLI actions on a single small YAML file; each state change completes well under 1 s including the lock + CAS re-read (no perceptible overhead versus v1).

**Constraints**: Offline-capable; deterministic (same inputs → same output); atomic and interruption-safe state changes; read-only commands never mutate; fail-closed on ambiguous identity or invariant violation. Exit codes are gates (0 ok, 1 blocking `SpecopsError`, 2 parse/corruption `LedgerParseError`).

**Scale/Scope**: One ledger per feature; tens of tasks and a handful of review cycles per ledger; single supported prior schema (v1) to migrate.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment |
|-----------|------------|
| **I. Speckit Extension, Never Replacement** | ✅ Additive: no Speckit file is forked or replaced; only SpecOps-owned `status.yaml` and the SpecOps CLI change. |
| **II. Physical State Ledger (Repo-as-State)** | ✅ Directly strengthens this principle. All state changes remain CLI-only (`specops status …`), never hand-edited; identity + CAS + invariants make the Git-verifiable ledger stricter, not looser. `specops reconcile`'s exit-1-on-divergence contract is preserved. |
| **III. Automated Evidence Collection** | ✅ Untouched. Evidence format is explicitly **not** redesigned (FR-030; deferred to Feature 012). `complete-task --auto` behavior is preserved. |
| **IV. Surgical Agent Behavior via Injected Prompts** | ✅ No directive content changes. Injected templates under `src/specops/templates/directives/` are unchanged (delivery-mechanism and ledger internals only). |
| **V. Domain Agnosticism** | ✅ All new logic is generic (schema version, revision, timestamps, git ancestry). No stack/framework coupling; nothing new enters `specops.json`. |
| **VI. Exit Codes as Gates** | ✅ New failure modes (stale write, identity mismatch, too-new/unsupported schema, invariant violation) map to `SpecopsError` (exit 1) or `LedgerParseError` (exit 2) via the existing `_handle_errors` boundary. No interactive prompts. |
| **Development Workflow (no self-application)** | ✅ SpecOps is **not** run against this repo. No `specops.json` / `status.yaml` is created at this repo's root or under `specs/*`. All v2 behavior is validated exclusively through pytest fixtures under `tests/`, including synthetic v1 ledgers, injected interruptions, and simulated concurrent writers. |
| **Technical Constraints (deps)** | ✅ No new runtime dependency; locking/timestamps are stdlib. |

**Result: PASS.** No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/006-ledger-v2-integrity/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions R1–R9
├── data-model.md        # Phase 1 output — v2 schema, entities, invariants, state machine
├── quickstart.md        # Phase 1 output — runnable validation scenarios
├── contracts/           # Phase 1 output
│   ├── ledger-schema.md          # v2 field-by-field schema + version classification + backup
│   ├── state-change-preconditions.md  # identity + migration + CAS + invariant gate order
│   └── cli-status-migrate.md     # new `specops status migrate` command contract
└── checklists/
    └── requirements.md  # Spec quality checklist (from /speckit-specify)
```

### Source Code (repository root)

```text
src/specops/
├── ledger.py            # NEW — v2 core: schema constants, classify(), migrate_to_current(),
│                        #   timezone helpers, validate_invariants(), workspace-identity check,
│                        #   concurrency-safe load()/save() (revision CAS + lock + atomic write),
│                        #   pre-migration backup (reuses .specify/.specops-backup convention)
├── status.py            # MODIFY — route load/save through ledger.py; apply the pre-write gate;
│                        #   add cmd_migrate() and cmd_rebaseline() (identity escape hatch, FR-019a);
│                        #   keep command semantics for init/start/complete/transition
├── gitops.py            # REUSE — is_ancestor(), current_branch(), head_sha(), commit_exists()
│                        #   (add a small helper only if a merge-base/ancestor variant is missing)
├── reconcile.py         # MODIFY (light) — keep read-only warnings; delegate identity wording to ledger.py
├── errors.py            # REUSE — SpecopsError (exit 1), LedgerParseError (exit 2);
│                        #   add StaleLedgerError(SpecopsError) if a distinct message/type helps tests
├── cli.py               # MODIFY — register `status migrate` subcommand
└── templates/
    └── status.yaml      # MODIFY — add schema_version, revision, workflow_lane, active_artifact,
                         #   enriched recovery; timezone-aware created_at/updated_at

tests/
├── unit/
│   ├── test_ledger.py        # NEW — classify(), migrate_to_current(), invariants, timestamps, CAS unit
│   ├── test_status.py        # MODIFY — identity gate, migration-on-first-write, stable no-op save
│   └── test_reconcile.py     # MODIFY — read-only stays non-mutating on abnormal ledgers
└── integration/
    ├── test_ledger.py            # MODIFY — end-to-end migration, concurrent writers, interruption
    └── test_ledger_migration.py  # NEW — every supported v1 shape migrates losslessly + backup created
```

**Structure Decision**: Keep the existing single-project layout. The v2 mechanics are concentrated in a new `ledger.py` so `status.py` stays a thin command layer, `reconcile.py`/`consistency.py` keep reading the same dict shape, and the read-only vs state-change split (the crux of FR-007/FR-021/FR-029a) lives behind one module boundary. Every path above was verified to exist (or to be a net-new sibling) against the current tree.

## Complexity Tracking

Not required — Constitution Check passed with no violations.
