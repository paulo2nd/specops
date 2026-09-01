"""Integration: renumbering a feature end to end (Feature 026, T066).

The field scenario behind #75's second ask: a colleague's merge takes the number this
feature reserved. Today that means hand-moving a directory, artifacts, a branch
reference and a ledger that is explicitly not hand-editable — and the workaround
found was to delete the ledger and re-run `init-spec`, destroying the audit trail.

Covers SC-008: the renamed feature keeps every record and passes both gates.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from tests.conftest import cli, git

OLD, NEW = "specs/026-old-name", "specs/027-new-name"


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    git(root, "config", "user.email", "t@t.com")
    git(root, "config", "user.name", "T")
    (root / "README.md").write_text("# test\n")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "init")

    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": OLD})
    )
    fd = root / OLD
    fd.mkdir(parents=True)
    (fd / "spec.md").write_text(
        "# Feature Specification: Old Name\n\n"
        "**Feature Branch**: `026-old-name`\n\n"
        "## Success Criteria\n\n- **SC-001**: works\n"
    )
    (fd / "plan.md").write_text("# Plan\n\nSee `specs/026-old-name/spec.md`.\n")
    (fd / "tasks.md").write_text("- [ ] T001 [SC-001] do it\n")
    return root


def _ledger(fd: Path) -> dict:
    return yaml.safe_load((fd / "status.yaml").read_text(encoding="utf-8"))


def test_renumber_preserves_the_ledger_and_passes_both_gates(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    created = cli(root, "status", "init-spec")
    assert created.returncode == 0, created.stderr
    started = cli(root, "status", "start-task", "T001")
    assert started.returncode == 0, started.stderr
    closed = cli(root, "status", "complete-task", "T001", "--evidence", "CLI_LOG:done")
    assert closed.returncode == 0, closed.stderr

    before = _ledger(root / OLD)
    assert before["tasks"][0]["status"] == "DONE"

    # The colleague's merge took 026. Rename the branch, then record it.
    git(root, "branch", "-m", "027-new-name")
    renamed = cli(root, "feature", "rename", OLD, NEW, "--branch", "027-new-name")
    assert renamed.returncode == 0, renamed.stderr
    assert "026-old-name → 027-new-name" in renamed.stdout or "→" in renamed.stdout

    # Every recorded fact travelled; only the identity changed.
    after = _ledger(root / NEW)
    assert not (root / OLD).exists()
    for key in ("tasks", "evidence", "acknowledgements", "review_cycles"):
        assert after.get(key) == before.get(key)
    assert after["feature"] == "027-new-name"
    assert after["branch"] == "027-new-name"
    assert after["revision"] == before["revision"]

    # The pointer followed, and both gates accept the feature under its new name.
    pointer = json.loads((root / ".specify" / "feature.json").read_text())
    assert pointer["feature_directory"] == NEW
    assert cli(root, "reconcile").returncode == 0
    consistency = cli(root, "consistency")
    assert consistency.returncode == 0, consistency.stderr
    assert f"feature: {NEW}" in consistency.stdout


def test_stale_prose_references_are_reported_and_left_alone(tmp_path: Path) -> None:
    """FR-016b: SpecOps rewrites the one header it owns and reports the rest — a
    reference to the old name may well be deliberate, and only a human can tell."""
    root = _repo(tmp_path)
    cli(root, "status", "init-spec")
    before_plan = (root / OLD / "plan.md").read_bytes()

    result = cli(root, "feature", "rename", OLD, NEW)

    assert result.returncode == 0, result.stderr
    assert "plan.md:3" in result.stdout
    assert (root / NEW / "plan.md").read_bytes() == before_plan
    assert "**Feature Branch**: `027-new-name`" in (root / NEW / "spec.md").read_text()


def test_a_refused_rename_changes_nothing(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    cli(root, "status", "init-spec")
    (root / NEW).mkdir(parents=True)
    before = (root / OLD / "status.yaml").read_bytes()

    result = cli(root, "feature", "rename", OLD, NEW)

    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert (root / OLD / "status.yaml").read_bytes() == before
    assert json.loads(
        (root / ".specify" / "feature.json").read_text()
    )["feature_directory"] == OLD
