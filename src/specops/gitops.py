"""Git helpers using GitPython (R7)."""
from __future__ import annotations

from pathlib import Path

import git
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError


def find_repo(path: Path = Path(".")) -> git.Repo | None:
    """Return the Repo for *path*, or None if not inside a Git repository."""
    try:
        return git.Repo(path, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return None


def is_git_repo(path: Path = Path(".")) -> bool:
    return find_repo(path) is not None


def current_branch(repo: git.Repo) -> str:
    try:
        return repo.active_branch.name
    except TypeError:
        return repo.head.commit.hexsha[:7]


def head_sha(repo: git.Repo) -> str:
    return repo.head.commit.hexsha


def commits_in_range(repo: git.Repo, start_sha: str, end_sha: str = "HEAD") -> list[str]:
    """Return commit shas in *start_sha..end_sha* (exclusive start, inclusive end)."""
    try:
        repo.commit(start_sha)
    except (GitCommandError, git.BadName, ValueError):
        return []
    commits = list(repo.iter_commits(rev=f"{start_sha}..{end_sha}"))
    return [c.hexsha for c in commits]


def is_ancestor(repo: git.Repo, sha: str) -> bool:
    """Return True when *sha* is reachable from HEAD (i.e. an ancestor).

    A pure git ancestry predicate: ledger-domain sentinels (the human-work
    commit marker) are filtered by callers via ``ledger.is_human_commit`` —
    this generic layer knows nothing about them (Feature 019 US4, FR-009).
    """
    try:
        repo.commit(sha)
        # merge_base returns list; non-empty means sha is ancestor of HEAD
        base = repo.merge_base(sha, repo.head.commit)
        if not base:
            return False
        return base[0].hexsha == repo.commit(sha).hexsha
    except (GitCommandError, git.BadName, ValueError):
        return False


def commit_exists(repo: git.Repo, sha: str) -> bool:
    """Return True when *sha* resolves to a commit in this clone."""
    try:
        repo.commit(sha)
        return True
    except (GitCommandError, git.BadName, ValueError):
        return False


def blob_sha(repo: git.Repo, rev: str, path: str) -> str | None:
    """Return the git blob SHA of *path* at *rev*, or None when it does not resolve.

    A deterministic, offline, per-path content digest (git's own object hash): two
    revisions with byte-identical content at *path* share a blob SHA, so a change to
    any other path leaves it unchanged (Feature 015 per-path staleness). Returns
    None when *rev* is unresolvable or *path* is absent (a removed/renamed path),
    which the caller treats as stale.
    """
    try:
        tree = repo.commit(rev).tree
    except (GitCommandError, git.BadName, ValueError):
        return None
    try:
        return tree[path].hexsha
    except KeyError:
        return None


def dirty_files(repo: git.Repo) -> list[str]:
    """Return `git status --porcelain` lines; empty list means a clean tree."""
    out = repo.git.status("--porcelain")
    return [line for line in out.splitlines() if line.strip()]


def name_only_diff(repo: git.Repo, start_sha: str, end_sha: str = "HEAD") -> list[str]:
    """Return deduplicated list of changed file paths between *start_sha* and *end_sha*."""
    try:
        diffs = repo.git.diff("--name-only", start_sha, end_sha)
        return [f for f in diffs.splitlines() if f]
    except GitCommandError:
        return []


def parse_name_status(raw: str) -> list[tuple[str, str]]:
    """Parse ``git diff --name-status`` output into ``(status, path)`` pairs.

    The single parse loop (Feature 019 US4, FR-008): ``status`` is the first
    letter of the code (``R100`` → ``R``), ``path`` the last tab field — the NEW
    path for a rename line. Blank lines are skipped.
    """
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        out.append((parts[0][:1], parts[-1]))
    return out


def name_status_diff(
    repo: git.Repo, start_sha: str | None, end_sha: str = "HEAD", *,
    rename_aware: bool, cached: bool = False,
) -> list[tuple[str, str]]:
    """The single ``--name-status`` invocation, rename-awareness as a parameter
    (Feature 019 US4, FR-008).

    ``rename_aware=False`` → ``--no-renames``: a rename **decomposes** into a
    removed old path plus an added new path (no similarity threshold).
    ``rename_aware=True`` → ``-M``: a rename is a single ``R`` on the NEW path
    (an ordinary file move is not mis-flagged destructive — lane safety).
    ``cached=True`` diffs the index (staged changes; the commit range is
    ignored). Raises ``GitCommandError`` — each caller owns its degradation
    policy (``effective_diff_status`` returns ``[]``; lane suppresses).
    """
    flag = "-M" if rename_aware else "--no-renames"
    if cached:
        raw = repo.git.diff("--cached", "--name-status", flag)
    else:
        raw = repo.git.diff("--name-status", flag, start_sha, end_sha)
    return parse_name_status(raw)


def effective_diff_status(
    repo: git.Repo, start_sha: str, end_sha: str = "HEAD"
) -> list[tuple[str, str]]:
    """Return `(status, path)` pairs between *start_sha* and *end_sha* (Feature 010, R1).

    The rename-decomposed projection of :func:`name_status_diff` (same name,
    signature, and ``[]``-on-error semantics as always). Mode-only changes are
    still listed; symlinks appear by their own path entry and are not followed
    (``git diff`` never dereferences them). ``status`` is Git's single-letter
    code (``A``/``M``/``D``/…).
    """
    try:
        return name_status_diff(repo, start_sha, end_sha, rename_aware=False)
    except GitCommandError:
        return []


def effective_diff(repo: git.Repo, start_sha: str, end_sha: str = "HEAD") -> list[str]:
    """Return the deterministic, codepoint-sorted effective-diff paths (name-only).

    A thin projection of :func:`effective_diff_status` so the diff invocation lives
    in exactly one place.
    """
    return sorted({p for _status, p in effective_diff_status(repo, start_sha, end_sha)})
