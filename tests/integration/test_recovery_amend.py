"""Integration: the full recovery path for a wrongly-closed task (Feature 026, T035).

Reproduces the field scenario behind #74 end to end: a session closes a task with
placeholder evidence and dies; a recovery session that has re-run the gates records
the verified truth through `amend-task`; the ledger then reads correctly through
every downstream surface — `reconcile`, `trace report`, and a review finding closed
against that task.

Covers SC-001 (correction without a hand edit), SC-003 (the amendment is visible as
one), and SC-004 (no amended value loses its provenance by being inherited).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from specops import handoff, ledger, reconcile, trace
from specops import status as s
from tests.unit.test_amend_task import _repo_with_done_task

VERIFIED = "TEST_REPORT:1795 passed, 0 failed"
WHY = "original close recorded no gate run; session terminated mid-flight"


def _ledger(feature_dir: Path) -> dict:
    return yaml.safe_load((feature_dir / "status.yaml").read_text(encoding="utf-8"))


def test_wrongly_closed_task_is_corrected_end_to_end(tmp_path: Path) -> None:
    root, feature_dir = _repo_with_done_task(tmp_path, evidence="CLI_LOG:placeholder")

    # The state the interrupted session left behind: DONE, with evidence that is a lie.
    before = _ledger(feature_dir)
    task_before = next(t for t in before["tasks"] if t["id"] == "T001")
    assert task_before["status"] == "DONE"
    assert task_before["evidence"] == "CLI_LOG:placeholder"

    # The recovery session records what it actually verified — no hand edit anywhere.
    out = s.cmd_amend_task(root, "T001", evidence=VERIFIED, reason=WHY)
    assert "amended" in out and WHY in out

    data = _ledger(feature_dir)
    task = next(t for t in data["tasks"] if t["id"] == "T001")

    # 1. The correction is current; the original is retained, superseded, unaltered.
    assert task["evidence"] == VERIFIED
    by_id = {r["id"]: r for r in data["evidence"]}
    records = [by_id[r] for r in task["evidence_refs"]]
    assert len(records) == 2
    original, amendment = records
    assert original["summary"] == "CLI_LOG:placeholder"
    assert original["superseded_by"] == amendment["id"]
    assert amendment["amendment"] is True and amendment["reason"] == WHY

    # 2. Nothing about the close moved.
    assert task["status"] == "DONE"
    assert task["completed_at"] == task_before["completed_at"]
    assert task["commits"] == task_before["commits"]

    # 3. The integrity check accepts it.
    assert ledger.validate_invariants(data) == []
    _warnings, violations = reconcile.run(root)
    assert violations == []

    # 4. The audit surface shows it as an amendment, with its history reachable.
    graph = trace.build_graph(root)
    node = next(t for t in graph["tasks"] if t["id"] == "T001")
    assert node["evidence"] == VERIFIED
    assert node["evidence_amended"] is True
    assert node["evidence_history"] == [original["id"]]


def test_a_finding_closed_against_an_amended_task_keeps_the_provenance(
    tmp_path: Path,
) -> None:
    """The laundering path: `finding fix --auto` copies the task's evidence string.
    The copy must arrive carrying the amendment marker (FR-006a/SC-004)."""
    root, feature_dir = _repo_with_done_task(tmp_path, evidence="CLI_LOG:placeholder")
    s.cmd_amend_task(root, "T001", evidence=VERIFIED, reason=WHY)

    # Open a review round with one finding, then close it against the amended task.
    s.cmd_transition_phase(root, "REVIEW", result=None)
    add = handoff.cmd_finding_add(
        root, severity="blocking", rule="L2", file="src/a.py", line=1,
        action="fix it", expected_evidence="a test", closure="test passes")
    assert add.exit_code == 0

    from specops import gitops
    head = gitops.head_sha(gitops.find_repo(root))
    fix = handoff.cmd_finding_fix(
        root, add.extra["id"], task="T001", commits=[head], evidence=None, auto=True)
    assert fix.status == handoff.FINDING_FIXED

    data = _ledger(feature_dir)
    finding = data["review_cycles"][-1]["handoff"]["findings"][0]
    inherited = next(r for r in data["evidence"] if r["id"] == finding["evidence_id"])
    assert finding["evidence"] == VERIFIED
    assert inherited["amendment"] is True
    assert inherited["reason"] == WHY


def test_amending_twice_keeps_the_whole_chain_readable(tmp_path: Path) -> None:
    """An amended task is *more* informative than a silently-correct one — that is
    what stops amendment from being a way to launder a bad close."""
    root, feature_dir = _repo_with_done_task(tmp_path, evidence="CLI_LOG:placeholder")
    s.cmd_amend_task(root, "T001", evidence="TEST_REPORT:partial rerun", reason="first pass")
    s.cmd_amend_task(root, "T001", evidence=VERIFIED, reason=WHY)

    data = _ledger(feature_dir)
    task = next(t for t in data["tasks"] if t["id"] == "T001")
    by_id = {r["id"]: r for r in data["evidence"]}
    chain = [by_id[r] for r in task["evidence_refs"]]

    assert [c["summary"] for c in chain] == [
        "CLI_LOG:placeholder", "TEST_REPORT:partial rerun", VERIFIED,
    ]
    assert [c.get("reason") for c in chain] == [None, "first pass", WHY]
    assert [c["superseded_by"] is None for c in chain] == [False, False, True]
    assert ledger.validate_invariants(data) == []
