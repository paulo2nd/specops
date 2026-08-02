"""specops.json load/validate/merge helpers (R10)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from specops.errors import SpecopsError

CONFIG_FILENAME = "specops.json"

# Feature 025 — the maximum number of semantic review rounds before SpecOps halts
# and asks a human (the non-pierceable core; never a fabricated verdict).
DEFAULT_REVIEW_ROUND_CAP = 10

_DEFAULTS: dict[str, Any] = {
    "test_command": "pytest",
    "lint_command": "",
    "skills_dir": ".specify/skills",
    "min_cli_version": "0.3.0",
    "review_round_cap": DEFAULT_REVIEW_ROUND_CAP,
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
        return json.loads(path.read_text(encoding="utf-8"))
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


def review_round_cap(cfg: dict[str, Any]) -> int:
    """Return the configured review round cap (Feature 025).

    Defensively coerced at the read site (there is no central config validator):
    a non-integer or non-positive value falls back to
    :data:`DEFAULT_REVIEW_ROUND_CAP`, mirroring :func:`lane_safety_overrides`.
    """
    raw = cfg.get("review_round_cap")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return raw
    return DEFAULT_REVIEW_ROUND_CAP


def lane_safety_overrides(cfg: dict[str, Any]) -> dict[str, list[str]]:
    """Return per-category extra safety globs from ``lane.safety`` (Feature 013).

    These *add* to the built-in non-removable detection floor in :mod:`specops.safety`;
    they never remove it (protecting the non-pierceable core). A malformed block is
    ignored (treated as no overrides) rather than failing — the floor always applies.
    """
    lane = cfg.get("lane")
    safety = lane.get("safety") if isinstance(lane, dict) else None
    if not isinstance(safety, dict):
        return {}
    out: dict[str, list[str]] = {}
    for category, globs in safety.items():
        if isinstance(globs, list):
            out[str(category)] = [str(g) for g in globs if isinstance(g, str)]
    return out


def create_or_merge(root: Path) -> tuple[dict[str, Any], bool]:
    """
    Create specops.json from defaults, or merge-preserve an existing one.

    Returns (config_dict, created) where *created* is True when the file
    was newly created, False when an existing file was updated.
    """
    path = config_path(root)
    if path.is_file():
        # Reuse load() so a corrupted file raises ConfigError instead of being
        # silently discarded — honors the unknown-keys-are-preserved contract (R10, #23).
        existing = load(root)
        merged = merge_preserve(existing, _DEFAULTS)
        # Skip the write when nothing changed: preserves the user's exact bytes
        # and keeps install byte-for-byte idempotent ("unchanged", #23).
        if merged != existing:
            path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        return merged, False
    else:
        path.write_text(json.dumps(_DEFAULTS, indent=2) + "\n", encoding="utf-8")
        return dict(_DEFAULTS), True
