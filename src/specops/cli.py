"""SpecOps CLI entrypoint (Typer). All output is in English (FR-014)."""
from __future__ import annotations

import contextlib
import functools
import importlib.metadata
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import git
import typer

from specops import gitops
from specops.errors import LedgerParseError, SpecopsError


def _force_utf8_output() -> None:
    """Force UTF-8 on stdout/stderr so non-ASCII output (e.g. the '→' in help
    and phase-transition messages) does not crash on Windows consoles that
    default to cp1252. Runs at import time, before any output is written."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(ValueError, OSError):
            reconfigure(encoding="utf-8")


_force_utf8_output()


def _version_callback(value: bool) -> None:
    if value:
        try:
            version = importlib.metadata.version("speckit-specops")
        except importlib.metadata.PackageNotFoundError:
            version = "0.0.0.dev0"
        typer.echo(f"specops {version}")
        raise typer.Exit(0)


app = typer.Typer(
    name="specops",
    help="SpecOps CLI — Speckit companion for agent-guided atomic development.",
    no_args_is_help=True,
)


@app.callback()
def _root_callback(
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    pass

status_app = typer.Typer(
    name="status",
    help="Ledger management: init-spec, start-task, complete-task, transition-phase.",
    no_args_is_help=True,
)
app.add_typer(status_app, name="status")

extension_app = typer.Typer(
    name="extension",
    help="Native Spec Kit extension lifecycle: install, status.",
    no_args_is_help=True,
)
app.add_typer(extension_app, name="extension")

context_app = typer.Typer(
    name="context",
    help="Context map: init, validate, resolve, explain (Feature 008).",
    no_args_is_help=True,
)
app.add_typer(context_app, name="context")

trace_app = typer.Typer(
    name="trace",
    help="End-to-end traceability: classify, validate, report, acknowledge (Feature 010).",
    no_args_is_help=True,
)
app.add_typer(trace_app, name="trace")

handoff_app = typer.Typer(
    name="handoff",
    help="Structured corrective handoffs: findings, close, validate, report (Feature 011).",
    no_args_is_help=True,
)
app.add_typer(handoff_app, name="handoff")

finding_app = typer.Typer(
    name="finding",
    help="Finding lifecycle: add, fix, verify.",
    no_args_is_help=True,
)
handoff_app.add_typer(finding_app, name="finding")

gate_app = typer.Typer(
    name="gate",
    help="Gate profiles: list, validate (read-only inspection) (Feature 012).",
    no_args_is_help=True,
)
app.add_typer(gate_app, name="gate")

# ---------------------------------------------------------------------------
# Error boundary: single exit-code mapper (contracts/errors.md)
# ---------------------------------------------------------------------------

_F = TypeVar("_F", bound=Callable[..., Any])


def _handle_errors(fn: _F) -> _F:
    """Catch SpecopsError, echo message to stderr, exit with the mapped code."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except SpecopsError as exc:
            typer.echo(exc.message, err=True)
            raise typer.Exit(exc.exit_code) from None
    return wrapper  # type: ignore[return-value]


def _require_git(root: Path = Path(".")) -> git.Repo:
    """Fail with exit 1 within <1 s when not inside a Git repo (FR-002, SC-008).

    Returns the resolved Repo so callers that need it don't re-derive it.
    """
    repo = gitops.find_repo(root)
    if repo is None:
        typer.echo("Not a Git repository. Run 'git init' or 'specops init' first.", err=True)
        raise typer.Exit(1)
    return repo


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("init")
@_handle_errors
def init(
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Decline all interactive prompts.",
    ),
) -> None:
    """Prepare a Speckit repository for SpecOps."""
    from specops import initializer
    root = Path(".")
    initializer.run(root, non_interactive=non_interactive)


