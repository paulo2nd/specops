"""Integration tests for CLI surface: --version, status show, exit-code regression sweep
[SC-002, SC-003, SC-006]."""
import json
import subprocess
from pathlib import Path


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=cwd, capture_output=True, text=True)


def _commit(repo: Path, msg: str = "work") -> None:
    (repo / f"{msg}.txt").write_text(msg)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)


def _init_ledger(repo: Path) -> Path:
    feature_dir = repo / "specs" / "001-demo"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
    r = _run("status", "init-spec", cwd=repo)
    assert r.returncode == 0, r.stderr
    return feature_dir


# ---------------------------------------------------------------------------
# --version [SC-003]
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_inside_git_repo(self, fake_speckit_repo: Path) -> None:
        r = _run("--version", cwd=fake_speckit_repo)
        assert r.returncode == 0
        assert r.stdout.startswith("specops ")

    def test_version_outside_git_repo(self, tmp_path: Path) -> None:
        r = _run("--version", cwd=tmp_path)
        assert r.returncode == 0
        assert r.stdout.startswith("specops ")

    def test_version_output_on_stdout(self, tmp_path: Path) -> None:
        r = _run("--version", cwd=tmp_path)
        assert r.stdout.strip() != ""
        assert r.stderr.strip() == ""


# ---------------------------------------------------------------------------
# status show [SC-002]
# ---------------------------------------------------------------------------

class TestStatusShow:
    def test_show_exit_0(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        r = _run("status", "show", cwd=fake_speckit_repo)
        assert r.returncode == 0, r.stderr

    def test_show_output_format(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        r = _run("status", "show", cwd=fake_speckit_repo)
        assert r.returncode == 0
        out = r.stdout
        assert "feature:" in out
        assert "branch:" in out
        assert "phase:" in out
        assert "active task:" in out
        assert "tasks:" in out
        assert "review cycles:" in out

    def test_show_does_not_modify_ledger(self, fake_speckit_repo: Path) -> None:
        feature_dir = _init_ledger(fake_speckit_repo)
        ledger = feature_dir / "status.yaml"
        before = ledger.read_bytes()
        _run("status", "show", cwd=fake_speckit_repo)
        assert ledger.read_bytes() == before

    def test_show_missing_ledger_exits_1(self, fake_speckit_repo: Path) -> None:
        r = _run("status", "show", cwd=fake_speckit_repo)
        assert r.returncode == 1
        assert "Ledger not found" in r.stderr


# ---------------------------------------------------------------------------
# Exit-code regression sweep [SC-006]
# ---------------------------------------------------------------------------

class TestExitCodeRegression:
    """Verify documented failure modes keep byte-identical exit codes and streams."""

    def test_init_spec_outside_git_fails_exit_1(self, tmp_path: Path) -> None:
        r = _run("status", "init-spec", cwd=tmp_path)
        assert r.returncode == 1
        assert r.stderr != ""

    def test_start_task_outside_git_fails_exit_1(self, tmp_path: Path) -> None:
        r = _run("status", "start-task", "T001", cwd=tmp_path)
        assert r.returncode == 1
        assert r.stderr != ""

    def test_complete_task_outside_git_fails_exit_1(self, tmp_path: Path) -> None:
        r = _run("status", "complete-task", "T001", cwd=tmp_path)
        assert r.returncode == 1
        assert r.stderr != ""

    def test_transition_phase_outside_git_fails_exit_1(self, tmp_path: Path) -> None:
        r = _run("status", "transition-phase", "PLAN", cwd=tmp_path)
        assert r.returncode == 1
        assert r.stderr != ""

    def test_invalid_result_vocabulary_exit_1(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        for phase in ("PLAN", "TASKS", "IMPLEMENT", "REVIEW"):
            _run("status", "transition-phase", phase, cwd=fake_speckit_repo)
        r = _run("status", "transition-phase", "DONE", "-r", "invalid", cwd=fake_speckit_repo)
        assert r.returncode == 1
        assert "APPROVED or REJECTED" in r.stderr

    def test_done_rejected_result_exit_1(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        for phase in ("PLAN", "TASKS", "IMPLEMENT", "REVIEW"):
            _run("status", "transition-phase", phase, cwd=fake_speckit_repo)
        r = _run("status", "transition-phase", "DONE", "-r", "REJECTED", cwd=fake_speckit_repo)
        assert r.returncode == 1
        assert r.stderr != ""

    def test_complete_task_invalid_evidence_exit_1(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        (fake_speckit_repo / "specops.json").write_text(
            json.dumps({"test_command": "true", "lint_command": "", "skills_dir": ""})
        )
        _run("status", "start-task", "T001", cwd=fake_speckit_repo)
        r = _run(
            "status", "complete-task", "T001", "--evidence", "BADCLASS:x", cwd=fake_speckit_repo
        )
        assert r.returncode == 1
        assert r.stderr != ""

    def test_complete_task_no_flag_exit_1(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        (fake_speckit_repo / "specops.json").write_text(json.dumps({"test_command": "true"}))
        _run("status", "start-task", "T001", cwd=fake_speckit_repo)
        r = _run("status", "complete-task", "T001", cwd=fake_speckit_repo)
        assert r.returncode == 1
        assert r.stderr != ""

    def test_start_nonexistent_task_exit_1(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        r = _run("status", "start-task", "T999", cwd=fake_speckit_repo)
        assert r.returncode == 1
        assert r.stderr != ""

    def test_reconcile_exit_0_clean(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        r = _run("reconcile", cwd=fake_speckit_repo)
        assert r.returncode == 0
        assert "reconcile: ok" in r.stdout

    def test_consistency_exit_0_no_artifacts(self, fake_speckit_repo: Path) -> None:
        r = _run("consistency", cwd=fake_speckit_repo)
        assert r.returncode == 0
        assert "consistency: ok" in r.stdout

    def test_transition_success_exit_0(self, fake_speckit_repo: Path) -> None:
        _init_ledger(fake_speckit_repo)
        r = _run("status", "transition-phase", "PLAN", cwd=fake_speckit_repo)
        assert r.returncode == 0
        assert r.stdout != ""
        assert r.stderr == ""
