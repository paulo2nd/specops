"""specops doctor + specops report — read-only diagnostics and machine reports (Feature 014).

A single read-only surface that composes SpecOps's existing pure-read APIs
(ledger, reconcile, context map, gate profiles, handoff, migration, compat, speckit,
gitops) into one severity-classified health view, plus a compact status report.

Everything here is strictly read-only: it never mutates the repository, ledger,
context map, or configuration (FR-001/SC-003). It never executes ``specify`` or any
gate command — it *defers* to the native commands by pointing at them via a
``next_action_code`` (FR-011), which also keeps the machine output byte-identical
across runs (FR-007). The only environment interaction beyond file reads is git reads
(GitPython) and ``shutil.which`` PATH lookups for gate availability (locate only,
never execute — FR-015a).
"""
from __future__ import annotations

import shlex
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specops import (
    compat,
    config,
    contextmap,
    gateprofiles,
    gitops,
    handoff,
    ledger,
    migration,
    outcome,
    reconcile,
    review,
    speckit,
)
from specops.errors import LedgerParseError, SpecopsError

# The version of the doctor/report machine-readable output contract
# (contracts/doctor-output.schema.json). Additive changes (a new domain, a new
# next_action_code) keep this version; a breaking change bumps it (research D4).
OUTPUT_VERSION = 1

# --- Severities (ordered) — FR-002/FR-005 ----------------------------------
OK = "ok"
WARNING = "warning"
BLOCKING = "blocking"
EXECUTION_ERROR = "execution-error"
_SEVERITY_ORDER = {OK: 0, WARNING: 1, BLOCKING: 2, EXECUTION_ERROR: 3}

# Severity → outcome class → exit code (reuses the Feature 007 contract, FR-008).
_CLASS_MAP = {
    OK: outcome.PASS,
    WARNING: outcome.PASS,
    BLOCKING: outcome.GATE_REJECTION,
    EXECUTION_ERROR: outcome.INFRA_ERROR,
}

# --- Diagnostic domains (fixed order) — FR-003 -----------------------------
D_ENVIRONMENT = "environment"
D_CLI_EXTENSION = "cli_extension"
D_INTEGRATION = "integration"
D_LEGACY = "legacy_artifacts"
D_CONFIG = "configuration"
D_FEATURE_IDENTITY = "feature_identity"
D_LEDGER = "ledger"
D_CONTEXT_MAP = "context_map"
D_WORKFLOW_DIVERGENCE = "workflow_divergence"
D_GATE_AVAILABILITY = "gate_availability"

# --- next_action_code enum (versioned with OUTPUT_VERSION) — FR-004 --------
NA_NONE = "none"
NA_INITIALIZE_REPOSITORY = "initialize_repository"
NA_INSTALL_SPECOPS = "install_specops"
NA_UPGRADE_CLI = "upgrade_cli"
NA_RUN_SPECIFY_CHECK = "run_specify_check"
NA_RUN_SPECIFY_WORKFLOW_STATUS = "run_specify_workflow_status"
NA_MIGRATE_LEGACY = "migrate_legacy_install"
NA_FIX_CONFIG = "fix_config"
NA_START_OR_SELECT_FEATURE = "start_or_select_feature"
NA_RESOLVE_IDENTITY = "resolve_identity_conflict"
NA_RUN_STATUS_MIGRATE = "run_status_migrate"
NA_LEDGER_UNSUPPORTED = "ledger_schema_unsupported"
NA_FIX_CONTEXT_MAP = "fix_context_map"
NA_REFRESH_PROVENANCE = "refresh_context_provenance"
NA_RECONCILE = "reconcile_repository"
NA_INSTALL_GATE_COMMAND = "install_gate_command"
NA_FIX_GATE_PROFILES = "fix_gate_profiles"
NA_VERIFY_BLOCKING = "verify_blocking_findings"
NA_REPAIR_UNREADABLE_INPUT = "repair_unreadable_input"


