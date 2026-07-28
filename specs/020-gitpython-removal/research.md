# Phase 0 Research: GitPython Removal

All `NEEDS CLARIFICATION` from the spec were resolved in the 2026-07-28
clarification session (git precondition = "present & functional", no pinned
minimum version; doctor git finding = `blocking`). This document records the
technical decisions that make the replacement byte-identical.

## Decision 1 — Git invocation mechanism

**Decision**: A single private argv-based runner in `gitops.py`
(`subprocess.run([...], cwd=<root>, capture_output=True)`), decoding stdout as
UTF-8 with a documented error strategy (see Decision 5). **Not** `shell.py`.

**Rationale**: `shell.py`'s `run_client_command` is `shell=True` for
user-authored client command *strings* (test/lint) with process-group timeout
handling — the wrong tool for fixed git argv. Git plumbing needs argv (no shell
interpolation, injection-safe), no timeout (fast local operations), and its own
error mapping. GitPython itself already shells out to `git` for
`repo.git.diff/status/ls_files/symbolic_ref` (over half our surface), so a
subprocess runner is not a new I/O model — it is the model already in use.

**Alternatives considered**: (a) Reuse `shell.py` — rejected: shell=True +
timeout semantics are a mismatch and a mild injection surface. (b) `pygit2`
(libgit2 bindings) — rejected: reintroduces a C-extension runtime dependency,
the opposite of the feature's goal. (c) `dulwich` (pure-Python git) — rejected:
still a dependency; the point is to depend only on the `git` already required.

## Decision 2 — Operation → plumbing command mapping

Every current `gitops` operation and its byte-identical plumbing replacement.
Ordering and shapes verified against GitPython's current behavior.

| Operation (current) | GitPython impl | Plumbing replacement | Identical-output note |
|---|---|---|---|
| `find_repo(path)` | `git.Repo(path, search_parent_directories=True)` | `git -C <path> rev-parse --show-toplevel` → root, else `None` | Non-zero exit / not-a-repo → `None` (maps `InvalidGitRepositoryError`/`NoSuchPathError`) |
| `is_git_repo` | `find_repo is not None` | unchanged (delegates) | — |
| `current_branch` | `repo.active_branch.name`, `TypeError` → `hexsha[:7]` | `git symbolic-ref --quiet --short HEAD`; on non-zero (detached) → `git rev-parse HEAD`, slice `[:7]` in Python | Slicing full sha `[:7]` reproduces GitPython's exact 7-char fallback (avoids `--short` abbrev variance) |
| `head_sha` | `repo.head.commit.hexsha` | `git rev-parse HEAD` | Full 40-char sha |
| `commits_in_range(start,end)` | verify `commit(start)` then `iter_commits(start..end)` | `git rev-parse --verify -q start^{commit}` (else `[]`), then `git rev-list start..end` | `rev-list` default order = `iter_commits` default (reverse-chronological); byte-identical sha list |
| `is_ancestor(sha)` | `merge_base(sha, HEAD)[0] == sha` | `git merge-base --is-ancestor sha HEAD` → exit 0 True; non-zero → False | Bad object (exit 128) and non-ancestor (exit 1) both → False, matching the current except-guard |
| `merge_base(a,b)` (used in trace) | `repo.merge_base(a, HEAD)` → commit list; caller reads `[0].hexsha` | `git merge-base a b` → first line sha, empty → `None` | Preserves trace baseline fallback |
| `symbolic_ref(name)` (trace) | `repo.git.symbolic_ref("--short", name)` | `git symbolic-ref --short name` → str, non-zero → `GitError` | origin/HEAD default detection unchanged |
| `commit_exists(sha)` | `repo.commit(sha)` in try | `git rev-parse --verify -q sha^{commit}` → exit 0 | maps `GitCommandError`/`BadName`/`ValueError` → False |
| `blob_sha(rev,path)` | `repo.commit(rev).tree[path].hexsha`, `KeyError`→None | `git rev-parse --verify -q rev:path` → blob sha, non-zero → `None` | `<rev>:<path>` resolves the blob object hash directly; unresolvable rev or absent path → `None` |
| `dirty_files` | `repo.git.status("--porcelain")` | `git status --porcelain` | already a shell-out; direct |
| porcelain `-uall` (lane) | `repo.git.status("--porcelain","-uall")` | `git status --porcelain -uall` | lane untracked enumeration unchanged |
| `name_only_diff` | `repo.git.diff("--name-only",start,end)` | `git diff --name-only start end`, non-zero → `[]` | — |
| `name_status_diff` | `repo.git.diff("--name-status",flag,[--cached],start,end)` | same argv; non-zero → raise `GitError` | `-M`/`--no-renames`/`--cached` variants unchanged; `parse_name_status` reused verbatim |
| `ls_files` (cli) | `repo.git.ls_files()` | `git ls-files` → non-empty lines | tracked-file enumeration for context orphan check |

