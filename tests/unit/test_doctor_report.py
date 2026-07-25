"""Unit tests for the compact status report (Feature 014, US3): field mapping."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specops import doctor, status
from specops.errors import LedgerParseError


def test_compact_status_maps_ledger_fields(doctor_healthy_repo: Path) -> None:
    led = doctor_healthy_repo / "specs" / "001-demo" / "status.yaml"
    data = yaml.safe_load(led.read_text())
    data["tasks"] = [
        {"id": "T001", "status": "IN_PROGRESS", "orphaned": False},
        {"id": "T002", "status": "DONE", "orphaned": False, "evidence": "CLI_LOG:ok"},
        {"id": "T003", "status": "PENDING", "orphaned": False},
    ]
    led.write_text(yaml.dump(data))

    snap = status.compact_status(doctor_healthy_repo)
    assert snap["active_feature"] == "001-demo"
    assert snap["phase"] == "IMPLEMENT"
    assert snap["active_task"] == "T001"
    assert snap["tasks"] == {"pending": 1, "in_progress": 1, "done": 1, "orphaned": 0, "total": 3}
    assert snap["workflow_lane"] == "full"
    assert snap["review"]["blocking_open"] == 0


def test_compact_status_no_active_feature_is_null(context_map_repo: Path) -> None:
    snap = status.compact_status(context_map_repo)
    assert snap["active_feature"] is None
    assert snap["tasks"]["total"] == 0
    assert snap["phase"] is None


def test_compact_status_raises_on_corrupt_ledger(doctor_healthy_repo: Path) -> None:
    (doctor_healthy_repo / "specs" / "001-demo" / "status.yaml").write_text(":\n  - [broken")
    with pytest.raises(LedgerParseError):
        status.compact_status(doctor_healthy_repo)


def test_cmd_report_builds_versioned_payload(doctor_healthy_repo: Path) -> None:
    result = doctor.cmd_report(doctor_healthy_repo)
    assert result.payload["command"] == "report"
    assert result.payload["output_version"] == doctor.OUTPUT_VERSION
    assert result.payload["active_feature"] == "001-demo"
    assert result.exit_code == 0