@app.command("reconcile")
@_handle_errors
def reconcile(
    json_out: bool = typer.Option(
        False, "--json", help="Emit the stable outcome JSON (Feature 007)."
    ),
) -> None:
    """Validate the ledger against Git history and the workspace."""
    root = Path(".")
    _require_git(root)
    from specops import outcome
    from specops import reconcile as rec_mod
    if json_out:
        try:
            feature_dir, data, repo = rec_mod.load_state(root)
            warnings, violations = rec_mod.history_checks(root, feature_dir, data, repo)
            dim = rec_mod.divergence_of(root, feature_dir, data, repo)
        except (LedgerParseError, SpecopsError) as exc:
            typer.echo(outcome.render("reconcile", outcome.INFRA_ERROR, detail=exc.message))
            raise typer.Exit(outcome.exit_for(outcome.INFRA_ERROR)) from None
        warns = warnings or None
        if dim is not None:
            # Workspace/identity/workflow-state divergence — rebaseline re-anchors it.
            typer.echo(outcome.render(
                "reconcile", outcome.INFRA_ERROR,
                diverged_dimension=dim, remedy="specops status rebaseline", warnings=warns,
            ))
            raise typer.Exit(outcome.exit_for(outcome.INFRA_ERROR))
        if violations:
            # Commit-history / evidence integrity — NOT rebaseline-fixable (no remedy).
            typer.echo(outcome.render(
                "reconcile", outcome.INFRA_ERROR, violations=violations, warnings=warns,
            ))
            raise typer.Exit(outcome.exit_for(outcome.INFRA_ERROR))
        typer.echo(outcome.render("reconcile", outcome.PASS, warnings=warns))
        return
    warnings, violations = rec_mod.run(root)
    for w in warnings:
        typer.echo(w)
    if violations:
        for v in violations:
            typer.echo(v, err=True)
        raise typer.Exit(1)
    typer.echo("reconcile: ok")


@app.command("consistency")
@_handle_errors
def consistency(
    json_out: bool = typer.Option(
        False, "--json", help="Emit the stable outcome JSON (Feature 007)."
    ),
) -> None:
    """Validate SC-ID coverage and plan path-suffix declarations."""
    root = Path(".")
    _require_git(root)
    from specops import consistency as con_mod
    from specops import outcome
    if json_out:
        try:
            _warnings, violations = con_mod.run(root)
        except (LedgerParseError, SpecopsError) as exc:
            typer.echo(outcome.render("consistency", outcome.INFRA_ERROR, detail=exc.message))
            raise typer.Exit(outcome.exit_for(outcome.INFRA_ERROR)) from None
        if violations:
            typer.echo(outcome.render("consistency", outcome.GATE_REJECTION, violations=violations))
            raise typer.Exit(outcome.exit_for(outcome.GATE_REJECTION))
        typer.echo(outcome.render("consistency", outcome.PASS))
        return
    warnings, violations = con_mod.run(root)
    for w in warnings:
        typer.echo(w)
    if violations:
        for v in violations:
            typer.echo(v, err=True)
        raise typer.Exit(1)
    typer.echo("consistency: ok")


@app.command("review")
@_handle_errors
def review(
    json_out: bool = typer.Option(
        False, "--json", help="Emit the stable outcome JSON (Feature 007)."
    ),
    soft: bool = typer.Option(
        False, "--soft",
        help="With --json, always exit 0 (the verdict is in the JSON). Use inside a "
             "do-while loop body so a REJECTED verdict drives the loop instead of "
             "aborting the run (Feature 007).",
    ),
    sarif: bool = typer.Option(
        False, "--sarif",
        help="Emit a SARIF 2.1.0 projection of the review findings and exit 0 "
             "(a read-only findings export, opt-in; Feature 012).",
    ),
) -> None:
    """Run the deterministic review gates (reconcile → profile suite → working tree)."""
    repo = _require_git(Path("."))
    from specops import gateprofiles, outcome
    from specops import review as review_mod
    # Contract: usable from any directory inside the repo — resolve the root.
    if repo.working_tree_dir is None:  # bare repository — no tree to review
        typer.echo("Not a work tree (bare repository).", err=True)
        raise typer.Exit(1)
    root = Path(repo.working_tree_dir)
    if sarif:
        _emit_sarif(root)
        return
    _ov = gateprofiles.OUTPUT_VERSION
    if json_out:
        try:
            report = review_mod.evaluate(root)
        except (LedgerParseError, SpecopsError) as exc:
            typer.echo(outcome.render("review", outcome.INFRA_ERROR, detail=exc.message))
            raise typer.Exit(outcome.exit_for(outcome.INFRA_ERROR)) from None
        gates = [_gate_json(r) for r in report.results]
        if report.passed:
            typer.echo(outcome.render(
                "review", outcome.PASS, verdict="APPROVED", gates=gates, output_version=_ov))
            return
        typer.echo(outcome.render(
            "review", outcome.GATE_REJECTION, verdict="REJECTED", gates=gates, output_version=_ov))
        # --soft keeps exit 0 so a do-while body can branch on the verdict; the
        # terminal gate (hard `specops review`) is what fails closed on REJECTED.
        if not soft:
            raise typer.Exit(outcome.exit_for(outcome.GATE_REJECTION))
        return
    typer.echo(review_mod.run_gates(root))


