"""Unit tests for status.py — phase machine, task transitions, evidence validation."""
import datetime
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from specops import status as s
from specops.errors import SpecopsError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ledger(
    tmp_path: Path,
    phase: str = "SPECIFY",
    tasks: list | None = None,
    baseline: str = "abc1234",
    branch: str = "main",
) -> dict:
    data = {
        "feature": "001-test",
        "branch": branch,
        "baseline": baseline,
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


def _task(id: str, status: str = "PENDING", started: str | None = None,
          commits: list | None = None, evidence: str | None = None) -> dict:
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

def _setup_feature(tmp_path: Path, phase: str = "SPECIFY") -> tuple[Path, Path]:
    """Return (root, feature_dir) with a minimal Speckit + ledger in *phase*."""
    import json
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

    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-test"})
    )
    feature_dir = root / "specs" / "001-test"
    feature_dir.mkdir(parents=True)

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    _make_ledger(feature_dir, phase=phase, baseline=head, branch=branch)
    return root, feature_dir


def test_record_step_appends_skip_decision(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "SPECIFY")
    msg = s.cmd_record_step(root, "clarify", decision="skip")
    assert "clarify" in msg and "skip" in msg
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    steps = data["workflow"]["skipped_steps"]
    assert len(steps) == 1
    assert steps[0]["step"] == "clarify"
    assert steps[0]["decision"] == "skip"
    assert steps[0]["at"]


def test_record_step_replaces_prior_entry_for_same_step(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "SPECIFY")
    s.cmd_record_step(root, "clarify", decision="skip")
    s.cmd_record_step(root, "clarify", decision="run")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    steps = data["workflow"]["skipped_steps"]
    assert len(steps) == 1
    assert steps[0]["decision"] == "run"


def test_record_step_rejects_unknown_step(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "SPECIFY")
    with pytest.raises(SpecopsError, match="Unknown optional step"):
        s.cmd_record_step(root, "implement", decision="skip")


def test_record_step_rejects_bad_decision(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "SPECIFY")
    with pytest.raises(SpecopsError, match="Invalid decision"):
        s.cmd_record_step(root, "clarify", decision="maybe")


def test_phase_specify_to_plan(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "SPECIFY")
    msg = s.cmd_transition_phase(root, "PLAN", result=None)
    assert "SPECIFY" in msg and "PLAN" in msg


# --- T014: idempotent-tolerant transitions (--if-needed, analyze C1) ---

def test_transition_if_needed_same_phase_is_noop(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "PLAN")
    before = (feature_dir / "status.yaml").read_text()
    msg = s.cmd_transition_phase(root, "PLAN", result=None, if_needed=True)
    assert "no-op" in msg
    # Ledger unchanged (no revision bump, no rewrite of content).
    assert (feature_dir / "status.yaml").read_text() == before


def test_transition_if_needed_still_advances_when_behind(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "SPECIFY")
    msg = s.cmd_transition_phase(root, "PLAN", result=None, if_needed=True)
    assert "PLAN" in msg and "no-op" not in msg


def test_transition_same_phase_without_if_needed_still_errors(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "PLAN")
    with pytest.raises(SpecopsError, match="Invalid transition"):
        s.cmd_transition_phase(root, "PLAN", result=None)


def test_phase_skip_raises(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "SPECIFY")
    with pytest.raises(SpecopsError, match="Invalid transition"):
        s.cmd_transition_phase(root, "REVIEW", result=None)


