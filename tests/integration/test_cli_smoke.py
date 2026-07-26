"""Subprocess smoke set (Feature 018 US4, T030, SC-005).

The bulk of the integration suite now invokes the CLI in-process (Typer CliRunner) for
speed. This small set is the deliberate exception: one invocation per command family
that spawns the **real** ``specops`` binary, so true process exit codes, stdout/stderr
stream separation, and console encoding stay covered — the Windows-class regressions
this project has shipped fixes for live exactly here. Marked ``@pytest.mark.subprocess``
so it can be selected (``pytest -m subprocess``) or excluded.

Fixtures and the subprocess runner are reused from the golden-capture harness.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.golden import harness

pytestmark = pytest.mark.subprocess


def _run(build, args, tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    harness.init_repo(root)
    build(root)
    return harness.run_specops(root, tuple(args))


@pytest.mark.parametrize("build, args", [
    (harness.build_context_valid, ["context", "validate"]),
    (harness.build_trace_classify, ["trace", "classify", "--json"]),
    (harness.build_handoff_report_clean, ["handoff", "report", "--json"]),
    (harness.build_gate, ["gate", "list", "--json"]),
    (harness.build_report, ["report", "--json"]),
    (harness.build_status_show, ["status", "show"]),
], ids=["context", "trace", "handoff", "gate", "report", "status"])
def test_family_smoke(build, args, tmp_path: Path) -> None:
    """Each family exits 0 on the happy path and produces real stdout."""
    proc = _run(build, args, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip()


def test_lane_smoke(tmp_path: Path) -> None:
    proc = _run(
        harness.build_lane,
        ["lane", "start", "--answers", "small,reversible,no-high-risk-category", "--json"],
        tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"output_version"' in proc.stdout  # the Feature 018 lane envelope, over the wire


def test_stream_separation_and_exit_code_on_error(tmp_path: Path) -> None:
    """A corrupt ledger writes its diagnostic to stderr (not stdout) and exits 2 — the
    real stream separation + exit-code fidelity the in-process runner cannot verify."""
    proc = _run(harness.build_reconcile_corrupt, ["reconcile"], tmp_path)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "Cannot parse ledger" in proc.stderr
