"""Integration tests for specops reconcile — Quickstart Scenario C."""
import json
import subprocess
from pathlib import Path

import pytest
import yaml


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=repo, capture_output=True, text=True)


def _commit(repo: Path, msg: str = "work") -> str:
    (repo / f"{msg}.txt").write_text(msg)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


class TestScenarioC:
    def test_clean_ledger_passes(self, fake_speckit_repo: Path) -> None:
        """Scenario C-1: clean ledger with valid commits → exit 0."""
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "true", "lint_command": "", "skills_dir": ""})
        )

        _run(repo, "status", "init-spec")
        _run(repo, "status", "start-task", "T001")
        _commit(repo, "T001-work")
        _run(repo, "status", "complete-task", "T001", "--auto")

        r = _run(repo, "reconcile")
        assert r.returncode == 0
        assert "reconcile: ok" in r.stdout

    def test_seeded_divergence_fails(self, fake_speckit_repo: Path) -> None:
        """Scenario C-2: seeded fake hash → exit 1, names task and hash (SC-003)."""
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "true", "lint_command": "", "skills_dir": ""})
        )

        _run(repo, "status", "init-spec")
        _run(repo, "status", "start-task", "T001")
        _commit(repo, "T001-work")
        _run(repo, "status", "complete-task", "T001", "--auto")

        # Seed a fake commit hash
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        data["tasks"][0]["commits"] = ["deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"]
        (feature_dir / "status.yaml").write_text(yaml.dump(data))

        r = _run(repo, "reconcile")
        assert r.returncode == 1
        assert "T001" in r.stderr
        assert "deadbee" in r.stderr  # sha[:7] prefix
