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
    """Config + ledger (baseline = pre-setup HEAD) committed → clean tree, effective diff."""
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
    assert "SKIPPED" not in out
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

    monkeypatch.setattr(review.subprocess, "run", _forbidden)
    with pytest.raises(SpecopsError) as exc:
        review.run_gates(root)
    msg = str(exc.value)
    assert "not in branch history" in msg
    assert "[gate] lint" not in msg


def test_reconcile_warning_echoed_and_gate_passes(fake_speckit_repo: Path) -> None:
    root = fake_speckit_repo
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
    real_run = review.subprocess.run
    calls: list[str] = []

    def _spy(cmd, **kwargs):
        calls.append(cmd)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(review.subprocess, "run", _spy)
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
