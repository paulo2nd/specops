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

from specops import extension, handoff, speckit
from specops import status as s
from specops.errors import SpecopsError
from tests.conftest import cli, head_commit, make_cycle, make_task

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / "src" / "specops" / "templates" / "workflows" / "specops" / "workflow.yml"
)


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return cli(repo, *args)


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


# --- US4 (SC-006/SC-007): outcome classes are distinct; read-only gates ---------

def test_readonly_json_gates_do_not_mutate_the_ledger(fake_speckit_repo: Path) -> None:
    """An execution/infra failure during a read-only gate never advances the ledger
    or records a rejection (SC-007) — the gates are non-mutating."""
    repo = fake_speckit_repo
    fd = repo / "specs" / "001-demo"
    (fd / "tasks.md").write_text("- [ ] T001 task\n")
    (fd / "spec.md").write_text("# spec\n")
    _run(repo, "status", "init-spec")
    before = (fd / "status.yaml").read_bytes()

    _run(repo, "reconcile", "--json")
    _run(repo, "review", "--json")  # no specops.json → infra-error, but read-only

    assert (fd / "status.yaml").read_bytes() == before  # no mutation of ledger


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


# --- Feature 016 -------------------------------------------------------------
#
# The composed semantic review (`command: specops.review`) needs a live agent and
# is not CI-reproducible; the tests below cover the CLI primitives the composition
# relies on, so SC-002/SC-004/SC-008 and FR-009/FR-011 are evidenced without an
# agent (spec Assumptions).


def _flatten_steps(steps: list[dict]) -> list[dict]:
    out: list[dict] = []
    for step in steps:
        out.append(step)
        for key in ("then", "else", "steps"):
            nested = step.get(key)
            if isinstance(nested, list):
                out.extend(_flatten_steps(nested))
    return out


def test_semantic_review_composed_adds_no_new_transition() -> None:
    """FR-009: composing the semantic review must not add a workflow-issued
    transition — the `command: specops.review` step issues its owned transitions at
    runtime, not in the yaml. The only workflow-owned transitions stay the
    corrective IMPLEMENT -r REJECTED and the idempotent DONE.

    Asserted over the PARSED step definitions (not a raw whole-file text scan) so a
    comment-only documentation edit cannot flip the result either way."""
    steps = _flatten_steps(yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["steps"])
    commands = [s["command"] for s in steps if isinstance(s.get("command"), str)]
    runs = [s["run"] for s in steps if isinstance(s.get("run"), str)]

    assert "specops.review" in commands  # the semantic review IS composed as a step

    # Every IMPLEMENT transition step remains the corrective form; exactly one DONE.
    for run in runs:
        if "transition-phase IMPLEMENT" in run:
            assert "-r REJECTED" in run
    done = [r for r in runs if "transition-phase DONE" in r]
    assert len(done) == 1 and "--if-needed" in done[0]  # only the idempotent `done`


def test_terminal_done_fails_closed_on_unverified_blocking(handoff_repo) -> None:
    """SC-002/FR-004/FR-005: the workflow's `done` step form
    (`transition-phase DONE -r APPROVED --if-needed`) cannot complete while a
    blocking finding is unverified; once the finding is verified it succeeds."""
    root = handoff_repo(tasks=[make_task("T001")], review_cycles=[make_cycle()])

    add = handoff.cmd_finding_add(
        root, severity="blocking", rule="L2", file="src/a.py", line=7,
        action="fix it", expected_evidence="a unit test", closure="the test passes",
    )
    assert add.status == handoff.FINDING_RECORDED

    # `--if-needed` (the actual workflow step) still hits the blocking gate.
    with pytest.raises(SpecopsError, match="unverified blocking"):
        s.cmd_transition_phase(root, "DONE", result="APPROVED", if_needed=True)

    # Resolve the finding the way a corrective round does, then verify it.
    handoff.cmd_finding_fix(
        root, "R1-F01", task="T001", commits=[head_commit(root)],
        evidence="CLI_LOG:fixed", auto=False,
    )
    assert handoff.cmd_finding_verify(root, "R1-F01").status == handoff.FINDING_VERIFIED

    # Now the same terminal step reaches DONE.
    msg = s.cmd_transition_phase(root, "DONE", result="APPROVED", if_needed=True)
    assert "DONE" in msg


def test_findings_signal_is_derived_from_persisted_state(handoff_repo, tmp_path: Path) -> None:
    """FR-011 (resumability, CI-verifiable half): the loop's findings signal
    (`handoff report` remaining_blocking) is a pure function of the PERSISTED
    ledger. A fresh invocation over an independent on-disk copy of the repository —
    sharing no in-process state — re-derives the same non-empty set, which is what
    lets `specify workflow resume` re-run the shell step and recover the signal
    from the ledger rather than in-memory step context. (The engine's own resume
    mechanism is Spec Kit's; this proves our step's output travels via the ledger.)"""
    root = handoff_repo(review_cycles=[make_cycle()])
    handoff.cmd_finding_add(
        root, severity="blocking", rule="L2", file="src/a.py", line=7,
        action="fix it", expected_evidence="a unit test", closure="the test passes",
    )
    original = handoff.cmd_report(root).extra["remaining_blocking"]
    assert original == ["R1-F01"]  # recorded and reported

    # Independent invocation: a byte-for-byte copy of the repo, read with a fresh
    # root — no in-process handoff state is shared with the original.
    resumed_root = tmp_path / "resumed"
    shutil.copytree(root, resumed_root)
    resumed = handoff.cmd_report(resumed_root).extra["remaining_blocking"]
    assert resumed == original  # signal survives via the persisted ledger, non-empty


def test_no_findings_degrades_and_report_is_read_only(handoff_repo) -> None:
    """SC-004/FR-006: a run with no findings has an empty remaining_blocking
    (completion falls to the mechanical verdict) and `handoff report` never mutates
    the ledger."""
    root = handoff_repo(review_cycles=[make_cycle()])  # no findings → no handoff
    fd = root / "specs" / "001-demo"
    before = (fd / "status.yaml").read_bytes()

    report = handoff.cmd_report(root)
    assert report.extra["remaining_blocking"] == []  # auto-degrade signal
    assert (fd / "status.yaml").read_bytes() == before  # read-only


def test_review_command_is_co_installed_with_the_workflow(fake_speckit_repo: Path) -> None:
    """FR-016: `install()` writes the `/specops-review` command wherever it writes
    the workflow, so the hard `command: specops.review` step can never silently
    degrade — an unavailable review aborts the run (fail closed)."""
    root = fake_speckit_repo
    extension.install(root)

    assert (root / ".specify" / "workflows" / "specops" / "workflow.yml").is_file()
    targets = speckit.review_command_targets(root)
    assert targets, "expected at least one integration to register the review command"
    for t in targets:
        assert t["review_path"].is_file(), f"review command missing for {t['integration']}"
