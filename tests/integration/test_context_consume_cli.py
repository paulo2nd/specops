"""Integration tests for the Feature 009 `context` consumption CLI.

Exercises `context plan-check`, `context impact`, and `context stale` end-to-end
through the Typer app: exit-code/status/`--json` matrix, the Git-default
degenerate cases for impact, and read-only behavior.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from specops.cli import app
from tests.conftest import DEP_GRAPH_MAP, write_map

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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True,
                          text=True).stdout.strip()


# ---------------------------------------------------------------------------
# plan-check (SC-004, SC-007)
# ---------------------------------------------------------------------------

def test_plan_check_ok_json(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    (context_map_repo / "plan.md").write_text(
        "**SpecOps-Contexts**: api, config\n`src/api/h.py` (modify)\n"
    )
    r = _run(context_map_repo, "plan-check", "--plan", "plan.md", "--json")
    assert r.exit_code == 0
    obj = _json(r)
    assert obj["status"] == "plan_check_ok"
    assert obj["output_version"] == 1


def test_plan_check_undeclared_owner_exit1(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    (context_map_repo / "plan.md").write_text(
        "**SpecOps-Contexts**: api\n`src/config/y.py` (modify)\n"
    )
    r = _run(context_map_repo, "plan-check", "--plan", "plan.md")
    assert r.exit_code == 1


def test_plan_check_no_map_exit0(context_map_repo: Path) -> None:
    (context_map_repo / "plan.md").write_text("**SpecOps-Contexts**: api\n")
    r = _run(context_map_repo, "plan-check", "--plan", "plan.md")
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# impact (SC-002, SC-003, SC-007, SC-001)
# ---------------------------------------------------------------------------

def test_impact_explicit_path_json(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = _run(context_map_repo, "impact", "--path", "src/config/x.py", "--json")
    assert r.exit_code == 0
    obj = _json(r)
    assert obj["status"] == "impact_ok"
    ids = {a["context_id"] for a in obj["impact"]["affected"]}
    assert ids == {"config", "api", "web"}


def test_impact_json_byte_identical(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    a = _run(context_map_repo, "impact", "--path", "src/config/x.py", "--json")
    b = _run(context_map_repo, "impact", "--path", "src/config/x.py", "--json")
    assert a.stdout == b.stdout


def test_impact_clean_tree_empty_exit0(context_map_repo: Path) -> None:
    # No --path, clean tree, valid ledger baseline → empty impact, exit 0.
    write_map(context_map_repo, DEP_GRAPH_MAP)
    _git(context_map_repo, "add", "-A")
    _git(context_map_repo, "commit", "-m", "add map")
    head = _git(context_map_repo, "rev-parse", "HEAD")
    feature_dir = context_map_repo / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (context_map_repo / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )
    import yaml
    (feature_dir / "status.yaml").write_text(yaml.dump({
        "schema_version": 3, "revision": 1, "feature": "001-demo",
        "branch": _git(context_map_repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "baseline": head, "current_phase": "IMPLEMENT",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [], "review_cycles": [],
    }))
    r = _run(context_map_repo, "impact", "--json")
    assert r.exit_code == 0
    assert _json(r)["impact"]["affected"] == []


def test_impact_no_repo_no_path_exit2(tmp_path: Path) -> None:
    # Not a Git repo and no --path → usage error (exit 2).
    (tmp_path / ".specify" / "specops").mkdir(parents=True)
    write_map(tmp_path, DEP_GRAPH_MAP)
    r = _run(tmp_path, "impact")
    assert r.exit_code == 2


def test_impact_no_baseline_exit2(context_map_repo: Path) -> None:
    # Git repo but no resolvable ledger baseline and no --path → exit 2.
    write_map(context_map_repo, DEP_GRAPH_MAP)
    r = _run(context_map_repo, "impact")
    assert r.exit_code == 2


# ---------------------------------------------------------------------------
# stale (SC-005, SC-007)
# ---------------------------------------------------------------------------

def test_stale_found_exit1(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    (context_map_repo / "src" / "config").mkdir(parents=True)
    (context_map_repo / "src" / "config" / "c.py").write_text("x=1\n")
    _git(context_map_repo, "add", "src/config/c.py")
    r = _run(context_map_repo, "stale", "--json")
    assert r.exit_code == 1
    obj = _json(r)
    assert obj["status"] == "stale_found"
    assert {s["context_id"] for s in obj["stale"]} == {"api", "web"}


def test_stale_ok_exit0(context_map_repo: Path) -> None:
    write_map(context_map_repo, DEP_GRAPH_MAP)
    for d in ("api", "web", "config"):
        (context_map_repo / "src" / d).mkdir(parents=True)
        (context_map_repo / "src" / d / "f.py").write_text("x=1\n")
        _git(context_map_repo, "add", f"src/{d}/f.py")
    r = _run(context_map_repo, "stale")
    assert r.exit_code == 0


def test_stale_no_map_exit0(context_map_repo: Path) -> None:
    r = _run(context_map_repo, "stale")
    assert r.exit_code == 0
