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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from specops import evidence as evidence_mod
from specops import fsutil, gitops, records, speckit
from specops.errors import LedgerParseError, SpecopsError, StaleLedgerError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEDGER_FILENAME = "status.yaml"

CURRENT_SCHEMA = 9
OLDEST_SUPPORTED = 1  # v1 == a ledger with no `schema_version` key

# Feature 026 (v9) — supported recovery operations. An evidence record may carry
# `amendment: true` + `reason` recording a correction made after the task closed
# (`status amend-task`). Both fields are optional — a pre-v9 record simply lacks them
# (it is "not an amendment") — so the migration is a pure version bump with no
# backfill (parity with v6→v7 and v7→v8). The amendment supersedes the task's prior
# records through the existing `superseded_by` pointer rather than mutating them, so
# no other invariant changes. See specops.evidence / specops.status.cmd_amend_task.

# Feature 025 (v8) — review round integrity. A review cycle may carry a
# git-derived `reviewed_range` ("<from>..<to>") + `review_role` ("anchor" |
# "corrective") recording the scope that round's Step-3 review covered, and the
# ledger may carry a top-level `review_halt` marker when the round cap is hit.
# All fields are optional — a pre-v8 cycle/ledger simply lacks them, so the
# migration is a pure version bump with no backfill (parity with v6→v7). The
# reviewed-range endpoints are deliberately exempt from the reconcile
# registered-commit invariant (see reconcile.history_checks). See reviewscope.
_REVIEW_ROLES = ("anchor", "corrective")

# Feature 009 — the no-map context-provenance marker backfilled onto records
# that predate the map-provenance schema (v3). See contextmap.provenance_for.
NO_MAP_PROVENANCE: records.ContextProvenance = {"map": "none"}
_PROVENANCE_MAP_STATES = ("none", "invalid", "present")
DEFAULT_WORKFLOW_LANE = "full"

# Feature 010 (v4) — the top-level acknowledgements list. Each record marks a
# discovered (unplanned) effective-diff path as legitimate; see specops.trace.
ACK_FIELDS = ("path", "task", "reason")

# The ledger's human-work sentinel (R11): a commit value recorded as "(human)"
# marks work performed outside Git. Owned HERE (Feature 019 US4, FR-009) — the
# generic git layer knows nothing about it; callers that read ledger commit-ish
# values filter via is_human_commit before asking git about ancestry.
HUMAN_COMMIT = "(human)"

# Feature 012 (v6) — structured evidence. A top-level `evidence` list holds
# id-addressable records; tasks carry `evidence_refs` and findings an `evidence_id`
# into it. The legacy `<CLASS>:<summary>` string is retained; see specops.evidence.

# Feature 015 (v7) — external review ingestion. An imported finding is a normal
# Feature 011 finding carrying additive optional fields (`imported`, `producer`,
# `reviewed_digest`, `promotion`); see specops.ingestion / specops.handoff. The
# fields are optional — a pre-v7 finding simply lacks them (it is "not imported"),
# so the migration is a pure version bump with no backfill.

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


def is_human_commit(sha: str) -> bool:
    """True when *sha* is the ledger's ``(human)`` outside-Git work sentinel (R11)."""
    return sha == HUMAN_COMMIT


# ---------------------------------------------------------------------------
# Version classification (FR-001, FR-002)
# ---------------------------------------------------------------------------


def classify(data: records.LedgerLike) -> str:
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


def attach_lane_provenance(data: records.LedgerLike, lane_data: dict) -> records.LedgerLike:
    """Add additive lightweight-lane promotion provenance to a synthesized ledger.

    Feature 013: a promoted lane synthesizes a full ledger (this dict) that records it
    came from the lite lane. The keys are additive on the v6 schema (no schema bump):
    ``promoted_from_lane`` and a ``lane_provenance`` block carrying the lane's identity,
    baseline, eligibility answers, and stop-and-ask decisions, so the full workflow
    continues with populated context rather than an empty ledger (P-2). Promotion runs from
    an OPEN lane (INV-2 ⇒ no closure block), so there is no closure gate-evidence to carry;
    the deterministic gate evidence is produced later by the full review pipeline.
    """
    data["promoted_from_lane"] = True
    data["lane_provenance"] = {
        "lane_id": lane_data.get("lane_id"),
        "baseline": lane_data.get("baseline"),
        "eligibility": lane_data.get("eligibility"),
        "decisions": lane_data.get("decisions") or [],
    }
    return data


def migrate_to_current(data: records.LedgerLike) -> records.LedgerLike:
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
    backfill_evidence(out)
    return out


