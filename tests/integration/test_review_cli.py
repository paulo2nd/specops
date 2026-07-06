"""Integration tests for `specops review` — exit codes, streams, ledger immutability (004)."""
import json
import subprocess
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_review(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["specops", "review"],
        cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def _write_config(root: Path, lint: str = "", test: str = "") -> None:
    (root / "specops.json").write_text(json.dumps({
        "test_command": test,
        "lint_command": lint,
        "skills_dir": ".specify/skills",
    }))


def _write_ledger(root: Path, baseline: str, phase: str = "IMPLEMENT") -> Path:
    feature_dir = root / "specs" / "001-demo"
    data = {
        "feature": "001-demo",
        "branch": _git(root, "branch", "--show-current"),
        "baseline": baseline,
        "current_phase": phase,
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [],
        "review_cycles": [],
    }
    ledger = feature_dir / "status.yaml"
    ledger.write_text(yaml.dump(data))
    return ledger


def _all_pass_setup(root: Path, phase: str = "IMPLEMENT") -> Path:
    baseline = _git(root, "rev-parse", "HEAD")
    _write_config(root)
    ledger = _write_ledger(root, baseline, phase=phase)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "setup")
    return ledger


# ---------------------------------------------------------------------------
# Exit codes and streams
# ---------------------------------------------------------------------------


class TestReviewExitCodes:
    def test_all_pass_exit_zero_report_on_stdout(self, fake_speckit_repo: Path) -> None:
        _all_pass_setup(fake_speckit_repo)
        result = _run_review(fake_speckit_repo)
        assert result.returncode == 0
        assert "[gate] reconcile" in result.stdout
        assert "[gate] working-tree" in result.stdout
        assert result.stderr == ""

    def test_gate_failure_exit_one_evidence_on_stderr(self, fake_speckit_repo: Path) -> None:
        _all_pass_setup(fake_speckit_repo)
        (fake_speckit_repo / "stray.txt").write_text("x\n")
        result = _run_review(fake_speckit_repo)
        assert result.returncode == 1
        assert "stray.txt" in result.stderr
        assert result.stdout == ""

    def test_corrupt_ledger_exit_two(self, fake_speckit_repo: Path) -> None:
        ledger = _all_pass_setup(fake_speckit_repo)
        ledger.write_text("{{{ not yaml :::")
        result = _run_review(fake_speckit_repo)
        assert result.returncode == 2

    def test_missing_config_exit_one_with_init_guidance(self, fake_speckit_repo: Path) -> None:
        baseline = _git(fake_speckit_repo, "rev-parse", "HEAD")
        _write_ledger(fake_speckit_repo, baseline)
        result = _run_review(fake_speckit_repo)
        assert result.returncode == 1
        assert "specops.json" in result.stderr
        assert "init" in result.stderr


# ---------------------------------------------------------------------------
# Ledger immutability (FR-007)
# ---------------------------------------------------------------------------


class TestReviewReadOnly:
    def test_ledger_byte_identical_on_pass(self, fake_speckit_repo: Path) -> None:
        ledger = _all_pass_setup(fake_speckit_repo)
        before = ledger.read_bytes()
        result = _run_review(fake_speckit_repo)
        assert result.returncode == 0
        assert ledger.read_bytes() == before

    def test_ledger_byte_identical_on_failure(self, fake_speckit_repo: Path) -> None:
        ledger = _all_pass_setup(fake_speckit_repo)
        (fake_speckit_repo / "stray.txt").write_text("x\n")
        before = ledger.read_bytes()
        result = _run_review(fake_speckit_repo)
        assert result.returncode == 1
        assert ledger.read_bytes() == before
