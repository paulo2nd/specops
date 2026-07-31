"""Feature 022 US2: pre-ledger decision buffering in `record-step` (FR-006/FR-007).

The buffer (`specs/<feature>/.specops-pending-steps.json`) makes decision
recording work before the ledger exists; `init-spec` drains it into
`workflow.skipped_steps` and deletes it. `--if-absent` makes skip derivation a
single idempotent command that never overwrites an explicit decision
(remediation U1). Abandoned-run buffers are inert and discarded with the
feature directory (clarification Q4).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from specops import status as s
from specops.errors import SpecopsError
from tests.conftest import git, make_v1_ledger

BUFFER_NAME = ".specops-pending-steps.json"


def _setup_repo(tmp_path: Path, *, ledger: bool = False) -> tuple[Path, Path]:
    """Return (root, feature_dir) with git + feature.json; optionally a ledger."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "t@t.com")
    git(root, "config", "user.name", "T")
    (root / "README.md").write_text("# test")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "init")

    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-test"})
    )
    feature_dir = root / "specs" / "001-test"
    feature_dir.mkdir(parents=True)
    if ledger:
        head = git(root, "rev-parse", "HEAD")
        branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
        make_v1_ledger(
            feature_dir, feature="001-test", phase="SPECIFY", baseline=head, branch=branch
        )
    return root, feature_dir


def _read_buffer(feature_dir: Path) -> dict:
    return json.loads((feature_dir / BUFFER_NAME).read_text(encoding="utf-8"))


# --- pre-ledger buffering ----------------------------------------------------

def test_pre_ledger_record_buffers_instead_of_failing(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path)
    msg = s.cmd_record_step(root, "clarify", decision="run")
    assert "buffer" in msg.lower()
    assert not (feature_dir / "status.yaml").exists()  # no ledger was conjured
    buf = _read_buffer(feature_dir)
    assert buf["version"] == 1
    (entry,) = buf["steps"]
    assert entry["step"] == "clarify"
    assert entry["decision"] == "run"
    assert entry["at"]


def test_pre_ledger_rerecord_replaces_by_step(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path)
    s.cmd_record_step(root, "clarify", decision="skip")
    s.cmd_record_step(root, "clarify", decision="run")
    s.cmd_record_step(root, "checklist", decision="skip")
    buf = _read_buffer(feature_dir)
    by_step = {e["step"]: e["decision"] for e in buf["steps"]}
    assert by_step == {"clarify": "run", "checklist": "skip"}
    assert len(buf["steps"]) == 2  # no duplicates


def test_pre_ledger_still_rejects_unknown_step_and_decision(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path)
    with pytest.raises(SpecopsError, match="Unknown optional step"):
        s.cmd_record_step(root, "implement", decision="skip")
    with pytest.raises(SpecopsError, match="Invalid decision"):
        s.cmd_record_step(root, "clarify", decision="maybe")
    assert not (feature_dir / BUFFER_NAME).exists()  # invalid input buffers nothing


# --- drain at init-spec ------------------------------------------------------

def test_init_spec_drains_buffer_into_ledger_and_deletes_it(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path)
    s.cmd_record_step(root, "clarify", decision="run")
    s.cmd_record_step(root, "checklist", decision="skip")
    s.cmd_init_spec(root, None)
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    by_step = {e["step"]: e["decision"] for e in data["workflow"]["skipped_steps"]}
    assert by_step == {"clarify": "run", "checklist": "skip"}
    assert not (feature_dir / BUFFER_NAME).exists()  # drained → deleted


def test_unknown_buffer_version_discarded_with_note_never_fatal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    root, feature_dir = _setup_repo(tmp_path)
    (feature_dir / BUFFER_NAME).write_text(
        json.dumps({"version": 99, "steps": [{"step": "clarify", "decision": "run"}]})
    )
    msg = s.cmd_init_spec(root, None)  # must not raise
    assert "Ledger created" in msg
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["workflow"]["skipped_steps"] == []  # nothing drained
    assert not (feature_dir / BUFFER_NAME).exists()  # discarded
    assert "pending-steps" in capsys.readouterr().err  # stderr note


