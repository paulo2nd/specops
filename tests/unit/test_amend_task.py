"""`status amend-task` — the ledger's supported correction path (Feature 026, US1).

A task closed with wrong or missing evidence had no legal move: `start-task` refuses
to reopen it and `complete-task` refuses to write to it (#74), while hand-editing
`status.yaml` is forbidden by the workflow. Amendment closes that gap **append-only**:
the corrected value becomes current, the displaced records stay readable as superseded
history, and the operator's reason is recorded beside them. An amended task is *more*
informative than a silently-correct one — which is what stops amendment from being a
way to launder a bad close.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from specops import ledger
from specops import status as s
from specops.errors import LedgerParseError, SpecopsError
from tests.conftest import git, make_v1_ledger

REASON = "original close recorded no gate run; session terminated mid-flight"
GOOD = "TEST_REPORT:1795 passed, 0 failed"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _repo_with_done_task(tmp_path: Path, *, tasks_md: str = "- [ ] T001 do something\n",
                         evidence: str = "CLI_LOG:placeholder") -> tuple[Path, Path]:
    """A repo whose T001 is DONE with `evidence`, closed through the real command."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "t@t.com")
    git(root, "config", "user.name", "T")
    (root / "README.md").write_text("# test")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "init")

    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-test"})
    )
    feature_dir = root / "specs" / "001-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text(tasks_md)

    head = git(root, "rev-parse", "HEAD")
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    make_v1_ledger(feature_dir, feature="001-test", phase="IMPLEMENT",
                   baseline=head, branch=branch)

    s.cmd_start_task(root, "T001")
    s.cmd_complete_task(root, "T001", auto=False, evidence=evidence)
    return root, feature_dir


def _read(feature_dir: Path) -> dict:
    return yaml.safe_load((feature_dir / "status.yaml").read_text(encoding="utf-8"))


def _task(data: dict, tid: str = "T001") -> dict:
    return next(t for t in data["tasks"] if t["id"] == tid)


def _records(data: dict, task: dict) -> list[dict]:
    by_id = {r["id"]: r for r in data.get("evidence", [])}
    return [by_id[ref] for ref in task.get("evidence_refs", [])]


def _current(data: dict, task: dict) -> list[dict]:
    return [r for r in _records(data, task) if r.get("superseded_by") is None]


# ---------------------------------------------------------------------------
# T018 — the close-time facts are untouched
# ---------------------------------------------------------------------------

def test_amend_leaves_every_close_time_fact_untouched(tmp_path: Path) -> None:
    """FR-002: amendment corrects *evidence*, and nothing else about the close."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    before = _task(_read(feature_dir))

    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)

    after = _task(_read(feature_dir))
    assert after["status"] == "DONE"
    for field in ("completed_at", "commits", "started_commit", "context_provenance"):
        assert after[field] == before[field], f"{field} was modified by the amendment"


def test_amend_makes_the_correction_current(tmp_path: Path) -> None:
    """FR-002a: the amendment is what downstream reads."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)

    data = _read(feature_dir)
    task = _task(data)
    assert task["evidence"] == GOOD
    current = _current(data, task)
    assert len(current) == 1
    assert current[0]["summary"] == GOOD
    assert current[0]["amendment"] is True
    assert current[0]["reason"] == REASON
    assert current[0]["producer"] == "amend"


# ---------------------------------------------------------------------------
# T019 — append-only
# ---------------------------------------------------------------------------