def test_phase_review_to_implement_rejected(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [
        {"round": 1, "started_at": "2026-07-05", "completed_at": None, "result": None}
    ]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    msg = s.cmd_transition_phase(root, "IMPLEMENT", result="REJECTED")
    assert "IMPLEMENT" in msg
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["current_phase"] == "IMPLEMENT"
    assert data["review_cycles"][0]["result"] == "REJECTED"


def test_phase_review_to_implement_without_rejected_fails(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path, "REVIEW")
    with pytest.raises(SpecopsError):
        s.cmd_transition_phase(root, "IMPLEMENT", result=None)


def test_phase_done_requires_approved(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [
        {"round": 1, "started_at": "2026-07-05", "completed_at": "2026-07-05", "result": "REJECTED"}
    ]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    with pytest.raises(SpecopsError, match="Must be APPROVED"):
        s.cmd_transition_phase(root, "DONE", result=None)


def test_phase_done_with_approved_succeeds(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [
        {"round": 1, "started_at": "2026-07-05", "completed_at": "2026-07-05", "result": "APPROVED"}
    ]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    msg = s.cmd_transition_phase(root, "DONE", result=None)
    assert "DONE" in msg


def test_corrective_round_increments_review_cycle(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [
        {"round": 1, "started_at": "2026-07-05", "completed_at": None, "result": None}
    ]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    s.cmd_transition_phase(root, "IMPLEMENT", result="REJECTED")

    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert len(data["review_cycles"]) == 2
    assert data["review_cycles"][0]["result"] == "REJECTED"
    assert data["review_cycles"][1]["round"] == 2


def test_corrective_round_reuses_placeholder_when_review_resumes(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [
        {"round": 1, "started_at": "2026-07-05", "completed_at": None, "result": None}
    ]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    s.cmd_transition_phase(root, "IMPLEMENT", result="REJECTED")
    s.cmd_transition_phase(root, "REVIEW", result=None)

    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert len(data["review_cycles"]) == 2
    assert data["review_cycles"][0]["result"] == "REJECTED"
    assert data["review_cycles"][1]["round"] == 2
    assert data["review_cycles"][1]["started_at"] is not None
    assert data["review_cycles"][1]["completed_at"] is None
    assert data["review_cycles"][1]["result"] is None


# ---------------------------------------------------------------------------
# Task transitions
# ---------------------------------------------------------------------------

def test_start_task_sets_in_progress(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001 Do something\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = [_task("T001")]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    msg = s.cmd_start_task(root, "T001")
    assert "T001" in msg

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

    with pytest.raises(SpecopsError, match="IN_PROGRESS"):
        s.cmd_start_task(root, "T002")


def test_start_task_done_fails(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = [_task("T001", "DONE")]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    with pytest.raises(SpecopsError, match="already DONE"):
        s.cmd_start_task(root, "T001")


def test_complete_task_requires_evidence_source(tmp_path: Path) -> None:
    root, _ = _setup_feature(tmp_path)
    with pytest.raises(SpecopsError, match="evidence source required"):
        s.cmd_complete_task(root, "T001", auto=False, evidence=None)


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

    msg = s.cmd_complete_task(root, "T001", auto=False, evidence="CLI_LOG:manual ok")
    assert "T001" in msg and "completed" in msg

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

    with pytest.raises(SpecopsError, match="Invalid evidence"):
        s.cmd_complete_task(root, "T001", auto=False, evidence="BAD_CLASS:something")


def test_orphan_flagging_preserved(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T002\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["tasks"] = [_task("T001", "DONE"), _task("T002")]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    # T002 starts successfully; T001 is absent from tasks.md so gets orphaned during sync
    s.cmd_start_task(root, "T002")

    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    by_id = {t["id"]: t for t in data["tasks"]}
    assert by_id["T001"].get("orphaned") is True


# ---------------------------------------------------------------------------
# T004 — US1: review result vocabulary and application order [SC-001]
# ---------------------------------------------------------------------------

def _setup_review(tmp_path: Path, extra_cycles: list | None = None) -> tuple[Path, Path]:
    """Return (root, feature_dir) in REVIEW phase with one open review cycle.

    Any *extra_cycles* precede the open cycle; the open cycle's round follows
    them so rounds stay strictly increasing (Ledger v2 review-cycle invariant).
    """
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    base = extra_cycles or []
    open_round = len(base) + 1
    cycles = [
        *base,
        {"round": open_round, "started_at": "2026-07-05", "completed_at": None, "result": None},
    ]
    data["review_cycles"] = cycles
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    return root, feature_dir


def test_done_with_approved_records_and_advances(tmp_path: Path) -> None:
    """(a) DONE -r APPROVED records APPROVED + completed_at and advances phase in one save."""
    root, feature_dir = _setup_review(tmp_path)
    msg = s.cmd_transition_phase(root, "DONE", result="APPROVED")
    assert "DONE" in msg
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["current_phase"] == "DONE"
    cycle = data["review_cycles"][-1]
    assert cycle["result"] == "APPROVED"
    assert cycle["completed_at"] is not None


def test_done_with_rejected_fails_and_ledger_unchanged(tmp_path: Path) -> None:
    """(b) DONE -r REJECTED exits 1, message names the corrective path, ledger unchanged."""
    root, feature_dir = _setup_review(tmp_path)
    original = (feature_dir / "status.yaml").read_text()
    with pytest.raises(SpecopsError, match="IMPLEMENT"):
        s.cmd_transition_phase(root, "DONE", result="REJECTED")
    assert (feature_dir / "status.yaml").read_text() == original


def test_invalid_result_vocabulary_fails_before_ledger_read(tmp_path: Path) -> None:
    """(c) -r 'note ok' exits 1 before any ledger read (invalid vocabulary)."""
    root, feature_dir = _setup_review(tmp_path)
    # Remove ledger to prove we don't even read it
    (feature_dir / "status.yaml").unlink()
    with pytest.raises(SpecopsError, match="Expected APPROVED or REJECTED"):
        s.cmd_transition_phase(root, "DONE", result="note ok")
    assert not (feature_dir / "status.yaml").exists()


def test_done_with_pre_approved_cycle_passes(tmp_path: Path) -> None:
    """(d) DONE with pre-APPROVED cycle still passes (no -r needed)."""
    root, feature_dir = _setup_feature(tmp_path, "REVIEW")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["review_cycles"] = [
        {"round": 1, "started_at": "2026-07-05", "completed_at": "2026-07-05", "result": "APPROVED"}
    ]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    msg = s.cmd_transition_phase(root, "DONE", result=None)
    assert "DONE" in msg


def test_result_applies_to_open_cycle_after_closed_rejected(tmp_path: Path) -> None:
    """(e) result applies to the open placeholder when a closed REJECTED round precedes it."""
    closed = {
        "round": 1, "started_at": "2026-07-05", "completed_at": "2026-07-05", "result": "REJECTED"
    }
    root, feature_dir = _setup_review(tmp_path, extra_cycles=[closed])
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["review_cycles"][0]["result"] == "REJECTED"
    assert data["review_cycles"][1]["result"] is None
    msg = s.cmd_transition_phase(root, "DONE", result="APPROVED")
    assert "DONE" in msg
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert data["review_cycles"][1]["result"] == "APPROVED"
    assert data["current_phase"] == "DONE"


# ---------------------------------------------------------------------------
# T012 — US3: evidence grammar matrix and atomic save [SC-004, SC-005]
# ---------------------------------------------------------------------------

def test_evidence_empty_summary_rejected() -> None:
    """CLI_LOG: with no summary is invalid."""
    assert not s._validate_evidence("CLI_LOG:")


def test_evidence_unknown_class_rejected() -> None:
    """LOG:x is not a known evidence class."""
    assert not s._validate_evidence("LOG:x")


def test_evidence_orphan_segment_rejected() -> None:
    """CLI_LOG:a; done — 'done' is not a valid part."""
    assert not s._validate_evidence("CLI_LOG:a; done")


def test_evidence_missing_colon_rejected() -> None:
    """Missing colon is invalid."""
    assert not s._validate_evidence("CLI_LOG no colon")


def test_evidence_valid_single_part() -> None:
    assert s._validate_evidence("CLI_LOG:run passed")


def test_evidence_valid_multi_part() -> None:
    assert s._validate_evidence("TEST_REPORT:42 ok; CODE_DIFF:3 files in 2 commits")


def test_stale_tmp_ignored_on_read(tmp_path: Path) -> None:
    """A stale status.yaml.tmp must not affect _load_ledger."""
    root, feature_dir = _setup_feature(tmp_path, "SPECIFY")
    (feature_dir / "status.yaml.tmp").write_text("corrupted: [bad yaml: {")
    data = s._load_ledger(feature_dir)
    assert isinstance(data, dict)
    assert data["current_phase"] == "SPECIFY"


# ---------------------------------------------------------------------------
# cmd_init_spec
# ---------------------------------------------------------------------------

def _make_fresh_git_repo(tmp_path: Path) -> tuple[Path, Path]:
    import json as _json
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
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        _json.dumps({"feature_directory": "specs/001-test"})
    )
    feature_dir = root / "specs" / "001-test"
    feature_dir.mkdir(parents=True)
    return root, feature_dir


def test_cmd_init_spec_creates_ledger(tmp_path: Path) -> None:
    root, feature_dir = _make_fresh_git_repo(tmp_path)
    msg = s.cmd_init_spec(root, None)
    assert "Ledger created" in msg
    assert (feature_dir / "status.yaml").is_file()


def test_cmd_init_spec_with_tasks_md(tmp_path: Path) -> None:
    root, feature_dir = _make_fresh_git_repo(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001 first task\n- [ ] T002 second task\n")

    msg = s.cmd_init_spec(root, None)
    assert "Ledger created" in msg
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    task_ids = [t["id"] for t in data["tasks"]]
    assert "T001" in task_ids
    assert "T002" in task_ids


def test_cmd_init_spec_fails_if_ledger_exists(tmp_path: Path) -> None:
    root, feature_dir = _setup_feature(tmp_path, "SPECIFY")
    with pytest.raises(SpecopsError, match="already exists"):
        s.cmd_init_spec(root, None)


def test_cmd_init_spec_name_mismatch_raises(tmp_path: Path) -> None:
    root, _ = _make_fresh_git_repo(tmp_path)
    with pytest.raises(SpecopsError, match="resolves to"):
        s.cmd_init_spec(root, "002-wrong-name")


# ---------------------------------------------------------------------------
# cmd_complete_task --auto path
# ---------------------------------------------------------------------------

def _setup_in_progress(tmp_path: Path) -> tuple[Path, Path]:
    root, feature_dir = _setup_feature(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001 do something\n")
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    data["tasks"] = [{
        "id": "T001", "status": "IN_PROGRESS", "started_commit": head,
        "commits": [], "evidence": None, "completed_at": None,
    }]
    data["recovery"] = {"active_task": "T001", "last_commit": None}
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    return root, feature_dir


def test_complete_task_auto_no_test_command_fails(tmp_path: Path) -> None:
    root, _ = _setup_in_progress(tmp_path)
    import json as _json
    (root / "specops.json").write_text(_json.dumps({"test_command": ""}))
    with pytest.raises(SpecopsError, match="test_command not set"):
        s.cmd_complete_task(root, "T001", auto=True, evidence=None)


def test_complete_task_auto_failing_test_command_raises(tmp_path: Path) -> None:
    root, _ = _setup_in_progress(tmp_path)
    import json as _json
    (root / "specops.json").write_text(_json.dumps({"test_command": "false"}))
    with pytest.raises(SpecopsError, match="test_command failed"):
        s.cmd_complete_task(root, "T001", auto=True, evidence=None)


def test_complete_task_auto_no_commits_raises(tmp_path: Path) -> None:
    root, feature_dir = _setup_in_progress(tmp_path)
    import json as _json
    (root / "specops.json").write_text(_json.dumps({"test_command": "true"}))
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    fake_sha = "deadbeef" * 5
    data["tasks"][0]["started_commit"] = fake_sha
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    with pytest.raises(SpecopsError):
        s.cmd_complete_task(root, "T001", auto=True, evidence=None)


def test_complete_task_auto_success(tmp_path: Path) -> None:
    root, feature_dir = _setup_in_progress(tmp_path)
    import json as _json
    (root / "specops.json").write_text(_json.dumps({"test_command": "true"}))
    (root / "work.txt").write_text("change")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "work"], cwd=root, check=True, capture_output=True)

    msg = s.cmd_complete_task(root, "T001", auto=True, evidence=None)
    assert "T001" in msg
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    t = next(t for t in data["tasks"] if t["id"] == "T001")
    assert t["status"] == "DONE"
    assert "TEST_REPORT" in t["evidence"]


# ---------------------------------------------------------------------------
# read_baseline (004: read-only accessor for the review working-tree gate)
# ---------------------------------------------------------------------------

def test_complete_task_auto_runs_test_command_from_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--auto executes test_command with cwd=root (shared shell runner)."""
    import json as _json
    import sys as _sys
    root, feature_dir = _setup_in_progress(tmp_path)
    probe = (
        f'"{_sys.executable}" -c '
        '"import os, sys; sys.exit(0 if os.path.exists(\'specops.json\') else 7)"'
    )
    (root / "specops.json").write_text(_json.dumps({"test_command": probe}))
    (root / "work.txt").write_text("change")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "work"], cwd=root, check=True, capture_output=True
    )
    monkeypatch.chdir(tmp_path.parent)  # process cwd elsewhere on purpose
    msg = s.cmd_complete_task(root, "T001", auto=True, evidence=None)
    assert "T001" in msg


def test_read_baseline_returns_ledger_value(tmp_path: Path) -> None:
    _make_ledger(tmp_path)
    with patch.object(s, "_get_feature_dir", return_value=tmp_path):
        assert s.read_baseline(Path(".")) == "abc1234"


def test_read_baseline_missing_field_returns_empty(tmp_path: Path) -> None:
    data = _make_ledger(tmp_path)
    del data["baseline"]
    (tmp_path / "status.yaml").write_text(yaml.dump(data))
    with patch.object(s, "_get_feature_dir", return_value=tmp_path):
        assert s.read_baseline(Path(".")) == ""


def test_read_baseline_does_not_mutate_ledger(tmp_path: Path) -> None:
    _make_ledger(tmp_path)
    before = (tmp_path / "status.yaml").read_bytes()
    with patch.object(s, "_get_feature_dir", return_value=tmp_path):
        s.read_baseline(Path("."))
    assert (tmp_path / "status.yaml").read_bytes() == before
