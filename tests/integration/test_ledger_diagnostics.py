"""Ledger diagnostic convergence (Feature 018 US3, T020, SC-004).

``status show``, ``report``, and ``reconcile`` all load the ledger through the single
``ledger.load_raw`` authority, so a corrupted ledger yields the *identical* diagnostic
and exit code 2 from all three (retiring reconcile's legacy "Cannot parse ledger"
wording). A non-mapping task entry renders (filtered) instead of crashing in both
``status show`` and ``report``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from specops import ledger
from specops.cli import app
from specops.errors import LedgerParseError

runner = CliRunner()


def _invoke(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, list(args))
    finally:
        os.chdir(cwd)


def test_corrupt_ledger_converges_across_commands(doctor_healthy_repo: Path) -> None:
    root = doctor_healthy_repo
    (root / "specs" / "001-demo" / "status.yaml").write_text(":\n  - [broken")

    # The canonical diagnostic from the single loading authority.
    with pytest.raises(LedgerParseError) as excinfo:
        ledger.load_raw(root / "specs" / "001-demo")
    canonical = excinfo.value.message

    show = _invoke(root, "status", "show")
    report = _invoke(root, "report", "--json")
    rec = _invoke(root, "reconcile")

    assert show.exit_code == 2, show.output
    assert report.exit_code == 2, report.output
    assert rec.exit_code == 2, rec.output
    # Identical load_raw diagnostic surfaced by all three (SC-004). show/reconcile
    # print it as human text; report --json carries it verbatim in its `detail` field.
    assert canonical in show.output
    assert canonical in rec.output
    assert json.loads(report.output)["detail"] == canonical


def test_non_mapping_task_renders_not_crashes(doctor_healthy_repo: Path) -> None:
    root = doctor_healthy_repo
    fd = root / "specs" / "001-demo"
    data = yaml.safe_load((fd / "status.yaml").read_text())
    # A hand-edited ledger with a non-mapping task entry must degrade gracefully.
    data["tasks"] = ["i am not a dict", {"id": "T001", "status": "DONE"}]
    (fd / "status.yaml").write_text(yaml.dump(data))

    show = _invoke(root, "status", "show")
    report = _invoke(root, "report", "--json")

    assert show.exit_code == 0, show.output
    assert report.exit_code == 0, report.output
    assert "feature: 001-demo" in show.output  # rendered, not crashed
