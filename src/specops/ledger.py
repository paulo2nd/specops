"""Ledger v2 core (Feature 006): schema versioning, migration, timezone-aware
timestamps, invariants, workspace-identity validation, and a concurrency-safe,
interruption-safe load/save cycle.

This module owns the on-disk contract of `specs/<feature>/status.yaml`. The
command layer in :mod:`specops.status` routes every state-changing read/write
through here so all commands share identical migration, identity, concurrency,
and atomicity behavior. Read-only surfaces read the raw dict without mutating.

It never imports :mod:`specops.status` (one-way dependency: status -> ledger).
"""
from __future__ import annotations

import contextlib
import copy
import datetime
import os
import time
from pathlib import Path

import yaml

from specops import gitops, speckit
from specops.errors import LedgerParseError, SpecopsError, StaleLedgerError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEDGER_FILENAME = "status.yaml"

CURRENT_SCHEMA = 5
OLDEST_SUPPORTED = 1  # v1 == a ledger with no `schema_version` key

# Feature 009 — the no-map context-provenance marker backfilled onto records
# that predate the map-provenance schema (v3). See contextmap.provenance_for.
NO_MAP_PROVENANCE = {"map": "none"}
_PROVENANCE_MAP_STATES = ("none", "invalid", "present")
DEFAULT_WORKFLOW_LANE = "full"

# Feature 010 (v4) — the top-level acknowledgements list. Each record marks a
# discovered (unplanned) effective-diff path as legitimate; see specops.trace.
ACK_FIELDS = ("path", "task", "reason")

# Feature 011 (v5) — structured corrective handoffs. Each review cycle may carry
# a nested `handoff` object holding the round's findings; see specops.handoff.
SEVERITIES = ("blocking", "advisory")
# OPEN → FIXED → VERIFIED is the correction lifecycle; DISMISSED is a terminal
# state for a finding withdrawn as a false positive or a superseded round.
FINDING_STATES = ("OPEN", "FIXED", "VERIFIED", "DISMISSED")

PHASES = ["SPECIFY", "PLAN", "TASKS", "IMPLEMENT", "REVIEW", "DONE"]
TASK_STATUSES = ["PENDING", "IN_PROGRESS", "DONE"]

_BACKUP_DIRNAME = ".specops-backup"

_ARTIFACT_FOR_PHASE = {
    "SPECIFY": "spec.md",
    "PLAN": "plan.md",
    "TASKS": "tasks.md",
    "IMPLEMENT": "tasks.md",
    "REVIEW": "tasks.md",
    "DONE": "tasks.md",
}

# Classification results
CURRENT = "current"
MIGRATABLE = "migratable"
TOO_NEW = "too_new"
UNSUPPORTED = "unsupported"


# ---------------------------------------------------------------------------
# Timestamps (FR-009, FR-010)
# ---------------------------------------------------------------------------


