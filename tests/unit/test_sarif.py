"""Unit tests for the SARIF 2.1.0 projection (Feature 012, US4, T031).

Covers FR-013/SC-009: rule/location/severity mapping, deduped+sorted rules,
deterministic order, and `region` omitted when a finding has no line.
"""
from __future__ import annotations

import json

from specops import sarif


def _f(fid, rule, severity, file, line, action):
    return {"id": fid, "rule": rule, "severity": severity,
            "file": file, "line": line, "action": action}


def test_version_and_driver() -> None:
    doc = sarif.project([], tool_version="0.4.0")
    assert doc["version"] == "2.1.0"
    driver = doc["runs"][0]["tool"]["driver"]
    assert driver["name"] == "specops" and driver["version"] == "0.4.0"


def test_severity_mapping() -> None:
    doc = sarif.project([
        _f("R1-F01", "no-secrets", "blocking", "a.py", 42, "fix"),
        _f("R1-F02", "style", "advisory", "b.py", None, "nit"),
    ])
    results = doc["runs"][0]["results"]
    assert results[0]["level"] == "error"
    assert results[1]["level"] == "warning"


def test_location_and_region() -> None:
    doc = sarif.project([_f("R1-F01", "r", "blocking", "src/x.py", 10, "a")])
    loc = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "src/x.py"
    assert loc["region"]["startLine"] == 10


def test_region_omitted_without_line() -> None:
    doc = sarif.project([_f("R1-F01", "r", "blocking", "src/x.py", None, "a")])
    loc = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert "region" not in loc


def test_rules_deduped_and_sorted() -> None:
    doc = sarif.project([
        _f("1", "b", "blocking", "x", 1, "a"),
        _f("2", "a", "advisory", "y", 2, "b"),
        _f("3", "b", "blocking", "z", 3, "c"),
    ])
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    assert [r["id"] for r in rules] == ["a", "b"]


def test_message_includes_id_and_action() -> None:
    doc = sarif.project([_f("R1-F01", "r", "blocking", "x", 1, "remove secret")])
    assert doc["runs"][0]["results"][0]["message"]["text"] == "R1-F01: remove secret"


def test_deterministic() -> None:
    fs = [_f("R1-F01", "r", "blocking", "x", 1, "a")]
    assert json.dumps(sarif.project(fs)) == json.dumps(sarif.project(fs))
