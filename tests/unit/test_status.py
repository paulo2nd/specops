"""Unit tests for status.py — phase machine, task transitions, evidence validation."""
import datetime
import subprocess
from pathlib import Path
from typing import Optional

import pytest
import yaml

from specops import status as s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ledger(tmp_path: Path, phase: str = "SPECIFY", tasks: Optional[list] = None) -> dict:
    data = {
        "feature": "001-test",
        "branch": "main",
        "baseline": "abc1234",
        "created_at": str(datetime.date.today()),
        "updated_at": str(datetime.date.today()),
        "current_phase": phase,
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": tasks or [],
        "review_cycles": [],
    }
    ledger = tmp_path / "status.yaml"
    ledger.write_text(yaml.dump(data))
    return data


def _task(id: str, status: str = "PENDING", started: Optional[str] = None,
          commits: Optional[list] = None, evidence: Optional[str] = None) -> dict:
    return {
        "id": id,
        "status": status,
        "started_commit": started,
        "commits": commits or [],
        "evidence": evidence,
        "completed_at": None,
    }


# ---------------------------------------------------------------------------
# _validate_evidence
# ---------------------------------------------------------------------------

def test_evidence_valid_single() -> None:
    assert s._validate_evidence("TEST_REPORT:all tests passed")


def test_evidence_valid_multiple() -> None:
    assert s._validate_evidence("TEST_REPORT:42 ok; CODE_DIFF:3 files")


def test_evidence_invalid_class() -> None:
    assert not s._validate_evidence("BAD_CLASS:something")


def test_evidence_invalid_no_colon() -> None:
    assert not s._validate_evidence("no colon here")


def test_evidence_empty_string() -> None:
    assert not s._validate_evidence("")


# ---------------------------------------------------------------------------
# _sync_tasks
# ---------------------------------------------------------------------------

def test_sync_adds_new_task() -> None:
    data = {"tasks": []}
    s._sync_tasks(data, "- [ ] T001 Do something\n")
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["id"] == "T001"
    assert data["tasks"][0]["status"] == "PENDING"


def test_sync_preserves_existing_task_state() -> None:
    data = {"tasks": [_task("T001", "DONE", evidence="CLI_LOG:ok")]}
    s._sync_tasks(data, "- [ ] T001 Do something\n- [ ] T002 Another\n")
    by_id = {t["id"]: t for t in data["tasks"]}
    assert by_id["T001"]["status"] == "DONE"
    assert by_id["T002"]["status"] == "PENDING"


def test_sync_marks_vanished_as_orphaned() -> None:
    data = {"tasks": [_task("T001", "DONE")]}
    s._sync_tasks(data, "- [ ] T002 New task\n")
    by_id = {t["id"]: t for t in data["tasks"]}
    assert by_id["T001"].get("orphaned") is True
    assert by_id["T002"]["status"] == "PENDING"


def test_sync_idempotent() -> None:
    text = "- [ ] T001 task\n"
    data = {"tasks": []}
    s._sync_tasks(data, text)
    before = list(data["tasks"])
    s._sync_tasks(data, text)
    assert data["tasks"] == before


# ---------------------------------------------------------------------------
# Phase machine (transition validation)
# ---------------------------------------------------------------------------
# We test the state machine logic directly by calling cmd_transition_phase
# with a properly set up tmp directory.

def _setup_feature(tmp_path: Path, phase: str = "SPECIFY") -> tuple[Path, Path]:
    """Return (root, feature_dir) with a minimal Speckit + ledger in *phase*."""
    import json
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True, capture_output=True)
    (root / "README.md").write_text("# test")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-test"})
    )
    feature_dir = root / "specs" / "001-test"
    feature_dir.mkdir(parents=True)

    _make_ledger(feature_dir, phase=phase)
    return root, feature_dir


def test_phase_specify_to_plan(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "SPECIFY")
    with pytest.raises(SystemExit) as exc:
        s.cmd_transition_phase(root, "PLAN", result=None)
    assert exc.value.code == 0


def test_phase_skip_raises(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "SPECIFY")
    with pytest.raises(SystemExit) as exc:
        s.cmd_transition_phase(root, "REVIEW", result=None)
    assert exc.value.code == 1


