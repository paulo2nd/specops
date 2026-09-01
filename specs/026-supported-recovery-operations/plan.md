# Implementation Plan: Supported Recovery Operations

**Branch**: `026-supported-recovery-operations` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-supported-recovery-operations/spec.md`

## Summary

Give the ledger a supported way to be corrected. Three commands close two states
that today have no legal move: `status amend-task` appends a corrected evidence
record (with its reason) to a task already `DONE` without reopening it; `feature
use` repoints the active feature explicitly and `status init-spec` repoints
automatically; `feature rename` carries a renumbering across directory, ledger
identity, branch reference and pointer. A fourth, smaller thread aligns SpecOps'
feature resolution with Spec Kit's precedence, so the two tools can never answer
about different features.

Technically the feature is small because the ledger already owns the machinery:
structured evidence records are append-only, id-addressable and carry a
`superseded_by` pointer. The amendment reuses that record with two additive
optional fields (`amendment`, `reason`) and a task-scoped supersede step — the one
place where the existing helper is deliberately *not* reused, because its
producer-wide scope is built for gate caching and would reach across tasks
(research D3). Ledger schema goes v8 → v9 as a pure version bump, following the
v7 and v8 precedent.

## Technical Context

**Language/Version**: Python 3.10+ (`pyproject.toml`: `requires-python = ">=3.10"`)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), `packaging`. **No new
dependency.** Directory move and pointer write use `os.rename` / the existing
`fsutil.atomic_write`; the stale-reference scan is plain string search.

**Storage**: `specs/<feature>/status.yaml` (ledger, schema v8 → **v9**);
`.specify/feature.json` (active-feature pointer, shape unchanged)

**Testing**: pytest (`tests/unit/`, `tests/integration/`), mypy, ruff — run under
`conda run -n specops …`

**Target Platform**: cross-platform CLI (macOS/Linux/Windows); no
platform-specific paths — resolved feature directories are emitted POSIX-style,
matching the existing `_resolved_feature` contract

**Project Type**: single Python package + CLI (`src/specops/`)

**Performance Goals**: none beyond existing CLI responsiveness; all three commands
are single-ledger, single-pass operations

**Constraints**: exit codes confined to the frozen `{0,1,2}` set; every refusal
exits non-zero (FR-021); no Git write operations (SpecOps' `gitops` seam is
read-only and stays so); pre-v9 ledgers must load, migrate and behave identically

**Scale/Scope**: ~3 new commands, 1 new module, 2 modified modules, 1 schema bump,
1 migration test, directive + docs updates in English and Portuguese

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Verdict | Basis |
|---|---|---|
| **I. Speckit Extension, Never Replacement** | **PASS** | Nothing forks or patches Spec Kit. `feature use` writes `.specify/feature.json`, a file Spec Kit itself writes via `Save-FeatureJson` — SpecOps adds the operator-facing command Spec Kit never exposed, not a competing store. Aligning resolution precedence (D6) moves SpecOps *toward* Spec Kit's behaviour, and deliberately does not persist the override, honouring the `-NoPersist` carve-out Spec Kit made for read-only resolution. |
| **II. Physical State Ledger** | **PASS — and this is the point of the feature.** Every correction is a CLI-mediated ledger write; the feature exists precisely to remove the last two states that forced hand-editing. No commit hash is invented: amendment touches evidence only, never `commits` or `started_commit`, so the reconcile ancestry invariant is untouched. |
| **III. Automated Evidence Collection** | **PASS with a stated boundary.** An amendment is operator-supplied by construction (FR-023 forbids inference), so it is *not* machine-collected evidence and must never masquerade as it. That is exactly why the record is marked `amendment: true` with a mandatory reason and a distinct `producer: "amend"` — a human assertion is labelled as one, never rendered as an `auto` harvest. |
| **IV. Surgical Agent Behavior** | **PASS** | FR-025 puts amendment into the injected directives as a *recovery* move, restricted to correcting a previous session's record. FR-026 keeps the restriction instructional: SpecOps records, it does not adjudicate which session closed a task. |
| **V. Domain Agnosticism** | **PASS** | No technology, framework or client rule enters. All three commands operate on SpecOps' own artifacts. |
| **VI. Exit Codes as Gates** | **PASS** | No new exit code. Every refusal path exits 1 (or 2 for infra/parse), enumerated in [contracts/cli-commands.md](./contracts/cli-commands.md). |

**Post-Phase-1 re-evaluation**: unchanged, all PASS. The design added no
dependency, no new persisted file, and no Git write. One item was promoted to an
explicit output requirement during design rather than left implicit: a rename that
updates `branch` to a name not yet present in Git will make the *next* command
fail closed via `ledger.validate_identity`; the rename must say so in its output
(see data-model §5). That is fail-closed behaviour working as designed, but a
silent version of it would be a bad experience.

**Complexity Tracking**: not required — no violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/026-supported-recovery-operations/
├── plan.md              # This file
├── research.md          # Phase 0 — 10 decisions (D1–D10), code-cited
├── data-model.md        # Phase 1 — v9 record shapes, resolution model, identity
├── quickstart.md        # Phase 1 — runnable validation per user story
├── contracts/
│   └── cli-commands.md  # Phase 1 — command surface, messages, exit codes
├── checklists/
│   └── requirements.md  # Spec quality checklist (16/16)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/specops/
├── feature.py           # (create) feature use / feature rename
├── speckit.py           # (modify) SPECIFY_FEATURE_DIRECTORY precedence + resolution provenance
├── status.py            # (modify) cmd_amend_task; init-spec repoints; cmd_show echoes dir
├── evidence.py          # (modify) amendment fields on build_record
├── records.py           # (modify) EvidenceRecord: amendment, reason
├── ledger.py            # (modify) CURRENT_SCHEMA 8 → 9; amendment invariants
├── handoff.py           # (modify) carry amendment provenance into inherited evidence (FR-006a)
├── cli.py               # (modify) status amend-task; new `feature` sub-app; echo suffix
├── trace.py             # (modify) evidence_amended / evidence_history in the report
├── doctor.py            # (modify) report the active-feature selection; fail on a broken one
├── templates/
│   ├── status.yaml      # (modify) drop the stale schema_version declaration
│   └── directives/
│       └── implement.md # (modify) amendment as a recovery-only move (FR-025)

tests/
├── fixtures/
│   └── ledger_v8_with_evidence.yaml    # (create) migration-test input
├── unit/
│   ├── test_amend_task.py              # (create)
│   ├── test_feature_use.py             # (create)
│   ├── test_feature_rename.py          # (create)
│   ├── test_ledger_v9_migration.py     # (create)
│   ├── test_speckit_resolution.py      # (create) precedence + provenance
│   ├── test_evidence_record.py         # (modify) amendment fields + id derivation
│   ├── test_trace.py                   # (modify) evidence_amended / evidence_history
│   ├── test_handoff.py                 # (modify) inherited-evidence provenance
│   ├── test_status.py                  # (modify) init-spec repoint
│   ├── test_extension.py               # (modify) directive recovery-move text
│   ├── test_cli.py                     # (modify) echo suffix + refusal sweep
│   └── test_doctor.py                  # (modify) selection diagnostics
└── integration/
    ├── test_recovery_amend.py          # (create)
    ├── test_recovery_pointer.py        # (create)
    └── test_recovery_rename.py         # (create)

docs/commands.md         # (modify) three new commands
README.md                # (modify) recovery operations
README.pt-br.md          # (modify) equivalent — full parity, same PR
CHANGELOG.md             # (modify) v9 bump, new commands, migration note
```

