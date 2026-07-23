"""Unit tests for deterministic gate selection (Feature 012, US1, T006).

Covers FR-002/FR-003/SC-001: each predicate branch, the closed reason set, byte-identical
reproducibility, and the no-map/no-baseline degrade.
"""
from __future__ import annotations

from specops import gateprofiles
from specops.gateprofiles import ApplicabilityPredicate as AP
from specops.gateprofiles import GateProfile


def _gate(name, **applies_kw):
    return GateProfile(name=name, command="cmd", applies=AP(**applies_kw))


# affected-context shape mirrors contextmap.cmd_impact(...)["affected"] entries.
AFFECTED = [
    {"context_id": "api", "gates": ["schema-guard"], "risk": {"tier": "high", "persisted": True}},
    {"context_id": "core", "gates": [], "risk": {}},
]


def test_always_selected() -> None:
    [s] = gateprofiles.select_gates([_gate("t", always=True)], [], [])
    assert s.selected and s.reason == gateprofiles.R_ALWAYS


def test_context_match() -> None:
    [s] = gateprofiles.select_gates([_gate("g", contexts=("api",))], ["src/api/x.py"], AFFECTED)
    assert s.selected and s.reason.startswith(gateprofiles.R_CONTEXT)


def test_context_no_match_out_of_scope() -> None:
    [s] = gateprofiles.select_gates([_gate("g", contexts=("billing",))], [], AFFECTED)
    assert not s.selected and s.reason == gateprofiles.R_OUT


def test_path_match() -> None:
    gates = [_gate("g", paths=("migrations/**",))]
    [s] = gateprofiles.select_gates(gates, ["migrations/001.sql"], AFFECTED)
    assert s.selected and s.reason.startswith(gateprofiles.R_PATH)


def test_path_no_match() -> None:
    gates = [_gate("g", paths=("migrations/**",))]
    [s] = gateprofiles.select_gates(gates, ["src/api/x.py"], AFFECTED)
    assert not s.selected


def test_risk_named_key_presence() -> None:
    [s] = gateprofiles.select_gates([_gate("g", risk=(("persisted", None),))], [], AFFECTED)
    assert s.selected and s.reason.startswith(gateprofiles.R_RISK)


def test_risk_named_key_equality() -> None:
    [hit] = gateprofiles.select_gates([_gate("g", risk=(("tier", "high"),))], [], AFFECTED)
    [miss] = gateprofiles.select_gates([_gate("g", risk=(("tier", "low"),))], [], AFFECTED)
    assert hit.selected
    assert not miss.selected


def test_gate_ref_implicit_by_name() -> None:
    # A profile named after a gate id in an affected context's `gates` list is selected.
    [s] = gateprofiles.select_gates([_gate("schema-guard")], [], AFFECTED)
    assert s.selected and s.reason.startswith(gateprofiles.R_GATE_REF)


def test_gate_ref_explicit() -> None:
    [s] = gateprofiles.select_gates([_gate("g", gate_ref="schema-guard")], [], AFFECTED)
    assert s.selected and s.reason.startswith(gateprofiles.R_GATE_REF)


def test_no_map_degrade_only_always_and_paths() -> None:
    gates = [
        _gate("ctx", contexts=("api",)),
        _gate("risky", risk=(("tier", "high"),)),
        _gate("glob", paths=("src/**",)),
        _gate("all", always=True),
    ]
    sel = gateprofiles.select_gates(gates, ["src/x.py"], [])  # empty affected = no map
    by = {s.profile.name: s for s in sel}
    assert not by["ctx"].selected
    assert not by["risky"].selected
    assert by["glob"].selected
    assert by["all"].selected


def test_declared_order_preserved_and_deterministic() -> None:
    gates = [_gate(n, always=True) for n in ("c", "a", "b")]
    r1 = [(s.profile.name, s.reason) for s in gateprofiles.select_gates(gates, [], AFFECTED)]
    r2 = [(s.profile.name, s.reason) for s in gateprofiles.select_gates(gates, [], AFFECTED)]
    assert r1 == [("c", "always"), ("a", "always"), ("b", "always")]
    assert r1 == r2  # byte-identical across runs (SC-001)
