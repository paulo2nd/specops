"""specops.json load/validate/merge helpers (R10)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from specops.errors import SpecopsError

CONFIG_FILENAME = "specops.json"

_DEFAULTS: dict[str, Any] = {
    "test_command": "pytest",
    "lint_command": "",
    "skills_dir": ".specify/skills",
    "min_cli_version": "0.3.0",
}


class ConfigError(SpecopsError):
    """Raised on missing or unreadable specops.json."""


def config_path(root: Path) -> Path:
    return root / CONFIG_FILENAME


def load(root: Path) -> dict[str, Any]:
    """
    Load specops.json from *root*.

    Raises ConfigError when the file is absent or not valid JSON.
    Unknown keys are preserved (R10).
    """
    path = config_path(root)
    if not path.is_file():
        raise ConfigError(
            f"{CONFIG_FILENAME} not found in {root}. Run 'specops init' first."
        )
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Cannot parse {path}: {exc}") from exc


def merge_preserve(existing: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    """
    Merge *template* into *existing*, keeping existing values and unknown keys.

    New keys from *template* that are absent in *existing* are added with
    their template values. Existing keys (including unknown ones) are untouched.
    """
    result = dict(existing)
    for key, value in template.items():
        if key not in result:
            result[key] = value
    return result


def create_or_merge(root: Path) -> tuple[dict[str, Any], bool]:
    """
    Create specops.json from defaults, or merge-preserve an existing one.

    Returns (config_dict, created) where *created* is True when the file
    was newly created, False when an existing file was updated.
    """
    path = config_path(root)
    if path.is_file():
        try:
            existing = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
        merged = merge_preserve(existing, _DEFAULTS)
        path.write_text(json.dumps(merged, indent=2) + "\n")
        return merged, False
    else:
        path.write_text(json.dumps(_DEFAULTS, indent=2) + "\n")
        return dict(_DEFAULTS), True
