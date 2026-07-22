"""Unit tests for review.py — deterministic review gates (004)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from specops import review
from specops.errors import SpecopsError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(root: Path, lint: str = "", test: str = "") -> None:
    (root / "specops.json").write_text(json.dumps({
        "test_command": test,
        "lint_command": lint,
        "skills_dir": ".specify/skills",
    }))


def _write_ledger(root: Path, baseline: str, branch: str = "main",
                  tasks: list | None = None) -> None:
    feature_dir = root / "specs" / "001-demo"
    data = {
        "feature": "001-demo",
        "branch": branch,
        "baseline": baseline,
        "current_phase": "IMPLEMENT",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": tasks or [],
        "review_cycles": [],
    }
    (feature_dir / "status.yaml").write_text(yaml.dump(data))


def _commit_all(root: Path, msg: str = "setup") -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=root, check=True, capture_output=True)


def _head(root: Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def _branch(root: Path) -> str:
    out = subprocess.run(
        ["git", "branch", "--show-current"], cwd=root,
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def _all_pass_setup(root: Path, lint: str = "", test: str = "") -> None:
    """Config + ledger (baseline = pre-setup HEAD) committed → clean tree, effective diff.

    Scaffolding is committed *before* the baseline (as a real feature branches
    from a point that already contains it), so the post-baseline effective diff is
    only SpecOps-managed state (specops.json, status.yaml), which the Feature 010
    drift gate excludes — leaving zero unexplained paths.
    """
    _commit_all(root, "scaffolding")
    baseline = _head(root)
    _write_config(root, lint=lint, test=test)
    _write_ledger(root, baseline, branch=_branch(root))
    _commit_all(root)


# ---------------------------------------------------------------------------
# Happy path and gate ordering
# ---------------------------------------------------------------------------


def test_all_gates_pass_renders_ordered_report(fake_speckit_repo: Path) -> None:
    _all_pass_setup(fake_speckit_repo)
    out = review.run_gates(fake_speckit_repo)
    assert "[gate] reconcile" in out
    assert "SKIPPED (lint_command empty)" in out
    assert "SKIPPED (test_command empty)" in out
    assert "[gate] working-tree" in out
    positions = [out.index(f"[gate] {n}") for n in review.GATE_ORDER]
    assert positions == sorted(positions)


def test_lint_and_test_pass_with_real_commands(fake_speckit_repo: Path) -> None:
    ok_cmd = f'"{sys.executable}" -c "print(1)"'
    _all_pass_setup(fake_speckit_repo, lint=ok_cmd, test=ok_cmd)
    out = review.run_gates(fake_speckit_repo)
    # lint and test ran (not skipped); the drift gate legitimately SKIPs here —
    # this minimal fixture declares no plan paths/contexts/acknowledgements.
    assert "SKIPPED (lint" not in out and "SKIPPED (test" not in out
    for name in review.GATE_ORDER:
        assert f"[gate] {name}" in out


# ---------------------------------------------------------------------------
# Reconcile gate
# ---------------------------------------------------------------------------


def test_reconcile_violation_stops_before_lint(
    fake_speckit_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = fake_speckit_repo
    baseline = _head(root)
    _write_config(root, lint="echo lint", test="echo test")
    _write_ledger(root, baseline, branch=_branch(root), tasks=[{
        "id": "T001", "status": "DONE", "started_commit": None,
        "commits": ["deadbeef" * 5], "evidence": "TEST_REPORT:x",
        "completed_at": None,
    }])
    _commit_all(root)

    def _forbidden(*args, **kwargs):
        raise AssertionError("lint/test must not run after a reconcile FAIL")

    monkeypatch.setattr(review.shell, "run_client_command", _forbidden)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(root)
    msg = str(exc.value)
    assert "not in branch history" in msg
    assert "[gate] lint" not in msg


def test_reconcile_warning_echoed_and_gate_passes(fake_speckit_repo: Path) -> None:
    root = fake_speckit_repo
    _commit_all(root, "scaffolding")  # scaffolding precedes the baseline (see _all_pass_setup)
    baseline = _head(root)
    _write_config(root)
    _write_ledger(root, baseline, branch="branch-that-does-not-match")
    _commit_all(root)
    out = review.run_gates(root)
    assert "Warning:" in out
    assert "[gate] reconcile" in out


# ---------------------------------------------------------------------------
# Lint / test gates
# ---------------------------------------------------------------------------


def test_failing_test_command_reports_exit_code_and_tail(fake_speckit_repo: Path) -> None:
    cmd = f'"{sys.executable}" -c "import sys; [print(i) for i in range(200)]; sys.exit(3)"'
    _all_pass_setup(fake_speckit_repo, test=cmd)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(fake_speckit_repo)
    msg = str(exc.value)
    assert "[gate] test" in msg
    assert "exit code: 3" in msg
    assert "[output: 200 lines, showing last 50]" in msg
    assert "  199" in msg          # last line present
    assert "  149" not in msg      # line before the tail window absent


def test_failing_lint_stops_before_test(
    fake_speckit_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fail_cmd = f'"{sys.executable}" -c "import sys; sys.exit(2)"'
    _all_pass_setup(fake_speckit_repo, lint=fail_cmd, test="echo test")
    real_run = review.shell.run_client_command
    calls: list[str] = []

    def _spy(cmd, cwd):
        calls.append(cmd)
        return real_run(cmd, cwd)

    monkeypatch.setattr(review.shell, "run_client_command", _spy)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(fake_speckit_repo)
    msg = str(exc.value)
    assert "[gate] lint" in msg and "exit code: 2" in msg
    assert calls == [fail_cmd]
    assert "[gate] test" not in msg


def test_short_output_not_truncated(fake_speckit_repo: Path) -> None:
    cmd = f'"{sys.executable}" -c "import sys; print(\'boom\'); sys.exit(1)"'
    _all_pass_setup(fake_speckit_repo, test=cmd)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(fake_speckit_repo)
    msg = str(exc.value)
    assert "boom" in msg
    assert "showing last" not in msg


# ---------------------------------------------------------------------------
# Working-tree gate
# ---------------------------------------------------------------------------


def test_dirty_tree_fails_with_file_list(fake_speckit_repo: Path) -> None:
    _all_pass_setup(fake_speckit_repo)
    (fake_speckit_repo / "stray.txt").write_text("x\n")
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(fake_speckit_repo)
    msg = str(exc.value)
    assert "[gate] working-tree" in msg
    assert "stray.txt" in msg


def test_no_effective_diff_fails(
    fake_speckit_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _all_pass_setup(fake_speckit_repo)
    monkeypatch.setattr(review.gitops, "name_only_diff", lambda *a, **k: [])
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(fake_speckit_repo)
    assert "no effective diff" in str(exc.value)


def test_missing_baseline_fails_working_tree(fake_speckit_repo: Path) -> None:
    root = fake_speckit_repo
    _write_config(root)
    _write_ledger(root, baseline="", branch=_branch(root))
    _commit_all(root)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(root)
    msg = str(exc.value)
    assert "[gate] working-tree" in msg
    assert "baseline" in msg


def test_unresolvable_baseline_reported_as_such(fake_speckit_repo: Path) -> None:
    """A baseline missing from the clone is not misdiagnosed as an empty diff."""
    root = fake_speckit_repo
    _write_config(root)
    _write_ledger(root, baseline="deadbeef" * 5, branch=_branch(root))
    _commit_all(root)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(root)
    msg = str(exc.value)
    assert "cannot be resolved" in msg
    assert "no effective diff" not in msg


def test_pass_report_lists_changed_files_and_baseline(fake_speckit_repo: Path) -> None:
    """The surgical-review agent reads its scope from the gate output (finding 1)."""
    _all_pass_setup(fake_speckit_repo)
    out = review.run_gates(fake_speckit_repo)
    assert "changed since baseline" in out
    assert "specops.json" in out          # a real changed file is listed
    assert "specs/001-demo/status.yaml" in out


def test_artifacts_created_by_test_command_do_not_fail_working_tree(
    fake_speckit_repo: Path,
) -> None:
    """Dirty state is snapshotted at invocation, before lint/test run (finding 2)."""
    cmd = f'"{sys.executable}" -c "open(\'artifact.tmp\', \'w\').write(\'x\')"'
    _all_pass_setup(fake_speckit_repo, test=cmd)
    out = review.run_gates(fake_speckit_repo)
    assert "[gate] working-tree" in out
    assert "artifact.tmp" not in out


def test_command_gate_runs_from_repo_root(
    fake_speckit_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """lint/test execute with cwd=root even when the process cwd is elsewhere."""
    probe = (
        f'"{sys.executable}" -c '
        '"import os, sys; sys.exit(0 if os.path.exists(\'specops.json\') else 7)"'
    )
    _all_pass_setup(fake_speckit_repo, test=probe)
    monkeypatch.chdir(tmp_path)
    out = review.run_gates(fake_speckit_repo)
    assert "[gate] test" in out


def test_non_utf8_command_output_degrades_cleanly(fake_speckit_repo: Path) -> None:
    """Invalid bytes in lint/test output become a FAIL report, not a crash."""
    cmd = (
        f'"{sys.executable}" -c '
        '"import sys; sys.stdout.buffer.write(b\'bad \\xff\\xfe bytes\\n\'); sys.exit(1)"'
    )
    _all_pass_setup(fake_speckit_repo, test=cmd)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(fake_speckit_repo)
    msg = str(exc.value)
    assert "exit code: 1" in msg
    assert "bad" in msg


def test_reconcile_fail_still_echoes_warnings(fake_speckit_repo: Path) -> None:
    """Warnings are not dropped when violations exist (finding 7)."""
    root = fake_speckit_repo
    baseline = _head(root)
    _write_config(root)
    _write_ledger(root, baseline, branch="branch-that-does-not-match", tasks=[{
        "id": "T001", "status": "DONE", "started_commit": None,
        "commits": ["deadbeef" * 5], "evidence": "TEST_REPORT:x",
        "completed_at": None,
    }])
    _commit_all(root)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(root)
    msg = str(exc.value)
    assert "not in branch history" in msg
    assert "Warning:" in msg


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_skipped_reason_inline() -> None:
    report = review.GateReport(results=[
        review.GateResult("reconcile", "PASS"),
        review.GateResult("lint", "SKIPPED", ["lint_command empty"]),
    ])
    lines = report.render().splitlines()
    assert lines[0].startswith("[gate] reconcile")
    assert lines[0].rstrip().endswith("PASS")
    assert lines[1].rstrip().endswith("SKIPPED (lint_command empty)")


def test_report_passed_property() -> None:
    ok = review.GateReport(results=[review.GateResult("reconcile", "PASS")])
    bad = review.GateReport(results=[
        review.GateResult("reconcile", "PASS"),
        review.GateResult("lint", "FAIL", ["exit code: 2"]),
    ])
    assert ok.passed
    assert not bad.passed


# ---------------------------------------------------------------------------
# Feature 009 — context-map digest drift (non-blocking warning) [SC-008]
# ---------------------------------------------------------------------------

def _ledger_with_task_provenance(root: Path, digest: str) -> None:
    feature_dir = root / "specs" / "001-demo"
    data = {
        "feature": "001-demo", "branch": _branch(root), "baseline": _head(root),
        "current_phase": "IMPLEMENT",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [{"id": "T001", "status": "DONE", "evidence": "CLI_LOG:ok",
                   "context_provenance": {"map": "present", "digest": digest,
                                          "context_ids": ["api"], "output_version": 1}}],
        "review_cycles": [],
    }
    (feature_dir / "status.yaml").write_text(yaml.dump(data))


def test_no_drift_warning_when_no_map(fake_speckit_repo: Path) -> None:
    from specops import review
    _ledger_with_task_provenance(fake_speckit_repo, "deadbeef")
    assert review.digest_drift_warning(fake_speckit_repo) is None


def test_drift_warning_when_digest_changed(fake_speckit_repo: Path) -> None:
    from specops import contextmap, review
    from tests.conftest import DEP_GRAPH_MAP, write_map
    write_map(fake_speckit_repo, DEP_GRAPH_MAP)
    _ledger_with_task_provenance(fake_speckit_repo, "stale000digest")
    warning = review.digest_drift_warning(fake_speckit_repo)
    assert warning is not None and "drift" in warning
    # sanity: recorded != current
    assert contextmap.map_digest(fake_speckit_repo) != "stale000digest"


def test_no_drift_warning_when_digest_matches(fake_speckit_repo: Path) -> None:
    from specops import contextmap, review
    from tests.conftest import DEP_GRAPH_MAP, write_map
    write_map(fake_speckit_repo, DEP_GRAPH_MAP)
    current = contextmap.map_digest(fake_speckit_repo)
    _ledger_with_task_provenance(fake_speckit_repo, current)
    assert review.digest_drift_warning(fake_speckit_repo) is None


def test_drift_warning_not_masked_by_review_cycle_digest(fake_speckit_repo: Path) -> None:
    # Finding 2 regression: a review-cycle record written at review time carries
    # the CURRENT (drifted) digest; it must not mask the stale planning digest
    # recorded on task records.
    from specops import contextmap, review
    from tests.conftest import DEP_GRAPH_MAP, write_map
    write_map(fake_speckit_repo, DEP_GRAPH_MAP)
    current = contextmap.map_digest(fake_speckit_repo)
    feature_dir = fake_speckit_repo / "specs" / "001-demo"
    data = {
        "feature": "001-demo", "branch": _branch(fake_speckit_repo),
        "baseline": _head(fake_speckit_repo), "current_phase": "REVIEW",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [{"id": "T001", "status": "DONE", "evidence": "CLI_LOG:ok",
                   "context_provenance": {"map": "present", "digest": "planning0digest",
                                          "context_ids": ["api"], "output_version": 1}}],
        "review_cycles": [{"round": 1, "started_at": "2026-07-05", "completed_at": None,
                           "result": None,
                           "context_provenance": {"map": "present", "digest": current,
                                                  "context_ids": ["api"], "output_version": 1}}],
    }
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    warning = review.digest_drift_warning(fake_speckit_repo)
    assert warning is not None and "planning0dig" in warning


# ---------------------------------------------------------------------------
# Feature 010 (T007) — the drift gate blocks only unexplained paths
# ---------------------------------------------------------------------------


def test_drift_gate_is_terminal_in_gate_order() -> None:
    assert review.GATE_ORDER[-1] == "drift"


def test_drift_gate_fails_on_unexplained_path(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/planned.py"],
                      changed={"src/planned.py": "x\n", "src/surprise.py": "y\n"})
    result = review._drift_gate(root)
    assert result.status == "FAIL"
    assert any("src/surprise.py" in d for d in result.detail)
    assert not any("src/planned.py" in d for d in result.detail)


def test_drift_gate_passes_when_all_planned(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/planned.py"], changed={"src/planned.py": "x\n"})
    assert review._drift_gate(root).status == "PASS"


def test_drift_gate_passes_on_acknowledged_path(trace_repo) -> None:
    from tests.conftest import make_task
    root = trace_repo(
        plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")],
        acks=[{"path": "src/disc.py", "task": "T001", "reason": "r",
               "map_digest": None, "at": "t"}],
        changed={"src/disc.py": "x\n"},
    )
    assert review._drift_gate(root).status == "PASS"


def test_review_evaluate_blocks_on_drift(trace_repo) -> None:
    # A declared plan path gives the gate a classification basis; the undeclared
    # src/surprise.py is then genuinely unexplained.
    root = trace_repo(plan_paths=["src/planned.py"],
                      changed={"src/planned.py": "x\n", "src/surprise.py": "y\n"})
    (root / "specops.json").write_text('{"test_command": "", "lint_command": ""}')
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "cfg"], cwd=root, check=True, capture_output=True)
    report = review.evaluate(root)
    drift = next(r for r in report.results if r.name == "drift")
    assert drift.status == "FAIL"
    assert not report.passed


def test_drift_gate_skipped_without_basis(trace_repo) -> None:
    # No plan path declarations, no map, no acknowledgements → the gate degrades
    # to SKIPPED instead of retroactively rejecting (Feature 010, Finding 6).
    root = trace_repo(plan_paths=[], changed={"src/surprise.py": "y\n"})
    assert review._drift_gate(root).status == "SKIPPED"
