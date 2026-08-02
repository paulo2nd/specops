"""Unit tests for reviewed-scope derivation and union coverage (Feature 025).

Covers FR-001/FR-002 (git-derived anchor/corrective ranges), FR-003 (union
coverage vs baseline..HEAD), FR-008 (degradation switch), and R7 (rebase
tolerance: an unresolvable endpoint is dropped, never an error).
"""
from __future__ import annotations

from pathlib import Path

from specops import gitops, reviewscope
from tests.conftest import git

# ---------------------------------------------------------------------------
# derive_range / has_any_scope — pure (no git)
# ---------------------------------------------------------------------------


def test_derive_anchor_when_no_prior_scope() -> None:
    dr = reviewscope.derive_range("BASE", "HEAD", [{"round": 1}])
    assert dr.review_role == reviewscope.ANCHOR
    assert (dr.from_commit, dr.to_commit) == ("BASE", "HEAD")
    assert dr.range_str == "BASE..HEAD"


def test_derive_corrective_from_prior_to() -> None:
    cycles = [{"round": 1, "reviewed_range": "BASE..H1", "review_role": "anchor"}, {"round": 2}]
    dr = reviewscope.derive_range("BASE", "H2", cycles)
    assert dr.review_role == reviewscope.CORRECTIVE
    assert (dr.from_commit, dr.to_commit) == ("H1", "H2")


def test_derive_idempotent_excludes_current_own_range() -> None:
    # Re-running on a round that already carries a range derives from EARLIER cycles,
    # never from its own prior record (idempotent to the current HEAD).
    cycles = [
        {"round": 1, "reviewed_range": "BASE..H1"},
        {"round": 2, "reviewed_range": "H1..H2OLD"},
    ]
    dr = reviewscope.derive_range("BASE", "H2NEW", cycles)
    assert dr.review_role == reviewscope.CORRECTIVE
    assert dr.from_commit == "H1"       # earlier cycle's `to`, not its own
    assert dr.to_commit == "H2NEW"


def test_derive_anchor_idempotent_when_only_current_has_range() -> None:
    dr = reviewscope.derive_range("BASE", "H1NEW", [{"round": 1, "reviewed_range": "BASE..H1OLD"}])
    assert dr.review_role == reviewscope.ANCHOR
    assert dr.from_commit == "BASE"


def test_has_any_scope() -> None:
    assert not reviewscope.has_any_scope([{"round": 1}])
    assert reviewscope.has_any_scope([{"round": 1, "reviewed_range": "a..b"}])
    # Malformed ranges are not "scope records".
    assert not reviewscope.has_any_scope([{"round": 1, "reviewed_range": "malformed"}])
    assert not reviewscope.has_any_scope([{"round": 1, "reviewed_range": "a.."}])


# ---------------------------------------------------------------------------
# coverage — real git
# ---------------------------------------------------------------------------


def _commit(root: Path, path: str, content: str) -> str:
    (root / path).write_text(content)
    git(root, "add", "-A")
    git(root, "commit", "-m", f"edit {path}")
    return git(root, "rev-parse", "HEAD")


def _linear_repo(root: Path) -> tuple[str, str, str]:
    base = _commit(root, "a.py", "1")
    h1 = _commit(root, "a.py", "2")
    h2 = _commit(root, "b.py", "1")
    return base, h1, h2


def test_assess_anchor_reaching_head_is_complete(tmp_git_repo: Path) -> None:
    base, _h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{h2}"}])
    assert a.has_scope_records and a.has_anchor and a.frontier_resolves
    assert not a.target_empty and a.unreviewed_tail == []


def test_assess_unreviewed_tail_after_frontier(tmp_git_repo: Path) -> None:
    # [5]: a commit lands (b.py) after the frontier (anchor stopped at h1) — the tail
    # catches the unreviewed change even though b.py is a "new" path, and would catch a
    # re-touch of an already-reviewed file too.
    base, h1, _h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{h1}"}])
    assert a.has_anchor and a.frontier_resolves
    assert a.unreviewed_tail == ["b.py"]


def test_assess_pruned_intermediate_endpoint_does_not_block(tmp_git_repo: Path) -> None:
    # [2]: an earlier round's (non-frontier) endpoint is unresolvable, but the frontier
    # reaches HEAD — the middle range is never re-diffed, so no false block.
    base, _h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(
        repo, base, "HEAD",
        [{"reviewed_range": f"{base}..{'0' * 40}"}, {"reviewed_range": f"{base}..{h2}"}],
    )
    assert a.has_anchor and a.frontier_resolves and a.unreviewed_tail == []


def test_assess_no_anchor_when_no_range_starts_at_baseline(tmp_git_repo: Path) -> None:
    base, h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{h1}..{h2}"}])
    assert a.has_scope_records and not a.has_anchor


def test_assess_frontier_unresolvable(tmp_git_repo: Path) -> None:
    base, _h1, _h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{'0' * 40}"}])
    assert a.has_scope_records and a.has_anchor and not a.frontier_resolves


def test_assess_target_empty_when_baseline_is_head(tmp_git_repo: Path) -> None:
    _base, _h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, h2, "HEAD", [{"reviewed_range": f"{h2}..{h2}"}])
    assert a.target_empty


def test_assess_no_scope_records(tmp_git_repo: Path) -> None:
    base, _h1, _h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"round": 1}])
    assert not a.has_scope_records
