"""Unit tests for the SPECOPS marker-injection engine."""
from pathlib import Path

import pytest

from specops.initializer import InjectionError, _scan_markers, inject_block, remove_block


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _scan_markers
# ---------------------------------------------------------------------------

def test_scan_markers_empty_file() -> None:
    assert _scan_markers("") == []


def test_scan_markers_clean_block() -> None:
    text = "# header\n\n<!-- SPECOPS:BEGIN plan v1 -->\ncontent\n<!-- SPECOPS:END plan -->\n"
    regions = _scan_markers(text)
    assert len(regions) == 1
    assert regions[0][0] == "plan"


def test_scan_markers_begin_without_end_raises() -> None:
    text = "<!-- SPECOPS:BEGIN plan v1 -->\ncontent without end\n"
    with pytest.raises(InjectionError, match="without matching END"):
        _scan_markers(text)


def test_scan_markers_end_without_begin_raises() -> None:
    text = "<!-- SPECOPS:END plan -->\n"
    with pytest.raises(InjectionError, match="without matching BEGIN"):
        _scan_markers(text)


def test_scan_markers_duplicate_begin_raises() -> None:
    text = (
        "<!-- SPECOPS:BEGIN plan v1 -->\n"
        "<!-- SPECOPS:BEGIN plan v1 -->\n"
        "<!-- SPECOPS:END plan -->\n"
    )
    with pytest.raises(InjectionError, match="duplicate BEGIN"):
        _scan_markers(text)


def test_scan_markers_nested_raises() -> None:
    text = (
        "<!-- SPECOPS:BEGIN plan v1 -->\n"
        "<!-- SPECOPS:BEGIN implement v1 -->\n"
        "<!-- SPECOPS:END plan -->\n"
        "<!-- SPECOPS:END implement -->\n"
    )
    with pytest.raises(InjectionError, match="nested BEGIN"):
        _scan_markers(text)


# ---------------------------------------------------------------------------
# inject_block — clean append
# ---------------------------------------------------------------------------

def test_inject_block_appends_to_clean_file(tmp_path: Path) -> None:
    p = _write(tmp_path, "SKILL.md", "# original content\n")
    result = inject_block(p, "plan", "directive text")
    assert result == "created"
    text = p.read_text()
    assert "<!-- SPECOPS:BEGIN plan v1 -->" in text
    assert "<!-- SPECOPS:END plan -->" in text
    assert text.startswith("# original content")


def test_inject_block_original_bytes_before_block_unchanged(tmp_path: Path) -> None:
    original = "# header\nsome text\n"
    p = _write(tmp_path, "SKILL.md", original)
    inject_block(p, "plan", "new content")
    text = p.read_text()
    assert text.startswith(original)


def test_inject_block_two_blocks_independent(tmp_path: Path) -> None:
    p = _write(tmp_path, "SKILL.md", "# header\n")
    inject_block(p, "plan", "plan content")
    inject_block(p, "implement", "implement content")
    text = p.read_text()
    assert "SPECOPS:BEGIN plan" in text
    assert "SPECOPS:BEGIN implement" in text


# ---------------------------------------------------------------------------
# inject_block — in-place update
# ---------------------------------------------------------------------------

def test_inject_block_updates_existing(tmp_path: Path) -> None:
    p = _write(tmp_path, "SKILL.md", "# header\n")
    inject_block(p, "plan", "old content")
    result = inject_block(p, "plan", "new content")
    assert result == "updated"
    text = p.read_text()
    assert "new content" in text
    assert "old content" not in text


def test_inject_block_unchanged_when_same_content(tmp_path: Path) -> None:
    p = _write(tmp_path, "SKILL.md", "# header\n")
    inject_block(p, "plan", "same content")
    result = inject_block(p, "plan", "same content")
    assert result == "unchanged"


def test_inject_block_version_bump_triggers_update(tmp_path: Path) -> None:
    p = _write(tmp_path, "SKILL.md", "# header\n")
    inject_block(p, "plan", "content", version=1)
    result = inject_block(p, "plan", "content", version=2)
    assert result in ("updated",)


# ---------------------------------------------------------------------------
# remove_block
# ---------------------------------------------------------------------------

def test_remove_block_restores_original_bytes(tmp_path: Path) -> None:
    original = "# original prompt\n"
    p = _write(tmp_path, "SKILL.md", original)
    inject_block(p, "plan", "directive content")
    assert p.read_text() != original
    remove_block(p, "plan")
    assert p.read_text() == original


def test_remove_block_not_present_returns_false(tmp_path: Path) -> None:
    p = _write(tmp_path, "SKILL.md", "# header\n")
    assert remove_block(p, "plan") is False


def test_remove_block_second_block_unaffected(tmp_path: Path) -> None:
    p = _write(tmp_path, "SKILL.md", "# header\n")
    inject_block(p, "plan", "plan content")
    inject_block(p, "implement", "implement content")
    remove_block(p, "plan")
    text = p.read_text()
    assert "SPECOPS:BEGIN implement" in text
    assert "SPECOPS:BEGIN plan" not in text
