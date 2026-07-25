"""Integration tests for `specops report` (Feature 014, US3)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from specops import doctor
from specops.cli import app

runner = CliRunner()


def _invoke(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, list(args))
    finally:
        os.chdir(cwd)


def test_report_human(doctor_healthy_repo: Path) -> None:
    result = _invoke(doctor_healthy_repo, "report")
    assert result.exit_code == 0
    assert "feature: 001-demo" in result.stdout
    assert "phase: IMPLEMENT" in result.stdout


def test_report_json_fields(doctor_healthy_repo: Path) -> None:
    result = _invoke(doctor_healthy_repo, "report", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "report"
    assert payload["output_version"] == doctor.OUTPUT_VERSION
    assert payload["active_feature"] == "001-demo"
    assert payload["phase"] == "IMPLEMENT"


def test_report_no_active_feature_is_ok(context_map_repo: Path) -> None:
    result = _invoke(context_map_repo, "report", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["active_feature"] is None


def test_report_corrupt_ledger_exit_two(doctor_healthy_repo: Path) -> None:
    (doctor_healthy_repo / "specs" / "001-demo" / "status.yaml").write_text(":\n  - [broken")
    result = _invoke(doctor_healthy_repo, "report", "--json")
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["class"] == "infra-error"
