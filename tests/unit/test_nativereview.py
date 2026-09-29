"""Native code review per integration (Feature 028)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specops import compat, extension, initializer, nativereview

_CLAUDE_REVIEW = Path(".claude/skills/specops-review/SKILL.md")
_LEGACY_WORDING = ("If your environment provides", "e.g. the `/code-review`")


@pytest.fixture()
def compat_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compat, "installed_version", lambda: compat.MIN_CLI_VERSION)


# --- Phase 2: one render, both install paths --------------------------------------


def test_render_leaves_no_placeholder(fake_speckit_repo: Path) -> None:
    assert "{{" not in nativereview.render_review(fake_speckit_repo, "claude")


def test_init_and_extension_install_write_identical_review(
    fake_speckit_repo: Path, tmp_path: Path, compat_ok: None
) -> None:
    """Principle IV: both install paths source the review command identically."""
    other = tmp_path / "native"
    shutil.copytree(fake_speckit_repo, other)
    initializer.run(fake_speckit_repo, non_interactive=True)
    extension.install(other)
    assert (fake_speckit_repo / _CLAUDE_REVIEW).read_text() == (other / _CLAUDE_REVIEW).read_text()


# --- US1: the Claude Code copy names and requires /code-review --------------------


def test_claude_step_3a_is_unconditional_and_mandatory(fake_speckit_repo: Path) -> None:
    text = nativereview.render_review(fake_speckit_repo, "claude")
    for phrase in (
        "/code-review",
        "the Skill tool",
        'Skill(skill: "code-review", args: "high ',
        "reviewed_range",
        "ultra",
        "--fix",
        "If you delegate this review to a subagent, that subagent must have the Skill tool",
        "native review not run",
        '--rule "native-review-not-run"',
        "specops handoff finding add --severity blocking",
        "import-json",
    ):
        assert phrase in text, phrase
    for legacy in _LEGACY_WORDING:
        assert legacy not in text


# --- US2: integrations without a native reviewer get an honest instruction ------


@pytest.mark.parametrize("integration", ["gemini", "some-future-id"])
def test_unmapped_integration_renders_no_native_review(
    fake_speckit_repo: Path, integration: str
) -> None:
    text = nativereview.render_review(fake_speckit_repo, integration)
    assert f"This integration (`{integration}`) has no native code-review command" in text
    for absent in ("/code-review", "native-review-not-run", "Skill tool", *_LEGACY_WORDING):
        assert absent not in text, absent


def test_builtin_map_is_claude_only() -> None:
    """SC-003: every built-in entry is backed by research.md R1. A new entry must
    update that evidence and this assertion together."""
    assert set(nativereview.BUILTIN) == {"claude"}