def test_phase_review_to_implement_rejected(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    # Add an open review cycle
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [{"round": 1, "started_at": "2026-07-05", "completed_at": None, "result": None}]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SystemExit) as exc:
        s.cmd_transition_phase(root, "IMPLEMENT", result="REJECTED")
    assert exc.value.code == 0
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["current_phase"] == "IMPLEMENT"
    assert data["review_cycles"][0]["result"] == "REJECTED"


def test_phase_review_to_implement_without_rejected_fails(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "REVIEW")
    with pytest.raises(SystemExit) as exc:
        s.cmd_transition_phase(root, "IMPLEMENT", result=None)
    assert exc.value.code == 1


def test_phase_done_requires_approved(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [{"round": 1, "started_at": "2026-07-05", "completed_at": "2026-07-05", "result": "REJECTED"}]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    with pytest.raises(SystemExit) as exc:
        s.cmd_transition_phase(root, "DONE", result=None)
    assert exc.value.code == 1


def test_phase_done_with_approved_succeeds(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [{"round": 1, "started_at": "2026-07-05", "completed_at": "2026-07-05", "result": "APPROVED"}]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    with pytest.raises(SystemExit) as exc:
        s.cmd_transition_phase(root, "DONE", result=None)
    assert exc.value.code == 0


def test_corrective_round_increments_review_cycle(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [{"round": 1, "started_at": "2026-07-05", "completed_at": None, "result": None}]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SystemExit):
        s.cmd_transition_phase(root, "IMPLEMENT", result="REJECTED")

    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    # Old cycle closed, new placeholder added
    assert len(data["review_cycles"]) == 2
    assert data["review_cycles"][0]["result"] == "REJECTED"
    assert data["review_cycles"][1]["round"] == 2


# ---------------------------------------------------------------------------
# Task transitions
# ---------------------------------------------------------------------------

def test_start_task_sets_in_progress(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001 Do something\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = [_task("T001")]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SystemExit) as exc:
        s.cmd_start_task(root, "T001")
    assert exc.value.code == 0

    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    t = next(t for t in data["tasks"] if t["id"] == "T001")
    assert t["status"] == "IN_PROGRESS"
    assert data["recovery"]["active_task"] == "T001"


def test_start_task_blocks_when_another_active(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001\n- [ ] T002\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = [_task("T001", "IN_PROGRESS", started="abc"), _task("T002")]
    data["recovery"]["active_task"] = "T001"
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SystemExit) as exc:
        s.cmd_start_task(root, "T002")
    assert exc.value.code == 1


def test_start_task_done_fails(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = [_task("T001", "DONE")]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SystemExit) as exc:
        s.cmd_start_task(root, "T001")
    assert exc.value.code == 1


def test_complete_task_requires_evidence_source(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path)
    with pytest.raises(SystemExit) as exc:
        s.cmd_complete_task(root, "T001", auto=False, evidence=None)
    assert exc.value.code == 1


def test_complete_task_manual_evidence_valid(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    import subprocess as sp
    result = sp.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    head = result.stdout.strip()
    data["tasks"] = [_task("T001", "IN_PROGRESS", started=head)]
    data["recovery"]["active_task"] = "T001"
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SystemExit) as exc:
        s.cmd_complete_task(root, "T001", auto=False, evidence="CLI_LOG:manual ok")
    assert exc.value.code == 0

    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    t = next(t for t in data["tasks"] if t["id"] == "T001")
    assert t["status"] == "DONE"
    assert t["evidence"] == "CLI_LOG:manual ok"


def test_complete_task_invalid_evidence_class_fails(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = [_task("T001", "IN_PROGRESS", started="abc")]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SystemExit) as exc:
        s.cmd_complete_task(root, "T001", auto=False, evidence="BAD_CLASS:something")
    assert exc.value.code == 1


def test_orphan_flagging_preserved(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T002\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = [_task("T001", "DONE"), _task("T002")]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SystemExit):
        s.cmd_start_task(root, "T002")

    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    by_id = {t["id"]: t for t in data["tasks"]}
    assert by_id["T001"].get("orphaned") is True
