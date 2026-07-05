"""Integration test for multi-stack behaviour (T039, SC-006, FR-015)."""
import json
import subprocess
from pathlib import Path

import yaml


def _make_repo(tmp_path: Path, suffix: str, test_cmd: str, lint_cmd: str) -> Path:
    """Create a Speckit-like sandbox with the given specops.json settings."""
    root = tmp_path / f"repo-{suffix}"
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
    (root / ".specify" / "integrations").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-plan").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-implement").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-plan" / "SKILL.md").write_text("# plan\n")
    (root / ".claude" / "skills" / "speckit-implement" / "SKILL.md").write_text("# implement\n")

    (root / ".specify" / "integration.json").write_text(json.dumps({
        "installed_integrations": ["claude"],
        "integration_settings": {"claude": {"invoke_separator": "-"}},
    }))
    (root / ".specify" / "integrations" / "claude.manifest.json").write_text(json.dumps({
        "integration": "claude",
        "files": {
            ".claude/skills/speckit-plan/SKILL.md": "-",
            ".claude/skills/speckit-implement/SKILL.md": "-",
        },
    }))

    feature_dir = root / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )
    (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")

    # Stack-specific specops.json
    (root / "specops.json").write_text(json.dumps({
        "test_command": test_cmd,
        "lint_command": lint_cmd,
        "skills_dir": ".specify/skills",
    }))
    return root


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=repo, capture_output=True, text=True)


def _commit(repo: Path, msg: str = "work") -> str:
    (repo / f"{msg}.txt").write_text(msg)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()


class TestMultiStack:
    def test_two_stacks_behave_identically(self, tmp_path: Path) -> None:
        """Two repos with different test/lint commands but identical SpecOps flow
        (SC-006, FR-015)."""
        npm = _make_repo(tmp_path, "npm", test_cmd="true", lint_cmd="true")
        pytest_repo = _make_repo(tmp_path, "pytest", test_cmd="true", lint_cmd="")

        for repo in [npm, pytest_repo]:
            # init
            r = _run(repo, "init", "--non-interactive")
            assert r.returncode == 0, f"{repo.name}: init failed: {r.stderr}"

            # init-spec
            r = _run(repo, "status", "init-spec")
            assert r.returncode == 0, f"{repo.name}: init-spec failed: {r.stderr}"

            # start T001
            r = _run(repo, "status", "start-task", "T001")
            assert r.returncode == 0, f"{repo.name}: start-task failed: {r.stderr}"

            # commit work
            _commit(repo, "T001-work")

            # complete T001 --auto (both have test_command=true)
            r = _run(repo, "status", "complete-task", "T001", "--auto")
            assert r.returncode == 0, f"{repo.name}: complete-task failed: {r.stderr}"

            # reconcile
            r = _run(repo, "reconcile")
            assert r.returncode == 0, f"{repo.name}: reconcile failed: {r.stderr}"

            # Verify ledger state
            ledger = yaml.safe_load(
                (repo / "specs" / "001-demo" / "status.yaml").read_text()
            )
            t001 = next(t for t in ledger["tasks"] if t["id"] == "T001")
            assert t001["status"] == "DONE"
            assert t001["evidence"] is not None
