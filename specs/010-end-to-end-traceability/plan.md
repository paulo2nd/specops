# Implementation Plan: End-to-End Traceability

**Branch**: `010-end-to-end-traceability` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-end-to-end-traceability/spec.md`

## Summary

Materialize a deterministic **end-to-end trace** — success criterion → task → contexts/paths → commits → evidence → review findings → corrections — from the existing Ledger v3 (Feature 006) and context provenance (Feature 009), and use it to classify every **effective-diff** path as `planned` / `discovered-and-acknowledged` / `unexplained` so review blocks *only* unexplained drift. Nothing in Spec Kit's engine is reimplemented (Rule 8) and no language-specific parser is added (Principle V): the trace is read out of state SpecOps already records mechanically. The feature delivers five surfaces plus a one-time state-changing action and a ledger schema bump:

1. **Path classification + review drift gate** — a new `trace.py` classifier computes the effective diff (ledger `baseline` → `HEAD`, renames decomposed, `--path` override) and labels each path. It is wired into `review.evaluate` as a new terminal **`drift`** gate that FAILs (exit `1`) only when an `unexplained` path exists, and exposed standalone as `specops trace classify` (read-only, stable JSON).
2. **Acknowledgement** — `specops trace acknowledge <path> --task <id> --reason <text>` records a **path-level** acknowledgement through the existing atomic + revision-CAS ledger write, moving a discovered path to `discovered-and-acknowledged`. Idempotent for an identical triple; fail-closed (exit `2`) on a conflicting acknowledgement or unknown task; no-op (exit `0`) on an already-`planned`, never-discovered path.
3. **Trace report** — `specops trace report` renders the full chain in concise text and stable JSON, surfacing `discovered-and-acknowledged` paths distinctly with their reason + task.
4. **Trace validation** — `specops trace validate` fails closed (exit `1`) on the four defect classes: uncovered success criterion, completed-task-without-evidence / user-story-final-task-without-commit, dangling reference, contradictory ownership; commit-existence enforcement is deferred to `specops reconcile` (Principle II).
5. **Context provenance & findings consumption** — the trace reads the Feature 009 `context_provenance` on task/cycle records and the `revisions/revision-X.md` findings (linked by `[File]` token + cycle round), introducing **no** per-finding identifiers (Feature 011).
6. **Acknowledgement ledger schema** — a `v3 → v4` bump adds the `acknowledgements` list with a deterministic migration that backfills `[]` onto prior ledgers (read-compatible); every JSON output carries an explicit `output_version`.

The **map-digest drift** already surfaced by `review.digest_drift_warning` stays a **non-blocking** warning (spec SC-008): the drift 010 *enforces* is unexplained **path** drift, not digest drift. All new read commands reuse the `0/1/2` exit taxonomy with a stable `status` field; the acknowledgement write reuses `status._load_for_write`/`_finalize` (identity gate + CAS). Every behavior is proven by fixtures under `tests/`, never by running `specops` against this repository (No Self-Application; memory: [[no-specops-self-application]]).

## Technical Context

**Language/Version**: Python ≥ 3.10 (`pyproject.toml` `requires-python = ">=3.10"`; ruff/mypy target `py310`).

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), GitPython (effective diff / commit resolution). **No new runtime dependency** — trace materialization, classification, and validation are pure functions over the parsed ledger, the parsed context map (Feature 008 engine), and Git diff/commit reads already wrapped by `gitops`. This honors the constitution's Typer/PyYAML/GitPython-only limit.

**Storage**: Reads the per-feature ledger `specs/*/status.yaml` (Feature 006, currently v3) and the repo-wide map `.specify/specops/context-map.yaml` (Feature 008). Writes only the ledger to add the `acknowledgements` list; schema advances **v3 → v4**. Reads `specs/*/revisions/revision-*.md` (Feature 004/injected-review convention) for findings. No new persisted file is introduced.

**Testing**: pytest. New: `tests/unit/test_trace.py` (trace graph, classification + precedence + rename decomposition, four validation defects, acknowledgement idempotency/conflict/unknown-task/already-planned, determinism, `output_version`), `tests/integration/test_trace_cli.py` (exit/status/`--json` matrix for `classify`/`report`/`validate`/`acknowledge`; Git-default degenerate cases; drift gate inside `specops review`). Extended: `tests/unit/test_ledger.py` + `tests/integration/test_ledger_migration.py` (v3→v4 acknowledgement migration, backfill, read-compat), `tests/unit/test_review.py` (drift gate blocks unexplained / passes planned+acknowledged; digest drift stays non-blocking), `tests/unit/test_gitops.py` (rename-decomposed effective diff). Fixtures under `tests/fixtures/` (ledgers with completed/broken chains, revision files, contradictory-ownership maps). Coverage threshold **85%** (`--cov-fail-under=85`).

**Target Platform**: Cross-platform CLI + Spec Kit extension. Trace materialization and validation are pure over parsed inputs; classification and reporting read Git (diff/commits) via GitPython; the acknowledgement write is atomic + interruption-safe.

**Project Type**: Single-project Python CLI + Spec Kit extension. New `trace` subcommands register through a new `trace_app` Typer group; the drift gate joins `review.GATE_ORDER`; the extension install ships the updated directive templates.

**Performance Goals**: Determinism is total (SC-001): classification and every report are byte-for-byte reproducible (Unicode-codepoint ordering, canonical serialization, no timestamps in read outputs). Effective diff is a single `git diff --no-renames` read; classification is O(paths × contexts) reusing Feature 008's glob engine; trace materialization is O(SCs + tasks + commits + findings) over the in-memory ledger.

**Constraints**: All four trace read commands are read-only (FR-012, verified by before/after state comparison); the acknowledgement write goes through the existing atomic + revision-CAS `ledger.save` (interruption-safe, lost-update-safe — FR-005/FR-006); fail-closed on invalid/ambiguous/unsupported map, deferring to `context validate` (FR-013/FR-017); commit-existence stays owned by `reconcile` (FR-010); domain-agnostic (Principle V); exit codes as gates (Principle VI).

**Scale/Scope**: One new module (`trace.py`) with classification + trace-graph + validation + acknowledgement; a `gitops` rename-decomposed diff helper; a Ledger v3→v4 acknowledgement migration; a new `drift` gate in `review.py`; a `trace_app` CLI group; additive directive-template wiring; a MINOR constitution amendment.

## Constitution Check

*GATE: evaluated pre-Phase 0 and re-checked post-Phase 1. Result: PASS, contingent on the human-approved MINOR constitution amendment noted under Principle IV.*

| Principle | Assessment |
|---|---|
| **I. Speckit Extension, Never Replacement** (NON-NEGOTIABLE) | **PASS.** All new surfaces are additive Typer subcommands, one additive review gate, and SpecOps-owned directive templates. No Speckit-owned file/command/workflow is forked or destructively edited. No Spec Kit primitive (engine/gate/resume/loop) is reimplemented (Rule 8) — the trace is a read over SpecOps's own ledger. |
| **II. Physical State Ledger (Repo-as-State)** | **PASS.** The trace is materialized *from* the Git-verifiable ledger, never from agent memory. The acknowledgement extends the ledger through a versioned bump (`v3 → v4`) with a deterministic forward migration and read-compat; writes use the existing atomic + revision-CAS `save`. Commit-existence enforcement remains delegated to `specops reconcile` (FR-010) — the trace surfaces a dangling reference but does not duplicate or contradict reconcile's authoritative block. The three read commands never mutate state. |
| **III. Automated Evidence Collection** | **PASS (unaffected).** Evidence representation is untouched (structured evidence is Feature 012); the trace *links* the existing machine-collected `<CLASS>:<summary>` string. Completed-task/final-commit completeness is read mechanically from ledger task state, not agent narration. |
| **IV. Surgical Agent Behavior via Injected Prompts** | **PASS — requires a MINOR constitution amendment (1.5.0 → 1.6.0).** This feature *extends* the **Token-Optimized Review** directive (the review agent now also runs the deterministic `drift` gate / `specops trace validate`, and records acknowledgements are honored) and the **Stop-and-Ask / Ledger & Phase Wiring** directives (implement may `trace acknowledge` a genuine discovery). Per Governance a Principle IV directive change bumps the version and propagates to `src/specops/templates/directives/`. The amendment is additive (no principle removed/redefined) and is submitted in the same change set for **explicit human approval** (roadmap §3). |
| **V. Domain Agnosticism** | **PASS.** Path classes, the acknowledgement record (path/task/reason/digest/timestamp strings), the trace graph, and the four defect kinds are all stack-neutral; no framework/business coupling; **no new runtime dependency**. No source-code dependency/diff parser beyond Git's own name-only diff (FR-019). |
| **VI. Exit Codes as Gates** | **PASS.** `classify`, `report`, `validate`, and `acknowledge` map every outcome onto the fixed taxonomy — `0` (success incl. empty-diff, no-map, all-explained, already-planned no-op), `1` (blocking: any `unexplained` path; any uncovered-SC / missing-evidence-or-commit / dangling-reference / contradictory-ownership defect), `2` (usage/input: not a Git repo, no resolvable baseline, conflicting or unknown-task acknowledgement) — plus a stable `status` field and an `output_version` for fine-grained, versioned branching. |

**Development-workflow compliance**: Built with plain Spec Kit; **no** ledger, `context-map.yaml`, or `specops` invocation is created/run against this repository. All delivered behavior is exercised via `tests/` fixtures (Constitution §Development Workflow & Quality Gates; memory: [[no-specops-self-application]]). The directive templates are product assets edited here but never executed against this repo.

## Project Structure

### Documentation (this feature)

```text
specs/010-end-to-end-traceability/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions R1–R12
├── data-model.md        # Phase 1 output — trace graph, path classes, acknowledgement record, defects, taxonomies
├── quickstart.md        # Phase 1 output — run + validate every SC via fixtures
├── contracts/           # Phase 1 output
│   ├── trace-cli.md            # classify / report / validate / acknowledge: args, exit codes, status, output_version
│   ├── path-classification.md  # effective-diff derivation, class precedence, rename decomposition
│   ├── trace-graph.md          # SC→task→paths/contexts→commits→evidence→findings→corrections + defect rules
│   └── acknowledgement-ledger.md  # acknowledgement record, ledger v3→v4 migration, CAS/idempotency/conflict
├── checklists/
│   ├── requirements.md  # spec-quality checklist (from /speckit-specify)
│   └── traceability.md  # requirements-quality checklist (from /speckit-checklist)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Paths verified against the current worktree; action suffixes per Constitution Principle IV
(Empirical Verification). `specops consistency` (a delivered capability) validates these against
the worktree in this feature's own tests — it is not run against this repo.

