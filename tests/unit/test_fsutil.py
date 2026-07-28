"""Unit tests for fsutil.atomic_write — the single durable-write path (#25)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from specops import fsutil
from specops.errors import SpecopsError


def test_writes_content_utf8(tmp_path: Path) -> None:
    target = tmp_path / "out.md"
    fsutil.atomic_write(target, "línea → ok\n")
    assert target.read_text(encoding="utf-8") == "línea → ok\n"


def test_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.md"
    target.write_text("old\n", encoding="utf-8")
    fsutil.atomic_write(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_creates_missing_parent(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "out.md"
    fsutil.atomic_write(target, "x\n")
    assert target.read_text(encoding="utf-8") == "x\n"


def test_failed_promotion_leaves_target_intact_and_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure before promotion never touches the target or leaks a temp file."""
    target = tmp_path / "out.md"
    target.write_text("original\n", encoding="utf-8")

    def boom(src: str, dst: str) -> None:
        raise OSError("simulated crash at promotion")

    monkeypatch.setattr(fsutil.os, "replace", boom)
    with pytest.raises(OSError, match="simulated crash"):
        fsutil.atomic_write(target, "partial\n")
    assert target.read_text(encoding="utf-8") == "original\n"
    assert [p.name for p in tmp_path.iterdir()] == ["out.md"]


def test_no_temp_left_behind_on_success(tmp_path: Path) -> None:
    target = tmp_path / "out.md"
    fsutil.atomic_write(target, "x\n")
    assert [p.name for p in tmp_path.iterdir()] == ["out.md"]


def test_fsync_failure_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A write that cannot be made durable fails loudly, leaving the target alone."""
    target = tmp_path / "out.md"
    target.write_text("original\n", encoding="utf-8")

    real_fsync = os.fsync

    def boom(fd: int) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(fsutil.os, "fsync", boom)
    try:
        with pytest.raises(OSError, match="simulated fsync"):
            fsutil.atomic_write(target, "partial\n")
    finally:
        monkeypatch.setattr(fsutil.os, "fsync", real_fsync)
    assert target.read_text(encoding="utf-8") == "original\n"
    assert [p.name for p in tmp_path.iterdir()] == ["out.md"]


# ---------------------------------------------------------------------------
# Feature 019 US4 (FR-010/SC-006): render_template asserts placeholder
# completeness — template drift fails loudly, never silent {{...}} residue.
# ---------------------------------------------------------------------------


def test_render_template_fills_every_placeholder() -> None:
    out = fsutil.render_template(
        "feature: {{feature-name}}\nbranch: {{branch}}\n",
        {"feature-name": "001-demo", "branch": "main"},
    )
    assert out == "feature: 001-demo\nbranch: main\n"
    assert "{{" not in out


def test_render_template_extra_mapping_keys_are_ignored() -> None:
    out = fsutil.render_template("id: {{lane-id}}\n", {"lane-id": "x", "unused": "y"})
    assert out == "id: x\n"


def test_render_template_drift_fails_loudly_naming_the_placeholder() -> None:
    with pytest.raises(SpecopsError) as exc:
        fsutil.render_template(
            "a: {{known}}\nb: {{new-placeholder}}\n", {"known": "v"}
        )
    assert "{{new-placeholder}}" in str(exc.value)
    assert "{{known}}" not in str(exc.value)  # filled keys are not reported


def test_render_template_repeated_placeholders_all_fill() -> None:
    out = fsutil.render_template("{{ts}} and {{ts}}", {"ts": "T"})
    assert out == "T and T"


def test_render_template_value_with_braces_is_literal_not_drift() -> None:
    # A branch/feature name containing a {{...}} sequence is a legal value: it must
    # be inserted literally, never flagged as unfilled residue (would crash a valid
    # `init-spec`/`lane start`) nor re-substituted by a later key.
    out = fsutil.render_template(
        "branch: {{branch}}\nts: {{ts}}\n",
        {"branch": "fix/{{ts}}", "ts": "2026"},
    )
    assert out == "branch: fix/{{ts}}\nts: 2026\n"


def test_render_template_value_with_unknown_brace_token_is_not_flagged() -> None:
    out = fsutil.render_template("name: {{name}}\n", {"name": "foo{{x}}"})
    assert out == "name: foo{{x}}\n"
