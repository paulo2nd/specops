# Implementation Plan: Hardening II — API & State Robustness

**Branch**: `019-api-state-robustness` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-api-state-robustness/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Finish the internal robustness pass Feature 018 deferred, with zero user-visible change: fix the ledger-lock stale-reclaim TOCTOU race (two contenders can both `unlink`+recreate a stale lock — `ledger.py` `_LedgerLock.__enter__`) with an atomic-rename reclaim, covered by a concurrency test that fails on the old code; decompose `status.cmd_transition_phase` (~155 lines) and `status.cmd_complete_task` into named sub-steps and collapse the verbatim-duplicated Feature 006 DONE gate (the two identical "no cycles / latest not APPROVED" blocks inside `cmd_transition_phase`) into one helper; replace `handoff._load_write`'s union return (9 `isinstance(loaded, HandoffResult)` call sites) with a `LoadedLedger` dataclass plus a typed refusal exception converted in one place; give ledger records `TypedDict` schemas in a new dependency-free `records.py` (static-only, zero serialization change); single-source the `git diff --name-status` parser in `gitops` with rename-awareness as a parameter (deleting `lane._parse_name_status`); move the `(human)` sentinel out of `gitops.is_ancestor` to a `ledger.HUMAN_COMMIT` constant filtered by callers; make the three `{{...}}` template-render sites assert placeholder completeness via a shared `fsutil.render_template`; drive `gateprofiles` lenient parse and validate from one declarative field table; and stop `doctor` threading `state_error` exceptions as domain-check arguments. No new runtime dependency (the `filelock` alternative is rejected in research D1); ledger schema stays at v7.

## Technical Context

**Language/Version**: Python 3.10+ (existing project floor; `pyproject.toml` `requires-python = ">=3.10"`)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), GitPython (evidence collection), `packaging` (version compare) — unchanged; the lock fix is in-tree (research D1), so FR-001 adds nothing

**Storage**: repository files — `status.yaml` ledger (v7, no schema change), its `.lock` sidecar (reclaim protocol hardened, same file name), `lane.yaml`, `specops.json`; serialization formats untouched (SC-007)

**Testing**: pytest + pytest-cov (≥85% enforced floor), ruff, mypy (`disallow_untyped_defs`, existing `git.*` override only — FR-006 forbids new suppressions); new concurrency regression test for the lock (FR-002); run via `conda run -n specops …`

**Target Platform**: cross-platform CLI (macOS/Linux/Windows) — the rename-based reclaim uses `os.rename` to a unique per-contender name, atomic on POSIX and valid on Windows for a file no live process holds open

**Project Type**: single Python CLI package (`src/specops/`)

**Performance Goals**: none — behavior-preserving refactor; lock acquisition latency unchanged on the uncontended path (same `O_CREAT|O_EXCL` fast path)

**Constraints**: byte-identical human/JSON output and exit codes for every command (FR-013, SC-001 — this feature has **no** sanctioned delta, unlike 018); no ledger schema bump; no new CLI surface; No Self-Application (constitution §Development Workflow) — all verification via test fixtures

