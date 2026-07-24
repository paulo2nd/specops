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


# --- US3: corrective loop + terminal deterministic gate (FR-015..FR-019) -------

def test_corrective_loop_is_native_do_while_on_verdict() -> None:
    steps = {s["id"]: s for s in _load()["steps"]}
    loop = steps["corrective-loop"]
    assert loop["type"] == "do-while"
    assert "max_iterations" in loop  # native bound (FR-015)
    assert "REJECTED" in loop["condition"]  # loops while the review verdict is REJECTED
    body = [s["id"] for s in loop["steps"]]
    assert "implement" in body and "review-soft" in body


def test_in_loop_review_is_soft_terminal_gate_is_hard() -> None:
    """The in-loop review must not abort the run (--soft, exit 0); the terminal
    gate must fail closed (hard `specops review`) — FR-019."""
    all_steps = {s["id"]: s for s in _flatten(_load()["steps"])}
    assert "--soft" in all_steps["review-soft"]["run"]
    assert all_steps["terminal-gate"]["run"] == "specops review"  # no --soft → fails closed


def test_terminal_gate_between_loop_and_done() -> None:
    ids = [s["id"] for s in _load()["steps"]]
    assert ids.index("corrective-loop") < ids.index("terminal-gate") < ids.index("done")


# --- Feature 016: semantic review composed into the corrective loop -----------

def _loop() -> dict:
    return {s["id"]: s for s in _load()["steps"]}["corrective-loop"]


def _loop_body_ids() -> list[str]:
    """Direct child step ids of the corrective loop, in order."""
    return [s["id"] for s in _loop()["steps"]]


def test_semantic_review_is_composed_and_guarded_by_mechanical_pass() -> None:
    """FR-001/FR-002 (US1): the loop invokes the semantic `specops.review` command,
    wrapped in an `if` gated on the mechanical gate passing, positioned after the
    deterministic `review-soft` gate."""
    all_steps = {s["id"]: s for s in _flatten(_load()["steps"])}

    # The semantic review is the registered agent command, not a shell gate.
    review = all_steps["semantic-review"]
    assert review.get("command") == "specops.review"
    assert "type" not in review or review["type"] == "command"  # native command step

    # It lives inside a guard that only runs when the mechanical gate did NOT reject.
    guard = all_steps["semantic-review-round"]
    assert guard["type"] == "if"
    assert "semantic-review" in [s["id"] for s in guard["then"]]

    # Ordering (mechanical-first): review-soft precedes the semantic review round.
    body = _loop_body_ids()
    assert body.index("review-soft") < body.index("semantic-review-round")


def test_semantic_review_guard_is_exact_mechanical_pass() -> None:
    """FR-002 (US4): the guard runs the semantic review only when the mechanical
    verdict is not REJECTED — a mechanical reject skips the review that round."""
    guard = {s["id"]: s for s in _flatten(_load()["steps"])}["semantic-review-round"]
    assert guard["condition"] == "{{ steps.review-soft.output.data.verdict != 'REJECTED' }}"


def test_loop_condition_reacts_to_unverified_blocking() -> None:
    """FR-003/FR-008 (US2): the do-while condition re-iterates on a mechanical
    REJECTED OR any unverified blocking finding, read from the existing handoff
    report surface (`remaining_blocking`)."""
    loop = _loop()
    assert "REJECTED" in loop["condition"]
    assert "remaining_blocking" in loop["condition"]

    report = {s["id"]: s for s in _flatten(_load()["steps"])}["handoff-report"]
    assert report["run"] == "specops handoff report --json"
    assert report.get("output_format") == "json"
    # The findings signal is produced after the semantic review, still inside the loop.
    body = _loop_body_ids()
    assert body.index("semantic-review-round") < body.index("handoff-report")


def test_loop_bound_is_unchanged() -> None:
    """FR-010: composing the review does not remove/weaken the iteration bound."""
    assert _loop()["max_iterations"] == 3


def test_enforcement_is_not_gated_by_configuration() -> None:
    """FR-015 (US3): enforcement is always-on with auto-degrade — no config/inputs
    flag gates the semantic review or the loop condition. Degrade is by absence of
    findings only (empty `remaining_blocking`)."""
    loop = _loop()
    guard = {s["id"]: s for s in _flatten(_load()["steps"])}["semantic-review-round"]
    for expr in (loop["condition"], guard["condition"]):
        assert "inputs." not in expr
        assert "config" not in expr.lower()
