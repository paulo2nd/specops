"""Unit tests for Feature 011 — Structured Corrective Handoff (handoff.py)."""
from __future__ import annotations

import json

from specops import findings, handoff, outcome, trace
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


def test_command_name_single_source_no_body_drift(handoff_repo, tmp_path_factory) -> None:
    """The command label on the decorator's not-a-repo refusal and on a body-level
    error derive from the SAME source (the decorator argument), so the two paths can
    never report different names for one command — the drift the duplicated literal
    invited. cmd_close reaches a body error (no handoff to close) on a fresh repo."""
    body_err = handoff.cmd_close(handoff_repo())
    assert body_err.status == handoff.BAD_ARGS  # body path, not the decorator's refusal

    # An isolated dir NOT nested under the fixture's git repo, so find_repo returns None.
    non_repo = tmp_path_factory.mktemp("non_repo")
    (non_repo / ".specify").mkdir()
    (non_repo / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"}))
    (non_repo / "specs" / "001-demo").mkdir(parents=True)
    refusal = handoff.cmd_close(non_repo)  # not a Git repo -> decorator conversion

    assert refusal.status == handoff.NOT_A_REPO
    assert refusal.command == body_err.command == "handoff close"


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
    # rich header + counts + per-finding block
    assert text.startswith("# Review — Round 1")
    assert "**Verdict:** REJECTED" in text  # an OPEN blocking finding
    assert "**Findings:** 1 blocking · 1 advisory" in text
    assert "### R1-F01 · OPEN · `a.py:9`" in text
    # 010-compat flat appendix, blocking first (canonical), at the end
    assert text.rstrip().endswith("a.py:9 - fix it\nz.py:1 - minor")


def test_render_zero_findings_is_approved() -> None:
    data = {"review_cycles": [make_cycle(round=1, findings=[])]}
    text = handoff.render_revision_text(data, 1)
    assert "**Verdict:** APPROVED" in text
    assert "**Findings:** 0 blocking · 0 advisory · " \
           "**Remaining blocking (this round):** none" in text
    assert text.rstrip().endswith("APPROVED")  # flat appendix still says APPROVED


def test_render_multiline_field_stays_import_inert() -> None:
    # a finding field carrying a newline + finding-shaped text must not inject a
    # spurious finding on import — every rich line stays single-line (code-review #64)
    from specops import findings as findings_mod
    evil = "do this\nsrc/evil.py:99 - handle the edge case"
    data = {"review_cycles": [make_cycle(round=1, findings=[
        make_finding("R1-F01", severity="blocking", file="src/x.py", line=42,
                     action="fix it", closure=evil)])]}
    text = handoff.render_revision_text(data, 1)
    parsed = [p for p in (findings_mod.parse_finding_line(ln) for ln in text.splitlines())
              if p is not None]
    assert parsed == [{"file": "src/x.py", "line": 42, "action": "fix it"}]  # only the flat line


def test_render_remaining_blocking_is_round_scoped() -> None:
    # round 2 has only a VERIFIED blocking finding; round 1 has an OPEN blocker.
    # revision-2.md must not claim round-1's blocker (no self-contradiction).
    data = {"review_cycles": [
        make_cycle(round=1, findings=[make_finding("R1-F05", severity="blocking", state="OPEN")]),
        make_cycle(round=2, findings=[make_finding(
            "R2-F01", severity="blocking", state="VERIFIED", task="T1",
            commits=["a"], evidence="TEST:ok")]),
    ]}
    text = handoff.render_revision_text(data, 2)
    assert "**Verdict:** APPROVED" in text          # this round's blocker is resolved
    assert "**Remaining blocking (this round):** none" in text
    assert "R1-F05" not in text                      # a foreign-round id never appears


def test_render_revision_rich_fields_and_range() -> None:
    cycle = make_cycle(round=2, result="REJECTED", findings=[
        make_finding("R2-F01", severity="blocking", state="OPEN", rule="off-by-one",
                     file="src/x.py", line=42, action="fix the loop",
                     expected_evidence="a boundary test", closure="the test passes",
                     task="T007", evidence="TEST:green"),
    ])
    cycle["review_role"] = "corrective"
    cycle["reviewed_range"] = "base..HEAD"
    text = handoff.render_revision_text({"review_cycles": [cycle]}, 2)
    assert "# Review — Round 2 (corrective)" in text
    assert "**Range:** `base..HEAD`" in text
    assert "- **Rule:** off-by-one" in text
    assert "- **Expected evidence:** a boundary test" in text
    assert "- **Closure:** the test passes" in text
    assert "- **Task:** T007 · **Commits:** —" in text
    assert "- **Evidence:** TEST:green" in text


def test_render_rich_header_is_import_inert() -> None:
    # only the flat appendix parses back to findings; the rich header is inert even
    # when a finding's action itself contains " - " (which the flat line round-trips).
    from specops import findings as findings_mod
    data = {"review_cycles": [make_cycle(round=2, result="REJECTED", findings=[
        make_finding("R2-F01", severity="blocking", file="src/x.py", line=42,
                     action="fix - the loop", task="T007", evidence="TEST:green"),
        make_finding("R2-F02", severity="advisory", file="y.py", line=3, action="rename"),
    ])]}
    text = handoff.render_revision_text(data, 2)
    parsed = [p for p in (findings_mod.parse_finding_line(ln) for ln in text.splitlines())
              if p is not None]
    assert parsed == [
        {"file": "src/x.py", "line": 42, "action": "fix - the loop"},
        {"file": "y.py", "line": 3, "action": "rename"},
    ]


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


def test_rich_render_import_round_trips_without_spurious_findings(handoff_repo) -> None:
    # render the enriched revision file, then import it back: the two real findings
    # dedupe (idempotent) and the rich header introduces no spurious findings.
    root = handoff_repo(review_cycles=[make_cycle(round=1, findings=[
        make_finding("R1-F01", severity="blocking", file="src/x.py", line=42,
                     action="fix - the loop"),
        make_finding("R1-F02", severity="advisory", file="y.py", line=3, action="rename"),
    ])])
    assert handoff.render_revision(root, 1).status == handoff.RENDER_OK
    # importing the file we just rendered adds nothing (all flat lines already exist)
    assert handoff.cmd_import(root, None).extra["imported"] == 0
    findings = read_ledger(_fd(root))["review_cycles"][-1]["handoff"]["findings"]
    assert len(findings) == 2  # no header line leaked in as a finding


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
    # the line-less flat form appears in the 010-compat appendix and round-trips
    assert text.rstrip().endswith("a.py - file-level issue")
    assert findings.parse_finding_line("a.py - file-level issue") == {
        "file": "a.py", "line": None, "action": "file-level issue",
    }


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


# ---------------------------------------------------------------------------
# Feature 026 (T034) — inherited evidence keeps its amendment provenance
# ---------------------------------------------------------------------------


def _amended_task(tid: str = "T001") -> dict:
    """A task whose current evidence is an amendment, as `status amend-task` leaves it."""
    t = make_task(tid, evidence="TEST_REPORT:verified on recovery")
    t["evidence_refs"] = ["EV-original0001", "EV-amendment01"]
    return t


def _with_amended_evidence(root) -> None:
    """Attach the matching evidence records to the ledger written by the fixture."""
    import yaml

    fd = _fd(root)
    data = yaml.safe_load((fd / "status.yaml").read_text(encoding="utf-8"))
    base = {"producer": "auto", "command": "c", "exit_code": 0,
            "timestamp": "2026-09-01T00:00:00+00:00", "commit_range": "a..b",
            "affected_paths": [], "superseded_by": None}
    data["evidence"] = [
        {**base, "id": "EV-original0001", "summary": "CLI_LOG:placeholder",
         "superseded_by": "EV-amendment01"},
        {**base, "id": "EV-amendment01", "summary": "TEST_REPORT:verified on recovery",
         "producer": "amend", "amendment": True, "reason": "no gate run at close"},
    ]
    (fd / "status.yaml").write_text(yaml.dump(data))


def test_auto_fix_inherits_amendment_provenance(handoff_repo) -> None:
    """FR-006a: `finding fix --auto` copies the task's evidence string. When that value
    is an amendment, the finding's own record must carry the amendment provenance —
    otherwise the correction is laundered one record downstream, which is precisely
    what this feature exists to prevent."""
    root = handoff_repo(tasks=[_amended_task()],
                        review_cycles=[make_cycle(findings=[make_finding("R1-F01")])])
    _with_amended_evidence(root)
    sha = head_commit(root)

    res = handoff.cmd_finding_fix(root, "R1-F01", task="T001", commits=[sha],
                                  evidence=None, auto=True)

    assert res.status == handoff.FINDING_FIXED
    led = read_ledger(_fd(root))
    finding = led["review_cycles"][-1]["handoff"]["findings"][0]
    inherited = next(r for r in led["evidence"] if r["id"] == finding["evidence_id"])
    assert inherited["amendment"] is True
    assert inherited["reason"] == "no gate run at close"


def test_auto_fix_from_an_unamended_task_carries_no_provenance(handoff_repo) -> None:
    """The ordinary path is byte-identical to before: absence marks an original."""
    root = handoff_repo(tasks=[make_task("T001", evidence="CLI_LOG:ordinary")],
                        review_cycles=[make_cycle(findings=[make_finding("R1-F01")])])
    sha = head_commit(root)

    handoff.cmd_finding_fix(root, "R1-F01", task="T001", commits=[sha],
                            evidence=None, auto=True)

    led = read_ledger(_fd(root))
    finding = led["review_cycles"][-1]["handoff"]["findings"][0]
    record = next(r for r in led["evidence"] if r["id"] == finding["evidence_id"])
    assert "amendment" not in record
    assert "reason" not in record


def test_explicit_evidence_is_never_marked_as_inherited(handoff_repo) -> None:
    """Only *inheritance* carries provenance. Evidence the operator supplies directly
    is their own assertion about the fix, not a copy of the task's amended value."""
    root = handoff_repo(tasks=[_amended_task()],
                        review_cycles=[make_cycle(findings=[make_finding("R1-F01")])])
    _with_amended_evidence(root)
    sha = head_commit(root)

    handoff.cmd_finding_fix(root, "R1-F01", task="T001", commits=[sha],
                            evidence="CLI_LOG:fixed by hand", auto=False)

    led = read_ledger(_fd(root))
    finding = led["review_cycles"][-1]["handoff"]["findings"][0]
    record = next(r for r in led["evidence"] if r["id"] == finding["evidence_id"])
    assert "amendment" not in record
