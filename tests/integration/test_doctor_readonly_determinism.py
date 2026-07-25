"""Read-only + determinism sweep for `specops doctor` / `specops report` (Feature 014).

Covers SC-003 (byte-for-byte unchanged) and SC-005 (byte-identical output), plus the
FR-017 no-side-effect guarantee (offline, no telemetry, no auto-repair): no new files.
"""
from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from specops.cli import app
from tests.conftest import snapshot_tree

runner = CliRunner()


def _invoke(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, list(args))
    finally:
        os.chdir(cwd)


def test_doctor_is_read_only_and_deterministic(doctor_healthy_repo: Path) -> None:
    before = snapshot_tree(doctor_healthy_repo)
    out1 = _invoke(doctor_healthy_repo, "doctor", "--json").stdout
    out2 = _invoke(doctor_healthy_repo, "doctor", "--json").stdout
    after = snapshot_tree(doctor_healthy_repo)
    assert before == after          # SC-003 / FR-017: no file created or mutated
    assert out1 == out2             # SC-005: byte-identical


def test_report_is_read_only_and_deterministic(doctor_healthy_repo: Path) -> None:
    before = snapshot_tree(doctor_healthy_repo)
    out1 = _invoke(doctor_healthy_repo, "report", "--json").stdout
    out2 = _invoke(doctor_healthy_repo, "report", "--json").stdout
    after = snapshot_tree(doctor_healthy_repo)
    assert before == after
    assert out1 == out2


def test_doctor_creates_no_files(doctor_healthy_repo: Path) -> None:
    before = set(snapshot_tree(doctor_healthy_repo))
    _invoke(doctor_healthy_repo, "doctor")
    _invoke(doctor_healthy_repo, "doctor", "--json")
    after = set(snapshot_tree(doctor_healthy_repo))
    assert before == after  # FR-017: no telemetry file, no cache, no repair artifact
