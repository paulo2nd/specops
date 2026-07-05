"""specops reconcile: ledger ↔ Git history validator (US3, FR-011)."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from specops import gitops, speckit


def run(root: Path) -> None:
    """
    Validate every recorded commit exists in branch history.

    Exit 0 when clean; exit 1 listing each divergence as '<task-id>: <reason>'.
    `(human)` commit values are exempt (R11).
    Warns (does not fail) on branch mismatch or missing baseline.
    """
    import typer

    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        typer.echo("Cannot resolve active feature directory.", err=True)
        sys.exit(1)

    ledger_path = feature_dir / "status.yaml"
    if not ledger_path.is_file():
        typer.echo(f"Ledger not found: {ledger_path}. Run 'specops status init-spec' first.", err=True)
        sys.exit(1)

    try:
        data = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        typer.echo(f"Cannot parse ledger: {exc}", err=True)
        sys.exit(2)

    if not isinstance(data, dict):
        typer.echo("Ledger has invalid structure.", err=True)
        sys.exit(2)

    repo = gitops.find_repo(root)
    if repo is None:
        typer.echo("Not a Git repository.", err=True)
        sys.exit(1)

    divergences: list[str] = []

    # Branch mismatch warning (not fail)
    ledger_branch = data.get("branch", "")
    current = gitops.current_branch(repo)
    if ledger_branch and current != ledger_branch:
        typer.echo(
            f"Warning: ledger branch '{ledger_branch}' ≠ current branch '{current}'.",
        )

    # Baseline check (warn only)
    baseline = data.get("baseline", "")
    if baseline and not gitops.is_ancestor(repo, baseline):
        typer.echo(
            f"Warning: baseline commit '{baseline[:7]}' not found in local history."
        )

    tasks = data.get("tasks", [])
    for task in tasks:
        tid = task.get("id", "?")

        # Report orphaned tasks
        if task.get("orphaned"):
            typer.echo(f"Warning: '{tid}' is orphaned (removed from tasks.md).")

        # L3: every commit in commits[] must be an ancestor of HEAD
        for sha in task.get("commits", []):
            if sha == "(human)":
                continue
            if not gitops.is_ancestor(repo, sha):
                divergences.append(f"{tid}: commit '{sha[:7]}' is not in branch history")

        # L1: DONE tasks require commits[] and evidence
        if task.get("status") == "DONE":
            if not task.get("commits"):
                divergences.append(f"{tid}: DONE but no commits recorded")
            if not task.get("evidence"):
                divergences.append(f"{tid}: DONE but no evidence recorded")

    if divergences:
        for d in divergences:
            typer.echo(d, err=True)
        sys.exit(1)

    typer.echo("reconcile: ok")
    sys.exit(0)