def backfill_context_provenance(data: records.LedgerLike) -> None:
    """Back-fill the explicit no-map provenance marker onto records lacking it.

    Feature 009 (v3): every task and review-cycle record carries a
    ``context_provenance`` object. Records written before v3 gain the explicit
    ``{"map": "none"}`` marker (never an omitted field, per FR-009/FR-018) so a
    pre-feature ledger stays readable and unambiguous. Idempotent.
    """
    for task in data.get("tasks") or []:
        if isinstance(task, dict):
            task.setdefault("context_provenance", NO_MAP_PROVENANCE.copy())
    for cycle in data.get("review_cycles") or []:
        if isinstance(cycle, dict):
            cycle.setdefault("context_provenance", NO_MAP_PROVENANCE.copy())


def _commit_range_for_task(task: records.TaskRecord | dict) -> str:
    """Best-effort commit range for a task's migrated evidence (baseline..HEAD-like)."""
    commits = [str(c) for c in (task.get("commits") or [])]
    if len(commits) > 1:
        return f"{commits[0]}..{commits[-1]}"
    if commits:
        return commits[-1]
    started = task.get("started_commit")
    return str(started) if started else ""


def backfill_evidence(data: records.LedgerLike) -> None:
    """Back-fill the top-level ``evidence`` list (Feature 012, v6). Idempotent.

    A ledger written before v6 has no ``evidence`` list; it gains an explicit empty
    list (never an omitted key). Each task's legacy ``<CLASS>:<summary>`` string is
    parsed into structured record(s), appended, and referenced by the task's
    ``evidence_refs`` — the legacy string is **retained** (never replaced), so
    Feature 010/011 rendering is unaffected (FR-007). Idempotent: a task that already
    carries ``evidence_refs`` is left untouched.
    """
    ev_list = data.get("evidence")
    if not isinstance(ev_list, list):
        ev_list = []
        data["evidence"] = ev_list
    fallback_ts = data.get("updated_at") or now_utc()
    for task in data.get("tasks") or []:
        if not isinstance(task, dict) or task.get("evidence_refs") is not None:
            continue
        refs: list[str] = []
        legacy = task.get("evidence")
        if isinstance(legacy, str) and legacy:
            ts = task.get("completed_at") or fallback_ts
            commit_range = _commit_range_for_task(task)
            for rec in evidence_mod.parse_legacy_string(
                legacy, timestamp=ts, commit_range=commit_range, subject=task.get("id"),
            ):
                stored = evidence_mod.append_record(ev_list, rec)
                refs.append(stored["id"])
        task["evidence_refs"] = refs


def backfill_acknowledgements(data: records.LedgerLike) -> None:
    """Back-fill the top-level ``acknowledgements`` list (Feature 010, v4). Idempotent.

    A ledger written before v4 has no acknowledgements; it gains an explicit empty
    list rather than an omitted key so a pre-feature ledger stays readable and a
    discovered path is simply ``unexplained`` until acknowledged (FR-016).
    """
    acks = data.get("acknowledgements")
    if not isinstance(acks, list):
        data["acknowledgements"] = []


def ensure_workflow_block(data: records.LedgerLike) -> None:
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


def validate_invariants(data: records.LedgerLike) -> list[str]:
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
    violations.extend(_evidence_violations(data))
    violations.extend(_reviewed_scope_violations(data))

    return violations


def _reviewed_scope_violations(data: records.LedgerLike) -> list[str]:
    """Structural checks on the optional v8 reviewed-scope fields (Feature 025).

    When a cycle carries a ``reviewed_range``/``review_role`` it MUST be a
    well-formed ``"<from>..<to>"`` string with non-empty endpoints and a valid
    role; a ``corrective`` role MUST have an earlier scoped round. These are
    string-shape checks only — never a git round-trip (resolvability is checked
    lazily by the coverage guard, so a rebased-away endpoint is not a violation).
    """
    out: list[str] = []
    seen_scope = False
    for cycle in data.get("review_cycles") or []:
        if not isinstance(cycle, dict):
            continue
        rng = cycle.get("reviewed_range")
        role = cycle.get("review_role")
        if rng is None and role is None:
            continue
        rnd = cycle.get("round")
        if not isinstance(rng, str) or rng.count("..") != 1 or not all(rng.split("..")):
            out.append(f"review cycle {rnd} reviewed_range is malformed: {rng!r}")
        if role not in _REVIEW_ROLES:
            out.append(f"review cycle {rnd} review_role is invalid: {role!r}")
        elif role == "corrective" and not seen_scope:
            out.append(f"review cycle {rnd} is corrective but no earlier scoped round exists")
        seen_scope = True
    return out


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


def finding_structural_defects(data: records.LedgerLike) -> list[tuple[str, str]]:
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


