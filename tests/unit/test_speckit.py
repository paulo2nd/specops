"""Unit tests for speckit.py — parsing and manifest resolution."""
import json
from pathlib import Path

import pytest

from specops import speckit

# ---------------------------------------------------------------------------
# has_speckit
# ---------------------------------------------------------------------------

def test_has_speckit_true(fake_speckit_repo: Path) -> None:
    assert speckit.has_speckit(fake_speckit_repo)


def test_has_speckit_false(tmp_path: Path) -> None:
    assert not speckit.has_speckit(tmp_path)


# ---------------------------------------------------------------------------
# resolve_feature_dir
# ---------------------------------------------------------------------------

def test_feature_dir_from_feature_json(fake_speckit_repo: Path) -> None:
    fd = speckit.resolve_feature_dir(fake_speckit_repo)
    assert fd is not None
    assert fd.name == "001-demo"


def test_feature_dir_fallback_to_newest_specs(tmp_path: Path) -> None:
    (tmp_path / ".specify" / "templates").mkdir(parents=True)
    (tmp_path / "specs" / "002-second").mkdir(parents=True)
    (tmp_path / "specs" / "001-first").mkdir(parents=True)
    fd = speckit.resolve_feature_dir(tmp_path)
    assert fd is not None
    assert fd.name == "002-second"


def test_feature_dir_numeric_ordering_9_vs_10(tmp_path: Path) -> None:
    """10-* must sort higher than 9-* (numeric, not lexicographic)."""
    (tmp_path / "specs" / "9-old").mkdir(parents=True)
    (tmp_path / "specs" / "10-new").mkdir(parents=True)
    fd = speckit.resolve_feature_dir(tmp_path)
    assert fd is not None
    assert fd.name == "10-new"


def test_feature_dir_numeric_ordering_large_numbers(tmp_path: Path) -> None:
    """100-* > 20-* > 9-*."""
    for name in ("9-a", "20-b", "100-c"):
        (tmp_path / "specs" / name).mkdir(parents=True)
    fd = speckit.resolve_feature_dir(tmp_path)
    assert fd is not None
    assert fd.name == "100-c"


def test_feature_dir_none_when_nothing(tmp_path: Path) -> None:
    assert speckit.resolve_feature_dir(tmp_path) is None


def test_feature_dir_invalid_json_falls_to_fallback(tmp_path: Path) -> None:
    (tmp_path / ".specify").mkdir()
    (tmp_path / ".specify" / "feature.json").write_text("NOT JSON")
    (tmp_path / "specs" / "001-demo").mkdir(parents=True)
    fd = speckit.resolve_feature_dir(tmp_path)
    assert fd is not None
    assert fd.name == "001-demo"


# ---------------------------------------------------------------------------
# extract_task_ids
# ---------------------------------------------------------------------------

def test_extract_task_ids_basic() -> None:
    text = "- [ ] T001 Do something\n- [X] T002 Already done\n- [ ] T003 Another"
    assert speckit.extract_task_ids(text) == ["T001", "T002", "T003"]


def test_extract_task_ids_skips_non_task_lines() -> None:
    text = "Some header\n- [ ] T005 valid\nRandom text"
    assert speckit.extract_task_ids(text) == ["T005"]


def test_extract_task_ids_empty() -> None:
    assert speckit.extract_task_ids("no tasks here") == []


# ---------------------------------------------------------------------------
# extract_sc_ids
# ---------------------------------------------------------------------------

def test_extract_sc_ids_basic() -> None:
    text = "- **SC-001**: passes\n- **SC-002**: second"
    assert speckit.extract_sc_ids(text) == ["SC-001", "SC-002"]


def test_extract_sc_ids_empty() -> None:
    assert speckit.extract_sc_ids("no criteria") == []


# ---------------------------------------------------------------------------
# extract_coverage_tags
# ---------------------------------------------------------------------------

def test_coverage_tags_single() -> None:
    line = "- [ ] T001 [SC-001] Do something"
    assert speckit.extract_coverage_tags(line) == ["SC-001"]


def test_coverage_tags_multiple() -> None:
    line = "- [ ] T002 [SC-001,SC-003] More work"
    assert speckit.extract_coverage_tags(line) == ["SC-001", "SC-003"]


def test_coverage_tags_none() -> None:
    assert speckit.extract_coverage_tags("- [ ] T003 No tags here") == []


# ---------------------------------------------------------------------------
# extract_action_suffixes
# ---------------------------------------------------------------------------

def test_action_suffix_create() -> None:
    text = "├── src/foo.py (create) — new module"
    pairs = speckit.extract_action_suffixes(text)
    assert len(pairs) == 1
    assert pairs[0][1] == "create"


def test_action_suffix_modify() -> None:
    text = "├── src/bar.py (modify) — update"
    pairs = speckit.extract_action_suffixes(text)
    assert pairs[0][1] == "modify"


def test_action_suffix_remove() -> None:
    text = "├── src/old.py (remove)"
    pairs = speckit.extract_action_suffixes(text)
    assert pairs[0][1] == "remove"


def test_action_suffix_mixed_line() -> None:
    text = "├── src/baz.py (create OR modify)"
    pairs = speckit.extract_action_suffixes(text)
    assert len(pairs) == 1


def test_action_suffix_missing_returns_empty() -> None:
    assert speckit.extract_action_suffixes("src/foo.py — no suffix") == []


# ---------------------------------------------------------------------------
# parse_plan_path_action (public helper, T016)
# ---------------------------------------------------------------------------

def test_parse_plan_path_action_create() -> None:
    line = "- `src/specops/errors.py` (create) — new module"
    result = speckit.parse_plan_path_action(line)
    assert result is not None
    assert result[0] == "src/specops/errors.py"
    assert result[1] == "create"


