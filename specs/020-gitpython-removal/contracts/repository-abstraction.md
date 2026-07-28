# Contract: `gitops` Repository Abstraction

The single git access layer. After this feature, `gitops` is the **only**
production module that invokes `git`; no other module imports a git library or
names a third-party repository type (FR-002). This contract fixes the surface
other modules bind to — signatures are byte-compatible with today's `gitops`
functions, changing only the `repo` parameter type (`git.Repo` → `Repository`).

## Types

```text
class Repository:            # holds the resolved working-tree root
    root: Path

class GitError(SpecopsError):  # exit_code = 1
    ...
```

## Construction & availability

| Function | Signature | Behavior |
|---|---|---|
| `find_repo` | `(path: Path = Path(".")) -> Repository \| None` | `git -C path rev-parse --show-toplevel`; `None` if not a repo |
| `is_git_repo` | `(path: Path = Path(".")) -> bool` | `find_repo(path) is not None` |
| `ensure_git_available` | `() -> str` | probe `git --version`; return version string, or raise `GitError`/`SpecopsError` with a clear diagnostic when absent/nonfunctional (name TBD in impl) |

## Read operations (all read-only; no mutation of repo or ledger)

| Function | Signature | Non-happy-path contract |
|---|---|---|
| `current_branch` | `(repo) -> str` | detached HEAD → 7-char short sha (verbatim fallback) |
| `head_sha` | `(repo) -> str` | full 40-char sha |
| `commits_in_range` | `(repo, start_sha, end_sha="HEAD") -> list[str]` | unresolvable start → `[]` |
| `is_ancestor` | `(repo, sha) -> bool` | unresolvable/non-ancestor → `False` |
| `merge_base` | `(repo, a, b) -> str \| None` | no common base / unborn HEAD → `None` (trace baseline) |
| `symbolic_ref` | `(repo, name) -> str \| None` | unadvertised ref → `None` (or raise `GitError`, caught by trace) |
| `commit_exists` | `(repo, sha) -> bool` | unresolvable → `False` |
| `blob_sha` | `(repo, rev, path) -> str \| None` | unresolvable rev or absent path → `None` |
| `dirty_files` | `(repo) -> list[str]` | clean tree → `[]` |
| `porcelain_status` | `(repo, *, untracked_all=False) -> list[str]` | lane's `-uall` variant; clean → `[]` |
| `ls_files` | `(repo) -> list[str]` | tracked files; none → `[]` |
| `name_only_diff` | `(repo, start_sha, end_sha="HEAD") -> list[str]` | git error → `[]` |
| `name_status_diff` | `(repo, start_sha, end_sha="HEAD", *, rename_aware, cached=False) -> list[tuple[str,str]]` | **raises `GitError`** — callers own degradation |
| `effective_diff_status` | `(repo, start_sha, end_sha="HEAD") -> list[tuple[str,str]]` | git error → `[]` (catches `GitError`) |
| `effective_diff` | `(repo, start_sha, end_sha="HEAD") -> list[str]` | codepoint-sorted, deduplicated |

## Pure helpers (unchanged, retained verbatim)

- `parse_name_status(raw: str) -> list[tuple[str, str]]`

## Guarantees

- **G1 — single seam**: only `gitops` imports subprocess/git primitives; a scan
  of other production modules for git-library imports returns zero (SC-003).
- **G2 — byte-identical output**: every function returns exactly what the
  GitPython implementation returned for the same repository state (SC-002),
  including ordering and path encoding (`core.quotePath=false` + surrogateescape).
- **G3 — degradation preserved**: the `[]`/`None`/`False` returns above match the
  current except-guards one-for-one (FR-006).
- **G4 — no ledger domain**: no `(human)` sentinel handling in this layer (FR-011).
- **G5 — read-only**: none of these operations write to the repository or ledger.
