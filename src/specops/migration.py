"""Installation-state detection and legacy→native migration (Feature 005).

This module owns the detection matrix (absent | native | legacy | native+legacy)
used by every lifecycle command. Backup/restore and the migrate orchestration
(US2) build on top of this detection.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from specops import extension, speckit

ABSENT = "absent"
NATIVE = "native"
LEGACY = "legacy"
NATIVE_AND_LEGACY = "native+legacy"

_LEGACY_MARKER = "SPECOPS:BEGIN"


def _has_native(root: Path) -> bool:
    """True when `.specify/extensions.yml` carries any SpecOps-owned entry."""
    path = speckit.extensions_yml_path(root)
    if not path.is_file():
        return False
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False
    for entries in (data.get("hooks") or {}).values():
        if any(e.get("extension") == extension.OWNER for e in (entries or [])):
            return True
    return any(c.get("extension") == extension.OWNER for c in (data.get("commands") or []))


def _has_legacy(root: Path) -> bool:
    """True when any resolved host prompt file still contains SpecOps markers."""
    for path in speckit.host_prompt_paths(root):
        try:
            if _LEGACY_MARKER in path.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def detect_state(root: Path) -> str:
    """Return the installation state (FR-006).

    - ``native``: native manifest carries SpecOps entries.
    - ``legacy``: a host prompt file still has marker-injected blocks.
    - ``native+legacy``: both (partial migration — complete it).
    - ``absent``: neither signal present.
    """
    native = _has_native(root)
    legacy = _has_legacy(root)
    if native and legacy:
        return NATIVE_AND_LEGACY
    if native:
        return NATIVE
    if legacy:
        return LEGACY
    return ABSENT