def test_parse_plan_path_action_modify() -> None:
    line = "- `src/specops/status.py` (modify) — fix transition"
    result = speckit.parse_plan_path_action(line)
    assert result is not None
    assert result[1] == "modify"


def test_parse_plan_path_action_remove() -> None:
    line = "- `src/specops/old.py` (remove)"
    result = speckit.parse_plan_path_action(line)
    assert result is not None
    assert result[1] == "remove"


def test_parse_plan_path_action_no_suffix_returns_none() -> None:
    assert speckit.parse_plan_path_action("src/foo.py — no suffix") is None


def test_parse_plan_path_action_no_path_returns_none() -> None:
    assert speckit.parse_plan_path_action("(create)") is None


# ---------------------------------------------------------------------------
# resolve_prompt_targets
# ---------------------------------------------------------------------------

def test_resolve_prompt_targets_success(fake_speckit_repo: Path) -> None:
    targets = speckit.resolve_prompt_targets(fake_speckit_repo)
    assert len(targets) == 1
    t = targets[0]
    assert t["integration"] == "claude"
    assert t["separator"] == "-"
    assert t["plan_path"].name == "SKILL.md"
    assert "speckit-plan" in str(t["plan_path"])
    assert "speckit-implement" in str(t["implement_path"])


def test_resolve_prompt_targets_missing_integration_json(tmp_path: Path) -> None:
    with pytest.raises(speckit.ManifestResolutionError, match="Missing"):
        speckit.resolve_prompt_targets(tmp_path)


def test_resolve_prompt_targets_missing_manifest(tmp_path: Path) -> None:
    (tmp_path / ".specify" / "integrations").mkdir(parents=True)
    integration = {
        "installed_integrations": ["claude"],
        "integration_settings": {"claude": {"invoke_separator": "-"}},
    }
    (tmp_path / ".specify" / "integration.json").write_text(json.dumps(integration))
    with pytest.raises(speckit.ManifestResolutionError, match="Missing manifest"):
        speckit.resolve_prompt_targets(tmp_path)


def test_resolve_prompt_targets_missing_file(fake_speckit_repo: Path) -> None:
    # Remove the plan SKILL.md
    (fake_speckit_repo / ".claude" / "skills" / "speckit-plan" / "SKILL.md").unlink()
    with pytest.raises(speckit.ManifestResolutionError, match="does not exist"):
        speckit.resolve_prompt_targets(fake_speckit_repo)


def test_resolve_prompt_targets_includes_specify_tasks(fake_speckit_repo: Path) -> None:
    """Full layout: specify_path and tasks_path resolve to existing prompts."""
    t = speckit.resolve_prompt_targets(fake_speckit_repo)[0]
    assert t["specify_path"] is not None
    assert "speckit-specify" in str(t["specify_path"])
    assert t["tasks_path"] is not None
    assert "speckit-tasks" in str(t["tasks_path"])


def test_resolve_prompt_targets_optional_none_when_absent(tmp_path: Path) -> None:
    """Partial layout (only plan/implement) → specify_path/tasks_path are None."""
    root = tmp_path
    (root / ".specify" / "integrations").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-plan").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-implement").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-plan" / "SKILL.md").write_text("# p\n")
    (root / ".claude" / "skills" / "speckit-implement" / "SKILL.md").write_text("# i\n")
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
    t = speckit.resolve_prompt_targets(root)[0]
    assert t["specify_path"] is None
    assert t["tasks_path"] is None


def test_resolve_tasks_not_confused_by_taskstoissues(fake_speckit_repo: Path) -> None:
    """Full layout: role='tasks' resolves to speckit-tasks, never speckit-taskstoissues."""
    t = speckit.resolve_prompt_targets(fake_speckit_repo)[0]
    assert t["tasks_path"] is not None
    assert t["tasks_path"].parent.name == "speckit-tasks"
    assert "taskstoissues" not in str(t["tasks_path"])


def test_resolve_tasks_none_when_only_taskstoissues_present(tmp_path: Path) -> None:
    """Regression: 'speckit-tasks' substring must not match 'speckit-taskstoissues'.

    Partial layout with taskstoissues but no tasks prompt → tasks_path is None,
    NOT the taskstoissues file.
    """
    root = tmp_path
    (root / ".specify" / "integrations").mkdir(parents=True)
    for name in ("speckit-plan", "speckit-implement", "speckit-taskstoissues"):
        d = root / ".claude" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# prompt\n")
    (root / ".specify" / "integration.json").write_text(json.dumps({
        "installed_integrations": ["claude"],
        "integration_settings": {"claude": {"invoke_separator": "-"}},
    }))
    (root / ".specify" / "integrations" / "claude.manifest.json").write_text(json.dumps({
        "integration": "claude",
        "files": {
            ".claude/skills/speckit-plan/SKILL.md": "-",
            ".claude/skills/speckit-implement/SKILL.md": "-",
            ".claude/skills/speckit-taskstoissues/SKILL.md": "-",
        },
    }))
    t = speckit.resolve_prompt_targets(root)[0]
    assert t["tasks_path"] is None


# ---------------------------------------------------------------------------
# derive_review_path
# ---------------------------------------------------------------------------

def test_derive_review_path(fake_speckit_repo: Path) -> None:
    plan_path = fake_speckit_repo / ".claude" / "skills" / "speckit-plan" / "SKILL.md"
    review = speckit.derive_review_path(plan_path, fake_speckit_repo, sep="-")
    assert str(review).endswith(".claude/skills/specops-review/SKILL.md")
