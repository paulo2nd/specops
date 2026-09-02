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


def test_corrective_reanchors_when_prior_endpoint_rewritten(handoff_repo) -> None:
    # [6]: the prior round's `to` was rewritten away (rebase/squash). record-scope
    # re-anchors over the full baseline..HEAD instead of failing closed.
    root, _h = _anchored_corrective_repo(handoff_repo)
    fp = root / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    baseline = data["baseline"]
    data["review_cycles"][0]["reviewed_range"] = f"{baseline}..{'0' * 40}"  # dead prior `to`
    fp.write_text(yaml.dump(data))
    _commit(root, "src/c.py", "fixed")
    r = cli(root, "handoff", "record-scope", "--json")
    assert r.returncode == 0, r.stderr
    obj = json.loads(r.stdout)
    assert obj["review_role"] == "anchor"                  # re-anchored, not fail-closed
    assert obj["reviewed_range"].startswith(baseline)


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


# ---------------------------------------------------------------------------
# Feature 027 US1 — the round also emits the full baseline set (FR-001/FR-002)
# ---------------------------------------------------------------------------


def test_corrective_round_emits_the_full_baseline_set(handoff_repo) -> None:
    """SC-001: the priority set narrows, the emitted baseline set does not. `src/a.py`
    changed before the anchor round's `to` and is untouched since — exactly the file
    #76 said becomes structurally invisible from round 2 onward."""
    root, _h = _anchored_corrective_repo(handoff_repo)
    _commit(root, "src/c.py", "fixed")
    obj = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)

    assert set(obj["scope_paths"]) == {"src/c.py"}
    assert set(obj["baseline_paths"]) == {f"src/{n}.py" for n in "abcde"}
    assert "src/a.py" in obj["baseline_paths"]


def test_not_reverified_is_the_baseline_set_minus_the_priority_set(handoff_repo) -> None:
    """SC-001 set algebra: disjoint from the priority set, and the two together cover
    the whole baseline set."""
    root, _h = _anchored_corrective_repo(handoff_repo)
    _commit(root, "src/c.py", "fixed")
    obj = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)

    scope, baseline = set(obj["scope_paths"]), set(obj["baseline_paths"])
    not_rev = set(obj["not_reverified_paths"])
    assert not_rev == baseline - scope
    assert not_rev & scope == set()
    assert scope | not_rev >= baseline


def test_anchor_round_implies_no_second_reading_obligation(handoff_repo) -> None:
    """AS US1-2: on an anchor round the two sets coincide, so the remainder is empty
    and the human output prints no `not yet re-verified` block."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    for name in ("a", "b"):
        _commit(root, f"src/{name}.py")
    obj = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)

    assert obj["review_role"] == "anchor"
    assert set(obj["scope_paths"]) == set(obj["baseline_paths"])
    assert obj["not_reverified_paths"] == []
    human = cli(root, "handoff", "record-scope").stdout
    assert "not yet re-verified" not in human


def test_emission_changes_nothing_the_round_persists(handoff_repo) -> None:
    """FR-002/FR-010: the emitted sets are presentation. Only `reviewed_range` and
    `review_role` reach the ledger — no emitted set is written."""
    root, h_anchor = _anchored_corrective_repo(handoff_repo)
    head = _commit(root, "src/c.py", "fixed")
    cli(root, "handoff", "record-scope")

    cycle = _ledger(root)["review_cycles"][1]
    assert cycle["reviewed_range"] == f"{h_anchor}..{head}"
    assert cycle["review_role"] == "corrective"
    for leaked in ("baseline_paths", "not_reverified_paths", "never_reached_paths"):
        assert leaked not in cycle
    assert "scope_paths" not in cycle


def test_record_scope_json_keys_are_additive_only(handoff_repo) -> None:
    """The Feature 021 stability policy: new OPTIONAL keys, nothing removed or
    repurposed, and the family's `output_version` does not move."""
    root = handoff_repo(review_cycles=[make_cycle(round=1)])
    _commit(root, "src/a.py")
    obj = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)

    assert {"round", "review_role", "reviewed_range", "scope_paths"} <= obj.keys()
    assert obj["output_version"] == 1
    assert obj["command"] == "handoff record-scope"
    assert obj["outcome"] == "ok"


def test_human_output_labels_each_set_and_omits_empty_blocks(handoff_repo) -> None:
    root, _h = _anchored_corrective_repo(handoff_repo)
    _commit(root, "src/c.py", "fixed")
    human = cli(root, "handoff", "record-scope").stdout

    assert "review scope: corrective round 2" in human
    assert "not yet re-verified this round" in human
    # The remainder is 4 of the 5 baseline files.
    assert "(4 of 5 baseline file(s))" in human
    for path in ("src/a.py", "src/b.py", "src/d.py", "src/e.py"):
        assert path in human


def test_record_scope_reports_the_never_reached_set(handoff_repo) -> None:
    """US2/SC-003: the history's holes surface where the reviewer can act on them —
    a third labelled subset, distinct from the priority set and the remainder.

    The state that produces a hole `record-scope` cannot self-heal: the recorded
    chain never reaches back to the baseline (a rebaselined feature), so
    `derive_range` chains from the last resolvable `to` instead of re-anchoring.
    An orphaned chain SUFFIX is the other case and it *does* self-heal — that path
    is covered by the recovery test in test_review_coverage_guard.py.
    """
    root = handoff_repo(review_cycles=[
        make_cycle(round=1, result="REJECTED"),
        make_cycle(round=2),
    ])
    _commit(root, "src/a.py")            # changed in baseline..h_a — no round covers it
    h_a = git(root, "rev-parse", "HEAD")
    for name in ("b", "c"):
        _commit(root, f"src/{name}.py")
    h_anchor = git(root, "rev-parse", "HEAD")
    fp = root / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    data["review_cycles"][0]["reviewed_range"] = f"{h_a}..{h_anchor}"   # starts AFTER the baseline
    data["review_cycles"][0]["review_role"] = "anchor"
    fp.write_text(yaml.dump(data))
    _commit(root, "src/c.py", "fixed")

    obj = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)
    assert obj["never_reached_paths"] == ["src/a.py"]
    assert "src/c.py" not in obj["never_reached_paths"]   # this round's own range
    assert "src/b.py" not in obj["never_reached_paths"]   # the recorded round's range

    human = cli(root, "handoff", "record-scope").stdout
    assert "never reviewed by any round (1)" in human


def test_never_reached_is_empty_and_omitted_on_an_intact_history(handoff_repo) -> None:
    root, _h = _anchored_corrective_repo(handoff_repo)
    _commit(root, "src/c.py", "fixed")
    obj = json.loads(cli(root, "handoff", "record-scope", "--json").stdout)
    assert obj["never_reached_paths"] == []
    assert "never reviewed by any round" not in cli(root, "handoff", "record-scope").stdout
