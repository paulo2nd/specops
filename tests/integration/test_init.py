"""Integration tests for specops init — Quickstart Scenario A."""
import json
import subprocess
import time
from pathlib import Path

import pytest

from specops import initializer, speckit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_init(repo: Path, non_interactive: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["specops", "init", "--non-interactive"] if non_interactive else ["specops", "init"],
        cwd=repo,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Scenario A-1: no-git non-interactive decline → exit 1, < 1 s (SC-008)
# ---------------------------------------------------------------------------

def test_init_no_git_non_interactive_fails_fast(tmp_path: Path) -> None:
    """Step 1: no git repo + --non-interactive → exit 1 in < 1 s."""
    (tmp_path / ".specify" / "templates").mkdir(parents=True)
    start = time.monotonic()
    result = run_init(tmp_path, non_interactive=True)
    elapsed = time.monotonic() - start
    assert result.returncode == 1
    assert elapsed < 1.0


# ---------------------------------------------------------------------------
# Scenario A-2: no-speckit → exit 1
# ---------------------------------------------------------------------------

def test_init_no_speckit_fails(fake_speckit_repo: Path) -> None:
    """Speckit detection: abort when .specify/templates/ is missing."""
    import shutil
    shutil.rmtree(fake_speckit_repo / ".specify" / "templates")
    result = run_init(fake_speckit_repo)
    assert result.returncode == 1
    assert "Speckit" in result.stderr


# ---------------------------------------------------------------------------
# Scenario A-3: fresh init → exit 0, files created
# ---------------------------------------------------------------------------

def test_init_fresh_creates_files(fake_speckit_repo: Path) -> None:
    """Step 2: fresh init creates specops.json and review command; both prompts get blocks."""
    result = run_init(fake_speckit_repo)
    assert result.returncode == 0, result.stderr

    # specops.json created
    assert (fake_speckit_repo / "specops.json").is_file()

    # review command installed at expected path
    review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
    assert review_path.is_file()

    # plan prompt has SPECOPS:BEGIN plan block
    plan_text = (fake_speckit_repo / ".claude" / "skills" / "speckit-plan" / "SKILL.md").read_text()
    assert "<!-- SPECOPS:BEGIN plan" in plan_text
    assert "<!-- SPECOPS:END plan -->" in plan_text

    # implement prompt has SPECOPS:BEGIN implement block
    impl_text = (fake_speckit_repo / ".claude" / "skills" / "speckit-implement" / "SKILL.md").read_text()
    assert "<!-- SPECOPS:BEGIN implement" in impl_text
    assert "<!-- SPECOPS:END implement -->" in impl_text


# ---------------------------------------------------------------------------
# Scenario A-4: idempotent re-run → no duplicate blocks (SC-005)
# ---------------------------------------------------------------------------

def test_init_idempotent_no_duplicate_blocks(fake_speckit_repo: Path) -> None:
    """Step 3: re-running init must not duplicate directive blocks."""
    run_init(fake_speckit_repo)
    run_init(fake_speckit_repo)

    plan_text = (fake_speckit_repo / ".claude" / "skills" / "speckit-plan" / "SKILL.md").read_text()
    assert plan_text.count("<!-- SPECOPS:BEGIN plan") == 1
    assert plan_text.count("<!-- SPECOPS:END plan -->") == 1


# ---------------------------------------------------------------------------
# Scenario A-5: byte-identical restore (SC-010)
# ---------------------------------------------------------------------------

def test_init_block_removal_restores_original(fake_speckit_repo: Path) -> None:
    """Step 4: removing appended block region → byte-identical original."""
    plan_path = fake_speckit_repo / ".claude" / "skills" / "speckit-plan" / "SKILL.md"
    original = plan_path.read_text()

    run_init(fake_speckit_repo)
    assert plan_path.read_text() != original  # block appended

    from specops.initializer import remove_block
    remove_block(plan_path, "plan")
    assert plan_path.read_text() == original  # byte-identical restore


def test_init_block_removal_restores_implement_original(fake_speckit_repo: Path) -> None:
    impl_path = fake_speckit_repo / ".claude" / "skills" / "speckit-implement" / "SKILL.md"
    original = impl_path.read_text()

    run_init(fake_speckit_repo)
    from specops.initializer import remove_block
    remove_block(impl_path, "implement")
    assert impl_path.read_text() == original


# ---------------------------------------------------------------------------
# Scenario A-6: missing manifest → exit 1, nothing written (R2)
# ---------------------------------------------------------------------------

def test_init_missing_manifest_fails_closed(fake_speckit_repo: Path) -> None:
    """Step 6: missing manifest → exit 1, zero files written."""
    manifest = fake_speckit_repo / ".specify" / "integrations" / "claude.manifest.json"
    manifest.unlink()

    plan_path = fake_speckit_repo / ".claude" / "skills" / "speckit-plan" / "SKILL.md"
    original_plan = plan_path.read_text()

    result = run_init(fake_speckit_repo)
    assert result.returncode == 1
    # original file unchanged
    assert plan_path.read_text() == original_plan
    # specops.json may or may not exist; what matters: no block injection


# ---------------------------------------------------------------------------
# Scenario A-7: second integration (dotted layout) also injected
# ---------------------------------------------------------------------------

def test_init_second_integration_dotted_layout(fake_speckit_repo: Path) -> None:
    """A second integration with dot separator also gets directive blocks."""
    # Add a second integration: 'copilot' with dot separator and .md layout
    (fake_speckit_repo / ".github" / "prompts").mkdir(parents=True)
    plan_md = fake_speckit_repo / ".github" / "prompts" / "speckit.plan.md"
    impl_md = fake_speckit_repo / ".github" / "prompts" / "speckit.implement.md"
    plan_md.write_text("# copilot plan\n")
    impl_md.write_text("# copilot implement\n")

    # Update integration.json to include copilot
    integration = {
        "installed_integrations": ["claude", "copilot"],
        "integration_settings": {
            "claude": {"invoke_separator": "-"},
            "copilot": {"invoke_separator": "."},
        },
    }
    (fake_speckit_repo / ".specify" / "integration.json").write_text(json.dumps(integration))

    copilot_manifest = {
        "integration": "copilot",
        "files": {
            ".github/prompts/speckit.plan.md": ".",
            ".github/prompts/speckit.implement.md": ".",
        },
    }
    (fake_speckit_repo / ".specify" / "integrations" / "copilot.manifest.json").write_text(
        json.dumps(copilot_manifest)
    )

    result = run_init(fake_speckit_repo)
    assert result.returncode == 0, result.stderr

    assert "<!-- SPECOPS:BEGIN plan" in plan_md.read_text()
    assert "<!-- SPECOPS:BEGIN implement" in impl_md.read_text()

    # Copilot review command uses dot separator
    review_path = fake_speckit_repo / ".github" / "prompts" / "specops.review.md"
    assert review_path.is_file()


# ---------------------------------------------------------------------------
# Scenario A-8: config merge preservation
# ---------------------------------------------------------------------------

def test_init_config_merge_preserves_user_values(fake_speckit_repo: Path) -> None:
    """Existing specops.json user values are preserved on re-init."""
    cfg_path = fake_speckit_repo / "specops.json"
    cfg_path.write_text(json.dumps({"test_command": "my_runner", "custom_key": "custom_val"}))

    run_init(fake_speckit_repo)

    cfg = json.loads(cfg_path.read_text())
    assert cfg["test_command"] == "my_runner"
    assert cfg["custom_key"] == "custom_val"
    # template keys filled
    assert "lint_command" in cfg
