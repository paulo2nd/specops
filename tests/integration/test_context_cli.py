"""Integration tests for the `specops context` CLI (Feature 008)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from specops.cli import app
from tests.conftest import load_map_fixture, write_map

runner = CliRunner()


def _run(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, ["context", *args])
    finally:
        os.chdir(cwd)


def _json(result) -> dict:
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# init (SC-009, SC-013)
# ---------------------------------------------------------------------------


def test_init_idempotent(context_map_repo: Path) -> None:
    r1 = _run(context_map_repo, "init", "--json")
    assert r1.exit_code == 0 and _json(r1)["status"] == "created"
    r2 = _run(context_map_repo, "init", "--json")
    assert r2.exit_code == 0 and _json(r2)["status"] == "already_exists"


def test_init_not_speckit_repo_usage_error(tmp_git_repo: Path) -> None:
    r = _run(tmp_git_repo, "init")
    assert r.exit_code == 2  # usage error


# ---------------------------------------------------------------------------
# Five map states, each distinguishable (SC-005)
# ---------------------------------------------------------------------------


def test_five_states(context_map_repo: Path) -> None:
    # absent
    assert _json(_run(context_map_repo, "validate", "--json"))["status"] == "no_map_present"
    # malformed
    write_map(context_map_repo, "contexts: [oops\n")
    assert _json(_run(context_map_repo, "validate", "--json"))["status"] == "malformed"
    # schema-invalid
    write_map(context_map_repo, {"schema_version": 1, "contexts": [{"id": "a", "match": []}]})
    assert _json(_run(context_map_repo, "validate", "--json"))["status"] == "schema_invalid"
    # empty-valid
    write_map(context_map_repo, load_map_fixture("empty.yaml"))
    assert _json(_run(context_map_repo, "validate", "--json"))["status"] == "empty_valid"
    # valid
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    assert _json(_run(context_map_repo, "validate", "--json"))["status"] == "valid"


# ---------------------------------------------------------------------------
# Exit-code matrix (SC-013)
# ---------------------------------------------------------------------------


def test_exit_code_matrix(context_map_repo: Path) -> None:
    # absent map → 0
    assert _run(context_map_repo, "validate").exit_code == 0
    # valid → 0
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    assert _run(context_map_repo, "validate").exit_code == 0
    assert _run(context_map_repo, "resolve", "--id", "api").exit_code == 0
    # no-match → 0
    assert _run(context_map_repo, "resolve", "--path", "no/where").exit_code == 0
    # invalid map → 1
    write_map(context_map_repo,
              {"schema_version": 1, "contexts": [{"id": "a", "match": ["/abs/**"]}]})
    assert _run(context_map_repo, "validate").exit_code == 1
    # unsupported version → 1
    write_map(context_map_repo, load_map_fixture("unsupported_version.yaml"))
    assert _run(context_map_repo, "validate").exit_code == 1
    # usage error → 2
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    assert _run(context_map_repo, "resolve").exit_code == 2
    assert _run(context_map_repo, "resolve", "--path", "a", "--id", "b").exit_code == 2


# ---------------------------------------------------------------------------
# Selector contract (SC-015)
# ---------------------------------------------------------------------------


def test_selector_contract(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    assert _json(_run(context_map_repo, "resolve", "--path", "a", "--id", "b", "--json"))[
        "status"] == "usage_error"
    assert _json(_run(context_map_repo, "resolve", "--json"))["status"] == "usage_error"
    assert _json(_run(context_map_repo, "resolve", "--id", "ghost", "--json"))[
        "status"] == "no_matching_context"


# ---------------------------------------------------------------------------
# Absent map across all read-only commands, no writes (SC-004)
# ---------------------------------------------------------------------------


def test_absent_map_all_commands(context_map_repo: Path) -> None:
    for cmd in ("validate", "resolve", "explain"):
        args = [cmd, "--json"] + (["--path", "x"] if cmd != "validate" else [])
        res = _run(context_map_repo, *args)
        assert res.exit_code == 0
        assert _json(res)["status"] == "no_map_present"
    from specops import contextmap
    assert not contextmap.map_path(context_map_repo).exists()


# ---------------------------------------------------------------------------
# Stable JSON shape (SC-006)
# ---------------------------------------------------------------------------


def test_json_shape_stable(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    a = _run(context_map_repo, "resolve", "--path", "src/api/auth/x.py", "--json").stdout
    b = _run(context_map_repo, "resolve", "--path", "src/api/auth/x.py", "--json").stdout
    assert a == b  # byte-for-byte identical
    obj = json.loads(a)
    assert set(obj) >= {"command", "outcome", "class", "status", "output_version", "package"}
    assert obj["output_version"] == 1
    pkg = obj["package"]
    assert set(pkg) == {"context_id", "phase", "read_set", "read_set_source",
                        "dependencies", "expanded_read_set", "gates", "risk"}


def test_explain_json_trace_shape(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    obj = _json(_run(context_map_repo, "explain", "--path", "src/api/auth/x.py", "--json"))
    assert obj["status"] == "resolved"
    trace = obj["trace"]
    assert set(trace) == {"input", "candidates", "selected", "read_set_source",
                          "dependency_edges", "gates"}
    assert trace["selected"]["deciding_dimension"] == "literal_prefix"


def test_unknown_phase_exit_2(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    r = _run(context_map_repo, "resolve", "--path", "src/api/x.py", "--phase", "paln")
    assert r.exit_code == 2


def test_human_output_concise(context_map_repo: Path) -> None:
    write_map(context_map_repo, load_map_fixture("valid.yaml"))
    res = _run(context_map_repo, "resolve", "--id", "api")
    assert res.exit_code == 0
    assert res.stdout.strip() == "resolve: api"  # single concise line (FR-019)
