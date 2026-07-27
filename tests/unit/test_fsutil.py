"""Unit tests for fsutil.atomic_write — the single durable-write path (#25)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from specops import fsutil


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
