"""Unit tests for Feature 011 — Structured Corrective Handoff (handoff.py)."""
from __future__ import annotations

import json

from specops import handoff, outcome, trace
from tests.conftest import head_commit, make_cycle, make_finding, make_task, read_ledger

FEATURE_DIR = "specs/001-demo"


def _fd(root):
    return root / FEATURE_DIR


# ---------------------------------------------------------------------------
# US1 — record a resumable corrective handoff
# ---------------------------------------------------------------------------


def test_finding_add_records_stable_id(handoff_repo) -> None:
    root = handoff_repo()
    res = handoff.cmd_finding_add(
        root, severity="blocking", rule="L2", file="src/a.py", line=42,
        action="fix guard", expected_evidence="a test", closure="test passes")
    assert res.status == handoff.FINDING_RECORDED
    assert res.exit_code == 0
    assert res.extra["id"] == "R1-F01"
    led = read_ledger(_fd(root))
    f = led["review_cycles"][-1]["handoff"]["findings"][0]
    assert f["id"] == "R1-F01" and f["state"] == "OPEN" and f["severity"] == "blocking"
    assert f["file"] == "src/a.py" and f["line"] == 42


def test_finding_id_sequence_and_stability(handoff_repo) -> None:
    root = handoff_repo()
    a = handoff.cmd_finding_add(root, severity="advisory", rule="x", file="a.py",
                                line=1, action="a", expected_evidence="", closure="")
    b = handoff.cmd_finding_add(root, severity="blocking", rule="y", file="b.py",
                                line=2, action="b", expected_evidence="e", closure="c")
    assert (a.extra["id"], b.extra["id"]) == ("R1-F01", "R1-F02")
    # ids are stable across a reload (append-order, never renumbered)
    ids = [f["id"] for f in read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"]]
    assert ids == ["R1-F01", "R1-F02"]


def test_finding_add_blocking_requires_closure(handoff_repo) -> None:
    root = handoff_repo()
    res = handoff.cmd_finding_add(root, severity="blocking", rule="x", file="a.py",
                                  line=1, action="a", expected_evidence="", closure="")
    assert res.status == handoff.BAD_ARGS and res.exit_code == 2
    # nothing recorded (no handoff created)
    assert "handoff" not in read_ledger(_fd(root))["review_cycles"][-1]


def test_finding_add_invalid_severity(handoff_repo) -> None:
    root = handoff_repo()
    res = handoff.cmd_finding_add(root, severity="critical", rule="x", file="a.py",
                                  line=1, action="a", expected_evidence="e", closure="c")
    assert res.status == handoff.BAD_ARGS and res.exit_code == 2


def test_advisory_optional_closure_and_line(handoff_repo) -> None:
    root = handoff_repo()
    res = handoff.cmd_finding_add(root, severity="advisory", rule="x", file="a.py",
                                  line=None, action="a", expected_evidence="", closure="")
    assert res.status == handoff.FINDING_RECORDED
    f = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"][0]
    assert f["line"] is None and f["closure_criteria"] is None


def test_authorize_records_normalized_paths(handoff_repo) -> None:
    root = handoff_repo()
    res = handoff.cmd_authorize(root, ["./src/handoff.py", "src/handoff.py"])
    assert res.status == handoff.HANDOFF_AUTHORIZED
    paths = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["authorized_paths"]
    assert paths == ["src/handoff.py"]  # normalized + deduped


def test_zero_findings_means_no_handoff_key(handoff_repo) -> None:
    root = handoff_repo()
    assert "handoff" not in read_ledger(_fd(root))["review_cycles"][-1]


def test_resumability_roundtrip(handoff_repo) -> None:
    root = handoff_repo()
    handoff.cmd_finding_add(root, severity="blocking", rule="L2", file="a.py", line=7,
                            action="do", expected_evidence="a test", closure="passes")
    handoff.cmd_authorize(root, ["a.py"])
    # A fresh read reconstructs everything from repository state alone.
    f = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]
    assert f["authorized_paths"] == ["a.py"]
    fnd = f["findings"][0]
    assert fnd["expected_evidence"] == "a test" and fnd["closure_criteria"] == "passes"


# ---------------------------------------------------------------------------
# US2 — lifecycle + approval + close
# ---------------------------------------------------------------------------


def _repo_with_open_finding(handoff_repo, **finding_kw):
    fnd = make_finding("R1-F01", **finding_kw)
    return handoff_repo(
        tasks=[make_task("T001")],
        review_cycles=[make_cycle(findings=[fnd])],
    )


def test_fix_open_to_fixed(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo)
    sha = head_commit(root)
    res = handoff.cmd_finding_fix(root, "R1-F01", task="T001", commits=[sha],
                                  evidence="TEST_REPORT:guard", auto=False)
    assert res.status == handoff.FINDING_FIXED
    f = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"][0]
    assert f["state"] == "FIXED" and f["task"] == "T001" and f["commits"] == [sha]
    assert f["evidence"] == "TEST_REPORT:guard"


