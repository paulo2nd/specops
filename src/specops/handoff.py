"""Structured corrective handoffs (Feature 011).

Promotes review findings and correction authorization from free-form
``revisions/revision-X.md`` prose to first-class, versioned **ledger state**: a
per-review-cycle handoff holding structured findings (stable ``R<round>-F<NN>``
ids, ``blocking``/``advisory`` severity, per-finding expected evidence + closure
criteria), an ``OPEN -> FIXED -> VERIFIED`` lifecycle, and the feature-global
blocking-approval invariant that keeps a review un-approvable while any blocking
finding is unverified.

Read commands (``validate``/``report``) never mutate state. State-changing
commands (``finding add``/``authorize``/``fix``/``verify``/``close``/``import``)
route through the ledger's atomic + revision-CAS write via :mod:`specops.status`.
The findings are authoritative; ``revisions/revision-X.md`` is a rendered
projection (``render_revision``). No Spec Kit primitive is reimplemented and no
language-specific parser is added — the handoff is deterministic ledger state.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specops import gitops, ledger, outcome, speckit, status, trace
from specops.errors import SpecopsError

# --- Versioned JSON contract (FR-012) --------------------------------------
OUTPUT_VERSION = 1

# --- Status vocabulary (data-model: status -> class -> exit) ----------------
FINDING_RECORDED = "finding_recorded"
HANDOFF_AUTHORIZED = "handoff_authorized"
FINDING_FIXED = "finding_fixed"
FINDING_VERIFIED = "finding_verified"
FINDING_DISMISSED = "finding_dismissed"
HANDOFF_CLOSED = "handoff_closed"
HANDOFF_ALREADY_CLOSED = "handoff_already_closed"
VALIDATE_OK = "validate_ok"
REPORT_OK = "report_ok"
RENDER_OK = "render_ok"

APPROVAL_BLOCKED = "approval_blocked"
CLOSE_BLOCKED = "close_blocked"
DANGLING_REFERENCE = "dangling_reference"
MISSING_CLOSURE = "missing_closure"
CONTRADICTORY_STATE = "contradictory_state"
DUPLICATE_ID = "duplicate_id"

ILLEGAL_TRANSITION = "illegal_transition"
PRECONDITION_UNMET = "precondition_unmet"
UNKNOWN_TASK = "unknown_task"
UNKNOWN_FINDING = "unknown_finding"
DUPLICATE_ID_CREATE = "duplicate_id_create"
NOT_A_REPO = "not_a_repo"
BAD_ARGS = "bad_args"

_CLASS_FOR_STATUS = {
    FINDING_RECORDED: outcome.PASS,
    HANDOFF_AUTHORIZED: outcome.PASS,
    FINDING_FIXED: outcome.PASS,
    FINDING_VERIFIED: outcome.PASS,
    FINDING_DISMISSED: outcome.PASS,
    HANDOFF_CLOSED: outcome.PASS,
    HANDOFF_ALREADY_CLOSED: outcome.PASS,
    VALIDATE_OK: outcome.PASS,
    REPORT_OK: outcome.PASS,
    RENDER_OK: outcome.PASS,
    APPROVAL_BLOCKED: outcome.GATE_REJECTION,
    CLOSE_BLOCKED: outcome.GATE_REJECTION,
    DANGLING_REFERENCE: outcome.GATE_REJECTION,
    MISSING_CLOSURE: outcome.GATE_REJECTION,
    CONTRADICTORY_STATE: outcome.GATE_REJECTION,
    DUPLICATE_ID: outcome.GATE_REJECTION,
    ILLEGAL_TRANSITION: outcome.INFRA_ERROR,
    PRECONDITION_UNMET: outcome.INFRA_ERROR,
    UNKNOWN_TASK: outcome.INFRA_ERROR,
    UNKNOWN_FINDING: outcome.INFRA_ERROR,
    DUPLICATE_ID_CREATE: outcome.INFRA_ERROR,
    NOT_A_REPO: outcome.INFRA_ERROR,
    BAD_ARGS: outcome.INFRA_ERROR,
}

_SEVERITY_RANK = {"blocking": 0, "advisory": 1}


@dataclass
class HandoffResult:
    """A render-agnostic command outcome consumed by the CLI (mirrors
    :class:`specops.trace.TraceResult`)."""

    command: str
    status: str
    human: str
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def cls(self) -> str:
        return _CLASS_FOR_STATUS[self.status]

    @property
    def exit_code(self) -> int:
        return outcome.exit_for(self.cls)


# ---------------------------------------------------------------------------
# Ledger accessors (pure)
# ---------------------------------------------------------------------------


def _feature_dir(root: Path) -> Path | None:
    return speckit.resolve_feature_dir(root)


def _cycles(data: dict) -> list[dict]:
    return [c for c in data.get("review_cycles") or [] if isinstance(c, dict)]


def _current_cycle(data: dict) -> dict | None:
    """The current round = the latest review-cycle record (or None)."""
    cycles = _cycles(data)
    return cycles[-1] if cycles else None


def _ensure_handoff(cycle: dict) -> dict:
    handoff = cycle.get("handoff")
    if not isinstance(handoff, dict):
        handoff = cycle["handoff"] = {
            "authorized_paths": [], "closed_at": None, "findings": [],
        }
    handoff.setdefault("authorized_paths", [])
    handoff.setdefault("closed_at", None)
    handoff.setdefault("findings", [])
    return handoff


def _iter_findings(data: dict) -> Iterator[tuple[dict, dict]]:
    """Yield (cycle, finding) for every structured finding across all cycles."""
    for cycle in _cycles(data):
        handoff = cycle.get("handoff")
        if isinstance(handoff, dict):
            for f in handoff.get("findings") or []:
                if isinstance(f, dict):
                    yield cycle, f


def _find_by_id(data: dict, fid: str) -> tuple[dict, dict] | None:
    for cycle, f in _iter_findings(data):
        if f.get("id") == fid:
            return cycle, f
    return None


def _next_id(cycle: dict) -> str:
    handoff = _ensure_handoff(cycle)
    return f"R{cycle.get('round')}-F{len(handoff['findings']) + 1:02d}"


def _sort_key(cycle: dict, f: dict) -> tuple:  # noqa: ANN401 (heterogeneous sort key)
    line = f.get("line")
    return (
        cycle.get("round") or 0,
        _SEVERITY_RANK.get(str(f.get("severity")), 9),
        f.get("file") or "",
        line if isinstance(line, int) else -1,
        f.get("id") or "",
    )


def _canonical(data: dict) -> list[tuple[dict, dict]]:
    """Every (cycle, finding) in canonical order (round, severity, file, line, id)."""
    return sorted(_iter_findings(data), key=lambda cf: _sort_key(*cf))


def blocking_approval_check(data: dict) -> list[str]:
    """Ids of every ``blocking`` finding across all cycles that is not resolved.

    Feature-global (all rounds). A blocking finding is resolved once it is
    ``VERIFIED`` or ``DISMISSED``; empty ⇒ approval permitted / every handoff is
    closable; empty also when no handoffs exist (degrade to the Feature 006 gate).
    Sorted by canonical order for a stable, actionable diagnostic. A finding
    lacking a usable ``id`` is skipped here (it is a ledger defect surfaced by
    ``handoff validate``, not a silent, un-nameable blocker).
    """
    return _unresolved_blocking_ids(f for _cycle, f in _canonical(data))


def _is_resolved(finding: dict) -> bool:
    """A blocking finding no longer gates approval once VERIFIED or DISMISSED."""
    return finding.get("state") in ("VERIFIED", "DISMISSED")


def _unresolved_blocking_ids(findings: Iterator[dict]) -> list[str]:
    """Ids of the blocking, unresolved findings in *findings* (with a usable id)."""
    return [
        f["id"] for f in findings
        if f.get("severity") == "blocking" and not _is_resolved(f)
        and isinstance(f.get("id"), str)
    ]


# ---------------------------------------------------------------------------
# State-changing commands
# ---------------------------------------------------------------------------


def _load_write(
    root: Path,
) -> HandoffResult | tuple[Path, dict, int, list[str], Any]:
    """Shared write preamble: repo check + identity/CAS load. Returns
    (feature_dir, data, base_rev, base_violations, repo) or a HandoffResult on
    the not-a-repo usage error."""
    repo = gitops.find_repo(root)
    if repo is None:
        return HandoffResult("handoff", NOT_A_REPO, "handoff: not a Git repository")
    feature_dir = status._get_feature_dir(root)
    data, base_rev, base_violations, _repo = status._load_for_write(root, feature_dir)
    return feature_dir, data, base_rev, base_violations, repo


def cmd_finding_add(
    root: Path, *, severity: str, rule: str, file: str, line: int | None,
    action: str, expected_evidence: str, closure: str,
) -> HandoffResult:
    """Record a structured finding in the current round's handoff (FR-001)."""
    cmd = "handoff finding add"
    severity = (severity or "").strip()
    if severity not in ledger.SEVERITIES:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: invalid severity '{severity}'")
    file = trace._norm(file) if file else ""
    for name, val in (("--rule", rule), ("--file", file), ("--action", action)):
        if not (val or "").strip():
            return HandoffResult(cmd, BAD_ARGS, f"{cmd}: {name} is required")
    ee, cl = (expected_evidence or "").strip(), (closure or "").strip()
    if severity == "blocking" and not (ee and cl):
        return HandoffResult(
            cmd, BAD_ARGS,
            f"{cmd}: a blocking finding requires --expected-evidence and --closure")

    loaded = _load_write(root)
    if isinstance(loaded, HandoffResult):
        return HandoffResult(cmd, loaded.status, loaded.human)
    feature_dir, data, base_rev, base_violations, _repo = loaded

    cycle = _current_cycle(data)
    if cycle is None:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: no open review cycle to attach a finding to")
    existing = cycle.get("handoff")
    if isinstance(existing, dict) and existing.get("closed_at"):
        return HandoffResult(cmd, BAD_ARGS,
                             f"{cmd}: the round's handoff is closed; open a new review round")
    handoff = _ensure_handoff(cycle)
    fid = _next_id(cycle)
    if _find_by_id(data, fid) is not None:
        return HandoffResult(cmd, DUPLICATE_ID_CREATE, f"{cmd}: finding id '{fid}' already exists",
                             {"id": fid})

    handoff["findings"].append({
        "id": fid, "severity": severity, "rule": rule.strip(), "file": file,
        "line": line, "action": action.strip(),
        "expected_evidence": (expected_evidence or "").strip() or None,
        "closure_criteria": (closure or "").strip() or None,
        "state": "OPEN", "task": None, "commits": [], "evidence": None,
        "fixed_at": None, "verified_at": None,
    })
    status._finalize(feature_dir, data, base_rev, base_violations)
    return HandoffResult(cmd, FINDING_RECORDED, f"{cmd}: recorded {fid} ({severity})", {"id": fid})


