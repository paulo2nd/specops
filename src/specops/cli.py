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
        w = warnings or None
        if dim is not None:
            # Workspace/identity/workflow-state divergence — rebaseline re-anchors it.
            typer.echo(outcome.render(
                "reconcile", outcome.INFRA_ERROR,
                diverged_dimension=dim, remedy="specops status rebaseline", warnings=w,
            ))
            raise typer.Exit(outcome.exit_for(outcome.INFRA_ERROR))
        if violations:
            # Commit-history / evidence integrity — NOT rebaseline-fixable (no remedy).
            typer.echo(outcome.render(
                "reconcile", outcome.INFRA_ERROR, violations=violations, warnings=w,
            ))
            raise typer.Exit(outcome.exit_for(outcome.INFRA_ERROR))
        typer.echo(outcome.render("reconcile", outcome.PASS, warnings=w))
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
) -> None:
    """Run the deterministic review gates (reconcile → lint → test → working tree)."""
    repo = _require_git(Path("."))
    from specops import outcome
    from specops import review as review_mod
    # Contract: usable from any directory inside the repo — resolve the root.
    if repo.working_tree_dir is None:  # bare repository — no tree to review
        typer.echo("Not a work tree (bare repository).", err=True)
        raise typer.Exit(1)
    root = Path(repo.working_tree_dir)
    if json_out:
        try:
            report = review_mod.evaluate(root)
        except (LedgerParseError, SpecopsError) as exc:
            typer.echo(outcome.render("review", outcome.INFRA_ERROR, detail=exc.message))
            raise typer.Exit(outcome.exit_for(outcome.INFRA_ERROR)) from None
        gates = [{"name": r.name, "status": r.status} for r in report.results]
        if report.passed:
            typer.echo(outcome.render("review", outcome.PASS, verdict="APPROVED", gates=gates))
            return
        typer.echo(
            outcome.render("review", outcome.GATE_REJECTION, verdict="REJECTED", gates=gates)
        )
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


if __name__ == "__main__":
    app()
