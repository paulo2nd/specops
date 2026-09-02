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
    (root / path).parent.mkdir(parents=True, exist_ok=True)
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
    assert a.has_scope_records and not a.target_empty
    assert a.never_reached == [] and a.has_anchor and a.frontier_resolves
    assert a.unreviewed_tail == []


def test_assess_change_after_the_last_round_is_uncovered(tmp_git_repo: Path) -> None:
    # [5]: a commit lands (b.py) after the anchor stopped at h1. Feature 025 caught
    # this as `unreviewed_tail`; it is now the same block, per path and by name.
    base, h1, _h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{h1}"}])
    assert a.never_reached == ["b.py"] and a.unreviewed_tail == ["b.py"]


def test_assess_pruned_intermediate_endpoint_does_not_block(tmp_git_repo: Path) -> None:
    # [2]: an earlier round's endpoint is unresolvable, but ANOTHER recorded range
    # still covers the same span — so the orphan costs nothing and there is no false
    # block. (What Feature 027 changes is the case where nothing else covers it.)
    base, _h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(
        repo, base, "HEAD",
        [{"reviewed_range": f"{base}..{'0' * 40}"}, {"reviewed_range": f"{base}..{h2}"}],
    )
    assert a.never_reached == []


def test_assess_no_range_starting_at_baseline_leaves_the_head_uncovered(
    tmp_git_repo: Path,
) -> None:
    # Feature 025 reported this as `not has_anchor`; it is now the same block with the
    # file named.
    base, h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{h1}..{h2}"}])
    assert a.has_scope_records and a.never_reached == ["a.py"]


def test_assess_sole_range_unresolvable_covers_nothing(tmp_git_repo: Path) -> None:
    # Feature 025 reported this as `not frontier_resolves`; now the paths it was
    # silently credited with are named instead.
    base, _h1, _h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{'0' * 40}"}])
    assert a.has_scope_records and a.never_reached == ["a.py", "b.py"]


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


# ---------------------------------------------------------------------------
# product_paths — the widened managed-path exclusion (Feature 027, FR-005/FR-005a)
# ---------------------------------------------------------------------------


def test_product_paths_drops_every_managed_artifact() -> None:
    """The exclusion covers `.specify/`, `specops.json`, the ACTIVE feature's spec
    dir — and, since Feature 027, EVERY `specs/<feature>/` directory."""
    paths = [
        "src/a.py",
        "tests/test_a.py",
        ".specify/memory/constitution.md",
        "specops.json",
        "specs/027-cross-round/spec.md",     # active feature
        "specs/003-other-feature/tasks.md",  # a DIFFERENT feature — 027 widening
        "specs/README.md",
    ]
    assert reviewscope.product_paths(paths, "027-cross-round") == ["src/a.py", "tests/test_a.py"]


def test_product_paths_widening_holds_without_a_feature_name() -> None:
    # With no active feature resolved, `is_managed` cannot drop any spec dir; the
    # widened prefix check still does.
    assert reviewscope.product_paths(["specs/003-x/spec.md", "src/a.py"], None) == ["src/a.py"]


def test_product_paths_keeps_a_product_path_that_merely_starts_with_spec() -> None:
    # The prefix is `specs/`, not `spec`: a product package named `specs_util/` or a
    # file named `specset.py` is product code and must survive.
    kept = ["specset.py", "specs_util/core.py", "src/specs.py"]
    assert reviewscope.product_paths(kept, "027-cross-round") == kept


def test_product_paths_renamed_feature_leaves_no_orphan_spec_paths() -> None:
    """Feature 026 renames a feature; the ledger keeps no rename history, so
    `is_managed` (which knows only the CURRENT name) would let the OLD directory's
    paths through and park them in the never-reached set. The widening prevents it."""
    diff_after_rename = [
        "specs/026-old-name/spec.md",   # deleted by the rename — not the active name
        "specs/026-new-name/spec.md",   # added by the rename — the active name
        "src/product.py",
    ]
    assert reviewscope.product_paths(diff_after_rename, "026-new-name") == ["src/product.py"]


# ---------------------------------------------------------------------------
# Feature 027 US2 — per-path coverage: what NO recorded round has ever reached
# ---------------------------------------------------------------------------


