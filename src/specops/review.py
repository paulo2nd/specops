"""specops review: deterministic review gates, cheapest-first (004, FR-001..FR-009).

Gate order is fixed: reconcile → lint → test → working-tree. The first FAIL
stops the run. Evaluation is read-only — the command never writes to the
ledger or any repository file (FR-007). Working-tree cleanliness is
snapshotted at invocation time, so artifacts created by the client's own
lint/test commands cannot fail the run that created them.
"""
from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass, field
from pathlib import Path

import git

from specops import (
    config,
    contextmap,
    evidence,
    gateprofiles,
    gitops,
    ledger,
    shell,
    speckit,
    status,
    trace,
)
from specops import reconcile as reconcile_mod
from specops.errors import SpecopsError

# Canonical default layout (reconcile → the profile suite → working-tree → drift).
# With the default profile the suite is `lint` → `test`, so this order is what a
# no-config repository renders (Feature 012 replaces the fixed lint/test gates with
# the selected profile suite, FR-011).
GATE_ORDER = ["reconcile", "lint", "test", "working-tree", "drift"]
TAIL_LINES = 50
_LINE_WIDTH = 24  # dot-padded label width: "[gate] working-tree ...."


@dataclass
class GateResult:
    """Outcome of one evaluated gate (data-model.md).

    ``status`` (PASS|FAIL|SKIPPED) drives the blocking decision (``GateReport.passed``);
    only a required profile gate's failure/unavailability sets FAIL. ``disposition``
    (Feature 012, FR-008) annotates a profile gate with the outcome taxonomy
    (required|optional|skipped|cached|failed|unavailable); it is None for the fixed
    reconcile/working-tree/drift gates. The remaining fields carry verdict provenance
    (FR-011): the selection ``reason``, the covered ``commit_range``/``affected_paths``,
    and the supporting ``evidence_id``.
    """

    name: str
    status: str  # PASS | FAIL | SKIPPED
    detail: list[str] = field(default_factory=list)
    disposition: str | None = None
    reason: str | None = None
    evidence_id: str | None = None
    commit_range: str | None = None
    affected_paths: list[str] = field(default_factory=list)
    required: bool = True


@dataclass
class GateReport:
    """Ordered gate outcomes for one run (data-model.md)."""

    results: list[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.status != "FAIL" for r in self.results)

    def render(self) -> str:
        lines: list[str] = []
        for r in self.results:
            label = f"[gate] {r.name} ".ljust(_LINE_WIDTH, ".")
            if r.status == "SKIPPED":
                reason = r.detail[0] if r.detail else ""
                lines.append(f"{label} SKIPPED ({reason})")
                continue
            lines.append(f"{label} {r.status}")
            lines.extend(f"  {d}" for d in r.detail)
        return "\n".join(lines)


def _tail(output: str, limit: int = TAIL_LINES) -> list[str]:
    """Last *limit* lines of *output*, prefixed with a note when truncated."""
    lines = output.splitlines()
    if len(lines) <= limit:
        return lines
    note = f"[output: {len(lines)} lines, showing last {limit}]"
    return [note, *lines[-limit:]]


def _reconcile_gate(root: Path) -> GateResult:
    """Violations FAIL the gate; warnings are always echoed (clarification)."""
    warnings, violations = reconcile_mod.run(root)
    if violations:
        return GateResult("reconcile", "FAIL", [*warnings, *violations])
    return GateResult("reconcile", "PASS", warnings)


def _cli_version() -> str:
    try:
        return importlib.metadata.version("speckit-specops")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover - dev install
        return "0.0.0"


def _existing_evidence(root: Path) -> list[dict]:
    """Read the active ledger's structured evidence list (read-only; [] when absent).

    Used only for the cache-lookup: `specops review` never writes the ledger (the
    Feature 004 read-only contract holds), so a `cached` disposition is reported when a
    matching, non-superseded record already exists (recorded by a state-changing path).
    NOTE: no production path currently persists a ``gate:<name>@<ver>`` record, so a
    gate's *own* prior run never cache-hits end-to-end — persisting gate-run evidence
    from review is deferred (see spec FR-009 + research.md R9a).
    """
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        return []
    try:
        data = ledger.load_raw(feature_dir)
    except SpecopsError:
        return []
    ev = data.get("evidence")
    return ev if isinstance(ev, list) else []


def _cached_record(existing: list[dict], eid: str) -> dict | None:
    for rec in existing:
        if isinstance(rec, dict) and rec.get("id") == eid and rec.get("superseded_by") is None:
            return rec
    return None


def _blocking_result(
    p: gateprofiles.GateProfile, reason: str, detail: list[str], disposition: str,
    eid: str, commit_range: str, changed: list[str],
) -> GateResult:
    """A required failure/unavailability FAILs (blocks); an optional one is recorded
    but never flips the verdict (FR-004/FR-008)."""
    if p.required:
        return GateResult(p.name, "FAIL", detail, disposition=disposition, reason=reason,
                          evidence_id=eid, commit_range=commit_range,
                          affected_paths=changed, required=True)
    return GateResult(p.name, "PASS", [*detail, "(optional gate — non-blocking)"],
                      disposition=disposition, reason=reason, evidence_id=eid,
                      commit_range=commit_range, affected_paths=changed, required=False)