def test_fix_requires_commit_and_evidence(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo)
    res = handoff.cmd_finding_fix(root, "R1-F01", task="T001", commits=[],
                                  evidence="CLI_LOG:x", auto=False)
    assert res.status == handoff.PRECONDITION_UNMET and res.exit_code == 2
    assert read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"][0]["state"] == "OPEN"


def test_fix_unknown_task(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo)
    res = handoff.cmd_finding_fix(root, "R1-F01", task="T999", commits=["a"],
                                  evidence="CLI_LOG:x", auto=False)
    assert res.status == handoff.UNKNOWN_TASK and res.exit_code == 2


def test_fix_unknown_finding(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo)
    res = handoff.cmd_finding_fix(root, "R9-F99", task="T001", commits=["a"],
                                  evidence="CLI_LOG:x", auto=False)
    assert res.status == handoff.UNKNOWN_FINDING and res.exit_code == 2


def test_fix_illegal_from_fixed(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo, state="FIXED", task="T001",
                                   commits=["a"], evidence="CLI_LOG:x")
    res = handoff.cmd_finding_fix(root, "R1-F01", task="T001", commits=["b"],
                                  evidence="CLI_LOG:y", auto=False)
    assert res.status == handoff.ILLEGAL_TRANSITION and res.exit_code == 2


def test_verify_fixed_to_verified(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo, state="FIXED", task="T001",
                                   commits=["a"], evidence="CLI_LOG:x")
    res = handoff.cmd_finding_verify(root, "R1-F01")
    assert res.status == handoff.FINDING_VERIFIED
    st = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"][0]["state"]
    assert st == "VERIFIED"


def test_verify_from_open_is_illegal(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo)
    res = handoff.cmd_finding_verify(root, "R1-F01")
    assert res.status == handoff.ILLEGAL_TRANSITION and res.exit_code == 2


def test_verify_requires_evidence(handoff_repo) -> None:
    # a FIXED finding with links but no evidence fails the mechanical precondition
    root = _repo_with_open_finding(handoff_repo, state="FIXED", task="T001",
                                   commits=["a"], evidence=None)
    res = handoff.cmd_finding_verify(root, "R1-F01")
    assert res.status == handoff.PRECONDITION_UNMET and res.exit_code == 2


def test_blocking_approval_check_feature_global() -> None:
    data = {"review_cycles": [
        make_cycle(round=1, findings=[make_finding("R1-F01", state="VERIFIED", task="T",
                                                    commits=["a"], evidence="CLI_LOG:x")]),
        make_cycle(round=2, findings=[make_finding("R2-F01", state="OPEN")]),
    ]}
    assert handoff.blocking_approval_check(data) == ["R2-F01"]


def test_blocking_approval_check_all_verified_or_advisory() -> None:
    data = {"review_cycles": [make_cycle(findings=[
        make_finding("R1-F01", severity="advisory", state="OPEN"),
        make_finding("R1-F02", severity="blocking", state="VERIFIED", task="T",
                     commits=["a"], evidence="CLI_LOG:x"),
    ])]}
    assert handoff.blocking_approval_check(data) == []


def test_close_blocked_then_closed_then_idempotent(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo, state="FIXED", task="T001",
                                   commits=["a"], evidence="CLI_LOG:x")
    blocked = handoff.cmd_close(root)
    assert blocked.status == handoff.CLOSE_BLOCKED and blocked.exit_code == 1
    handoff.cmd_finding_verify(root, "R1-F01")
    closed = handoff.cmd_close(root)
    assert closed.status == handoff.HANDOFF_CLOSED
    again = handoff.cmd_close(root)
    assert again.status == handoff.HANDOFF_ALREADY_CLOSED and again.exit_code == 0


# ---------------------------------------------------------------------------
# US3 — validation + report
# ---------------------------------------------------------------------------


def test_validate_clean(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo)
    assert handoff.cmd_validate(root).status == handoff.VALIDATE_OK


def test_validate_missing_closure(handoff_repo) -> None:
    fnd = make_finding("R1-F01", severity="blocking", closure=None, expected_evidence=None)
    root = handoff_repo(review_cycles=[make_cycle(findings=[fnd])])
    res = handoff.cmd_validate(root)
    assert res.status == handoff.MISSING_CLOSURE and res.exit_code == 1


