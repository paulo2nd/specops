"""Read-only + determinism sweep for the gate/review surfaces (Feature 012, Polish, T042).

Covers FR-015/FR-017/SC-008: `gate list`/`validate`/`report` and `review` evaluation
leave the ledger + config byte-unchanged and produce byte-identical output for identical
recorded state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from specops.cli import app
from tests.conftest import snapshot_tree, write_profiles
from tests.unit.test_review import _all_pass_setup

runner = CliRunner()


def _invoke(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, list(args))
    finally:
        os.chdir(cwd)


def test_gate_list_and_validate_read_only(context_map_repo: Path) -> None:
    (context_map_repo / "specops.json").write_text(json.dumps({"test_command": "pytest"}))
    write_profiles(context_map_repo, {"output_version": 1, "profiles": [
        {"name": "unit", "command": "pytest", "applies": {"always": True}, "timeout": 60},
    ]})
    before = snapshot_tree(context_map_repo)
    out1 = _invoke(context_map_repo, "gate", "list", "--json").stdout
    _invoke(context_map_repo, "gate", "validate", "--json")
    out2 = _invoke(context_map_repo, "gate", "list", "--json").stdout
    assert snapshot_tree(context_map_repo) == before  # nothing mutated
    assert out1 == out2  # deterministic


def test_review_and_gate_report_read_only(fake_speckit_repo: Path) -> None:
    _all_pass_setup(fake_speckit_repo)
    before = snapshot_tree(fake_speckit_repo)
    r1 = _invoke(fake_speckit_repo, "review", "--json").stdout
    rep1 = _invoke(fake_speckit_repo, "gate", "report", "--json").stdout
    r2 = _invoke(fake_speckit_repo, "review", "--json").stdout
    rep2 = _invoke(fake_speckit_repo, "gate", "report", "--json").stdout
    assert snapshot_tree(fake_speckit_repo) == before  # review + report never mutate state
    assert r1 == r2 and rep1 == rep2  # byte-for-byte deterministic
