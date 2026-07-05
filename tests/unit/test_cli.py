"""Unit tests for cli.py via typer.testing.CliRunner."""
from __future__ import annotations

import json
import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from specops.cli import app
from specops.errors import SpecopsError

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=root, check=True, capture_output=True
    )
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
    yield root


@pytest.fixture
def ledger_repo(git_repo: Path) -> Path:
    feature_dir = git_repo / "specs" / "001-test"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True
    ).stdout.strip()
    data = {
        "feature": "001-test",
        "branch": "main",
        "current_phase": "SPECIFY",
        "baseline": head,
        "tasks": [{"id": "T001", "status": "PENDING", "started_commit": None,
                   "commits": [], "evidence": None, "completed_at": None}],
        "review_cycles": [],
        "recovery": {"active_task": None, "last_commit": None},
    }
    ledger = feature_dir / "status.yaml"
    ledger.write_text(yaml.dump(data))
    return git_repo


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_exits_0(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_version_prints_specops(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert "specops" in result.output

    def test_version_fallback_when_package_not_found(self) -> None:
        import importlib.metadata
        with patch.object(
            importlib.metadata, "version", side_effect=importlib.metadata.PackageNotFoundError
        ):
            result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.0.0.dev0" in result.output


# ---------------------------------------------------------------------------
# Error boundary: SpecopsError → exit 1 with message on stderr
# ---------------------------------------------------------------------------

class TestErrorBoundary:
    def test_specops_error_maps_to_exit_1(self) -> None:
        with patch("specops.status.cmd_show", side_effect=SpecopsError("boom")):
            result = runner.invoke(app, ["status", "show"])
        assert result.exit_code == 1

    def test_specops_error_message_in_output(self) -> None:
        with patch("specops.status.cmd_show", side_effect=SpecopsError("boom msg")):
            result = runner.invoke(app, ["status", "show"])
        assert "boom msg" in result.output


# ---------------------------------------------------------------------------
# status show
# ---------------------------------------------------------------------------

class TestStatusShow:
    def test_show_exits_0(self, ledger_repo: Path) -> None:
        with patch("specops.cli.Path", return_value=ledger_repo):
            result = runner.invoke(app, ["status", "show"])
        assert result.exit_code == 0

    def test_show_invokes_cmd_show(self, ledger_repo: Path) -> None:
        with (
            patch("specops.status.cmd_show", return_value="ledger summary") as mock_show,
            patch("specops.cli.Path", return_value=ledger_repo),
        ):
            result = runner.invoke(app, ["status", "show"])
        mock_show.assert_called_once()
        assert "ledger summary" in result.output


# ---------------------------------------------------------------------------
# init command
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_invokes_initializer(self, git_repo: Path) -> None:
        with patch("specops.initializer.run") as mock_run, patch(
            "specops.cli.Path", return_value=git_repo
        ):
            result = runner.invoke(app, ["init", "--non-interactive"])
        mock_run.assert_called_once()
        assert result.exit_code == 0

    def test_init_specops_error_maps_to_exit_1(self, git_repo: Path) -> None:
        with patch("specops.initializer.run", side_effect=SpecopsError("init failed")), patch(
            "specops.cli.Path", return_value=git_repo
        ):
            result = runner.invoke(app, ["init", "--non-interactive"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# status init-spec
# ---------------------------------------------------------------------------

class TestStatusInitSpec:
    def test_init_spec_requires_git(self, tmp_path: Path) -> None:
        bare = tmp_path / "bare"
        bare.mkdir()
        with patch("specops.cli.Path", return_value=bare):
            result = runner.invoke(app, ["status", "init-spec"])
        assert result.exit_code != 0

    def test_init_spec_exits_0_on_success(self, git_repo: Path) -> None:
        with patch("specops.status.cmd_init_spec", return_value="Ledger created: x") as m, patch(
            "specops.cli.Path", return_value=git_repo
        ):
            result = runner.invoke(app, ["status", "init-spec"])
        m.assert_called_once()
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# status start-task / complete-task
# ---------------------------------------------------------------------------

class TestStatusStartCompleteTask:
    def test_start_task_requires_git(self, tmp_path: Path) -> None:
        bare = tmp_path / "bare"
        bare.mkdir()
        with patch("specops.cli.Path", return_value=bare):
            result = runner.invoke(app, ["status", "start-task", "T001"])
        assert result.exit_code != 0

    def test_start_task_success(self, ledger_repo: Path) -> None:
        with patch(
            "specops.status.cmd_start_task", return_value="Task 'T001' started."
        ) as m, patch("specops.cli.Path", return_value=ledger_repo):
            result = runner.invoke(app, ["status", "start-task", "T001"])
        m.assert_called_once()
        assert result.exit_code == 0

    def test_complete_task_success(self, ledger_repo: Path) -> None:
        with patch(
            "specops.status.cmd_complete_task", return_value="Task 'T001' completed."
        ) as m, patch("specops.cli.Path", return_value=ledger_repo):
            result = runner.invoke(
                app, ["status", "complete-task", "T001", "--evidence", "CLI_LOG:ok"]
            )
        m.assert_called_once()
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# status transition-phase
# ---------------------------------------------------------------------------

class TestStatusTransitionPhase:
    def test_transition_phase_success(self, ledger_repo: Path) -> None:
        with patch(
            "specops.status.cmd_transition_phase",
            return_value="Phase transition: SPECIFY → PLAN.",
        ) as m, patch("specops.cli.Path", return_value=ledger_repo):
            result = runner.invoke(app, ["status", "transition-phase", "PLAN"])
        m.assert_called_once()
        assert result.exit_code == 0

    def test_transition_phase_with_result_flag(self, ledger_repo: Path) -> None:
        with patch(
            "specops.status.cmd_transition_phase",
            return_value="Phase transition: REVIEW → DONE.",
        ) as m, patch("specops.cli.Path", return_value=ledger_repo):
            result = runner.invoke(
                app, ["status", "transition-phase", "DONE", "-r", "APPROVED"]
            )
        m.assert_called_once()
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# reconcile / consistency
# ---------------------------------------------------------------------------

class TestReconcileConsistency:
    def test_reconcile_requires_git(self, tmp_path: Path) -> None:
        bare = tmp_path / "bare"
        bare.mkdir()
        with patch("specops.cli.Path", return_value=bare):
            result = runner.invoke(app, ["reconcile"])
        assert result.exit_code != 0

    def test_reconcile_clean_prints_ok(self, ledger_repo: Path) -> None:
        with patch("specops.reconcile.run", return_value=([], [])), patch(
            "specops.cli.Path", return_value=ledger_repo
        ):
            result = runner.invoke(app, ["reconcile"])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_reconcile_violations_exit_1(self, ledger_repo: Path) -> None:
        with patch("specops.reconcile.run", return_value=([], ["bad hash"])), patch(
            "specops.cli.Path", return_value=ledger_repo
        ):
            result = runner.invoke(app, ["reconcile"])
        assert result.exit_code == 1

    def test_consistency_requires_git(self, tmp_path: Path) -> None:
        bare = tmp_path / "bare"
        bare.mkdir()
        with patch("specops.cli.Path", return_value=bare):
            result = runner.invoke(app, ["consistency"])
        assert result.exit_code != 0

    def test_consistency_clean_prints_ok(self, ledger_repo: Path) -> None:
        with patch("specops.consistency.run", return_value=([], [])), patch(
            "specops.cli.Path", return_value=ledger_repo
        ):
            result = runner.invoke(app, ["consistency"])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_consistency_violations_exit_1(self, ledger_repo: Path) -> None:
        with patch("specops.consistency.run", return_value=([], ["violation"])), patch(
            "specops.cli.Path", return_value=ledger_repo
        ):
            result = runner.invoke(app, ["consistency"])
        assert result.exit_code == 1

    def test_reconcile_with_warnings_prints_them(self, ledger_repo: Path) -> None:
        with patch("specops.reconcile.run", return_value=(["warn1", "warn2"], [])), patch(
            "specops.cli.Path", return_value=ledger_repo
        ):
            result = runner.invoke(app, ["reconcile"])
        assert result.exit_code == 0
        assert "warn1" in result.output
        assert "warn2" in result.output

    def test_consistency_with_warnings_prints_them(self, ledger_repo: Path) -> None:
        with patch("specops.consistency.run", return_value=(["w1"], [])), patch(
            "specops.cli.Path", return_value=ledger_repo
        ):
            result = runner.invoke(app, ["consistency"])
        assert result.exit_code == 0
        assert "w1" in result.output
