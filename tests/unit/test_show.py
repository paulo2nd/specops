"""Unit tests for status show rendering [SC-002]."""
from pathlib import Path

import pytest
import yaml

from specops import status as s


def _write_ledger(feature_dir: Path, data: dict) -> None:
    (feature_dir / "status.yaml").write_text(yaml.dump(data), encoding="utf-8")


def _populated_ledger(feature_dir: Path) -> dict:
    data = {
        "feature": "002-cli-hardening-dx",
        "branch": "main",
        "current_phase": "REVIEW",
        "baseline": "abc1234",
        "created_at": "2026-07-05",
        "updated_at": "2026-07-05",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [
            {"id": "T001", "status": "DONE", "evidence": "CLI_LOG:ok", "completed_at": "2026-07-05",
             "started_commit": None, "commits": []},
            {"id": "T002", "status": "IN_PROGRESS", "evidence": None, "completed_at": None,
             "started_commit": None, "commits": []},
            {"id": "T003", "status": "PENDING", "evidence": None, "completed_at": None,
             "started_commit": None, "commits": []},
            {"id": "T099", "status": "DONE", "evidence": "CLI_LOG:old",
             "completed_at": "2026-07-05", "started_commit": None, "commits": [], "orphaned": True},
        ],
        "review_cycles": [
            {"round": 1, "started_at": "2026-07-05", "completed_at": "2026-07-05",
             "result": "REJECTED"},
            {"round": 2, "started_at": None, "completed_at": None, "result": None},
        ],
    }
    _write_ledger(feature_dir, data)
    return data


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    import json
    import subprocess
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=root, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True, capture_output=True)
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/002-test"})
    )
    feature_dir = root / "specs" / "002-test"
    feature_dir.mkdir(parents=True)
    return root, feature_dir


def test_show_populated_ledger(tmp_path: Path) -> None:
    root, feature_dir = _setup(tmp_path)
    _populated_ledger(feature_dir)
    output = s.cmd_show(root)
    assert "feature: 002-cli-hardening-dx" in output
    assert "branch: main" in output
    assert "phase: REVIEW" in output
    assert "active task: T002" in output
    assert "4 total" in output
    assert "1 pending" in output
    assert "1 in progress" in output
    assert "1 done" in output
    assert "1 orphaned" in output
    assert "review cycles: 2" in output
    assert "round 1: REJECTED" in output
    assert "round 2: open" in output


def test_show_legacy_ledger_no_review_cycles(tmp_path: Path) -> None:
    """Legacy ledger without review_cycles renders zero counts without crashing."""
    root, feature_dir = _setup(tmp_path)
    data = {
        "feature": "legacy",
        "branch": "dev",
        "current_phase": "IMPLEMENT",
        "baseline": "abc",
        "created_at": "2026-01-01",
        "updated_at": "2026-01-01",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
    }
    _write_ledger(feature_dir, data)
    output = s.cmd_show(root)
    assert "phase: IMPLEMENT" in output
    assert "0 total" in output
    assert "review cycles: 0" in output


def test_show_active_task_none_when_all_pending(tmp_path: Path) -> None:
    root, feature_dir = _setup(tmp_path)
    data = {
        "feature": "test",
        "branch": "main",
        "current_phase": "TASKS",
        "baseline": "abc",
        "created_at": "2026-07-05",
        "updated_at": "2026-07-05",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [
            {"id": "T001", "status": "PENDING", "evidence": None, "completed_at": None,
             "started_commit": None, "commits": []},
        ],
        "review_cycles": [],
    }
    _write_ledger(feature_dir, data)
    output = s.cmd_show(root)
    assert "active task: none" in output


def test_show_is_readonly(tmp_path: Path) -> None:
    """status show must not modify the ledger file."""
    root, feature_dir = _setup(tmp_path)
    _populated_ledger(feature_dir)
    before = (feature_dir / "status.yaml").read_bytes()
    s.cmd_show(root)
    after = (feature_dir / "status.yaml").read_bytes()
    assert before == after


def test_show_missing_ledger_raises_specops_error(tmp_path: Path) -> None:
    """Missing ledger raises SpecopsError (not-found)."""
    from specops.errors import SpecopsError
    root, feature_dir = _setup(tmp_path)
    with pytest.raises(SpecopsError, match="Ledger not found"):
        s.cmd_show(root)