`parse_name_status`, `effective_diff_status`, and `effective_diff` are pure
functions over the raw diff text and are **kept verbatim** — only their upstream
invocation changes.

## Decision 3 — The `Repository` abstraction

**Decision**: A small `gitops.Repository` dataclass/class holding the resolved
working-tree root path. Methods correspond 1:1 to the operations above. The
module-level functions (`current_branch(repo)`, `head_sha(repo)`, …) are retained
as thin wrappers **or** converted to methods; to minimize churn and keep
byte-identical call sites, **retain the existing `gitops.<fn>(repo, …)`
module-level function signatures**, changing only the `repo` parameter's type
from `git.Repo` to `gitops.Repository`. Callers that today write
`repo.git.status(...)`, `repo.git.ls_files()`, `repo.git.symbolic_ref(...)`,
`repo.merge_base(...)`, `repo.head.commit`, `repo.active_branch` move to
`gitops` functions/methods.

**Rationale**: keeping the module-level function surface stable makes the diff
mechanical and the golden replay trivially comparable; only the ~7 sites that
reach through to `repo.git.*`/`repo.head`/`repo.merge_base` need rewriting to
abstraction calls.

**Alternatives considered**: full method-oriented API (`repo.head_sha()`) —
rejected as unnecessary churn for a behavior-freeze feature; can follow later.

## Decision 4 — Error taxonomy mapping

**Decision**: One `gitops.GitError(SpecopsError)` replaces every externally-caught
`git.exc.GitCommandError`. Internal degradations (`find_repo`→`None`;
`commits_in_range`→`[]`; `is_ancestor`/`commit_exists`→`False`;
`blob_sha`→`None`) are preserved by mapping non-zero plumbing exits to those same
returns inside `gitops`.

Mapping table:

| GitPython exception (today) | Caught where | New behavior |
|---|---|---|
| `InvalidGitRepositoryError`, `NoSuchPathError` | `find_repo` | rev-parse non-zero → `None` (unchanged contract) |
| `GitCommandError`, `BadName`, `ValueError` | `commits_in_range`, `is_ancestor`, `commit_exists`, `blob_sha` (internal try) | non-zero exit → the same `[]`/`False`/`None` |
| `gitops.git.GitCommandError` | trace.py ×2, consistency.py ×1, lane.py ×2 | `gitops.GitError` (raised by `name_status_diff`/`symbolic_ref` on non-zero) |
| `ValueError` (unborn HEAD / BadName) | trace.py merge_base guard | `gitops.GitError` — the merge_base/symbolic-ref helpers raise `GitError` on unborn HEAD (rev-parse HEAD non-zero); trace catches `gitops.GitError` |

`_require_git` (cli) and `specops doctor` keep emitting their current
diagnostics; the git-availability precondition (below) is the only new message.

**Note**: `gitops.git` (the re-exported module attribute) is **removed**; the 5
catch sites switch to `gitops.GitError`. This is the single riskiest edit set —
each site's expected degradation is enumerated above and covered by a unit test.

## Decision 5 — Path decoding / encoding fidelity

