"""Unit tests for the Feature 009 consumption layer (contextmap + speckit).

Covers: map digest determinism (R1), reverse-edge impact incl. cycle-safety and
closed edge-set attribution (R2/R3), plan-topology validation (R4), stale
detection over tracked files (R8), and provenance markers (R6). Behavior is
exercised against fixtures/inline maps — never this repository.
"""
from __future__ import annotations

from pathlib import Path

from specops import contextmap as cm
from specops import outcome, speckit
from specops.contextmap import Context
from tests.conftest import DEP_GRAPH_MAP, write_map


def _ctx(cid: str, match: list[str], deps: list[str] | None = None,
         reads: dict | None = None, gates: list[str] | None = None,
         risk: dict | None = None) -> Context:
    return Context(id=cid, match=match, reads=reads or {}, ownership=None,
                   dependencies=deps or [], gates=gates or [], risk=risk or {},
                   decl_index=0)


# ---------------------------------------------------------------------------
# Map digest (R1, SC-001, SC-008)
# ---------------------------------------------------------------------------

def test_digest_is_order_independent() -> None:
    a = [_ctx("api", ["src/api/**"], ["config"]), _ctx("config", ["src/config/**"])]
    assert cm._digest_contexts(a) == cm._digest_contexts(list(reversed(a)))


def test_digest_changes_with_meaning() -> None:
    a = [_ctx("api", ["src/api/**"], ["config"]), _ctx("config", ["src/config/**"])]
    b = [_ctx("api", ["src/api/**"], []), _ctx("config", ["src/config/**"])]
    assert cm._digest_contexts(a) != cm._digest_contexts(b)


def test_map_digest_absent_is_none(context_map_repo: Path) -> None:
    assert cm.map_digest(context_map_repo) is None