def test_prior_record_survives_with_its_original_content(tmp_path: Path) -> None:
    """FR-002: the displaced record keeps its summary and timestamp verbatim."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    original = _records(_read(feature_dir), _task(_read(feature_dir)))[0]

    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)

    data = _read(feature_dir)
    kept = next(r for r in data["evidence"] if r["id"] == original["id"])
    assert kept["summary"] == original["summary"]
    assert kept["timestamp"] == original["timestamp"]
    assert kept["producer"] == original["producer"]
    assert kept["superseded_by"] is not None  # the only permitted change


def test_exactly_one_record_is_current_after_amendment(tmp_path: Path) -> None:
    root, feature_dir = _repo_with_done_task(tmp_path)
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)
    data = _read(feature_dir)
    assert len(_current(data, _task(data))) == 1


# ---------------------------------------------------------------------------
# T020 — repeated amendment
# ---------------------------------------------------------------------------

def test_amending_twice_retains_three_records(tmp_path: Path) -> None:
    """Acceptance scenario 2: an amendment never erases an earlier amendment."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    s.cmd_amend_task(root, "T001", evidence="TEST_REPORT:first pass", reason="first")
    s.cmd_amend_task(root, "T001", evidence="TEST_REPORT:second pass", reason="second")

    data = _read(feature_dir)
    task = _task(data)
    records = _records(data, task)
    assert len(records) == 3
    assert [r.get("superseded_by") is None for r in records] == [False, False, True]
    assert records[-1]["summary"] == "TEST_REPORT:second pass"
    assert records[-1]["reason"] == "second"
    assert records[1]["reason"] == "first"  # the displaced amendment keeps its reason


# ---------------------------------------------------------------------------
# T021 — the supersede is scoped to the task
# ---------------------------------------------------------------------------

def test_amendment_does_not_supersede_another_tasks_evidence(tmp_path: Path) -> None:
    """research D3: `append_record(supersede=True)` matches on *producer* across the
    whole ledger — semantics built for gate caching. Applied here it would reach into
    other tasks' records. The supersede must be scoped to this task's own refs."""
    root, feature_dir = _repo_with_done_task(
        tmp_path, tasks_md="- [ ] T001 first\n- [ ] T002 second\n"
    )
    s.cmd_start_task(root, "T002")
    s.cmd_complete_task(root, "T002", auto=False, evidence="CLI_LOG:t2 evidence")
    t2_before = _records(_read(feature_dir), _task(_read(feature_dir), "T002"))

    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)

    data = _read(feature_dir)
    t2_after = _records(data, _task(data, "T002"))
    assert t2_after == t2_before
    assert all(r.get("superseded_by") is None for r in t2_after)
    assert _task(data, "T002")["evidence"] == "CLI_LOG:t2 evidence"


# ---------------------------------------------------------------------------
# T022 — several current records are superseded together
# ---------------------------------------------------------------------------

def test_all_current_records_are_superseded_together(tmp_path: Path) -> None:
    """FR-002b: a task carrying several current records (a legacy string that expanded
    into multiple records on migration) never ends up with a mixed current/stale set."""
    root, feature_dir = _repo_with_done_task(
        tmp_path, evidence="TEST_REPORT:42 ok; CODE_DIFF:3 files"
    )
    data = _read(feature_dir)
    task = _task(data)
    # Simulate the migration shape: two current records, both referenced by the task.
    extra = dict(_records(data, task)[0])
    extra["id"] = "EV-secondcurrent"
    extra["summary"] = "CODE_DIFF:3 files"
    data["evidence"].append(extra)
    task["evidence_refs"] = task["evidence_refs"] + ["EV-secondcurrent"]
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    assert len(_current(_read(feature_dir), _task(_read(feature_dir)))) == 2

    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)

    data = _read(feature_dir)
    assert len(_current(data, _task(data))) == 1


# ---------------------------------------------------------------------------
# T023 — no per-record targeting
# ---------------------------------------------------------------------------

def test_amend_task_accepts_no_evidence_identifier(tmp_path: Path) -> None:
    """FR-002b: amendment is task-level. The operator's model is "this task's evidence
    is wrong", not "record EV-a3f1 is wrong" — and requiring an id would make recovery
    harder exactly when the operator is reconstructing state from wreckage."""
    import inspect
    params = set(inspect.signature(s.cmd_amend_task).parameters)
    assert "evidence_id" not in params
    assert params == {"root", "task_id", "evidence", "reason"}


def test_cli_exposes_no_evidence_id_option() -> None:
    from typer.testing import CliRunner

    from specops.cli import app
    out = CliRunner().invoke(app, ["status", "amend-task", "--help"]).output
    assert "--evidence-id" not in out


# ---------------------------------------------------------------------------
# T024 — the legacy-string safety net
# ---------------------------------------------------------------------------