def cmd_authorize(root: Path, paths: list[str]) -> HandoffResult:
    """Set/extend the current round handoff's authorized corrective paths (FR-009)."""
    cmd = "handoff authorize"
    norm = [trace._norm(p) for p in paths if (p or "").strip()]
    if not norm:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: at least one --path is required")
    loaded = _load_write(root)
    if isinstance(loaded, HandoffResult):
        return HandoffResult(cmd, loaded.status, loaded.human)
    feature_dir, data, base_rev, base_violations, _repo = loaded
    cycle = _current_cycle(data)
    if cycle is None:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: no open review cycle")
    handoff = _ensure_handoff(cycle)
    for p in norm:
        if p not in handoff["authorized_paths"]:
            handoff["authorized_paths"].append(p)
    status._finalize(feature_dir, data, base_rev, base_violations)
    return HandoffResult(cmd, HANDOFF_AUTHORIZED,
                         f"{cmd}: authorized {len(norm)} path(s)",
                         {"authorized_paths": list(handoff["authorized_paths"])})


def cmd_finding_fix(
    root: Path, fid: str, *, task: str, commits: list[str],
    evidence: str | None, auto: bool,
) -> HandoffResult:
    """OPEN -> FIXED: link the resolving task, commit(s), and evidence (FR-005)."""
    cmd = "handoff finding fix"
    loaded = _load_write(root)
    if isinstance(loaded, HandoffResult):
        return HandoffResult(cmd, loaded.status, loaded.human)
    feature_dir, data, base_rev, base_violations, repo = loaded

    located = _find_by_id(data, fid)
    if located is None:
        return HandoffResult(cmd, UNKNOWN_FINDING, f"{cmd}: unknown finding '{fid}'", {"id": fid})
    _cycle, finding = located
    if finding.get("state") != "OPEN":
        return HandoffResult(cmd, ILLEGAL_TRANSITION,
                             f"{cmd}: finding '{fid}' is {finding.get('state')}, not OPEN",
                             {"id": fid})

    tasks = {t.get("id"): t for t in data.get("tasks") or [] if isinstance(t, dict)}
    task_rec = tasks.get(task)
    if task_rec is None:
        return HandoffResult(cmd, UNKNOWN_TASK, f"{cmd}: unknown task '{task}'", {"id": fid})

    commits = list(commits or [])
    if auto:
        # Prefer the task's own recorded commits (scoped to that task) over the
        # whole started_commit..HEAD range, which would sweep in unrelated work
        # from other tasks that landed on the branch in between.
        if not commits:
            recorded = task_rec.get("commits")
            if recorded:
                commits = list(recorded)
            elif task_rec.get("started_commit"):
                commits = gitops.commits_in_range(repo, task_rec["started_commit"])
        evidence = evidence or task_rec.get("evidence")
    if not commits:
        return HandoffResult(cmd, PRECONDITION_UNMET,
                             f"{cmd}: at least one --commit (or --auto) is required", {"id": fid})
    if not evidence or not status._validate_evidence(evidence):
        return HandoffResult(cmd, PRECONDITION_UNMET,
                             f"{cmd}: valid <CLASS>:<summary> --evidence is required", {"id": fid})

    finding.update({
        "state": "FIXED", "task": task, "commits": commits,
        "evidence": evidence, "fixed_at": ledger.now_utc(),
    })
    status._finalize(feature_dir, data, base_rev, base_violations)
    return HandoffResult(cmd, FINDING_FIXED, f"{cmd}: {fid} -> FIXED (task {task})", {"id": fid})