**Scale/Scope**: 9 production modules touched (`ledger`, `status`, `handoff`, `gitops`, `lane`, `trace`, `gateprofiles`, `doctor`, `fsutil`) + 1 new (`records.py`); baselines: 2 verbatim DONE-gate copies → 1, 2 `--name-status` parsers → 1, 9 `isinstance` loader probes → 0, 3 unchecked `{{...}}` render sites → 1 checked helper, 2 gate-profile field spellings → 1 table

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|-----------|------------|--------|
| I. Speckit Extension, Never Replacement | Pure internal refactor of SpecOps' own modules. No Spec Kit surface, workflow, template asset, or integration file changes behavior; the `status.yaml`/`lane.yaml` scaffold templates are untouched (only their rendering gains a completeness assertion). | PASS |
| II. Physical State Ledger | Strengthened: the lock race fix removes the one known way two writers could enter the read-modify-write section together. Revision-CAS in `ledger.save` remains the durable authority (FR-001 preserves it). Schema stays v7; CLI-exclusive manipulation unchanged. | PASS |
| III. Automated Evidence Collection | Evidence grammar, structured records, and `<CLASS>:<summary>` strings unchanged; `records.py` only *types* the existing shapes (`EvidenceRecord` TypedDict mirrors `evidence.build_record`'s output byte-for-byte). | PASS |
| IV. Surgical Agent Behavior via Injected Prompts | No directive content changes; templates under `src/specops/templates/` unchanged in content. No constitution amendment required. | PASS |
| V. Domain Agnosticism | Improved: the `(human)` ledger-domain sentinel leaves the generic git layer (`gitops.is_ancestor`), moving to the ledger domain where it belongs. No client-facing configuration change. | PASS |
| VI. Exit Codes as Gates | Exit codes are part of the byte-identical contract (FR-013); the handoff loader's typed error path preserves each refusal's status→class→exit-code mapping exactly (`NOT_A_REPO` → INFRA_ERROR → 2, etc.). | PASS |
| Technical Constraints (deps) | No new runtime dependency: the lock is hardened in-tree (research D1; `filelock` evaluated and rejected). Nothing to justify in Complexity Tracking. | PASS |
| Dev Workflow (No Self-Application) | All verification through `tests/` fixtures; the concurrency test races threads/processes over a fixture ledger lock, never this repository's state. | PASS |

**Post-Phase-1 re-check (2026-07-27)**: design artifacts introduce no new dependencies, no schema changes, no Spec Kit surface changes, and no output deltas. All gates still PASS.

## Project Structure

### Documentation (this feature)

```text
specs/019-api-state-robustness/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: verified inventories + decisions D1–D10
├── data-model.md        # Phase 1: typed record schemas, LoadedLedger, DiffEntry, lock protocol states
├── quickstart.md        # Phase 1: validation guide (capture, race test, mypy seeded typo, scans)
├── contracts/
│   ├── internal-api.md  # New/changed internal contracts (records, loader, parser, render, field table)
│   └── lock-protocol.md # The hardened lock acquire/reclaim/release protocol
├── checklists/
│   └── requirements.md  # Spec quality checklist (complete)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/specops/
├── ledger.py            # (modify) _LedgerLock: atomic-rename stale reclaim (D1); HUMAN_COMMIT constant + is_human_commit predicate (D7); validate_identity filters the sentinel itself
├── status.py            # (modify) cmd_transition_phase/cmd_complete_task decomposed into named sub-steps (D3); single _require_approved_cycle DONE gate (D2); template rendering via fsutil.render_template (D8); record signatures adopt records.* types (D4)
├── handoff.py           # (modify) _load_write → LoadedLedger + HandoffLoadRefused exception, converted by one decorator (D5); cmd_validate filters HUMAN_COMMIT before gitops.is_ancestor (D7); finding iteration adopts records.FindingRecord (D4)
├── gitops.py            # (modify) sentinel removed from is_ancestor (D7); shared name-status parse + name_status_diff(rename_aware, cached) (D6); effective_diff_status delegates
├── lane.py              # (modify) _parse_name_status deleted; _diff_status consumes gitops.name_status_diff (D6); template rendering via fsutil.render_template (D8)
├── records.py           # (create) dependency-free TypedDict schemas: LedgerDocument, TaskRecord, ReviewCycleRecord, HandoffRecord, FindingRecord, EvidenceRecord, ContextProvenance (D4)
├── evidence.py          # (modify) build_record/append_record signatures adopt records.EvidenceRecord (D4); grammar and behavior untouched
├── findings.py          # (modify) new_finding returns records.FindingRecord (D4); shape untouched
├── gateprofiles.py      # (modify) declarative field table single-sources parse + validate field knowledge (D9); parsing/validation behavior byte-identical
├── doctor.py            # (modify) state_error no longer threaded as an argument; shared _error_domain helper builds the execution-error DomainResult (D10)
├── trace.py             # (modify) signature-level adoption of records types where it reads tasks/acks (D4); _name_status keeps delegating to gitops
└── fsutil.py            # (modify) render_template(text, mapping) with placeholder-completeness assertion (D8)

tests/
├── unit/test_ledger_lock.py        # (create) FR-002 concurrency regression: staled lock + barrier-raced contenders; single-winner assertion that fails on the old unlink+recreate reclaim
├── unit/test_records_typing.py     # (create) runtime shape parity: TypedDict keys == the dicts the factories emit (serialization guard for SC-007)
├── unit/                           # (modify) template-drift test (unfilled placeholder → loud failure, SC-006); gate-profile table parity tests; doctor error-flow output parity
└── integration/                    # (modify) only where renamed internals are referenced; no scenario changes (SC-001 relies on the existing suite as the capture set)
```

**Structure Decision**: single-project layout, unchanged. One new module (`src/specops/records.py`) holds the typed schemas — dependency-free (like `evidence.py`) so `ledger`, `status`, `handoff`, and `findings` can all import it without cycles. Everything else is in-place modification. No packaging or build changes.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.
>
> The one decision the roadmap reserved for this plan — harden the in-tree lock vs adopt a locking dependency — is resolved **without** a new dependency (research D1), so no justification entry is required. The rejected alternative (`filelock`) and its trade-offs are documented in research.md D1.