# ---------------------------------------------------------------------------
# status subcommands
# ---------------------------------------------------------------------------

@status_app.command("init-spec")
@_handle_errors
def status_init_spec(
    name: str = typer.Argument(None, help="Feature directory name (optional)."),
) -> None:
    """Create status.yaml for the active feature."""
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(status.cmd_init_spec(root, name))


@status_app.command("start-task")
@_handle_errors
def status_start_task(
    task_id: str = typer.Argument(..., help="Task identifier, e.g. T001."),
) -> None:
    """Mark a task IN_PROGRESS and record the start commit."""
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(status.cmd_start_task(root, task_id))


@status_app.command("complete-task")
@_handle_errors
def status_complete_task(
    task_id: str = typer.Argument(..., help="Task identifier, e.g. T001."),
    auto: bool = typer.Option(
        False, "--auto", help="Run test_command and harvest evidence automatically."
    ),
    evidence: str = typer.Option(
        None, "--evidence", help='Caller-supplied evidence string, e.g. "CLI_LOG:checked ok".'
    ),
) -> None:
    """Mark a task DONE with evidence."""
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(status.cmd_complete_task(root, task_id, auto=auto, evidence=evidence))


@status_app.command("show")
@_handle_errors
def status_show() -> None:
    """Show ledger state (read-only)."""
    root = Path(".")
    from specops import status
    typer.echo(status.cmd_show(root))


@status_app.command("migrate")
@_handle_errors
def status_migrate() -> None:
    """Migrate the active feature's ledger to the current schema (idempotent)."""
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(f"status migrate: {status.cmd_migrate(root)}")


@status_app.command("rebaseline")
@_handle_errors
def status_rebaseline() -> None:
    """Re-anchor the ledger's branch/baseline to the current workspace.

    Use after a deliberate branch rename or history rewrite that the identity
    gate refuses. Never changes the bound feature identity.
    """
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(f"status rebaseline: {status.cmd_rebaseline(root)}")


@status_app.command("record-step")
@_handle_errors
def status_record_step(
    step: str = typer.Argument(..., help="Optional step: clarify | checklist | analyze."),
    decision: str = typer.Option(..., "--decision", help="Decision: run | skip."),
) -> None:
    """Record a human run/skip decision for an optional lifecycle step (Feature 007)."""
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(status.cmd_record_step(root, step, decision=decision))


@status_app.command("transition-phase")
@_handle_errors
def status_transition_phase(
    phase: str = typer.Argument(..., help="Target phase, e.g. PLAN."),
    result: str = typer.Option(
        None, "-r", "--result", help="Transition result (APPROVED|REJECTED)."
    ),
    if_needed: bool = typer.Option(
        False, "--if-needed",
        help="No-op-and-continue if the ledger is already in the target phase (Feature 007).",
    ),
) -> None:
    """Advance the feature phase state machine."""
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(status.cmd_transition_phase(root, phase, result=result, if_needed=if_needed))


# ---------------------------------------------------------------------------
# extension subcommands (Feature 005 — native Spec Kit extension)
# ---------------------------------------------------------------------------

@extension_app.command("status")
@_handle_errors
def extension_status() -> None:
    """Report the native-extension installation state (read-only)."""
    root = Path(".")
    from specops import compat, migration
    state = migration.detect_state(root)
    result = compat.check()
    typer.echo(f"installation: {state}")
    typer.echo(f"cli: {result.installed or 'absent'} (requires >= {result.required})")


@extension_app.command("install")
@_handle_errors
def extension_install() -> None:
    """Register SpecOps natively via the host's extension mechanism.

    Non-interactive by design: it never prompts and fails closed (leaving the
    repository unchanged) when preconditions are not met.
    """
    root = Path(".")
    from specops import extension
    status = extension.install(root)
    typer.echo(f"extension install: {status}")


@extension_app.command("migrate")
@_handle_errors
def extension_migrate() -> None:
    """Migrate a legacy marker-injected installation to the native extension."""
    root = Path(".")
    from specops import migration
    status = migration.migrate(root)
    typer.echo(f"extension migrate: {status}")


