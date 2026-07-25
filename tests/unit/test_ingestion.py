"""Unit tests for the pure ingestion module (Feature 015): parse_contract,
parse_sarif, content identity, per-path staleness, and gitops.blob_sha.
"""
from __future__ import annotations

from pathlib import Path

from specops import gitops, ingestion
from tests.conftest import _git

# ---------------------------------------------------------------------------
# T007 — JSON findings-input contract
# ---------------------------------------------------------------------------


def _doc(**over):
    doc = {
        "contract_version": 1,
        "producer": {"name": "acme-llm", "version": "1.2.0"},
        "findings": [{"rule": "L2", "file": "src/a.py", "line": 42, "action": "fix it"}],
    }
    doc.update(over)
    return doc


def test_parse_contract_valid() -> None:
    normalized, defects = ingestion.parse_contract(_doc())
    assert defects == []
    assert len(normalized) == 1
    nf = normalized[0]
    assert nf.rule == "L2" and nf.file == "src/a.py" and nf.line == 42
    assert nf.producer_name == "acme-llm" and nf.producer_version == "1.2.0"
    assert nf.source_format == "json"


def test_parse_contract_unknown_version_defect() -> None:
    normalized, defects = ingestion.parse_contract(_doc(contract_version=99))
    assert normalized == [] and any("contract_version" in d for d in defects)


def test_parse_contract_missing_fields_named_all_or_nothing() -> None:
    doc = _doc(findings=[{"file": "a.py"}])  # missing rule + action
    normalized, defects = ingestion.parse_contract(doc)
    assert normalized == []
    assert any("rule" in d for d in defects) and any("action" in d for d in defects)


def test_parse_contract_missing_producer_defect() -> None:
    doc = {"contract_version": 1,
           "findings": [{"rule": "x", "file": "a.py", "action": "y"}]}
    normalized, defects = ingestion.parse_contract(doc)
    assert normalized == [] and any("producer" in d for d in defects)


def test_parse_contract_producer_without_version_is_unspecified() -> None:
    doc = _doc(producer={"name": "codeql"})
    normalized, _ = ingestion.parse_contract(doc)
    assert normalized[0].producer_version == ingestion.UNSPECIFIED_VERSION


def test_parse_contract_empty_is_noop_success() -> None:
    normalized, defects = ingestion.parse_contract(_doc(findings=[]))
    assert normalized == [] and defects == []


def test_parse_contract_per_finding_producer_override() -> None:
    doc = _doc(findings=[
        {"rule": "L2", "file": "a.py", "action": "x", "producer": {"name": "semgrep"}}])
    normalized, _ = ingestion.parse_contract(doc)
    assert normalized[0].producer_name == "semgrep"


def test_parse_contract_within_doc_dup_collapses() -> None:
    f = {"rule": "L2", "file": "a.py", "line": 1, "action": "x"}
    normalized, _ = ingestion.parse_contract(_doc(findings=[f, dict(f)]))
    assert len(normalized) == 1


def test_content_identity_excludes_digest_and_is_deterministic() -> None:
    a, _ = ingestion.parse_contract(_doc())
    b, _ = ingestion.parse_contract(_doc(reviewed_commit="deadbeef"))
    # Same producer/rule/file/line/action ⇒ identical identity regardless of commit.
    assert ingestion.content_identity(a[0]) == ingestion.content_identity(b[0])


# ---------------------------------------------------------------------------
# T015 — SARIF 2.1.0 input adapter
# ---------------------------------------------------------------------------


def _sarif(results, *, version="2.1.0", name="codeql", tver="2.15.0"):
    return {
        "version": version,
        "runs": [{
            "tool": {"driver": {"name": name, "version": tver}},
            "results": results,
        }],
    }


def _result(uri="src/b.py", line=7, rule="py/x", text="bug here", level="error"):
    return {
        "ruleId": rule, "level": level,
        "message": {"text": text},
        "locations": [{"physicalLocation": {
            "artifactLocation": {"uri": uri}, "region": {"startLine": line}}}],
    }


