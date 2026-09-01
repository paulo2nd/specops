"""Feature-identity operations: repointing and renaming (Feature 026).

The active feature is selected by `.specify/feature.json` and, at higher precedence,
Spec Kit's `SPECIFY_FEATURE_DIRECTORY` override (see :mod:`specops.speckit`). Neither
had a command that *writes* it, so starting or renumbering a feature meant hand-editing
the very files the ledger exists to make trustworthy — the contradiction this module
removes (#75).

Both commands record; neither validates intent. A repoint states what it moved and
what it left behind; a rename carries identity across the directory, the ledger, the
branch reference and the pointer without touching a single recorded fact.

Imports :mod:`specops.ledger` and :mod:`specops.speckit`, never :mod:`specops.status`
— the same one-way direction the rest of the package follows.
"""
from __future__ import annotations

import json
from pathlib import Path

from specops import fsutil, gitops, ledger, speckit
from specops.errors import LedgerParseError, SpecopsError

__all__ = ["cmd_use", "record_active"]

POINTER_REL = ".specify/feature.json"
SPECS_DIR = "specs"
# The downstream artifacts a feature accumulates. Only `spec.md` is required to point
# at a feature — pointing *before* planning is the normal flow this command serves —
# so the rest are reported as not-yet-present rather than demanded.
EXPECTED_ARTIFACTS = ("plan.md", "tasks.md", "status.yaml")


def _pointer_path(root: Path) -> Path:
    return root / ".specify" / "feature.json"


def _read_pointer(root: Path) -> str | None:
    """The stored pointer value, or None when absent. Raises on a malformed file.

    A malformed pointer is an infrastructure error (exit 2), never a silent None: it
    is the file this command exists to manage, and guessing past it is how a repoint
    ends up reporting success while resolution answers something else.
    """
    path = _pointer_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise LedgerParseError(f"Cannot parse {POINTER_REL}: {exc}") from None
    value = data.get("feature_directory")
    return str(value) if value else None


def _write_pointer(root: Path, rel: str) -> None:
    """Persist the pointer atomically, preserving any unknown keys already stored.

    Spec Kit writes this file too; dropping a key it added would be a destructive edit
    of an integration-owned file (Principle I).
    """
    path = _pointer_path(root)
    data: dict = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                data = existing
        except (json.JSONDecodeError, OSError):
            data = {}
    data["feature_directory"] = rel
    fsutil.atomic_write(path, json.dumps(data, indent=2) + "\n")


def _relative(root: Path, target: Path) -> str:
    """*target* as a repo-relative POSIX string.

    POSIX separators always: the pointer is read by Spec Kit as well, and a backslash
    would make the stored value platform-dependent.
    """
    try:
        return target.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return target.resolve().as_posix()


def _validate_target(root: Path, raw: str) -> Path:
    """Resolve and validate a feature directory, or raise with the reason."""
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = Path(str(candidate).rstrip("/\\")).resolve()

    if not candidate.is_dir():
        raise SpecopsError(f"Feature directory not found: {_relative(root, candidate)}")
    specs_root = (root / SPECS_DIR).resolve()
    if specs_root not in candidate.parents:
        raise SpecopsError(
            f"Feature directory must live under '{SPECS_DIR}/': {_relative(root, candidate)}"
        )
    if not (candidate / "spec.md").is_file():
        raise SpecopsError(
            f"Not a feature directory (no spec.md): {_relative(root, candidate)}"
        )
    return candidate


def _outgoing_state(feature_dir: Path | None) -> list[str]:
    """What the feature being left behind still has open, as human phrases.

    Reported, never enforced (FR-012a): a hard refusal would break the legitimate case
    of parking a feature to attend to another, and SpecOps does not judge intent. But
    repointing away from in-flight work with no cue would reproduce the silent failure
    this command exists to remove.
    """
    if feature_dir is None or not (feature_dir / "status.yaml").is_file():
        return []
    try:
        data = ledger.load_raw(feature_dir)
    except SpecopsError:
        return []  # an unreadable outgoing ledger is not this command's business
    notes: list[str] = []
    for task in data.get("tasks") or []:
        if isinstance(task, dict) and task.get("status") == "IN_PROGRESS":
            notes.append(f"task {task.get('id')} IN_PROGRESS")
    for cycle in data.get("review_cycles") or []:
        if isinstance(cycle, dict) and cycle.get("result") is None:
            notes.append(f"review round {cycle.get('round')} open")
    return notes


def _foreign_ledger_note(target: Path) -> str | None:
    """A ledger naming a different feature is reported, not pre-judged.

    SpecOps records the pointer move and lets `consistency` / `reconcile` report the
    mismatch — deciding for the operator that it is wrong would be validation, not
    recording (Principle IV).
    """
    if not (target / "status.yaml").is_file():
        return None
    try:
        name = ledger.load_raw(target).get("feature")
    except SpecopsError:
        return None
    if isinstance(name, str) and name and name != target.name:
        return f"Ledger there names feature '{name}', not '{target.name}'."
    return None


def cmd_use(root: Path, target: str) -> str:
    """Repoint the active feature (cli-contract: feature use).

    Refuses when the target is not a feature directory, and when an environment
    override names somewhere else — writing the pointer would then have no effect on
    resolution, and reporting success on a write that cannot take effect is the very
    failure mode this command removes (FR-010a).
    """
    if gitops.find_repo(root) is None:
        raise SpecopsError("Not a Git repository. Run 'git init' or 'specops init' first.")

    resolved = _validate_target(root, target)
    rel = _relative(root, resolved)

    override = speckit.override_value(root)
    if override is not None and override.resolve() != resolved:
        raise SpecopsError(
            f"{speckit.FEATURE_DIR_ENV} is set to '{_relative(root, override)}' and takes "
            f"precedence over {POINTER_REL}; repointing to '{rel}' would have no effect. "
            "Unset it, or run with the target you want."
        )

    previous = _read_pointer(root)
    if previous is not None and (root / previous).resolve() == resolved:
        return f"Active feature already: {rel} (no change)."

    outgoing = speckit.resolve_feature_dir(root)
    _write_pointer(root, rel)

    lines = [f"Active feature: {previous or '(none)'} → {rel}"]
    missing = [a for a in EXPECTED_ARTIFACTS if not (resolved / a).is_file()]
    if missing:
        lines.append("Not yet present: " + ", ".join(missing))
    foreign = _foreign_ledger_note(resolved)
    if foreign:
        lines.append(foreign)
    notes = _outgoing_state(outgoing)
    if notes:
        lines.append("Outgoing feature has unfinished work: " + ", ".join(notes))
    return "\n".join(lines)


def record_active(root: Path, feature_dir: Path) -> None:
    """Persist *feature_dir* as the active feature, if it is not already recorded.

    Used by ``status init-spec`` (FR-013). Silent and idempotent: it records a fact the
    caller already established, so it neither reports nor refuses — a failure to write
    the pointer must not undo a ledger that was created successfully.
    """
    rel = _relative(root, feature_dir)
    try:
        if _read_pointer(root) == rel:
            return
        _write_pointer(root, rel)
    except (LedgerParseError, OSError):
        return  # a pointer we cannot read or write is not worth losing the ledger over
