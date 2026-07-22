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


def test_commit_exists_true_for_head(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert gitops.commit_exists(repo, gitops.head_sha(repo))


def test_commit_exists_false_for_unknown_sha(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert not gitops.commit_exists(repo, "deadbeef" * 5)


def test_dirty_files_clean_tree_returns_empty(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert gitops.dirty_files(repo) == []


def test_dirty_files_lists_modified_file(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    (tmp_git_repo / "README.md").write_text("# changed\n")
    lines = gitops.dirty_files(repo)
    assert any("README.md" in line for line in lines)


def test_dirty_files_lists_untracked_file(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    (tmp_git_repo / "new.txt").write_text("x\n")
    lines = gitops.dirty_files(repo)
    assert any("new.txt" in line for line in lines)


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


# ---------------------------------------------------------------------------
# effective_diff (Feature 010, T002) — rename decomposition + mode-only
# ---------------------------------------------------------------------------


def _run(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(root: Path, msg: str) -> str:
    _run(root, "add", "-A")
    _run(root, "commit", "-m", msg)
    return _run(root, "rev-parse", "HEAD")


def test_effective_diff_decomposes_rename(tmp_git_repo: Path) -> None:
    (tmp_git_repo / "old_name.py").write_text("a = 1\nb = 2\nc = 3\n")
    base = _commit(tmp_git_repo, "add old")
    (tmp_git_repo / "old_name.py").rename(tmp_git_repo / "new_name.py")
    _commit(tmp_git_repo, "rename")
    diff = gitops.effective_diff(gitops.find_repo(tmp_git_repo), base)
    # No similarity-threshold rename detection: both old (removed) and new (added).
    assert diff == ["new_name.py", "old_name.py"]


def test_effective_diff_includes_mode_only_change(tmp_git_repo: Path) -> None:
    import os
    f = tmp_git_repo / "script.sh"
    f.write_text("#!/bin/sh\necho hi\n")
    os.chmod(f, 0o644)
    base = _commit(tmp_git_repo, "add script")
    os.chmod(f, 0o755)  # mode-only change, no content delta
    _commit(tmp_git_repo, "chmod")
    diff = gitops.effective_diff(gitops.find_repo(tmp_git_repo), base)
    assert "script.sh" in diff


def test_effective_diff_empty_when_no_change(tmp_git_repo: Path) -> None:
    head = _run(tmp_git_repo, "rev-parse", "HEAD")
    assert gitops.effective_diff(gitops.find_repo(tmp_git_repo), head) == []


def test_effective_diff_is_codepoint_sorted(tmp_git_repo: Path) -> None:
    base = _run(tmp_git_repo, "rev-parse", "HEAD")
    for name in ("zeta.py", "alpha.py", "mid.py"):
        (tmp_git_repo / name).write_text("x\n")
    _commit(tmp_git_repo, "three files")
    diff = gitops.effective_diff(gitops.find_repo(tmp_git_repo), base)
    assert diff == sorted(diff)
