"""Unit tests for gitops.py."""
import subprocess
import sys
from pathlib import Path

import pytest

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


# The "(human)" exemption moved OUT of the git layer to its ledger-owning
# callers (Feature 019 US4, FR-009) — the git-layer and command-level contracts
# are now pinned by tests/unit/test_human_commit.py.


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


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX file modes are invisible to git on Windows"
)
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


# ---------------------------------------------------------------------------
# Feature 019 US4 (FR-008): the single --name-status parser, rename-awareness
# as a parameter.
# ---------------------------------------------------------------------------


def test_parse_name_status_plain_and_blank_lines() -> None:
    raw = "M\tsrc/a.py\nA\tsrc/b.py\n\n   \n"
    assert gitops.parse_name_status(raw) == [("M", "src/a.py"), ("A", "src/b.py")]


def test_parse_name_status_rename_line_reports_new_path() -> None:
    assert gitops.parse_name_status("R100\told.py\tnew.py") == [("R", "new.py")]


def _rename_repo(tmp_git_repo):
    """A repo whose HEAD renames tracked.py -> moved.py relative to the baseline."""
    from tests.conftest import git

    root = tmp_git_repo
    (root / "tracked.py").write_text("x = 1\n")
    git(root, "add", "-A")
    git(root, "commit", "-m", "add tracked")
    baseline = git(root, "rev-parse", "HEAD")
    git(root, "mv", "tracked.py", "moved.py")
    git(root, "commit", "-m", "rename")
    return root, baseline


def test_name_status_diff_rename_aware_single_r(tmp_git_repo) -> None:
    root, baseline = _rename_repo(tmp_git_repo)
    repo = gitops.find_repo(root)
    pairs = gitops.name_status_diff(repo, baseline, "HEAD", rename_aware=True)
    assert pairs == [("R", "moved.py")]


def test_name_status_diff_no_renames_decomposes(tmp_git_repo) -> None:
    root, baseline = _rename_repo(tmp_git_repo)
    repo = gitops.find_repo(root)
    pairs = gitops.name_status_diff(repo, baseline, "HEAD", rename_aware=False)
    assert set(pairs) == {("D", "tracked.py"), ("A", "moved.py")}
    # effective_diff_status stays the thin rename-decomposed projection.
    assert set(gitops.effective_diff_status(repo, baseline, "HEAD")) == set(pairs)


def test_name_status_diff_cached_reads_the_index(tmp_git_repo) -> None:
    from tests.conftest import git

    root = tmp_git_repo
    (root / "staged.txt").write_text("s\n")
    git(root, "add", "staged.txt")
    repo = gitops.find_repo(root)
    pairs = gitops.name_status_diff(repo, None, rename_aware=True, cached=True)
    assert ("A", "staged.txt") in pairs


# ---------------------------------------------------------------------------
# Feature 020: plumbing engine — Repository, error mapping, new operations
# ---------------------------------------------------------------------------