def _run_profile_gate(
    sel: gateprofiles.SelectedGate, root: Path, changed: list[str],
    commit_range: str, map_digest: str | None, existing: list[dict],
) -> GateResult:
    """Evaluate one selected/skipped profile gate → GateResult with a disposition.

    Reuses a matching evidence record as `cached` (no re-run, FR-009); runs otherwise
    with the gate's timeout (FR-010) and maps the outcome to the taxonomy: an empty
    command is a benign SKIP (as today), a missing tool (exit 127) is `unavailable`,
    a timeout or non-zero exit is `failed`.
    """
    p = sel.profile
    if not sel.selected:
        return GateResult(p.name, "SKIPPED", [f"out of scope ({sel.reason})"],
                          disposition="skipped", reason=sel.reason, required=p.required)
    if not p.command:
        return GateResult(p.name, "SKIPPED", [f"{p.name}_command empty"],
                          disposition="skipped", reason=sel.reason, required=p.required)
    producer = f"gate:{p.name}@{_cli_version()}"
    key = evidence.cache_key(
        producer=producer, command=p.command, commit_range=commit_range,
        affected_paths=changed, context_map_digest=map_digest,
    )
    eid = evidence.derive_id(key)
    if _cached_record(existing, eid) is not None:
        return GateResult(p.name, "PASS", [f"cached ({sel.reason})"], disposition="cached",
                          reason=sel.reason, evidence_id=eid, commit_range=commit_range,
                          affected_paths=changed, required=p.required)
    result = shell.run_client_command(p.command, root, timeout=p.timeout)
    if result.timed_out:
        detail = [f"command: {p.command}", f"timeout after {p.timeout}s"]
        return _blocking_result(p, sel.reason, detail, "failed", eid, commit_range, changed)
    if result.returncode == 127:
        detail = [f"command: {p.command}", "command not found (tool unavailable)"]
        return _blocking_result(p, sel.reason, detail, "unavailable", eid, commit_range, changed)
    if result.returncode == 0:
        disposition = "required" if p.required else "optional"
        return GateResult(p.name, "PASS", [], disposition=disposition,
                          reason=sel.reason, evidence_id=eid, commit_range=commit_range,
                          affected_paths=changed, required=p.required)
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    detail = [f"command: {p.command}", f"exit code: {result.returncode}", *_tail(combined)]
    return _blocking_result(p, sel.reason, detail, "failed", eid, commit_range, changed)


def _profile_gates(root: Path, repo: git.Repo, baseline: str) -> list[GateResult]:
    """The selected profile suite (replaces the fixed lint/test gates — FR-011).

    Deterministically selects gates from the effective diff + context impact, then runs
    the selected required gates in declared order, stopping at the first blocking
    failure (matching the pipeline's early-stop). Read-only.
    """
    changed = (
        gitops.name_only_diff(repo, baseline, "HEAD")
        if baseline and gitops.commit_exists(repo, baseline) else []
    )
    # Fail closed on an invalid *present* config — never silently fall back to the
    # default suite (which would skip declared required gates and pass, a fail-open).
    gates = gateprofiles.resolve_suite(root)
    affected = gateprofiles._affected_for(root, changed)
    selection = gateprofiles.select_gates(gates, changed, affected)
    head = gitops.head_sha(repo)
    commit_range = f"{baseline}..{head}" if baseline else head
    map_digest = contextmap.map_digest(root)
    existing = _existing_evidence(root)
    results: list[GateResult] = []
    for sel in selection:
        gr = _run_profile_gate(sel, root, changed, commit_range, map_digest, existing)
        results.append(gr)
        if gr.status == "FAIL":
            break  # blocking failure — do not execute later gates (early stop)
    return results


def _working_tree_gate(repo: git.Repo, dirty: list[str], baseline: str) -> GateResult:
    """Tree clean at invocation, with an effective diff against the baseline (R4)."""
    if dirty:
        return GateResult("working-tree", "FAIL", ["uncommitted changes:", *dirty])
    if not baseline:
        return GateResult(
            "working-tree", "FAIL",
            ["ledger has no baseline commit; cannot determine the effective diff"],
        )
    if not gitops.commit_exists(repo, baseline):
        return GateResult(
            "working-tree", "FAIL",
            [
                f"ledger baseline commit '{baseline[:7]}' cannot be resolved in "
                "this clone (shallow clone or rewritten history); fetch full "
                "history or re-create the ledger baseline",
            ],
        )
    changed = gitops.name_only_diff(repo, baseline, "HEAD")
    if not changed:
        return GateResult(
            "working-tree", "FAIL", ["no effective diff — nothing to review"]
        )
    header = f"{len(changed)} file(s) changed since baseline {baseline[:7]}:"
    return GateResult("working-tree", "PASS", [header, *changed])


