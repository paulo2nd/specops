# Implementation Plan: Structured Corrective Handoff

**Branch**: `011-structured-corrective-handoff` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-structured-corrective-handoff/spec.md`

## Summary

Promote review findings and correction authorization from free-form `revisions/revision-X.md` prose
to first-class, versioned **ledger state**, so a rejected review is fully machine-checkable and
resumable from repository state alone, and approval is impossible while any **blocking** finding is
unverified. Nothing in Spec Kit's engine is reimplemented (Rule 8); no new runtime dependency and
no language-specific parser is added (Principle V) — findings are written through, and read out of,
state SpecOps already owns. The feature delivers one new module, one CLI group, a ledger schema
bump, and additive wiring into the existing phase-transition gate and directives:

1. **Structured findings + corrective handoff** — a new `handoff.py` records, per review-cycle
   round, a handoff (`authorized_paths`, `closed_at`, `findings`) whose findings carry a stable
   `R<round>-F<NN>` id, `severity` (`blocking`|`advisory`), `rule`, `file[:line]`, `action`, and a
   **per-finding** `expected_evidence` + `closure_criteria`. Written through the existing atomic +
   revision-CAS ledger path (`status._load_for_write`/`_finalize`).
2. **Finding lifecycle** — `handoff finding fix|verify` drive a monotonic, fail-closed
   `OPEN → FIXED → VERIFIED` machine (mechanical guard; no auto-verify), linking each correction to
   its task/commit(s)/evidence and originating cycle.
3. **Blocking-approval invariant** — `blocking_approval_check` is wired into
   `status.cmd_transition_phase` at the DONE/APPROVED gate: `APPROVED`/`DONE` fail closed (exit 1)
   while any blocking finding across any round is unverified; **degrades** to the Feature 006 gate
   when no structured findings exist (Rule 5).
4. **Handoff close, validation & reports** — `handoff close` (closability-gated, idempotent),
   `handoff validate` (four defect classes, exit 1), `handoff report` (human + JSON parity, stable
   `output_version`).
5. **Markdown projection & re-sourcing** — `revisions/revision-X.md` is rendered *from* the
   structured state in the byte-compatible `<file>:<line> - <action>` format; Feature 010's
   `trace._findings` re-sources findings (resolving stable ids) with a fallback to legacy parsing.
6. **Ledger v4 → v5** — an additive schema bump nests `handoff` on review-cycle records, with a
   deterministic migration (no backfill; absence = zero findings), read-compat for prior shapes,
   and new finding-shape invariants; every JSON output carries `output_version`.

Legacy revision prose stays a supported prior shape (`handoff import` is opt-in, `advisory` by
default, and never retroactively blocks). Evidence is *linked* as the existing `<CLASS>:<summary>`
string (structured evidence is Feature 012); findings introduce **no** issue-tracker integration
and **no** parallel correction ownership. Every behavior is proven by fixtures under `tests/`, never
by running `specops` against this repository (No Self-Application; memory:
[[no-specops-self-application]]).

## Technical Context

**Language/Version**: Python ≥ 3.10 (`pyproject.toml` `requires-python = ">=3.10"`; ruff/mypy target
`py310`, `disallow_untyped_defs = true`).

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), GitPython (commit resolution for `fix
--auto`). **No new runtime dependency** — findings/handoffs are pure structures over the parsed
ledger; commit collection reuses `gitops.commits_in_range`. Honors the constitution's
Typer/PyYAML/GitPython-only limit.

**Storage**: Reads/writes the per-feature Ledger `specs/*/status.yaml` (Feature 006, **v4 → v5**);
nests `handoff` on `review_cycles[i]`. Renders `specs/*/revisions/revision-*.md` from that state and
reads legacy prose for `import`/fallback. No new persisted file.

**Testing**: pytest. New: `tests/unit/test_handoff.py` (id scheme + stability, finding shape,
lifecycle preconditions + illegal transitions, blocking-approval predicate, four validation defects,
close idempotency, determinism + `output_version`, render byte-equality), `tests/integration/
test_handoff_cli.py` (exit/status/`--json` matrix for `finding add|fix|verify`, `authorize`,
`close`, `validate`, `report`, `import`; degenerate not-a-repo). Extended: `tests/unit/
test_ledger.py` + `tests/integration/test_ledger_migration.py` (v4→v5 additive migration + read-
compat + finding invariants), `tests/unit/test_status.py` (approval-gate block/permit/degrade),
`tests/unit/test_trace.py` (re-source structured findings; legacy fallback unchanged). Fixtures via
`conftest.py` builders (ledger with a rejected cycle + findings in each state; a v4 ledger; a legacy
revision file; each defect seed). Coverage threshold **85%** (`--cov-fail-under=85`).

**Target Platform**: Cross-platform CLI + Spec Kit extension. Finding structures and the approval
predicate are pure over the parsed ledger; `fix --auto` reads Git via GitPython; every write is
atomic + interruption-safe + CAS-guarded.

**Project Type**: Single-project Python CLI + Spec Kit extension. New `handoff` subcommands register
through a new `handoff_app` Typer group; the approval invariant joins the existing
`status.cmd_transition_phase` gate; the extension install ships the updated directive templates.

**Performance Goals**: Determinism is total (SC-001/SC-008): every read command is byte-for-byte
reproducible (canonical order = round, severity, file codepoint, line, id; canonical serialization;
no timestamps in read output). The approval predicate and validation are O(findings) over the
in-memory ledger.

**Constraints**: `report`/`validate` are read-only (FR-016, verified by before/after comparison);
every write goes through `ledger.save` (interruption-safe, lost-update-safe — FR-002); the
`VERIFIED` guard is mechanical, never a semantic judgment (FR-006, Principle IV owns the judgment);
commit-existence stays owned by `reconcile` (FR-011); domain-agnostic (Principle V); exit codes as
gates (Principle VI).

**Scale/Scope**: One new module (`handoff.py`: findings/handoff records + lifecycle + validation +
report + render + `blocking_approval_check`); a Ledger v4→v5 additive migration + finding
invariants; an approval-gate hook in `status.py`; a `trace._findings` re-source; a `handoff_app`
CLI group; additive directive-template wiring; a MINOR constitution amendment.

## Constitution Check

*GATE: evaluated pre-Phase 0 and re-checked post-Phase 1. Result: PASS, contingent on the
human-approved MINOR constitution amendment noted under Principle IV.*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** (NON-NEGOTIABLE) | **PASS.** All new surfaces are additive Typer subcommands, one additive approval-gate check inside SpecOps's own phase transition, a ledger schema bump, and SpecOps-owned directive templates. No Speckit-owned file/command/workflow is forked or destructively edited; no Spec Kit primitive (engine/gate/resume/loop) is reimplemented (Rule 8). |
| **II. Physical State Ledger (Repo-as-State)** | **PASS.** Findings/handoffs are written through a versioned bump (`v4 → v5`) with a deterministic forward migration and read-compat; writes use the existing atomic + revision-CAS `save`. A rejected review is reconstructable from the ledger alone (FR-020). Commit-existence enforcement stays delegated to `specops reconcile` (FR-011). `report`/`validate` never mutate state. |
| **III. Automated Evidence Collection** | **PASS (unaffected).** Evidence representation is untouched (structured evidence is Feature 012); a `FIXED` finding *links* the existing machine-collected `<CLASS>:<summary>` string (validated by `status._validate_evidence`). Completion/verification are read mechanically from state, not agent narration. |
| **IV. Surgical Agent Behavior via Injected Prompts** | **PASS — requires a MINOR constitution amendment (1.6.0 → 1.7.0).** The **Token-Optimized Review** directive now authors *structured* findings (`handoff finding add`), runs `handoff finding verify`, and `handoff close` — `revision-X.md` becomes a rendered projection — and the **Ledger & Phase Wiring** directive lets implement mark findings `FIXED`. Per Governance a Principle IV directive change bumps the version and propagates to `src/specops/templates/`. Additive (no principle removed/redefined); submitted in the same change set for **explicit human approval** (roadmap §3). |
| **V. Domain Agnosticism** | **PASS.** Findings (id/severity/rule/path/line/action/evidence strings), the handoff record, the lifecycle states, and the four defect kinds are stack-neutral; no framework/business coupling; **no new runtime dependency**; no source-code parser (FR-022). |
| **VI. Exit Codes as Gates** | **PASS.** Every `handoff` command and the approval hook map onto the fixed taxonomy — `0` (recorded/fixed/verified/closed/validate-ok/report-ok, incl. idempotent re-close and the no-findings degrade), `1` (blocking: `approval-blocked`, `close-blocked`, each validation defect), `2` (usage: illegal transition, precondition unmet, unknown task/finding, duplicate-id at creation, not-a-repo, bad args) — plus a stable `status` field and `output_version` for versioned branching. |

**Development-workflow compliance**: Built with plain Spec Kit; **no** ledger or `specops`
invocation is created/run against this repository. All delivered behavior is exercised via `tests/`
fixtures (Constitution §Development Workflow & Quality Gates; memory:
[[no-specops-self-application]]). The directive templates are product assets edited here but never
executed against this repo.

## Project Structure

### Documentation (this feature)

```text
specs/011-structured-corrective-handoff/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions R1–R15
├── data-model.md        # Phase 1 output — handoff/finding records, lifecycle, defects, v4→v5, taxonomies
├── quickstart.md        # Phase 1 output — run + validate every SC via fixtures
├── contracts/           # Phase 1 output
│   ├── handoff-cli.md         # handoff command surface: args, exit codes, status, output_version
│   ├── finding-lifecycle.md   # OPEN→FIXED→VERIFIED preconditions + blocking-approval invariant + close
│   ├── handoff-ledger.md      # v5 record placement, migration, invariants, CAS/idempotency
│   └── revision-render.md     # revision-X.md projection, trace re-sourcing, legacy import
├── checklists/
│   ├── requirements.md  # spec-quality checklist (from /speckit-specify)
│   └── handoff.md       # requirements-quality checklist (from /speckit-checklist)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Paths verified against the current worktree; action suffixes per Constitution Principle IV
(Empirical Verification). `specops consistency` (a delivered capability) validates these against the
worktree in this feature's own tests — it is not run against this repo.

