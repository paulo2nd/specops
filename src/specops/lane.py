"""specops lane: the lightweight workflow lane (Feature 013).

A proportional lane for small reversible changes. State lives in a dedicated
``lane.yaml`` record (its own schema, never the full ``status.yaml`` ledger — the
Session 2026-07-24 clarification); the branch's Git commit history is the working
record. Safety enforcement is hybrid: four categories are detected from the diff
(:mod:`specops.safety`), two are attested by a human. Closure runs the deterministic
gate-profile suite; promotion synthesizes a full ledger at PLAN with zero commit loss.

Every command here is agent/workflow-facing and non-interactive (Principle VI): it
returns a :class:`LaneResult` mapping to the stable outcome contract. Human decisions
arrive as arguments supplied by the ``specops-lite`` workflow's native gate/prompt steps
(the human never drives this CLI — FR-022).
"""
from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import yaml

from specops import config, gitops, ledger, outcome, safety, speckit
from specops.errors import LedgerParseError, SpecopsError

LANE_FILENAME = "lane.yaml"
LANE_SCHEMA = 1
STATES = ("OPEN", "CLOSED", "PROMOTED")

# Versioned JSON contract (Feature 018): lane joins the standard output envelope
# emitted by every other command family. Its ``--json`` now carries ``output_version``
# and a top-level ``status`` — the feature's one sanctioned, additive behavior delta.
OUTPUT_VERSION = 1

CRITERIA_VERSION = 1
# The stable, deterministic eligibility checklist (FR-004). SpecOps presents it and
# records the human's confirmation; it does not itself judge "small" (Design Philosophy).
ELIGIBILITY_CRITERIA = ("small", "reversible", "no-high-risk-category")

# Attestation answers.
ATTEST_CLEAR = "clear"
ATTEST_FLAG = "flag"


# ---------------------------------------------------------------------------
# Result type (agent/workflow-facing; rendered by the CLI via outcome.render)
# ---------------------------------------------------------------------------

class LaneResult(outcome.CommandResult):
    """A lane command outcome — the shared :class:`outcome.CommandResult`.

    Lane has no status vocabulary finer than the outcome status, so its ``status``
    token *is* the outcome status (``ok``/``blocked``/``error``); the ``command`` value
    (``lane-start`` …) is stamped by the CLI at emit time. Errors surface as raised
    exceptions, so a LaneResult is only ever ``ok`` or ``blocked``."""

    _CLASS_MAP = {
        outcome.OK: outcome.PASS,
        outcome.BLOCKED: outcome.GATE_REJECTION,
        outcome.ERROR: outcome.INFRA_ERROR,
    }


def _ok(human: str, **extra: Any) -> LaneResult:
    return LaneResult(
        command="", status=outcome.OK, human=human,
        extra={k: v for k, v in extra.items() if v is not None},
    )


def _blocked(human: str, **extra: Any) -> LaneResult:
    return LaneResult(
        command="", status=outcome.BLOCKED, human=human,
        extra={k: v for k, v in extra.items() if v is not None},
    )


# ---------------------------------------------------------------------------
# Record I/O
# ---------------------------------------------------------------------------

def _lane_path(feature_dir: Path) -> Path:
    return feature_dir / LANE_FILENAME