def now_utc() -> str:
    """Return the current instant as a timezone-aware RFC3339 UTC string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def to_aware(value: str | None) -> str | None:
    """Return *value* as a timezone-aware RFC3339 UTC string, preserving the instant.

    A date-only value (``2026-07-19``) is interpreted as UTC midnight; a naive
    datetime is interpreted as UTC; an aware datetime is normalized to UTC. An
    unparseable value is returned unchanged (best effort). ``None`` stays ``None``.
    """
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    dt: datetime.datetime | None = None
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        try:
            d = datetime.date.fromisoformat(text)
            dt = datetime.datetime(d.year, d.month, d.day)
        except ValueError:
            return text
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.isoformat(timespec="seconds")


def artifact_for_phase(phase: str | None) -> str:
    """Return the artifact bound to *phase* (FR-027)."""
    return _ARTIFACT_FOR_PHASE.get(phase or "", "spec.md")


# ---------------------------------------------------------------------------
# Version classification (FR-001, FR-002)
# ---------------------------------------------------------------------------


def classify(data: dict) -> str:
    """Return one of CURRENT | MIGRATABLE | TOO_NEW | UNSUPPORTED for *data*."""
    sv = data.get("schema_version")
    if sv is None:
        return MIGRATABLE  # v1: no schema_version key
    if isinstance(sv, bool) or not isinstance(sv, int):
        return UNSUPPORTED
    if sv == CURRENT_SCHEMA:
        return CURRENT
    if OLDEST_SUPPORTED <= sv < CURRENT_SCHEMA:
        return MIGRATABLE
    if sv > CURRENT_SCHEMA:
        return TOO_NEW
    return UNSUPPORTED  # sv < OLDEST_SUPPORTED (e.g. 0 or negative)


def diagnostic_line(cls: str) -> str | None:
    """Return the read-only diagnostic text for a classification, or None when current.

    Callers add their own prefix (``diagnostic:`` for show, ``Warning:`` for
    reconcile). Single source of truth for the classify→message mapping.
    """
    if cls == TOO_NEW:
        return "ledger schema is newer than this SpecOps release; upgrade SpecOps."
    if cls == UNSUPPORTED:
        return "unsupported ledger schema."
    if cls == MIGRATABLE:
        return (
            f"older ledger schema (below v{CURRENT_SCHEMA}); it will migrate on the "
            "next state change or via 'specops status migrate'."
        )
    return None


def refusal_message(cls: str) -> str | None:
    """Return the state-change refusal message for a classification, or None when writable."""
    if cls == TOO_NEW:
        return (
            "Ledger schema is newer than this SpecOps release understands; "
            "upgrade SpecOps to continue."
        )
    if cls == UNSUPPORTED:
        return "Unsupported ledger schema; cannot operate on this ledger."
    return None


# ---------------------------------------------------------------------------
# Migration (FR-003, FR-004, FR-008, FR-010, FR-028)
# ---------------------------------------------------------------------------


def migrate_to_current(data: dict) -> dict:
    """Deterministically upgrade a migratable ledger to CURRENT_SCHEMA. Pure; no I/O.

    Preserves every phase, task, evidence entry, and review cycle with identical
    meaning (evidence representation is untouched — FR-030). Idempotent when the
    input is already current (returns an equivalent dict without reordering).
    """
    cls = classify(data)
    if cls == CURRENT:
        return copy.deepcopy(data)
    if cls in (TOO_NEW, UNSUPPORTED):
        raise SpecopsError(f"Cannot migrate a {cls} ledger.")

    out = copy.deepcopy(data)
    out["schema_version"] = CURRENT_SCHEMA
    out.setdefault("revision", 1)
    out["workflow_lane"] = out.get("workflow_lane") or DEFAULT_WORKFLOW_LANE

    out["created_at"] = to_aware(out.get("created_at")) or now_utc()
    out["updated_at"] = to_aware(out.get("updated_at")) or out["created_at"]
    out["active_artifact"] = out.get("active_artifact") or artifact_for_phase(
        out.get("current_phase")
    )

    # Convert every remaining recorded timestamp to zone-aware (SC-007).
    for task in out.get("tasks") or []:
        if task.get("completed_at"):
            task["completed_at"] = to_aware(task["completed_at"])
    for cycle in out.get("review_cycles") or []:
        if cycle.get("started_at"):
            cycle["started_at"] = to_aware(cycle["started_at"])
        if cycle.get("completed_at"):
            cycle["completed_at"] = to_aware(cycle["completed_at"])

    rec = out.setdefault("recovery", {})
    rec.setdefault("active_task", None)
    rec.setdefault("last_commit", None)
    rec.setdefault("blockers", [])
    rec["last_consistent_revision"] = out["revision"]
    rec["last_consistent_at"] = out["updated_at"]
    rec.setdefault("migrated_from_backup", None)
    ensure_workflow_block(out)
    backfill_context_provenance(out)
    backfill_acknowledgements(out)
    return out


def backfill_context_provenance(data: dict) -> None:
    """Back-fill the explicit no-map provenance marker onto records lacking it.

    Feature 009 (v3): every task and review-cycle record carries a
    ``context_provenance`` object. Records written before v3 gain the explicit
    ``{"map": "none"}`` marker (never an omitted field, per FR-009/FR-018) so a
    pre-feature ledger stays readable and unambiguous. Idempotent.
    """
    for task in data.get("tasks") or []:
        if isinstance(task, dict):
            task.setdefault("context_provenance", dict(NO_MAP_PROVENANCE))
    for cycle in data.get("review_cycles") or []:
        if isinstance(cycle, dict):
            cycle.setdefault("context_provenance", dict(NO_MAP_PROVENANCE))


def backfill_acknowledgements(data: dict) -> None:
    """Back-fill the top-level ``acknowledgements`` list (Feature 010, v4). Idempotent.

    A ledger written before v4 has no acknowledgements; it gains an explicit empty
    list rather than an omitted key so a pre-feature ledger stays readable and a
    discovered path is simply ``unexplained`` until acknowledged (FR-016).
    """
    acks = data.get("acknowledgements")
    if not isinstance(acks, list):
        data["acknowledgements"] = []


def ensure_workflow_block(data: dict) -> None:
    """Back-fill the additive `workflow` block in place (Feature 007). Idempotent.

    The block (currently ``{skipped_steps: []}``) records the human run/skip
    decisions for optional lifecycle steps (FR-006). It is a **within-v2 additive
    field**, not a schema bump: it carries no invariants and old readers ignore
    it, so a ledger that predates it (a v2 ledger written by Feature 006) gains
    the block on its next state-changing write rather than forcing every ledger
    to re-migrate.
    """
    wf = data.get("workflow")
    if not isinstance(wf, dict):
        wf = data["workflow"] = {}
    steps = wf.get("skipped_steps")
    if not isinstance(steps, list):
        wf["skipped_steps"] = []


# ---------------------------------------------------------------------------
# Invariants (FR-025, FR-026)
# ---------------------------------------------------------------------------


def validate_invariants(data: dict) -> list[str]:
    """Return a list of invariant-violation strings ([] when valid).

    A non-empty result MUST block a state change (fail closed). Orphaned tasks
    (removed from tasks.md) are exempt from task-level invariants.
    """
    violations: list[str] = []

    phase = data.get("current_phase")
    if phase not in PHASES:
        violations.append(f"invalid current_phase '{phase}'")

    active: list[str] = []
    for task in data.get("tasks") or []:
        if task.get("orphaned"):
            continue
        tid = task.get("id")
        st = task.get("status")
        if st not in TASK_STATUSES:
            violations.append(f"task '{tid}' has invalid status '{st}'")
        if st == "IN_PROGRESS":
            active.append(tid)
        if st == "DONE" and not task.get("evidence"):
            violations.append(f"task '{tid}' is DONE without evidence")
    if len(active) > 1:
        violations.append(f"more than one IN_PROGRESS task: {active}")

    rec = data.get("recovery") or {}
    at = rec.get("active_task")
    if at is not None and at not in active:
        violations.append(f"recovery.active_task '{at}' is not the IN_PROGRESS task")

    prev = 0
    open_cycles = 0
    for cycle in data.get("review_cycles") or []:
        rnd = cycle.get("round")
        if not isinstance(rnd, int) or rnd <= prev:
            violations.append(f"review cycle round not strictly increasing: {rnd}")
        else:
            prev = rnd
        if cycle.get("result") is None:
            open_cycles += 1
        violations.extend(_provenance_violations(cycle, f"review cycle {cycle.get('round')}"))
    if open_cycles > 1:
        violations.append("more than one open review cycle")

    for task in data.get("tasks") or []:
        if task.get("orphaned"):
            continue
        violations.extend(_provenance_violations(task, f"task '{task.get('id')}'"))

    violations.extend(_acknowledgement_violations(data))
    violations.extend(_finding_violations(data))

    return violations


# Finding structural-defect kinds — the single source of truth shared by the
# write-time invariant (``_finding_violations``) and the read-time
# ``handoff validate`` report (Feature 011). Reference-resolution defects
# (unknown task / unresolvable commit) are NOT here — they need repo/ledger
# context the caller owns, so ``handoff`` adds them on top.
FINDING_DEFECT_MALFORMED = "malformed"
FINDING_DEFECT_SEVERITY = "invalid-severity"
FINDING_DEFECT_STATE = "invalid-state"
FINDING_DEFECT_MISSING_CLOSURE = "missing-closure"
FINDING_DEFECT_CONTRADICTORY = "contradictory-state"
FINDING_DEFECT_DUPLICATE_ID = "duplicate-id"


def finding_structural_defects(data: dict) -> list[tuple[str, str]]:
    """Return ``(kind, message)`` for every *structural* finding defect.

    The shared source of truth for both the write-time invariant and the
    ``handoff validate`` read command, so the two can never diverge. Validates
    the optional v5 finding/handoff state nested on review cycles (absent is
    allowed — a pre-v5 ledger or a round with no findings): a ``handoff`` MUST be
    a mapping with list ``authorized_paths``/``findings``; each finding MUST carry
    a non-empty ``id``, a valid ``severity``/``state``, and — for a ``blocking``
    finding — non-empty ``closure_criteria``/``expected_evidence``;
    ``FIXED``/``VERIFIED`` findings MUST carry their correction links; a
    ``VERIFIED`` finding MUST carry evidence; ids MUST be unique per feature.
    """
    out: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for cycle in data.get("review_cycles") or []:
        if not isinstance(cycle, dict):
            continue
        handoff = cycle.get("handoff")
        if handoff is None:
            continue
        rnd = cycle.get("round")
        if not isinstance(handoff, dict):
            out.append((FINDING_DEFECT_MALFORMED, f"review cycle {rnd} handoff is not a mapping"))
            continue
        if not isinstance(handoff.get("authorized_paths", []), list):
            out.append((FINDING_DEFECT_MALFORMED,
                        f"review cycle {rnd} handoff authorized_paths is not a list"))
        findings = handoff.get("findings", [])
        if not isinstance(findings, list):
            out.append((FINDING_DEFECT_MALFORMED,
                        f"review cycle {rnd} handoff findings is not a list"))
            continue
        for f in findings:
            if not isinstance(f, dict):
                out.append((FINDING_DEFECT_MALFORMED,
                            f"review cycle {rnd} has a malformed finding"))
                continue
            fid = f.get("id")
            if not isinstance(fid, str) or not fid:
                out.append((FINDING_DEFECT_MALFORMED,
                            f"review cycle {rnd} has a finding without an id"))
                continue
            seen[fid] = seen.get(fid, 0) + 1
            if f.get("severity") not in SEVERITIES:
                out.append((FINDING_DEFECT_SEVERITY,
                            f"finding '{fid}' has invalid severity '{f.get('severity')}'"))
            if f.get("state") not in FINDING_STATES:
                out.append((FINDING_DEFECT_STATE,
                            f"finding '{fid}' has invalid state '{f.get('state')}'"))
            if f.get("severity") == "blocking" and not (
                f.get("closure_criteria") and f.get("expected_evidence")
            ):
                out.append((FINDING_DEFECT_MISSING_CLOSURE,
                            f"blocking finding '{fid}' missing closure_criteria/expected_evidence"))
            if f.get("state") in ("FIXED", "VERIFIED") and not (
                f.get("task") and f.get("commits")
            ):
                out.append((FINDING_DEFECT_CONTRADICTORY,
                            f"finding '{fid}' in state {f.get('state')} missing task/commits link"))
            if f.get("state") == "VERIFIED" and not f.get("evidence"):
                out.append((FINDING_DEFECT_CONTRADICTORY,
                            f"finding '{fid}' is VERIFIED without evidence"))
    out.extend((FINDING_DEFECT_DUPLICATE_ID, f"duplicate finding id '{fid}'")
               for fid, n in sorted(seen.items()) if n > 1)
    return out


def _finding_violations(data: dict) -> list[str]:
    """Write-time invariant messages, derived from :func:`finding_structural_defects`."""
    return [msg for _kind, msg in finding_structural_defects(data)]


def _acknowledgement_violations(data: dict) -> list[str]:
    """Validate the optional ``acknowledgements`` list (Feature 010, v4).

    Absent is allowed (a pre-v4 ledger). When present each record MUST be a
    mapping carrying non-empty ``path``/``task``/``reason`` whose ``task`` matches
    a known non-orphaned task id (no dangling task reference, FR-007).
    """
    acks = data.get("acknowledgements")
    if acks is None:
        return []
    if not isinstance(acks, list):
        return ["acknowledgements is not a list"]
    # Include orphaned tasks: a task removed from tasks.md still has a ledger
    # record, so an acknowledgement referencing it is not dangling. Excluding
    # orphaned ids would turn a previously-valid ledger invalid the moment its
    # task orphans, bricking every subsequent mutating command.
    known = {
        t.get("id")
        for t in data.get("tasks") or []
        if isinstance(t, dict)
    }
    out: list[str] = []
    for i, rec in enumerate(acks):
        if not isinstance(rec, dict) or any(
            not isinstance(rec.get(f), str) or not rec.get(f) for f in ACK_FIELDS
        ):
            out.append(f"acknowledgement {i} is malformed (path/task/reason required)")
            continue
        if rec["task"] not in known:
            out.append(
                f"acknowledgement {i} references unknown task '{rec['task']}'"
            )
    return out


def _provenance_violations(record: dict, label: str) -> list[str]:
    """Validate a record's optional ``context_provenance`` shape (Feature 009).

    Absent is allowed (a pre-v3 record). When present it MUST be a mapping whose
    ``map`` is one of ``none``/``invalid``/``present``; a ``present`` record MUST
    carry a ``digest`` and a ``context_ids`` list.
    """
    prov = record.get("context_provenance")
    if prov is None:
        return []
    if not isinstance(prov, dict) or prov.get("map") not in _PROVENANCE_MAP_STATES:
        return [f"{label} has malformed context_provenance"]
    if prov["map"] == "present" and (
        not isinstance(prov.get("digest"), str)
        or not isinstance(prov.get("context_ids"), list)
    ):
        return [f"{label} present-provenance missing digest/context_ids"]
    return []


# ---------------------------------------------------------------------------
# Workspace identity (FR-017, FR-017a, FR-018, FR-019, FR-020)
# ---------------------------------------------------------------------------


def validate_identity(root: Path, repo: gitops.git.Repo, data: dict) -> str | None:
    """Return the first diverged identity dimension, or None when consistent.

    Checks feature, branch, then baseline (branch-point commit reachable as an
    ancestor of HEAD). An unresolvable feature fails closed as 'feature'.
    """
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        return "feature"
    if feature_dir.name != data.get("feature"):
        return "feature"

    ledger_branch = data.get("branch")
    if ledger_branch and gitops.current_branch(repo) != ledger_branch:
        return "branch"

    baseline = data.get("baseline")
    if baseline and not gitops.is_ancestor(repo, baseline):
        return "baseline"

    return None


# ---------------------------------------------------------------------------
# Backup before migration (FR-008a)
# ---------------------------------------------------------------------------


def backup_ledger(root: Path, feature_dir: Path) -> str:
    """Copy the current ledger to a retained backup and return its repo-relative path.

    Mirrors the ledger's repo-relative path under `.specify/.specops-backup/`
    (the Feature 005 namespaced backup convention). Retained (never discarded)
    so a defective migration can be rolled back deterministically.
    """
    ledger_path = feature_dir / LEDGER_FILENAME
    root = root.resolve()
    try:
        rel = ledger_path.resolve().relative_to(root)
    except ValueError:
        rel = Path(ledger_path.name)
    backup_path = root / ".specify" / _BACKUP_DIRNAME / rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_bytes(ledger_path.read_bytes())
    return str((Path(".specify") / _BACKUP_DIRNAME / rel).as_posix())


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------


def _ledger_path(feature_dir: Path) -> Path:
    return feature_dir / LEDGER_FILENAME


def load_raw(feature_dir: Path) -> dict:
    """Read the ledger dict. Never mutates disk. Ignores any stale `.tmp` sidecar."""
    path = _ledger_path(feature_dir)
    if not path.is_file():
        raise SpecopsError(
            f"Ledger not found: {path}. Run 'specops status init-spec' first."
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LedgerParseError(f"Cannot parse ledger {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LedgerParseError(f"Ledger {path} has invalid structure.")
    return data


def revision_of(data: dict) -> int:
    """Return the ledger revision (0 for a v1 ledger with no revision)."""
    rev = data.get("revision", 0)
    return rev if isinstance(rev, int) and not isinstance(rev, bool) else 0


def _logical(data: dict) -> dict:
    """Return a copy of *data* stripped of volatile fields for stable-diff comparison."""
    c = copy.deepcopy(data)
    c.pop("updated_at", None)
    c.pop("revision", None)
    rec = c.get("recovery")
    if isinstance(rec, dict):
        rec.pop("last_consistent_revision", None)
        rec.pop("last_consistent_at", None)
    return c


def _dump(data: dict) -> str:
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* atomically: tmp -> fsync -> os.replace -> dir fsync.

    Shared interruption-safe write idiom reused by the context map (Feature 008)
    so the ledger and the map use one durable-write path. An interrupted write
    leaves the previous file (if any) intact and never promotes a partial `.tmp`.
    """
    tmp_path = path.parent / (path.name + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    with open(tmp_path, "rb") as fh:
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(str(tmp_path), str(path))
    # Durability of the rename itself (FR-022): fsync the containing directory.
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass  # directory fsync is best-effort (not supported on all platforms)


# Back-compat private alias (retained so existing call sites need no change).
_atomic_write = atomic_write


class _LedgerLock:
    """Short-lived exclusive lock for a ledger's read-modify-write critical section.

    Uses an O_CREAT|O_EXCL lock file (portable). A lock older than ``stale``
    seconds (leaked by a killed process) is reclaimed. The revision compare in
    :func:`save` is the durable authority, so a lock is only an in-process
    serialization aid — it can never, on its own, cause a lost update.
    """

    def __init__(self, path: Path, timeout: float = 5.0, stale: float = 30.0) -> None:
        self.lock_path = Path(str(path) + ".lock")
        self.timeout = timeout
        self.stale = stale
        self._fd: int | None = None
        # Unique owner token stamped into the lock file so __exit__ never deletes
        # a lock another process created after reclaiming ours as stale.
        self._token = f"{os.getpid()}:{time.monotonic_ns()}".encode()

    def __enter__(self) -> _LedgerLock:
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._fd = os.open(
                    str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                )
                os.write(self._fd, self._token)
                os.fsync(self._fd)
                return self
            except FileExistsError:
                try:
                    age = time.time() - os.path.getmtime(self.lock_path)
                    if age > self.stale:
                        os.unlink(self.lock_path)
                        continue
                except OSError:
                    continue  # lock vanished between checks — retry
                if time.monotonic() >= deadline:
                    raise SpecopsError(
                        f"Ledger is locked by another process: {self.lock_path.name}. Retry."
                    ) from None
                time.sleep(0.05)

    def __exit__(self, *exc: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
        # Only remove the lock if it still carries OUR token — otherwise another
        # process reclaimed it as stale and now owns it (deleting it would break
        # their mutual exclusion).
        with contextlib.suppress(OSError):
            if self.lock_path.read_bytes() == self._token:
                os.unlink(self.lock_path)


def write_new(feature_dir: Path, data: dict) -> None:
    """Atomically write a brand-new ledger (init-spec). No CAS (file must be absent)."""
    _atomic_write(_ledger_path(feature_dir), _dump(data))


def save(feature_dir: Path, data: dict, *, base_revision: int) -> None:
    """Concurrency-safe, atomic, stable write of an existing ledger.

    - Acquires a short-lived lock, re-reads the on-disk revision; if it differs
      from *base_revision* raises StaleLedgerError (no write) — lost-update guard.
    - If the logical content is unchanged, returns without writing (byte-stable).
    - Otherwise advances the revision, refreshes timestamps and recovery metadata,
      and writes atomically.
    """
    path = _ledger_path(feature_dir)
    with _LedgerLock(path):
        on_disk: dict | None = None
        if path.is_file():
            on_disk = load_raw(feature_dir)
        disk_rev = revision_of(on_disk) if on_disk is not None else 0
        if on_disk is not None and disk_rev != base_revision:
            raise StaleLedgerError(
                f"Ledger moved on (on-disk revision {disk_rev} != {base_revision}). "
                "Re-read the current ledger and retry."
            )
        if on_disk is not None and _logical(on_disk) == _logical(data):
            return  # stable no-op: nothing logical changed (FR-011)

        new_rev = base_revision + 1
        ts = now_utc()
        data["revision"] = new_rev
        data["updated_at"] = ts
        rec = data.setdefault("recovery", {})
        rec["last_consistent_revision"] = new_rev
        rec["last_consistent_at"] = ts
        _atomic_write(path, _dump(data))