```text
src/specops/
├── handoff.py                          (create)  # NEW module — the corrective-handoff domain:
│                                                  #   Finding/Handoff records (nested on review_cycles);
│                                                  #   R<round>-F<NN> id assignment; OPEN→FIXED→VERIFIED lifecycle
│                                                  #   with mechanical guards; blocking_approval_check (feature-global);
│                                                  #   validate() → four defect kinds; render_revision() projection;
│                                                  #   cmd_finding_add/authorize/fix/verify/close/validate/report/import;
│                                                  #   HandoffResult contract (status→class→exit) + _STATUS_CLASS + OUTPUT_VERSION
├── ledger.py                           (modify)  # CURRENT_SCHEMA 4→5; migrate_to_current: additive (no findings backfill);
│                                                  #   validate_invariants: finding-shape checks (severity/state/id-unique/
│                                                  #   blocking-closure/links); read-compat for pre-v5 ledgers
├── status.py                           (modify)  # cmd_transition_phase DONE/APPROVED gate: call blocking_approval_check
│                                                  #   BEFORE recording APPROVED / entering DONE (fail closed, name findings);
│                                                  #   degrade when no handoffs (FR-008)
├── trace.py                            (modify)  # _findings(): prefer structured handoff findings (emit stable id),
│                                                  #   fall back to revision-X.md parsing (legacy) — additive, no 010 regression
├── cli.py                              (modify)  # register `handoff finding add|fix|verify`, `authorize`, `close`,
│                                                  #   `validate`, `report`, `import`; _emit_handoff bridge (mirror _emit_trace)
└── templates/
    ├── directives/implement.md         (modify)  # note: mark a resolved finding FIXED via `handoff finding fix` (additive)
    └── review.md                       (modify)  # author structured findings; verify + close; revision-X.md is rendered
                                                   #   (additive) — the /specops-review directive asset

.specify/memory/constitution.md         (modify)  # MINOR amendment 1.6.0→1.7.0 (Principle IV directive extension)

tests/
├── unit/
│   ├── test_handoff.py                 (create)  # id scheme + stability; finding shape/optionality; lifecycle
│   │                                             #   preconditions + illegal transitions (exit 2); blocking-approval
│   │                                             #   predicate; four validation defects; close idempotency;
│   │                                             #   determinism + output_version; render byte-equality
│   ├── test_ledger.py                  (modify)  # + v5 finding/handoff shape + invariant tolerance/enforcement
│   ├── test_status.py                  (modify)  # + approval gate blocks/permits/degrades; advisory never blocks
│   └── test_trace.py                   (modify)  # + structured re-source (stable ids) + legacy fallback unchanged
├── integration/
│   ├── test_handoff_cli.py             (create)  # exit/status/--json matrix for add/authorize/fix/verify/close/
│   │                                             #   validate/report/import; not-a-repo; approval-block via transition
│   └── test_ledger_migration.py        (modify)  # + v4→v5 additive migration + read-compat + zero data loss
├── conftest.py                         (modify)  # + builders: rejected-cycle ledger with findings in each state,
│                                                  #   v4 ledger, legacy revision-X.md, each defect seed
└── fixtures/                           (modify)  # + as needed (static, per existing convention)
```