@extension_app.command("update")
@_handle_errors
def extension_update() -> None:
    """Refresh the registered hooks/command to the current templates."""
    root = Path(".")
    from specops import extension
    typer.echo(f"extension update: {extension.update(root)}")


@extension_app.command("disable")
@_handle_errors
def extension_disable() -> None:
    """Unregister hooks/command from the host while retaining config and ledgers."""
    root = Path(".")
    from specops import extension
    typer.echo(f"extension disable: {extension.disable(root)}")


@extension_app.command("enable")
@_handle_errors
def extension_enable() -> None:
    """Re-register from retained configuration."""
    root = Path(".")
    from specops import extension
    typer.echo(f"extension enable: {extension.enable(root)}")


@extension_app.command("remove")
@_handle_errors
def extension_remove(
    purge: bool = typer.Option(
        False, "--purge", help="Also delete SpecOps configuration and feature ledgers.",
    ),
) -> None:
    """Remove the native installation (retains config/ledgers unless --purge)."""
    root = Path(".")
    from specops import extension
    typer.echo(f"extension remove: {extension.remove(root, purge=purge)}")


# ---------------------------------------------------------------------------
# context subcommands (Feature 008 — context map core)
# ---------------------------------------------------------------------------


def _emit_context(result: Any, json_out: bool) -> None:
    """Render a contextmap.CommandResult and exit with its mapped code."""
    from specops import contextmap, outcome
    if json_out:
        typer.echo(outcome.render(
            result.command, result.cls,
            status=result.status, output_version=contextmap.OUTPUT_VERSION,
            **result.extra,
        ))
    else:
        typer.echo(result.human, err=result.cls != outcome.PASS)
    raise typer.Exit(result.exit_code)


