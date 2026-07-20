"""Unit tests for migration primitives: backup set + marker stripping (US2)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from specops import initializer, migration


def test_backupset_roundtrips_bytes_and_discards(tmp_path: Path) -> None:
    root = tmp_path
    host = root / "host.md"
    original = "line1\nline2\n"
    host.write_text(original)

    backups = migration.BackupSet(root)
    backups.back_up(host)
    assert backups.entries[0]["sha256"] == hashlib.sha256(original.encode()).hexdigest()

    host.write_text("CORRUPTED")  # simulate a mid-migration edit
    backups.restore_all()

    assert host.read_text() == original  # exact bytes restored (SC-008)
    assert not (root / ".specify" / migration._BACKUP_DIRNAME).exists()  # discarded


def test_strip_removes_specops_blocks_preserving_surrounding(tmp_path: Path) -> None:
    host = tmp_path / "plan.md"
    host.write_text("# Plan prompt\n\nBody before.\n")
    initializer.inject_block(host, "plan", "SPECOPS DIRECTIVE BODY")
    assert "SPECOPS:BEGIN" in host.read_text()

    migration._strip_all_specops_blocks(host)

    text = host.read_text()
    assert "SPECOPS:BEGIN" not in text
    assert "SPECOPS DIRECTIVE BODY" not in text
    assert "# Plan prompt" in text  # surrounding content preserved
    assert "Body before." in text


def test_strip_handles_multiple_blocks(tmp_path: Path) -> None:
    host = tmp_path / "multi.md"
    host.write_text("# Prompt\n")
    initializer.inject_block(host, "plan", "PLAN BODY")
    initializer.inject_block(host, "implement", "IMPL BODY")
    assert host.read_text().count("SPECOPS:BEGIN") == 2

    migration._strip_all_specops_blocks(host)

    assert "SPECOPS:BEGIN" not in host.read_text()
    assert "# Prompt" in host.read_text()
