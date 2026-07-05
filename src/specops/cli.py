"""SpecOps CLI entrypoint (Typer). All output is in English (FR-014)."""
from __future__ import annotations

from pathlib import Path

import typer

from specops import gitops

app = typer.Typer(
    name="specops",
    help="SpecOps CLI — Speckit companion for agent-guided atomic development.",
    no_args_is_help=True,
)

status_app = typer.Typer(
    name="status",
    help="Ledger management: init-spec, start-task, complete-task, transition-phase.",
    no_args_is_help=True,
)
app.add_typer(status_app, name="status")

# ---------------------------------------------------------------------------
# Exit-code helpers (R9): 0 = success, 1 = blocking failure, 2 = unexpected error
# ---------------------------------------------------------------------------

def exit_ok(message: str = "") -> None:
    if message:
        typer.echo(message)
    raise typer.Exit(0)


def exit_fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def exit_error(message: str) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(2)


def _require_git(root: Path = Path(".")) -> None:
    """Fail with exit 1 within <1 s when not inside a Git repo (FR-002, SC-008)."""
    if not gitops.is_git_repo(root):
        exit_fail("Not a Git repository. Run 'git init' or 'specops init' first.")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("init")
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
def reconcile() -> None:
    """Validate ledger commit hashes against Git history."""
    root = Path(".")
    _require_git(root)
    from specops import reconcile as rec_mod
    rec_mod.run(root)


@app.command("consistency")
def consistency() -> None:
    """Validate SC-ID coverage and plan path-suffix declarations."""
    root = Path(".")
    _require_git(root)
    from specops import consistency as con_mod
    con_mod.run(root)


# ---------------------------------------------------------------------------
# status subcommands
# ---------------------------------------------------------------------------

@status_app.command("init-spec")
def status_init_spec(
    name: str = typer.Argument(None, help="Feature directory name (optional)."),
) -> None:
    """Create status.yaml for the active feature."""
    root = Path(".")
    _require_git(root)
    from specops import status
    status.cmd_init_spec(root, name)


@status_app.command("start-task")
def status_start_task(
    task_id: str = typer.Argument(..., help="Task identifier, e.g. T001."),
) -> None:
    """Mark a task IN_PROGRESS and record the start commit."""
    root = Path(".")
    _require_git(root)
    from specops import status
    status.cmd_start_task(root, task_id)


@status_app.command("complete-task")
def status_complete_task(
    task_id: str = typer.Argument(..., help="Task identifier, e.g. T001."),
    auto: bool = typer.Option(False, "--auto", help="Run test_command and harvest evidence automatically."),
    evidence: str = typer.Option(None, "--evidence", help='Caller-supplied evidence string, e.g. "CLI_LOG:checked ok".'),
) -> None:
    """Mark a task DONE with evidence."""
    root = Path(".")
    _require_git(root)
    from specops import status
    status.cmd_complete_task(root, task_id, auto=auto, evidence=evidence)


@status_app.command("transition-phase")
def status_transition_phase(
    phase: str = typer.Argument(..., help="Target phase, e.g. PLAN."),
    result: str = typer.Option(None, "-r", "--result", help="Transition result (APPROVED|REJECTED|note)."),
) -> None:
    """Advance the feature phase state machine."""
    root = Path(".")
    _require_git(root)
    from specops import status
    status.cmd_transition_phase(root, phase, result=result)


if __name__ == "__main__":
    app()