def test_parse_sarif_valid_maps_result() -> None:
    normalized, defects = ingestion.parse_sarif(_sarif([_result()]))
    assert defects == []
    nf = normalized[0]
    assert nf.rule == "py/x" and nf.file == "src/b.py" and nf.line == 7
    assert nf.action == "bug here"
    assert nf.producer_name == "codeql" and nf.producer_version == "2.15.0"
    assert nf.source_format == "sarif" and nf.declared_severity == "error"


def test_parse_sarif_bad_version_defect() -> None:
    normalized, defects = ingestion.parse_sarif(_sarif([_result()], version="2.0.0"))
    assert normalized == [] and any("SARIF version" in d for d in defects)


def test_parse_sarif_no_location_is_per_result_defect() -> None:
    res = {"ruleId": "x", "message": {"text": "y"}, "locations": []}
    normalized, defects = ingestion.parse_sarif(_sarif([res]))
    assert normalized == [] and any("no usable physical location" in d for d in defects)


def test_parse_sarif_missing_tool_name_defect() -> None:
    doc = {"version": "2.1.0", "runs": [{"tool": {"driver": {}}, "results": [_result()]}]}
    normalized, defects = ingestion.parse_sarif(doc)
    assert normalized == [] and any("tool.driver.name" in d for d in defects)


def test_parse_sarif_primary_location_is_first_with_uri() -> None:
    res = _result()
    res["locations"] = [
        {"physicalLocation": {"logicalLocation": {}}},  # no uri — skipped
        {"physicalLocation": {"artifactLocation": {"uri": "src/c.py"},
                              "region": {"startLine": 3}}},
    ]
    normalized, _ = ingestion.parse_sarif(_sarif([res]))
    assert normalized[0].file == "src/c.py" and normalized[0].line == 3


def test_parse_sarif_every_result_is_advisory_severity_informational() -> None:
    # declared_severity is retained but the recorded severity (set by handoff) is advisory.
    normalized, _ = ingestion.parse_sarif(_sarif([_result(level="error")]))
    assert normalized[0].declared_severity == "error"  # informational only


# ---------------------------------------------------------------------------
# T020 — per-path staleness comparison
# ---------------------------------------------------------------------------


def test_is_stale_semantics() -> None:
    assert ingestion.is_stale("sha-a", "sha-a") is False
    assert ingestion.is_stale("sha-a", "sha-b") is True
    assert ingestion.is_stale("sha-a", None) is True  # path removed at HEAD


# ---------------------------------------------------------------------------
# T004 — gitops.blob_sha
# ---------------------------------------------------------------------------


def test_blob_sha_present_and_stable(tmp_git_repo: Path) -> None:
    (tmp_git_repo / "f.py").write_text("print(1)\n")
    _git(tmp_git_repo, "add", "-A")
    _git(tmp_git_repo, "commit", "-m", "add f")
    repo = gitops.find_repo(tmp_git_repo)
    sha1 = gitops.blob_sha(repo, "HEAD", "f.py")
    assert sha1 and gitops.blob_sha(repo, "HEAD", "f.py") == sha1  # stable


def test_blob_sha_changes_with_content(tmp_git_repo: Path) -> None:
    fp = tmp_git_repo / "f.py"
    fp.write_text("print(1)\n")
    _git(tmp_git_repo, "add", "-A")
    _git(tmp_git_repo, "commit", "-m", "v1")
    repo = gitops.find_repo(tmp_git_repo)
    before = gitops.blob_sha(repo, "HEAD", "f.py")
    fp.write_text("print(2)\n")
    _git(tmp_git_repo, "add", "-A")
    _git(tmp_git_repo, "commit", "-m", "v2")
    assert gitops.blob_sha(repo, "HEAD", "f.py") != before


def test_blob_sha_missing_path_or_rev_is_none(tmp_git_repo: Path) -> None:
    repo = gitops.find_repo(tmp_git_repo)
    assert gitops.blob_sha(repo, "HEAD", "nope.py") is None
    assert gitops.blob_sha(repo, "nonexistent-rev", "README.md") is None
