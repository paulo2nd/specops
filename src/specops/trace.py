"""End-to-end traceability (Feature 010).

Materializes a deterministic trace — success criterion → task → contexts/paths →
commits → evidence → review findings → corrections — out of the Git-verifiable
ledger (Feature 006) and context provenance (Feature 009), and classifies every
**effective-diff** path as ``planned`` / ``discovered-and-acknowledged`` /
``unexplained`` so review blocks only unexplained drift.

Read commands (``classify``/``report``/``validate``) never mutate state. The sole
state-changing action (``acknowledge``) routes through the ledger's atomic +
revision-CAS write via :mod:`specops.status`. No Spec Kit primitive is
reimplemented and no language-specific parser is added — the trace is a *read*.
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from specops import contextmap, gitops, ledger, speckit, status
from specops.errors import SpecopsError

# --- Versioned JSON contract (FR-014) --------------------------------------
OUTPUT_VERSION = 1

# --- Path classes (closed set, FR-003) -------------------------------------
PLANNED = "planned"
DISCOVERED = "discovered-and-acknowledged"
UNEXPLAINED = "unexplained"

# --- Status vocabulary (R8) ------------------------------------------------
TRACE_OK = "trace_ok"
DRIFT_CLEAN = "drift_clean"
DRIFT_BLOCKED = "drift_blocked"
TRACE_INCOMPLETE = "trace_incomplete"
ACK_RECORDED = "ack_recorded"
ACK_IDEMPOTENT = "ack_idempotent"
ACK_ALREADY_PLANNED = "ack_already_planned"
ACK_CONFLICT = "ack_conflict"
ACK_UNKNOWN_TASK = "ack_unknown_task"
USAGE_ERROR = "usage_error"

# outcome class per status: pass(0) / gate-rejection(1) / infra-error(2)
from specops import outcome  # noqa: E402  (imported after constants for clarity)

_CLASS_FOR_STATUS = {
    TRACE_OK: outcome.PASS,
    DRIFT_CLEAN: outcome.PASS,
    ACK_RECORDED: outcome.PASS,
    ACK_IDEMPOTENT: outcome.PASS,
    ACK_ALREADY_PLANNED: outcome.PASS,
    DRIFT_BLOCKED: outcome.GATE_REJECTION,
    TRACE_INCOMPLETE: outcome.GATE_REJECTION,
    USAGE_ERROR: outcome.INFRA_ERROR,
    ACK_CONFLICT: outcome.INFRA_ERROR,
    ACK_UNKNOWN_TASK: outcome.INFRA_ERROR,
}

# The line number is optional so a line-less finding (`<file> - <action>`) round-
# trips through render → import faithfully; `<file>:<line> - <action>` still matches.
_FINDING_RE = re.compile(r"^(?P<file>[^:\s]+)(?::(?P<line>\d+))?\s*-\s*(?P<text>.+)$")

# SpecOps/Speckit-managed artifact paths are methodology state, not product drift.
# They are excluded from effective-diff classification so the drift gate never
# false-blocks on its own bookkeeping (e.g. status.yaml changes on every task
# close) — required for SC-003. Only the ACTIVE feature's own directory under
# specs/ is excluded (not all of specs/), so a repo that stores product under a
# top-level specs/ (e.g. OpenAPI specs) is still classified.
_MANAGED_PREFIXES = (".specify/",)
_MANAGED_FILES = ("specops.json",)


def _norm(path: str) -> str:
    """Normalize a repo-relative path to match Git's reporting (``./a`` → ``a``).

    User-supplied paths (``--path``, ``acknowledge <path>``, plan declarations)
    are normalized so they compare equal to the paths Git reports; without this an
    acknowledgement of ``./src/foo.py`` would be recorded but never match
    ``src/foo.py`` in classification.
    """
    return posixpath.normpath(path.strip())


def _is_managed(path: str, feature_name: str | None = None) -> bool:
    if path in _MANAGED_FILES or path.startswith(_MANAGED_PREFIXES):
        return True
    return feature_name is not None and path.startswith(f"specs/{feature_name}/")


@dataclass
class TraceResult:
    """A render-agnostic command outcome consumed by the CLI layer (mirrors
    :class:`contextmap.CommandResult`)."""

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
# Effective diff + baseline (R1)
# ---------------------------------------------------------------------------


def _feature_dir(root: Path) -> Path | None:
    return speckit.resolve_feature_dir(root)


def resolve_baseline(root: Path, repo: gitops.git.Repo) -> str | None:
    """Return the effective-diff baseline commit, or None when unresolvable (R1).

    The ledger-recorded baseline (Feature 006) is authoritative; when absent, fall
    back to the merge-base of HEAD with the default branch (``main`` then
    ``master``). None means "cannot derive" → the caller reports a usage error.
    """
    try:
        baseline = status.read_baseline(root)
    except SpecopsError:
        baseline = ""
    if baseline and gitops.commit_exists(repo, baseline):
        return baseline
    # No ledger baseline: fall back to the merge-base with the default branch.
    # Try the remote's advertised default (origin/HEAD → e.g. develop/trunk)
    # first, then the common local names, so a non-main/master default resolves.
    candidates: list[str] = []
    try:
        ref = repo.git.symbolic_ref("--short", "refs/remotes/origin/HEAD")
        if ref:
            candidates.append(ref.strip())
    except Exception:
        pass
    candidates += ["main", "master"]
    for default in candidates:
        try:
            base = repo.merge_base(default, repo.head.commit)
        except Exception:
            continue
        if base:
            return base[0].hexsha
    return None


def _name_status(repo: gitops.git.Repo, baseline: str) -> list[tuple[str, str]]:
    """Return [(change, path)] for baseline..HEAD, rename-decomposed (R1).

    Delegates to the single diff invocation in :func:`gitops.effective_diff_status`
    and maps Git's status letters to human words.
    """
    mapping = {"A": "added", "D": "removed"}
    return [
        (mapping.get(code, "modified"), _norm(path))
        for code, path in gitops.effective_diff_status(repo, baseline, "HEAD")
    ]


# ---------------------------------------------------------------------------
# Plan-declared topology (reused from Feature 004/009 parsers)
# ---------------------------------------------------------------------------


def _plan_text(root: Path) -> str:
    fd = _feature_dir(root)
    plan = (fd / "plan.md") if fd is not None else Path("plan.md")
    return plan.read_text(encoding="utf-8") if plan.is_file() else ""


def _planned_paths(plan_text: str) -> set[str]:
    return {_norm(p) for (p, _action) in _iter_plan_paths(plan_text)}


def _iter_plan_paths(plan_text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in plan_text.splitlines():
        parsed = speckit.parse_plan_path_action(line)
        if parsed:
            out.append(parsed)
    return out


def _owning_context(path: str, contexts: list[contextmap.Context]) -> str | None:
    """Return the id of a context that owns *path* (most-specific), else None."""
    cands = contextmap._candidates_for_path(contexts, path)
    return cands[0][0].id if cands else None


# ---------------------------------------------------------------------------
# Classification (US1, FR-003)
# ---------------------------------------------------------------------------


@dataclass
class _Classification:
    paths: list[dict[str, str]]
    counts: dict[str, int]
    # basis is True when there is any signal to classify against (plan path
    # declarations, declared/recorded contexts, a resolvable map, or an
    # acknowledgement). When False, every path would be `unexplained`, which is
    # not a meaningful drift signal — the always-on review gate degrades to
    # SKIPPED so upgrading a repo whose plan predates the declaration convention
    # is not retroactively rejected (roadmap Rule 5).
    basis: bool


@dataclass
class _Ctx:
    """Classification inputs loaded once (map parsed once) and reused across
    classify / validate / ownership to avoid re-deriving state (R9)."""

    data: dict
    acks: set[str]
    planned: set[str]
    accounted: set[str]
    contexts: list[contextmap.Context] | None
    feature_name: str | None


def _load_ctx(root: Path) -> _Ctx:
    fd = _feature_dir(root)
    data = ledger.load_raw(fd) if fd is not None and (fd / "status.yaml").is_file() else {}
    plan_text = _plan_text(root)
    # "accounted" contexts = declared in the plan ∪ recorded in any task's
    # provenance. classify (ownership branch) and validate (contradictory
    # ownership) use the SAME set so the two commands never disagree — a path
    # owned by an accounted context is `planned`/no-defect; owned by an
    # unaccounted context is `unexplained`/contradictory-ownership.
    accounted = set(speckit.parse_plan_context_ids(plan_text))
    for t in data.get("tasks") or []:
        if isinstance(t, dict):
            accounted.update((t.get("context_provenance") or {}).get("context_ids") or [])
    vr = contextmap.validate(root)
    contexts = vr.contexts if vr.status in contextmap._RESOLVABLE else None
    return _Ctx(
        data=data, acks=_acknowledged_paths(data), planned=_planned_paths(plan_text),
        accounted=accounted, contexts=contexts, feature_name=fd.name if fd is not None else None,
    )


def _acknowledged_paths(data: dict) -> set[str]:
    return {
        _norm(a["path"])
        for a in data.get("acknowledgements") or []
        if isinstance(a, dict) and isinstance(a.get("path"), str)
    }


def classify(
    root: Path, *, explicit_paths: list[str] | None = None, ctx: _Ctx | None = None
) -> _Classification | TraceResult:
    """Classify every effective-diff path (R2). Returns a usage :class:`TraceResult`
    when the change set cannot be derived from Git (fail closed, never fail open)."""
    ctx = ctx or _load_ctx(root)

    if explicit_paths is not None:
        changes = [("specified", _norm(p)) for p in explicit_paths]
    else:
        repo = gitops.find_repo(root)
        if repo is None:
            return TraceResult(
                "trace classify", USAGE_ERROR,
                "trace classify: not a Git repository and no --path given",
            )
        baseline = resolve_baseline(root, repo)
        if baseline is None:
            return TraceResult(
                "trace classify", USAGE_ERROR,
                "trace classify: no resolvable baseline; pass --path explicitly",
            )
        changes = _name_status(repo, baseline)

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for change, path in sorted(changes, key=lambda t: t[1]):
        if path in seen or _is_managed(path, ctx.feature_name):
            continue
        seen.add(path)
        cls, attribution = _classify_one(path, ctx)
        rows.append({"path": path, "change": change, "class": cls, "attribution": attribution})

    counts = {PLANNED: 0, DISCOVERED: 0, UNEXPLAINED: 0}
    for r in rows:
        counts[r["class"]] += 1
    basis = bool(ctx.planned or ctx.accounted or ctx.acks or ctx.contexts)
    return _Classification(paths=rows, counts=counts, basis=basis)


def _classify_one(path: str, ctx: _Ctx) -> tuple[str, str]:
    """Assign one class by the fixed precedence: discovery > planned > unexplained."""
    if path in ctx.acks:  # discovery precedence (FR-003)
        return DISCOVERED, "acknowledged"
    if path in ctx.planned:
        return PLANNED, "plan-declared"
    if ctx.contexts is not None and ctx.accounted:
        owner = _owning_context(path, ctx.contexts)
        if owner is not None and owner in ctx.accounted:
            return PLANNED, f"owned-by:{owner}"
    return UNEXPLAINED, "none"


def cmd_classify(root: Path, *, explicit_paths: list[str] | None = None) -> TraceResult:
    """`specops trace classify` — describe every effective-diff path (read-only)."""
    result = classify(root, explicit_paths=explicit_paths)
    if isinstance(result, TraceResult):
        return result
    lines = [
        f"{r['class']:<28} {r['path']}  ({r['attribution']})"
        for r in sorted(result.paths, key=lambda r: (r["class"], r["path"]))
    ]
    header = (
        f"trace classify: {result.counts[PLANNED]} planned, "
        f"{result.counts[DISCOVERED]} discovered-and-acknowledged, "
        f"{result.counts[UNEXPLAINED]} unexplained"
    )
    human = header + ("\n" + "\n".join(lines) if lines else "")
    return TraceResult(
        "trace classify", TRACE_OK, human,
        {"paths": result.paths, "counts": result.counts},
    )


# ---------------------------------------------------------------------------
# Trace graph + validation (US3, FR-009)
# ---------------------------------------------------------------------------


def _coverage(spec_text: str, tasks_text: str) -> dict[str, list[str]]:
    """Map each spec SC id → covering task ids (mirrors consistency.run)."""
    scs = set(speckit.extract_sc_ids(spec_text))
    covered: dict[str, list[str]] = {sc: [] for sc in scs}
    for line in tasks_text.splitlines():
        task_ids = speckit.extract_task_ids(line)
        tid = task_ids[0] if task_ids else None
        if tid is None:
            continue
        for tag in speckit.extract_coverage_tags(line):
            if tag in covered:
                covered[tag].append(tid)
    return covered


def _story_of_task(tasks_text: str) -> dict[str, str]:
    """Map task id → its `[USn]` story label (or '' when unlabeled)."""
    out: dict[str, str] = {}
    for line in tasks_text.splitlines():
        ids = speckit.extract_task_ids(line)
        if not ids:
            continue
        m = re.search(r"\[(US\d+)\]", line)
        out[ids[0]] = m.group(1) if m else ""
    return out


def _structured_rounds(data: dict) -> set[int]:
    """Rounds whose cycle owns a structured handoff (Feature 011)."""
    return {
        cycle.get("round") or 0
        for cycle in data.get("review_cycles") or []
        if isinstance(cycle, dict) and isinstance(cycle.get("handoff"), dict)
    }


def _structured_findings(data: dict) -> list[dict[str, Any]]:
    """Findings sourced from the v5 handoff state, carrying stable ids (Feature 011)."""
    out: list[dict[str, Any]] = []
    for cycle in data.get("review_cycles") or []:
        if not isinstance(cycle, dict):
            continue
        handoff = cycle.get("handoff")
        if not isinstance(handoff, dict):
            continue
        rnd = cycle.get("round") or 0
        for f in handoff.get("findings") or []:
            if isinstance(f, dict):
                out.append({
                    "id": f.get("id"), "file": f.get("file"), "line": f.get("line"),
                    "text": f.get("action"), "round": rnd,
                })
    return out


def _legacy_findings(feature_dir: Path, skip_rounds: set[int]) -> list[dict[str, Any]]:
    """Parse `revisions/revision-*.md` for rounds not covered by a structured handoff."""
    rev_dir = feature_dir / "revisions"
    if not rev_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for rev in sorted(rev_dir.glob("revision-*.md")):
        m = re.search(r"revision-(\d+)\.md$", rev.name)
        rnd = int(m.group(1)) if m else 0
        if rnd in skip_rounds:
            continue
        for line in rev.read_text(encoding="utf-8").splitlines():
            fm = _FINDING_RE.match(line.strip())
            if fm:
                out.append({
                    "file": fm.group("file"),
                    "line": int(fm.group("line")) if fm.group("line") else None,
                    "text": fm.group("text").strip(), "round": rnd,
                })
    return out


def _findings(feature_dir: Path, data: dict | None = None) -> list[dict[str, Any]]:
    """Findings for the trace. Uses the v5 structured handoff findings (with stable
    ids) for rounds that have a handoff, and falls back to parsing
    `revisions/revision-*.md` for **rounds that do not** — so a feature that mixes
    early legacy rounds with later structured rounds reports both, and pre-feature
    ledgers still trace (FR-015)."""
    data = data or {}
    findings = _structured_findings(data) + _legacy_findings(
        feature_dir, skip_rounds=_structured_rounds(data)
    )
    return sorted(findings, key=lambda f: (
        f["round"], f.get("file") or "",
        f["line"] if isinstance(f.get("line"), int) else -1, f.get("id") or "",
    ))


def build_graph(root: Path) -> dict[str, Any]:
    """Materialize the trace graph from ledger + provenance + findings (R4)."""
    fd = _feature_dir(root)
    if fd is None:
        raise SpecopsError("Cannot resolve active feature directory.")
    data = ledger.load_raw(fd) if (fd / "status.yaml").is_file() else {}
    spec_text = _read(fd / "spec.md")
    tasks_text = _read(fd / "tasks.md")

    coverage = _coverage(spec_text, tasks_text)
    tasks_by_id: dict[str, dict] = {
        t["id"]: t
        for t in data.get("tasks") or []
        if isinstance(t, dict) and isinstance(t.get("id"), str)
    }

    sc_nodes = []
    for sc in sorted(coverage):
        covering = coverage[sc]
        done = [
            tid for tid in covering
            if tasks_by_id.get(tid, {}).get("status") == "DONE"
        ]
        sc_nodes.append({
            "sc": sc,
            "tasks": sorted(covering),
            "completed": bool(covering) and len(done) == len(covering),
        })

    task_nodes = []
    for tid in sorted(tasks_by_id):
        t = tasks_by_id[tid]
        if t.get("orphaned"):
            continue
        prov = t.get("context_provenance") or {}
        task_nodes.append({
            "id": tid,
            "status": t.get("status"),
            "evidence": t.get("evidence"),
            "commits": t.get("commits") or [],
            "contexts": prov.get("context_ids") or [],
            "digest": prov.get("digest"),
        })

    cycles = [
        {"round": c.get("round"), "result": c.get("result")}
        for c in data.get("review_cycles") or [] if isinstance(c, dict)
    ]

    return {
        "success_criteria": sc_nodes,
        "tasks": task_nodes,
        "review_cycles": cycles,
        "findings": _findings(fd, data),
        "acknowledgements": [
            {"path": a.get("path"), "task": a.get("task"), "reason": a.get("reason")}
            for a in data.get("acknowledgements") or [] if isinstance(a, dict)
        ],
    }


def _defect(kind: str, detail: str, ref: str) -> dict[str, str]:
    return {"kind": kind, "detail": detail, "ref": ref}


def validate_trace(root: Path, *, ctx: _Ctx | None = None) -> list[dict[str, str]]:
    """Return the trace defects (R5); [] when the trace is complete."""
    fd = _feature_dir(root)
    if fd is None:
        raise SpecopsError("Cannot resolve active feature directory.")
    ctx = ctx or _load_ctx(root)
    data = ctx.data
    spec_text = _read(fd / "spec.md")
    tasks_text = _read(fd / "tasks.md")

    coverage = _coverage(spec_text, tasks_text)
    tasks_by_id: dict[str, dict] = {
        t["id"]: t
        for t in data.get("tasks") or []
        if isinstance(t, dict) and isinstance(t.get("id"), str)
    }
    story_of = _story_of_task(tasks_text)
    defects: list[dict[str, str]] = []

    # 1. uncovered-sc
    for sc in sorted(coverage):
        if not coverage[sc]:
            defects.append(_defect("uncovered-sc", f"SC '{sc}' has no covering task", sc))

    # 2. missing-link: DONE task without evidence; user story with no commit
    for tid in sorted(tasks_by_id):
        t = tasks_by_id[tid]
        if t.get("orphaned"):
            continue
        if t.get("status") == "DONE" and not t.get("evidence"):
            defects.append(_defect("missing-link", f"task '{tid}' is DONE without evidence", tid))
    for story, tids in sorted(_group_by_story(tasks_by_id, story_of).items()):
        if not story or not tids:
            continue
        if all(tasks_by_id[t].get("status") == "DONE" for t in tids) and not any(
            tasks_by_id[t].get("commits") for t in tids
        ):
            defects.append(_defect("missing-link", f"user story '{story}' has no commit", story))

    # 3. dangling-reference: coverage/ack/commit references that do not resolve
    for sc, tids in sorted(coverage.items()):
        for tid in tids:
            if tid not in tasks_by_id:
                defects.append(
                    _defect("dangling-reference",
                            f"SC '{sc}' covering task '{tid}' not in ledger", tid)
                )
    known_tasks = {tid for tid, t in tasks_by_id.items() if not t.get("orphaned")}
    for a in data.get("acknowledgements") or []:
        if isinstance(a, dict) and a.get("task") not in known_tasks:
            defects.append(
                _defect("dangling-reference",
                        f"acknowledgement task '{a.get('task')}' not in ledger", str(a.get("task")))
            )
    repo = gitops.find_repo(root)
    if repo is not None:
        for tid in sorted(tasks_by_id):
            for sha in tasks_by_id[tid].get("commits") or []:
                if not gitops.commit_exists(repo, sha):
                    defects.append(_defect(
                        "dangling-reference",
                        f"task '{tid}' commit '{sha[:7]}' not in Git tree "
                        "(see 'specops reconcile')", sha))

    # 4. contradictory-ownership: effective-diff path owned by an unaccounted context
    defects.extend(_ownership_defects(root, ctx))
    return defects


def _group_by_story(tasks_by_id: dict, story_of: dict[str, str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for tid, t in tasks_by_id.items():
        if t.get("orphaned"):
            continue
        groups.setdefault(story_of.get(tid, ""), []).append(tid)
    return groups


def _ownership_defects(root: Path, ctx: _Ctx) -> list[dict[str, str]]:
    # Uses the same `accounted` set as classify, so a path classify calls
    # `unexplained` for an unaccounted owner is reported here, and one it calls
    # `planned` is not — the two commands agree.
    if ctx.contexts is None:
        return []
    repo = gitops.find_repo(root)
    if repo is None:
        return []
    baseline = resolve_baseline(root, repo)
    if baseline is None:
        return []
    out: list[dict[str, str]] = []
    for _change, path in sorted(_name_status(repo, baseline), key=lambda t: t[1]):
        if _is_managed(path, ctx.feature_name) or path in ctx.planned or path in ctx.acks:
            continue
        owner = _owning_context(path, ctx.contexts)
        if owner is not None and owner not in ctx.accounted:
            out.append({
                "kind": "contradictory-ownership",
                "detail": f"path '{path}' owned by undeclared/unassociated context '{owner}'",
                "ref": path,
            })
    return out


def cmd_validate(root: Path) -> TraceResult:
    """`specops trace validate` — fail closed on any defect or unexplained path.

    Loads classification inputs once (map parsed once). If the effective diff
    cannot be derived (not a repo / no baseline) the classify usage error is
    returned as-is (exit `2`) — the command fails closed, never reporting a clean
    pass for drift it never actually evaluated (Principle VI)."""
    ctx = _load_ctx(root)
    result = classify(root, ctx=ctx)
    if isinstance(result, TraceResult):
        return result  # usage error — fail closed, not a silent pass
    unexplained = [r["path"] for r in result.paths if r["class"] == UNEXPLAINED]
    defects = validate_trace(root, ctx=ctx)
    if not defects and not unexplained:
        return TraceResult("trace validate", TRACE_OK,
                           "trace validate: complete trace, no unexplained paths",
                           {"defects": [], "unexplained": []})
    lines = [f"trace: {d['kind']} - {d['detail']}" for d in defects]
    lines += [f"trace: unexplained path - {p}" for p in unexplained]
    status_val = DRIFT_BLOCKED if unexplained and not defects else TRACE_INCOMPLETE
    return TraceResult("trace validate", status_val, "\n".join(lines),
                       {"defects": defects, "unexplained": unexplained})


def cmd_report(root: Path) -> TraceResult:
    """`specops trace report` — render the full chain (read-only)."""
    graph = build_graph(root)
    lines: list[str] = []
    for sc in graph["success_criteria"]:
        mark = "complete" if sc["completed"] else "in-progress"
        lines.append(f"{sc['sc']} [{mark}]: tasks {', '.join(sc['tasks']) or '(none)'}")
    disc = graph["acknowledgements"]
    if disc:
        lines.append("Discoveries:")
        for a in sorted(disc, key=lambda a: str(a.get("path"))):
            lines.append(f"  {a['path']}  (task {a['task']}: {a['reason']})")
    human = "\n".join(lines) if lines else "trace report: no success criteria"
    return TraceResult("trace report", TRACE_OK, human, {"graph": graph})


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# ---------------------------------------------------------------------------
# Acknowledgement (US2, FR-005..FR-007)
# ---------------------------------------------------------------------------


def cmd_acknowledge(root: Path, path: str, *, task: str, reason: str) -> TraceResult:
    """Record a one-time path-level acknowledgement (state-changing).

    Precondition failures (not-a-repo, identity mismatch, stale write) raise
    SpecopsError for the CLI error boundary; semantic outcomes return a
    :class:`TraceResult`.
    """
    reason = (reason or "").strip()
    if not path or not task or not reason:
        return TraceResult("trace acknowledge", USAGE_ERROR,
                           "trace acknowledge: path, --task and --reason are all required")
    path = _norm(path)  # store normalized so classification matches Git-reported paths

    repo = gitops.find_repo(root)
    if repo is None:
        return TraceResult("trace acknowledge", USAGE_ERROR,
                           "trace acknowledge: not a Git repository")

    feature_dir = status._get_feature_dir(root)
    data, base_rev, base_violations, _repo = status._load_for_write(root, feature_dir)

    known = {t.get("id") for t in data.get("tasks") or [] if not t.get("orphaned")}
    if task not in known:
        return TraceResult("trace acknowledge", ACK_UNKNOWN_TASK,
                           f"trace acknowledge: unknown task '{task}'",
                           {"path": path, "task": task})

    # already-planned (never-discovered) path → no-op (FR-007). The check ignores
    # existing acknowledgements (acks=∅) so it reflects only plan/ownership.
    check_ctx = replace(_load_ctx(root), acks=set())
    existing = {
        _norm(a["path"]): a for a in data.get("acknowledgements") or []
        if isinstance(a, dict) and isinstance(a.get("path"), str)
    }
    if path not in existing:
        cls, _attr = _classify_one(path, check_ctx)
        if cls == PLANNED:
            return TraceResult("trace acknowledge", ACK_ALREADY_PLANNED,
                               f"trace acknowledge: '{path}' is already planned; "
                               "no acknowledgement recorded",
                               {"path": path, "task": task})

    prior = existing.get(path)
    if prior is not None:
        if prior.get("task") == task and (prior.get("reason") or "").strip() == reason:
            return TraceResult("trace acknowledge", ACK_IDEMPOTENT,
                               f"trace acknowledge: '{path}' already acknowledged (idempotent)",
                               {"path": path, "task": task})
        return TraceResult("trace acknowledge", ACK_CONFLICT,
                           f"trace acknowledge: '{path}' already acknowledged by a "
                           "different task/reason; "
                           "existing record left unchanged", {"path": path, "task": task})

    record = {
        "path": path, "task": task, "reason": reason,
        "map_digest": contextmap.map_digest(root), "at": ledger.now_utc(),
    }
    data.setdefault("acknowledgements", []).append(record)
    status._finalize(feature_dir, data, base_rev, base_violations)
    return TraceResult("trace acknowledge", ACK_RECORDED,
                       f"trace acknowledge: recorded '{path}' (task {task})",
                       {"path": path, "task": task})
