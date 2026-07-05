"""Unit tests for reconcile.py — validation logic."""
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from specops import reconcile
from specops.errors import LedgerParseError, SpecopsError


def _setup(tmp_path: Path, tasks: list) -> tuple[Path, Path]:
    """Return (root, feature_dir) with a git repo and a ledger containing *tasks*."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=root, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True, capture_output=True)
    (root / "README.md").write_text("# test")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    ).stdout.strip()

    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-test"})
    )
    feature_dir = root / "specs" / "001-test"
    feature_dir.mkdir(parents=True)

    data = {
        "feature": "001-test",
        "branch": "main",
        "baseline": head,
        "current_phase": "IMPLEMENT",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": tasks,
        "review_cycles": [],
    }
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    return root, feature_dir


def test_reconcile_clean_ledger_passes(tmp_path: Path) -> None:
    root, _ = _setup(tmp_path, [])
    warnings, violations = reconcile.run(root)
    assert violations == []


def test_reconcile_done_task_with_real_commit_passes(tmp_path: Path) -> None:
    root, feature_dir = _setup(tmp_path, [])
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    tasks = [{"id": "T001", "status": "DONE", "started_commit": head, "commits": [head],
              "evidence": "CLI_LOG:ok", "completed_at": "2026-07-05"}]
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = tasks
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    warnings, violations = reconcile.run(root)
    assert violations == []


def test_reconcile_fake_commit_fails(tmp_path: Path) -> None:
    root, feature_dir = _setup(tmp_path, [])
    fake = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    tasks = [{"id": "T001", "status": "DONE", "started_commit": fake, "commits": [fake],
              "evidence": "CLI_LOG:ok", "completed_at": "2026-07-05"}]
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = tasks
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    warnings, violations = reconcile.run(root)
    assert any("not in branch history" in v for v in violations)


def test_reconcile_human_marker_exempt(tmp_path: Path) -> None:
    root, feature_dir = _setup(tmp_path, [])
    tasks = [{"id": "T001", "status": "DONE", "started_commit": "(human)", "commits": ["(human)"],
              "evidence": "CLI_LOG:human committed", "completed_at": "2026-07-05"}]
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = tasks
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    warnings, violations = reconcile.run(root)
    assert violations == []


def test_reconcile_done_without_evidence_fails(tmp_path: Path) -> None:
    root, feature_dir = _setup(tmp_path, [])
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    tasks = [{"id": "T001", "status": "DONE", "started_commit": head, "commits": [head],
              "evidence": None, "completed_at": "2026-07-05"}]
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = tasks
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    warnings, violations = reconcile.run(root)
    assert any("no evidence" in v for v in violations)


def test_reconcile_done_without_commits_but_with_evidence_passes(tmp_path: Path) -> None:
    """L1 relaxed: DONE + evidence + empty commits[] → valid (intermediate US task)."""
    root, feature_dir = _setup(tmp_path, [])
    tasks = [{"id": "T001", "status": "DONE", "started_commit": None, "commits": [],
              "evidence": "CLI_LOG:intermediate task done", "completed_at": "2026-07-05"}]
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = tasks
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    warnings, violations = reconcile.run(root)
    assert violations == []


def test_reconcile_orphaned_task_reported(tmp_path: Path) -> None:
    root, feature_dir = _setup(tmp_path, [])
    tasks = [{"id": "T099", "status": "DONE", "commits": [], "evidence": "CLI_LOG:ok",
              "completed_at": "2026-07-05", "orphaned": True}]
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = tasks
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    warnings, violations = reconcile.run(root)
    assert any("orphaned" in w for w in warnings)


def test_reconcile_missing_feature_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(SpecopsError):
        reconcile.run(tmp_path)


def test_reconcile_corrupt_ledger_raises(tmp_path: Path) -> None:
    root, feature_dir = _setup(tmp_path, [])
    (feature_dir / "status.yaml").write_text("bad: [yaml: {")
    with pytest.raises(LedgerParseError):
        reconcile.run(root)
