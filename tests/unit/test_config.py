"""Unit tests for config.py."""
import json
from pathlib import Path

import pytest

from specops import config


def test_load_success(tmp_path: Path) -> None:
    (tmp_path / "specops.json").write_text(json.dumps({"test_command": "pytest"}))
    cfg = config.load(tmp_path)
    assert cfg["test_command"] == "pytest"


def test_load_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(config.ConfigError, match="not found"):
        config.load(tmp_path)


def test_load_invalid_json_raises(tmp_path: Path) -> None:
    (tmp_path / "specops.json").write_text("NOT JSON")
    with pytest.raises(config.ConfigError, match="Cannot parse"):
        config.load(tmp_path)


def test_merge_preserve_adds_missing_keys() -> None:
    existing = {"test_command": "mytest"}
    template = {"test_command": "pytest", "lint_command": "ruff", "skills_dir": ".specify/skills"}
    result = config.merge_preserve(existing, template)
    # existing value preserved
    assert result["test_command"] == "mytest"
    # missing keys filled from template
    assert result["lint_command"] == "ruff"
    assert result["skills_dir"] == ".specify/skills"


def test_merge_preserve_keeps_unknown_keys() -> None:
    existing = {"test_command": "pytest", "custom_key": "custom_value"}
    template = {"test_command": "pytest"}
    result = config.merge_preserve(existing, template)
    assert result["custom_key"] == "custom_value"


def test_create_or_merge_creates_new_file(tmp_path: Path) -> None:
    cfg, created = config.create_or_merge(tmp_path)
    assert created is True
    path = tmp_path / "specops.json"
    assert path.is_file()
    on_disk = json.loads(path.read_text())
    assert on_disk["test_command"] == "pytest"


def test_create_or_merge_preserves_existing(tmp_path: Path) -> None:
    (tmp_path / "specops.json").write_text(
        json.dumps({"test_command": "my_runner", "custom": "val"})
    )
    cfg, created = config.create_or_merge(tmp_path)
    assert created is False
    assert cfg["test_command"] == "my_runner"
    assert cfg["custom"] == "val"
    # missing keys added
    assert "lint_command" in cfg


def test_create_or_merge_idempotent(tmp_path: Path) -> None:
    config.create_or_merge(tmp_path)
    cfg1, _ = config.create_or_merge(tmp_path)
    cfg2, _ = config.create_or_merge(tmp_path)
    assert cfg1 == cfg2


def test_create_or_merge_raises_on_corrupted(tmp_path: Path) -> None:
    # A corrupted file must NOT be silently discarded and rewritten with defaults
    # (#23): create_or_merge propagates ConfigError, same contract as load().
    path = tmp_path / "specops.json"
    path.write_text("NOT JSON", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="Cannot parse"):
        config.create_or_merge(tmp_path)
    # The user's original bytes are left untouched.
    assert path.read_text(encoding="utf-8") == "NOT JSON"


def test_create_or_merge_skips_write_when_unchanged(tmp_path: Path) -> None:
    # When the merge produces no change, the file is not rewritten, keeping the
    # user's exact bytes and byte-for-byte install idempotence (#23).
    config.create_or_merge(tmp_path)
    path = tmp_path / "specops.json"
    before = path.read_bytes()
    mtime_before = path.stat().st_mtime_ns
    cfg, created = config.create_or_merge(tmp_path)
    assert created is False
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == mtime_before


def test_create_or_merge_preserves_user_formatting_when_complete(tmp_path: Path) -> None:
    # An existing file that already has every default key is not reformatted:
    # unknown keys and the user's own layout survive verbatim (#23).
    path = tmp_path / "specops.json"
    original = (
        '{"test_command": "mytest", "lint_command": "ruff", '
        '"skills_dir": ".specify/skills", "min_cli_version": "0.3.0", '
        '"custom": "keep"}'
    )
    path.write_text(original, encoding="utf-8")
    cfg, created = config.create_or_merge(tmp_path)
    assert created is False
    assert cfg["custom"] == "keep"
    assert path.read_text(encoding="utf-8") == original
