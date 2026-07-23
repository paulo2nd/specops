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
    """Ids of every ``blocking`` finding across all cycles that is not ``VERIFIED``.

    Feature-global (all rounds). Empty ⇒ approval permitted / every handoff is
    closable; empty also when no handoffs exist (degrade to the Feature 006 gate).
    Sorted by canonical order for a stable, actionable diagnostic.
    """
    return [
        f["id"] for cycle, f in _canonical(data)
        if f.get("severity") == "blocking" and f.get("state") != "VERIFIED"
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
        started = task_rec.get("started_commit") or ""
        if started:
            commits = commits or gitops.commits_in_range(repo, started)
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

    unverified = [
        f["id"] for f in handoff.get("findings") or []
        if f.get("severity") == "blocking" and f.get("state") != "VERIFIED"
    ]
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
    imported = 0
    for raw in rev.read_text(encoding="utf-8").splitlines():
        m = trace._FINDING_RE.match(raw.strip())
        if not m:
            continue
        handoff["findings"].append({
            "id": _next_id(cycle), "severity": "advisory", "rule": "imported",
            "file": trace._norm(m.group("file")), "line": int(m.group("line")),
            "action": m.group("text").strip(),
            "expected_evidence": None, "closure_criteria": None,
            "state": "OPEN", "task": None, "commits": [], "evidence": None,
            "fixed_at": None, "verified_at": None,
        })
        imported += 1
    if imported == 0:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: no importable finding lines found")
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


def cmd_validate(root: Path) -> HandoffResult:
    """Read-only: fail closed on any handoff defect, one diagnostic per defect (FR-010)."""
    cmd = "handoff validate"
    data = _load_read(root)
    repo = gitops.find_repo(root)
    known_tasks = {t.get("id") for t in data.get("tasks") or [] if isinstance(t, dict)}

    defects: list[tuple[str, str]] = []  # (status, message)
    seen: dict[str, int] = {}
    for _cycle, f in _canonical(data):
        fid = str(f.get("id"))
        state = f.get("state")
        task = f.get("task")
        seen[fid] = seen.get(fid, 0) + 1
        # (b) missing closure on a blocking finding
        if f.get("severity") == "blocking" and not (
            f.get("closure_criteria") and f.get("expected_evidence")
        ):
            defects.append((MISSING_CLOSURE, f"{fid}: blocking finding missing closure criteria"))
        # (c) contradictory state
        if state == "VERIFIED" and not f.get("evidence"):
            defects.append((CONTRADICTORY_STATE, f"{fid}: VERIFIED without linked evidence"))
        if state in ("FIXED", "VERIFIED") and not (task and f.get("commits")):
            defects.append((CONTRADICTORY_STATE, f"{fid}: {state} without task/commit link"))
        # (a) dangling reference: task, or commit not resolvable (existence -> reconcile)
        if task and task not in known_tasks:
            defects.append((DANGLING_REFERENCE, f"{fid}: references unknown task '{task}'"))
        if repo is not None:
            for sha in f.get("commits") or []:
                if not gitops.is_ancestor(repo, sha):
                    defects.append((DANGLING_REFERENCE,
                                    f"{fid}: references unresolvable commit '{sha[:7]}' "
                                    "(existence enforced by 'specops reconcile')"))
    # (d) duplicate id
    for fid, n in sorted(seen.items()):
        if n > 1:
            defects.append((DUPLICATE_ID, f"duplicate finding id '{fid}'"))

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
    """Write revisions/revision-<round>.md from the structured state (FR-013)."""
    cmd = "handoff render"
    feature_dir = _feature_dir(root)
    if feature_dir is None:
        return HandoffResult(cmd, BAD_ARGS, f"{cmd}: cannot resolve feature directory")
    data = _load_read(root)
    text = render_revision_text(data, round)
    rev_dir = feature_dir / "revisions"
    rev_dir.mkdir(parents=True, exist_ok=True)
    ledger.atomic_write(rev_dir / f"revision-{round}.md", text)
    return HandoffResult(cmd, RENDER_OK, f"{cmd}: wrote revisions/revision-{round}.md",
                         {"round": round})