@context_app.command("init")
@_handle_errors
def context_init(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Create the starter context map when absent (idempotent, atomic)."""
    from specops import contextmap
    _emit_context(contextmap.cmd_init(Path(".")), json_out)


@context_app.command("validate")
@_handle_errors
def context_validate(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Validate the context map; report all defects in one pass."""
    from specops import contextmap
    _emit_context(contextmap.cmd_validate(Path(".")), json_out)


@context_app.command("resolve")
@_handle_errors
def context_resolve(
    path: str = typer.Option(None, "--path", help="Repository path to resolve."),
    ctx_id: str = typer.Option(None, "--id", help="Context id to resolve."),
    phase: str = typer.Option(None, "--phase", help="Lifecycle phase for the read set."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Resolve a path or id to its ordered, phase-specific context package."""
    from specops import contextmap
    _emit_context(
        contextmap.cmd_resolve(Path("."), path=path, ctx_id=ctx_id, phase=phase), json_out
    )


@context_app.command("explain")
@_handle_errors
def context_explain(
    path: str = typer.Option(None, "--path", help="Repository path to explain."),
    ctx_id: str = typer.Option(None, "--id", help="Context id to explain."),
    phase: str = typer.Option(None, "--phase", help="Lifecycle phase for the read set."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Explain why a context was resolved (ordered reason trace)."""
    from specops import contextmap
    _emit_context(
        contextmap.cmd_explain(Path("."), path=path, ctx_id=ctx_id, phase=phase), json_out
    )


@context_app.command("plan-check")
@_handle_errors
def context_plan_check(
    plan: str = typer.Option(None, "--plan", help="Path to plan.md (default: active feature)."),
    phase: str = typer.Option(None, "--phase", help="Lifecycle phase for the read set."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Validate the plan's declared context topology against the map (Feature 009)."""
    from specops import contextmap, speckit
    root = Path(".")
    if plan is not None:
        plan_path = Path(plan)
    else:
        feature_dir = speckit.resolve_feature_dir(root)
        plan_path = (feature_dir / "plan.md") if feature_dir is not None else Path("plan.md")
    plan_text = plan_path.read_text(encoding="utf-8") if plan_path.is_file() else ""
    _emit_context(
        contextmap.cmd_plan_check(root, plan_text=plan_text, phase=phase), json_out
    )


@context_app.command("impact")
@_handle_errors
def context_impact(
    path: list[str] = typer.Option(None, "--path", help="Changed path (repeatable); else Git."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Report contexts affected by a change, over reverse dependency edges (Feature 009)."""
    from specops import contextmap, gitops, status
    root = Path(".")
    if path:
        paths: list[str] = list(path)
    else:
        repo = gitops.find_repo(root)
        if repo is None:
            _emit_context(contextmap.CommandResult(
                "impact", contextmap.S_USAGE_ERROR,
                "context impact: not a Git repository and no --path given"), json_out)
            return
        try:
            baseline = status.read_baseline(root)
        except Exception:
            baseline = ""
        if not baseline or not gitops.commit_exists(repo, baseline):
            _emit_context(contextmap.CommandResult(
                "impact", contextmap.S_USAGE_ERROR,
                "context impact: no resolvable ledger baseline; pass --path explicitly"), json_out)
            return
        paths = gitops.name_only_diff(repo, baseline, "HEAD")
    _emit_context(contextmap.cmd_impact(root, paths=paths), json_out)


@context_app.command("stale")
@_handle_errors
def context_stale(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Report context-map patterns that match zero Git-tracked files (Feature 009)."""
    from specops import contextmap, gitops
    root = Path(".")
    repo = gitops.find_repo(root)
    if repo is None:
        _emit_context(contextmap.CommandResult(
            "stale", contextmap.S_USAGE_ERROR, "context stale: not a Git repository"), json_out)
        return
    tracked = [f for f in repo.git.ls_files().splitlines() if f]
    _emit_context(contextmap.cmd_stale(root, tracked), json_out)


# ---------------------------------------------------------------------------
# trace subcommands (Feature 010 — end-to-end traceability)
# ---------------------------------------------------------------------------


def _emit_trace(result: Any, json_out: bool) -> None:
    """Render a trace.TraceResult and exit with its mapped code."""
    from specops import outcome, trace
    if json_out:
        typer.echo(outcome.render(
            result.command, result.cls,
            status=result.status, output_version=trace.OUTPUT_VERSION,
            **result.extra,
        ))
    else:
        typer.echo(result.human, err=result.cls != outcome.PASS)
    raise typer.Exit(result.exit_code)


@trace_app.command("classify")
@_handle_errors
def trace_classify(
    path: list[str] = typer.Option(None, "--path", help="Changed path (repeatable); else Git."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Classify every effective-diff path (planned / discovered / unexplained)."""
    from specops import trace
    _emit_trace(
        trace.cmd_classify(Path("."), explicit_paths=list(path) if path else None), json_out
    )


@trace_app.command("validate")
@_handle_errors
def trace_validate(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Fail closed on any trace defect or unexplained effective-diff path."""
    from specops import trace
    _emit_trace(trace.cmd_validate(Path(".")), json_out)


@trace_app.command("report")
@_handle_errors
def trace_report(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Render the full trace: success criteria → tasks → commits → evidence → findings."""
    from specops import trace
    _emit_trace(trace.cmd_report(Path(".")), json_out)


@trace_app.command("acknowledge")
@_handle_errors
def trace_acknowledge(
    path: str = typer.Argument(..., help="Repo-relative path to acknowledge."),
    task: str = typer.Option(..., "--task", help="Task id the discovery belongs to."),
    reason: str = typer.Option(..., "--reason", help="Concise reason for the discovery."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Record a one-time path-level acknowledgement of a discovered path."""
    from specops import trace
    _emit_trace(trace.cmd_acknowledge(Path("."), path, task=task, reason=reason), json_out)


# ---------------------------------------------------------------------------
# handoff — structured corrective handoffs (Feature 011)
# ---------------------------------------------------------------------------


def _emit_handoff(result: Any, json_out: bool) -> None:
    """Render a handoff.HandoffResult and exit with its mapped code."""
    from specops import handoff, outcome
    if json_out:
        typer.echo(outcome.render(
            result.command, result.cls,
            status=result.status, output_version=handoff.OUTPUT_VERSION,
            **result.extra,
        ))
    else:
        typer.echo(result.human, err=result.cls != outcome.PASS)
    raise typer.Exit(result.exit_code)


@finding_app.command("add")
@_handle_errors
def handoff_finding_add(
    severity: str = typer.Option(..., "--severity", help="blocking | advisory."),
    rule: str = typer.Option(..., "--rule", help="The rule/principle violated."),
    file: str = typer.Option(..., "--file", help="Repo-relative path of the finding."),
    action: str = typer.Option(..., "--action", help="Concise corrective action."),
    line: int = typer.Option(None, "--line", help="Line number (optional)."),
    expected_evidence: str = typer.Option(
        None, "--expected-evidence", help="Declared evidence that will close it (blocking)."),
    closure: str = typer.Option(None, "--closure", help="Closure criteria (blocking)."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Record a structured finding in the current review round's handoff."""
    from specops import handoff
    _emit_handoff(handoff.cmd_finding_add(
        Path("."), severity=severity, rule=rule, file=file, line=line, action=action,
        expected_evidence=expected_evidence, closure=closure,
    ), json_out)


@finding_app.command("fix")
@_handle_errors
def handoff_finding_fix(
    finding_id: str = typer.Argument(..., help="Finding id (e.g. R2-F01)."),
    task: str = typer.Option(..., "--task", help="Resolving task id."),
    commit: list[str] = typer.Option(None, "--commit", help="Corrective commit sha (repeatable)."),
    evidence: str = typer.Option(None, "--evidence", help="Actual <CLASS>:<summary> evidence."),
    auto: bool = typer.Option(False, "--auto", help="Collect commits/evidence from the task."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """OPEN -> FIXED: link the resolving task, commit(s), and evidence."""
    from specops import handoff
    _emit_handoff(handoff.cmd_finding_fix(
        Path("."), finding_id, task=task, commits=list(commit) if commit else [],
        evidence=evidence, auto=auto,
    ), json_out)


@finding_app.command("verify")
@_handle_errors
def handoff_finding_verify(
    finding_id: str = typer.Argument(..., help="Finding id (e.g. R2-F01)."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """FIXED -> VERIFIED: mechanical precondition guard; the reviewer's closure judgment."""
    from specops import handoff
    _emit_handoff(handoff.cmd_finding_verify(Path("."), finding_id), json_out)


@finding_app.command("dismiss")
@_handle_errors
def handoff_finding_dismiss(
    finding_id: str = typer.Argument(..., help="Finding id (e.g. R2-F01)."),
    reason: str = typer.Option(..., "--reason", help="Why the finding is withdrawn."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Withdraw a false-positive or superseded finding to the terminal DISMISSED state."""
    from specops import handoff
    _emit_handoff(handoff.cmd_finding_dismiss(Path("."), finding_id, reason=reason), json_out)


@handoff_app.command("authorize")
@_handle_errors
def handoff_authorize(
    path: list[str] = typer.Option(..., "--path", help="Authorized corrective path (repeatable)."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Set/extend the current round handoff's authorized corrective paths."""
    from specops import handoff
    _emit_handoff(handoff.cmd_authorize(Path("."), list(path)), json_out)


@handoff_app.command("close")
@_handle_errors
def handoff_close(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Close the current round's handoff (all blocking findings VERIFIED); idempotent."""
    from specops import handoff
    _emit_handoff(handoff.cmd_close(Path(".")), json_out)


@handoff_app.command("validate")
@_handle_errors
def handoff_validate(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Fail closed on any handoff defect (dangling ref, missing closure, contradictory)."""
    from specops import handoff
    _emit_handoff(handoff.cmd_validate(Path(".")), json_out)


@handoff_app.command("report")
@_handle_errors
def handoff_report(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Render every handoff finding and the remaining unverified blocking set."""
    from specops import handoff
    _emit_handoff(handoff.cmd_report(Path(".")), json_out)


@handoff_app.command("import")
@_handle_errors
def handoff_import(
    round: int = typer.Option(None, "--round", help="Review round to import (default: current)."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Import legacy revision-X.md prose into structured advisory findings."""
    from specops import handoff
    _emit_handoff(handoff.cmd_import(Path("."), round), json_out)


@handoff_app.command("render")
@_handle_errors
def handoff_render(
    round: int = typer.Option(..., "--round", help="Review round to render."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Project the round's handoff to revisions/revision-<round>.md (structured -> Markdown)."""
    from specops import handoff
    _emit_handoff(handoff.render_revision(Path("."), round), json_out)


# ---------------------------------------------------------------------------
# gate subcommands (Feature 012 — read-only inspection; profiles run in review)
# ---------------------------------------------------------------------------


def _emit_sarif(root: Path) -> None:
    """Emit a SARIF 2.1.0 projection of the ledger's findings (read-only, exit 0)."""
    import json as _json

    from specops import ledger, sarif, speckit
    feature_dir = speckit.resolve_feature_dir(root)
    data: dict[str, Any] = {}
    if feature_dir is not None:
        try:
            data = ledger.load_raw(feature_dir)
        except SpecopsError:
            data = {}
    version = "0.0.0"
    with contextlib.suppress(importlib.metadata.PackageNotFoundError):
        version = importlib.metadata.version("speckit-specops")
    typer.echo(_json.dumps(sarif.from_ledger(data, tool_version=version)))


def _gate_json(r: Any) -> dict[str, Any]:
    """Provenance object for one gate in a verdict (Feature 012, FR-011/FR-012)."""
    obj: dict[str, Any] = {"name": r.name, "status": r.status}
    for field_name in ("disposition", "reason", "evidence_id", "commit_range"):
        value = getattr(r, field_name, None)
        if value is not None:
            obj[field_name] = value
    if getattr(r, "affected_paths", None):
        obj["affected_paths"] = r.affected_paths
    return obj


def _emit_gate(result: Any, json_out: bool) -> None:
    """Render a gateprofiles.GateCommandResult and exit with its mapped code."""
    from specops import gateprofiles, outcome
    if json_out:
        typer.echo(outcome.render(
            result.command, result.cls,
            status=result.status, output_version=gateprofiles.OUTPUT_VERSION,
            **result.extra,
        ))
    else:
        typer.echo(result.human, err=result.cls != outcome.PASS)
    raise typer.Exit(result.exit_code)


def _effective_diff_paths(root: Path) -> list[str]:
    """Best-effort effective-diff paths for selection; [] when undeterminable."""
    from specops import gitops, status
    repo = gitops.find_repo(root)
    if repo is None:
        return []
    try:
        baseline = status.read_baseline(root)
    except Exception:
        baseline = ""
    if not baseline or not gitops.commit_exists(repo, baseline):
        return []
    return gitops.name_only_diff(repo, baseline, "HEAD")


@gate_app.command("list")
@_handle_errors
def gate_list(
    path: list[str] = typer.Option(None, "--path", help="Changed path (repeatable); else Git."),
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Resolve and display the selected gate suite for the effective diff (read-only)."""
    from specops import gateprofiles
    root = Path(".")
    changed = list(path) if path else _effective_diff_paths(root)
    _emit_gate(gateprofiles.cmd_list(root, changed), json_out)


@gate_app.command("validate")
@_handle_errors
def gate_validate(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
) -> None:
    """Validate the gate-profile config; report every defect in one pass (FR-014)."""
    from specops import gateprofiles
    _emit_gate(gateprofiles.validate(Path(".")), json_out)


@gate_app.command("report")
@_handle_errors
def gate_report(
    json_out: bool = typer.Option(False, "--json", help="Emit the stable outcome JSON."),
    sarif: bool = typer.Option(
        False, "--sarif", help="Emit a SARIF 2.1.0 findings projection and exit 0 (opt-in)."),
) -> None:
    """Report the verdict's provenance: each gate's disposition/reason/inputs/evidence
    plus the ledger's structured evidence records (read-only, FR-011/FR-012)."""
    from specops import gateprofiles, review
    root = Path(".")
    repo = _require_git(root)
    if repo.working_tree_dir is None:
        typer.echo("Not a work tree (bare repository).", err=True)
        raise typer.Exit(1)
    root = Path(repo.working_tree_dir)
    if sarif:
        _emit_sarif(root)
        return
    try:
        report = review.evaluate(root)
    except (LedgerParseError, SpecopsError) as exc:
        typer.echo(f"gate-report: cannot evaluate: {exc.message}", err=True)
        raise typer.Exit(2) from None
    from specops import evidence as evidence_mod
    gates = [_gate_json(r) for r in report.results]
    ev = evidence_mod.canonical_sort(review._existing_evidence(root))  # FR-021 ordering
    if json_out:
        import json as _json
        typer.echo(_json.dumps({
            "command": "gate-report", "output_version": gateprofiles.OUTPUT_VERSION,
            "verdict": "APPROVED" if report.passed else "REJECTED",
            "gates": gates, "evidence": ev,
        }))
    else:
        typer.echo(report.render())
        typer.echo(f"[evidence] {len(ev)} structured record(s) in the ledger.")


if __name__ == "__main__":
    app()
