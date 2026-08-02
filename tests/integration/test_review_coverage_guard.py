"""Integration tests for the union-coverage approval guard (Feature 025, US1).

Drives the real CLI (`handoff record-scope`, `status transition-phase`) against a
git fixture. Covers quickstart Scenarios 2, 3, 6 and the FR-004 assertion; the
unresolvable-baseline fail-closed (Scenario 7) is a unit test on the guard, since
the transition's identity check also fail-closes a bogus baseline first.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from specops import gitops, records, status
from tests.conftest import cli, git, make_cycle, make_finding


def _ledger(root: Path) -> dict:
    return yaml.safe_load((root / "specs" / "001-demo" / "status.yaml").read_text())


def _commit(root: Path, path: str, content: str = "x") -> str:
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    git(root, "add", "-A")
    git(root, "commit", "-m", f"edit {path}")
    return git(root, "rev-parse", "HEAD")


def _verified_finding() -> dict:
    return make_finding("R1-F01", state="VERIFIED", task="T1", commits=["abc123"], evidence="X:y")


def test_anchor_scope_then_approve(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    _commit(root, "src/a.py")
    r = cli(root, "handoff", "record-scope", "--json")
    assert r.returncode == 0, r.stderr
    obj = json.loads(r.stdout)
    assert obj["review_role"] == "anchor"
    assert "src/a.py" in obj["scope_paths"]
    r2 = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r2.returncode == 0, r2.stderr
    assert _ledger(root)["current_phase"] == "DONE"


def test_partial_coverage_blocks_approval(handoff_repo) -> None:
    """Scenario 2: a change made after recording scope leaves an uncovered path."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    _commit(root, "src/a.py")
    assert cli(root, "handoff", "record-scope").returncode == 0
    _commit(root, "src/b.py")  # new change the recorded anchor range does not cover
    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 1
    assert "src/b.py" in (r.stdout + r.stderr)
    assert _ledger(root)["current_phase"] == "REVIEW"  # not transitioned


def test_legacy_no_scope_records_degrades(handoff_repo) -> None:
    """Scenario 6: a cycle with no reviewed_range approves via the prior path."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 0, r.stderr
    assert _ledger(root)["current_phase"] == "DONE"


def test_fr004_verified_finding_does_not_block_when_coverage_complete(handoff_repo) -> None:
    """FR-004: the guard never blocks on a finding's merit — complete coverage +
    a VERIFIED blocking finding approves."""
    root = handoff_repo(review_cycles=[make_cycle(round=1, findings=[_verified_finding()])])
    _commit(root, "src/a.py")
    assert cli(root, "handoff", "record-scope").returncode == 0
    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 0, r.stderr


def test_fr004_incomplete_coverage_blocks_even_with_findings_verified(handoff_repo) -> None:
    """FR-004: coverage is evaluated independently of findings — incomplete coverage
    blocks even when every blocking finding is VERIFIED."""
    root = handoff_repo(review_cycles=[make_cycle(round=1, findings=[_verified_finding()])])
    _commit(root, "src/a.py")
    assert cli(root, "handoff", "record-scope").returncode == 0
    _commit(root, "src/b.py")
    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 1
    assert "src/b.py" in (r.stdout + r.stderr)


def test_record_scope_takes_no_range_argument(handoff_repo) -> None:
    """SC-006: scope is git-derived, never reviewer-supplied — the command exposes
    no positional/range argument."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    _commit(root, "src/a.py")
    r = cli(root, "handoff", "record-scope", "deadbeef..cafef00d")
    assert r.returncode != 0  # Typer rejects the unexpected extra argument


def test_unreviewed_commit_after_frontier_blocks(handoff_repo) -> None:
    """[5]: a commit that lands after the recorded review (even re-touching an
    already-reviewed file) is caught by the frontier..HEAD tail, not falsely passed."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    _commit(root, "src/a.py", "v1")
    assert cli(root, "handoff", "record-scope").returncode == 0  # anchor frontier = HEAD
    _commit(root, "src/a.py", "v2")  # re-touch the SAME already-reviewed file
    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 1
    assert "src/a.py" in (r.stdout + r.stderr)
    assert _ledger(root)["current_phase"] == "REVIEW"


def test_rebaseline_clears_stale_reviewed_scope(handoff_repo) -> None:
    """[7]: rebaseline drops stale reviewed_range records so the coverage guard cannot
    pass vacuously against an empty baseline..HEAD."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    _commit(root, "src/a.py")
    assert cli(root, "handoff", "record-scope").returncode == 0
    assert _ledger(root)["review_cycles"][0].get("reviewed_range")  # present before
    r = cli(root, "status", "rebaseline")
    assert r.returncode == 0, r.stderr
    cyc = _ledger(root)["review_cycles"][0]
    assert "reviewed_range" not in cyc and "review_role" not in cyc


def test_unresolvable_baseline_fails_closed(tmp_git_repo: Path) -> None:
    """Scenario 7 (unit): scope records + an unresolvable baseline → the guard raises
    (never a silent approval)."""
    root = tmp_git_repo
    (root / "a.py").write_text("1")
    git(root, "add", "-A")
    git(root, "commit", "-m", "c")
    repo = gitops.find_repo(root)
    data: records.LedgerDocument = {
        "baseline": "0" * 40,  # unresolvable
        "review_cycles": [{"round": 1, "reviewed_range": f"{'0' * 40}..{'1' * 40}",
                           "review_role": "anchor", "result": "APPROVED"}],
    }
    try:
        status._gate_review_coverage(data, repo)
        raised = False
    except Exception as exc:  # noqa: BLE001
        raised = True
        assert "baseline" in str(exc).lower()
    assert raised
