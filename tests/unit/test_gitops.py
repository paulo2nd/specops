"""Unit tests for gitops.py."""
import subprocess
from pathlib import Path

from specops import gitops


def test_is_git_repo_true(tmp_git_repo: Path) -> None:
    assert gitops.is_git_repo(tmp_git_repo)


def test_is_git_repo_false(tmp_path: Path) -> None:
    assert not gitops.is_git_repo(tmp_path)


def test_find_repo_returns_none_outside_repo(tmp_path: Path) -> None:
    assert gitops.find_repo(tmp_path) is None


def test_head_sha_returns_full_hex(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    sha = gitops.head_sha(repo)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


def test_commits_in_range_empty_when_no_new_commits(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    start = gitops.head_sha(repo)
    commits = gitops.commits_in_range(repo, start)
    assert commits == []


def test_commits_in_range_captures_new_commit(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    start = gitops.head_sha(repo)

    # add a new commit
    (tmp_git_repo / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "file.txt"], cwd=tmp_git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=tmp_git_repo, check=True, capture_output=True,
    )

    commits = gitops.commits_in_range(repo, start)
    assert len(commits) == 1


def test_commits_in_range_bad_sha_returns_empty(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    result = gitops.commits_in_range(repo, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
    assert result == []


def test_is_ancestor_head_is_own_ancestor(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    sha = gitops.head_sha(repo)
    assert gitops.is_ancestor(repo, sha)


def test_is_ancestor_fake_sha_returns_false(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert not gitops.is_ancestor(repo, "deadbeef" * 5)


def test_is_ancestor_human_marker_exempt(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert gitops.is_ancestor(repo, "(human)")


def test_name_only_diff_empty_range(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    sha = gitops.head_sha(repo)
    assert gitops.name_only_diff(repo, sha) == []


def test_name_only_diff_captures_changed_file(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    start = gitops.head_sha(repo)

    (tmp_git_repo / "changed.py").write_text("x = 1")
    subprocess.run(["git", "add", "changed.py"], cwd=tmp_git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add changed"],
        cwd=tmp_git_repo, check=True, capture_output=True,
    )

    diff = gitops.name_only_diff(repo, start)
    assert "changed.py" in diff
