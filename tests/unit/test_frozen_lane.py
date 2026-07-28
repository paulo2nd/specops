"""Frozen-shape contract test — lane.yaml lightweight-lane state, schema v1 (Feature 021). [SC-002]

Locks the lane schema version, the state enum, and the top-level key set. A change to the
version, an added/removed/renamed state, or a change to the frozen top-level keys fails here.
"""
from __future__ import annotations

from specops import lane

# Enumerated frozen baseline (data-model.md Entity 3).
_FROZEN_STATES = ("OPEN", "CLOSED", "PROMOTED")
_FROZEN_TOP_LEVEL = {
    "schema_version", "lane_id", "feature", "branch", "baseline", "created_at",
    "updated_at", "state", "eligibility", "decisions", "closure", "promotion",
}


def test_lane_schema_version_pinned() -> None:
    assert lane.LANE_SCHEMA == 1


def test_lane_state_enum_frozen() -> None:
    assert tuple(lane.STATES) == _FROZEN_STATES


def test_lane_template_top_level_keys_frozen() -> None:
    """The template is the canonical shape a fresh lane is born with; its top-level keys
    are the frozen contract adopters read."""
    import yaml

    template = yaml.safe_load(lane._TEMPLATE.read_text(encoding="utf-8")) if hasattr(
        lane, "_TEMPLATE"
    ) else None
    if template is None:
        # Fall back to the load path over a rendered template if the constant name differs.
        import pathlib

        tmpl = pathlib.Path(lane.__file__).resolve().parent / "templates" / "lane.yaml"
        template = yaml.safe_load(tmpl.read_text(encoding="utf-8"))
    assert set(template) == _FROZEN_TOP_LEVEL
