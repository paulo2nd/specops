"""Feature 019 US2: characterization tests pinning every reachable failure-path
message of ``cmd_transition_phase`` / ``cmd_complete_task`` BEFORE decomposition
(FR-003/FR-004, SC-001) — the byte-identical harness for the D3 refactor.

Deliberately message-exact: any wording drift during the decomposition is a
defect. The ``elif target == "DONE"`` twin gate (pre-refactor status.py:711-721)
is statically dead — sequence validation only admits ``target=DONE`` from
REVIEW, which the first branch captures — so no non-REVIEW DONE characterization
exists here (see specs/019-api-state-robustness/tasks.md T008).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from specops import ledger, status
from specops.errors import SpecopsError
from tests.conftest import git, make_cycle, make_finding, make_trace_ledger


def _feature_repo(
    root: Path,
    *,
    phase: str,
    tasks: list | None = None,
    review_cycles: list | None = None,
    tasks_md: str | None = None,
) -> Path:
    """Position a current-schema ledger at *phase* in a real git repo."""
    (root / ".specify").mkdir(exist_ok=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )
    feature_dir = root / "specs" / "001-demo"
    feature_dir.mkdir(parents=True, exist_ok=True)
    led = make_trace_ledger(
        feature="001-demo",
        branch=git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        baseline=git(root, "rev-parse", "HEAD"),
        phase=phase,
        tasks=tasks,
        review_cycles=review_cycles,
    )
    led["schema_version"] = ledger.CURRENT_SCHEMA
    (feature_dir / "status.yaml").write_text(yaml.dump(led))
    if tasks_md is not None:
        (feature_dir / "tasks.md").write_text(tasks_md)
    return feature_dir


# ---------------------------------------------------------------------------
# cmd_transition_phase
# ---------------------------------------------------------------------------


def test_invalid_result_vocabulary(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="REVIEW")
    with pytest.raises(SpecopsError) as exc:
        status.cmd_transition_phase(tmp_git_repo, "DONE", result="MAYBE")
    assert str(exc.value) == "Invalid result 'MAYBE'. Expected APPROVED or REJECTED."


def test_unknown_phase(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="SPECIFY")
    with pytest.raises(SpecopsError) as exc:
        status.cmd_transition_phase(tmp_git_repo, "WAT", result=None)
    assert str(exc.value) == (
        "Unknown phase 'WAT'. Valid phases: SPECIFY, PLAN, TASKS, IMPLEMENT, REVIEW, DONE."
    )


def test_invalid_sequence_skipping_a_phase(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="SPECIFY")
    with pytest.raises(SpecopsError) as exc:
        status.cmd_transition_phase(tmp_git_repo, "TASKS", result=None)
    assert str(exc.value) == (
        "Invalid transition: SPECIFY → TASKS. Expected next phase: PLAN."
    )


def test_review_to_implement_requires_rejected(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="REVIEW", review_cycles=[make_cycle(round=1)])
    with pytest.raises(SpecopsError) as exc:
        status.cmd_transition_phase(tmp_git_repo, "IMPLEMENT", result=None)
    assert str(exc.value) == (
        "REVIEW → IMPLEMENT requires '-r REJECTED'. "
        "Supply the result to record a corrective round."
    )


def test_done_with_no_cycles(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="REVIEW", review_cycles=[])
    with pytest.raises(SpecopsError) as exc:
        status.cmd_transition_phase(tmp_git_repo, "DONE", result=None)
    assert str(exc.value) == "Cannot enter DONE: no review cycles recorded."


def test_done_with_open_unresulted_cycle(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="REVIEW", review_cycles=[make_cycle(round=1)])
    with pytest.raises(SpecopsError) as exc:
        status.cmd_transition_phase(tmp_git_repo, "DONE", result=None)
    assert str(exc.value) == (
        "Cannot enter DONE: latest review cycle result is 'None'. Must be APPROVED."
    )


def test_done_with_rejected_result(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="REVIEW", review_cycles=[make_cycle(round=1)])
    with pytest.raises(SpecopsError) as exc:
        status.cmd_transition_phase(tmp_git_repo, "DONE", result="REJECTED")
    assert str(exc.value) == (
        "Cannot enter DONE with result REJECTED. "
        "Use 'transition-phase IMPLEMENT -r REJECTED' to record a corrective round."
    )


def test_done_blocked_by_unverified_blocking_finding(tmp_git_repo: Path) -> None:
    cycle = make_cycle(
        round=1, findings=[make_finding("R1-F01", severity="blocking", state="OPEN")]
    )
    _feature_repo(tmp_git_repo, phase="REVIEW", review_cycles=[cycle])
    with pytest.raises(SpecopsError) as exc:
        status.cmd_transition_phase(tmp_git_repo, "DONE", result="APPROVED")
    assert str(exc.value) == (
        "Cannot enter DONE: unverified blocking findings remain: R1-F01. "
        "Verify them ('specops handoff finding verify') first."
    )


def test_done_approved_success_message(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="REVIEW", review_cycles=[make_cycle(round=1)])
    out = status.cmd_transition_phase(tmp_git_repo, "DONE", result="APPROVED")
    assert out == "Phase transition: REVIEW → DONE."


def test_if_needed_noop_message(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="REVIEW", review_cycles=[make_cycle(round=1)])
    out = status.cmd_transition_phase(
        tmp_git_repo, "REVIEW", result=None, if_needed=True
    )
    assert out == "Ledger already in REVIEW; transition to REVIEW is a no-op."


def test_corrective_rejected_round_message_and_placeholder(tmp_git_repo: Path) -> None:
    feature_dir = _feature_repo(
        tmp_git_repo, phase="REVIEW", review_cycles=[make_cycle(round=1)]
    )
    out = status.cmd_transition_phase(tmp_git_repo, "IMPLEMENT", result="REJECTED")
    assert out == "Phase transition: REVIEW → IMPLEMENT."
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    cycles = data["review_cycles"]
    assert cycles[0]["result"] == "REJECTED"
    assert cycles[0]["completed_at"] is not None
    assert cycles[1] == {
        "round": 2, "started_at": None, "completed_at": None, "result": None,
    }


# ---------------------------------------------------------------------------
# cmd_complete_task
# ---------------------------------------------------------------------------

_TASKS_MD = "# Tasks\n\n- [ ] T001 Do the thing\n- [ ] T002 Do the other thing\n"


def _task(tid: str, *, tstatus: str, started: str | None) -> dict:
    return {
        "id": tid, "status": tstatus, "started_commit": started,
        "commits": [], "evidence": None, "completed_at": None,
    }


def test_complete_task_requires_exactly_one_evidence_source(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="IMPLEMENT", tasks_md=_TASKS_MD)
    with pytest.raises(SpecopsError) as exc:
        status.cmd_complete_task(tmp_git_repo, "T001", auto=False, evidence=None)
    assert str(exc.value) == (
        "Exactly one evidence source required: --auto or --evidence."
    )
    with pytest.raises(SpecopsError) as exc:
        status.cmd_complete_task(tmp_git_repo, "T001", auto=True, evidence="CLI_LOG:x")
    assert str(exc.value) == "Provide --auto or --evidence, not both."


def test_complete_unknown_task(tmp_git_repo: Path) -> None:
    _feature_repo(tmp_git_repo, phase="IMPLEMENT", tasks_md=_TASKS_MD)
    with pytest.raises(SpecopsError) as exc:
        status.cmd_complete_task(tmp_git_repo, "T099", auto=False, evidence="CLI_LOG:x")
    assert str(exc.value) == "Task 'T099' not found in tasks.md."


def test_complete_task_not_in_progress(tmp_git_repo: Path) -> None:
    _feature_repo(
        tmp_git_repo, phase="IMPLEMENT", tasks_md=_TASKS_MD,
        tasks=[_task("T001", tstatus="PENDING", started=None)],
    )
    with pytest.raises(SpecopsError) as exc:
        status.cmd_complete_task(tmp_git_repo, "T001", auto=False, evidence="CLI_LOG:x")
    assert str(exc.value) == "Task 'T001' is not IN_PROGRESS (status: PENDING)."


def test_complete_task_missing_started_commit(tmp_git_repo: Path) -> None:
    _feature_repo(
        tmp_git_repo, phase="IMPLEMENT", tasks_md=_TASKS_MD,
        tasks=[_task("T001", tstatus="IN_PROGRESS", started=None)],
    )
    with pytest.raises(SpecopsError) as exc:
        status.cmd_complete_task(tmp_git_repo, "T001", auto=False, evidence="CLI_LOG:x")
    assert str(exc.value) == (
        "Task 'T001' has no started_commit; cannot harvest evidence."
    )


def test_complete_task_invalid_manual_evidence(tmp_git_repo: Path) -> None:
    baseline = git(tmp_git_repo, "rev-parse", "HEAD")
    _feature_repo(
        tmp_git_repo, phase="IMPLEMENT", tasks_md=_TASKS_MD,
        tasks=[_task("T001", tstatus="IN_PROGRESS", started=baseline)],
    )
    with pytest.raises(SpecopsError) as exc:
        status.cmd_complete_task(tmp_git_repo, "T001", auto=False, evidence="garbage")
    assert str(exc.value) == (
        "Invalid evidence format. Expected '<CLASS>:<summary>[; ...]' "
        "with class in ['CLI_LOG', 'CODE_DIFF', 'SCREENSHOT_PATH', 'TEST_REPORT']."
    )


def test_complete_task_manual_evidence_success_message(tmp_git_repo: Path) -> None:
    baseline = git(tmp_git_repo, "rev-parse", "HEAD")
    feature_dir = _feature_repo(
        tmp_git_repo, phase="IMPLEMENT", tasks_md=_TASKS_MD,
        tasks=[_task("T001", tstatus="IN_PROGRESS", started=baseline)],
    )
    out = status.cmd_complete_task(
        tmp_git_repo, "T001", auto=False, evidence="CLI_LOG:manual run ok"
    )
    assert out == "Task 'T001' completed. Evidence: CLI_LOG:manual run ok"
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    task = next(t for t in data["tasks"] if t["id"] == "T001")
    assert task["status"] == "DONE"
    assert task["evidence"] == "CLI_LOG:manual run ok"
    assert task["evidence_refs"] and task["evidence_refs"][0].startswith("EV-")
    assert data["recovery"]["active_task"] is None