**Decision**: Decode git stdout as UTF-8 with `errors="surrogateescape"` and
disable git's path quoting via `-c core.quotePath=false` on diff/status/ls-files
invocations, matching GitPython's default of returning unquoted, filesystem-faithful
paths. Verified on the Windows CI leg (added specifically for the encoding/path
bug class after the 0.2.1 Windows-only UTF-8 hotfix).

**Rationale**: git by default C-quotes non-ASCII paths in `status`/`diff`/`ls-files`
output (`"\303\251.txt"`); GitPython returns them decoded. `core.quotePath=false`
makes git emit raw UTF-8 bytes, and `surrogateescape` round-trips any
non-decodable bytes without crashing — the closest match to GitPython's behavior
and to the existing `errors="replace"` tolerance elsewhere. The golden harness +
a non-UTF-8 fixture confirm byte-identity.

**Alternatives considered**: `errors="replace"` (matches `shell.py`) — acceptable
fallback but lossy on exotic bytes; `surrogateescape` is strictly more faithful.
Leaving quoting on and un-quoting in Python — rejected: re-implements git's C-quote
parser, more code and more risk than `core.quotePath=false`.

## Decision 6 — Git-availability precondition (FR-012/FR-013)

**Decision**: A single `gitops.ensure_git_available()` (name TBD in impl) that
runs a trivial probe (`git --version`) and raises `gitops.GitError`/`SpecopsError`
with a clear diagnostic when git is absent (`FileNotFoundError`) or non-zero.
Consumed by: `specops init` as its first step (before repo check / `git init`
offer); `_domain_environment` in `doctor.py` as an additive finding — `blocking`
when unavailable, `ok` with the detected version string when present; and
implicitly by every git-dependent command (a missing git surfaces the same clean
diagnostic instead of a `FileNotFoundError` traceback).

**Rationale**: single-sourced per FR-012; "present & functional" (probe runs)
per the clarification; no version parsing/floor because every flag used predates
git ~1.8 (2012). `doctor`'s existing `_domain_environment` already owns the
"Git … repository present" finding, so the git-*binary* check belongs there,
ordered before the repo (`repo is None`) check since repo resolution now itself
needs git.

**Alternatives considered**: pin a minimum version — rejected in clarification
(cost with no realistic benefit). PATH-only `shutil.which` check — rejected: a
resolvable-but-broken git would pass and fail later, less cleanly.

## Decision 7 — Dependency + mypy cleanup

**Decision**: Remove `"gitpython>=3.1.40"` from `pyproject.toml` dependencies
(gitdb/smmap drop transitively) and delete the `[[tool.mypy.overrides]] module =
"git.*"` block; no replacement suppression. Amend constitution Technical
Constraints dependency list to drop GitPython with rationale, in the same change
set (FR-008). `gitops.py`'s type annotations reference `gitops.Repository`, so
mypy passes without the override.

**Rationale**: FR-008/FR-009; the override exists only because GitPython ships no
type stubs — once `import git` is gone, the override is dead config.

## Decision 8 — Verification strategy

**Decision**: Primary evidence is the Feature 018 golden-capture harness (before
capture on `main`/pre-change, after capture post-change; assert byte-identical
except the two sanctioned deltas) plus the subprocess smoke set over real repos
on the full CI matrix including the Windows leg. Add targeted unit tests per
`gitops` operation and per error-mapping row, plus fixtures for: unborn HEAD,
detached HEAD, rename-aware vs decomposed diff, blob absent at rev, non-UTF-8
path, and the git-availability precondition (init + doctor).

**Rationale**: byte-identity on the happy path is necessary but not sufficient
(FR-005 risk is on error paths); the per-row unit tests lock the taxonomy, and
the golden harness locks user-visible output. Coverage stays ≥85%.

## Open items deferred to /speckit-tasks

- Exact internal helper names (`_run_git`, `ensure_git_available`, `Repository`
  field/method names) — naming, not behavior.
- Whether module-level wrappers or methods host each operation (Decision 3 leans
  wrapper-retain; final split is a task-level detail with no behavior impact).