```text
src/specops/
├── trace.py                             (create)  # NEW module — the trace domain:
│                                                   #   effective_diff classification (planned/discovered-ack/unexplained,
│                                                   #   discovery precedence); TraceGraph materialization from ledger +
│                                                   #   provenance + revision findings; validate() → four defect kinds;
│                                                   #   cmd_classify/cmd_report/cmd_validate (read-only) + cmd_acknowledge
│                                                   #   (state-changing via status._load_for_write/_finalize); TraceResult
│                                                   #   contract (status→class→exit) + S_* statuses + OUTPUT_VERSION
├── gitops.py                            (modify)  # + effective_diff(repo, baseline): git diff --no-renames baseline..HEAD
│                                                   #   (rename → removed old + added new; mode-only included). Keeps
│                                                   #   name_only_diff for existing callers (rename-collapsing) unchanged.
├── ledger.py                            (modify)  # CURRENT_SCHEMA 3→4; migrate_to_current backfills acknowledgements: [];
│                                                   #   validate_invariants: acknowledgement-shape check (path/task/reason);
│                                                   #   ACK_* constants; read-compat for pre-v4 ledgers
├── review.py                            (modify)  # GATE_ORDER += "drift" (terminal): FAIL only on unexplained paths,
│                                                   #   reusing trace classifier; digest_drift_warning stays non-blocking
│                                                   #   (correct the stale "deferred to Feature 010" comment)
├── cli.py                               (modify)  # register `trace report | validate | classify | acknowledge`; wire
│                                                   #   --path/--json + outcome/exit bridge (mirror _emit_context)
└── templates/
    ├── directives/implement.md         (modify)  # note: `trace acknowledge` a genuine discovered path (additive)
    └── review.md                       (modify)  # run the drift gate / `trace validate`; honor acknowledgements
                                                   #   (additive) — this is the /specops-review directive asset

.specify/memory/constitution.md          (modify)  # MINOR amendment 1.5.0→1.6.0 (Principle IV directive extension)

tests/
├── unit/
│   ├── test_trace.py                   (create)  # classification (precedence, rename-decomposed, deleted, planned/ack/
│   │                                              #   unexplained, no-map fallback); trace graph; four validation defects;
│   │                                              #   acknowledgement idempotent/conflict/unknown-task/already-planned;
│   │                                              #   determinism + output_version
│   ├── test_gitops.py                  (modify)  # + effective_diff rename decomposition + mode-only inclusion
│   ├── test_ledger.py                  (modify)  # + v4 acknowledgement shape + invariant tolerance/enforcement
│   └── test_review.py                  (modify)  # + drift gate blocks unexplained / passes planned+ack; digest non-blocking
├── integration/
│   ├── test_trace_cli.py               (create)  # exit/status/--json matrix for classify/report/validate/acknowledge;
│   │                                              #   Git-default degenerate cases (clean/no-repo/no-baseline); review drift
│   └── test_ledger_migration.py        (modify)  # + v3→v4 migration + acknowledgements backfill + read-compat
├── conftest.py                         (modify)  # + builders (matching the existing inline-fixture convention):
│                                                   #   ledger with complete/broken chain, revision-X.md findings,
│                                                   #   acknowledgements list, pre-v4 ledger
└── fixtures/
    └── context_maps/                   (modify)  # + contradictory-ownership map fixture (static, per existing convention)
```

