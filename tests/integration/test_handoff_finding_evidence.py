"""Integration: finding fix links structured evidence (Feature 012, US2, T016).

Covers FR-006/SC-004: `handoff finding fix` records a StructuredEvidence record and
sets `finding.evidence_id` (the actual evidence linked at FIXED, Feature 011 FR-005);
`verify` still resolves; the v6 invariants pass (no dangling evidence reference).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from specops import handoff, ledger
from tests.conftest import head_commit, make_cycle, make_finding, make_task


def _ledger(root: Path) -> dict:
    return yaml.safe_load((root / "specs" / "001-demo" / "status.yaml").read_text())


def test_finding_fix_sets_resolvable_evidence_id(handoff_repo) -> None:
    root = handoff_repo(
        tasks=[make_task("T001")],
        review_cycles=[make_cycle(findings=[make_finding("R1-F01")])],
    )
    sha = head_commit(root)

    res = handoff.cmd_finding_fix(
        root, "R1-F01", task="T001", commits=[sha], evidence="TEST_REPORT:ok", auto=False
    )
    assert res.status == handoff.FINDING_FIXED

    data = _ledger(root)
    finding = data["review_cycles"][-1]["handoff"]["findings"][0]
    eid = finding["evidence_id"]
    assert eid and eid.startswith("EV-")
    # the referenced record exists in the top-level evidence list
    ids = {r["id"] for r in data["evidence"]}
    assert eid in ids
    # legacy per-finding evidence string retained (Feature 011)
    assert finding["evidence"] == "TEST_REPORT:ok"
    # no dangling references (v6 invariant)
    assert ledger.validate_invariants(data) == []


def test_verify_after_fix_with_structured_evidence(handoff_repo) -> None:
    root = handoff_repo(
        tasks=[make_task("T001")],
        review_cycles=[make_cycle(findings=[make_finding("R1-F01")])],
    )
    sha = head_commit(root)
    handoff.cmd_finding_fix(
        root, "R1-F01", task="T001", commits=[sha], evidence="TEST_REPORT:ok", auto=False
    )
    res = handoff.cmd_finding_verify(root, "R1-F01")
    assert res.status == handoff.FINDING_VERIFIED
