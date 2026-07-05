"""
Shared pytest fixtures: temporary Git repository and fake Speckit layout.
"""
import json
import subprocess
from pathlib import Path

import pytest


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

    # Claude skills prompts
    (root / ".claude" / "skills" / "speckit-plan").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-implement").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-plan" / "SKILL.md").write_text("# plan prompt\n")
    (root / ".claude" / "skills" / "speckit-implement" / "SKILL.md").write_text("# implement prompt\n")

    # Speckit integration records
    integration = {
        "installed_integrations": ["claude"],
        "integration_settings": {"claude": {"invoke_separator": "-"}},
    }
    (root / ".specify" / "integration.json").write_text(json.dumps(integration))

    manifest = {
        "integration": "claude",
        "files": {
            ".claude/skills/speckit-plan/SKILL.md": "-",
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
