"""Integration tests for the installed /specops-review asset (US5 T033; 004 US2)."""
import subprocess
from pathlib import Path

import pytest


def _run_init(repo: Path) -> None:
    subprocess.run(
        ["specops", "init", "--non-interactive"], cwd=repo, check=True, capture_output=True
    )


@pytest.fixture()
def installed_review(fake_speckit_repo: Path) -> str:
    """Run specops init and return the installed review prompt content."""
    _run_init(fake_speckit_repo)
    review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
    assert review_path.is_file()
    return review_path.read_text()


class TestReviewAsset:
    def test_review_skill_installed_at_correct_path(self, fake_speckit_repo: Path) -> None:
        """Post-init, review command is at the layout-derived path."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        assert review_path.is_file()

    def test_review_skill_has_frontmatter(self, installed_review: str) -> None:
        """Skills-mode review file has YAML frontmatter."""
        assert installed_review.startswith("---\n")
        assert "description:" in installed_review

    def test_review_contains_collapsed_gate_step(self, installed_review: str) -> None:
        """The gate step delegates to the CLI: run specops review."""
        assert "specops review" in installed_review

    def test_review_gate_step_rejects_on_nonzero_exit(self, installed_review: str) -> None:
        """Non-zero exit → REJECTED, report output, stop without reading code."""
        assert "REJECTED" in installed_review
        assert "Do not read any code" in installed_review

    def test_review_no_individual_reconcile_instruction(self, installed_review: str) -> None:
        """The agent is no longer told to run reconcile itself (CLI owns it)."""
        assert "specops reconcile" not in installed_review

    def test_review_no_individual_lint_test_instruction(self, installed_review: str) -> None:
        """The agent is no longer told to run lint/test commands itself."""
        assert "lint_command" not in installed_review
        assert "test_command" not in installed_review

    def test_review_no_individual_porcelain_instruction(self, installed_review: str) -> None:
        """The agent is no longer told to run git status --porcelain itself."""
        assert "git status --porcelain" not in installed_review

    def test_review_gate_step_before_surgical_review(self, installed_review: str) -> None:
        """The CLI gate step appears before the surgical diff review step."""
        gate_pos = installed_review.find("specops review")
        surgical_pos = installed_review.find("Surgical Diff Review")
        assert gate_pos != -1 and surgical_pos != -1
        assert gate_pos < surgical_pos

    def test_review_contains_revision_report_format(self, installed_review: str) -> None:
        """Review prompt keeps the [File]:[Line] - ... finding format."""
        assert "[File]:[Line]" in installed_review

    def test_review_contains_revision_numbering(self, installed_review: str) -> None:
        """Review prompt keeps revisions/revision-X.md max+1 numbering."""
        assert "revision" in installed_review.lower()

    def test_review_keeps_verdict_transition(self, installed_review: str) -> None:
        """Verdict transition stays agent-driven (unchanged in 004)."""
        assert "transition-phase DONE" in installed_review
        assert "transition-phase IMPLEMENT" in installed_review

    def test_review_keeps_active_learning(self, installed_review: str) -> None:
        """Active Learning section is unchanged."""
        assert "Active Learning" in installed_review
