"""Integration tests for the installed /specops-review asset (US5, T033)."""
import subprocess
from pathlib import Path

import pytest


def _run_init(repo: Path) -> None:
    subprocess.run(["specops", "init", "--non-interactive"], cwd=repo, check=True, capture_output=True)


class TestReviewAsset:
    def test_review_skill_installed_at_correct_path(self, fake_speckit_repo: Path) -> None:
        """Post-init, review command is at the layout-derived path."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        assert review_path.is_file()

    def test_review_skill_has_frontmatter(self, fake_speckit_repo: Path) -> None:
        """Skills-mode review file has YAML frontmatter."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        content = review_path.read_text()
        assert content.startswith("---\n")
        assert "description:" in content

    def test_review_contains_reconcile_abort(self, fake_speckit_repo: Path) -> None:
        """Review prompt includes the reconcile-first abort directive."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        content = review_path.read_text()
        assert "specops reconcile" in content

    def test_review_contains_lint_test_prefilter(self, fake_speckit_repo: Path) -> None:
        """Review prompt includes lint/test pre-filter."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        content = review_path.read_text()
        assert "lint_command" in content or "test_command" in content

    def test_review_contains_porcelain_scope_check(self, fake_speckit_repo: Path) -> None:
        """Review prompt includes git status --porcelain scope check."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        content = review_path.read_text()
        assert "git status --porcelain" in content

    def test_review_contains_revision_report_format(self, fake_speckit_repo: Path) -> None:
        """Review prompt contains the [File]:[Line] - ... finding format."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        content = review_path.read_text()
        assert "[File]:[Line]" in content

    def test_review_contains_revision_numbering(self, fake_speckit_repo: Path) -> None:
        """Review prompt mentions revisions/revision-X.md max+1 numbering."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        content = review_path.read_text()
        assert "revision" in content.lower()

    def test_review_step_order_reconcile_before_lint(self, fake_speckit_repo: Path) -> None:
        """Reconcile step must appear before lint/test step in the review prompt."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        content = review_path.read_text()
        reconcile_pos = content.find("specops reconcile")
        lint_pos = content.find("lint_command")
        if lint_pos == -1:
            lint_pos = content.find("test_command")
        assert reconcile_pos < lint_pos, "Reconcile must come before lint/test in review prompt"

    def test_review_empty_diff_rejected(self, fake_speckit_repo: Path) -> None:
        """Review prompt must instruct rejection on empty diff."""
        _run_init(fake_speckit_repo)
        review_path = fake_speckit_repo / ".claude" / "skills" / "specops-review" / "SKILL.md"
        content = review_path.read_text()
        assert "empty diff" in content or "no effective diff" in content or "No changed files" in content
