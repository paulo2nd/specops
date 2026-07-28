# Implementation Plan: GitPython Removal

**Branch**: `020-gitpython-removal` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/020-gitpython-removal/spec.md`

## Summary

Replace GitPython with direct `git` plumbing invocations behind the existing
`gitops` seam. `gitops` becomes the single git access layer, exposing a small
SpecOps-owned `Repository` abstraction (root, branch, HEAD, commit ranges,
ancestry/merge-base, commit existence, blob/tree lookup, symbolic-ref, porcelain
status, tracked-file listing, name-status/name-only diffs) implemented over
`git` subprocess calls. GitPython's error taxonomy is mapped onto a single
`gitops`-owned error type routed to the existing SpecOps error contract, so exit
codes and diagnostics stay identical. The `gitpython`/`gitdb`/`smmap` runtime
dependencies and the `git.*` mypy override are removed; the constitution's
dependency list is amended in the same change set. The only sanctioned surface
deltas are additive: a `blocking` git-availability finding in `specops doctor`
and a clean fail-closed diagnostic from `specops init` when `git` is absent
(both on error paths that carry no defined output contract today). Behavior is
proven byte-identical against the Feature 018 golden-capture harness plus the
subprocess smoke set (Ubuntu 3.10/3.12/3.14 + the Windows leg already in CI).

## Technical Context

**Language/Version**: Python ≥3.10 (CI matrix: 3.10, 3.12, 3.14 on Ubuntu; 3.12 on Windows)

**Primary Dependencies**: Typer (CLI), PyYAML (ledger), `packaging` (version compare). **Removed**: `gitpython`, `gitdb`, `smmap`. No new runtime dependency is added — git access moves to the `git` executable already required today.

**Storage**: Files — `status.yaml` ledger, `specops.json`, `lane.yaml`, gate-profile YAML. Unchanged (no schema bump).

**Testing**: pytest (+ pytest-xdist, pytest-cov; coverage floor 85%), mypy (python_version 3.10), ruff. Feature 018 golden-capture harness + subprocess smoke set are the behavior-freeze mechanism.

**Target Platform**: Linux and Windows (CI matrix); offline after install. Requires a functional `git` on PATH — already an implicit precondition (GitPython itself requires an installed `git`).

**Project Type**: Single-project CLI (`src/specops/`, `tests/`).

**Performance Goals**: No regression. `_require_git` must still fail within <1 s when not in a repo (existing SC-008 of Feature 001). No new performance work.

**Constraints**: Byte-identical CLI human/JSON output, exit codes, and ledger writes except the two sanctioned additive deltas (doctor git check, init git-absent diagnostic). No new runtime dependency. No new CLI command or option. `specops preflight`/read-only commands stay read-only. No `git.*` mypy override or replacement suppression.

**Scale/Scope**: ~14 git operations, all currently in `gitops.py` plus direct `import git` in `review.py`, `status.py`, `cli.py`; 5 catch sites referencing `gitops.git.GitCommandError` (trace ×2, consistency ×1, lane ×2); `git.Repo` type in ~10 signatures.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.9.1. Evaluated against all six Core Principles, Technical
Constraints, and the Stop-and-Ask gates:

- **I. Speckit Extension, Never Replacement** — PASS. Internal refactor; no
  Speckit file, command, or workflow is touched. `specops init` still validates
  a Git repository (offering `git init`) exactly as Principle I requires — now
  via plumbing, and hardened to fail closed first when `git` itself is absent.
- **II. Physical State Ledger (Repo-as-State)** — PASS. No ledger format change.
  `specops reconcile`'s "every commit hash exists in the Git tree" check and its
  exit-code-1-on-divergence contract are preserved; the underlying commit-existence
  and ancestry queries move to plumbing with identical results.
- **III. Automated Evidence Collection** — PASS. `complete-task --auto` still
  harvests commit hashes and `CODE_DIFF` via Git; the diff/commit-range queries
  move to plumbing with byte-identical output. No evidence-record change.
- **IV. Surgical Agent Behavior via Injected Prompts** — PASS. No directive or
  template change. The drift gate's effective-diff computation and `git status
  --porcelain` read are preserved behind the same `gitops` functions.
- **V. Domain Agnosticism** — PASS. `git` is generic VCS plumbing, not a
  client stack; no coupling introduced. Behavior stays configured only via
  `specops.json`.
- **VI. Exit Codes as Gates** — PASS. `SpecopsError` (exit 1) / `LedgerParseError`
  (exit 2) contract preserved; the new git-availability precondition fails closed
  as a `SpecopsError` (exit 1), and the doctor finding maps `blocking → exit 1`
  via the existing severity→exit-code map.
- **Technical Constraints — Dependencies** — REQUIRES AMENDMENT (sanctioned).
  The dependency list names GitPython; FR-008 removes it. This is a PATCH-level
  constitution amendment (the enumeration updates; the rule "new runtime
  dependencies require justification" is unchanged), landing in the same change
  set — the same discipline the `packaging` addition followed (#24). This is a
  *removal*, so no Complexity Tracking justification for a new dependency is
  needed.
- **Stop-and-Ask Gates** — NOT TRIGGERED. No persisted-schema change, no secrets,
  no public-contract break (the `Repository` abstraction replaces `git.Repo` only
  in maintainer-facing internal signatures; the supported surface remains the CLI,
  unchanged). No destructive/irreversible action.

**Result: PASS.** No unjustified violations. The one governing-document change
(dependency-list amendment) is a required, roadmap-sanctioned PATCH.

## Project Structure

### Documentation (this feature)

```text
specs/020-gitpython-removal/
├── plan.md              # This file
├── research.md          # Phase 0 output — operation→plumbing mapping, error taxonomy, decisions
├── data-model.md        # Phase 1 output — Repository, GitError, DiffEntry, git-availability precondition
├── quickstart.md        # Phase 1 output — validation scenarios
├── contracts/           # Phase 1 output — repository-abstraction.md, git-invocation.md
│   ├── repository-abstraction.md
│   └── git-invocation.md
└── checklists/
    └── requirements.md  # From /speckit-specify (20/20)