def test_repository_working_tree_dir_set_for_normal_repo(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert repo is not None
    assert repo.working_tree_dir is not None
    assert repo.root == repo.working_tree_dir


def test_find_repo_from_subdirectory_resolves_root(tmp_git_repo: Path) -> None:
    sub = tmp_git_repo / "a" / "b"
    sub.mkdir(parents=True)
    repo = gitops.find_repo(sub)
    assert repo is not None
    # search_parent_directories parity: resolves to the worktree root.
    assert repo.working_tree_dir == gitops.find_repo(tmp_git_repo).working_tree_dir


def test_find_repo_in_worktreeless_gitdir_has_no_working_tree(tmp_git_repo: Path) -> None:
    # cwd inside `.git` is a worktree-less GIT_DIR context: `--show-toplevel`
    # fails there. find_repo must return working_tree_dir=None (GitPython parity)
    # so the bare/worktree guard fires — never Repository(root='.') running the
    # command against the git directory (code-review finding).
    repo = gitops.find_repo(tmp_git_repo / ".git")
    assert repo is not None
    assert repo.working_tree_dir is None
    assert repo.root != Path(".")


def test_find_repo_bare_repo_has_no_working_tree(tmp_path: Path) -> None:
    from tests.conftest import git

    bare = tmp_path / "bare.git"
    git(tmp_path, "init", "--bare", str(bare))
    repo = gitops.find_repo(bare)
    assert repo is not None
    assert repo.working_tree_dir is None


def test_current_branch_returns_branch_name(tmp_git_repo: Path) -> None:
    from tests.conftest import git

    git(tmp_git_repo, "checkout", "-b", "feature-x")
    repo = gitops.find_repo(tmp_git_repo)
    assert gitops.current_branch(repo) == "feature-x"


def test_current_branch_detached_head_returns_short_sha(tmp_git_repo: Path) -> None:
    from tests.conftest import git

    repo = gitops.find_repo(tmp_git_repo)
    full = gitops.head_sha(repo)
    git(tmp_git_repo, "checkout", full)  # detach
    branch = gitops.current_branch(repo)
    assert branch == full[:7]
    assert len(branch) == 7


def test_merge_base_returns_common_ancestor(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    head = gitops.head_sha(repo)
    assert gitops.merge_base(repo, head, "HEAD") == head


def test_merge_base_absent_ref_returns_none(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert gitops.merge_base(repo, "no-such-ref", "HEAD") is None


def test_symbolic_ref_unresolvable_returns_none(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    # origin/HEAD is not advertised in a fresh local repo.
    assert gitops.symbolic_ref(repo, "refs/remotes/origin/HEAD") is None


def test_blob_sha_present_and_absent(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    sha = gitops.blob_sha(repo, "HEAD", "README.md")
    assert sha and len(sha) == 40
    assert gitops.blob_sha(repo, "HEAD", "does-not-exist.txt") is None
    assert gitops.blob_sha(repo, "deadbeef" * 5, "README.md") is None


def test_ls_files_lists_tracked(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert "README.md" in gitops.ls_files(repo)


def test_is_tracked_true_and_false(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert gitops.is_tracked(repo, "README.md")
    assert not gitops.is_tracked(repo, "untracked.txt")


def test_porcelain_status_untracked_all_lists_nested_untracked(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    nested = tmp_git_repo / "pkg" / "mod.py"
    nested.parent.mkdir()
    nested.write_text("x\n")
    lines = gitops.porcelain_status(repo, untracked_all=True)
    assert any("pkg/mod.py" in line for line in lines)


def test_name_status_diff_raises_giterror_on_bad_range(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    with pytest.raises(gitops.GitError):
        gitops.name_status_diff(repo, "nonexistent-ref", "HEAD", rename_aware=True)


def test_effective_diff_status_degrades_to_empty_on_bad_range(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert gitops.effective_diff_status(repo, "nonexistent-ref") == []


def test_ensure_git_available_returns_version() -> None:
    version = gitops.ensure_git_available()
    assert "git" in version.lower()


def test_ensure_git_available_raises_when_binary_missing(monkeypatch) -> None:
    def _boom(*_a, **_k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitops.subprocess, "run", _boom)
    with pytest.raises(gitops.GitError):
        gitops.ensure_git_available()


def test_run_git_missing_binary_raises_giterror(monkeypatch, tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)

    def _boom(*_a, **_k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitops.subprocess, "run", _boom)
    with pytest.raises(gitops.GitError):
        gitops.head_sha(repo)


# ---------------------------------------------------------------------------
# Feature 020 US1/T029: encoding fidelity — non-ASCII paths stay C-quoted,
# matching the previous GitPython behavior byte-for-byte.
# ---------------------------------------------------------------------------


def test_non_ascii_path_is_c_quoted_like_gitpython(tmp_git_repo: Path) -> None:
    from tests.conftest import git

    (tmp_git_repo / "café.txt").write_text("x\n", encoding="utf-8")
    git(tmp_git_repo, "add", "-A")
    repo = gitops.find_repo(tmp_git_repo)
    # git's default quotePath C-quotes the non-ASCII bytes; GitPython returned the
    # same form (verified empirically), so byte-identity requires it here too.
    assert any("caf" in line and "\\303\\251" in line for line in gitops.ls_files(repo))
    assert any("\\303\\251" in line for line in gitops.dirty_files(repo)) or \
        any("caf" in line for line in gitops.porcelain_status(repo))


# ---------------------------------------------------------------------------
# Feature 020 US4/FR-011 guard: the generic git layer carries no ledger sentinel.
# ---------------------------------------------------------------------------


def test_gitops_has_no_human_sentinel_specialcase(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    # "(human)" is a ledger convention; the git layer must treat it as an
    # ordinary (unresolvable) ref, never exempt it (FR-011 / Feature 019 US4).
    assert not gitops.commit_exists(repo, "(human)")
    assert not gitops.is_ancestor(repo, "(human)")
    # No code path branches on the ledger sentinel — a real commit and the
    # sentinel are resolved by the same generic plumbing (no special-case).
    assert gitops.commit_exists(repo, gitops.head_sha(repo))
