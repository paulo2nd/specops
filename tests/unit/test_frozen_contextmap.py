"""Frozen-shape contract test — context-map file, schema v1 (Feature 021, sweep Entity 8). [SC-002]

The FR-003 sweep surfaced the user-authored context-map file (`.specify/specops/context-map.yaml`)
as an adopter-facing persisted format beyond the named seven; it is frozen at schema v1.
"""
from __future__ import annotations

from pathlib import Path

from specops import contextmap


def test_contextmap_schema_baseline_pinned() -> None:
    assert contextmap.CURRENT_SCHEMA == 1


def test_contextmap_file_relpath_frozen() -> None:
    """The on-disk location adopters author is part of the frozen contract."""
    assert Path(".specify") / "specops" / "context-map.yaml" == contextmap.MAP_RELPATH


def test_contextmap_rejects_unsupported_schema() -> None:
    """A schema_version above CURRENT_SCHEMA is classified unsupported (fails closed),
    proving the version gate is real — the basis for the freeze's bump obligation."""
    kind = contextmap.classify(contextmap.CURRENT_SCHEMA + 1)
    assert kind != "current" and kind is not None