def cmd_finding_verify(root: Path, fid: str) -> HandoffResult:
    """FIXED -> VERIFIED: mechanical precondition (evidence present + links resolve),
    no auto-verify; the reviewer's call is the closure judgment (FR-006)."""
    cmd = "handoff finding verify"
    loaded = _load_write(root)
    if isinstance(loaded, HandoffResult):
        return HandoffResult(cmd, loaded.status, loaded.human)
    feature_dir, data, base_rev, base_violations, _repo = loaded

    located = _find_by_id(data, fid)
    if located is None:
        return HandoffResult(cmd, UNKNOWN_FINDING, f"{cmd}: unknown finding '{fid}'", {"id": fid})
    _cycle, finding = located
    if finding.get("state") != "FIXED":
        return HandoffResult(cmd, ILLEGAL_TRANSITION,
                             f"{cmd}: finding '{fid}' is {finding.get('state')}, not FIXED "
                             "(cannot verify before it is fixed)", {"id": fid})
    if not (finding.get("evidence") and finding.get("task") and finding.get("commits")):
        return HandoffResult(cmd, PRECONDITION_UNMET,
                             f"{cmd}: finding '{fid}' missing evidence/task/commit links",
                             {"id": fid})

    finding.update({"state": "VERIFIED", "verified_at": ledger.now_utc()})
    status._finalize(feature_dir, data, base_rev, base_violations)
    return HandoffResult(cmd, FINDING_VERIFIED, f"{cmd}: {fid} -> VERIFIED", {"id": fid})


