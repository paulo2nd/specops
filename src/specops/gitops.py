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
    """Return True when *sha* is reachable from HEAD (i.e. an ancestor)."""
    if sha == "(human)":
        return True
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