**Structure Decision**: Single-project layout (existing). The corrective-handoff domain gets its
**own module** (`handoff.py`) rather than joining `status.py` or `trace.py`, because it owns a new
record family (findings/handoffs), a lifecycle state machine, a validation surface, and a Markdown
projection — the same cohesion rationale that gave Feature 010 `trace.py` and Feature 007
`outcome.py` their own modules. The one cross-module hook (the blocking-approval invariant) lives at
`status.cmd_transition_phase`'s single DONE/APPROVED choke point so there is one approval authority
(Rule 8), and findings are written behind the ledger's versioned schema reusing
`status._load_for_write`/`_finalize` for identity + CAS. No new engine module, no orchestration
runtime, no new dependency.

## Complexity Tracking

> No Constitution Check *violations*. The MINOR constitution amendment (Principle IV directive
> extension) is a required **governance action**, not a complexity exception, and is listed for
> visibility. No new runtime dependency is introduced. The table is otherwise intentionally empty.

| Item | Why Needed | Simpler Alternative Rejected Because |
|------|------------|--------------------------------------|
| Constitution amendment 1.6.0→1.7.0 | The delivered lifecycle behavior — structured findings replace `revision-X.md` prose, and review verifies/closes them — is only real if the Principle IV review/implement directives drive it | Shipping only the CLI without the directive change would leave the roadmap's "structured corrective handoff" undelivered in the actual lifecycle; the amendment is additive and human-approved |
| Approval hook in `status.cmd_transition_phase` (vs a new `review` gate) | "Prevent approval while blocking findings remain unverified" (FR-007) is a **phase-transition** decision, and the DONE/APPROVED gate is its single choke point | A second `review.GATE_ORDER` gate would split the approval authority across two engines and duplicate the cycle-result check Feature 006 already owns |