```

### Source Code (repository root)

```text
src/specops/
├── gitops.py        # (modify) becomes the SOLE git access layer: git-invocation
│                    #   helper (argv subprocess), Repository abstraction, GitError,
│                    #   all operations reimplemented over plumbing. No `import git`.
├── review.py        # (modify) drop `import git`; type as gitops.Repository
├── status.py        # (modify) drop `import git`; type as gitops.Repository (5 signatures)
├── cli.py           # (modify) drop `import git`; _require_git -> gitops.Repository;
│                    #   ls-files via abstraction; init git-availability first-step (FR-013)
├── trace.py         # (modify) symbolic_ref/merge_base via abstraction; catch gitops.GitError
├── consistency.py   # (modify) catch gitops.GitError (was gitops.git.GitCommandError)
├── lane.py          # (modify) porcelain status + diffs via abstraction; catch gitops.GitError
├── doctor.py        # (modify) add blocking git-availability check in _domain_environment
└── reconcile.py     # (verify) uses gitops functions only; confirm no direct git

pyproject.toml       # (modify) remove gitpython dep; remove [[tool.mypy.overrides]] git.*
.specify/memory/constitution.md  # (modify) amend Technical Constraints dependency list

tests/
├── unit/            # (add) gitops plumbing unit tests: each operation + error mapping,
│                    #   unborn/detached HEAD, rename-aware/decomposed diff, blob-absent,
│                    #   non-UTF-8 & Windows-class paths, git-availability precondition
├── integration/     # (add) init/doctor git-absent behavior; golden replay hooks
└── (golden harness) # (reuse) Feature 018 golden-capture + subprocess smoke set
```

**Structure Decision**: Single-project CLI layout (existing). All git access is
consolidated into the existing `src/specops/gitops.py` module — the seam already
named by the roadmap — with every other module depending only on
`gitops.Repository` / `gitops.GitError` and the module-level functions.

## Complexity Tracking

No Constitution Check violations require justification. The feature removes
dependencies and adds no new one; the sole governing-document change is the
sanctioned PATCH amendment to the dependency enumeration (FR-008), not an added
complexity.

| Item | Disposition |
|------|-------------|
| Remove `gitpython`/`gitdb`/`smmap` | Roadmap-sanctioned; PATCH constitution amendment in same change set |
| Hand-mapped git error taxonomy | Accepted: a single `gitops.GitError` + `find_repo`→None / `[]`/`None`/`False` degradations replace the library taxonomy 1:1 (see contracts/git-invocation.md) |
| New runtime dependency | None added (git binary already required) — no justification needed |
```