**Structure Decision**: Single-project layout (existing). The trace domain gets its **own module** (`trace.py`) rather than joining `contextmap.py` or `consistency.py`, because it composes *three* domains (ledger records, context ownership, Git diff) and owns a new read/validate/acknowledge surface — the same cohesion rationale that gave Feature 007 `outcome.py` and Feature 004 `consistency.py` their own modules. The acknowledgement write lives behind the ledger's versioned schema and reuses `status._load_for_write`/`_finalize` for identity + CAS. The drift gate joins the existing `review.GATE_ORDER` engine rather than forking a parallel review path. No new engine module, no orchestration runtime, no new dependency.

## Complexity Tracking

> No Constitution Check *violations*. The MINOR constitution amendment (Principle IV directive extension) is a required **governance action**, not a complexity exception, and is listed for visibility. No new runtime dependency is introduced. The table is otherwise intentionally empty.

| Item | Why Needed | Simpler Alternative Rejected Because |
|------|------------|--------------------------------------|
| Constitution amendment 1.5.0→1.6.0 | Feature 010 must make review block unexplained drift and let implementation acknowledge discoveries, both governed by the Principle IV injected directives | Shipping only the CLI commands without the review-directive drift gate would leave the roadmap's "block review only for unexplained effective-diff paths" undelivered in the actual lifecycle; the amendment is additive and human-approved |
| New `drift` gate in `review.GATE_ORDER` | The "review drift gate" (FR-004) is only a *delivered lifecycle behavior* if it runs inside `specops review`, the deterministic gate engine | A standalone command alone would not gate the real review; adding the gate to the existing engine (vs a second review path) avoids duplicating the reconcile/lint/test/working-tree pipeline |