def cmd_finding_dismiss(root: Path, fid: str, *, reason: str) -> HandoffResult:
    """Withdraw a finding to the terminal DISMISSED state with an audited reason.

    Escape hatch for a false-positive or superseded-round finding: it stops
    gating approval without fabricating a fix (no task/commit/evidence link).
    An already-VERIFIED finding is not dismissable (it was genuinely resolved)."""
    cmd = "handoff finding dismiss"
    reason = (reason or "").strip()
    if not reason:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: --reason is required", {"id": fid})
    loaded = _load_write(root)
    if isinstance(loaded, HandoffResult):
        return HandoffResult(cmd, loaded.status, loaded.human)
    feature_dir, data, base_rev, base_violations, _repo = loaded

    located = _find_by_id(data, fid)
    if located is None:
        return HandoffResult(cmd, UNKNOWN_FINDING, f"{cmd}: unknown finding '{fid}'", {"id": fid})
    _cycle, finding = located
    if finding.get("state") in ("VERIFIED", "DISMISSED"):
        return HandoffResult(cmd, ILLEGAL_TRANSITION,
                             f"{cmd}: finding '{fid}' is {finding.get('state')}; not dismissable",
                             {"id": fid})

    finding.update({"state": "DISMISSED", "dismiss_reason": reason,
                    "verified_at": ledger.now_utc()})
    status._finalize(feature_dir, data, base_rev, base_violations)
    return HandoffResult(cmd, FINDING_DISMISSED, f"{cmd}: {fid} -> DISMISSED", {"id": fid})