def _finding_violations(data: records.LedgerLike) -> list[str]:
    """Write-time invariant messages, derived from :func:`finding_structural_defects`."""
    return [msg for _kind, msg in finding_structural_defects(data)]


def _acknowledgement_violations(data: records.LedgerLike) -> list[str]:
    """Validate the optional ``acknowledgements`` list (Feature 010, v4).

    Absent is allowed (a pre-v4 ledger). When present each record MUST be a
    mapping carrying non-empty ``path``/``task``/``reason`` whose ``task`` matches
    a known non-orphaned task id (no dangling task reference, FR-007). An
    ``out_of_feature`` record (issue #63) instead carries only ``path``/``reason``
    (a tooling/methodology path that belongs to no task) — no ``task`` is required
    or checked.
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
        oof = isinstance(rec, dict) and bool(rec.get("out_of_feature"))
        required = ("path", "reason") if oof else ACK_FIELDS
        if not isinstance(rec, dict) or any(
            not isinstance(rec.get(f), str) or not rec.get(f) for f in required
        ):
            need = "path/reason" if oof else "path/task/reason"
            out.append(f"acknowledgement {i} is malformed ({need} required)")
            continue
        if oof and rec.get("task"):
            out.append(
                f"acknowledgement {i} is malformed "
                "(out_of_feature record must not carry a task)"
            )
            continue
        if not oof and rec["task"] not in known:
            out.append(
                f"acknowledgement {i} references unknown task '{rec['task']}'"
            )
    return out


def _evidence_violations(data: records.LedgerLike) -> list[str]:
    """Validate the optional v6 ``evidence`` list + its references (Feature 012).

    Absent is allowed (a pre-v6 or hand-built ledger). When present, each record MUST
    be a mapping with a non-empty, unique ``id``; every ``task.evidence_refs`` entry and
    every ``finding.evidence_id`` MUST resolve to a recorded evidence id (no dangling
    reference). Feature 026 (v9): a record marked ``amendment`` MUST carry a non-empty
    ``reason`` — an unexplained correction is the one thing the amendment path exists
    to prevent (the reason's *content* is never judged; only its presence).
    """
    ev = data.get("evidence")
    if ev is None:
        return []
    if not isinstance(ev, list):
        return ["evidence is not a list"]
    out: list[str] = []
    ids: set[str] = set()
    for i, rec in enumerate(ev):
        if not isinstance(rec, dict):
            out.append(f"evidence[{i}] is not a mapping")
            continue
        rid = rec.get("id")
        if not isinstance(rid, str) or not rid:
            out.append(f"evidence[{i}] missing id")
            continue
        if rid in ids:
            out.append(f"duplicate evidence id '{rid}'")
        ids.add(rid)
        if rec.get("amendment") and not rec.get("reason"):
            out.append(f"evidence '{rid}' is an amendment without a reason")
    for task in data.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        for ref in task.get("evidence_refs") or []:
            if ref not in ids:
                out.append(f"task '{task.get('id')}' references unknown evidence '{ref}'")
    for cycle in data.get("review_cycles") or []:
        handoff = cycle.get("handoff") if isinstance(cycle, dict) else None
        if not isinstance(handoff, dict):
            continue
        for f in handoff.get("findings") or []:
            eid = f.get("evidence_id") if isinstance(f, dict) else None
            if eid is not None and eid not in ids:
                out.append(f"finding '{f.get('id')}' references unknown evidence '{eid}'")
    return out


def _provenance_violations(record: Mapping[str, Any], label: str) -> list[str]:
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


def validate_identity(
    root: Path, repo: gitops.Repository, data: records.LedgerLike
) -> str | None:
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
    if baseline and not is_human_commit(baseline) and not gitops.is_ancestor(repo, baseline):
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


def ledger_path(feature_dir: Path) -> Path:
    """Return the canonical ``status.yaml`` path for *feature_dir*.

    Public cross-module contract (Feature 018): the single source of the ledger's
    on-disk location; lane resolves the ledger path through this rather than
    re-deriving it. Pure — never touches disk.
    """
    return feature_dir / LEDGER_FILENAME


def load_raw(feature_dir: Path) -> dict:
    """Read the ledger dict. Never mutates disk. Ignores any stale `.tmp` sidecar."""
    path = ledger_path(feature_dir)
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


def revision_of(data: records.LedgerLike) -> int:
    """Return the ledger revision (0 for a v1 ledger with no revision)."""
    rev = data.get("revision", 0)
    return rev if isinstance(rev, int) and not isinstance(rev, bool) else 0


def _logical(data: records.LedgerLike) -> records.LedgerLike:
    """Return a copy of *data* stripped of volatile fields for stable-diff comparison."""
    c = copy.deepcopy(data)
    c.pop("updated_at", None)
    c.pop("revision", None)
    rec = c.get("recovery")
    if isinstance(rec, dict):
        rec.pop("last_consistent_revision", None)
        rec.pop("last_consistent_at", None)
    return c


def _dump(data: records.LedgerLike) -> str:
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* atomically and durably.

    Public cross-module contract (Feature 018): the ledger, context map, lane
    state, and handoff revisions all write through this one name. The
    implementation is the shared :func:`specops.fsutil.atomic_write` (#25).
    """
    fsutil.atomic_write(path, content)


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
        # A reclaim holds the ``.reclaim`` sentinel only across a sub-millisecond
        # critical section, so a sentinel older than this was leaked by a reclaimer
        # that crashed mid-reclaim. It is kept well UNDER ``timeout`` (never the
        # main lock's ``stale``): reusing ``stale`` (30 s) here meant a leaked young
        # sentinel wedged every waiter until it aged out, long past the 5 s acquire
        # deadline — a stale main lock then failed to reclaim within ``timeout``,
        # spuriously raising "Ledger is locked by another process". The under-mutex
        # main-lock staleness re-check (not this bound) remains the guard that a
        # fresh lock is never deleted, so an aggressive bound stays correct.
        self._sentinel_stale = min(self.stale, self.timeout / 5)
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
                except OSError:
                    continue  # lock vanished between checks — retry
                if age > self.stale and self._reclaim_stale():
                    continue  # stale lock removed — compete via the normal O_EXCL create
                if time.monotonic() >= deadline:
                    raise SpecopsError(
                        f"Ledger is locked by another process: {self.lock_path.name}. Retry."
                    ) from None
                time.sleep(0.05)

    def _reclaim_stale(self) -> bool:
        """Single-winner removal of a stale main lock (Feature 019, FR-001).

        The old ``check-stale -> unlink -> recreate`` reclaim was a TOCTOU: two
        waiters could both observe "stale", and the slower one then deleted the
        *fresh* lock the faster one had just created — double-granting the
        critical section. Name-based operations cannot pin the checked inode
        (POSIX has no compare-and-unlink), so removal is serialized through a
        reclaim-mutex sentinel (``<lock>.reclaim``, O_CREAT|O_EXCL): only the
        sentinel holder may unlink the main lock, and it re-checks staleness
        UNDER the mutex first, so a freshly recreated lock is never touched.
        Returns True when this contender held the sentinel (the caller then
        competes through the normal O_EXCL create); False when another reclaim
        is in flight (the caller falls back to the ordinary wait loop). A
        sentinel leaked by a reclaimer that crashed mid-reclaim goes stale by
        age (``_sentinel_stale``, kept under ``timeout``) and is removed so a
        later pass within the same acquire deadline can retry.
        """
        sentinel = str(self.lock_path) + ".reclaim"
        try:
            fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - os.path.getmtime(sentinel) > self._sentinel_stale:
                    os.unlink(sentinel)  # leaked by a crashed reclaimer
            return False
        try:
            os.write(fd, self._token)
            with contextlib.suppress(OSError):
                if time.time() - os.path.getmtime(self.lock_path) > self.stale:
                    os.unlink(self.lock_path)
            return True
        finally:
            os.close(fd)
            # Token-checked, like __exit__: never delete a sentinel another
            # process now owns (possible only after a stale-sentinel break).
            with contextlib.suppress(OSError):
                if Path(sentinel).read_bytes() == self._token:
                    os.unlink(sentinel)

    def __exit__(self, *exc: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
        # Only remove the lock if it still carries OUR token — otherwise another
        # process reclaimed it as stale and now owns it (deleting it would break
        # their mutual exclusion).
        with contextlib.suppress(OSError):
            if self.lock_path.read_bytes() == self._token:
                os.unlink(self.lock_path)


def write_new(feature_dir: Path, data: records.LedgerLike) -> None:
    """Atomically write a brand-new ledger (init-spec). No CAS (file must be absent)."""
    _atomic_write(ledger_path(feature_dir), _dump(data))


def save(feature_dir: Path, data: records.LedgerLike, *, base_revision: int) -> None:
    """Concurrency-safe, atomic, stable write of an existing ledger.

    - Acquires a short-lived lock, re-reads the on-disk revision; if it differs
      from *base_revision* raises StaleLedgerError (no write) — lost-update guard.
    - If the logical content is unchanged, returns without writing (byte-stable).
    - Otherwise advances the revision, refreshes timestamps and recovery metadata,
      and writes atomically.
    """
    path = ledger_path(feature_dir)
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