def test_never_reached_empty_on_an_intact_chain(tmp_git_repo: Path) -> None:
    """SC-002, the no-false-block case. anchor base..h1 + corrective h1..h2 chains
    to HEAD, so nothing is left over."""
    base, h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [
        {"reviewed_range": f"{base}..{h1}"},
        {"reviewed_range": f"{h1}..{h2}"},
    ])
    assert a.never_reached == []


def test_never_reached_empty_when_a_file_changed_only_mid_chain(tmp_git_repo: Path) -> None:
    """R1's transitivity argument: segment tree-diffs compose. `mid.py` is created and
    then modified inside the middle segment and never touched again — it must count as
    reached even though no single segment endpoint pair is `base..HEAD`."""
    base = _commit(tmp_git_repo, "a.py", "1")
    h1 = _commit(tmp_git_repo, "mid.py", "1")
    h2 = _commit(tmp_git_repo, "mid.py", "2")
    _commit(tmp_git_repo, "z.py", "1")
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [
        {"reviewed_range": f"{base}..{h1}"},
        {"reviewed_range": f"{h1}..{h2}"},
        {"reviewed_range": f"{h2}..HEAD"},
    ])
    assert a.never_reached == []


def test_unresolvable_range_is_credited_with_nothing(tmp_git_repo: Path) -> None:
    """SC-003, the silent-credit hole. The anchor's `to` was rewritten away; the
    paths it alone accounted for fall back to never-reached and are NAMED."""
    base, _h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [
        {"reviewed_range": f"{base}..{'0' * 40}"},   # orphaned
        {"reviewed_range": f"{h2}..HEAD"},           # resolves, but covers nothing new
    ])
    assert a.never_reached == ["a.py", "b.py"]


def test_moved_baseline_names_the_newly_included_span(tmp_git_repo: Path) -> None:
    """SC-003: the rounds were recorded against a later baseline; pointing the
    baseline earlier widens the target, and the extra span is unreviewed."""
    base, h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{h1}..{h2}"}])
    # h1..h2 introduced b.py; a.py changed in base..h1, which no round covers.
    assert a.never_reached == ["a.py"]


def test_no_anchor_names_the_uncovered_head_of_the_chain(tmp_git_repo: Path) -> None:
    """Subsumes the old `has_anchor` branch — same block, now with the file named."""
    base, h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{h1}..{h2}"}])
    assert a.has_scope_records and a.never_reached == ["a.py"]


def test_tail_after_the_last_round_is_named(tmp_git_repo: Path) -> None:
    """Subsumes the old `unreviewed_tail` branch — same block, now per path."""
    base, h1, _h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{h1}"}])
    assert a.never_reached == ["b.py"] and a.unreviewed_tail == ["b.py"]


def test_never_reached_is_sorted_and_deterministic(tmp_git_repo: Path) -> None:
    """SC-006: two derivations on unchanged inputs are identical, and the order is
    stable regardless of the order the paths happen to come out of git."""
    base = _commit(tmp_git_repo, "z.py", "1")
    _commit(tmp_git_repo, "a.py", "1")
    _commit(tmp_git_repo, "m.py", "1")
    repo = gitops.find_repo(tmp_git_repo)
    first = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{'0' * 40}"}])
    second = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{'0' * 40}"}])
    assert first.never_reached == second.never_reached == ["a.py", "m.py"]


def test_managed_artifacts_never_enter_either_coverage_set(tmp_git_repo: Path) -> None:
    """Methodology bookkeeping cannot block approval — including ANOTHER feature's
    spec dir, per the Feature 027 widening."""
    base = _commit(tmp_git_repo, "src/a.py", "1")
    _commit(tmp_git_repo, "specs/003-other/tasks.md", "x")
    _commit(tmp_git_repo, ".specify/memory/constitution.md", "x")
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, base, "HEAD", [{"reviewed_range": f"{base}..{'0' * 40}"}],
                           "001-active")
    assert a.never_reached == []
    assert a.target_empty


def test_target_empty_still_short_circuits(tmp_git_repo: Path) -> None:
    _base, _h1, h2 = _linear_repo(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    a = reviewscope.assess(repo, h2, "HEAD", [{"reviewed_range": f"{h2}..{h2}"}])
    assert a.target_empty and a.never_reached == []
