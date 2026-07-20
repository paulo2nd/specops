"""Integration coverage for the `specops` workflow (Feature 007, US1).

A full end-to-end run of the workflow is intentionally NOT automated here: its
`command` steps dispatch real agent commands (specify/plan/implement) that need a
live integration/LLM, and its `gate` steps need an interactive TTY — neither is
CI-reproducible. Equivalent coverage is achieved by:

  * the static definition contract (native-only steps, readiness-gate position,
    no forward transition steps) — see also tests/unit/test_workflow_definition.py,
  * the behavior of the SpecOps CLI steps the workflow invokes (record-step,
    idempotent DONE transition), driven directly against a real ledger, and
  * a smoke test that the shipped definition parses in Spec Kit's own engine via
    `specify workflow info` (skipped when `specify` is not installed).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / "src" / "specops" / "templates" / "workflows" / "specops" / "workflow.yml"
)


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=repo, capture_output=True, text=True)


# --- C1: the workflow never duplicates directive-owned forward transitions -----

def test_workflow_has_no_forward_transition_or_initspec_steps() -> None:
    """The definition must not init-spec or issue forward-seam transitions — those
    are owned by the Principle IV directives. Only the final DONE is workflow-owned,
    and it is idempotent-tolerant (--if-needed)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "init-spec" not in text
    # Pure forward seams (PLAN/TASKS) are owned by the directives — never re-issued.
    for forward in ("transition-phase PLAN", "transition-phase TASKS"):
        assert forward not in text, f"workflow must not issue forward transition {forward!r}"
    # The only workflow-owned transitions are the corrective REVIEW→IMPLEMENT round
    # (no directive performs it) and the idempotent-tolerant final DONE.
    assert "transition-phase IMPLEMENT -r REJECTED --if-needed" in text
    assert "transition-phase DONE -r APPROVED --if-needed" in text
    # Any IMPLEMENT transition present must be the corrective (-r REJECTED) form.
    for line in text.splitlines():
        if "transition-phase IMPLEMENT" in line:
            assert "-r REJECTED" in line


# --- FR-006: the skip decision the workflow records lands in the ledger --------

def test_skip_decisions_recorded_in_ledger(fake_speckit_repo: Path) -> None:
    repo = fake_speckit_repo
    feature_dir = repo / "specs" / "001-demo"
    (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
    assert _run(repo, "status", "init-spec").returncode == 0

    assert _run(repo, "status", "record-step", "clarify", "--decision", "skip").returncode == 0
    assert _run(repo, "status", "record-step", "analyze", "--decision", "run").returncode == 0

    data = yaml.safe_load((feature_dir / "status.yaml").read_text())
    recorded = {s["step"]: s["decision"] for s in data["workflow"]["skipped_steps"]}
    assert recorded == {"clarify": "skip", "analyze": "run"}


# --- T014/SC-007: idempotent DONE transition survives a directive-advanced ledger

def test_done_transition_is_idempotent_when_already_done(fake_speckit_repo: Path) -> None:
    repo = fake_speckit_repo
    feature_dir = repo / "specs" / "001-demo"
    (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
    _run(repo, "status", "init-spec")
    # Walk to DONE the way the directives would.
    for target, extra in [("PLAN", []), ("TASKS", []), ("IMPLEMENT", []),
                          ("REVIEW", []), ("DONE", ["-r", "APPROVED"])]:
        assert _run(repo, "status", "transition-phase", target, *extra).returncode == 0

    # The workflow's own `done` step then runs — must be a clean no-op, not an error.
    r = _run(repo, "status", "transition-phase", "DONE", "-r", "APPROVED", "--if-needed")
    assert r.returncode == 0, r.stderr
    assert "no-op" in r.stdout


# --- Smoke: the shipped definition parses in Spec Kit's own engine -------------

@pytest.mark.skipif(shutil.which("specify") is None, reason="Spec Kit CLI not installed")
def test_definition_parses_in_real_speckit_engine() -> None:
    proc = subprocess.run(
        ["specify", "workflow", "info", str(WORKFLOW)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "specops" in proc.stdout
    # The readiness gate and the step graph are present.
    assert "readiness-gate" in proc.stdout
    assert re.search(r"Steps \(\d+\)", proc.stdout)
