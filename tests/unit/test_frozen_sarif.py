"""Frozen-shape contract test — SARIF output, v2.1.0 (Feature 021, sweep Entity 9). [SC-002]

The FR-003 sweep surfaced the opt-in SARIF output (`--sarif`) as an adopter-facing output
format beyond the named seven; it is frozen at SARIF 2.1.0 with its blocking→error /
advisory→warning level mapping.
"""
from __future__ import annotations

from specops import sarif


def test_sarif_version_pinned() -> None:
    assert sarif.SARIF_VERSION == "2.1.0"


def test_sarif_projection_carries_frozen_version() -> None:
    """A projected SARIF document declares the frozen version at its top level."""
    doc = sarif.from_ledger({"schema_version": 7}, tool_version="1.2.3")
    assert doc["version"] == "2.1.0"
    assert "runs" in doc  # SARIF top-level shape
