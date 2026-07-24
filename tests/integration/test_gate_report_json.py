"""Integration: `gate report --json` is a stable, versioned contract (Feature 012, US4, T030).

Covers FR-012/SC-009: the report embeds output_version, renders gates + evidence, and
is byte-for-byte identical for identical recorded state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from specops import gateprofiles
from specops.cli import app
from tests.unit.test_review import _all_pass_setup

runner = CliRunner()


def _run(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, ["gate", "report", *args])
    finally:
        os.chdir(cwd)


def test_gate_report_json_has_output_version(fake_speckit_repo: Path) -> None:
    _all_pass_setup(fake_speckit_repo)
    result = _run(fake_speckit_repo, "--json")
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["output_version"] == gateprofiles.OUTPUT_VERSION
    assert payload["command"] == "gate-report"
    assert "gates" in payload and "evidence" in payload
    assert any(g["name"] == "reconcile" for g in payload["gates"])


def test_gate_report_json_deterministic(fake_speckit_repo: Path) -> None:
    _all_pass_setup(fake_speckit_repo)
    first = _run(fake_speckit_repo, "--json").stdout
    second = _run(fake_speckit_repo, "--json").stdout
    assert first == second  # byte-for-byte identical for identical recorded state
