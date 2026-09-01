"""Integration: the active-feature pointer is managed by command (Feature 026, T051).

Reproduces the field scenario behind #75: a feature is finished, the next one is
authored on a new branch, and `consistency` answers `ok` about the *finished* one
while the feature actually under work goes unvalidated — a silent failure reporting
success. The fix is not a better message; it is a pointer the operator can move.

Covers SC-005 (validated with zero hand edits) and SC-007 (SpecOps and Spec Kit
resolve the same feature from the same repository state).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from tests.conftest import cli, git


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
        json.dumps({"feature_directory": "specs/025-finished"})
    )
    done = root / "specs" / "025-finished"
    done.mkdir(parents=True)
    (done / "spec.md").write_text("- **SC-001**: works\n")
    (done / "tasks.md").write_text("- [ ] T001 [SC-001] do it\n")
    return root


def _pointer(root: Path) -> str:
    return json.loads(
        (root / ".specify" / "feature.json").read_text(encoding="utf-8")
    )["feature_directory"]


def test_new_feature_is_validated_without_a_hand_edit(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    # The next feature is authored; the pointer still names the finished one.
    fresh = root / "specs" / "026-current"
    fresh.mkdir(parents=True)
    (fresh / "spec.md").write_text("- **SC-001**: works\n- **SC-002**: also works\n")
    (fresh / "tasks.md").write_text("- [ ] T001 [SC-001,SC-002] do it\n")

    # Before: the answer is about the wrong feature — and says so (0.12.0), but the
    # operator still cannot do anything about it from the CLI.
    before = cli(root, "consistency")
    assert "feature: specs/025-finished" in before.stdout

    # One command, no hand edit.
    moved = cli(root, "feature", "use", "specs/026-current")
    assert moved.returncode == 0, moved.stderr
    assert "025-finished" in moved.stdout and "026-current" in moved.stdout
    assert _pointer(root) == "specs/026-current"

    after = cli(root, "consistency")
    assert after.returncode == 0, after.stderr
    assert "feature: specs/026-current" in after.stdout
    assert "consistency: ok" in after.stdout


def test_init_spec_records_the_feature_and_consistency_follows(tmp_path: Path) -> None:
    """The `init-spec` half of the same story: the ledger and the pointer agree."""
    root = _repo(tmp_path)
    fresh = root / "specs" / "026-current"
    fresh.mkdir(parents=True)
    (fresh / "spec.md").write_text("- **SC-001**: works\n")
    (fresh / "tasks.md").write_text("- [ ] T001 [SC-001] do it\n")
    (root / ".specify" / "feature.json").unlink()   # resolution falls back to a guess

    created = cli(root, "status", "init-spec")
    assert created.returncode == 0, created.stderr
    assert (fresh / "status.yaml").is_file()
    assert _pointer(root) == "specs/026-current"    # the guess is now a record

    shown = cli(root, "status", "show")
    assert "feature directory: specs/026-current" in shown.stdout
    assert "inferred" not in shown.stdout


def test_specops_and_speckit_resolve_the_same_feature(tmp_path: Path) -> None:
    """SC-007: Spec Kit consults SPECIFY_FEATURE_DIRECTORY before the pointer file.
    Reading only the pointer made the two tools answer about different features."""
    root = _repo(tmp_path)
    other = root / "specs" / "026-current"
    other.mkdir(parents=True)
    (other / "spec.md").write_text("- **SC-001**: works\n")
    (other / "tasks.md").write_text("- [ ] T001 [SC-001] do it\n")

    env = {**os.environ, "SPECIFY_FEATURE_DIRECTORY": "specs/026-current"}
    result = subprocess.run(
        ["specops", "consistency", "--json"], cwd=root,
        capture_output=True, text=True, env=env,
    )
    payload = json.loads(result.stdout)
    assert payload["feature"] == "specs/026-current"   # the override, not the pointer
    assert payload["feature_source"] == "override"


def test_repoint_under_an_override_is_refused_not_silently_ineffective(
    tmp_path: Path,
) -> None:
    """The write would not change what any command resolves. Reporting success on a
    no-op is the #75 failure mode itself, so the command refuses instead."""
    root = _repo(tmp_path)
    other = root / "specs" / "026-current"
    other.mkdir(parents=True)
    (other / "spec.md").write_text("- **SC-001**: works\n")

    env = {**os.environ, "SPECIFY_FEATURE_DIRECTORY": "specs/025-finished"}
    result = subprocess.run(
        ["specops", "feature", "use", "specs/026-current"], cwd=root,
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "SPECIFY_FEATURE_DIRECTORY" in result.stderr
    assert _pointer(root) == "specs/025-finished"
