"""
Shared pytest fixtures: temporary Git repository and fake Speckit layout.
"""
import datetime
import json
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.fixture()
def tmp_git_repo(tmp_path: Path) -> Path:
    """Return a path to a freshly initialised Git repository."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    readme = tmp_path / "README.md"
    readme.write_text("# test\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


@pytest.fixture()
def fake_speckit_repo(tmp_git_repo: Path) -> Path:
    """
    Return a Git repo with a minimal Speckit layout (Claude skills mode,
    invoke separator '-') including integration.json and a claude manifest.
    """
    root = tmp_git_repo

    # Speckit core dirs
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "integrations").mkdir(parents=True)

    # Claude skills prompts (full layout: specify, plan, tasks, implement)
    (root / ".claude" / "skills" / "speckit-specify").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-plan").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-tasks").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-implement").mkdir(parents=True)
    # speckit-taskstoissues shares the 'speckit-tasks' prefix — kept in the
    # fixture so resolution must not confuse it with the tasks prompt.
    (root / ".claude" / "skills" / "speckit-taskstoissues").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-specify" / "SKILL.md").write_text("# specify prompt\n")
    (root / ".claude" / "skills" / "speckit-plan" / "SKILL.md").write_text("# plan prompt\n")
    (root / ".claude" / "skills" / "speckit-tasks" / "SKILL.md").write_text("# tasks prompt\n")
    (root / ".claude" / "skills" / "speckit-taskstoissues" / "SKILL.md").write_text(
        "# taskstoissues prompt\n"
    )
    (root / ".claude" / "skills" / "speckit-implement" / "SKILL.md").write_text(
        "# implement prompt\n"
    )

    # Speckit integration records
    integration = {
        "installed_integrations": ["claude"],
        "integration_settings": {"claude": {"invoke_separator": "-"}},
    }
    (root / ".specify" / "integration.json").write_text(json.dumps(integration))

    manifest = {
        "integration": "claude",
        "files": {
            ".claude/skills/speckit-specify/SKILL.md": "-",
            ".claude/skills/speckit-plan/SKILL.md": "-",
            ".claude/skills/speckit-tasks/SKILL.md": "-",
            ".claude/skills/speckit-taskstoissues/SKILL.md": "-",
            ".claude/skills/speckit-implement/SKILL.md": "-",
        },
    }
    (root / ".specify" / "integrations" / "claude.manifest.json").write_text(
        json.dumps(manifest)
    )

    # feature.json pointing to specs/001-demo
    (root / "specs" / "001-demo").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )

    return root


@pytest.fixture()
def ledger_in_review(tmp_git_repo: Path) -> Path:
    """Feature repo with status.yaml at REVIEW phase, one open review cycle."""
    root = tmp_git_repo
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-review-test"})
    )
    feature_dir = root / "specs" / "001-review-test"
    feature_dir.mkdir(parents=True)

    data = {
        "feature": "001-review-test",
        "branch": "main",
        "baseline": "abc1234",
        "created_at": str(datetime.date.today()),
        "updated_at": str(datetime.date.today()),
        "current_phase": "REVIEW",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [],
        "review_cycles": [
            {
                "round": 1,
                "started_at": str(datetime.date.today()),
                "completed_at": None,
                "result": None,
            }
        ],
    }
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    return root


def read_ledger(feature_dir: Path) -> dict:
    """Read and return the ledger YAML from feature_dir/status.yaml."""
    return yaml.safe_load((feature_dir / "status.yaml").read_text(encoding="utf-8"))
