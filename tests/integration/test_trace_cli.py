"""Integration tests for the `specops trace` CLI (Feature 010)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from tests.conftest import make_task


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=root, capture_output=True, text=True)


def _ledger(root: Path) -> dict:
    return yaml.safe_load((root / "specs" / "001-demo" / "status.yaml").read_text())


# ---------------------------------------------------------------------------
# classify (T008)
# ---------------------------------------------------------------------------


def test_classify_json_contract(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/planned.py"],
                      changed={"src/planned.py": "x\n", "src/surprise.py": "y\n"})
    r = _run(root, "trace", "classify", "--json")
    assert r.returncode == 0, r.stderr
    obj = json.loads(r.stdout)
    assert obj["command"] == "trace classify"
    assert obj["output_version"] == 1
    assert obj["status"] == "trace_ok"
    assert obj["counts"] == {"planned": 1, "discovered-and-acknowledged": 0, "unexplained": 1}


def test_classify_explicit_path_bypasses_git(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/a.py"])
    r = _run(root, "trace", "classify", "--path", "src/a.py", "--path", "src/b.py", "--json")
    assert r.returncode == 0
    obj = json.loads(r.stdout)
    assert obj["counts"]["planned"] == 1 and obj["counts"]["unexplained"] == 1


def test_classify_read_only(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/planned.py"], changed={"src/surprise.py": "y\n"})
    before = _ledger(root)
    _run(root, "trace", "classify")
    assert _ledger(root) == before


# ---------------------------------------------------------------------------
# validate (T018)
# ---------------------------------------------------------------------------


def test_validate_blocks_on_unexplained(trace_repo) -> None:
    root = trace_repo(plan_paths=[], changed={"src/surprise.py": "y\n"})
    r = _run(root, "trace", "validate", "--json")
    assert r.returncode == 1
    obj = json.loads(r.stdout)
    assert obj["status"] in ("drift_blocked", "trace_incomplete")
    assert "src/surprise.py" in obj["unexplained"]


def test_validate_uncovered_sc_exit_one(trace_repo) -> None:
    root = trace_repo(
        spec_scs=["SC-001", "SC-002"], plan_paths=["src/a.py"],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", commits=["a" * 40])],
        changed={"src/a.py": "x\n"},
    )
    r = _run(root, "trace", "validate", "--json")
    assert r.returncode == 1
    obj = json.loads(r.stdout)
    assert any(d["kind"] == "uncovered-sc" for d in obj["defects"])


# ---------------------------------------------------------------------------
# acknowledge (T013)
# ---------------------------------------------------------------------------


def test_acknowledge_records_then_reclassifies(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")],
                      changed={"src/disc.py": "y\n"})
    r = _run(root, "trace", "acknowledge", "src/disc.py", "--task", "T001",
             "--reason", "moved during T001", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["status"] == "ack_recorded"
    # now classify labels it discovered-and-acknowledged
    c = json.loads(_run(root, "trace", "classify", "--json").stdout)
    row = next(p for p in c["paths"] if p["path"] == "src/disc.py")
    assert row["class"] == "discovered-and-acknowledged"


def test_acknowledge_conflict_exit_two(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS"),
                                            make_task("T002", status="PENDING")])
    _run(root, "trace", "acknowledge", "src/d.py", "--task", "T001", "--reason", "r")
    r = _run(root, "trace", "acknowledge", "src/d.py", "--task", "T002", "--reason", "other")
    assert r.returncode == 2


def test_acknowledge_unknown_task_exit_two(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    r = _run(root, "trace", "acknowledge", "src/d.py", "--task", "T999", "--reason", "r")
    assert r.returncode == 2
    assert (_ledger(root).get("acknowledgements") or []) == []


# ---------------------------------------------------------------------------
# report + drift gate inside `specops review` (T008/T018)
# ---------------------------------------------------------------------------


def test_report_runs(trace_repo) -> None:
    root = trace_repo(spec_scs=["SC-001"], plan_paths=[],
                      tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
                      tasks=[make_task("T001", commits=["a" * 40])])
    r = _run(root, "trace", "report", "--json")
    assert r.returncode == 0
    assert "success_criteria" in json.loads(r.stdout)["graph"]


def test_review_drift_gate_blocks_unexplained(trace_repo) -> None:
    # a declared plan path gives the gate a basis; src/surprise.py is unexplained
    root = trace_repo(plan_paths=["src/planned.py"],
                      changed={"src/planned.py": "x\n", "src/surprise.py": "y\n"})
    (root / "specops.json").write_text('{"test_command": "", "lint_command": ""}')
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "cfg"], cwd=root, check=True, capture_output=True)
    r = _run(root, "review")
    assert r.returncode == 1
    out = r.stdout + r.stderr
    assert "drift" in out and "src/surprise.py" in out