# ---------------------------------------------------------------------------
# Data model (in-memory only; nothing is persisted)
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single diagnosed fact within a domain (see data-model.md)."""

    severity: str
    message: str
    next_action_code: str = NA_NONE
    next_action: str = ""
    id: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "message": self.message,
            "next_action_code": self.next_action_code,
            "next_action": self.next_action,
            "id": self.id,
        }


@dataclass
class DomainResult:
    """One inspected surface: a domain id and its ordered findings."""

    domain: str
    findings: list[Finding]

    @property
    def severity(self) -> str:
        """Rollup = the most severe finding (OK when the domain has no findings)."""
        worst = OK
        for f in self.findings:
            if _SEVERITY_ORDER[f.severity] > _SEVERITY_ORDER[worst]:
                worst = f.severity
        return worst

    def as_json(self) -> dict[str, Any]:
        ordered = sorted(self.findings, key=lambda f: (f.id, f.message))
        return {
            "domain": self.domain,
            "severity": self.severity,
            "findings": [f.as_json() for f in ordered],
        }


class DoctorResult(outcome.CommandResult):
    """A doctor outcome — the shared CommandResult with the severity→class map.

    ``status`` carries the overall verdict severity; ``cls``/``exit_code`` derive
    from it via ``_CLASS_MAP`` (single-sourced exit derivation, research D9).
    """

    _CLASS_MAP = _CLASS_MAP


# ---------------------------------------------------------------------------
# Finding helpers
# ---------------------------------------------------------------------------


def _ok(fid: str, message: str) -> Finding:
    return Finding(OK, message, NA_NONE, "", fid)


def _finding(severity: str, fid: str, message: str, code: str, action: str) -> Finding:
    return Finding(severity, message, code, action, fid)


def _max_severity(domains: list[DomainResult]) -> str:
    worst = OK
    for d in domains:
        if _SEVERITY_ORDER[d.severity] > _SEVERITY_ORDER[worst]:
            worst = d.severity
    return worst


# ---------------------------------------------------------------------------
# Per-domain checks (each returns a DomainResult; each is read-only)
# ---------------------------------------------------------------------------


def _domain_environment(
    repo: Any, has_speckit: bool, git_version: str | None, git_error: Exception | None,
) -> DomainResult:
    findings: list[Finding] = []
    # Git availability (FR-012), reported first — a missing/nonfunctional `git`
    # is why nothing else works, and repo resolution itself now invokes git. An
    # additive finding (the sole sanctioned doctor surface delta of Feature 020).
    if git_error is not None:
        findings.append(_finding(
            BLOCKING, "git-availability", gitops.GIT_UNAVAILABLE_MSG,
            NA_INITIALIZE_REPOSITORY, "Install Git and ensure `git` is on your PATH.",
        ))
    else:
        findings.append(_ok("git-availability", f"git available ({git_version})"))

    problems: list[Finding] = []
    # The repo check is only meaningful when git is available to answer it.
    if git_error is None and repo is None:
        problems.append(_finding(
            BLOCKING, "git", "not a Git repository", NA_INITIALIZE_REPOSITORY,
            "Run 'git init' (or 'specops init') in the repository root.",
        ))
    if not has_speckit:
        problems.append(_finding(
            BLOCKING, "speckit", "not a Spec Kit repository (no .specify/templates)",
            NA_INSTALL_SPECOPS, "Initialize Spec Kit ('specify init') before using SpecOps.",
        ))
    if not problems:
        problems.append(_ok("env", "Git and Spec Kit repository present."))
    return DomainResult(D_ENVIRONMENT, findings + problems)


def _domain_cli_extension(install_state: str | None) -> DomainResult:
    findings: list[Finding] = []
    result = compat.check()
    if not result.satisfied:
        if result.installed is None:
            findings.append(_finding(
                WARNING, "cli", result.reason(), NA_INSTALL_SPECOPS,
                "Install the SpecOps CLI ('pip install speckit-specops').",
            ))
        else:
            findings.append(_finding(
                WARNING, "cli", result.reason(), NA_UPGRADE_CLI,
                f"Upgrade the SpecOps CLI to >= {result.required}.",
            ))
    if install_state == migration.ABSENT:
        findings.append(_finding(
            WARNING, "extension", "SpecOps extension is not installed", NA_INSTALL_SPECOPS,
            "Install the native extension with 'specops init'.",
        ))
    if not findings:
        findings.append(_ok(
            "compat", f"SpecOps CLI {result.installed} present; extension installed."))
    return DomainResult(D_CLI_EXTENSION, findings)


def _domain_integration(root: Path, has_speckit: bool) -> DomainResult:
    if not has_speckit:
        return DomainResult(D_INTEGRATION, [_ok("integration", "no Spec Kit repository; skipped.")])
    try:
        targets = speckit.resolve_prompt_targets(root)
    except SpecopsError as exc:
        return DomainResult(D_INTEGRATION, [_finding(
            WARNING, "integration", f"integration manifests unresolved: {exc.message}",
            NA_RUN_SPECIFY_CHECK,
            "Run 'specify check' for authoritative engine/integration health.",
        )])
    if not targets:
        return DomainResult(D_INTEGRATION, [_finding(
            WARNING, "integration", "no integrations installed", NA_RUN_SPECIFY_CHECK,
            "Run 'specify check' to confirm engine/integration health.",
        )])
    return DomainResult(D_INTEGRATION, [_ok(
        "integration", f"{len(targets)} integration(s) resolvable (defer to 'specify check')."
    )])


def _domain_legacy(install_state: str | None) -> DomainResult:
    if install_state in (migration.LEGACY, migration.NATIVE_AND_LEGACY):
        return DomainResult(D_LEGACY, [_finding(
            WARNING, "legacy",
            f"legacy marker-injected installation detected ({install_state})",
            NA_MIGRATE_LEGACY, "Migrate to the native extension with 'specops extension migrate'.",
        )])
    return DomainResult(D_LEGACY, [_ok("legacy", "no legacy marker-injected artifacts.")])


def _domain_config(root: Path) -> DomainResult:
    path = config.config_path(root)
    if not path.is_file():
        return DomainResult(D_CONFIG, [_finding(
            WARNING, "config", "specops.json not found", NA_FIX_CONFIG,
            "Create configuration with 'specops init'.",
        )])
    try:
        config.load(root)
    except SpecopsError as exc:
        return DomainResult(D_CONFIG, [_finding(
            BLOCKING, "config", f"specops.json is invalid: {exc.message}", NA_FIX_CONFIG,
            "Fix the JSON syntax of specops.json.",
        )])
    return DomainResult(D_CONFIG, [_ok("config", "specops.json is valid.")])


def _domain_feature_identity(
    root: Path, repo: Any, feature_dir: Path | None, data: dict | None
) -> DomainResult:
    if feature_dir is None:
        return DomainResult(D_FEATURE_IDENTITY, [_finding(
            OK, "feature", "no active SpecOps feature", NA_START_OR_SELECT_FEATURE,
            "Start or select a feature (e.g. 'specops status init-spec').",
        )])
    if data is not None and repo is not None:
        dim = ledger.validate_identity(root, repo, data)
        if dim is not None:
            return DomainResult(D_FEATURE_IDENTITY, [_finding(
                BLOCKING, "identity", f"ledger {dim} diverges from the workspace",
                NA_RESOLVE_IDENTITY, "Re-anchor the ledger with 'specops status rebaseline'.",
            )])
    return DomainResult(D_FEATURE_IDENTITY, [_ok("feature", f"active feature: {feature_dir.name}")])


def _domain_ledger(
    feature_dir: Path | None, data: dict | None, ledger_error: LedgerParseError | None
) -> DomainResult:
    if feature_dir is None:
        return DomainResult(D_LEDGER, [_ok("ledger", "no active feature; no ledger to inspect.")])
    if ledger_error is not None:
        return DomainResult(D_LEDGER, [_finding(
            EXECUTION_ERROR, "ledger", f"cannot read ledger: {ledger_error.message}",
            NA_REPAIR_UNREADABLE_INPUT, "Repair or restore the ledger 'status.yaml'.",
        )])
    if data is None:
        return DomainResult(D_LEDGER, [_ok("ledger", "active feature has no ledger yet.")])

    findings: list[Finding] = []
    cls = ledger.classify(data)
    if cls == ledger.MIGRATABLE:
        findings.append(_finding(
            WARNING, "schema", ledger.diagnostic_line(cls) or "older ledger schema",
            NA_RUN_STATUS_MIGRATE, "Migrate the ledger with 'specops status migrate'.",
        ))
    elif cls in (ledger.TOO_NEW, ledger.UNSUPPORTED):
        findings.append(_finding(
            BLOCKING, "schema",
            (ledger.refusal_message(cls) or ledger.diagnostic_line(cls)
             or "unsupported ledger schema"),
            NA_LEDGER_UNSUPPORTED,
            "Upgrade SpecOps to a release that understands this ledger schema.",
        ))
    for i, violation in enumerate(ledger.validate_invariants(data)):
        findings.append(_finding(
            BLOCKING, f"invariant-{i:03d}", f"ledger invariant violated: {violation}",
            NA_RECONCILE, "Reconcile/rebaseline the ledger to restore consistency.",
        ))
    for i, (_kind, message) in enumerate(ledger.finding_structural_defects(data)):
        findings.append(_finding(
            BLOCKING, f"finding-{i:03d}", f"handoff/finding defect: {message}",
            NA_VERIFY_BLOCKING, "Resolve the finding via 'specops handoff' before approval.",
        ))
    unresolved = handoff.blocking_approval_check(data)
    if unresolved:
        findings.append(_finding(
            BLOCKING, "blocking-findings",
            f"unverified blocking finding(s): {', '.join(unresolved)}",
            NA_VERIFY_BLOCKING, "Verify or dismiss the blocking findings before approval.",
        ))
    if not findings:
        findings.append(_ok(
            "ledger", f"ledger schema current (v{ledger.CURRENT_SCHEMA}); integrity ok."))
    return DomainResult(D_LEDGER, findings)


def _domain_context_map(root: Path) -> DomainResult:
    findings: list[Finding] = []
    result = contextmap.validate(root)
    cls = contextmap.CLASS_FOR_STATUS.get(result.status, outcome.INFRA_ERROR)
    if cls == outcome.GATE_REJECTION:
        detail = "; ".join(
            d.get("message", d.get("code", "?")) for d in result.diagnostics
        ) or result.status
        findings.append(_finding(
            BLOCKING, "map", f"context map invalid: {detail}", NA_FIX_CONTEXT_MAP,
            "Fix the context map (.specify/specops/context-map.yaml).",
        ))
    elif cls == outcome.INFRA_ERROR:
        findings.append(_finding(
            EXECUTION_ERROR, "map", f"cannot evaluate context map ({result.status})",
            NA_REPAIR_UNREADABLE_INPUT, "Repair the context-map file.",
        ))
    drift = review.digest_drift_warning(root)
    if drift is not None:
        findings.append(_finding(
            WARNING, "drift", drift, NA_REFRESH_PROVENANCE,
            "Refresh context provenance (re-plan) so the recorded digest matches.",
        ))
    if not findings:
        note = (
            "no context map (supported)"
            if result.status == contextmap.S_NO_MAP else "context map valid."
        )
        findings.append(_ok("map", note))
    return DomainResult(D_CONTEXT_MAP, findings)


def _domain_workflow_divergence(root: Path, feature_dir: Path | None) -> DomainResult:
    if feature_dir is None or not (feature_dir / "status.yaml").is_file():
        return DomainResult(
            D_WORKFLOW_DIVERGENCE, [_ok("divergence", "no ledger; nothing to reconcile.")])
    try:
        warnings, violations = reconcile.run(root)
    except LedgerParseError as exc:
        return DomainResult(D_WORKFLOW_DIVERGENCE, [_finding(
            EXECUTION_ERROR, "divergence", f"cannot reconcile: {exc.message}",
            NA_REPAIR_UNREADABLE_INPUT, "Repair the ledger 'status.yaml'.",
        )])
    except SpecopsError:
        # Missing repo/feature precondition — reported by the environment/identity domains.
        return DomainResult(
            D_WORKFLOW_DIVERGENCE, [_ok("divergence", "precondition unmet; skipped.")])
    findings: list[Finding] = []
    for i, violation in enumerate(violations):
        findings.append(_finding(
            BLOCKING, f"violation-{i:03d}", violation, NA_RECONCILE,
            "Reconcile the repository ('specops reconcile') and fix the divergence.",
        ))
    for i, warning in enumerate(warnings):
        findings.append(_finding(
            WARNING, f"warning-{i:03d}", warning, NA_RECONCILE,
            "Review the reconcile warning ('specops reconcile').",
        ))
    if not findings:
        findings.append(_ok("divergence", "ledger agrees with the Git tree and workflow state."))
    return DomainResult(D_WORKFLOW_DIVERGENCE, findings)


def _domain_gate_availability(root: Path) -> DomainResult:
    findings: list[Finding] = []
    validation = gateprofiles.validate(root)
    if validation.status == gateprofiles.S_INVALID:
        return DomainResult(D_GATE_AVAILABILITY, [_finding(
            BLOCKING, "config", f"gate-profiles.yaml invalid: {validation.human}",
            NA_FIX_GATE_PROFILES, "Fix .specify/specops/gate-profiles.yaml.",
        )])
    if validation.status == gateprofiles.S_USAGE_ERROR:
        return DomainResult(D_GATE_AVAILABILITY, [_finding(
            EXECUTION_ERROR, "config", f"cannot read gate profiles: {validation.human}",
            NA_REPAIR_UNREADABLE_INPUT, "Repair .specify/specops/gate-profiles.yaml.",
        )])
    try:
        profiles = gateprofiles.profiles_for(root)
    except SpecopsError:
        # A default suite cannot be synthesized (e.g. no specops.json) — reported by the
        # configuration domain; nothing to probe here.
        return DomainResult(
            D_GATE_AVAILABILITY, [_ok("gate", "no gate profiles configured; skipped.")])
    for profile in profiles:
        parts = shlex.split(profile.command)
        executable = parts[0] if parts else ""
        if executable and shutil.which(executable) is None:
            findings.append(_finding(
                WARNING, f"gate-{profile.name}",
                f"gate '{profile.name}': command '{executable}' not found on PATH",
                NA_INSTALL_GATE_COMMAND,
                f"Install '{executable}' (or fix the gate command) before running preflight.",
            ))
    if not findings:
        findings.append(_ok("gate", "gate profiles valid; all commands resolvable on PATH."))
    return DomainResult(D_GATE_AVAILABILITY, findings)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _error_domain(domain: str, exc: Exception) -> DomainResult:
    """Convert a failed check into *domain*'s execution-error finding (FR-015).

    The single failure→finding conversion (Feature 019 US4, FR-012): used by
    :func:`_run` for in-check failures AND by :func:`diagnose` for shared-read
    failures — exceptions are converted where they are caught, never threaded
    through domain-check argument lists.
    """
    if isinstance(exc, LedgerParseError):
        return DomainResult(domain, [_finding(
            EXECUTION_ERROR, "input", f"cannot evaluate: {exc.message}",
            NA_REPAIR_UNREADABLE_INPUT, "Repair the unreadable input file.",
        )])
    return DomainResult(domain, [_finding(
        EXECUTION_ERROR, "error", f"unexpected error: {exc}",
        NA_REPAIR_UNREADABLE_INPUT, "Inspect the repository state for this domain.",
    )])


def _run(domain: str, fn: Callable[..., DomainResult], *args: Any) -> DomainResult:
    """Run a domain check, converting any unexpected failure into an execution-error
    finding so the diagnostic never crashes and never omits a domain (FR-015)."""
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001 — fail-safe: a domain bug must not crash doctor
        return _error_domain(domain, exc)


def _load_ledger_data(
    feature_dir: Path | None,
) -> tuple[dict | None, LedgerParseError | None]:
    """Read the active feature's ledger read-only. Returns (data, error): (None, None)
    when there is no feature or no ledger yet; (data, None) on success; (None, error)
    when the ledger is unreadable/corrupt."""
    if feature_dir is None or not (feature_dir / "status.yaml").is_file():
        return None, None
    try:
        return ledger.load_raw(feature_dir), None
    except LedgerParseError as exc:
        return None, exc
    except Exception as exc:  # noqa: BLE001 — e.g. a non-UTF8/unreadable ledger (OSError,
        # UnicodeDecodeError). The shared pre-read runs outside the per-domain _run
        # fail-safe, so it must never propagate — convert it to an execution-error the
        # ledger domain reports (FR-015 never-crash / never-omit-a-domain).
        return None, LedgerParseError(f"cannot read ledger: {exc}")


def diagnose(root: Path) -> list[DomainResult]:
    """Run every diagnostic domain in the fixed order and return their results.

    Shared surfaces (repo, active feature, ledger, Spec Kit presence, install state) are
    read once here and threaded into the domains, halving repeated I/O. Any failure of a
    shared read is captured (never raised) so a bad manifest/ledger surfaces as an
    execution-error inside the owning domain rather than crashing doctor (FR-015).
    """
    # Git availability first (FR-012): probe before find_repo, which now itself
    # invokes git. A missing binary yields a blocking git-availability finding
    # rather than crashing every git-dependent domain.
    try:
        git_version: str | None = gitops.ensure_git_available()
        git_error: Exception | None = None
    except gitops.GitError as exc:
        git_version, git_error = None, exc
    repo = gitops.find_repo(root) if git_error is None else None
    feature_dir = speckit.resolve_feature_dir(root)
    data, ledger_error = _load_ledger_data(feature_dir)
    has_speckit = speckit.has_speckit(root)
    try:
        install_state: str | None = migration.detect_state(root)
        state_error: Exception | None = None
    except Exception as exc:  # noqa: BLE001 — surfaced as execution-error by the owning domains
        install_state, state_error = None, exc
    return [
        _run(D_ENVIRONMENT, _domain_environment, repo, has_speckit, git_version, git_error),
        (_run(D_CLI_EXTENSION, _domain_cli_extension, install_state)
         if state_error is None else _error_domain(D_CLI_EXTENSION, state_error)),
        _run(D_INTEGRATION, _domain_integration, root, has_speckit),
        (_run(D_LEGACY, _domain_legacy, install_state)
         if state_error is None else _error_domain(D_LEGACY, state_error)),
        _run(D_CONFIG, _domain_config, root),
        _run(D_FEATURE_IDENTITY, _domain_feature_identity, root, repo, feature_dir, data),
        _run(D_LEDGER, _domain_ledger, feature_dir, data, ledger_error),
        _run(D_CONTEXT_MAP, _domain_context_map, root),
        _run(D_WORKFLOW_DIVERGENCE, _domain_workflow_divergence, root, feature_dir),
        _run(D_GATE_AVAILABILITY, _domain_gate_availability, root),
    ]


def _render_human(domains: list[DomainResult], verdict: str) -> str:
    lines: list[str] = []
    for domain in domains:
        for finding in sorted(domain.findings, key=lambda f: (f.id, f.message)):
            lines.append(f"[{finding.severity}] {domain.domain}: {finding.message}")
            if finding.next_action:
                lines.append(f"    -> {finding.next_action} ({finding.next_action_code})")
    lines.append("")
    lines.append(f"verdict: {verdict}")
    return "\n".join(lines)


def cmd_doctor(root: Path) -> DoctorResult:
    """Run the read-only diagnostic and return a severity-classified result."""
    domains = diagnose(root)
    verdict = _max_severity(domains)
    human = _render_human(domains, verdict)
    return DoctorResult(
        "doctor",
        verdict,
        human,
        {"verdict": verdict, "domains": [d.as_json() for d in domains]},
    )


def doctor_json(result: DoctorResult) -> str:
    """Render the stable, versioned machine-readable document (contracts/)."""
    return outcome.render(
        "doctor",
        result.cls,
        output_version=OUTPUT_VERSION,
        verdict=result.status,
        domains=result.extra["domains"],
    )


# ---------------------------------------------------------------------------
# Compact status report (specops report) — FR-014
# ---------------------------------------------------------------------------


@dataclass
class ReportResult:
    """A report outcome: an outcome class, human text, and the machine payload."""

    cls: str
    human: str
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return outcome.exit_for(self.cls)


def cmd_report(root: Path) -> ReportResult:
    """Build the compact project/feature status report (read-only).

    Raises LedgerParseError when the active feature's ledger is unreadable so the CLI
    can map it to an execution error (exit 2). A missing active feature is an ``ok``
    state with null fields.
    """
    from specops import status

    snapshot = status.compact_status(root)
    payload = {
        "command": "report",
        "output_version": OUTPUT_VERSION,
        "outcome": outcome.status_for(outcome.PASS),
        "class": outcome.PASS,
        **snapshot,
    }
    human = _render_report_human(snapshot)
    return ReportResult(outcome.PASS, human, payload)


def _render_report_human(s: dict[str, Any]) -> str:
    if s["active_feature"] is None:
        return "no active feature."
    tasks = s["tasks"]
    return "\n".join([
        f"feature: {s['active_feature']}",
        f"branch: {s['branch']}",
        f"phase: {s['phase']}",
        f"active task: {s['active_task'] or 'none'}",
        (
            f"tasks: {tasks['total']} total — {tasks['pending']} pending, "
            f"{tasks['in_progress']} in progress, {tasks['done']} done, "
            f"{tasks['orphaned']} orphaned"
        ),
        f"review cycles: {s['review']['cycles']} (blocking open: {s['review']['blocking_open']})",
        f"workflow lane: {s['workflow_lane']}",
    ])


def report_json(result: ReportResult) -> str:
    import json

    return json.dumps(result.payload)
