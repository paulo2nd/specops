"""Frozen-shape contract test — base JSON output envelope (Feature 021). [SC-002][SC-004][SC-010]

Locks the base command-result envelope: the key set {command, outcome, class,
output_version}, the outcome/class value enums, and the pinned output_version. Verifies the
key is present across every family and that documented per-command extensions are tolerated
(additive). Complements test_outcome_contract.py.
"""
from __future__ import annotations

import json

from specops import outcome

_BASE_KEYS = {"command", "outcome", "class", "output_version"}
_OUTCOME_ENUM = {"ok", "blocked", "error"}
_CLASS_ENUM = {"pass", "gate-rejection", "infra-error"}


def test_base_envelope_exact_key_set() -> None:
    obj = json.loads(outcome.render("consistency", outcome.PASS))
    assert set(obj) == _BASE_KEYS


def test_outcome_and_class_value_enums_frozen() -> None:
    seen_outcome, seen_class = set(), set()
    for cls in (outcome.PASS, outcome.GATE_REJECTION, outcome.INFRA_ERROR):
        obj = json.loads(outcome.render("x", cls))
        seen_outcome.add(obj["outcome"])
        seen_class.add(obj["class"])
    assert seen_outcome == _OUTCOME_ENUM
    assert seen_class == _CLASS_ENUM


def test_output_version_present_and_pinned() -> None:
    obj = json.loads(outcome.render("reconcile", outcome.PASS))
    assert obj["output_version"] == outcome.OUTPUT_VERSION == 1


def test_report_families_carry_output_version() -> None:
    """The report families pass output_version via _emit; assert their emitted envelope
    version equals the canonical value (byte-position unchanged, value single-sourced)."""
    from specops import contextmap, handoff, trace

    for mod in (trace, handoff, contextmap):
        obj = json.loads(
            outcome.render("x", outcome.PASS, status="pass", output_version=mod.OUTPUT_VERSION)
        )
        assert obj["output_version"] == outcome.OUTPUT_VERSION


def test_additive_extension_key_tolerated() -> None:
    """FR-007/SC-004: a new documented per-command key passes (no false positive)."""
    obj = json.loads(outcome.render("gate", outcome.PASS, verdict="APPROVED", gates=[]))
    assert set(obj) >= _BASE_KEYS
    assert obj["verdict"] == "APPROVED"
    assert obj["gates"] == []
