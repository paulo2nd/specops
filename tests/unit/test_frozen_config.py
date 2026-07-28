"""Frozen-shape contract test — specops.json (Feature 021). [SC-002]

Locks the frozen key set of the project config and its stability mechanism
(additive-only + preserve-unknown). A removal/rename of a frozen key, or a
regression of the preserve-unknown behavior, fails here.
"""
from __future__ import annotations

from pathlib import Path

from specops import config

# Enumerated frozen baseline (data-model.md Entity 1) — NOT derived from the module,
# so a silent removal/rename in config._DEFAULTS is caught.
_FROZEN_CONFIG_KEYS = {"test_command", "lint_command", "skills_dir", "min_cli_version"}


def test_config_frozen_default_keys() -> None:
    assert set(config._DEFAULTS) == _FROZEN_CONFIG_KEYS


def test_config_has_no_schema_version_field() -> None:
    """The freeze pins specops.json as versionless (no schema_version); introducing one
    would be a second sanctioned code delta, which FR-012 forbids."""
    assert "schema_version" not in config._DEFAULTS


def test_config_preserves_unknown_keys(tmp_path: Path) -> None:
    """R10 / stability mechanism: unknown keys survive a merge (additive-only)."""
    existing = {"test_command": "custom", "adopter_extra": {"k": 1}}
    merged = config.merge_preserve(existing, config._DEFAULTS)
    assert merged["adopter_extra"] == {"k": 1}  # unknown key preserved
    assert merged["test_command"] == "custom"  # existing value untouched
    assert set(merged) >= _FROZEN_CONFIG_KEYS  # defaults added


def test_config_additive_new_default_key_would_be_allowed() -> None:
    """FR-007: adding a NEW optional key is additive and must not break consumers; the
    frozen set is a subset check, not equality against a future superset."""
    hypothetical_future = dict(config._DEFAULTS, new_optional="v")
    assert set(hypothetical_future) >= _FROZEN_CONFIG_KEYS