**Structure Decision**: the existing single-package layout is kept. Placement is
dictated by the one-way import graph (`status` → `ledger` → `speckit`, and
`speckit` importing neither): `amend-task` sits beside `complete-task` in
`status.py` because it uses the identical `load_for_write` / `finalize` cycle,
while `feature use` / `feature rename` need both ledger access and directory
manipulation and therefore cannot live in `speckit.py` without inverting that
graph — hence one new module, `feature.py` (research D8).

## Implementation Phases

**Phase A — schema, record shape, and shared foundations.** `CURRENT_SCHEMA` 8 → 9
with the pure version bump, `EvidenceRecord` gains `amendment` / `reason`,
`build_record` learns to emit them, migration test lands alongside.

Two shared pieces land here rather than inside a story, because US2 and US3 both
need them and putting either in one story would make the other depend on it —
contradicting the spec's independence claim:

- the `src/specops/feature.py` module and its CLI sub-app registration (US2 adds
  `use`, US3 adds `rename`);
- the feature-resolution alignment in `speckit.py` (override precedence plus
  resolution provenance) — US2's `feature use` refuses on an override that would
  neutralize it, and US3's `feature rename` refuses on an override that the rename
  would invalidate. One mechanism, two consumers.

Nothing user-visible yet; every existing test must stay green.

**Phase B — `amend-task` (US1, P1).** The task-scoped supersede helper, the
legacy-string materialize safety net (research D4), the command, its refusals, and
the `trace report` amendment surfacing. Ships the feature's core value alone.

**Phase C — `feature use` (US2, P2).** `feature use` on top of the Phase A
resolution work, the `init-spec` repoint, and the resolved-feature echo across
`status show` / `consistency` / `preflight`.

**Phase D — `feature rename` (US3, P3).** Validation-then-ordered-mutation per
research D9, the identity-header rewrite, the stale-reference scan.

**Phase E — directives and documentation.** `implement.md` recovery-move text,
`docs/commands.md`, and both READMEs in parity.

Phases B, C and D are independently shippable **in any order** once Phase A is in.
Both shared foundations live in A, so no story depends on another — which is what
makes the spec's per-story independence claim true in practice rather than only on
paper.
