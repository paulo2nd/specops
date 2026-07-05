"""Integration tests for specops consistency — Quickstart Scenario D."""
import json
import subprocess
from pathlib import Path

import pytest


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", "consistency"], cwd=repo, capture_output=True, text=True)


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True, capture_output=True)
    (root / "README.md").write_text("# test")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

    (root / ".specify" / "templates").mkdir(parents=True)
    feature_dir = root / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )
    return root, feature_dir


class TestScenarioD:
    def test_compliant_pair_passes(self, tmp_path: Path) -> None:
        """D-1: all SCs covered → exit 0."""
        root, fd = _setup(tmp_path)
        (fd / "spec.md").write_text(
            "## Success Criteria\n- **SC-001**: passes\n- **SC-002**: second\n"
        )
        (fd / "tasks.md").write_text(
            "- [ ] T001 [SC-001] task one\n- [ ] T002 [SC-002] task two\n"
        )
        r = _run(root)
        assert r.returncode == 0

    def test_removed_coverage_tag_fails(self, tmp_path: Path) -> None:
        """D-2: remove [SC-002] tag → exit 1 naming SC-002."""
        root, fd = _setup(tmp_path)
        (fd / "spec.md").write_text(
            "## Success Criteria\n- **SC-001**: passes\n- **SC-002**: second\n"
        )
        (fd / "tasks.md").write_text(
            "- [ ] T001 [SC-001] task one\n- [ ] T002 no tag\n"
        )
        r = _run(root)
        assert r.returncode == 1
        assert "SC-002" in r.stderr

    def test_ghost_modify_path_fails(self, tmp_path: Path) -> None:
        """D-3: (modify) on non-existent file → exit 1."""
        root, fd = _setup(tmp_path)
        (fd / "spec.md").write_text("## Success Criteria\n")
        (fd / "tasks.md").write_text("- [ ] T001 task\n")
        (fd / "plan.md").write_text(
            "├── `src/ghost.py` (modify) — does not exist\n"
        )
        r = _run(root)
        assert r.returncode == 1
        assert "ghost.py" in r.stderr

    def test_non_english_prose_language_agnostic(self, tmp_path: Path) -> None:
        """D-4: spec and tasks in non-English prose → structural tokens still parsed (FR-014a)."""
        root, fd = _setup(tmp_path)
        # Portuguese prose but English structural tokens
        (fd / "spec.md").write_text(
            "## Critérios de Sucesso\n- **SC-001**: o sistema deve funcionar\n"
        )
        (fd / "tasks.md").write_text(
            "- [ ] T001 [SC-001] Implementar funcionalidade principal\n"
        )
        r = _run(root)
        assert r.returncode == 0, r.stderr
