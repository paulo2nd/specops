"""Integration tests for external review ingestion (Feature 015):
`handoff finding import-json | import-sarif | promote`, provenance, all-or-nothing,
idempotency, advisory-by-default, promotion enforcement, and per-path staleness.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from tests.conftest import _git, make_cycle, make_task


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=root, capture_output=True, text=True)


def _ledger_text(root: Path) -> str:
    return (root / "specs" / "001-demo" / "status.yaml").read_text()


def _findings(root: Path) -> list[dict]:
    data = yaml.safe_load(_ledger_text(root))
    cyc = data["review_cycles"][-1]
    return (cyc.get("handoff") or {}).get("findings") or []


def _write_doc(root: Path, name: str, doc: dict) -> str:
    p = root / name
    p.write_text(json.dumps(doc))
    return str(p)


def _add_commit(root: Path, path: str, content: str) -> None:
    fp = root / path
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", f"touch {path}")


def _json_doc(findings=None):
    return {
        "contract_version": 1,
        "producer": {"name": "acme-llm", "version": "1.2.0"},
        "findings": findings if findings is not None else [
            {"rule": "L2", "file": "src/a.py", "line": 42, "action": "fix a"}],
    }


def _sarif_doc(uri="src/b.py", line=7, name="codeql"):
    return {
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": name, "version": "2.15.0"}},
            "results": [{
                "ruleId": "py/x", "level": "error", "message": {"text": "bug"},
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": uri}, "region": {"startLine": line}}}],
            }],
        }],
    }


# ---------------------------------------------------------------------------
# T008 — US1: JSON contract import
# ---------------------------------------------------------------------------


def test_import_json_records_advisory_with_provenance(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    doc = _write_doc(root, "f.json", _json_doc())
    r = _run(root, "handoff", "finding", "import-json", "--file", doc, "--json")
    assert r.returncode == 0, r.stderr
    obj = json.loads(r.stdout)
    assert obj["status"] == "findings_imported" and obj["imported"] == 1
    fid = obj["ids"][0]
    f = _findings(root)[0]
    assert f["id"] == fid and f["severity"] == "advisory" and f["state"] == "OPEN"
    assert f["producer"] == {"name": "acme-llm", "version": "1.2.0"}
    assert f["imported"]["source_format"] == "json"
    assert f["reviewed_digest"]["path"] == "src/a.py"


def test_import_json_defect_is_all_or_nothing_exit2(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    doc = _write_doc(root, "bad.json", _json_doc(findings=[{"file": "a.py"}]))
    before = _ledger_text(root)
    r = _run(root, "handoff", "finding", "import-json", "--file", doc, "--json")
    assert r.returncode == 2 and json.loads(r.stdout)["status"] == "bad_args"
    assert _ledger_text(root) == before  # no partial write


def test_import_json_empty_is_noop_success(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    doc = _write_doc(root, "empty.json", _json_doc(findings=[]))
    before = _ledger_text(root)
    r = _run(root, "handoff", "finding", "import-json", "--file", doc, "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["imported"] == 0
    assert _ledger_text(root) == before  # no-op, no write


def test_import_json_no_open_cycle_exit2(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[])
    doc = _write_doc(root, "f.json", _json_doc())
    r = _run(root, "handoff", "finding", "import-json", "--file", doc, "--json")
    assert r.returncode == 2 and json.loads(r.stdout)["status"] == "bad_args"


def test_import_json_idempotent_no_duplicate(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    doc = _write_doc(root, "f.json", _json_doc())
    assert _run(root, "handoff", "finding", "import-json", "--file", doc).returncode == 0
    after_first = _ledger_text(root)
    r2 = _run(root, "handoff", "finding", "import-json", "--file", doc, "--json")
    assert r2.returncode == 0 and json.loads(r2.stdout)["imported"] == 0
    assert len(_findings(root)) == 1
    assert _ledger_text(root) == after_first  # byte-identical (no file at HEAD ⇒ blob stable None)


# ---------------------------------------------------------------------------
# T012 — US3: advisory-by-default + human promotion
# ---------------------------------------------------------------------------


def _report(root: Path) -> dict:
    return json.loads(_run(root, "handoff", "report", "--json").stdout)


def test_declared_severity_still_imports_advisory(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    doc = _write_doc(root, "f.json", _json_doc(findings=[
        {"rule": "L2", "file": "a.py", "action": "x", "severity": "error"}]))
    _run(root, "handoff", "finding", "import-json", "--file", doc)
    assert _findings(root)[0]["severity"] == "advisory"
    assert _report(root)["remaining_blocking"] == []  # does not block


def test_promote_blocks_approval_until_dismiss(handoff_repo) -> None:
    root = handoff_repo(tasks=[make_task("T001")], review_cycles=[make_cycle()])
    doc = _write_doc(root, "f.json", _json_doc())
    imp = _run(root, "handoff", "finding", "import-json", "--file", doc, "--json")
    fid = json.loads(imp.stdout)["ids"][0]
    pr = _run(root, "handoff", "finding", "promote", fid,
              "--closure", "guard added", "--expected-evidence", "TEST:covers", "--json")
    assert pr.returncode == 0 and json.loads(pr.stdout)["status"] == "finding_promoted"
    assert _findings(root)[0]["severity"] == "blocking"
    # Now gated:
    t = _run(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert t.returncode == 1 and "unverified blocking findings" in (t.stdout + t.stderr)
    # Dismiss (Feature 011 withdrawal path, CHK005) unblocks:
    dm = _run(root, "handoff", "finding", "dismiss", fid, "--reason", "false positive")
    assert dm.returncode == 0
    assert _report(root)["remaining_blocking"] == []


def test_promote_requires_closure_and_evidence_exit2(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    doc = _write_doc(root, "f.json", _json_doc())
    fid = json.loads(
        _run(root, "handoff", "finding", "import-json", "--file", doc, "--json").stdout)["ids"][0]
    r = _run(root, "handoff", "finding", "promote", fid, "--closure", "x", "--json")
    assert r.returncode == 2  # missing --expected-evidence (typer usage error)


def test_reimport_never_demotes_promotion(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    doc = _write_doc(root, "f.json", _json_doc())
    fid = json.loads(
        _run(root, "handoff", "finding", "import-json", "--file", doc, "--json").stdout)["ids"][0]
    _run(root, "handoff", "finding", "promote", fid,
         "--closure", "c", "--expected-evidence", "TEST:e")
    # Re-import the same document:
    _run(root, "handoff", "finding", "import-json", "--file", doc)
    f = _findings(root)[0]
    assert f["severity"] == "blocking" and f["promotion"] is not None
    assert len(_findings(root)) == 1


# ---------------------------------------------------------------------------
# T016 — US2: SARIF adapter + two producers
# ---------------------------------------------------------------------------


def test_import_sarif_records_tool_producer(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    doc = _write_doc(root, "s.sarif", _sarif_doc())
    r = _run(root, "handoff", "finding", "import-sarif", "--file", doc, "--json")
    assert r.returncode == 0, r.stderr
    f = _findings(root)[0]
    assert f["severity"] == "advisory" and f["rule"] == "py/x" and f["file"] == "src/b.py"
    assert f["producer"] == {"name": "codeql", "version": "2.15.0"}
    assert f["imported"]["source_format"] == "sarif"


def test_import_sarif_no_location_all_or_nothing(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    bad = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "t"}},
           "results": [{"ruleId": "x", "message": {"text": "y"}, "locations": []}]}]}
    doc = _write_doc(root, "bad.sarif", bad)
    before = _ledger_text(root)
    r = _run(root, "handoff", "finding", "import-sarif", "--file", doc, "--json")
    assert r.returncode == 2 and json.loads(r.stdout)["status"] == "bad_args"
    assert _ledger_text(root) == before


def test_two_producers_coexist_attributed(handoff_repo) -> None:
    """Roadmap acceptance gate: a JSON and a SARIF producer feed the same handoff."""
    root = handoff_repo(review_cycles=[make_cycle()])
    _run(root, "handoff", "finding", "import-json", "--file",
         _write_doc(root, "f.json", _json_doc()))
    _run(root, "handoff", "finding", "import-sarif", "--file",
         _write_doc(root, "s.sarif", _sarif_doc()))
    producers = {tuple(f["producer"].values()) for f in _findings(root)}
    assert ("acme-llm", "1.2.0") in producers and ("codeql", "2.15.0") in producers
    assert len(_findings(root)) == 2
    # Absence of SARIF is never a defect: the handoff still validates.
    assert _run(root, "handoff", "validate", "--json").returncode == 0


# ---------------------------------------------------------------------------
# T021 — US4: per-path staleness (read-only)
# ---------------------------------------------------------------------------


def test_staleness_is_per_path(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    _add_commit(root, "src/a.py", "print(1)\n")
    _add_commit(root, "src/other.py", "print(0)\n")
    doc = _write_doc(root, "f.json", _json_doc(findings=[
        {"rule": "L2", "file": "src/a.py", "line": 1, "action": "fix a"},
        {"rule": "L3", "file": "src/other.py", "line": 1, "action": "fix other"}]))
    _run(root, "handoff", "finding", "import-json", "--file", doc)
    before = _report(root)
    assert all(f["stale"] is False for f in before["findings"])
    # Change only src/a.py:
    _add_commit(root, "src/a.py", "print(2)\n")
    after = {f["file"]: f["stale"] for f in _report(root)["findings"]}
    assert after["src/a.py"] is True and after["src/other.py"] is False


def test_reimport_refreshes_reviewed_digest(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    _add_commit(root, "src/a.py", "print(1)\n")
    doc = _write_doc(root, "f.json", _json_doc(findings=[
        {"rule": "L2", "file": "src/a.py", "line": 1, "action": "fix a"}]))
    _run(root, "handoff", "finding", "import-json", "--file", doc)
    _add_commit(root, "src/a.py", "print(2)\n")
    assert _report(root)["findings"][0]["stale"] is True
    # Re-import against the now-current content refreshes the baseline in place:
    r = _run(root, "handoff", "finding", "import-json", "--file", doc, "--json")
    assert json.loads(r.stdout)["refreshed"] == 1 and json.loads(r.stdout)["imported"] == 0
    assert len(_findings(root)) == 1
    assert _report(root)["findings"][0]["stale"] is False


def test_report_is_read_only(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle()])
    _add_commit(root, "src/a.py", "print(1)\n")
    _run(root, "handoff", "finding", "import-json", "--file",
         _write_doc(root, "f.json", _json_doc()))
    before = _ledger_text(root)
    _run(root, "handoff", "report", "--json")
    _run(root, "handoff", "validate", "--json")
    assert _ledger_text(root) == before