def test_legacy_string_is_materialized_before_being_superseded(tmp_path: Path) -> None:
    """research D4: a current-schema ledger can carry a `DONE` task with an evidence
    string and no refs (hand-built, or hand-edited). The original wording must survive
    as a record — otherwise the amendment silently destroys the value it corrects."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    data = _read(feature_dir)
    task = _task(data)
    task["evidence_refs"] = []
    task["evidence"] = "CLI_LOG:the original wording"
    data["evidence"] = []
    (feature_dir / "status.yaml").write_text(yaml.dump(data))

    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)

    data = _read(feature_dir)
    summaries = [r["summary"] for r in data["evidence"]]
    assert "CLI_LOG:the original wording" in summaries
    assert GOOD in summaries
    assert len(_current(data, _task(data))) == 1


# ---------------------------------------------------------------------------
# T025 — identical evidence is still an amendment
# ---------------------------------------------------------------------------

def test_amending_with_identical_evidence_is_still_recorded(tmp_path: Path) -> None:
    """The operator's assertion that a correction occurred is itself the record —
    never silently dropped as a duplicate."""
    root, feature_dir = _repo_with_done_task(tmp_path, evidence=GOOD)
    before = len(_read(feature_dir)["evidence"])

    s.cmd_amend_task(root, "T001", evidence=GOOD, reason="re-verified by hand")

    data = _read(feature_dir)
    assert len(data["evidence"]) == before + 1
    current = _current(data, _task(data))[0]
    assert current["amendment"] is True and current["reason"] == "re-verified by hand"


# ---------------------------------------------------------------------------
# T026 — orphaned tasks
# ---------------------------------------------------------------------------

def test_orphaned_done_task_can_be_amended(tmp_path: Path) -> None:
    """An orphaned task's record is exactly the kind of residue that needs correcting."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T002 something else\n")  # T001 removed

    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)

    data = _read(feature_dir)
    task = _task(data)
    assert task.get("orphaned") is True
    assert task["evidence"] == GOOD


# ---------------------------------------------------------------------------
# T027 — the reason is recorded, never judged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reason", ["x", "asdf", "because", "  padded  ", "1"])
def test_any_non_empty_reason_is_accepted_verbatim(tmp_path: Path, reason: str) -> None:
    """FR-007 (Principle IV): SpecOps records, it does not validate. A low-quality
    reason is a *recorded* low-quality reason — visible, and therefore reviewable."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=reason)
    data = _read(feature_dir)
    assert _current(data, _task(data))[0]["reason"] == reason


# ---------------------------------------------------------------------------
# T028 — the recovery-only restriction is instructional, never mechanical
# ---------------------------------------------------------------------------

def test_a_task_closed_in_this_run_can_still_be_amended(tmp_path: Path) -> None:
    """FR-023/FR-026: SpecOps has no notion of "which session" closed a task and will
    not acquire one. The directives restrict amendment to recovery; the ledger's
    defence is that every amendment is recorded with its reason, not a refusal."""
    root, feature_dir = _repo_with_done_task(tmp_path)  # closed moments ago, same process
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason="changed my mind")
    assert _task(_read(feature_dir))["evidence"] == GOOD


# ---------------------------------------------------------------------------
# T029 — refusals (exit 1), nothing written
# ---------------------------------------------------------------------------

def test_unknown_task_is_refused(tmp_path: Path) -> None:
    root, feature_dir = _repo_with_done_task(tmp_path)
    before = (feature_dir / "status.yaml").read_bytes()
    with pytest.raises(SpecopsError, match="T099"):
        s.cmd_amend_task(root, "T099", evidence=GOOD, reason=REASON)
    assert (feature_dir / "status.yaml").read_bytes() == before


@pytest.mark.parametrize("status", ["PENDING", "IN_PROGRESS"])
def test_task_not_done_is_refused(tmp_path: Path, status: str) -> None:
    """Acceptance scenario 3: the refusal names the command for that state."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    data = _read(feature_dir)
    _task(data)["status"] = status
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    before = (feature_dir / "status.yaml").read_bytes()

    with pytest.raises(SpecopsError) as exc:
        s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)
    assert "not DONE" in exc.value.message
    assert ("start-task" in exc.value.message or "complete-task" in exc.value.message)
    assert (feature_dir / "status.yaml").read_bytes() == before


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_missing_reason_is_refused(tmp_path: Path, reason: str | None) -> None:
    root, feature_dir = _repo_with_done_task(tmp_path)
    before = (feature_dir / "status.yaml").read_bytes()
    with pytest.raises(SpecopsError, match="[Rr]eason"):
        s.cmd_amend_task(root, "T001", evidence=GOOD, reason=reason)
    assert (feature_dir / "status.yaml").read_bytes() == before


