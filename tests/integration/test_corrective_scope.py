"""Integration tests for corrective-round scoping (Feature 025, US2).

Quickstart Scenario 4 / SC-003: a corrective round is scoped to prev_to..HEAD
(the fix delta) plus prior non-terminal findings' files, never the untouched
already-reviewed remainder; and re-recording the same round is idempotent (U2).
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

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


def _anchored_corrective_repo(handoff_repo, *, findings=None):
    """Round 1 REJECTED (anchor over a..e recorded), round 2 open (corrective)."""
    root = handoff_repo(review_cycles=[
        make_cycle(round=1, result="REJECTED", findings=findings),
        make_cycle(round=2),
    ])
    for name in ("a", "b", "c", "d", "e"):
        _commit(root, f"src/{name}.py")
    h_anchor = git(root, "rev-parse", "HEAD")
    fp = root / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    data["review_cycles"][0]["reviewed_range"] = f"{data['baseline']}..{h_anchor}"
    data["review_cycles"][0]["review_role"] = "anchor"
    fp.write_text(yaml.dump(data))
    return root, h_anchor


def test_corrective_scope_excludes_untouched(handoff_repo) -> None:
    root, h_anchor = _anchored_corrective_repo(handoff_repo)
    _commit(root, "src/c.py", "fixed")  # the fix touches only c
    r = cli(root, "handoff", "record-scope", "--json")
    assert r.returncode == 0, r.stderr
    obj = json.loads(r.stdout)
    assert obj["review_role"] == "corrective"
    assert set(obj["scope_paths"]) == {"src/c.py"}
    for untouched in ("src/a.py", "src/b.py", "src/d.py", "src/e.py"):
        assert untouched not in obj["scope_paths"]
    assert obj["reviewed_range"] == f"{h_anchor}..{git(root, 'rev-parse', 'HEAD')}"


def test_corrective_scope_includes_prior_nonterminal_finding_file(handoff_repo) -> None:
    # An OPEN finding on src/a.py is part of the regression surface even though the
    # fix only touched c.
    root, _h = _anchored_corrective_repo(
        handoff_repo, findings=[make_finding("R1-F01", state="OPEN", file="src/a.py")])
    _commit(root, "src/c.py", "fixed")
    obj = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)
    assert set(obj["scope_paths"]) == {"src/c.py", "src/a.py"}


def test_corrective_record_scope_idempotent(handoff_repo) -> None:
    root, _h = _anchored_corrective_repo(handoff_repo)
    _commit(root, "src/c.py", "fixed")
    first = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)
    second = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)
    assert first["reviewed_range"] == second["reviewed_range"]
    assert first["review_role"] == second["review_role"] == "corrective"
    data = _ledger(root)
    assert len(data["review_cycles"]) == 2  # no extra cycle appended
    assert data["review_cycles"][1]["review_role"] == "corrective"
