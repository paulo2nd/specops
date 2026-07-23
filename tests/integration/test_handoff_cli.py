"""Integration tests for the `specops handoff` CLI (Feature 011)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from tests.conftest import head_commit, make_cycle, make_finding, make_task


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=root, capture_output=True, text=True)


def _ledger(root: Path) -> dict:
    return yaml.safe_load((root / "specs" / "001-demo" / "status.yaml").read_text())


# ---------------------------------------------------------------------------
# US1 — finding add / authorize
# ---------------------------------------------------------------------------


def test_finding_add_json_contract(handoff_repo) -> None:
    root = handoff_repo()
    r = _run(root, "handoff", "finding", "add", "--severity", "blocking", "--rule", "L2",
             "--file", "src/a.py", "--line", "42", "--action", "fix",
             "--expected-evidence", "a test", "--closure", "passes", "--json")
    assert r.returncode == 0, r.stderr
    obj = json.loads(r.stdout)
    assert obj["command"] == "handoff finding add"
    assert obj["output_version"] == 1 and obj["status"] == "finding_recorded"
    assert obj["id"] == "R1-F01"


def test_finding_add_bad_severity_exit2(handoff_repo) -> None:
    root = handoff_repo()
    r = _run(root, "handoff", "finding", "add", "--severity", "critical", "--rule", "x",
             "--file", "a.py", "--action", "a", "--json")
    assert r.returncode == 2
    assert json.loads(r.stdout)["status"] == "bad_args"


def test_authorize_and_report_roundtrip(handoff_repo) -> None:
    root = handoff_repo()
    _run(root, "handoff", "finding", "add", "--severity", "advisory", "--rule", "x",
         "--file", "a.py", "--line", "1", "--action", "note")
    r = _run(root, "handoff", "authorize", "--path", "a.py", "--json")
    assert r.returncode == 0
    assert _ledger(root)["review_cycles"][-1]["handoff"]["authorized_paths"] == ["a.py"]


# ---------------------------------------------------------------------------
# US2 — fix / verify / close / approval-block
# ---------------------------------------------------------------------------


def _repo_open_blocking(handoff_repo):
    return handoff_repo(
        tasks=[make_task("T001")],
        review_cycles=[make_cycle(findings=[make_finding("R1-F01")])],
    )


def test_fix_verify_close_flow(handoff_repo) -> None:
    root = _repo_open_blocking(handoff_repo)
    sha = head_commit(root)
    assert _run(root, "handoff", "finding", "fix", "R1-F01", "--task", "T001",
                "--commit", sha, "--evidence", "TEST_REPORT:ok").returncode == 0
    assert _run(root, "handoff", "finding", "verify", "R1-F01").returncode == 0
    close = _run(root, "handoff", "close", "--json")
    assert close.returncode == 0 and json.loads(close.stdout)["status"] == "handoff_closed"
    # idempotent re-close
    again = _run(root, "handoff", "close", "--json")
    assert again.returncode == 0 and json.loads(again.stdout)["status"] == "handoff_already_closed"


def test_verify_from_open_exit2(handoff_repo) -> None:
    root = _repo_open_blocking(handoff_repo)
    r = _run(root, "handoff", "finding", "verify", "R1-F01", "--json")
    assert r.returncode == 2 and json.loads(r.stdout)["status"] == "illegal_transition"


def test_close_blocked_exit1(handoff_repo) -> None:
    root = _repo_open_blocking(handoff_repo)
    r = _run(root, "handoff", "close", "--json")
    assert r.returncode == 1 and json.loads(r.stdout)["status"] == "close_blocked"


def test_approval_blocked_via_transition(handoff_repo) -> None:
    root = _repo_open_blocking(handoff_repo)
    r = _run(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert r.returncode == 1
    assert "unverified blocking findings" in (r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# US3 — validate / report (read-only)
# ---------------------------------------------------------------------------


def test_validate_clean_exit0(handoff_repo) -> None:
    root = _repo_open_blocking(handoff_repo)
    r = _run(root, "handoff", "validate", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "validate_ok"


def test_validate_duplicate_exit1(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(findings=[
        make_finding("R1-F01"), make_finding("R1-F01", file="b.py")])])
    r = _run(root, "handoff", "validate", "--json")
    assert r.returncode == 1 and json.loads(r.stdout)["status"] == "duplicate_id"


def test_report_readonly_and_deterministic(handoff_repo) -> None:
    root = _repo_open_blocking(handoff_repo)
    before = _ledger(root)
    a = _run(root, "handoff", "report", "--json")
    b = _run(root, "handoff", "report", "--json")
    assert a.stdout == b.stdout
    assert json.loads(a.stdout)["remaining_blocking"] == ["R1-F01"]
    assert _ledger(root) == before  # read-only


# ---------------------------------------------------------------------------
# US4 — import / render / not-a-repo
# ---------------------------------------------------------------------------


def test_import_legacy_prose(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    rev = root / "specs" / "001-demo" / "revisions"
    rev.mkdir()
    (rev / "revision-1.md").write_text("src/x.py:12 - do it\n")
    r = _run(root, "handoff", "import", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["imported"] == 1
    f = _ledger(root)["review_cycles"][-1]["handoff"]["findings"][0]
    assert f["severity"] == "advisory" and f["file"] == "src/x.py"


def test_render_projection_is_010_compatible(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(round=1, findings=[
        make_finding("R1-F01", file="a.py", line=9, action="fix it")])])
    r = _run(root, "handoff", "render", "--round", "1")
    assert r.returncode == 0
    text = (root / "specs" / "001-demo" / "revisions" / "revision-1.md").read_text()
    assert text == "a.py:9 - fix it\n"


def test_not_a_git_repo_exit2(tmp_path: Path) -> None:
    (tmp_path / ".specify").mkdir()
    (tmp_path / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"}))
    (tmp_path / "specs" / "001-demo").mkdir(parents=True)
    r = _run(tmp_path, "handoff", "close", "--json")
    assert r.returncode == 2 and json.loads(r.stdout)["status"] == "not_a_repo"