def cmd_close(root: Path) -> HandoffResult:
    """Close the current round's handoff once all its blocking findings are VERIFIED
    (idempotent re-close; else close-blocked). FR-023."""
    cmd = "handoff close"
    loaded = _load_write(root)
    if isinstance(loaded, HandoffResult):
        return HandoffResult(cmd, loaded.status, loaded.human)
    feature_dir, data, base_rev, base_violations, _repo = loaded

    cycle = _current_cycle(data)
    handoff = cycle.get("handoff") if cycle else None
    if not isinstance(handoff, dict):
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: no handoff in the current round to close")
    if handoff.get("closed_at"):
        return HandoffResult(cmd, HANDOFF_ALREADY_CLOSED, f"{cmd}: already closed (idempotent)")

    unverified = _unresolved_blocking_ids(iter(handoff.get("findings") or []))
    if unverified:
        return HandoffResult(cmd, CLOSE_BLOCKED,
                             f"{cmd}: unverified blocking findings remain: {', '.join(unverified)}",
                             {"unverified": unverified})
    handoff["closed_at"] = ledger.now_utc()
    status._finalize(feature_dir, data, base_rev, base_violations)
    return HandoffResult(cmd, HANDOFF_CLOSED, f"{cmd}: handoff closed")


def cmd_import(root: Path, round: int | None) -> HandoffResult:
    """Import legacy revision-X.md prose into structured advisory/OPEN findings (FR-014)."""
    cmd = "handoff import"
    loaded = _load_write(root)
    if isinstance(loaded, HandoffResult):
        return HandoffResult(cmd, loaded.status, loaded.human)
    feature_dir, data, base_rev, base_violations, _repo = loaded

    cycle = None
    if round is None:
        cycle = _current_cycle(data)
    else:
        cycle = next((c for c in _cycles(data) if c.get("round") == round), None)
    if cycle is None:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: no matching review cycle")
    rnd = cycle.get("round")
    rev = feature_dir / "revisions" / f"revision-{rnd}.md"
    if not rev.is_file():
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: no prose at revisions/revision-{rnd}.md")

    handoff = _ensure_handoff(cycle)
    # Idempotent: skip a legacy line already present as a finding (same
    # file/line/action), so re-running import never duplicates findings.
    seen = {(f.get("file"), f.get("line"), f.get("action"))
            for f in handoff["findings"]}
    imported = 0
    for raw in rev.read_text(encoding="utf-8").splitlines():
        m = trace._FINDING_RE.match(raw.strip())
        if not m:
            continue
        file = trace._norm(m.group("file"))
        line = int(m.group("line")) if m.group("line") else None
        action = m.group("text").strip()
        if (file, line, action) in seen:
            continue
        seen.add((file, line, action))
        handoff["findings"].append({
            "id": _next_id(cycle), "severity": "advisory", "rule": "imported",
            "file": file, "line": line, "action": action,
            "expected_evidence": None, "closure_criteria": None,
            "state": "OPEN", "task": None, "commits": [], "evidence": None,
            "fixed_at": None, "verified_at": None,
        })
        imported += 1
    if imported == 0:
        return HandoffResult(cmd, FINDING_RECORDED,
                             f"{cmd}: nothing new to import (idempotent)", {"imported": 0})
    status._finalize(feature_dir, data, base_rev, base_violations)
    return HandoffResult(cmd, FINDING_RECORDED, f"{cmd}: imported {imported} finding(s)",
                         {"imported": imported})