def test_validate_contradictory_verified_without_evidence(handoff_repo) -> None:
    root = handoff_repo(tasks=[make_task("T001")], review_cycles=[make_cycle()])
    sha = head_commit(root)
    led = read_ledger(_fd(root))
    led["review_cycles"][-1]["handoff"] = {"authorized_paths": [], "closed_at": None,
        "findings": [make_finding("R1-F01", state="VERIFIED", task="T001",
                              commits=[sha], evidence=None)]}
    import yaml
    (_fd(root) / "status.yaml").write_text(yaml.dump(led))
    res = handoff.cmd_validate(root)
    assert res.status == handoff.CONTRADICTORY_STATE and res.exit_code == 1


def test_validate_dangling_task(handoff_repo) -> None:
    fnd = make_finding("R1-F01", state="FIXED", task="T999", commits=["a"], evidence="CLI_LOG:x")
    root = handoff_repo(review_cycles=[make_cycle(findings=[fnd])])
    res = handoff.cmd_validate(root)
    assert res.status == handoff.DANGLING_REFERENCE and res.exit_code == 1


def test_validate_shares_structural_checks_with_ledger_invariant(handoff_repo) -> None:
    # An invalid severity is a structural defect: both the write-time invariant
    # and `handoff validate` now report it from the shared source of truth.
    from specops import ledger
    fnd = make_finding("R1-F01", severity="critical")
    root = handoff_repo(review_cycles=[make_cycle(findings=[fnd])])
    data = read_ledger(_fd(root))
    kinds = {k for k, _ in ledger.finding_structural_defects(data)}
    assert ledger.FINDING_DEFECT_SEVERITY in kinds
    res = handoff.cmd_validate(root)
    assert res.exit_code == 1  # validate no longer silently passes a malformed finding


def test_validate_duplicate_id(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(findings=[
        make_finding("R1-F01"), make_finding("R1-F01", file="b.py"),
    ])])
    res = handoff.cmd_validate(root)
    assert res.status == handoff.DUPLICATE_ID and res.exit_code == 1


def test_report_parity_and_remaining(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(findings=[
        make_finding("R1-F01", severity="blocking", state="OPEN"),
        make_finding("R1-F02", severity="advisory", state="OPEN"),
    ])])
    res = handoff.cmd_report(root)
    assert res.status == handoff.REPORT_OK
    assert [f["id"] for f in res.extra["findings"]] == ["R1-F01", "R1-F02"]  # blocking first
    assert res.extra["remaining_blocking"] == ["R1-F01"]


def test_report_deterministic_and_readonly(handoff_repo) -> None:
    root = _repo_with_open_finding(handoff_repo)
    before = read_ledger(_fd(root))
    a = outcome.render("handoff report", handoff.cmd_report(root).cls,
                       status=handoff.REPORT_OK, output_version=handoff.OUTPUT_VERSION,
                       **handoff.cmd_report(root).extra)
    b = outcome.render("handoff report", handoff.cmd_report(root).cls,
                       status=handoff.REPORT_OK, output_version=handoff.OUTPUT_VERSION,
                       **handoff.cmd_report(root).extra)
    assert a == b and json.loads(a)["output_version"] == 1
    assert read_ledger(_fd(root)) == before  # read-only


# ---------------------------------------------------------------------------
# US4 — render + trace re-source + import
# ---------------------------------------------------------------------------


def test_render_revision_text_canonical() -> None:
    data = {"review_cycles": [make_cycle(round=1, findings=[
        make_finding("R1-F02", severity="advisory", file="z.py", line=1, action="minor"),
        make_finding("R1-F01", severity="blocking", file="a.py", line=9, action="fix it"),
    ])]}
    text = handoff.render_revision_text(data, 1)
    assert text == "a.py:9 - fix it\nz.py:1 - minor\n"  # blocking first (canonical)


def test_render_zero_findings_is_approved() -> None:
    data = {"review_cycles": [make_cycle(round=1, findings=[])]}
    assert handoff.render_revision_text(data, 1) == "APPROVED\n"


def test_trace_resources_structured_findings_with_ids(handoff_repo) -> None:
    fnd = make_finding("R1-F01", file="a.py", line=3, action="do")
    root = handoff_repo(review_cycles=[make_cycle(findings=[fnd])])
    graph = trace.build_graph(root)
    assert graph["findings"] == [{"id": "R1-F01", "file": "a.py", "line": 3,
                                  "text": "do", "round": 1}]


def test_trace_falls_back_to_legacy_prose(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])  # no handoff
    (_fd(root) / "revisions").mkdir()
    (_fd(root) / "revisions" / "revision-1.md").write_text("a.py:5 - legacy note\n")
    graph = trace.build_graph(root)
    assert graph["findings"] == [{"file": "a.py", "line": 5, "text": "legacy note", "round": 1}]


