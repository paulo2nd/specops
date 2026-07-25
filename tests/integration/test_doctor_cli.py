"""Integration tests for `specops doctor` (Feature 014, US1/US2).

Drives the CLI via CliRunner asserting exit codes, the versioned --json document,
full domain coverage, multi-problem reporting, active-feature scope, and the
execution-error path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from typer.testing import CliRunner

from specops import doctor
from specops.cli import app
from tests.conftest import write_profiles, write_second_feature

runner = CliRunner()

DOMAIN_IDS = {
    "environment", "cli_extension", "integration", "legacy_artifacts", "configuration",
    "feature_identity", "ledger", "context_map", "workflow_divergence", "gate_availability",
}


def _invoke(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, list(args))
    finally:
        os.chdir(cwd)


def _ledger(root: Path) -> Path:
    return root / "specs" / "001-demo" / "status.yaml"


def test_healthy_human_exit_zero(doctor_healthy_repo: Path) -> None:
    result = _invoke(doctor_healthy_repo, "doctor")
    assert result.exit_code == 0
    assert "verdict: ok" in result.stdout


def test_json_reports_all_domains(doctor_healthy_repo: Path) -> None:
    result = _invoke(doctor_healthy_repo, "doctor", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "doctor"
    assert payload["output_version"] == doctor.OUTPUT_VERSION
    assert payload["verdict"] == "ok"
    assert {d["domain"] for d in payload["domains"]} == DOMAIN_IDS  # SC-002


def test_blocking_exit_one_and_distinct(doctor_healthy_repo: Path) -> None:
    data = yaml.safe_load(_ledger(doctor_healthy_repo).read_text())
    data["schema_version"] = 99
    _ledger(doctor_healthy_repo).write_text(yaml.dump(data))
    result = _invoke(doctor_healthy_repo, "doctor", "--json")
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "blocking"
    assert payload["class"] == "gate-rejection"


def test_execution_error_exit_two_domain_not_omitted(doctor_healthy_repo: Path) -> None:
    _ledger(doctor_healthy_repo).write_text(":\n  - [broken yaml")
    result = _invoke(doctor_healthy_repo, "doctor", "--json")
    assert result.exit_code == 2  # SC-004: distinct from 0 and 1
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "execution-error"
    ledger_domain = next(d for d in payload["domains"] if d["domain"] == "ledger")
    assert ledger_domain["severity"] == "execution-error"  # not silently ok / omitted


def test_multi_problem_reports_all_in_one_run(doctor_healthy_repo: Path) -> None:
    # Two independent problems: a too-new ledger AND an unavailable gate command.
    data = yaml.safe_load(_ledger(doctor_healthy_repo).read_text())
    data["schema_version"] = 99
    _ledger(doctor_healthy_repo).write_text(yaml.dump(data))
    write_profiles(doctor_healthy_repo, {
        "output_version": 1,
        "profiles": [{"name": "unit", "command": "no-such-cmd-xyz",
                      "applies": {"always": True}, "timeout": 60}],
    })
    payload = json.loads(_invoke(doctor_healthy_repo, "doctor", "--json").stdout)
    by = {d["domain"]: d["severity"] for d in payload["domains"]}
    assert by["ledger"] == "blocking"          # SC-007: both surfaced
    assert by["gate_availability"] == "warning"
    assert payload["verdict"] == "blocking"    # most severe wins


def test_active_feature_scope_ignores_other_features(doctor_healthy_repo: Path) -> None:
    write_second_feature(doctor_healthy_repo, schema_version=99)  # FR-012a
    result = _invoke(doctor_healthy_repo, "doctor", "--json")
    assert result.exit_code == 0
    assert "002-other" not in result.stdout


def test_every_non_ok_finding_carries_next_action(doctor_healthy_repo: Path) -> None:
    data = yaml.safe_load(_ledger(doctor_healthy_repo).read_text())
    data["schema_version"] = 5  # migratable → warning
    _ledger(doctor_healthy_repo).write_text(yaml.dump(data))
    payload = json.loads(_invoke(doctor_healthy_repo, "doctor", "--json").stdout)
    for domain in payload["domains"]:
        for finding in domain["findings"]:
            if finding["severity"] != "ok":
                assert finding["next_action_code"] != "none"  # SC-006
                assert finding["next_action"]
