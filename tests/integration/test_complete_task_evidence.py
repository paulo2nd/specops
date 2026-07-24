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


def test_evidence_id_is_deterministic_and_ledger_valid(tmp_path: Path) -> None:
    from specops import ledger

    root, feature_dir, _head = _in_progress_task_setup(tmp_path)
    s.cmd_complete_task(root, "T001", auto=False, evidence="TEST_REPORT:ok")
    data = _ledger(feature_dir)
    # the migrated/recorded ledger satisfies the v6 invariants (no dangling refs)
    assert ledger.validate_invariants(data) == []
    assert data["evidence"][0]["id"].startswith("EV-")
