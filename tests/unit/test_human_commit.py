"""Feature 019 US4 (FR-009): the ``(human)`` ledger sentinel leaves the generic
git layer; callers that own ledger values filter it explicitly.

Cross-module by design: the git layer's behavior change (``is_ancestor`` no
longer special-cases the sentinel) and every preserved command-level exemption
(reconcile R11, handoff validate, workspace-identity baseline) live side by side.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from specops import gitops, handoff, ledger, reconcile
from tests.conftest import git, make_cycle, make_finding, make_trace_ledger


def test_ledger_owns_the_sentinel_definition() -> None:
    assert ledger.HUMAN_COMMIT == "(human)"
    assert ledger.is_human_commit("(human)")
    assert not ledger.is_human_commit("abc1234")
    assert not ledger.is_human_commit("")


def test_is_ancestor_no_longer_special_cases_human(tmp_git_repo: Path) -> None:
    """At the git layer, ``(human)`` is just an unresolvable ref (sentinel-free)."""
    repo = gitops.find_repo(tmp_git_repo)
    assert repo is not None
    assert gitops.is_ancestor(repo, "(human)") is False


def _current_ledger(root: Path, **kwargs: object) -> Path:
    (root / ".specify").mkdir(exist_ok=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )
    feature_dir = root / "specs" / "001-demo"
    feature_dir.mkdir(parents=True, exist_ok=True)
    led = make_trace_ledger(
        feature="001-demo",
        branch=git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        baseline=git(root, "rev-parse", "HEAD"),
        **kwargs,  # type: ignore[arg-type]
    )
    led["schema_version"] = ledger.CURRENT_SCHEMA
    (feature_dir / "status.yaml").write_text(yaml.dump(led))
    return feature_dir


def test_reconcile_keeps_the_r11_task_commit_exemption(tmp_git_repo: Path) -> None:
    _current_ledger(
        tmp_git_repo,
        tasks=[{
            "id": "T001", "status": "DONE", "started_commit": "0" * 40,
            "commits": ["(human)"], "evidence": "CLI_LOG:ok", "completed_at": None,
        }],
    )
    warnings, violations = reconcile.run(tmp_git_repo)
    assert violations == []


def test_reconcile_baseline_warning_still_exempts_human(tmp_git_repo: Path) -> None:
    feature_dir = _current_ledger(tmp_git_repo)
    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    data["baseline"] = "(human)"
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    warnings, violations = reconcile.run(tmp_git_repo)
    assert violations == []
    assert not any("baseline" in w for w in warnings)


def test_validate_identity_passes_a_human_baseline(tmp_git_repo: Path) -> None:
    """A hand-edited ``(human)`` baseline passed the identity gate before the
    sentinel moved out of gitops — and must continue to (FR-009)."""
    _current_ledger(tmp_git_repo)
    repo = gitops.find_repo(tmp_git_repo)
    data = {
        "feature": "001-demo",
        "branch": git(tmp_git_repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "baseline": "(human)",
    }
    assert ledger.validate_identity(tmp_git_repo, repo, data) is None


def test_handoff_validate_exempts_human_finding_commits(tmp_git_repo: Path) -> None:
    finding = make_finding(
        "R1-F01", severity="blocking", state="FIXED", task="T001",
        commits=["(human)"], evidence="CLI_LOG:manual fix",
    )
    _current_ledger(
        tmp_git_repo,
        tasks=[{
            "id": "T001", "status": "DONE", "started_commit": "0" * 40,
            "commits": [], "evidence": "CLI_LOG:ok", "completed_at": None,
        }],
        review_cycles=[make_cycle(round=1, findings=[finding])],
    )
    result = handoff.cmd_validate(tmp_git_repo)
    assert result.status == handoff.VALIDATE_OK, result.human
