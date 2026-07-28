# Contract: Git Invocation & Error Taxonomy

Fixes how `gitops` invokes `git` and how failures map onto the SpecOps error
contract, so exit codes and diagnostics stay identical (FR-005).

## Invocation

- **Mechanism**: argv list via `subprocess.run`, never `shell=True`. No user
  string is interpolated into the argv (injection-safe).
- **Working directory**: the repository root (or the caller's path for
  `find_repo`).
- **Decoding**: stdout/stderr as UTF-8 with `errors="surrogateescape"`.
- **Path fidelity**: diff/status/ls-files invocations pass `-c
  core.quotePath=false` so git emits raw (unquoted) UTF-8 paths, matching
  GitPython's returned values.
- **No timeout**: git plumbing is local and fast; unlike client commands
  (`shell.py`) there is no timeout wrapper.

## Exit-code → outcome mapping

| git exit | Meaning | gitops behavior |
|---|---|---|
| `0` | success | parse stdout, return value |
| non-zero on `rev-parse --show-toplevel` | not a repo | `find_repo` → `None` |
| non-zero on `--verify` probes | unresolvable object/ref | `commit_exists`/`blob_sha`/`commits_in_range` → `False`/`None`/`[]` |
| `1` on `merge-base --is-ancestor` | not an ancestor | `is_ancestor` → `False` |
| `128` on `merge-base --is-ancestor` | bad object | `is_ancestor` → `False` |
| non-zero on `diff`/`symbolic_ref`/`merge_base` | git command failed | raise `GitError` (callers catch & degrade) |
| binary missing (`FileNotFoundError`) | no git on PATH | git-availability precondition fails closed |

## SpecOps error contract (preserved)

| Condition | Exception | Exit code | Where surfaced |
|---|---|---|---|
| Not a git repo (command requires one) | (existing `typer.Exit(1)` in `_require_git`) | 1 | `_require_git` diagnostic — unchanged |
| Git absent/nonfunctional | `GitError`/`SpecopsError` | 1 | new clean diagnostic (init first-step, any git command) |
| Git command failure caught by caller | `GitError` → caller degrades | n/a | trace/consistency/lane degrade paths — unchanged output |
| Ledger parse/corruption | `LedgerParseError` | 2 | unchanged |

## Doctor finding (additive, FR-012)

| git state | severity | fid | message | exit impact |
|---|---|---|---|---|
| present & functional | `ok` | `git-availability` | detected version shown informationally | none |
| absent / nonfunctional | `blocking` | `git-availability` | clear "git not available" diagnostic + next action | `blocking → exit 1` via existing severity→exit map |

Ordered **before** the existing `repo is None` check in `_domain_environment`,
because repo resolution now itself requires git.

## Migration of catch sites

Replace `except gitops.git.GitCommandError` (and the paired `ValueError` at the
trace baseline) with `except gitops.GitError`:

| File | Site | Was | Now |
|---|---|---|---|
| `trace.py` | origin/HEAD symbolic-ref | `gitops.git.GitCommandError` | `gitops.GitError` |
| `trace.py` | merge_base fallback | `(gitops.git.GitCommandError, ValueError)` | `gitops.GitError` |
| `consistency.py` | diff guard | `gitops.git.GitCommandError` | `gitops.GitError` |
| `lane.py` | committed diff | `gitops.git.GitCommandError` | `gitops.GitError` |
| `lane.py` | staged diff | `gitops.git.GitCommandError` | `gitops.GitError` |

Each migration is covered by a unit test asserting the same degradation (empty
result / continue) under a forced git failure.
