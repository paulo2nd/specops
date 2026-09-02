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


# ---------------------------------------------------------------------------
# Feature 027 US3 — approval fails closed on a path NO round ever reached,
# and says which one. Roadmap acceptance gate.
# ---------------------------------------------------------------------------


def _rejected_rejected_repo(handoff_repo):
    """Two REJECTED rounds and an open third, with `src/never.py` changed before the
    recorded chain starts — the rebaselined-feature shape, which `record-scope`
    cannot self-heal (its chain start still resolves)."""
    root = handoff_repo(review_cycles=[
        make_cycle(round=1, result="REJECTED"),
        make_cycle(round=2, result="REJECTED"),
        make_cycle(round=3),
    ])
    _commit(root, "src/never.py")
    h_gap = git(root, "rev-parse", "HEAD")
    _commit(root, "src/a.py")
    h1 = git(root, "rev-parse", "HEAD")
    _commit(root, "src/b.py")
    h2 = git(root, "rev-parse", "HEAD")
    fp = root / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    data["review_cycles"][0].update(reviewed_range=f"{h_gap}..{h1}", review_role="anchor")
    data["review_cycles"][1].update(reviewed_range=f"{h1}..{h2}", review_role="corrective")
    fp.write_text(yaml.dump(data))
    return root, data["baseline"], h_gap


def test_never_reached_path_fails_approval_closed_and_names_it(handoff_repo) -> None:
    """SC-004 / the roadmap acceptance gate: REJECTED -> REJECTED -> APPROVED where
    no round ever reached `src/never.py`."""
    root, _baseline, _h = _rejected_rejected_repo(handoff_repo)
    cli(root, "handoff", "record-scope")
    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")

    assert r.returncode == 1
    out = r.stdout + r.stderr
    assert "src/never.py" in out
    assert "never been reviewed by any recorded round" in out
    assert _ledger(root)["current_phase"] == "REVIEW"


def test_an_anchor_round_covering_it_approves(handoff_repo) -> None:
    """SC-004, the other half of the gate: the same sequence with a round whose range
    reaches the file approves."""
    root, baseline, _h = _rejected_rejected_repo(handoff_repo)
    fp = root / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    data["review_cycles"][0]["reviewed_range"] = (
        f"{baseline}..{data['review_cycles'][0]['reviewed_range'].split('..')[1]}"
    )
    fp.write_text(yaml.dump(data))
    cli(root, "handoff", "record-scope")

    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(root)["current_phase"] == "DONE"


def test_empty_target_still_approves(handoff_repo) -> None:
    """No product change since the baseline — coverage is vacuously satisfied."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    _commit(root, "specs/001-demo/notes.md")  # managed artifact only
    fp = root / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    data["review_cycles"][0].update(
        reviewed_range=f"{data['baseline']}..{git(root, 'rev-parse', 'HEAD')}",
        review_role="anchor",
    )
    fp.write_text(yaml.dump(data))
    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 0, r.stdout + r.stderr


def test_blocked_message_is_bounded_at_ten_paths(handoff_repo) -> None:
    """R6/SC-004: the count is always stated; at most 10 paths are named."""
    root = handoff_repo(review_cycles=[make_cycle(round=1, result="REJECTED"),
                                       make_cycle(round=2)])
    for i in range(37):
        _commit(root, f"src/f{i:02d}.py")
    h_gap = git(root, "rev-parse", "HEAD")
    _commit(root, "src/tail.py")
    h1 = git(root, "rev-parse", "HEAD")
    fp = root / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    data["review_cycles"][0].update(reviewed_range=f"{h_gap}..{h1}", review_role="anchor")
    fp.write_text(yaml.dump(data))
    cli(root, "handoff", "record-scope")

    blocked = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    out = blocked.stdout + blocked.stderr
    assert "37 product path(s)" in out
    assert "(10 shown of 37)" in out
    assert out.count("src/f") == 10
    # sorted order, so the first ten are f00..f09
    assert "src/f00.py" in out and "src/f09.py" in out and "src/f10.py" not in out


def test_blocked_message_names_them_all_when_few(handoff_repo) -> None:
    root, _baseline, _h = _rejected_rejected_repo(handoff_repo)
    cli(root, "handoff", "record-scope")
    blocked = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    out = blocked.stdout + blocked.stderr
    assert "1 product path(s)" in out
    assert "shown of" not in out


def test_orphaned_chain_suffix_recovers_in_one_record_scope(handoff_repo) -> None:
    """Research R2, all three facts. A squash/amend orphans the recorded review HEAD;
    approval blocks; ONE `record-scope` on the still-open round re-anchors over
    baseline..HEAD and the retry approves — with no new round consumed."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    _commit(root, "src/a.py")
    cli(root, "handoff", "record-scope")
    # Fact 1: a rewrite orphans a SUFFIX of the chain — here the whole of it.
    fp = root / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    data["review_cycles"][0]["reviewed_range"] = f"{data['baseline']}..{'0' * 40}"
    fp.write_text(yaml.dump(data))

    blocked = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert blocked.returncode == 1
    assert "src/a.py" in blocked.stdout + blocked.stderr

    # Fact 3: the guard raised before finalize, so the round is still open on disk.
    after_block = _ledger(root)
    assert after_block["review_cycles"][-1]["result"] is None
    assert len(after_block["review_cycles"]) == 1

    # Fact 2: derive_range falls back to ANCHOR because the prior `to` is orphaned.
    rescope = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)
    assert rescope["review_role"] == "anchor"
    assert rescope["never_reached_paths"] == []

    retry = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert _ledger(root)["current_phase"] == "DONE"
    assert len(_ledger(root)["review_cycles"]) == 1   # no new round consumed


def test_guard_never_reads_a_findings_merit(handoff_repo) -> None:
    """FR-011: coverage is evaluated from ranges and git only. A round carrying an
    OPEN advisory finding still approves when coverage is complete — the finding
    gate is a separate, earlier check."""
    root = handoff_repo(review_cycles=[make_cycle(
        round=1, findings=[make_finding("R1-F01", state="OPEN", severity="advisory")])])
    _commit(root, "src/a.py")
    cli(root, "handoff", "record-scope")
    r = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 0, r.stdout + r.stderr
