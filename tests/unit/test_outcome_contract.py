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
        "output_version": outcome.OUTPUT_VERSION,  # Feature 021: always present
    }
    assert "verdict" not in obj  # None extras are dropped


# --- Feature 021 (Contract Freeze): frozen exit-code + envelope version -----

def test_exit_codes_frozen() -> None:
    """SC-009: the three-value exit contract is locked; a change to any code's value
    or meaning fails here (and Principle VI must document all three)."""
    assert outcome.EXIT_OK == 0
    assert outcome.EXIT_BLOCKED == 1  # blocking gate result / review REJECTED
    assert outcome.EXIT_ERROR == 2  # infrastructure / data / usage error
    assert outcome.exit_for(outcome.PASS) == 0
    assert outcome.exit_for(outcome.GATE_REJECTION) == 1
    assert outcome.exit_for(outcome.INFRA_ERROR) == 2
    # No command may emit a code outside {0, 1, 2}.
    assert set(outcome._EXIT_FOR_CLASS.values()) == {0, 1, 2}


def test_base_envelope_always_carries_output_version() -> None:
    """SC-010/FR-009: every `--json` envelope carries a pinned output_version, even the
    families (consistency/reconcile) that do not pass one explicitly."""
    for cls in (outcome.PASS, outcome.GATE_REJECTION, outcome.INFRA_ERROR):
        obj = json.loads(outcome.render("consistency", cls))
        assert obj["output_version"] == outcome.OUTPUT_VERSION == 1


def test_base_envelope_default_version_is_independent_of_families() -> None:
    """FR-009/SC-010: the base envelope's default version is outcome.OUTPUT_VERSION and is
    NOT derived from any command family's constant. Command families keep their own
    independent output_version (retained unchanged); this asserts the base default does
    not silently track a family value — a family bump must not move the base envelope."""
    # The base envelope (a family with no richer payload, e.g. consistency) always stamps
    # outcome.OUTPUT_VERSION, regardless of what any family constant happens to be.
    obj = json.loads(outcome.render("consistency", outcome.PASS))
    assert obj["output_version"] == outcome.OUTPUT_VERSION


def test_per_family_output_versions_are_frozen_baselines() -> None:
    """SC-002: each command family's independent output_version is frozen at its 1.0
    baseline (all == 1). These are separate version axes, not a single global value —
    a family may bump on its own schedule per the versioning policy."""
    from specops import contextmap, doctor, gateprofiles, handoff, lane, trace

    for mod in (trace, handoff, contextmap, doctor, lane, gateprofiles):
        assert mod.OUTPUT_VERSION == 1, f"{mod.__name__}.OUTPUT_VERSION baseline is 1"


def test_base_envelope_key_set_is_frozen() -> None:
    """FR-004: the base envelope key set is exactly {command, outcome, class,
    output_version}; a rename/removal of a base key fails here. Documented per-command
    extension keys are still permitted (additive)."""
    obj = json.loads(outcome.render("consistency", outcome.PASS))
    assert set(obj) == {"command", "outcome", "class", "output_version"}
    # Additive tolerance: a new documented per-command key does not break the envelope.
    obj2 = json.loads(outcome.render("consistency", outcome.PASS, new_optional_key="x"))
    assert {"command", "outcome", "class", "output_version"} <= set(obj2)
    assert obj2["new_optional_key"] == "x"


def test_render_review_verdict_and_gates() -> None:
    gates = [{"name": "reconcile", "status": "PASS"}, {"name": "test", "status": "FAIL"}]
    obj = json.loads(
        outcome.render("review", outcome.GATE_REJECTION, verdict="REJECTED", gates=gates)
    )
    assert obj["verdict"] == "REJECTED"
    assert obj["gates"] == gates
    assert obj["outcome"] == "blocked"


def test_render_mirrors_invoked_command_name() -> None:
    """Feature 017 FR-004/SC-005: the `command` value mirrors the invoked name and the
    object shape (keys) is unchanged — `preflight` and its `review` alias differ only in
    this value."""
    gates = [{"name": "reconcile", "status": "PASS"}]
    pre = json.loads(
        outcome.render("preflight", outcome.PASS, verdict="APPROVED", gates=gates)
    )
    rev = json.loads(
        outcome.render("review", outcome.PASS, verdict="APPROVED", gates=gates)
    )
    assert pre["command"] == "preflight"
    assert rev["command"] == "review"
    # Same keys, same shape — only the command value differs (no key renamed).
    assert pre.keys() == rev.keys()
    assert {k: v for k, v in pre.items() if k != "command"} == {
        k: v for k, v in rev.items() if k != "command"
    }


# --- Feature 018 (US1): trace/handoff join the canonical CommandResult ------

# The exact status→exit-code contract every family must preserve after the
# consolidation. Enumerated here (not derived from the modules) so a subclass that
# drops or remaps a status is caught (SC-003, T007).
_TRACE_EXIT = {
    "trace_ok": 0, "drift_clean": 0, "ack_recorded": 0, "ack_idempotent": 0,
    "ack_already_planned": 0,
    "drift_blocked": 1, "trace_incomplete": 1,
    "usage_error": 2, "ack_conflict": 2, "ack_unknown_task": 2,
}
_HANDOFF_EXIT = {
    "finding_recorded": 0, "handoff_authorized": 0, "finding_fixed": 0,
    "finding_verified": 0, "finding_dismissed": 0, "findings_imported": 0,
    "finding_promoted": 0, "handoff_closed": 0, "handoff_already_closed": 0,
    "scope_recorded": 0, "validate_ok": 0, "report_ok": 0, "render_ok": 0,
    "approval_blocked": 1, "close_blocked": 1, "dangling_reference": 1,
    "scope_unresolvable": 1,
    "missing_closure": 1, "contradictory_state": 1, "duplicate_id": 1,
    "illegal_transition": 2, "precondition_unmet": 2, "unknown_task": 2,
    "unknown_finding": 2, "duplicate_id_create": 2, "not_a_repo": 2, "bad_args": 2,
}


def test_trace_and_handoff_results_are_command_result_subclasses() -> None:
    from specops import handoff, trace

    assert issubclass(trace.TraceResult, outcome.CommandResult)
    assert issubclass(handoff.HandoffResult, outcome.CommandResult)


@pytest.mark.parametrize(
    "module_attr, expected",
    [("trace.TraceResult", _TRACE_EXIT), ("handoff.HandoffResult", _HANDOFF_EXIT)],
)
def test_result_class_map_reproduces_exit_mapping(module_attr, expected) -> None:
    """Each family's _CLASS_MAP reproduces today's status→class→exit-code mapping exactly."""
    import importlib

    mod_name, cls_name = module_attr.split(".")
    cls = getattr(importlib.import_module(f"specops.{mod_name}"), cls_name)
    # Every enumerated status is present, and no extra statuses have crept in.
    assert set(cls._CLASS_MAP) == set(expected)
    for status, code in expected.items():
        r = cls(command="x", status=status, human="h")
        assert r.exit_code == code, f"{module_attr}[{status}] should exit {code}"
