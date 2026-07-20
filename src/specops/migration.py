"""Installation-state detection and legacy→native migration (Feature 005).

This module owns the detection matrix (absent | native | legacy | native+legacy)
used by every lifecycle command. Backup/restore and the migrate orchestration
(US2) build on top of this detection.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import yaml

from specops import extension, initializer, speckit

ABSENT = "absent"
NATIVE = "native"
LEGACY = "legacy"
NATIVE_AND_LEGACY = "native+legacy"

_LEGACY_MARKER = "SPECOPS:BEGIN"
_BACKUP_DIRNAME = ".specops-backup"


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


# ---------------------------------------------------------------------------
# Migration backup set (T022, FR-008a) — recoverable pre-edit snapshots
# ---------------------------------------------------------------------------

class BackupSet:
    """Pre-edit snapshots of host-owned files, restorable to exact bytes.

    All backups live under a SpecOps-namespaced directory inside `.specify/`,
    mirroring each file's repository-relative path. ``restore_all`` copies every
    snapshot back verbatim; ``discard`` removes the backup directory.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.location = root / ".specify" / _BACKUP_DIRNAME
        self.entries: list[dict] = []

    def back_up(self, path: Path) -> None:
        rel = path.relative_to(self.root)
        backup_path = self.location / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        backup_path.write_bytes(data)
        self.entries.append(
            {"original": path, "backup": backup_path, "sha256": hashlib.sha256(data).hexdigest()}
        )

    def restore_all(self) -> None:
        """Restore every backed-up file to its exact pre-migration bytes."""
        for entry in self.entries:
            entry["original"].write_bytes(entry["backup"].read_bytes())
        self.discard()

    def discard(self) -> None:
        if self.location.exists():
            shutil.rmtree(self.location)


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _strip_all_specops_blocks(path: Path) -> None:
    """Remove every SpecOps marker block from *path*, preserving surrounding
    content (delegates to the tested :func:`initializer.remove_block`)."""
    regions = initializer._scan_markers(path.read_text(encoding="utf-8"))
    for block_id, _begin, _end in regions:
        initializer.remove_block(path, block_id)


# ---------------------------------------------------------------------------
# Migrate orchestration (T023, FR-007/008/008a) — interruption-safe, ordered
# ---------------------------------------------------------------------------

def migrate(root: Path) -> str:
    """Convert a legacy marker-injected installation to native.

    Ordered, interruption-safe flow (research R4): pre-checks → back up every
    host file about to be edited → strip SpecOps marker blocks → register native.
    On any failure/abort, restore all backed-up host files to exact bytes and
    re-raise (SC-008). Preserves `specops.json` and every feature ledger (FR-007).

    Returns "already native" (no-op) or "migrated".
    """
    extension.preflight(root)  # fail closed before touching any file

    if detect_state(root) == NATIVE:
        return "already native"

    legacy_files = [
        p for p in speckit.host_prompt_paths(root) if _LEGACY_MARKER in _safe_read(p)
    ]
    backups = BackupSet(root)
    try:
        for path in legacy_files:
            backups.back_up(path)
        for path in legacy_files:
            _strip_all_specops_blocks(path)
        extension.install(root)
    except Exception:
        backups.restore_all()
        raise
    backups.discard()
    return "migrated"
