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
from specops.errors import SpecopsError


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
def reconcile() -> None:
    """Validate ledger commit hashes against Git history."""
    root = Path(".")
    _require_git(root)
    from specops import reconcile as rec_mod
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
def consistency() -> None:
    """Validate SC-ID coverage and plan path-suffix declarations."""
    root = Path(".")
    _require_git(root)
    from specops import consistency as con_mod
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
def review() -> None:
    """Run the deterministic review gates (reconcile → lint → test → working tree)."""
    repo = _require_git(Path("."))
    from specops import review as review_mod
    # Contract: usable from any directory inside the repo — resolve the root.
    if repo.working_tree_dir is None:  # bare repository — no tree to review
        typer.echo("Not a work tree (bare repository).", err=True)
        raise typer.Exit(1)
    root = Path(repo.working_tree_dir)
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


@status_app.command("transition-phase")
@_handle_errors
def status_transition_phase(
    phase: str = typer.Argument(..., help="Target phase, e.g. PLAN."),
    result: str = typer.Option(
        None, "-r", "--result", help="Transition result (APPROVED|REJECTED)."
    ),
) -> None:
    """Advance the feature phase state machine."""
    root = Path(".")
    _require_git(root)
    from specops import status
    typer.echo(status.cmd_transition_phase(root, phase, result=result))


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
def extension_install(
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Decline all interactive prompts.",
    ),
) -> None:
    """Register SpecOps natively via the host's extension mechanism."""
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
