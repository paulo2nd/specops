"""Integration: opt-in SARIF output (Feature 012, US4, T032).

Covers FR-013/SC-009: `--sarif` on `review` and `gate report` emits schema-valid
SARIF 2.1.0; without `--sarif` no SARIF is emitted (and its absence is not a defect).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import make_cycle, make_finding, make_task


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=root, capture_output=True,
                          text=True, stdin=subprocess.DEVNULL)


def _repo_with_finding(handoff_repo):
    return handoff_repo(
        tasks=[make_task("T001")],
        review_cycles=[make_cycle(findings=[make_finding("R1-F01")])],
    )


def test_review_sarif_emits_schema_valid_document(handoff_repo) -> None:
    root = _repo_with_finding(handoff_repo)
    r = _run(root, "review", "--sarif")
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["tool"]["driver"]["name"] == "specops"
    # the finding is projected to a result
    results = doc["runs"][0]["results"]
    assert any(res["ruleId"] for res in results)


def test_gate_report_sarif_emits_document(handoff_repo) -> None:
    root = _repo_with_finding(handoff_repo)
    r = _run(root, "gate", "report", "--sarif")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["version"] == "2.1.0"


def test_no_sarif_without_flag(handoff_repo) -> None:
    root = _repo_with_finding(handoff_repo)
    # Without --sarif the default output is the outcome contract, never a SARIF doc.
    r = _run(root, "review", "--json")
    payload = json.loads(r.stdout)
    assert payload.get("command") == "review"
    assert payload.get("version") != "2.1.0"
