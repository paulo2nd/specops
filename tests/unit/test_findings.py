"""Finding factory + co-located line grammar (Feature 018 US3, T021).

`findings.new_finding` is the single base-shape factory for the three current
construction sites (authoring, legacy import, external import); `parse_finding_line`
and `format_finding_line` are the co-located, round-trip-guaranteed pair for the
``<file>[:<line>] - <action>`` grammar (FR-008/FR-009, SC-003).
"""
from __future__ import annotations

import pytest

from specops import findings

# The base shape every construction path must share (FR-008).
BASE_KEYS = {
    "id", "severity", "rule", "file", "line", "action",
    "expected_evidence", "closure_criteria", "state", "task", "commits",
    "evidence", "fixed_at", "verified_at",
}


def test_new_finding_base_shape() -> None:
    f = findings.new_finding(
        id="R1-F01", severity="blocking", rule="R", file="src/a.py", line=1,
        action="do the thing", expected_evidence="a test", closure_criteria="passes",
    )
    assert set(f) == BASE_KEYS
    assert f["state"] == "OPEN"
    assert f["task"] is None and f["commits"] == [] and f["evidence"] is None
    assert f["fixed_at"] is None and f["verified_at"] is None
    assert f["expected_evidence"] == "a test" and f["closure_criteria"] == "passes"


def test_new_finding_optional_closure_defaults_none() -> None:
    f = findings.new_finding(
        id="R1-F02", severity="advisory", rule="imported", file="src/a.py",
        line=None, action="do",
    )
    assert f["expected_evidence"] is None and f["closure_criteria"] is None
    assert set(f) == BASE_KEYS


def test_new_finding_import_layers_on_identical_base() -> None:
    """The import path adds imported/producer/reviewed_digest atop the *identical* base
    dict — the base shape must not differ across the three creation paths (FR-008)."""
    kwargs = dict(id="R1-F03", severity="advisory", rule="r", file="src/a.py",
                  line=None, action="do")
    base = findings.new_finding(**kwargs)
    imported = findings.new_finding(
        **kwargs, imported={"contract_version": 1, "source_format": "json"},
        producer={"name": "p", "version": "1"}, reviewed_digest={"path": "src/a.py"},
    )
    assert set(imported) == BASE_KEYS | {"imported", "producer", "reviewed_digest"}
    assert {k: imported[k] for k in BASE_KEYS} == base


@pytest.mark.parametrize("finding", [
    {"file": "src/a.py", "line": 12, "action": "fix the thing"},
    {"file": "src/b.py", "line": None, "action": "no line here"},
    {"file": "docs/x.md", "line": 1, "action": "a - b - c dashes in action"},
])
def test_finding_line_round_trip(finding: dict) -> None:
    """parse(format(f)) is lossless for file/line/action, with and without a line."""
    rendered = findings.format_finding_line(finding)
    assert findings.parse_finding_line(rendered) == finding


def test_parse_returns_none_for_non_finding_line() -> None:
    assert findings.parse_finding_line("just some prose") is None
    assert findings.parse_finding_line("") is None