def _drift_gate(root: Path) -> GateResult:
    """Block only unexplained effective-diff paths (Feature 010, FR-004).

    Reuses the deterministic classifier: `planned` and
    `discovered-and-acknowledged` paths PASS; any `unexplained` path FAILs the
    gate (review REJECTED). Runs last, so it only evaluates an otherwise-clean,
    diffable tree (the working-tree gate has already passed).

    Fails closed if the effective diff cannot be derived (Principle VI), and
    degrades to SKIPPED when the feature declares no classification basis (no plan
    path declarations, contexts, map, or acknowledgements) — so upgrading a repo
    whose plan predates the declaration convention is not retroactively rejected.
    """
    result = trace.classify(root)
    if isinstance(result, trace.TraceResult):  # usage error → fail closed, never open
        return GateResult("drift", "FAIL", [f"cannot determine effective diff: {result.human}"])
    if not result.basis:
        return GateResult(
            "drift", "SKIPPED",
            ["no plan path declarations, context map, or acknowledgements to classify against"],
        )
    unexplained = [r["path"] for r in result.paths if r["class"] == trace.UNEXPLAINED]
    if unexplained:
        return GateResult(
            "drift", "FAIL",
            [f"{len(unexplained)} unexplained path(s) — acknowledge or plan them:", *unexplained],
        )
    return GateResult("drift", "PASS")


def evaluate(root: Path) -> GateReport:
    """Evaluate all gates cheapest-first with early stop; return the report.

    Never raises on a failing gate (unlike :func:`run_gates`) — the caller
    inspects ``report.passed`` and the per-gate results. Used by the ``--json``
    outcome contract (Feature 007) and by :func:`run_gates`.
    """
    config.load(root)  # fail closed (exit 1 + init guidance) when specops.json is absent
    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")
    # Snapshot before any gate runs: the working-tree gate evaluates the
    # tree as it was at invocation (artifacts created by the gate suite cannot
    # dirty it), and the baseline is read from the ledger exactly once.
    dirty_at_start = gitops.dirty_files(repo)
    baseline_at_start = status.read_baseline(root)

    report = GateReport()
    # 1. reconcile — the fail-closed precondition (Principle II / VI).
    report.results.append(_reconcile_gate(root))
    if not report.passed:
        return report
    # 2. the selected profile suite replaces the fixed lint/test gates (FR-011).
    for gr in _profile_gates(root, repo, baseline_at_start):
        report.results.append(gr)
        if gr.status == "FAIL":
            return report  # early stop on the first blocking gate failure
    # 3. working-tree, then 4. drift (cheapest-first, early-stop preserved).
    report.results.append(_working_tree_gate(repo, dirty_at_start, baseline_at_start))
    if not report.passed:
        return report
    report.results.append(_drift_gate(root))
    return report


def digest_drift_warning(root: Path) -> str | None:
    """Return a non-blocking warning when the map changed since planning (SC-008).

    Compares the most recent context-map digest recorded in the ledger's
    provenance (the plan/implement-time digest) with the current map digest. A
    difference is surfaced as a warning only — it never blocks review. Feature 010
    enforces unexplained *path* drift via the `drift` gate, but map-*digest* drift
    stays advisory (spec SC-008). Returns None when there is no map, no recorded
    digest, or the digests match.
    """
    current = contextmap.map_digest(root)
    if current is None:
        return None
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        return None
    try:
        data = ledger.load_raw(feature_dir)
    except SpecopsError:
        return None
    # Fire when ANY recorded present-provenance digest differs from the current
    # one. Tasks (recorded during planning/implementation) are scanned first, so
    # a review-cycle record written at review time — which carries the current,
    # already-drifted digest — cannot mask a genuinely stale planning digest.
    recorded: str | None = None
    for record in [*(data.get("tasks") or []), *(data.get("review_cycles") or [])]:
        prov = record.get("context_provenance") if isinstance(record, dict) else None
        if (
            isinstance(prov, dict)
            and prov.get("map") == "present"
            and prov.get("digest")
            and prov["digest"] != current
        ):
            recorded = prov["digest"]
            break
    if recorded is None:
        return None
    return (
        "context-map drift: the map digest changed since it was recorded "
        f"(planned {recorded[:12]}… → current {current[:12]}…). Non-blocking; "
        "re-run planning if the change affects this work."
    )


def run_gates(root: Path) -> str:
    """Evaluate all gates; return the rendered report on success, or raise
    SpecopsError carrying the report (exit 1) on the first FAIL.

    A non-blocking context-map drift warning (SC-008) is **appended** after the
    gate report when detected, so the report header stays at the start of the
    output/error (stable contract); it never changes the pass/fail outcome.
    """
    report = evaluate(root)
    rendered = report.render()
    warning = digest_drift_warning(root)
    suffix = f"\n[warning] {warning}" if warning else ""
    if not report.passed:
        raise SpecopsError(rendered + suffix)
    return rendered + suffix
