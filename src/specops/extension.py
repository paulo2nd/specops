"""Native Spec Kit extension engine (Feature 005).

Registers SpecOps through the host's own extension mechanism — a SpecOps-owned
`.specify/extensions.yml` hook manifest plus per-integration command
registration — without modifying any host-owned prompt file. The Python CLI
remains the deterministic engine; this layer only registers hooks/commands that
call it.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from specops import compat, config, gitops, initializer, speckit
from specops.errors import SpecopsError

OWNER = "specops"

# directive stem -> (hook_point, optional, description). Prompt provenance is the
# directive template (research R1); the host reads these hook points.
_HOOK_SPECS: list[tuple[str, str, bool, str]] = [
    ("specify", "after_specify", True, "SpecOps specification directives"),
    ("plan", "before_plan", False, "SpecOps planning directives (consistency gate)"),
    ("tasks", "after_tasks", False, "SpecOps task-generation directives (ledger creation seam)"),
    ("implement", "after_implement", False, "SpecOps implementation directives (review seam)"),
]


class ExtensionError(SpecopsError):
    """Blocking failure while installing/registering the native extension (exit 1)."""


# ---------------------------------------------------------------------------
# Template + manifest I/O
# ---------------------------------------------------------------------------

def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _directive(stem: str) -> str:
    return (_templates_dir() / "directives" / f"{stem}.md").read_text(encoding="utf-8").strip()


def _atomic_write(path: Path, text: str) -> None:
    """Write *text* to *path* atomically (temp-then-rename), interruption-safe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ext-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_manifest(root: Path) -> dict[str, Any]:
    """Load `.specify/extensions.yml` as a dict, or {} when absent/empty."""
    path = speckit.extensions_yml_path(root)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _dump(manifest: dict[str, Any]) -> str:
    return yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# SpecOps-owned entry construction & merge (preserves foreign entries)
# ---------------------------------------------------------------------------

def _build_hooks() -> dict[str, list[dict]]:
    return {
        hook_point: [
            {
                "extension": OWNER,
                "enabled": True,
                "optional": optional,
                "description": desc,
                "prompt": _directive(stem),
            }
        ]
        for stem, hook_point, optional, desc in _HOOK_SPECS
    }


def _merge_manifest(existing: dict[str, Any], commands: list[dict]) -> dict[str, Any]:
    """Merge SpecOps hooks/commands/cli_compat into *existing*, preserving every
    entry owned by another extension (invariant 1, contracts/extensions-manifest)."""
    result: dict[str, Any] = dict(existing)

    hooks: dict[str, Any] = dict(result.get("hooks") or {})
    for hook_point, entries in _build_hooks().items():
        foreign = [e for e in (hooks.get(hook_point) or []) if e.get("extension") != OWNER]
        hooks[hook_point] = foreign + entries
    result["hooks"] = hooks

    foreign_cmds = [c for c in (result.get("commands") or []) if c.get("extension") != OWNER]
    result["commands"] = foreign_cmds + commands

    result["specops"] = {"cli_compat": {"min_cli_version": compat.MIN_CLI_VERSION}}
    return result


def _specops_view(manifest: dict[str, Any]) -> dict[str, Any]:
    """Project the SpecOps-owned portion into a normalized, order-independent
    structure for semantic-equivalence comparison (research R5)."""
    view_hooks: dict[str, list[dict]] = {}
    for hook_point, entries in (manifest.get("hooks") or {}).items():
        owned = [
            {
                "optional": bool(e.get("optional", False)),
                "enabled": bool(e.get("enabled", True)),
                "description": e.get("description", ""),
                "prompt": (e.get("prompt") or "").strip(),
            }
            for e in (entries or [])
            if e.get("extension") == OWNER
        ]
        if owned:
            view_hooks[hook_point] = owned
    cmds = sorted(
        (
            {"id": c.get("id"), "integration": c.get("integration"), "path": c.get("path")}
            for c in (manifest.get("commands") or [])
            if c.get("extension") == OWNER
        ),
        key=lambda c: (c["integration"] or "", c["id"] or ""),
    )
    return {"hooks": view_hooks, "commands": cmds, "specops": manifest.get("specops") or {}}


def semantically_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True when the SpecOps-owned portions of two manifests are equivalent,
    ignoring key order, formatting, and foreign entries (FR-005, SC-002)."""
    return _specops_view(a) == _specops_view(b)


# ---------------------------------------------------------------------------
# Command registration (T015) — installs SpecOps-OWNED command files only
# ---------------------------------------------------------------------------

def register_commands(root: Path) -> list[dict]:
    """Install the `/specops-review` command file per integration and return
    their manifest command records. These are SpecOps-owned files, never listed
    in the host integration manifest (SC-006)."""
    review_content = (_templates_dir() / "review.md").read_text(encoding="utf-8")
    commands: list[dict] = []
    for target in speckit.review_command_targets(root):
        review_path: Path = target["review_path"]
        sep = target["separator"]
        initializer._install_review(review_path, review_content, sep)
        commands.append(
            {
                "id": f"specops{sep}review",
                "extension": OWNER,
                "integration": target["integration"],
                "path": str(review_path.relative_to(root)),
            }
        )
    return commands


# ---------------------------------------------------------------------------
# Install orchestration (T016)
# ---------------------------------------------------------------------------

def install(root: Path) -> str:
    """Register SpecOps natively. Fail-closed pre-checks run BEFORE any write, so
    a rejected install leaves the repository unchanged (FR-001, FR-013, FR-016).

    Returns "created", "updated", or "unchanged" (semantic idempotency, FR-005).
    """
    # 1. Pre-checks — nothing is written until all pass.
    if gitops.find_repo(root) is None:
        raise ExtensionError("Not a Git repository. Run 'git init' or 'specops init' first.")
    if not speckit.has_speckit(root):
        raise ExtensionError(
            "Speckit not detected (.specify/templates/ missing). Run Speckit initialization first."
        )
    result = compat.check()
    if not result.satisfied:
        raise ExtensionError(result.reason())
    try:
        targets = speckit.review_command_targets(root)
    except speckit.ManifestResolutionError as exc:
        raise ExtensionError(f"No compatible integration: {exc}") from None
    if not targets:
        raise ExtensionError("No installed integration to register with.")

    # 2. Compute desired state and compare for idempotency.
    existing = read_manifest(root)
    commands = [
        {
            "id": f"specops{t['separator']}review",
            "extension": OWNER,
            "integration": t["integration"],
            "path": str(t["review_path"].relative_to(root)),
        }
        for t in targets
    ]
    merged = _merge_manifest(existing, commands)
    manifest_path = speckit.extensions_yml_path(root)
    already = manifest_path.is_file() and semantically_equal(existing, merged)

    # 3. Register command files (idempotent overwrite of SpecOps-owned files).
    register_commands(root)
    config.create_or_merge(root)

    if already:
        return "unchanged"
    _atomic_write(manifest_path, _dump(merged))
    return "created" if not existing else "updated"
