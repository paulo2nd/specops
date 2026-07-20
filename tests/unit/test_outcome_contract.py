"""Unit tests for the stable CLI outcome contract (Feature 007, FR-021..024). [SC-006]"""
from __future__ import annotations

import json

import pytest

from specops import outcome


@pytest.mark.parametrize(
    "cls, status, code",
    [
        (outcome.PASS, outcome.OK, 0),
        (outcome.GATE_REJECTION, outcome.BLOCKED, 1),
        (outcome.INFRA_ERROR, outcome.ERROR, 2),
    ],
)
def test_class_maps_consistently_to_status_and_exit(cls, status, code) -> None:
    """G1: outcome ↔ class ↔ exit_code are consistent."""
    assert outcome.status_for(cls) == status
    assert outcome.exit_for(cls) == code
    obj = json.loads(outcome.render("review", cls))
    assert obj["class"] == cls
    assert obj["outcome"] == status


def test_render_includes_only_non_none_extras() -> None:
    obj = json.loads(
        outcome.render("reconcile", outcome.INFRA_ERROR,
                       diverged_dimension="baseline", remedy="specops status rebaseline",
                       verdict=None)
    )
    assert obj == {
        "command": "reconcile",
        "outcome": "error",
        "class": "infra-error",
        "diverged_dimension": "baseline",
        "remedy": "specops status rebaseline",
    }
    assert "verdict" not in obj  # None extras are dropped


def test_render_review_verdict_and_gates() -> None:
    gates = [{"name": "reconcile", "status": "PASS"}, {"name": "test", "status": "FAIL"}]
    obj = json.loads(
        outcome.render("review", outcome.GATE_REJECTION, verdict="REJECTED", gates=gates)
    )
    assert obj["verdict"] == "REJECTED"
    assert obj["gates"] == gates
    assert obj["outcome"] == "blocked"