## Phase 0 — Research

See [research.md](./research.md). Decisions **R1** (effective diff: ledger `baseline`→`HEAD`, merge-base fallback, `--no-renames` decomposition, mode-only included, `--path` bypass), **R2** (path-class model + discovery precedence + `planned` = plan paths ∪ declared-context ownership, reusing `speckit`/`contextmap`), **R3** (acknowledgement record + Ledger v3→v4 + migration + CAS/idempotency/conflict/unknown-task/already-planned semantics), **R4** (trace-graph materialization from ledger records + provenance + revision findings), **R5** (four validation defects + reconcile deferral for commit existence), **R6** (drift gate wired into `review.evaluate`; digest drift stays non-blocking — corrects the 009-era deferral note), **R7** (findings/corrections linkage: `revision-X` ↔ round X, `[File]` token, no finding IDs), **R8** (exit/`status` taxonomy + `output_version` JSON field), **R9** (determinism inputs: codepoint order, canonical serialization, no timestamps in read output), **R10** (`trace` CLI group + outcome/exit bridge), **R11** (directive wiring + MINOR constitution amendment scope), **R12** (completed-SC = all covering tasks DONE; per-task completeness = evidence always, commit only on the user-story-final task). All nine clarifications (two `/speckit-clarify` sessions) are folded in; **no `NEEDS CLARIFICATION` remain**. The deferred `traceability.md` items (status enumeration CHK004, sort keys CHK007, gate invocation point CHK008, concise-reason bound CHK010) are resolved here.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the Trace Graph, Effective-Diff Path, Path Class (with precedence), Acknowledgement Record, Trace Defect, and Trace Report entities; the classification and validation algorithms; the acknowledgement schema and v3→v4 migration table; and the exit/`status`/`output_version` mapping.
- [contracts/](./contracts/) — the CLI contract for the four commands, the path-classification rules (effective-diff derivation + precedence + rename decomposition), the trace-graph + defect rules, and the acknowledgement/migration contract.
- [quickstart.md](./quickstart.md) — install → seed a ledger with a complete and a broken chain → `trace report` → `trace validate` → `trace classify` → `trace acknowledge` → run the review drift gate → validate every Success Criterion via fixtures.

**Agent context update**: no repository agent-context file is maintained for SpecOps (development is plain Spec Kit); this step is a no-op here and recorded for traceability.

**Post-Design Constitution re-check**: PASS (unchanged). The design adds one module, one review gate, one ledger schema bump with migration, and additive CLI/directives — no new dependency, no reimplemented Spec Kit primitive, no self-application. The MINOR amendment remains the only governance action and is human-approved in the same change set.