def test_map_digest_stable_across_calls(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    assert cm.map_digest(context_map_repo) == cm.map_digest(context_map_repo)


def test_map_digest_invariant_to_comments(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    d1 = cm.map_digest(context_map_repo)
    # Re-serialize with a leading comment + reordered keys — meaning unchanged.
    p = cm.map_path(context_map_repo)
    p.write_text("# a comment\n" + p.read_text(), encoding="utf-8")
    assert cm.map_digest(context_map_repo) == d1


# ---------------------------------------------------------------------------
# Reverse-edge impact (R2/R3, SC-002, SC-003)
# ---------------------------------------------------------------------------

def test_reverse_adjacency() -> None:
    ctxs = [_ctx("api", ["src/api/**"], ["config"]),
            _ctx("web", ["src/web/**"], ["api"]), _ctx("config", ["src/config/**"])]
    assert cm._reverse_adjacency(ctxs) == {"config": ["api"], "api": ["web"]}


def test_impact_ownership_and_reverse_dependents(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_impact(context_map_repo, paths=["src/config/x.py"])
    assert r.status == cm.S_IMPACT_OK
    got = {a["context_id"]: a["via"] for a in r.extra["impact"]["affected"]}
    assert got == {"config": "ownership", "api": "dependency", "web": "dependency"}


def test_impact_every_context_has_closed_set_via(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_impact(context_map_repo, paths=["src/config/x.py"])
    for a in r.extra["impact"]["affected"]:
        assert a["via"] in {"ownership", "dependency", "policy"}
    # policy is enforced-but-empty against the current schema (no policy attributions)
    assert all(a["via"] != "policy" for a in r.extra["impact"]["affected"])


def test_impact_unowned_path_non_blocking(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_impact(context_map_repo, paths=["docs/readme.md"])
    assert r.status == cm.S_IMPACT_OK and r.exit_code == 0
    assert r.extra["impact"]["unowned_paths"] == ["docs/readme.md"]
    assert r.extra["impact"]["affected"] == []


def test_impact_is_deterministic(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    a = cm.cmd_impact(context_map_repo, paths=["src/config/x.py", "src/api/y.py"])
    b = cm.cmd_impact(context_map_repo, paths=["src/api/y.py", "src/config/x.py"])
    assert a.extra == b.extra


def test_affected_is_cycle_safe() -> None:
    # A cyclic reverse graph (a<->b) must terminate and still attribute every id.
    ctxs = [_ctx("a", ["a/**"], ["b"]), _ctx("b", ["b/**"], ["a"])]
    out = cm._affected(ctxs, ["a/x"])
    assert set(out["affected"]) == {"a", "b"}
    assert out["unbounded"] is None


def test_impact_catch_all_owner_is_unbounded(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "root", "match": ["**"], "reads": {"base": ["."]}}]})
    r = cm.cmd_impact(context_map_repo, paths=["anything/here.py"])
    assert r.status == cm.S_UNBOUNDED_EXPANSION and r.exit_code == 1


def test_impact_bounded_flag_true_on_normal(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_impact(context_map_repo, paths=["src/api/x.py"])
    assert r.extra["impact"]["bounded"] is True


def test_impact_empty_paths_is_ok_empty(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_impact(context_map_repo, paths=[])
    assert r.status == cm.S_IMPACT_OK and r.extra["impact"]["affected"] == []


def test_impact_fail_closed_on_invalid_map(context_map_repo: Path) -> None:
    write_map(context_map_repo, "schema_version: 1\ncontexts: [not-a-mapping]\n")
    r = cm.cmd_impact(context_map_repo, paths=["x"])
    assert r.cls == outcome.GATE_REJECTION and r.exit_code == 1


# ---------------------------------------------------------------------------
# Plan-topology validation (R4, SC-004)
# ---------------------------------------------------------------------------

_PLAN = "**SpecOps-Contexts**: {ids}\n{paths}\n"


def _plan(ids: str, paths: str = "") -> str:
    return _PLAN.format(ids=ids, paths=paths)


def test_plan_check_ok(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_plan_check(context_map_repo,
                          plan_text=_plan("api, config", "`src/api/h.py` (modify)"))
    assert r.status == cm.S_PLAN_CHECK_OK and r.exit_code == 0
    assert "api" in r.extra["read_sets"]


def test_plan_check_no_map_is_pass(context_map_repo: Path) -> None:
    r = cm.cmd_plan_check(context_map_repo, plan_text=_plan("api"))
    assert r.status == cm.S_NO_MAP and r.exit_code == 0


def test_plan_check_missing_declaration_blocks(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_plan_check(context_map_repo, plan_text="no declaration here\n")
    assert r.status == cm.S_MISSING_DECLARATION and r.exit_code == 1


def test_plan_check_unknown_id_blocks(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_plan_check(context_map_repo, plan_text=_plan("api, ghost"))
    assert r.status == cm.S_UNKNOWN_DECLARED_CONTEXT and r.exit_code == 1
    assert "ghost" in r.extra["unknown_context_ids"]


def test_plan_check_undeclared_owner_blocks(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_plan_check(context_map_repo,
                          plan_text=_plan("api", "`src/config/y.py` (modify)"))
    assert r.status == cm.S_UNDECLARED_OWNER and r.exit_code == 1
    assert r.extra["undeclared_owners"][0]["context_id"] == "config"


def test_plan_check_unowned_path_non_blocking(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_plan_check(context_map_repo,
                          plan_text=_plan("api", "`docs/x.md` (create)"))
    assert r.status == cm.S_PLAN_CHECK_OK
    assert r.extra["unowned_paths"] == ["docs/x.md"]


def test_plan_check_existence_agnostic_zero_match_ok(context_map_repo: Path) -> None:
    # A declared create-target under `api` that matches zero files must not fail.
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_plan_check(context_map_repo,
                          plan_text=_plan("api", "`src/api/new_module.py` (create)"))
    assert r.status == cm.S_PLAN_CHECK_OK


def test_plan_check_bad_phase_is_usage_error(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_plan_check(context_map_repo, plan_text=_plan("api"), phase="bogus")
    assert r.status == cm.S_USAGE_ERROR and r.exit_code == 2


# ---------------------------------------------------------------------------
# parse_plan_context_ids (R4)
# ---------------------------------------------------------------------------

def test_parse_context_ids_variants() -> None:
    parse = speckit.parse_plan_context_ids
    assert parse("**SpecOps-Contexts**: a, b-c, d/e") == ["a", "b-c", "d/e"]
    assert parse("- SpecOps-Contexts: x, x, y") == ["x", "y"]
    assert speckit.parse_plan_context_ids("nothing here") == []


# ---------------------------------------------------------------------------
# Stale detection (R8, SC-005)
# ---------------------------------------------------------------------------

def test_stale_reports_zero_match_patterns(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    # Only src/config/* is tracked → api and web patterns are stale.
    r = cm.cmd_stale(context_map_repo, ["src/config/a.py"])
    assert r.status == cm.S_STALE_FOUND and r.exit_code == 1
    assert [s["context_id"] for s in r.extra["stale"]] == ["api", "web"]


def test_stale_ok_when_all_match(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = cm.cmd_stale(context_map_repo,
                     ["src/api/a.py", "src/web/b.py", "src/config/c.py"])
    assert r.status == cm.S_STALE_OK and r.exit_code == 0


def test_stale_deterministic(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    a = cm.cmd_stale(context_map_repo, ["src/config/a.py"])
    b = cm.cmd_stale(context_map_repo, ["src/config/a.py"])
    assert a.extra == b.extra


def test_stale_no_map_is_pass(context_map_repo: Path) -> None:
    r = cm.cmd_stale(context_map_repo, ["anything"])
    assert r.status == cm.S_NO_MAP and r.exit_code == 0


# ---------------------------------------------------------------------------
# provenance_for (R6, SC-006)
# ---------------------------------------------------------------------------

def test_provenance_present(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    prov = cm.provenance_for(context_map_repo, ["src/config/x.py"])
    assert prov["map"] == "present"
    assert prov["digest"] == cm.map_digest(context_map_repo)
    assert prov["context_ids"] == ["api", "config", "web"]
    assert prov["output_version"] == cm.OUTPUT_VERSION


def test_provenance_no_map(context_map_repo: Path) -> None:
    assert cm.provenance_for(context_map_repo, ["x"]) == {"map": "none"}


def test_provenance_invalid_map(context_map_repo: Path) -> None:
    write_map(context_map_repo, "schema_version: 1\ncontexts: [oops]\n")
    assert cm.provenance_for(context_map_repo, ["x"]) == {"map": "invalid"}