@pytest.mark.parametrize("bad", ["", "nonsense", "BAD_CLASS: x", "CLI_LOG:", "no colon"])
def test_invalid_evidence_grammar_is_refused(tmp_path: Path, bad: str) -> None:
    root, feature_dir = _repo_with_done_task(tmp_path)
    before = (feature_dir / "status.yaml").read_bytes()
    with pytest.raises(SpecopsError, match="[Ee]vidence"):
        s.cmd_amend_task(root, "T001", evidence=bad, reason=REASON)
    assert (feature_dir / "status.yaml").read_bytes() == before


def test_refusals_are_checked_before_any_read(tmp_path: Path) -> None:
    """FR-005: argument validation precedes the ledger read, so a bad invocation fails
    identically whether or not the ledger is even loadable."""
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(SpecopsError, match="[Rr]eason"):
        s.cmd_amend_task(root, "T001", evidence=GOOD, reason="")


# ---------------------------------------------------------------------------
# T030 — infrastructure failures exit 2, not 1
# ---------------------------------------------------------------------------

def test_unparseable_ledger_raises_exit_2(tmp_path: Path) -> None:
    root, feature_dir = _repo_with_done_task(tmp_path)
    (feature_dir / "status.yaml").write_text("{[not: valid yaml")
    with pytest.raises(LedgerParseError) as exc:
        s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)
    assert exc.value.exit_code == 2


def test_outside_a_git_repository_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "nogit"
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-test"})
    )
    feature_dir = root / "specs" / "001-test"
    feature_dir.mkdir(parents=True)
    make_v1_ledger(feature_dir, feature="001-test")
    with pytest.raises(SpecopsError):
        s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)


# ---------------------------------------------------------------------------
# T031 — DONE is terminal
# ---------------------------------------------------------------------------

def test_amendment_never_reopens_the_task(tmp_path: Path) -> None:
    """FR-003: amendment-only is deliberately chosen over reopening, so a bad close
    cannot be quietly laundered into a good one."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)
    data = _read(feature_dir)
    assert _task(data)["status"] == "DONE"
    assert data["recovery"]["active_task"] is None
    with pytest.raises(SpecopsError, match="already DONE"):
        s.cmd_start_task(root, "T001")


# ---------------------------------------------------------------------------
# T032 — reconcile accepts the amended ledger
# ---------------------------------------------------------------------------

def test_reconcile_accepts_an_amended_ledger(tmp_path: Path) -> None:
    """FR-008: an amendment must not introduce a state the integrity check rejects."""
    from specops import reconcile as rec

    root, feature_dir = _repo_with_done_task(tmp_path)
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)
    warnings, violations = rec.run(root)
    assert violations == []


def test_amended_ledger_passes_invariants(tmp_path: Path) -> None:
    root, feature_dir = _repo_with_done_task(tmp_path)
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason=REASON)
    assert ledger.validate_invariants(_read(feature_dir)) == []


def test_amendment_is_idempotent_in_shape_not_content(tmp_path: Path) -> None:
    """Running it twice records two amendments (each is an operator assertion) while
    the ledger stays structurally valid — idempotency here is about validity, not
    about collapsing distinct corrections."""
    root, feature_dir = _repo_with_done_task(tmp_path)
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason="first")
    s.cmd_amend_task(root, "T001", evidence=GOOD, reason="second")
    data = _read(feature_dir)
    assert ledger.validate_invariants(data) == []
    assert len(_current(data, _task(data))) == 1
