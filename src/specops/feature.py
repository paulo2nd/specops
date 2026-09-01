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
import os
import re
from pathlib import Path

import yaml

from specops import fsutil, gitops, ledger, speckit
from specops.errors import LedgerParseError, SpecopsError

__all__ = ["cmd_rename", "cmd_use", "record_active"]

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


# ---------------------------------------------------------------------------
# Rename (US3) — carrying an identity without touching a history
# ---------------------------------------------------------------------------

# The one structured identity token SpecOps owns inside a specification. Everything
# else in the artifacts is prose: reported when it still names the old feature, never
# rewritten (FR-016a/FR-016b).
_BRANCH_HEADER_RE = re.compile(r"(\*\*Feature Branch\*\*:\s*`)([^`]*)(`)")


def _validate_rename(root: Path, source: str, target: str) -> tuple[Path, Path]:
    """Check every precondition before anything is written (research D9).

    A multi-file, multi-directory move cannot be transactional on a POSIX filesystem
    without a journal — which is exactly the over-engineering to avoid for a command
    run a handful of times in a repository's life. Complete up-front validation plus
    an ordering whose only irreversible step is last gets the guarantee that matters.
    """
    src = _validate_target(root, source)

    dst = Path(target)
    if not dst.is_absolute():
        dst = root / dst
    dst = Path(str(dst).rstrip("/\\")).resolve()

    if dst == src:
        raise SpecopsError(f"Source and target are the same feature: {_relative(root, src)}")
    if dst.exists():
        raise SpecopsError(f"Target already exists: {_relative(root, dst)}")
    specs_root = (root / SPECS_DIR).resolve()
    if specs_root != dst.parent:
        raise SpecopsError(
            f"Feature directory must live under '{SPECS_DIR}/': {_relative(root, dst)}"
        )

    override = speckit.override_value(root)
    if override is not None and override.resolve() == src:
        raise SpecopsError(
            f"{speckit.FEATURE_DIR_ENV} is set to '{_relative(root, src)}'; renaming it "
            "would leave the override pointing at a directory that no longer exists. "
            "Unset it and re-run."
        )
    return src, dst


def _stale_references(feature_dir: Path, old_name: str, old_branch: str | None) -> list[str]:
    """Every remaining mention of the old identity, as ``<relpath>:<line>`` (FR-016b).

    A plain literal scan: its false positives — a deliberate reference to the old
    feature — are exactly the cases a human must judge, which is why the result is
    informational and never fails the rename.
    """
    needles = {n for n in (old_name, old_branch) if n}
    hits: list[str] = []
    for path in sorted(feature_dir.rglob("*.md")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(feature_dir).as_posix()
        hits.extend(
            f"{rel}:{n}" for n, line in enumerate(lines, start=1)
            if any(needle in line for needle in needles)
        )
    return hits


def _rewrite_identity_header(spec: Path, new_name: str) -> bool:
    """Point the specification's feature-branch header at *new_name*. Idempotent."""
    if not spec.is_file():
        return False
    text = spec.read_text(encoding="utf-8")
    updated, count = _BRANCH_HEADER_RE.subn(rf"\g<1>{new_name}\g<3>", text, count=1)
    if count and updated != text:
        fsutil.atomic_write(spec, updated)
        return True
    return False


def cmd_rename(
    root: Path, source: str, target: str, *, branch: str | None = None
) -> str:
    """Rename a feature, carrying its identity (cli-contract: feature rename).

    Order (research D9): validate everything → write the ledger identity into the
    *source* → rewrite the spec header → move the directory → write the pointer. The
    only irreversible step is the move, and it comes after every check; a failure
    before it leaves a source directory that is internally consistent, and the ledger
    identity is rolled back so the pre-rename state is exactly restored.
    """
    if gitops.find_repo(root) is None:
        raise SpecopsError("Not a Git repository. Run 'git init' or 'specops init' first.")

    src, dst = _validate_rename(root, source, target)
    old_name, new_name = src.name, dst.name
    src_rel, dst_rel = _relative(root, src), _relative(root, dst)

    ledger_path = src / ledger.LEDGER_FILENAME
    ledger_backup: str | None = None
    old_branch: str | None = None
    if ledger_path.is_file():
        data = ledger.load_raw(src)          # raises exit 2 on a corrupt ledger
        ledger_backup = ledger_path.read_text(encoding="utf-8")
        recorded = data.get("branch")
        old_branch = str(recorded) if isinstance(recorded, str) and recorded else None
        data["feature"] = new_name
        if branch:
            data["branch"] = branch
        fsutil.atomic_write(ledger_path, yaml.dump(data, sort_keys=False))

    header_changed = _rewrite_identity_header(src / "spec.md", new_name)
    stale = _stale_references(src, old_name, old_branch)
    pointer_was_here = (_read_pointer(root) or "") and (
        (root / str(_read_pointer(root))).resolve() == src
    )

    try:
        os.rename(src, dst)
    except OSError as exc:
        # Undo the two in-place writes so the pre-rename state is exactly restored.
        if ledger_backup is not None:
            fsutil.atomic_write(ledger_path, ledger_backup)
        if header_changed:
            _rewrite_identity_header(src / "spec.md", old_name)
        raise SpecopsError(f"Could not move {src_rel} to {dst_rel}: {exc}") from None

    lines = [f"Renamed: {src_rel} → {dst_rel}"]
    if ledger_backup is not None:
        identity = f"Ledger identity: feature {old_name} → {new_name}; "
        identity += (
            f"branch {old_branch or '(unset)'} → {branch}. Rename the Git branch too "
            "(git branch -m) — until you do, the next command fails closed on the "
            "identity check."
            if branch else
            f"branch reference unchanged ({old_branch or 'unset'}) — pass --branch to update it."
        )
        lines.append(identity)
    if header_changed:
        lines.append("spec.md: **Feature Branch** header updated.")

    if pointer_was_here:
        _write_pointer(root, dst_rel)
        lines.append("Active feature pointer followed the rename.")
    else:
        lines.append(f"Active feature pointer unchanged ({_read_pointer(root) or 'none'}).")

    if stale:
        lines.append(
            f"{len(stale)} remaining reference{'' if len(stale) == 1 else 's'} to the old "
            "name (not changed):"
        )
        lines.extend(f"  {dst_rel}/{hit}" for hit in stale)
    return "\n".join(lines)
