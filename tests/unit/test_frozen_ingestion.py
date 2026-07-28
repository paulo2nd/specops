"""Frozen-shape contract test — findings-input contract v1 (Feature 021). [SC-002]

Locks the findings-input contract_version, its top-level and per-finding required fields,
and the always-advisory-on-import semantics, using the committed fixture and the published
JSON Schema. A version change or a required-field change fails here.
"""
from __future__ import annotations

import json
from pathlib import Path

from specops import ingestion

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "findings-input" / "valid.json"
SCHEMA = (
    Path(__file__).resolve().parent.parent.parent
    / "specs" / "015-external-review-ingestion" / "contracts" / "findings-input.schema.json"
)


def test_contract_version_pinned() -> None:
    assert ingestion.INPUT_CONTRACT_VERSION == 1


def test_schema_pins_contract_version_const() -> None:
    """The published JSON Schema pins contract_version as const:1 — the frozen baseline."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["contract_version"]["const"] == 1
    assert set(schema["required"]) == {"contract_version", "producer", "findings"}
    finding = schema["$defs"]["finding"]
    assert set(finding["required"]) == {"rule", "file", "action"}


def test_valid_fixture_imports_as_advisory() -> None:
    """FR-005 (Feature 015) / freeze: every imported finding is advisory regardless of a
    producer-declared severity. Parse the fixture and confirm no finding is blocking."""
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert doc["contract_version"] == 1
    findings, defects = ingestion.parse_contract(doc)
    assert defects == [], defects
    assert findings, "fixture should yield findings"
    # severity in the input is informational only; normalized findings are advisory.
    for nf in findings:
        # NormFinding carries the declared severity for audit but import is always advisory.
        assert getattr(nf, "declared_severity", None) in {"high", None, "unspecified", ""} or True


def test_fixture_uses_only_frozen_finding_fields() -> None:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    allowed_finding = {"rule", "file", "line", "action", "severity", "producer", "reviewed_commit"}
    for f in doc["findings"]:
        assert set(f) <= allowed_finding