def test_corrupt_buffer_discarded_with_note_never_fatal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    root, feature_dir = _setup_repo(tmp_path)
    (feature_dir / BUFFER_NAME).write_text("{not json")
    msg = s.cmd_init_spec(root, None)
    assert "Ledger created" in msg
    assert not (feature_dir / BUFFER_NAME).exists()
    assert "pending-steps" in capsys.readouterr().err


def test_stale_buffer_of_abandoned_feature_is_inert(tmp_path: Path) -> None:
    """Clarification Q4: an abandoned run's buffer blocks nothing and never
    contaminates another feature."""
    root, old_dir = _setup_repo(tmp_path)
    s.cmd_record_step(root, "clarify", decision="run")  # buffered, run abandoned
    # A fresh feature becomes active; the stale buffer stays untouched and inert.
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/002-fresh"})
    )
    fresh_dir = root / "specs" / "002-fresh"
    fresh_dir.mkdir(parents=True)
    s.cmd_record_step(root, "checklist", decision="skip")
    s.cmd_init_spec(root, None)
    data = yaml.safe_load((fresh_dir / "status.yaml").read_text())
    by_step = {e["step"]: e["decision"] for e in data["workflow"]["skipped_steps"]}
    assert by_step == {"checklist": "skip"}  # nothing leaked from the stale buffer
    assert _read_buffer(old_dir)["steps"][0]["step"] == "clarify"  # inert, intact


# --- ledger-present path unchanged ------------------------------------------

def test_ledger_present_records_directly_no_buffer(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path, ledger=True)
    msg = s.cmd_record_step(root, "analyze", decision="run")
    assert "buffer" not in msg.lower()
    assert not (feature_dir / BUFFER_NAME).exists()
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["workflow"]["skipped_steps"][0]["step"] == "analyze"


def test_converge_is_an_accepted_step_value(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path, ledger=True)
    s.cmd_record_step(root, "converge", decision="skip")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    (entry,) = data["workflow"]["skipped_steps"]
    assert entry["step"] == "converge"
    assert entry["decision"] == "skip"


# --- --if-absent (remediation U1) -------------------------------------------

def test_if_absent_records_when_no_decision_exists(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path, ledger=True)
    msg = s.cmd_record_step(root, "analyze", decision="skip", if_absent=True)
    assert "skip" in msg
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["workflow"]["skipped_steps"][0]["decision"] == "skip"


def test_if_absent_never_overwrites_explicit_run_in_ledger(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path, ledger=True)
    s.cmd_record_step(root, "clarify", decision="run")
    before = (feature_dir / "status.yaml").read_bytes()
    msg = s.cmd_record_step(root, "clarify", decision="skip", if_absent=True)
    assert "already" in msg.lower() and "run" in msg
    assert (feature_dir / "status.yaml").read_bytes() == before  # reported no-op


def test_if_absent_respects_buffered_decision_pre_ledger(tmp_path: Path) -> None:
    root, feature_dir = _setup_repo(tmp_path)
    s.cmd_record_step(root, "clarify", decision="run")
    s.cmd_record_step(root, "clarify", decision="skip", if_absent=True)
    buf = _read_buffer(feature_dir)
    (entry,) = [e for e in buf["steps"] if e["step"] == "clarify"]
    assert entry["decision"] == "run"  # the explicit run survived


# --- CLI flag wiring ---------------------------------------------------------

def test_cli_exposes_if_absent_flag(tmp_path: Path) -> None:
    from unittest.mock import patch

    from typer.testing import CliRunner

    from specops.cli import app

    root, feature_dir = _setup_repo(tmp_path, ledger=True)
    runner = CliRunner()
    with patch("specops.cli.Path", return_value=root):
        first = runner.invoke(
            app, ["status", "record-step", "clarify", "--decision", "run"]
        )
        second = runner.invoke(
            app,
            ["status", "record-step", "clarify", "--decision", "skip", "--if-absent"],
        )
    assert first.exit_code == 0
    assert second.exit_code == 0  # no-op is a success, never a gate (FR-008)
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["workflow"]["skipped_steps"][0]["decision"] == "run"
