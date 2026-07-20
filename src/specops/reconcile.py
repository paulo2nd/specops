"""specops reconcile: ledger ↔ Git history validator (US3, FR-011)."""
from __future__ import annotations

from pathlib import Path

import yaml

from specops import gitops, ledger, speckit
from specops.errors import LedgerParseError, SpecopsError


def load_state(root: Path) -> tuple[Path, dict, gitops.git.Repo]:
    """Resolve the feature dir, read+parse the ledger, and find the repo — once.

    Shared by :func:`run`, :func:`divergence`, and the ``--json`` CLI path so a
    single invocation loads the feature dir, ledger, and repo exactly once.
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

    return feature_dir, data, repo


def history_checks(
    root: Path, feature_dir: Path, data: dict, repo: gitops.git.Repo
) -> tuple[list[str], list[str]]:
    """Return (warnings, violations) from the commit-history / schema checks.

    `(human)` commit values are exempt (R11). Pure over the pre-loaded state.
    """
    warnings: list[str] = []
    violations: list[str] = []

    # Read-only schema diagnostic (FR-029a) — never mutates, never blocks.
    diagnostic = ledger.diagnostic_line(ledger.classify(data))
    if diagnostic is not None:
        warnings.append(f"Warning: {diagnostic}")

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

    for task in data.get("tasks", []):
        tid = task.get("id", "?")
        if task.get("orphaned"):
            warnings.append(f"Warning: '{tid}' is orphaned (removed from tasks.md).")
        for sha in task.get("commits", []):
            if sha == "(human)":
                continue
            if not gitops.is_ancestor(repo, sha):
                violations.append(f"{tid}: commit '{sha[:7]}' is not in branch history")
        if task.get("status") == "DONE" and not task.get("evidence"):
            violations.append(f"{tid}: DONE but no evidence recorded")

    return warnings, violations


def divergence_of(
    root: Path, feature_dir: Path, data: dict, repo: gitops.git.Repo
) -> str | None:
    """Return the first diverged dimension over pre-loaded state, or None.

    Feature 006 workspace identity (feature / branch / baseline) plus the 007
    **workflow-state** dimension (the current phase's active artifact must exist).
    The remedy for any of these is `specops status rebaseline` — no new command.
    """
    dim = ledger.validate_identity(root, repo, data)
    if dim is not None:
        return dim
    artifact = ledger.artifact_for_phase(data.get("current_phase"))
    if not (feature_dir / artifact).is_file():
        return "workflow-state"
    return None


def run(root: Path) -> tuple[list[str], list[str]]:
    """Validate every recorded commit exists in branch history.

    Returns (warnings, violations); violations block. Raises SpecopsError /
    LedgerParseError on blocking preconditions. Thin wrapper over load_state +
    history_checks (kept for the review gate and the plain CLI path).
    """
    feature_dir, data, repo = load_state(root)
    return history_checks(root, feature_dir, data, repo)


def divergence(root: Path) -> str | None:
    """Return the first diverged reconciliation dimension, or None (Feature 007).

    Powers the workflow's fail-closed `reconcile` precondition (FR-010/FR-012).
    A missing ledger returns None (nothing to reconcile yet).
    """
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        return "feature"
    if not (feature_dir / "status.yaml").is_file():
        return None
    feature_dir, data, repo = load_state(root)
    return divergence_of(root, feature_dir, data, repo)
