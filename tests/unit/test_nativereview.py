"""Native code review per integration (Feature 028)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from specops import config, extension, initializer, nativereview

_CLAUDE_REVIEW = Path(".claude/skills/specops-review/SKILL.md")
_LEGACY_WORDING = ("If your environment provides", "e.g. the `/code-review`")



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


# --- US3: projects override the map in specops.json ------------------------------


def _config(root: Path, native_review: object) -> None:
    (root / "specops.json").write_text(json.dumps({"native_review": native_review}))


def test_no_specops_json_uses_builtin_defaults(fake_speckit_repo: Path) -> None:
    assert not (fake_speckit_repo / "specops.json").exists()
    assert 'args: "high ' in nativereview.render_review(fake_speckit_repo, "claude")


@pytest.mark.parametrize(
    ("block", "integration", "present", "absent"),
    [
        ({}, "claude", 'args: "high ', "has no native"),
        ({"claude": {"effort": "max"}}, "claude", 'args: "max ', 'args: "high '),
        ({"claude": {"command": None}}, "claude", "(`claude`) has no native", "Skill tool"),
        (
            {"gemini": {"command": "/code-review"}},
            "gemini",
            "`/code-review` (configured in `specops.json`)",
            "has no native",
        ),
        ({"gemini": {"command": "/x"}}, "gemini", "your integration's own mechanism", "args:"),
        # an entry for another (maybe uninstalled) integration is ignored
        ({"qwen": {"effort": "bogus"}}, "claude", 'args: "high ', "has no native"),
    ],
)
def test_native_review_overrides_resolve(
    fake_speckit_repo: Path, block: dict, integration: str, present: str, absent: str
) -> None:
    _config(fake_speckit_repo, block)
    text = nativereview.render_review(fake_speckit_repo, integration)
    assert present in text
    assert absent not in text


@pytest.mark.parametrize(
    ("block", "integration", "key"),
    [
        ([], "claude", "native_review "),
        ({"claude": "x"}, "claude", "native_review.claude "),
        ({"claude": {"efort": "high"}}, "claude", "efort"),
        ({"claude": {"command": ""}}, "claude", "native_review.claude.command"),
        ({"claude": {"command": 3}}, "claude", "native_review.claude.command"),
        ({"claude": {"effort": "ultra"}}, "claude", "native_review.claude.effort"),
        ({"claude": {"effort": "turbo"}}, "claude", "native_review.claude.effort"),
        ({"gemini": {"effort": "high"}}, "gemini", "native_review.gemini.effort"),
        ({"claude": {"command": "/x", "effort": "high"}}, "claude", "native_review.claude.effort"),
    ],
)
def test_invalid_native_review_raises_config_error(
    fake_speckit_repo: Path, block: object, integration: str, key: str
) -> None:
    _config(fake_speckit_repo, block)
    with pytest.raises(config.ConfigError, match=key.replace(".", r"\.")):
        nativereview.render_review(fake_speckit_repo, integration)


def test_native_review_is_not_a_written_default(fake_speckit_repo: Path) -> None:
    """Research R4: the frozen specops.json defaults stay untouched (Feature 021)."""
    assert "native_review" not in config._DEFAULTS
    config.create_or_merge(fake_speckit_repo)
    assert "native_review" not in json.loads((fake_speckit_repo / "specops.json").read_text())


def test_override_command_is_shell_escaped_in_not_run_snippet(fake_speckit_repo: Path) -> None:
    _config(fake_speckit_repo, {"gemini": {"command": 'rev "a" `x` $y'}})
    text = nativereview.render_review(fake_speckit_repo, "gemini")
    assert 'not run: rev \\"a\\" \\`x\\` \\$y (<reason>)"' in text


def test_non_object_specops_json_raises_config_error(fake_speckit_repo: Path) -> None:
    (fake_speckit_repo / "specops.json").write_text("[]")
    with pytest.raises(config.ConfigError, match="JSON object"):
        nativereview.render_review(fake_speckit_repo, "claude")
