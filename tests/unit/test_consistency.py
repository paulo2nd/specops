"""Unit tests for consistency.py — SC coverage + path suffix validation."""
import json
import subprocess
from pathlib import Path

import pytest

from specops import consistency


def _setup(tmp_path: Path, spec: str = "", tasks: str = "", plan: str = "") -> Path:
    """Return repo root with git, .specify, and feature artifacts."""
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

    if spec:
        (feature_dir / "spec.md").write_text(spec)
    if tasks:
        (feature_dir / "tasks.md").write_text(tasks)
    if plan:
        (feature_dir / "plan.md").write_text(plan)

    return root


# ---------------------------------------------------------------------------
# SC coverage matrix
# ---------------------------------------------------------------------------

def test_all_scs_covered_passes(tmp_path: Path) -> None:
    spec = "- **SC-001**: first\n- **SC-002**: second\n"
    tasks = "- [ ] T001 [SC-001,SC-002] Combined\n"
    root = _setup(tmp_path, spec=spec, tasks=tasks)
    with pytest.raises(SystemExit) as exc:
        consistency.run(root)
    assert exc.value.code == 0


def test_uncovered_sc_fails(tmp_path: Path) -> None:
    spec = "- **SC-001**: first\n- **SC-002**: second\n"
    tasks = "- [ ] T001 [SC-001] Only first\n"
    root = _setup(tmp_path, spec=spec, tasks=tasks)
    with pytest.raises(SystemExit) as exc:
        consistency.run(root)
    assert exc.value.code == 1


def test_unknown_sc_ref_fails(tmp_path: Path) -> None:
    spec = "- **SC-001**: first\n"
    tasks = "- [ ] T001 [SC-001,SC-999] Bad ref\n"
    root = _setup(tmp_path, spec=spec, tasks=tasks)
    with pytest.raises(SystemExit) as exc:
        consistency.run(root)
    assert exc.value.code == 1


def test_no_scs_in_spec_passes(tmp_path: Path) -> None:
    """No SC definitions → no coverage required → ok."""
    root = _setup(tmp_path, spec="Just some text.", tasks="- [ ] T001 task\n")
    with pytest.raises(SystemExit) as exc:
        consistency.run(root)
    assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Path suffix rules
# ---------------------------------------------------------------------------

def test_create_suffix_existing_parent_passes(tmp_path: Path) -> None:
    """(create) with existing parent → ok."""
    root = _setup(tmp_path)
    (root / "src").mkdir()
    plan = "├── `src/newfile.py` (create) — new module\n"
    (root / "specs" / "001-test" / "plan.md").write_text(plan)
    with pytest.raises(SystemExit) as exc:
        consistency.run(root)
    assert exc.value.code == 0


def test_modify_suffix_existing_file_passes(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    (root / "existing.py").write_text("x = 1")
    plan = "├── `existing.py` (modify) — update\n"
    (root / "specs" / "001-test" / "plan.md").write_text(plan)
    with pytest.raises(SystemExit) as exc:
        consistency.run(root)
    assert exc.value.code == 0


def test_modify_suffix_missing_file_fails(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    plan = "├── `ghost.py` (modify) — ghost file\n"
    (root / "specs" / "001-test" / "plan.md").write_text(plan)
    with pytest.raises(SystemExit) as exc:
        consistency.run(root)
    assert exc.value.code == 1


def test_violation_line_format(tmp_path: Path) -> None:
    """Violation lines use 'consistency: file:line - ...' format."""
    spec = "- **SC-001**: criterion\n"
    tasks = "- [ ] T001 no coverage tags\n"
    root = _setup(tmp_path, spec=spec, tasks=tasks)
    # Capture via subprocess
    import subprocess
    r = subprocess.run(["specops", "consistency"], cwd=root, capture_output=True, text=True)
    assert r.returncode == 1
    assert "consistency:" in r.stderr
