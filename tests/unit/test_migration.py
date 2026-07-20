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


def test_restore_all_is_best_effort_and_reports_failures(tmp_path: Path) -> None:
    root = tmp_path
    a, b = root / "a.md", root / "b.md"
    a.write_text("A-orig")
    b.write_text("B-orig")

    backups = migration.BackupSet(root)
    backups.back_up(a)
    backups.back_up(b)
    a.write_text("A-stripped")
    b.write_text("B-stripped")

    a.chmod(0o444)  # make a's restore fail
    try:
        failed = backups.restore_all()
    finally:
        a.chmod(0o644)

    assert a in failed  # reported, not raised
    assert b.read_text() == "B-orig"  # b still restored despite a failing
    # partial failure keeps snapshots for manual recovery
    assert (root / ".specify" / migration._BACKUP_DIRNAME).exists()


def test_strip_handles_multiple_blocks(tmp_path: Path) -> None:
    host = tmp_path / "multi.md"
    host.write_text("# Prompt\n")
    initializer.inject_block(host, "plan", "PLAN BODY")
    initializer.inject_block(host, "implement", "IMPL BODY")
    assert host.read_text().count("SPECOPS:BEGIN") == 2

    migration._strip_all_specops_blocks(host)

    assert "SPECOPS:BEGIN" not in host.read_text()
    assert "# Prompt" in host.read_text()
