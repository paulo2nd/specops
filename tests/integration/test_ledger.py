"""Integration tests for the ledger — Quickstart Scenarios B and E."""
import json
import subprocess
from pathlib import Path

import yaml


def _commit(repo: Path, msg: str = "work") -> str:
    (repo / f"{msg}.txt").write_text(msg)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    return result.stdout.strip()


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["specops", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Scenario B — Full ledger loop
# ---------------------------------------------------------------------------

class TestScenarioB:
    def setup_method(self, fake_speckit_repo: Path) -> None:
        pass

    def test_full_ledger_loop(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"

        # Write tasks.md
        (feature_dir / "tasks.md").write_text(
            "- [ ] T001 First task\n- [ ] T002 Second task\n"
        )

        # Write specops.json with a passing test command
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "true", "lint_command": "", "skills_dir": ""})
        )

        # B-1: init-spec creates status.yaml
        r = _run(repo, "status", "init-spec")
        assert r.returncode == 0, r.stderr
        ledger_path = feature_dir / "status.yaml"
        assert ledger_path.is_file()

        data = yaml.safe_load(ledger_path.read_text())
        task_ids = [t["id"] for t in data["tasks"]]
        assert "T001" in task_ids and "T002" in task_ids

        # B-2: start T001
        r = _run(repo, "status", "start-task", "T001")
        assert r.returncode == 0, r.stderr

        # B-3: start T002 while T001 active → exit 1
        r = _run(repo, "status", "start-task", "T002")
        assert r.returncode == 1

        # B-4: commit work, then complete T001 --auto
        _commit(repo, "T001-work")
        r = _run(repo, "status", "complete-task", "T001", "--auto")
        assert r.returncode == 0, r.stderr

        data = yaml.safe_load(ledger_path.read_text())
        t001 = next(t for t in data["tasks"] if t["id"] == "T001")
        assert t001["status"] == "DONE"
        assert t001["evidence"] is not None
        assert "TEST_REPORT" in t001["evidence"]
        assert len(t001["commits"]) > 0

    def test_failing_test_command_blocks_completion(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"

        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "false", "lint_command": "", "skills_dir": ""})
        )

        _run(repo, "status", "init-spec")
        _run(repo, "status", "start-task", "T001")
        _commit(repo, "work")

        r = _run(repo, "status", "complete-task", "T001", "--auto")
        assert r.returncode == 1, "Failing test_command should prevent completion"

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        t001 = next(t for t in data["tasks"] if t["id"] == "T001")
        assert t001["status"] == "IN_PROGRESS"

    def test_manual_evidence_path(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"

        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "false", "lint_command": "", "skills_dir": ""})
        )

        _run(repo, "status", "init-spec")
        _run(repo, "status", "start-task", "T001")

        # B-6a: --evidence flag with failing test_command → ok
        r = _run(repo, "status", "complete-task", "T001", "--evidence", "CLI_LOG:manual check ok")
        assert r.returncode == 0, r.stderr

    def test_complete_without_flag_fails(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"

        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        (repo / "specops.json").write_text(json.dumps({"test_command": "true"}))

        _run(repo, "status", "init-spec")
        _run(repo, "status", "start-task", "T001")

        # B-6b: no flag → exit 1
        r = _run(repo, "status", "complete-task", "T001")
        assert r.returncode == 1


# ---------------------------------------------------------------------------
# Scenario E — Phase machine walk
# ---------------------------------------------------------------------------

class TestScenarioE:
    def test_phase_walk_and_corrective_loop(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")

        _run(repo, "status", "init-spec")

        # E-1: SPECIFY → PLAN
        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 0

        # E-2: skip TASKS → REVIEW (should fail)
        r = _run(repo, "status", "transition-phase", "REVIEW")
        assert r.returncode == 1

        # Walk to REVIEW
        _run(repo, "status", "transition-phase", "TASKS")
        _run(repo, "status", "transition-phase", "IMPLEMENT")
        r = _run(repo, "status", "transition-phase", "REVIEW")
        assert r.returncode == 0

        # E-3: REVIEW → IMPLEMENT -r REJECTED (corrective loop)
        r = _run(repo, "status", "transition-phase", "IMPLEMENT", "-r", "REJECTED")
        assert r.returncode == 0

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["current_phase"] == "IMPLEMENT"
        assert len(data["review_cycles"]) >= 2

        # E-4: transition DONE without APPROVED latest → fail
        _run(repo, "status", "transition-phase", "REVIEW")
        r = _run(repo, "status", "transition-phase", "DONE")
        assert r.returncode == 1


# ---------------------------------------------------------------------------
# T007 — SC-001: full lifecycle SPECIFY→DONE -r APPROVED via CLI only
# ---------------------------------------------------------------------------

class TestFullLifecycleSC001:
    def test_full_lifecycle_approve_via_cli(self, fake_speckit_repo: Path) -> None:
        """SPECIFY→PLAN→TASKS→IMPLEMENT→REVIEW→DONE -r APPROVED with no manual ledger edits."""
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 only task\n")
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "true", "lint_command": "", "skills_dir": ""})
        )

        # Init ledger
        r = _run(repo, "status", "init-spec")
        assert r.returncode == 0, r.stderr

        # Phase walk: SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW
        for phase in ("PLAN", "TASKS", "IMPLEMENT", "REVIEW"):
            r = _run(repo, "status", "transition-phase", phase)
            assert r.returncode == 0, f"transition to {phase} failed: {r.stderr}"

        # Verify in REVIEW phase
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["current_phase"] == "REVIEW"
        assert len(data["review_cycles"]) == 1
        assert data["review_cycles"][0]["result"] is None

        # REVIEW → DONE -r APPROVED (no manual ledger edit)
        r = _run(repo, "status", "transition-phase", "DONE", "-r", "APPROVED")
        assert r.returncode == 0, r.stderr

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["current_phase"] == "DONE"
        assert data["review_cycles"][-1]["result"] == "APPROVED"
        assert data["review_cycles"][-1]["completed_at"] is not None

    def test_invalid_result_rejected_by_cli(self, fake_speckit_repo: Path) -> None:
        """CLI rejects invalid result vocabulary before touching the ledger."""
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")

        _run(repo, "status", "init-spec")
        for phase in ("PLAN", "TASKS", "IMPLEMENT", "REVIEW"):
            _run(repo, "status", "transition-phase", phase)

        original = (feature_dir / "status.yaml").read_text()
        r = _run(repo, "status", "transition-phase", "DONE", "-r", "maybe")
        assert r.returncode == 1
        assert (feature_dir / "status.yaml").read_text() == original
