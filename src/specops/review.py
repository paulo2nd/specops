"""specops review: deterministic review gates, cheapest-first (004, FR-001..FR-009).

Gate order is fixed: reconcile → lint → test → working-tree. The first FAIL
stops the run. Evaluation is read-only — the command never writes to the
ledger or any repository file (FR-007). Working-tree cleanliness is
snapshotted at invocation time, so artifacts created by the client's own
lint/test commands cannot fail the run that created them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import git

from specops import config, gitops, shell, status
from specops import reconcile as reconcile_mod
from specops.errors import SpecopsError

GATE_ORDER = ["reconcile", "lint", "test", "working-tree"]
TAIL_LINES = 50
_LINE_WIDTH = 24  # dot-padded label width: "[gate] working-tree ...."


@dataclass
class GateResult:
    """Outcome of one evaluated gate (data-model.md)."""

    name: str
    status: str  # PASS | FAIL | SKIPPED
    detail: list[str] = field(default_factory=list)


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


def _command_gate(name: str, command: str, root: Path) -> GateResult:
    """Run a client lint/test command from the repo root (research R1/R2).

    Empty command → SKIPPED. Output is decoded with errors="replace" so
    non-UTF-8 bytes degrade to replacement characters instead of a crash.
    """
    if not command:
        return GateResult(name, "SKIPPED", [f"{name}_command empty"])
    result = shell.run_client_command(command, root)
    if result.returncode == 0:
        return GateResult(name, "PASS")
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    detail = [f"command: {command}", f"exit code: {result.returncode}", *_tail(combined)]
    return GateResult(name, "FAIL", detail)


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


def run_gates(root: Path) -> str:
    """Evaluate all gates cheapest-first with early stop.

    *root* is the repository root (the CLI resolves it from the invocation
    directory). Returns the rendered report on success; raises SpecopsError
    carrying the report (including the failing gate's evidence) on the
    first FAIL.
    """
    cfg = config.load(root)
    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")
    # Snapshot before any gate runs: the working-tree gate evaluates the
    # tree as it was at invocation (artifacts created by lint/test cannot
    # dirty it), and the baseline is read from the ledger exactly once.
    dirty_at_start = gitops.dirty_files(repo)
    baseline_at_start = status.read_baseline(root)

    report = GateReport()
    for name in GATE_ORDER:
        if name == "reconcile":
            result = _reconcile_gate(root)
        elif name == "lint":
            result = _command_gate("lint", str(cfg.get("lint_command") or ""), root)
        elif name == "test":
            result = _command_gate("test", str(cfg.get("test_command") or ""), root)
        else:
            result = _working_tree_gate(repo, dirty_at_start, baseline_at_start)
        report.results.append(result)
        if result.status == "FAIL":
            raise SpecopsError(report.render())
    return report.render()
