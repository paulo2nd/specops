"""Unit tests for the Context Map engine (Feature 008)."""
from __future__ import annotations

from pathlib import Path

from specops import contextmap as cm
from tests.conftest import load_map_fixture, write_map

# ---------------------------------------------------------------------------
# Version classification & migration scaffold (SC-010, T004)
# ---------------------------------------------------------------------------


def test_classify_version_range() -> None:
    assert cm.classify(1) == cm.VERSION_CURRENT
    assert cm.classify(2) == cm.VERSION_TOO_NEW
    assert cm.classify(0) == cm.VERSION_UNSUPPORTED
    assert cm.classify("1") == cm.VERSION_UNSUPPORTED
    assert cm.classify(True) == cm.VERSION_UNSUPPORTED  # bool is not a version


def test_migrate_to_current_is_identity_for_v1() -> None:
    data = {"schema_version": 1, "contexts": []}
    assert cm.migrate_to_current(data) == data


def test_unsupported_version_rejected(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("unsupported_version.yaml"))
    vr = cm.validate(context_map_repo)
    assert vr.status == cm.S_UNSUPPORTED_VERSION
    assert vr.diagnostics[0]["code"] == "unsupported_schema_version"


# ---------------------------------------------------------------------------
# Five-state classification (SC-005, T005)
# ---------------------------------------------------------------------------


def test_state_absent(context_map_repo: Path) -> None:
    assert cm.validate(context_map_repo).status == cm.S_NO_MAP


def test_state_malformed(context_map_repo: Path) -> None:
    write_map(context_map_repo, "schema_version: 1\ncontexts: [oops\n")  # bad YAML
    assert cm.validate(context_map_repo).status == cm.S_MALFORMED


def test_state_malformed_non_mapping_root(context_map_repo: Path) -> None:
    write_map(context_map_repo, "- just\n- a\n- list\n")
    assert cm.validate(context_map_repo).status == cm.S_MALFORMED


def test_state_empty_valid(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("empty.yaml"))
    assert cm.validate(context_map_repo).status == cm.S_EMPTY_VALID


def test_state_valid(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    vr = cm.validate(context_map_repo)
    assert vr.status == cm.S_VALID
    assert [c.id for c in (vr.contexts or [])] == ["api", "api-auth", "config"]


# ---------------------------------------------------------------------------
# Validation defect classes, one-pass (SC-002, SC-003, T011)
# ---------------------------------------------------------------------------


def _codes(vr: cm.ValidateResult) -> set[str]:
    return {d["code"] for d in vr.diagnostics}


def test_defect_invalid_path_pattern(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "a", "match": [""]}]})
    vr = cm.validate(context_map_repo)
    assert vr.status == cm.S_SCHEMA_INVALID
    assert "invalid_path_pattern" in _codes(vr)


def test_defect_unsafe_traversal(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "a", "match": ["../../etc/**"]}]})
    assert "unsafe_path_traversal" in _codes(cm.validate(context_map_repo))


def test_defect_absolute_path_is_traversal(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "a", "match": ["/etc/**"]}]})
    assert "unsafe_path_traversal" in _codes(cm.validate(context_map_repo))


def test_defect_duplicate_id(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["src/a/**"]},
        {"id": "a", "match": ["src/b/**"]},
    ]})
    assert "duplicate_context_id" in _codes(cm.validate(context_map_repo))


def test_defect_ambiguous_ownership(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["src/shared/**"]},
        {"id": "b", "match": ["src/shared/**"]},
    ]})
    assert "ambiguous_ownership" in _codes(cm.validate(context_map_repo))


def test_defect_dangling_dependency(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["src/a/**"], "dependencies": ["ghost"]},
    ]})
    assert "dangling_dependency" in _codes(cm.validate(context_map_repo))


def test_defect_dependency_cycle(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["src/a/**"], "dependencies": ["b"]},
        {"id": "b", "match": ["src/b/**"], "dependencies": ["a"]},
    ]})
    vr = cm.validate(context_map_repo)
    assert "dependency_cycle" in _codes(vr)
    # participating ids reported deterministically
    cyc = next(d for d in vr.diagnostics if d["code"] == "dependency_cycle")
    assert "a" in cyc["message"] and "b" in cyc["message"]


