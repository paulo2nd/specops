"""Integration tests for the lightweight lane via the Typer CLI (Feature 013).

Drives the `specops lane` primitives end-to-end (start → check → attest → close, and
promotion) — this is what the agent/workflow engine does at runtime; the human answers
only native gates (FR-022). Covers US1–US3, US5 (bundling), and the safe-degrade/offline
guarantee (FR-019/SC-006, T037).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from specops.cli import app

runner = CliRunner()


def _run(root: Path, *args: str):
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, ["lane", *args])
    finally:
        os.chdir(cwd)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout.strip()


def _commit(root: Path, rel: str, content: str, msg: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", msg)


def _feature(tmp_git_repo: Path, *, with_config: bool = True) -> Path:
    root = tmp_git_repo
    (root / ".specify").mkdir(exist_ok=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/013-lane"})
    )
    (root / "specs" / "013-lane").mkdir(parents=True)
    if with_config:
        (root / "specops.json").write_text(
            json.dumps({"test_command": "true", "lint_command": ""})
        )
    return root


_ELIG = "small,reversible,no-high-risk-category"


def test_clean_lane_completes_without_full_artifacts(tmp_git_repo: Path):
    """US1/SC-001: a small change closes with no spec/plan/tasks/status artifacts."""
    root = _feature(tmp_git_repo)
    assert _run(root, "start", "--answers", _ELIG).exit_code == 0
    _commit(root, "src/util.py", "x = 1\n", "small tweak")
    assert _run(root, "check", "--json").exit_code == 0
    attest = _run(root, "attest", "--root-cause", "clear", "--public-contract", "clear")
    assert attest.exit_code == 0
    res = _run(root, "close", "--json")
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["verdict"] == "APPROVED"
    feature_dir = root / "specs" / "013-lane"
    for artifact in ("spec.md", "plan.md", "tasks.md", "status.yaml"):
        assert not (feature_dir / artifact).exists(), artifact
    assert (feature_dir / "retrospective.md").exists()


def test_each_detectable_category_halts(tmp_git_repo: Path):
    """US2/SC-002: each of the four diff-detectable categories exits 1 at `check`."""
    cases = {
        "migration": ("db/migrations/1.sql", "ALTER TABLE t ADD c int;\n"),
        "secret": (".env", "TOKEN=abc\n"),
        "dependency": ("pyproject.toml", "[project]\nname='x'\n"),
    }
    for category, (rel, content) in cases.items():
        root = _feature(_fresh_repo(tmp_git_repo, category))
        assert _run(root, "start", "--answers", _ELIG).exit_code == 0
        _commit(root, rel, content, f"add {category}")
        res = _run(root, "check", "--json")
        assert res.exit_code == 1, category
        assert category in json.loads(res.stdout)["categories"], category


def test_destructive_deletion_halts(tmp_git_repo: Path):
    """US2/SC-002: a file deletion (status D) flags the destructive category."""
    root = _feature(tmp_git_repo)
    _commit(root, "src/old.py", "legacy = 1\n", "seed file to delete")
    assert _run(root, "start", "--answers", _ELIG).exit_code == 0
    _git(root, "rm", "src/old.py")
    _git(root, "commit", "-m", "remove legacy")
    res = _run(root, "check", "--json")
    assert res.exit_code == 1
    assert "destructive" in json.loads(res.stdout)["categories"]


def test_soft_keeps_exit_zero_for_workflow_conditions(tmp_git_repo: Path):
    """The specops-lite workflow branches on `check`/`attest` JSON: --soft must exit 0
    (class in the JSON) so a detection/flag drives the condition, not aborts the step."""
    root = _feature(tmp_git_repo)
    assert _run(root, "start", "--answers", _ELIG).exit_code == 0
    _commit(root, "db/migrations/1.sql", "ALTER TABLE t ADD c int;\n", "risky")
    res = _run(root, "check", "--json", "--soft")
    assert res.exit_code == 0  # soft: never aborts the shell step
    assert json.loads(res.stdout)["class"] == "gate-rejection"
    att = _run(root, "attest", "--root-cause", "flag", "--public-contract", "clear",
               "--json", "--soft")
    assert att.exit_code == 0
    assert json.loads(att.stdout)["class"] == "gate-rejection"


def test_flagged_attestation_halts(tmp_git_repo: Path):
    """US2: a flagged attestation (root-cause or public-contract) exits 1."""
    root = _feature(tmp_git_repo)
    assert _run(root, "start", "--answers", _ELIG).exit_code == 0
    res = _run(root, "attest", "--root-cause", "clear", "--public-contract", "flag", "--json")
    assert res.exit_code == 1
    assert "public-contract" in json.loads(res.stdout)["flagged"]


def test_promote_lands_at_plan_via_cli(tmp_git_repo: Path):
    """US3/SC-003: promotion synthesizes a ledger at PLAN with zero commit loss."""
    root = _feature(tmp_git_repo)
    assert _run(root, "start", "--answers", _ELIG).exit_code == 0
    _commit(root, "src/a.py", "a = 1\n", "c1")
    before = set(_git(root, "rev-list", "HEAD").splitlines())
    res = _run(root, "promote", "--reason", "scope-growth", "--json")
    assert res.exit_code == 0
    assert json.loads(res.stdout)["resumed_phase"] == "PLAN"
    assert set(_git(root, "rev-list", "HEAD").splitlines()) == before
    led = (root / "specs" / "013-lane" / "status.yaml").read_text()
    assert "current_phase: PLAN" in led


def test_bundle_flag_recorded(tmp_git_repo: Path):
    """US5: bundling under explicit confirmation sets the bundle flag."""
    root = _feature(tmp_git_repo)
    res = _run(root, "start", "--answers", _ELIG, "--bundle", "two tweaks", "--json")
    assert res.exit_code == 0
    assert json.loads(res.stdout)["bundled"] is True


def test_safe_degrade_no_context_map_and_offline(tmp_git_repo: Path):
    """FR-019/SC-006 (T037): lane check/close work with no context map present.

    The fixture has no `.specify/specops/context-map.yaml` and runs no network; the
    absence of the optional map must be treated as absent, not a failure.
    """
    root = _feature(tmp_git_repo)
    assert not (root / ".specify" / "specops" / "context-map.yaml").exists()
    assert _run(root, "start", "--answers", _ELIG).exit_code == 0
    _commit(root, "src/util.py", "x = 1\n", "tweak")
    assert _run(root, "check").exit_code == 0
    _run(root, "attest", "--root-cause", "clear", "--public-contract", "clear")
    assert _run(root, "close").exit_code == 0


# --- helpers ---------------------------------------------------------------

def _fresh_repo(base: Path, tag: str) -> Path:
    """Create a sibling git repo so category cases don't share a lane record."""
    root = base.parent / f"{base.name}-{tag}"
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=root, check=True,
                   capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True,
                   capture_output=True)
    (root / "README.md").write_text("# t\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)
    return root
