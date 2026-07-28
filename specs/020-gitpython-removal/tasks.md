# Tasks: GitPython Removal

**Input**: Design documents from `/specs/020-gitpython-removal/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included per the Constitution task gate — every task closes only with passing automated tests. The Feature 018 golden-capture harness (`tests/golden/`) is reused as this feature's behavior-freeze instrument: SC-002 demands **zero** capture diffs except the two sanctioned additive deltas (doctor git-availability finding; init git-absent diagnostic).

**Organization**: Tasks are grouped by user story. **Build order is dependency-driven, not priority-numeric**: the seam consolidation + plumbing engine (US2) is the enabler that must land before the dependency can be removed (US1), and the failure-behavior work (US3) sits between them. The delivered order is therefore **US2 → US3 → US1 → US4**, which the Dependencies section justifies. This is a cohesive refactor of a single seam (`gitops.py`) consumed by many modules, so cross-story parallelism is limited; `[P]` marks genuinely independent files. Run all commands via `conda run -n specops …`.

## Format: `[ID] [P?] [Story] Description (FR/SC-xxx)`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US4 (maps to spec.md user stories)
- **(FR/SC-xxx)**: requirement / success criterion the task serves
- Exact file paths are included in each description

## Path Conventions

Single project: `src/specops/`, `tests/` at repository root (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: branch bookkeeping, roadmap registration, baseline measurements

- [X] T001 Commit the `specs/020-gitpython-removal/` artifacts and the updated `.specify/feature.json` on branch `020-gitpython-removal` (done: commit `6ca7b68`)
- [X] T002 Flip the Feature 020 row `PLANNED → ACTIVE` in `ROADMAP.md` (feature overview table, line ~91) in this feature's first planning commit (done: commit `6ca7b68`)
- [X] T003 Record baselines in the PR description (SC-001/SC-003/SC-004): `pip show gitpython gitdb smmap` all present; `grep -rn "^import git\b\|^from git" src/specops/` → 4 modules (gitops, review, cli, status); `grep -rc "git\.Repo" src/specops/*.py` → 27 refs across 7 files; `grep -rn "gitops\.git\.GitCommandError" src/specops/` → 5 sites (trace ×2, consistency ×1, lane ×2)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: prove the behavior-freeze instrument is green and capture the "before" side before any code changes

**⚠️ CRITICAL**: no replacement task starts before T004–T005 pass

- [X] T004 Run the full gate on the untouched tree and confirm green: `conda run -n specops ruff check src tests && conda run -n specops mypy src && conda run -n specops python -m pytest`; any pre-existing failure blocks the feature and must be triaged first (SC-002 baseline)
- [X] T005 Capture the "before" golden baseline for every git-dependent command via the Feature 018 harness (`tests/golden/`), on the pre-change tree, so the post-change replay can assert byte-identity (SC-002)

**Checkpoint**: baseline green and captured — the replacement may begin

---

## Phase 3: User Story 2 — All git access flows through one owned seam (Priority: P2) 🎯 MVP-enabler

**Goal**: `gitops` becomes the single git access layer over `git` plumbing; a `Repository` abstraction + `GitError` replace `git.Repo`/`git.exc.*` everywhere; no production module imports a git library or references `gitops.git.*`.

**Independent Test**: `grep -rn "^import git\b\|^from git\|git\.Repo\|gitops\.git\b" src/specops/ | grep -v gitops.py` returns nothing; the abstraction covers every operation in `contracts/repository-abstraction.md`; full suite green.

### Engine (gitops.py)

- [X] T006 [US2] Add the argv git-invocation runner `_run_git(...)` and `GitError(SpecopsError)` in `src/specops/gitops.py` per `contracts/git-invocation.md`: `subprocess.run` (no shell), `cwd=root`, decode `errors="surrogateescape"`, `-c core.quotePath=false` on diff/status/ls-files; non-zero exits handled per the exit-code→outcome map (FR-002, FR-005, FR-007)
- [X] T007 [US2] Add the `Repository` class (holds `root: Path`) and reimplement `find_repo` (`git -C <path> rev-parse --show-toplevel` → `Repository`, else `None`) and `is_git_repo` in `src/specops/gitops.py`; changes the `repo` type across the module surface (FR-002, FR-003)
- [X] T008 [P] [US2] Unit tests in `tests/unit/test_gitops.py` for `_run_git`, `GitError`, `find_repo`/`is_git_repo` (inside repo, subdir, not-a-repo → `None`) (FR-002, FR-005)
- [X] T009 [US2] Reimplement the resolution/ancestry operations over plumbing in `src/specops/gitops.py` per the `research.md` Decision 2 mapping: `current_branch` (symbolic-ref, detached → `rev-parse HEAD`[:7]), `head_sha`, `commit_exists`, `commits_in_range` (rev-list), `is_ancestor` (`merge-base --is-ancestor`), new `merge_base(a,b)->str|None`, new `symbolic_ref(name)->str|None`, `blob_sha` (`rev-parse -q --verify rev:path`) (FR-003, FR-006)
- [X] T010 [P] [US2] Unit tests in `tests/unit/test_gitops.py` covering each op in T009 including unborn HEAD, detached HEAD, unknown commit/ref/path → `[]`/`False`/`None`, and merge_base/symbolic_ref happy + absent paths (FR-005, FR-006)
- [X] T011 [US2] Reimplement porcelain/diff/tracked-file ops over plumbing in `src/specops/gitops.py`: `dirty_files`, new `porcelain_status(*, untracked_all=False)` (the lane `-uall` variant), new `ls_files`, `name_only_diff`, `name_status_diff` (raises `GitError`); keep `parse_name_status`, `effective_diff_status`, `effective_diff` verbatim; **remove `import git`** from `gitops.py` (FR-003, FR-008, FR-011)
- [X] T012 [P] [US2] Unit tests in `tests/unit/test_gitops.py` for diff/status/ls-files ops: rename-aware (`-M`) vs decomposed (`--no-renames`), `--cached`, clean tree → `[]`, `name_status_diff` raising `GitError` on git failure (FR-003, FR-008)

### Consumer migration (one commitable group; different files → [P])

- [X] T013 [P] [US2] Migrate `src/specops/review.py`: drop `import git`; type `git.Repo → gitops.Repository` (`profile_gates`, `_working_tree_gate`, `evaluate`); porcelain access via `gitops` (FR-002)
- [X] T014 [P] [US2] Migrate `src/specops/status.py`: drop `import git`; type `git.Repo → gitops.Repository` in all 5 signatures (FR-002)
- [X] T015 [P] [US2] Migrate `src/specops/cli.py`: drop `import git`; `_require_git -> gitops.Repository`; replace `repo.git.ls_files()` (line ~732) with `gitops.ls_files(repo)` (FR-002)
- [X] T016 [P] [US2] Migrate `src/specops/trace.py`: retype the 2 `git.Repo`/`gitops.git.Repo` signature hints to `gitops.Repository`; replace `repo.git.symbolic_ref(...)`/`repo.merge_base(...)`/`repo.head.commit` with `gitops.symbolic_ref`/`gitops.merge_base`/`gitops.head_sha`; replace both `gitops.git.GitCommandError` catches (and the paired `ValueError`) with `gitops.GitError`, preserving the origin/HEAD → main/master baseline fallback (FR-002, FR-005)
- [X] T017 [P] [US2] Migrate `src/specops/consistency.py`: replace the `gitops.git.GitCommandError` catch with `gitops.GitError`, same degradation (FR-002, FR-005)
- [X] T018 [P] [US2] Migrate `src/specops/lane.py`: replace `repo.git.status("--porcelain","-uall")` with `gitops.porcelain_status(repo, untracked_all=True)`; keep the shared `gitops.name_status_diff`; replace both `gitops.git.GitCommandError` suppressions with `gitops.GitError` (FR-002, FR-008)
- [X] T019 [P] [US2] Migrate any residual `git.Repo` type references in `src/specops/reconcile.py` and `src/specops/ledger.py` to `gitops.Repository` (verify via `grep -rc "git\.Repo" src/specops`) (FR-002)
- [X] T020 [US2] Close the story: `grep -rn "^import git\b\|^from git\|git\.Repo\|gitops\.git\b" src/specops/ | grep -v gitops.py` returns zero (SC-003); full suite green

**Checkpoint**: the seam is single-sourced over plumbing; GitPython is still installed but no longer referenced

---

## Phase 4: User Story 3 — Failure diagnostics and exit codes are preserved (Priority: P3)

**Goal**: every failure mode yields today's diagnostic/exit code, and the git-availability precondition fails closed (init first-step + doctor `blocking` finding).

**Independent Test**: error-mode fixtures produce identical diagnostics/exit codes old vs new; with no `git` on PATH, `init` exits 1 with a clean diagnostic (no traceback) and `doctor` reports `git-availability` as `blocking`.

- [X] T021 [US3] Add `ensure_git_available()` in `src/specops/gitops.py` per `contracts/git-invocation.md`: probe `git --version`; `FileNotFoundError`/non-zero → clear diagnostic via `GitError`/`SpecopsError` (exit 1); returns the version string on success (FR-012)
- [X] T022 [US3] Wire the init first-step in `src/specops/initializer.py` `run()` (and/or `cli.py init`): call `ensure_git_available()` **before** the `gitops.is_git_repo` check and the `git init` offer, so a missing git fails closed cleanly instead of the current uncaught `git init` subprocess crash (FR-013)
- [X] T023 [US3] Add the git-availability finding to `src/specops/doctor.py` `_domain_environment`, ordered **before** the `repo is None` check: `blocking` (fid `git-availability`, clear message + next action) when absent/nonfunctional, `ok` with the detected version shown informationally when present (FR-012)
- [X] T024 [P] [US3] Error-parity tests in `tests/unit/test_gitops.py` / `tests/integration/`: not-a-repo (`_require_git` diagnostic, exit 1), unknown commit/rev/absent path, unborn/detached HEAD, rename vs decomposed diff — assert identical diagnostics/exit codes/degradations vs the pre-change contract (SC-004, FR-005)
- [X] T025 [P] [US3] Precondition tests in `tests/integration/`: with `PATH` lacking `git`, `specops init --non-interactive` exits 1 with a clean diagnostic (no traceback), and `specops doctor --json` reports `git-availability` as `blocking`; with git present, `ok` + version (SC-008, FR-012, FR-013)
- [X] T026 [US3] Close the story: error-parity + precondition suites green; full suite green

**Checkpoint**: failure behavior is provably identical; the git precondition is single-sourced and fail-closed

---

## Phase 5: User Story 1 — Installing SpecOps pulls no GitPython dependency tree (Priority: P1) 🎯 headline deliverable

**Goal**: remove the runtime dependency and prove byte-identical behavior across the golden harness and CI platforms.

**Independent Test**: installed tree has no gitpython/gitdb/smmap; golden replay shows zero diffs except the two sanctioned deltas; encoding/Windows fixtures byte-identical.

- [X] T027 [US1] Remove `"gitpython>=3.1.40"` from the `dependencies` array in `pyproject.toml` (gitdb/smmap drop transitively); no new runtime dependency added (FR-001)
- [X] T028 [P] [US1] Footprint test in `tests/unit/`: assert `gitpython`/`gitdb`/`smmap` are not importable / not in the resolved dependency set, and `import specops.gitops` imports with only `subprocess` (SC-001, FR-001)
- [X] T029 [P] [US1] Encoding/path-fidelity fixtures in `tests/`: a repo with a non-UTF-8 / non-ASCII filename; assert `status`/`diff`/`ls-files` output byte-identical to the GitPython capture (also exercised on the Windows CI leg) (SC-007, FR-007)
- [X] T030 [US1] Run the post-change golden replay (`tests/golden/`) and assert zero diffs except the two sanctioned additive deltas (doctor git-availability finding; init git-absent diagnostic) (SC-002, FR-004, FR-010)
- [X] T031 [US1] Close the story: footprint + encoding + golden replay green

**Checkpoint**: GitPython is gone from the footprint and behavior is byte-identical

---

## Phase 6: User Story 4 — Dependency contract and type-checker debt retired (Priority: P4)

**Goal**: governing documents and type-checker config match the new footprint, atomically with the code.

**Independent Test**: constitution dependency list omits GitPython (with rationale); no `git.*` mypy override or replacement suppression; mypy green.

- [X] T032 [US4] Remove the `[[tool.mypy.overrides]] module = "git.*"` block from `pyproject.toml` (lines ~80–82); add no replacement suppression (FR-009)
- [X] T033 [US4] Confirm `conda run -n specops mypy src` passes with git-related annotations naming `gitops.Repository`, no new `# type: ignore` (SC-005, FR-009)
- [X] T034 [US4] Amend `.specify/memory/constitution.md` Technical Constraints dependency list: remove GitPython, record the rationale (library in maintenance mode; git access behind the owned seam over plumbing); bump the constitution version (PATCH) and add a Sync Impact Report entry — same change set as the code (FR-008, SC-006)
- [X] T035 [US4] Close the story: `grep -i gitpython .specify/memory/constitution.md` shows GitPython absent from the dependency enumeration; mypy green

**Checkpoint**: contracts and config match reality; the amendment ships with the code

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: documentation, changelog, and the final full-matrix gate

- [X] T036 [P] Record in `CHANGELOG.md` under `[Unreleased]` (Feature 020): removed the gitpython/gitdb/smmap runtime dependencies; added the `specops doctor` git-availability check and the `specops init` fail-closed diagnostic when git is absent; no other user-visible change
- [X] T037 [P] Update EN/PT docs behaviorally-equivalently: `docs/commands.md` (doctor git-availability finding; git-on-PATH precondition) and `README.pt-br.md` where the dependency/requirements are described (roadmap DoD: EN/PT equivalence)
- [X] T038 Run the complete gate on all CI legs (Ubuntu 3.10/3.12/3.14 + Windows 3.12): `ruff check`, `mypy src`, `pytest` with coverage ≥85%, golden replay, subprocess smoke set (SC-007)
- [X] T039 Execute every `quickstart.md` scenario (1–8) and confirm the expected outcomes
- [X] T040 [P] Guard tests in `tests/`: (a) FR-011 — assert the generic git layer applies no `(human)` sentinel special-case (an ancestry/commit query over a `(human)` value is not exempted inside `gitops`; exemption stays with callers); (b) FR-010 — assert the CLI command/option surface is unchanged (e.g. snapshot `--help` command+option names against the pre-change set, since a *new option* would not be caught by golden output replay) (FR-010, FR-011)

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** must complete before any code change.
- **US2 (Phase 3)** is the enabler and comes first in build order despite being P2: the dependency cannot be removed (US1) while any module still imports `git`, and error parity (US3) is a facet of the plumbing reimplementation. Within US2: T006–T007 (runner/abstraction) block everything; T009/T011 (ops) block the consumer migrations T013–T019; T020 (scan=0) closes it.
- **US3 (Phase 4)** depends on US2 (needs `gitops.GitError` and the plumbing ops). T021 blocks T022/T023.
- **US1 (Phase 5)** depends on US2 **and** US3 (no module may import git before the dep is removed; parity must hold). T027 blocks T030.
- **US4 (Phase 6)** depends on US1 (remove the override/dep contract only once `import git` is gone). 
- **Polish (Phase 7)** last.

### Parallel opportunities

- **Tests alongside impl**: T008/T010/T012 ([P]) are new test files parallel to their gitops impl tasks.
- **Consumer migration**: T013–T019 ([P]) touch different files and can proceed together once T006–T011 land.
- **US1 verification**: T028/T029 ([P]) are independent test files.
- **Polish**: T036/T037 ([P]) are independent docs.
- Cross-story parallelism is otherwise NOT recommended — US2/US3/US1 all edit `gitops.py`.

## Implementation Strategy

- **Commit granularity**: one commit per user story (per the repo convention) — US2, US3, US1, US4 each land as one logical commit, plus a Polish commit. US4's constitution amendment and the `pyproject.toml` dep removal (US1) must be in the change set that removes `import git`, never split across PRs.
- **MVP note**: unlike a typical feature, there is no partial MVP — the value (US1: no GitPython) is only realized once US2+US3 make the seam plumbing-based. US2 is the enabling increment; US1 is the headline that closes it.
- **Behavior freeze**: the golden harness (T005 before / T030 after) is the authority; every story checkpoint re-runs the full suite.