def test_validation_reports_all_defects_one_pass(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["../x/**"], "dependencies": ["ghost"]},
        {"id": "a", "match": ["src/b/**"]},
    ]})
    codes = _codes(cm.validate(context_map_repo))
    assert {"unsafe_path_traversal", "dangling_dependency", "duplicate_context_id"} <= codes


def test_gates_and_risk_structural_only(context_map_repo: Path) -> None:
    # well-formed gate id + string-keyed risk map is valid; missing files not checked
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["does/not/exist/**"], "gates": ["some-gate"],
         "risk": {"tier": "low"}},
    ]})
    assert cm.validate(context_map_repo).status == cm.S_VALID


# ---------------------------------------------------------------------------
# Specificity comparator (SC-007, SC-014, T006)
# ---------------------------------------------------------------------------


def test_specificity_prefix_beats_broader() -> None:
    assert cm._specificity("src/api/auth/**") > cm._specificity("src/api/**")


def test_specificity_fewer_wildcards_wins_on_equal_prefix() -> None:
    # "src/**" (1 wildcard) vs "src/**/*.py" (2 wildcards): equal literal prefix
    a = cm._specificity("src/**")
    b = cm._specificity("src/**/*.py")
    assert a[0] == b[0] and a > b


def test_glob_matching() -> None:
    assert cm._matches("src/api/**", "src/api/auth/login.py")
    assert cm._matches("**/*.py", "src/a.py")
    assert cm._matches("src/**/*.py", "src/api/a.py")
    assert not cm._matches("src/api/**", "src/config/x.py")


# ---------------------------------------------------------------------------
# Resolution determinism, selection, fallback (SC-001, SC-007, SC-012)
# ---------------------------------------------------------------------------


def _valid_repo(repo: Path) -> Path:
    write_map(repo, load_map_fixture("valid.yaml"))
    return repo


def test_resolution_is_deterministic(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r1 = cm.cmd_resolve(context_map_repo, path="src/api/auth/x.py", ctx_id=None, phase="plan")
    r2 = cm.cmd_resolve(context_map_repo, path="src/api/auth/x.py", ctx_id=None, phase="plan")
    assert r1.status == cm.S_RESOLVED
    assert r1.extra == r2.extra  # byte-for-byte identical payload


def test_most_specific_wins(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r = cm.cmd_resolve(context_map_repo, path="src/api/auth/login.py", ctx_id=None, phase=None)
    assert r.extra["package"]["context_id"] == "api-auth"


def test_resolve_by_id(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r = cm.cmd_resolve(context_map_repo, path=None, ctx_id="api", phase=None)
    assert r.status == cm.S_RESOLVED and r.extra["package"]["context_id"] == "api"


def test_unknown_id_is_no_match(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r = cm.cmd_resolve(context_map_repo, path=None, ctx_id="ghost", phase=None)
    assert r.status == cm.S_NO_MATCH


def test_path_no_match(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r = cm.cmd_resolve(context_map_repo, path="unrelated/x", ctx_id=None, phase=None)
    assert r.status == cm.S_NO_MATCH


def test_phase_fallback_to_base(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r = cm.cmd_resolve(context_map_repo, path="src/api/x.py", ctx_id=None, phase="implement")
    pkg = r.extra["package"]
    assert pkg["read_set_source"] == "base"
    assert pkg["read_set"] == ["src/api/**"]


def test_phase_specific_read_set(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r = cm.cmd_resolve(context_map_repo, path="src/api/x.py", ctx_id=None, phase="plan")
    assert r.extra["package"]["read_set_source"] == "phase"


def test_no_base_yields_empty(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["src/a/**"], "reads": {"plan": ["docs/a.md"]}},
    ]})
    r = cm.cmd_resolve(context_map_repo, path="src/a/x", ctx_id=None, phase="implement")
    pkg = r.extra["package"]
    assert pkg["read_set"] == [] and pkg["read_set_source"] == "empty"


# ---------------------------------------------------------------------------
# Dependency expansion (SC-011) and cycle-safety (SC-008)
# ---------------------------------------------------------------------------


def test_expanded_read_set_dedup_order_attrib(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["src/a/**"], "reads": {"base": ["src/a/x", "shared/z"]},
         "dependencies": ["b", "c"]},
        {"id": "b", "match": ["src/b/**"], "reads": {"base": ["src/b/y", "shared/z"]}},
        {"id": "c", "match": ["src/c/**"], "reads": {"base": ["src/c/w"]}},
    ]})
    r = cm.cmd_resolve(context_map_repo, path=None, ctx_id="a", phase=None)
    exp = r.extra["package"]["expanded_read_set"]
    # dedup keeps first occurrence (shared/z via a, not repeated via b)
    assert exp == [
        {"path": "src/a/x", "via": "a"},
        {"path": "shared/z", "via": "a"},
        {"path": "src/b/y", "via": "a->b"},
        {"path": "src/c/w", "via": "a->c"},
    ]


def test_expansion_cycle_safe_does_not_hang(context_map_repo: Path) -> None:
    # A validation-invalid cycle still must not hang the expansion engine.
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["src/a/**"], "reads": {"base": ["a"]}, "dependencies": ["b"]},
        {"id": "b", "match": ["src/b/**"], "reads": {"base": ["b"]}, "dependencies": ["a"]},
    ]})
    from specops.contextmap import Context, _build_expanded
    a = Context("a", ["src/a/**"], {"base": ["a"]}, None, ["b"], [], {}, 0)
    b = Context("b", ["src/b/**"], {"base": ["b"]}, None, ["a"], [], {}, 1)
    expanded, edges = _build_expanded(a, {"a": a, "b": b}, None)
    assert [e["path"] for e in expanded] == ["a", "b"]  # each visited once


