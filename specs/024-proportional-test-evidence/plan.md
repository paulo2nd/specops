# Implementation Plan: Test Execution Only at the Review Gate

**Branch**: `024-proportional-test-evidence` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-proportional-test-evidence/spec.md`

## Summary

Move all target-project test execution to the review gate. Two coordinated changes: (1) `complete-task --auto` stops running the client `test_command` and records only mechanical commit + `CODE_DIFF` evidence; (2) the review/preflight gate suite persists a **passing** gate-run as append-only structured evidence (superseding the prior record for the same gate) so the terminal gate reuses the soft gate's already-computed full-suite result instead of re-executing it. Reuse is guarded by a **working-tree digest** added to the existing Feature 012 cache key, so any change — committed or not — invalidates the cache. Only the command-executing gates (`lint`, `test`) participate; state-derived gates (`reconcile`, `working-tree`, `drift`) always recompute. Net effect on the happy path: full-suite executions drop from **U+2 to 1**.

The cache lookup, id derivation, and `append_record(supersede=True)` machinery already exist from Feature 012 but are inert end-to-end because review never persisted gate evidence and the key lacked a working-tree dimension. This feature activates them and closes a latent correctness gap in the cache-hit branch.

## Technical Context

**Language/Version**: Python 3.11 (existing `speckit-specops` package)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), stdlib `hashlib`/`json` (evidence ids); Git via the existing `specops.gitops` subprocess wrapper. No new dependencies.

**Storage**: The feature-scoped ledger (`status.yaml`) under `specs/<feature>/`, schema **v7**. Structured evidence records live in the ledger's `evidence` list.

**Testing**: pytest, run under `conda run -n specops` (unit + integration + golden suites already present).

**Target Platform**: Local dev + CI (any Spec Kit client repo consuming the SpecOps CLI).

**Project Type**: Single-project Python CLI (methodology tooling; Principle V — domain-agnostic).

**Performance Goals**: Reduce redundant full-suite executions per feature run from U+2 to 1 (SC-001/SC-002); a repeated gate run over an unchanged tree executes each cacheable gate command 0 times (SC-003).

**Constraints**: Auto-record ids MUST stay byte-stable (no migration of existing `auto` evidence). Review/preflight MUST NOT mutate task/phase/finding state (narrowed read-only contract — appending gate evidence only). No test-framework-specific logic (Principle V).

**Scale/Scope**: ~6 source modules touched (`status.py`, `review.py`, `evidence.py`, `gitops.py`, `gateprofiles.py` unchanged except naming, `cli.py` minimal), the constitution (Principles III/IV), the implement directive, and their tests. No new CLI commands.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Speckit Extension, Never Replacement | ✅ Pass | No change to the extension/injection mechanism; behavior delivered through existing CLI + directive templates. |
| II. Physical State Ledger | ✅ Pass | Gate-run evidence is recorded in the ledger (the authoritative physical state), consistent with the ledger-as-state model. |
| III. Automated Evidence Collection | ⚠️ Amend (MINOR) | Currently mandates `complete-task --auto` "run the client's `test_command` … including the `TEST_REPORT`." This feature **narrows** it: `--auto` collects commit hashes + `CODE_DIFF` mechanically and runs **no** test; test verification moves to the review gate. Evidence collection stays tooling-driven (not agent-narrated), so the principle's rationale is preserved — only the "runs the test at close" clause is broadened. |
| IV. Surgical Agent Behavior via Injected Prompts | ⚠️ Amend (MINOR) | Currently states "`specops preflight` stays byte-for-byte read-only." This feature **narrows** it to "read-only except appending gate-run evidence records (passing runs, superseding the prior record for the same gate); task, phase, and finding state are never mutated." A broadening of an existing directive, not a removal. |
| V. Domain Agnosticism | ✅ Pass | No framework-specific test selection; the gate still runs the client's configured commands opaquely. Targeted per-story testing was deliberately rejected to keep this true. |
| VI. Exit Codes as Gates | ✅ Pass | No change to the `0`/`1`/`2` contract; preflight verdict/exit semantics unchanged. |

**Verdict**: PASS with two authorized MINOR amendments (Principles III and IV). Per the constitution's own versioning policy, broadening non-removed principles is a MINOR bump: **1.10.0 → 1.11.0**, applied in the same change set (Sync Impact Report + principle bodies + the affected `src/specops/templates/` directive), enforced as an implementation task. No unjustified violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/024-proportional-test-evidence/
├── plan.md              # This file
├── spec.md              # Feature spec (+ Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contracts.md # Phase 1 output — affected CLI behavior contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/specops/
├── status.py            # (modify) _auto_evidence: drop the test run; CODE_DIFF-only evidence
├── review.py            # (modify) profile_gates/_run_profile_gate: persist passing gate evidence
│                        #          (append-only, supersede); fix cache-hit to honor exit_code;
│                        #          add worktree digest to the gate cache key; update read-only note
├── evidence.py          # (modify) cache_key: optional worktree_digest field (conditional, back-compat)
├── gitops.py            # (add)    worktree_digest(repo): hash of uncommitted diff + untracked
├── gateprofiles.py      # (no functional change) lint/test remain the cacheable command gates
└── cli.py               # (verify) _run_gate still delegates to review.evaluate; no signature change

src/specops/templates/
├── directives/implement.md          # (modify) Ledger Loop wording: --auto records diff evidence, no test
└── ... (constitution not here)

.specify/memory/constitution.md      # (modify) Principles III & IV amendments + version 1.11.0 + Sync Impact

tests/
├── unit/test_status.py              # (modify) --auto no longer runs test_command; CODE_DIFF-only
├── unit/test_review.py              # (modify) gate persistence, cached exit_code, worktree-digest invalidation
├── unit/test_evidence.py            # (modify) cache_key worktree_digest; auto-id stability
├── unit/test_gitops.py              # (add)    worktree_digest determinism / invalidation
├── integration/test_gate_readonly_determinism.py  # (modify) narrow read-only to append-only-evidence
├── integration/test_preflight_cli.py             # (modify/add) terminal reuse (cached) over unchanged tree
└── integration/test_workflow_orchestration.py     # (verify) corrective-loop reuse end-to-end
```

**Structure Decision**: Single-project layout (existing). All changes are surgical edits to established modules plus their tests; no new module or CLI command is introduced. The design reuses Feature 012's evidence machinery rather than adding a parallel cache.

## Complexity Tracking

> No Constitution Check violations require justification. The two Principle amendments are authorized broadenings (MINOR), not violations, and are tracked as an implementation task rather than a complexity exception.
