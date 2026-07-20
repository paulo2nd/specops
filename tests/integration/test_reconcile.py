"""Integration tests for specops reconcile — Quickstart Scenario C."""
import json
import subprocess
from pathlib import Path

import yaml


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=repo, capture_output=True, text=True)


def _commit(repo: Path, msg: str = "work") -> str:
    (repo / f"{msg}.txt").write_text(msg)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()


class TestReconcileJsonOutcome:
    """Feature 007 US2 (T017/T018): `reconcile --json` fail-closed precondition. [SC-004]"""

    def _init(self, repo: Path) -> Path:
        fd = repo / "specs" / "001-demo"
        (fd / "tasks.md").write_text("- [ ] T001 task\n")
        (fd / "spec.md").write_text("# spec\n")
        _run(repo, "status", "init-spec")
        return fd

    def test_json_pass_when_consistent(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        self._init(repo)
        r = _run(repo, "reconcile", "--json")
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout)["class"] == "pass"

    def test_json_workflow_state_divergence(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        self._init(repo)
        # Advance to PLAN without a plan.md → the phase's active artifact is missing.
        assert _run(repo, "status", "transition-phase", "PLAN").returncode == 0
        r = _run(repo, "reconcile", "--json")
        assert r.returncode == 1
        obj = json.loads(r.stdout)
        assert obj["class"] == "infra-error"
        assert obj["diverged_dimension"] == "workflow-state"
        assert obj["remedy"] == "specops status rebaseline"

    def test_json_branch_divergence(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        self._init(repo)
        subprocess.run(["git", "checkout", "-b", "other"], cwd=repo,
                       check=True, capture_output=True)
        r = _run(repo, "reconcile", "--json")
        assert r.returncode == 1
        obj = json.loads(r.stdout)
        assert obj["diverged_dimension"] == "branch"
        assert obj["remedy"] == "specops status rebaseline"


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
