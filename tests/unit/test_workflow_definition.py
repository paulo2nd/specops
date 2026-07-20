"""Structural validation of the shipped `specops` workflow definition (Feature 007).

Portable "unit test for the definition": parses the YAML and asserts the
complement-boundary contract (C1-C4, FR-002/026) without requiring Spec Kit to be
importable. The definition is separately verified against Spec Kit's own
`validate_workflow` via `specify workflow info` during development.
"""
from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / "src" / "specops" / "templates" / "workflows" / "specops" / "workflow.yml"
)

# Spec Kit native step types — SpecOps introduces none (FR-002).
NATIVE_STEP_TYPES = {
    "command", "shell", "prompt", "gate", "if", "switch",
    "while", "do-while", "fan-out", "fan-in", "init",
}


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _flatten(steps: list[dict]) -> list[dict]:
    out: list[dict] = []
    for step in steps:
        out.append(step)
        for key in ("then", "else", "steps"):
            nested = step.get(key)
            if isinstance(nested, list):
                out.extend(_flatten(nested))
    return out


def test_workflow_identity() -> None:
    wf = _load()["workflow"]
    assert wf["id"] == "specops"
    assert wf["version"] == "1.0.0"


def test_all_steps_are_native_types() -> None:
    """FR-002/SC-002: SpecOps composes only Spec Kit native step types."""
    for step in _flatten(_load()["steps"]):
        step_type = step.get("type", "command")  # type defaults to 'command'
        assert step_type in NATIVE_STEP_TYPES, f"{step['id']}: non-native type {step_type!r}"


def test_no_fan_out_or_fan_in() -> None:
    """FR-026: strictly sequential — no parallel multi-agent fan-out."""
    types = {s.get("type", "command") for s in _flatten(_load()["steps"])}
    assert "fan-out" not in types
    assert "fan-in" not in types


def test_readiness_gate_between_plan_and_tasks() -> None:
    """FR-004: a human gate sits between plan and tasks; tasks cannot precede it."""
    ids = [s["id"] for s in _load()["steps"]]
    steps_by_id = {s["id"]: s for s in _load()["steps"]}
    assert "readiness-gate" in ids
    gate = steps_by_id["readiness-gate"]
    assert gate["type"] == "gate"
    assert gate.get("on_reject") == "abort"
    assert ids.index("plan") < ids.index("readiness-gate") < ids.index("tasks")


def test_optional_steps_are_human_gated() -> None:
    """FR-006: each optional step has a preceding gate and a skip-recording shell step."""
    ids = [s["id"] for s in _load()["steps"]]
    for opt in ("clarify", "checklist", "analyze"):
        assert f"{opt}-gate" in ids
        assert f"{opt}-record" in ids
        assert ids.index(f"{opt}-gate") < ids.index(f"{opt}-record")


def test_no_duplicate_step_ids() -> None:
    ids = [s["id"] for s in _flatten(_load()["steps"])]
    assert len(ids) == len(set(ids))