def test_trace_merges_legacy_and_structured_rounds(handoff_repo) -> None:
    # round 1 is legacy prose; round 2 is structured — both must appear.
    root = handoff_repo(review_cycles=[
        make_cycle(round=1, result="REJECTED"),
        make_cycle(round=2, findings=[make_finding("R2-F01", file="b.py", line=3, action="do")]),
    ])
    (_fd(root) / "revisions").mkdir()
    (_fd(root) / "revisions" / "revision-1.md").write_text("a.py:5 - legacy note\n")
    rounds = {f["round"] for f in trace.build_graph(root)["findings"]}
    assert rounds == {1, 2}  # legacy round 1 no longer dropped


# ---------------------------------------------------------------------------
# Code-review fixes (regression guards)
# ---------------------------------------------------------------------------


def test_render_refuses_round_without_handoff_preserving_legacy(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])  # no handoff on round 1
    rev = _fd(root) / "revisions"
    rev.mkdir()
    (rev / "revision-1.md").write_text("a.py:5 - real non-conformity\n")
    res = handoff.render_revision(root, 1)
    assert res.status == handoff.BAD_ARGS and res.exit_code == 2
    # legacy prose untouched — not overwritten with APPROVED
    assert (rev / "revision-1.md").read_text() == "a.py:5 - real non-conformity\n"


def test_dismiss_unblocks_approval(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(findings=[make_finding("R1-F01")])])
    res = handoff.cmd_finding_dismiss(root, "R1-F01", reason="false positive")
    assert res.status == handoff.FINDING_DISMISSED
    f = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"][0]
    assert f["state"] == "DISMISSED" and f["dismiss_reason"] == "false positive"
    assert handoff.blocking_approval_check(read_ledger(_fd(root))) == []


def test_dismiss_requires_reason_and_rejects_verified(handoff_repo) -> None:
    fnd = make_finding("R1-F01", state="VERIFIED", task="T001", commits=["a"],
                       evidence="CLI_LOG:x")
    root = handoff_repo(review_cycles=[make_cycle(findings=[fnd])])
    assert handoff.cmd_finding_dismiss(root, "R1-F01", reason="").status == handoff.BAD_ARGS
    r = handoff.cmd_finding_dismiss(root, "R1-F01", reason="x")
    assert r.status == handoff.ILLEGAL_TRANSITION


def test_import_is_idempotent(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    (_fd(root) / "revisions").mkdir()
    (_fd(root) / "revisions" / "revision-1.md").write_text("a.py:5 - note\n")
    assert handoff.cmd_import(root, None).extra["imported"] == 1
    assert handoff.cmd_import(root, None).extra["imported"] == 0  # no duplicates
    findings = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"]
    assert len(findings) == 1


def test_add_refused_after_close(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(
        findings=[make_finding("R1-F01", severity="advisory")],
        closed_at="2026-07-23T00:00:00+00:00")])
    res = handoff.cmd_finding_add(root, severity="blocking", rule="x", file="b.py",
                                  line=1, action="a", expected_evidence="e", closure="c")
    assert res.status == handoff.BAD_ARGS and "closed" in res.human


def test_fix_auto_uses_task_recorded_commits(handoff_repo) -> None:
    root = handoff_repo(
        tasks=[make_task("T001", commits=["sha-scoped"])],
        review_cycles=[make_cycle(findings=[make_finding("R1-F01")])])
    res = handoff.cmd_finding_fix(root, "R1-F01", task="T001", commits=[],
                                  evidence=None, auto=True)
    assert res.status == handoff.FINDING_FIXED
    f = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"][0]
    assert f["commits"] == ["sha-scoped"]  # task's own commits, not a HEAD range


def test_blocking_approval_check_skips_finding_without_id() -> None:
    bad = make_finding("x", severity="blocking", state="OPEN")
    del bad["id"]
    data = {"review_cycles": [make_cycle(findings=[bad])]}
    assert handoff.blocking_approval_check(data) == []  # no crash, skipped


def test_lineless_finding_render_import_roundtrip(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(round=1, findings=[
        make_finding("R1-F01", file="a.py", line=None, action="file-level issue")])])
    text = handoff.render_revision_text(read_ledger(_fd(root)), 1)
    assert text == "a.py - file-level issue\n"
    # the rendered line-less form is re-parseable
    m = trace._FINDING_RE.match(text.strip())
    assert m and m.group("file") == "a.py" and m.group("line") is None


def test_import_legacy_prose(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    (_fd(root) / "revisions").mkdir()
    (_fd(root) / "revisions" / "revision-1.md").write_text(
        "src/x.py:12 - do the thing\nAPPROVED\n")
    res = handoff.cmd_import(root, None)
    assert res.status == handoff.FINDING_RECORDED and res.extra["imported"] == 1
    f = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"][0]
    assert f["severity"] == "advisory" and f["file"] == "src/x.py" and f["line"] == 12
    assert f["action"] == "do the thing" and f["state"] == "OPEN"
