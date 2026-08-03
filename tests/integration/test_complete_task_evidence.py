"""Integration: complete-task records structured evidence (Feature 012, US2, T015).

Covers FR-006/SC-005: `complete-task --evidence`/`--auto` appends a StructuredEvidence
record to the ledger and sets `task.evidence_refs`, alongside the retained legacy string.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from specops import status as s
from tests.unit.test_status import _in_progress_task_setup


def _ledger(feature_dir: Path) -> dict:
    return yaml.safe_load((feature_dir / "status.yaml").read_text())


def test_manual_evidence_records_structured_record(tmp_path: Path) -> None:
    root, feature_dir, _head = _in_progress_task_setup(tmp_path)
    s.cmd_complete_task(root, "T001", auto=False, evidence="CLI_LOG:manual ok")

    data = _ledger(feature_dir)
    task = next(t for t in data["tasks"] if t["id"] == "T001")
    # legacy string retained
    assert task["evidence"] == "CLI_LOG:manual ok"
    # structured record + reference present and resolvable
    assert len(task["evidence_refs"]) == 1
    ref = task["evidence_refs"][0]
    ev = {r["id"]: r for r in data["evidence"]}
    assert ref in ev
    rec = ev[ref]
    assert rec["summary"] == "CLI_LOG:manual ok"
    assert rec["producer"] == "auto"
    assert rec["exit_code"] == 0
    assert "superseded_by" in rec


def test_complete_task_preserves_trace_linked_out_of_range_commit(tmp_path: Path) -> None:
    """`complete-task` must union, not overwrite: a commit bound via `trace link`
    that falls outside the harvested started..HEAD range survives completion."""
    import subprocess as sp

    from specops import trace
    root, feature_dir, started = _in_progress_task_setup(tmp_path)
    # `started` is an ancestor of HEAD but outside the exclusive started..HEAD range
    assert trace.cmd_link(root, task="T001", commits=[started]).status == trace.LINK_RECORDED
    # advance HEAD so the auto-harvest range is non-empty
    (root / "f.py").write_text("x\n")
    sp.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "work"], cwd=root, check=True, capture_output=True)

    s.cmd_complete_task(root, "T001", auto=True, evidence=None)

    task = next(t for t in _ledger(feature_dir)["tasks"] if t["id"] == "T001")
    assert started in task["commits"]        # the linked commit was not clobbered
    assert len(task["commits"]) >= 2         # harvested range + the linked commit
    assert task["commits"][0] != started     # harvest head stays newest-first


def test_evidence_id_is_deterministic_and_ledger_valid(tmp_path: Path) -> None:
    from specops import ledger

    root, feature_dir, _head = _in_progress_task_setup(tmp_path)
    s.cmd_complete_task(root, "T001", auto=False, evidence="TEST_REPORT:ok")
    data = _ledger(feature_dir)
    # the migrated/recorded ledger satisfies the v6 invariants (no dangling refs)
    assert ledger.validate_invariants(data) == []
    assert data["evidence"][0]["id"].startswith("EV-")