## Phase 0 — Research

See [research.md](./research.md). Decisions **R1** (v5 placement: `handoff` nested on
`review_cycles[i]`), **R2** (`R<round>-F<NN>` id scheme, CHK001), **R3** (finding shape + field
optionality, CHK005), **R4** (handoff shape + zero-findings = no `handoff` key, CHK006), **R5**
(lifecycle preconditions + guard/audit two-surface coherence, CHK018/CHK019/CHK021/CHK027), **R6**
(blocking-approval invariant wired into the DONE/APPROVED gate + degrade), **R7** (close: closability
vs closed, FR-023), **R8** (revision-X.md projection in the 010-compatible line format, CHK008),
**R9** (Feature 010 trace re-sourcing + legacy fallback, CHK033), **R10** (opt-in legacy import,
`advisory` default, FR-014), **R11** (canonical ordering + determinism, CHK004/CHK013/CHK014/CHK015),
**R12** (status enumeration + exit taxonomy + `output_version` + human/JSON parity,
CHK002/CHK010/CHK018), **R13** (`handoff` CLI group), **R14** (MINOR constitution amendment scope),
**R15** (validated dependencies bound to concrete symbols, CHK043). All three `/speckit-clarify`
answers are folded in and every deferred `handoff.md` checklist item is resolved; **no
`NEEDS CLARIFICATION` remain**.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the Corrective Handoff, Finding, Handoff Defect entities; the
  lifecycle state machine and blocking-approval predicate; the v4→v5 migration + invariants; and the
  status→class→exit / `output_version` mapping.
- [contracts/](./contracts/) — the `handoff` CLI surface, the finding lifecycle + approval invariant
  + close, the ledger v5 record/migration/CAS contract, and the revision-render / trace-re-source /
  legacy-import contract.
- [quickstart.md](./quickstart.md) — install → seed a rejected-cycle v5 ledger → record findings →
  drive `fix`/`verify`/`close` → hit the approval gate → `validate`/`report` → render + re-source +
  migrate — validating every Success Criterion via fixtures.

**Agent context update**: no repository agent-context file is maintained for SpecOps (development is
plain Spec Kit); this step is a no-op here and recorded for traceability.

**Post-Design Constitution re-check**: PASS (unchanged). The design adds one module, one approval
hook at the existing transition gate, one additive ledger schema bump with migration, one trace
re-source, and additive CLI/directives — no new dependency, no reimplemented Spec Kit primitive, no
self-application. The MINOR amendment remains the only governance action and is human-approved in the
same change set.
