"""specops reconcile: ledger ↔ Git history validator (US3, FR-011)."""
from __future__ import annotations

from pathlib import Path

import yaml

from specops import gitops, speckit
from specops.errors import LedgerParseError, SpecopsError


def run(root: Path) -> tuple[list[str], list[str]]:
    """
    Validate every recorded commit exists in branch history.

    Returns (warnings, violations). Violations map to exit 1; warnings are
    informational. `(human)` commit values are exempt (R11).
    Raises SpecopsError / LedgerParseError on blocking preconditions.
    """
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        raise SpecopsError("Cannot resolve active feature directory.")

    ledger_path = feature_dir / "status.yaml"
    if not ledger_path.is_file():
        raise SpecopsError(
            f"Ledger not found: {ledger_path}. Run 'specops status init-spec' first."
        )

    try:
        data = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LedgerParseError(f"Cannot parse ledger: {exc}") from exc

    if not isinstance(data, dict):
        raise LedgerParseError("Ledger has invalid structure.")

    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")

    warnings: list[str] = []
    violations: list[str] = []

    # Branch mismatch warning (not fail)
    ledger_branch = data.get("branch", "")
    current = gitops.current_branch(repo)
    if ledger_branch and current != ledger_branch:
        warnings.append(
            f"Warning: ledger branch '{ledger_branch}' ≠ current branch '{current}'."
        )

    # Baseline check (warn only)
    baseline = data.get("baseline", "")
    if baseline and not gitops.is_ancestor(repo, baseline):
        warnings.append(
            f"Warning: baseline commit '{baseline[:7]}' not found in local history."
        )

    tasks = data.get("tasks", [])
    for task in tasks:
        tid = task.get("id", "?")

        if task.get("orphaned"):
            warnings.append(f"Warning: '{tid}' is orphaned (removed from tasks.md).")

        for sha in task.get("commits", []):
            if sha == "(human)":
                continue
            if not gitops.is_ancestor(repo, sha):
                violations.append(
                    f"{tid}: commit '{sha[:7]}' is not in branch history"
                )

        if task.get("status") == "DONE" and not task.get("evidence"):
            violations.append(f"{tid}: DONE but no evidence recorded")

    return warnings, violations
