"""Integration tests: default-profile synthesis + gate CLI (Feature 012, US1, T007).

Covers FR-005 / SC-006: no config (or empty list) synthesizes the lint/test default;
`gate list`/`gate validate` exit 0 in the no-config state; the `test` gate is always
present (empty test_command still yields the gate, resolved downstream).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from specops import gateprofiles
from specops.cli import app
from tests.conftest import write_profiles

runner = CliRunner()


def _run(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, ["gate", *args])
    finally:
        os.chdir(cwd)


def _write_config(root: Path, **kv) -> None:
    (root / "specops.json").write_text(json.dumps(kv))


def test_default_profile_from_test_command(context_map_repo: Path) -> None:
    _write_config(context_map_repo, test_command="pytest", lint_command="")
    gates = gateprofiles.default_profile(context_map_repo)
    names = [g.name for g in gates]
    assert names == ["test"]  # lint omitted when lint_command empty
    assert gates[0].required and gates[0].applies.always


def test_default_profile_includes_lint_when_set(context_map_repo: Path) -> None:
    _write_config(context_map_repo, test_command="pytest", lint_command="ruff check .")
    gates = gateprofiles.default_profile(context_map_repo)
    assert [g.name for g in gates] == ["lint", "test"]  # declared order lint→test


def test_empty_profiles_list_falls_back_to_default(context_map_repo: Path) -> None:
    _write_config(context_map_repo, test_command="pytest")
    write_profiles(context_map_repo, {"output_version": 1, "profiles": []})
    gates = gateprofiles.profiles_for(context_map_repo)
    assert [g.name for g in gates] == ["test"]  # never zero gates (FR-005)


def test_cli_gate_list_no_config_exit_zero(context_map_repo: Path) -> None:
    _write_config(context_map_repo, test_command="pytest")
    result = _run(context_map_repo, "list", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["default_profile"] is True
    assert payload["output_version"] == gateprofiles.OUTPUT_VERSION
    assert any(row["name"] == "test" for row in payload["selection"])


def test_cli_gate_validate_no_config_exit_zero(context_map_repo: Path) -> None:
    _write_config(context_map_repo, test_command="pytest")
    result = _run(context_map_repo, "validate", "--json")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == gateprofiles.S_NO_CONFIG


def test_cli_gate_validate_defect_exit_one(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [{"name": "a", "command": ""}]})
    result = _run(context_map_repo, "validate")
    assert result.exit_code == 1