def exists(feature_dir: Path) -> bool:
    return _lane_path(feature_dir).is_file()


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def load(feature_dir: Path) -> dict:
    """Read and validate the lane record. Raises on absence/parse/schema errors."""
    path = _lane_path(feature_dir)
    if not path.is_file():
        raise SpecopsError(f"No lane record: {path}. Start a lane with 'specops lane start'.")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LedgerParseError(f"Cannot parse lane record {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LedgerParseError(f"Lane record {path} has invalid structure.")
    validate(data)
    return data


def save(feature_dir: Path, data: dict) -> None:
    """Atomically write the lane record, refreshing ``updated_at`` (INV-5)."""
    data["updated_at"] = ledger.now_utc()
    ledger.atomic_write(_lane_path(feature_dir), yaml.dump(data, default_flow_style=False,
                                                           allow_unicode=True))


def validate(data: dict) -> None:
    """Enforce the record invariants INV-1…INV-4 (structure only; git checks elsewhere)."""
    sv = data.get("schema_version")
    if sv != LANE_SCHEMA:
        raise LedgerParseError(
            f"Unsupported lane schema_version {sv!r} (expected {LANE_SCHEMA})."
        )
    state = data.get("state")
    if state not in STATES:
        raise LedgerParseError(f"Invalid lane state {state!r}.")
    closure, promotion = data.get("closure"), data.get("promotion")
    if state == "OPEN" and (closure is not None or promotion is not None):
        raise LedgerParseError("OPEN lane must have null closure and promotion (INV-2).")
    if state == "CLOSED" and closure is None:
        raise LedgerParseError("CLOSED lane must have a closure block (INV-2).")
    if state == "PROMOTED" and promotion is None:
        raise LedgerParseError("PROMOTED lane must have a promotion block (INV-2).")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _resolve(root: Path) -> tuple[Path, Any]:
    """Return (feature_dir, repo) or raise a SpecopsError (exit 1)."""
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        raise SpecopsError("No active feature. Run '/speckit-specify' first.")
    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository. Run 'git init' or 'specops init' first.")
    return feature_dir, repo


def _overrides(root: Path) -> dict[str, list[str]]:
    """Read optional per-category safety-pattern overrides from specops.json."""
    try:
        cfg = config.load(root)
    except SpecopsError:
        return {}
    return config.lane_safety_overrides(cfg)


def _parse_name_status(raw: str) -> list[tuple[str, str]]:
    """Parse `git diff --name-status -M` lines into (status, path) pairs.

    Rename-aware (``-M``): a rename is a single ``R`` on the NEW path, not a
    delete+add, so an ordinary file move is not mis-flagged destructive (safety.detect).
    """
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if line.strip():
            parts = line.split("\t")
            out.append((parts[0][:1], parts[-1]))
    return out


def _unmanaged_dirty(repo: Any, feature_name: str) -> list[str]:
    """Return uncommitted PRODUCT paths, excluding SpecOps/Speckit methodology artifacts.

    Reuses :func:`specops.trace.is_managed` (the single definition of methodology state:
    ``.specify/**``, ``specops.json``, and the active feature's ``specs/<name>/`` dir) so the
    lane's own ``lane.yaml``/``retrospective.md`` never count as a dirty tree at close.
    """
    from specops import trace
    # `-uall` expands untracked directories to individual files, so a wholly-untracked
    # `specs/<feature>/` is not collapsed to `specs/` (which would miss the managed-path
    # prefix and be mis-counted as a dirty product path).
    raw = repo.git.status("--porcelain", "-uall")
    out: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:  # rename: report the destination path
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if path and not trace.is_managed(path, feature_name):
            out.append(path)
    return out


def _require_resolvable_baseline(repo: Any, data: dict) -> None:
    """Fail closed (exit 2) when the lane baseline no longer resolves in this clone.

    A shallow clone or a history rewrite can orphan the stored baseline; scanning an
    empty diff would then fail *open* ("nothing detected"). The full review pipeline's
    working-tree gate fails closed here, and the lane must match (findings: fail-open diff).
    """
    baseline = str(data.get("baseline") or "")
    if baseline and not gitops.commit_exists(repo, baseline):
        raise LedgerParseError(
            f"Lane baseline {baseline[:7]} cannot be resolved in this clone "
            "(history rewritten or shallow). Reconcile the branch before continuing."
        )


def _diff_status(repo: Any, baseline: str, staged: bool) -> list[tuple[str, str]]:
    """Return rename-aware (status, path) pairs for baseline..HEAD, plus staged when asked."""
    pairs: list[tuple[str, str]] = []
    if baseline and gitops.commit_exists(repo, baseline):
        with contextlib.suppress(gitops.git.GitCommandError):  # degrade: no committed diff
            pairs.extend(_parse_name_status(repo.git.diff("--name-status", "-M", baseline, "HEAD")))
    if staged:
        with contextlib.suppress(gitops.git.GitCommandError):  # degrade: no staged diff
            pairs.extend(_parse_name_status(repo.git.diff("--cached", "--name-status", "-M")))
    return pairs


def _latest_attestations(data: dict) -> dict[str, str]:
    """Return the most recent attestation answer per attested category."""
    latest: dict[str, str] = {}
    for d in data.get("decisions", []):
        if isinstance(d, dict) and d.get("kind") == "attestation":
            cat = d.get("category")
            if cat in safety.ATTESTED_CATEGORIES:
                latest[str(cat)] = str(d.get("answer"))
    return latest


def _next_seq(data: dict) -> int:
    decisions = data.get("decisions") or []
    return len(decisions) + 1


# ---------------------------------------------------------------------------
# Lifecycle commands
# ---------------------------------------------------------------------------

def cmd_start(root: Path, *, answers: list[str], bundle: str | None) -> LaneResult:
    """Open a lane after confirming eligibility (FR-003/FR-004). Fail-closed."""
    feature_dir, repo = _resolve(root)
    if exists(feature_dir):
        raise SpecopsError(f"A lane is already open: {_lane_path(feature_dir)}.")
    if ledger.ledger_path(feature_dir).is_file():
        raise SpecopsError(
            "A full ledger (status.yaml) already exists — use the full workflow, not the lane."
        )
    confirmed = {a.strip() for a in answers if a.strip()}
    missing = [c for c in ELIGIBILITY_CRITERIA if c not in confirmed]
    if missing:
        return _blocked(
            "Ineligible for the lightweight lane: unconfirmed criteria "
            + ", ".join(missing) + ". Use the full workflow.",
            ineligible=missing,
        )
    baseline = gitops.head_sha(repo)
    branch = gitops.current_branch(repo)
    template = (_templates_dir() / LANE_FILENAME).read_text(encoding="utf-8")
    ts = ledger.now_utc()
    content = (
        template
        .replace("{{lane-id}}", feature_dir.name)
        .replace("{{feature-name}}", feature_dir.name)
        .replace("{{branch}}", branch)
        .replace("{{commit-hash}}", baseline)
        .replace("{{timestamp}}", ts)
    )
    data = yaml.safe_load(content)
    data["eligibility"]["answers"] = [
        {"key": c, "confirmed": True} for c in ELIGIBILITY_CRITERIA
    ]
    if bundle:
        data["eligibility"]["bundled"] = True
        data["eligibility"]["bundle_note"] = bundle
    validate(data)
    save(feature_dir, data)
    return _ok(
        f"Lane opened ({feature_dir.name}); baseline {baseline[:7]}.",
        lane_id=feature_dir.name, baseline=baseline, bundled=bool(bundle),
    )


def cmd_status(root: Path) -> LaneResult:
    """Read-only lane summary (never mutates the record)."""
    feature_dir, _repo = _resolve(root)
    data = load(feature_dir)
    state = data["state"]
    decisions = data.get("decisions") or []
    human = (
        f"Lane {data['lane_id']}: state={state}, baseline={str(data['baseline'])[:7]}, "
        f"decisions={len(decisions)}."
    )
    return _ok(
        human, state=state, baseline=data["baseline"], decisions=len(decisions),
        closure=data.get("closure"), promotion=data.get("promotion"),
    )


def cmd_check(root: Path, *, staged: bool) -> LaneResult:
    """Read-only hybrid safety detection over the diff (the four detectable categories)."""
    feature_dir, repo = _resolve(root)
    data = load(feature_dir)
    if data["state"] != "OPEN":
        raise SpecopsError(f"Lane is {data['state']}, not OPEN.")
    _require_resolvable_baseline(repo, data)
    detections = safety.detect(_diff_status(repo, data["baseline"], staged), _overrides(root))
    if not detections:
        return _ok("Safety check: no high-risk category detected.", detections=[])
    payload = [{"category": d.category, "path": d.path, "status": d.status} for d in detections]
    cats = safety.categories(detections)
    return _blocked(
        "Safety check flagged: " + ", ".join(cats) + ". Halt or promote (no bypass).",
        detections=payload, categories=cats,
    )


def cmd_attest(root: Path, *, root_cause: str, public_contract: str) -> LaneResult:
    """Record the two always-on attestations (root-cause, public-contract) (FR-007)."""
    feature_dir, _repo = _resolve(root)
    data = load(feature_dir)
    if data["state"] != "OPEN":
        raise SpecopsError(f"Lane is {data['state']}, not OPEN.")
    for value in (root_cause, public_contract):
        if value not in (ATTEST_CLEAR, ATTEST_FLAG):
            raise SpecopsError(f"Attestation answer must be 'clear' or 'flag', got {value!r}.")
    ts = ledger.now_utc()
    pairs = ((safety.ROOT_CAUSE, root_cause), (safety.PUBLIC_CONTRACT, public_contract))
    for category, answer in pairs:
        # Attestations record the CURRENT state of the change per category; the latest
        # answer governs closure (a flag blocks unless a later clear supersedes it —
        # after the human addresses it and re-attests). No standalone "resolution" field:
        # it never got updated and read as a permanent-pending audit artifact (finding 6).
        data.setdefault("decisions", []).append({
            "seq": _next_seq(data), "kind": "attestation", "category": category,
            "signal": "always-on", "answer": answer, "at": ts,
        })
    save(feature_dir, data)
    flagged = [c for c, v in (("root-cause", root_cause), ("public-contract", public_contract))
               if v == ATTEST_FLAG]
    if flagged:
        return _blocked(
            "Attestation flagged: " + ", ".join(flagged) + ". Halt or promote (no bypass).",
            flagged=flagged,
        )
    return _ok("Attestations recorded: both clear.")


def cmd_close(root: Path) -> LaneResult:
    """Fail-closed closure: gate-profile suite + retrospective + evidence (FR-011/FR-013)."""
    from specops import review as review_mod

    feature_dir, repo = _resolve(root)
    data = load(feature_dir)
    if data["state"] != "OPEN":
        raise SpecopsError(f"Lane is {data['state']}, not OPEN.")
    _require_resolvable_baseline(repo, data)

    # 1. the PRODUCT working tree must be clean — mirror the full pipeline's working-tree
    #    gate so staged/uncommitted high-risk changes cannot escape the safety scan and gates
    #    by sitting outside baseline..HEAD (findings: dirty-tree / staged-file fail-open).
    #    SpecOps/Speckit methodology artifacts (the lane's own lane.yaml/retrospective under
    #    specs/<feature>/, specops.json, .specify/**) are excluded, exactly as the drift gate.
    dirty = _unmanaged_dirty(repo, feature_dir.name)
    if dirty:
        return _blocked(
            f"Cannot close: working tree not clean ({len(dirty)} uncommitted change(s): "
            + ", ".join(dirty[:5]) + "). Commit or discard them so the lane's safety check "
            "and gates cover every change.",
            uncommitted=len(dirty),
        )
    # 2. attestations must both be recorded clear (D-2).
    att = _latest_attestations(data)
    not_clear = [c for c in safety.ATTESTED_CATEGORIES if att.get(c) != ATTEST_CLEAR]
    if not_clear:
        return _blocked(
            "Cannot close: attestations not clear for " + ", ".join(not_clear)
            + " (run 'specops lane attest').",
            unresolved_attestations=not_clear,
        )
    # 3. no diff-detectable category may remain (re-check, read-only).
    detections = safety.detect(_diff_status(repo, data["baseline"], False), _overrides(root))
    if detections:
        cats = safety.categories(detections)
        return _blocked(
            "Cannot close: unresolved safety detection (" + ", ".join(cats)
            + "). Halt or promote.", categories=cats,
        )
    # 4. run the deterministic gate-profile suite (fail-closed on a required gate).
    report = review_mod.GateReport()
    report.results.extend(review_mod.profile_gates(root, repo, data["baseline"]))
    gates = [_gate_evidence(r) for r in report.results]
    if not report.passed:
        return _blocked(
            "Cannot close: a required gate profile failed or is unavailable.",
            verdict="REJECTED", gates=gates,
        )
    # 4. write closure block + rendered retrospective.
    head = gitops.head_sha(repo)
    commits = gitops.commits_in_range(repo, data["baseline"], head)
    data["state"] = "CLOSED"
    data["closure"] = {
        "at": ledger.now_utc(),
        "commit_range": f"{data['baseline']}..{head}",
        "gate_evidence": {"verdict": "APPROVED", "gates": gates},
        "retrospective": {
            "summary": f"Lightweight change on {data['branch']} ({len(commits)} commit(s)).",
            "eligibility_basis": [a["key"] for a in data["eligibility"].get("answers", [])],
            "decisions": len(data.get("decisions") or []),
            "commits": [c[:7] for c in commits],
        },
    }
    save(feature_dir, data)
    retro_path = _render_retrospective(feature_dir, data)
    return _ok(
        f"Lane closed (APPROVED); retrospective at {retro_path}.",
        verdict="APPROVED", gates=gates, retrospective_path=str(retro_path),
    )


PROMOTE_REASONS = ("safety-trip", "scope-growth")


def cmd_promote(root: Path, *, reason: str) -> LaneResult:
    """Lossless promotion: synthesize a full ledger at PLAN, zero commit loss (FR-014/15)."""
    from specops import status as status_mod

    if reason not in PROMOTE_REASONS:
        raise SpecopsError(
            f"--reason must be one of {', '.join(PROMOTE_REASONS)}, got {reason!r}."
        )
    feature_dir, repo = _resolve(root)
    data = load(feature_dir)
    if data["state"] == "PROMOTED":
        return _blocked("Lane is already promoted.")
    if data["state"] != "OPEN":
        raise SpecopsError(f"Lane is {data['state']}, not OPEN.")
    if ledger.ledger_path(feature_dir).is_file():
        return _blocked("A full ledger (status.yaml) already exists; nothing to promote.")

    # P-1 (zero commit loss): the baseline must still resolve AND be an ancestor of HEAD.
    # `commits_in_range` only yields commits already reachable, so per-commit is_ancestor
    # can never fail — the real guard is on the *baseline* (a rewrite orphans it, which
    # would otherwise promote silently with 0 imported commits).
    baseline = str(data.get("baseline") or "")
    head = gitops.head_sha(repo)
    if baseline and (not gitops.commit_exists(repo, baseline)
                     or not gitops.is_ancestor(repo, baseline)):
        raise LedgerParseError(
            f"Lane baseline {baseline[:7]} is not an ancestor of HEAD (history diverged); "
            "reconcile the branch (e.g. 'specops status rebaseline') before promoting — "
            "promoting now would lose the lane's commit history."
        )
    imported = gitops.commits_in_range(repo, baseline, head)
    status_mod.synthesize_ledger_at_plan(feature_dir, repo, data)
    root_resolved = root.resolve()
    feature_resolved = feature_dir.resolve()
    data["state"] = "PROMOTED"
    data["promotion"] = {
        "at": ledger.now_utc(),
        "reason": reason,
        "synthesized_ledger": str(
            ledger.ledger_path(feature_resolved).relative_to(root_resolved)
            if feature_resolved.is_relative_to(root_resolved)
            else ledger.ledger_path(feature_dir)),
        "imported_commits": imported,
        "resumed_phase": "PLAN",
    }
    save(feature_dir, data)
    return _ok(
        f"Lane promoted at PLAN ({len(imported)} commit(s) preserved).",
        synthesized_ledger=str(ledger.ledger_path(feature_dir)),
        imported_commits=len(imported), resumed_phase="PLAN",
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _gate_evidence(r: Any) -> dict[str, Any]:
    """One gate's structured evidence record (Feature 012 taxonomy)."""
    obj: dict[str, Any] = {"name": r.name, "status": r.status}
    for fld in ("disposition", "reason", "evidence_id", "commit_range"):
        value = getattr(r, fld, None)
        if value is not None:
            obj[fld] = value
    if getattr(r, "affected_paths", None):
        obj["affected_paths"] = r.affected_paths
    return obj


def _render_retrospective(feature_dir: Path, data: dict) -> Path:
    """Render retrospective.md as a projection of the authoritative closure block (C-3)."""
    retro = data["closure"]["retrospective"]
    commit_lines = [f"- {c}" for c in retro["commits"]] or ["- (none)"]
    basis_lines = [f"- {k}" for k in retro["eligibility_basis"]] or ["- (none)"]
    lines = [
        f"# Retrospective: {data['lane_id']}",
        "",
        f"**Branch**: {data['branch']}  ",
        f"**Commit range**: {data['closure']['commit_range']}  ",
        f"**Verdict**: {data['closure']['gate_evidence']['verdict']}",
        "",
        "## Summary",
        "",
        retro["summary"],
        "",
        "## Eligibility basis",
        "",
        *basis_lines,
        "",
        "## Commits",
        "",
        *commit_lines,
        "",
        f"_Stop-and-ask decisions recorded: {retro['decisions']}._",
        "",
    ]
    path = feature_dir / "retrospective.md"
    ledger.atomic_write(path, "\n".join(lines))
    return path