# ---------------------------------------------------------------------------
# Read-only commands
# ---------------------------------------------------------------------------


def _load_read(root: Path) -> dict:
    feature_dir = _feature_dir(root)
    if feature_dir is None:
        raise SpecopsError("Cannot resolve active feature directory.")
    if not (feature_dir / "status.yaml").is_file():
        return {}
    return ledger.load_raw(feature_dir)


# Map a ledger structural-defect kind → the handoff validate status (all
# GATE_REJECTION / exit 1). Malformation/enum defects share CONTRADICTORY_STATE.
_STRUCTURAL_DEFECT_STATUS = {
    ledger.FINDING_DEFECT_MALFORMED: CONTRADICTORY_STATE,
    ledger.FINDING_DEFECT_SEVERITY: CONTRADICTORY_STATE,
    ledger.FINDING_DEFECT_STATE: CONTRADICTORY_STATE,
    ledger.FINDING_DEFECT_MISSING_CLOSURE: MISSING_CLOSURE,
    ledger.FINDING_DEFECT_CONTRADICTORY: CONTRADICTORY_STATE,
    ledger.FINDING_DEFECT_DUPLICATE_ID: DUPLICATE_ID,
}


def cmd_validate(root: Path) -> HandoffResult:
    """Read-only: fail closed on any handoff defect, one diagnostic per defect (FR-010).

    Structural defects (malformed shape, invalid severity/state, missing closure,
    contradictory state, duplicate id) come from the shared
    :func:`ledger.finding_structural_defects` — the same source of truth as the
    write-time invariant, so the two can never disagree. Reference-resolution
    defects (unknown task, unresolvable commit) need repo/ledger context and are
    added here; commit existence is deferred to ``specops reconcile`` (FR-011)."""
    cmd = "handoff validate"
    data = _load_read(root)
    repo = gitops.find_repo(root)
    known_tasks = {t.get("id") for t in data.get("tasks") or [] if isinstance(t, dict)}

    defects: list[tuple[str, str]] = [  # (status, message)
        (_STRUCTURAL_DEFECT_STATUS[kind], msg)
        for kind, msg in ledger.finding_structural_defects(data)
    ]
    for _cycle, f in _canonical(data):
        fid = str(f.get("id"))
        task = f.get("task")
        if task and task not in known_tasks:
            defects.append((DANGLING_REFERENCE, f"{fid}: references unknown task '{task}'"))
        if repo is not None:
            for sha in f.get("commits") or []:
                if not gitops.is_ancestor(repo, sha):
                    defects.append((DANGLING_REFERENCE,
                                    f"{fid}: references unresolvable commit '{sha[:7]}' "
                                    "(existence enforced by 'specops reconcile')"))

    if not defects:
        return HandoffResult(cmd, VALIDATE_OK, f"{cmd}: OK — no handoff defects", {"defects": []})
    # Deterministic representative status: first by a fixed defect priority.
    priority = [DANGLING_REFERENCE, MISSING_CLOSURE, CONTRADICTORY_STATE, DUPLICATE_ID]
    rep = min((s for s, _ in defects), key=priority.index)
    human = f"{cmd}: {len(defects)} defect(s)\n" + "\n".join(f"  - {m}" for _s, m in defects)
    return HandoffResult(cmd, rep, human, {"defects": [m for _s, m in defects]})