# ---------------------------------------------------------------------------
# Reason trace (SC-014, T022)
# ---------------------------------------------------------------------------


def test_explain_deciding_dimension_prefix(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r = cm.cmd_explain(context_map_repo, path="src/api/auth/x.py", ctx_id=None, phase=None)
    trace = r.extra["trace"]
    assert trace["selected"]["context_id"] == "api-auth"
    assert trace["selected"]["deciding_dimension"] == "literal_prefix"
    assert [c["context_id"] for c in trace["candidates"]] == ["api-auth", "api"]


def test_explain_only_candidate(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    r = cm.cmd_explain(context_map_repo, path="src/config/x", ctx_id=None, phase=None)
    assert r.extra["trace"]["selected"]["deciding_dimension"] == "only_candidate"


def test_explain_is_deterministic(context_map_repo: Path) -> None:
    _valid_repo(context_map_repo)
    a = cm.cmd_explain(context_map_repo, path="src/api/auth/x.py", ctx_id=None, phase=None)
    b = cm.cmd_explain(context_map_repo, path="src/api/auth/x.py", ctx_id=None, phase=None)
    assert a.extra == b.extra


# ---------------------------------------------------------------------------
# Fail-closed + absent-map + read-only (SC-003, SC-004)
# ---------------------------------------------------------------------------


def test_resolve_fail_closed_on_invalid_map(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "a", "match": ["../x/**"]}]})
    r = cm.cmd_resolve(context_map_repo, path="whatever", ctx_id=None, phase=None)
    assert r.status == cm.S_SCHEMA_INVALID
    assert "package" not in r.extra  # no package emitted


def test_absent_map_no_write(context_map_repo: Path) -> None:
    for fn in (
        lambda: cm.cmd_validate(context_map_repo),
        lambda: cm.cmd_resolve(context_map_repo, path="x", ctx_id=None, phase=None),
        lambda: cm.cmd_explain(context_map_repo, path="x", ctx_id=None, phase=None),
    ):
        assert fn().status == cm.S_NO_MAP
    assert not cm.map_path(context_map_repo).exists()  # nothing created


# ---------------------------------------------------------------------------
# init idempotency & atomicity (SC-009)
# ---------------------------------------------------------------------------


def test_init_creates_then_idempotent(context_map_repo: Path) -> None:
    r1 = cm.cmd_init(context_map_repo)
    assert r1.status == cm.S_CREATED and cm.map_path(context_map_repo).exists()
    original = cm.map_path(context_map_repo).read_text(encoding="utf-8")
    r2 = cm.cmd_init(context_map_repo)
    assert r2.status == cm.S_ALREADY_EXISTS
    assert cm.map_path(context_map_repo).read_text(encoding="utf-8") == original  # unmodified


