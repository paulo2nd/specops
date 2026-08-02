"""Integration tests for the review round cap (Feature 025, US3).

Quickstart Scenarios 5 & 8: exceeding the cap halts (exit 1), records a
``review_halt`` marker, keeps round-N REJECTED, opens no round N+1, and fabricates
no verdict; raising the cap then resumes the loop (research R8).
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from tests.conftest import cli, make_cycle


def _ledger(root: Path) -> dict:
    return yaml.safe_load((root / "specs" / "001-demo" / "status.yaml").read_text())


def _set_cap(root: Path, cap: int) -> None:
    (root / "specops.json").write_text(json.dumps({"review_round_cap": cap}))


def _two_round_repo(handoff_repo):
    """Round 1 REJECTED (closed), round 2 open — the next REJECTED would open round 3."""
    return handoff_repo(review_cycles=[
        make_cycle(round=1, result="REJECTED"),
        make_cycle(round=2),
    ])


def test_round_cap_halts_and_asks(handoff_repo) -> None:
    root = _two_round_repo(handoff_repo)
    _set_cap(root, 2)  # rounds 1..2 allowed; opening round 3 halts
    r = cli(root, "status", "transition-phase", "IMPLEMENT", "-r", "REJECTED")
    assert r.returncode == 1
    assert "cap" in (r.stdout + r.stderr).lower()
    data = _ledger(root)
    assert data["current_phase"] == "REVIEW"                 # not transitioned
    assert data["review_halt"]["at_round"] == 2
    assert data["review_halt"]["cap"] == 2
    assert data["review_cycles"][-1]["result"] == "REJECTED"  # round 2 verdict recorded
    assert len(data["review_cycles"]) == 2                    # no round 3 opened


def test_default_cap_allows_normal_cycles(handoff_repo) -> None:
    # No specops.json → default cap 10; a 3rd round opens normally.
    root = _two_round_repo(handoff_repo)
    r = cli(root, "status", "transition-phase", "IMPLEMENT", "-r", "REJECTED")
    assert r.returncode == 0, r.stderr
    data = _ledger(root)
    assert data["current_phase"] == "IMPLEMENT"
    assert len(data["review_cycles"]) == 3
    assert "review_halt" not in data


def test_resume_after_halt_by_raising_cap(handoff_repo) -> None:
    root = _two_round_repo(handoff_repo)
    _set_cap(root, 2)
    assert cli(root, "status", "transition-phase", "IMPLEMENT", "-r", "REJECTED").returncode == 1
    _set_cap(root, 5)  # raise the cap → resume
    r = cli(root, "status", "transition-phase", "IMPLEMENT", "-r", "REJECTED")
    assert r.returncode == 0, r.stderr
    data = _ledger(root)
    assert data["current_phase"] == "IMPLEMENT"
    assert len(data["review_cycles"]) == 3          # round 3 opened
    assert "review_halt" in data                    # marker retained for audit