def _finding_view(cycle: dict, f: dict) -> dict:
    return {
        "id": f.get("id"), "round": cycle.get("round"), "severity": f.get("severity"),
        "rule": f.get("rule"), "file": f.get("file"), "line": f.get("line"),
        "state": f.get("state"), "action": f.get("action"),
        "task": f.get("task"), "commits": list(f.get("commits") or []),
        "evidence": f.get("evidence"),
    }


def cmd_report(root: Path) -> HandoffResult:
    """Read-only: render every handoff + the remaining unverified blocking set,
    human and JSON from the same view (parity, FR-012)."""
    cmd = "handoff report"
    data = _load_read(root)
    views = [_finding_view(c, f) for c, f in _canonical(data)]
    remaining = blocking_approval_check(data)

    if not views:
        human = f"{cmd}: no structured findings"
    else:
        lines = [f"{cmd}: {len(views)} finding(s)"]
        for v in views:
            loc = f"{v['file']}:{v['line']}" if v["line"] is not None else v["file"]
            lines.append(
                f"  {v['id']} [{v['severity']}] {v['state']} {loc} — {v['action']}"
                + (f" (task {v['task']}, {len(v['commits'])} commit(s))" if v["task"] else "")
            )
        if remaining:
            lines.append(f"  remaining blocking: {', '.join(remaining)}")
        human = "\n".join(lines)
    return HandoffResult(cmd, REPORT_OK, human,
                         {"findings": views, "remaining_blocking": remaining})


# ---------------------------------------------------------------------------
# Revision-X.md projection (FR-013)
# ---------------------------------------------------------------------------


def render_revision_text(data: dict, round: int) -> str:
    """Deterministic revision-X.md content projected from a round's handoff.

    Line format is the 010-compatible ``<file>:<line> - <action>`` (ids live in
    the ledger, not the human line). Zero findings -> ``APPROVED``. Canonical order.
    """
    cycle = next((c for c in _cycles(data) if c.get("round") == round), None)
    findings = []
    if cycle is not None and isinstance(cycle.get("handoff"), dict):
        findings = [f for c, f in _canonical(data) if c is cycle]
    if not findings:
        return "APPROVED\n"
    lines = []
    for f in findings:
        loc = f"{f['file']}:{f['line']}" if f.get("line") is not None else f.get("file")
        lines.append(f"{loc} - {f.get('action')}")
    return "\n".join(lines) + "\n"


def render_revision(root: Path, round: int) -> HandoffResult:
    """Write revisions/revision-<round>.md from the structured state (FR-013).

    Refuses when the round has **no** structured handoff — otherwise it would
    overwrite a legacy, hand-authored revision file with ``APPROVED`` and destroy
    the recorded findings (a round with a handoff but zero findings renders
    ``APPROVED`` legitimately)."""
    cmd = "handoff render"
    feature_dir = _feature_dir(root)
    if feature_dir is None:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: cannot resolve feature directory")
    data = _load_read(root)
    cycle = next((c for c in _cycles(data) if c.get("round") == round), None)
    if cycle is None or not isinstance(cycle.get("handoff"), dict):
        return HandoffResult(cmd, BAD_ARGS,
                             f"{cmd}: round {round} has no structured handoff to render "
                             "(refusing to overwrite any legacy revision file)")
    text = render_revision_text(data, round)
    rev_dir = feature_dir / "revisions"
    rev_dir.mkdir(parents=True, exist_ok=True)
    ledger.atomic_write(rev_dir / f"revision-{round}.md", text)
    return HandoffResult(cmd, RENDER_OK, f"{cmd}: wrote revisions/revision-{round}.md",
                         {"round": round})