def test_init_requires_specify_dir(tmp_git_repo: Path) -> None:
    assert cm.cmd_init(tmp_git_repo).status == cm.S_USAGE_ERROR


def test_init_output_is_schema_valid(context_map_repo: Path) -> None:
    cm.cmd_init(context_map_repo)
    assert cm.validate(context_map_repo).status == cm.S_VALID


# ---------------------------------------------------------------------------
# Code-review regression fixes (C1–C10)
# ---------------------------------------------------------------------------


def test_c1_non_utf8_map_is_malformed_not_crash(context_map_repo: Path) -> None:
    # Latin-1 accented byte is invalid UTF-8; must be reported, not raise.
    cm.map_path(context_map_repo).write_bytes(b"schema_version: 1\n# caf\xe9\ncontexts: []\n")
    assert cm.validate(context_map_repo).status == cm.S_MALFORMED


def test_c2_ill_typed_empty_reads_is_schema_invalid(context_map_repo: Path) -> None:
    # `reads: []` is the wrong type (should be a mapping) and must NOT coerce to {}.
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "a", "match": ["src/a/**"], "reads": []}]})
    vr = cm.validate(context_map_repo)
    assert vr.status == cm.S_SCHEMA_INVALID
    assert any(d["field"] == "reads" for d in vr.diagnostics)


def test_c2_ill_typed_empty_dependencies_is_schema_invalid(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "a", "match": ["src/a/**"], "dependencies": {}}]})
    assert cm.validate(context_map_repo).status == cm.S_SCHEMA_INVALID


def test_c3_unknown_phase_is_usage_error(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    r = cm.cmd_resolve(context_map_repo, path="src/api/x.py", ctx_id=None, phase="paln")
    assert r.status == cm.S_USAGE_ERROR
    e = cm.cmd_explain(context_map_repo, path="src/api/x.py", ctx_id=None, phase="paln")
    assert e.status == cm.S_USAGE_ERROR


def test_c3_known_phase_still_works(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    r = cm.cmd_resolve(context_map_repo, path="src/api/x.py", ctx_id=None, phase="plan")
    assert r.status == cm.S_RESOLVED


def test_c4_missing_template_no_crash(context_map_repo: Path, monkeypatch) -> None:
    monkeypatch.setattr(cm, "_TEMPLATE", Path("/no/such/template.yaml"))
    r = cm.cmd_init(context_map_repo)
    assert r.status == cm.S_USAGE_ERROR
    assert not cm.map_path(context_map_repo).exists()  # nothing written


def test_c5_posix_colon_not_flagged_as_traversal(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "a", "match": ["a:b/**"]}]})
    assert cm.validate(context_map_repo).status == cm.S_VALID


def test_c5_windows_drive_still_flagged(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1,
              "contexts": [{"id": "a", "match": ["C:/win/**"]}]})
    assert "unsafe_path_traversal" in _codes(cm.validate(context_map_repo))


def test_c6_equal_specificity_overlap_flagged_at_validate(context_map_repo: Path) -> None:
    # Different patterns, equal specificity, overlapping paths → validate must reject
    # (previously validate said 'valid' while resolve rejected as ambiguous).
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "a", "match": ["src/api/*.py"]},
        {"id": "b", "match": ["src/api/*"]},
    ]})
    assert "ambiguous_ownership" in _codes(cm.validate(context_map_repo))


def test_c6_valid_map_not_false_flagged(context_map_repo: Path) -> None:
    # Different specificity (nested) must NOT be flagged as ambiguous.
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    assert cm.validate(context_map_repo).status == cm.S_VALID


def test_c7_migrate_is_on_the_validate_path(context_map_repo: Path, monkeypatch) -> None:
    calls: list[dict] = []

    def spy(data: dict) -> dict:
        calls.append(data)
        return data

    monkeypatch.setattr(cm, "migrate_to_current", spy)
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    cm.validate(context_map_repo)
    assert calls, "migrate_to_current must run on the validate path"


def test_c10_explain_returns_dependency_edges(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    r = cm.cmd_explain(context_map_repo, path=None, ctx_id="api", phase=None)
    assert {"from": "api", "to": "config"} in r.extra["trace"]["dependency_edges"]
