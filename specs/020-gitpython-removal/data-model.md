# Phase 1 Data Model: GitPython Removal

This feature introduces no persisted data and no schema change (ledger stays at
its current version). The "entities" here are the internal, maintainer-facing
types that replace GitPython's objects behind the `gitops` seam. None are part of
the supported external surface (which remains the CLI).

## Repository

The SpecOps-owned handle for an open git repository. Replaces `git.Repo` in every
signature.

| Field | Type | Meaning |
|---|---|---|
| `root` | `Path` | Absolute working-tree root, from `git rev-parse --show-toplevel` |

**Construction**: `gitops.find_repo(path) -> Repository | None` — `None` when
`path` is not inside a git repository (maps `InvalidGitRepositoryError` /
`NoSuchPathError`).

**Operations** (module-level `gitops.<fn>(repo, …)` functions, `repo:
Repository`; see `contracts/repository-abstraction.md` for full signatures):
root discovery, `current_branch`, `head_sha`, `commits_in_range`, `is_ancestor`,
`merge_base`, `symbolic_ref`, `commit_exists`, `blob_sha`, `dirty_files`,
porcelain status (incl. `-uall`), `ls_files`, `name_only_diff`,
`name_status_diff`, `effective_diff_status`, `effective_diff`.

**Invariants**:
- Constructing a `Repository` requires a functional `git` (Decision 6); absence
  is a fail-closed precondition, never a silent degradation.
- No ledger-domain knowledge (the `(human)` sentinel stays filtered by callers,
  FR-011 / Feature 019 US4).

## GitError

Single `gitops`-owned exception replacing externally-caught
`git.exc.GitCommandError` (and the `ValueError`/`BadName` unborn-HEAD cases at
the trace baseline site).

| Attribute | Value |
|---|---|
| Base | `SpecopsError` |
| `exit_code` | `1` (blocking) |
| Raised by | `name_status_diff`, `symbolic_ref`, `merge_base`, and the git-availability probe on non-zero exit / missing binary |
| Caught by | `trace.py` (×2), `consistency.py` (×1), `lane.py` (×2) — replacing `gitops.git.GitCommandError` |

Internal helpers that today swallow git errors keep their degradation returns
(`find_repo`→`None`; `commits_in_range`→`[]`; `is_ancestor`/`commit_exists`→
`False`; `blob_sha`→`None`) rather than raising.

## DiffEntry (unchanged)

The `(status, path)` pair produced by `parse_name_status`. Already the single
shared shape from Feature 019 US4; retained verbatim. `status` = first letter of
the git code (`R100`→`R`); `path` = last tab field (NEW path on a rename line).

## Git-availability precondition

Not a stored entity — a shared check with two observable outcomes.

| State | Detection | init (FR-013) | doctor (FR-012) | other git commands |
|---|---|---|---|---|
| present & functional | `git --version` exits 0 | proceeds to repo check / `git init` offer | `ok` finding, detected version shown informationally | run normally |
| absent / nonfunctional | `FileNotFoundError` or non-zero | fail closed, clear diagnostic, exit 1 (no traceback) | `blocking` finding → exit 1 via severity map | fail closed with the shared diagnostic |

No minimum version is enforced (clarification 2026-07-28).

## Removed types

- `git.Repo`, `git.exc.GitCommandError`, `git.BadName`,
  `InvalidGitRepositoryError`, `NoSuchPathError` — no longer imported anywhere.
- `gitops.git` (the re-exported module attribute) — removed; the 5 catch sites
  migrate to `gitops.GitError`.
