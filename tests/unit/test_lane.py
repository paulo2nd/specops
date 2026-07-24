"""Unit tests for the lightweight lane record + lifecycle (Feature 013).

Covers the record invariants, eligibility/start, status, check, attest, fail-closed
close (retrospective + evidence), and lossless promotion (commit-preservation).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from specops import lane, outcome
from specops.errors import LedgerParseError, SpecopsError


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout.strip()


def _commit(root: Path, rel: str, content: str, msg: str) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", msg)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture()
def feat(tmp_git_repo: Path) -> Path:
    """A lane-ready repo: feature dir + feature.json + specops.json."""
    root = tmp_git_repo
    (root / ".specify").mkdir(exist_ok=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/013-lane"})
    )
    (root / "specs" / "013-lane").mkdir(parents=True)
    (root / "specops.json").write_text(json.dumps({"test_command": "true", "lint_command": ""}))
    return root


def _start(root: Path, bundle: str | None = None):
    return lane.cmd_start(
        root, answers=list(lane.ELIGIBILITY_CRITERIA), bundle=bundle
    )


# --- record invariants -----------------------------------------------------

def test_validate_rejects_bad_schema():
    with pytest.raises(LedgerParseError):
        lane.validate({"schema_version": 99, "state": "OPEN"})


def test_validate_rejects_open_with_closure():
    with pytest.raises(LedgerParseError):
        lane.validate({"schema_version": 1, "state": "OPEN", "closure": {"x": 1},
                       "promotion": None})


def test_validate_requires_closure_when_closed():
    with pytest.raises(LedgerParseError):
        lane.validate({"schema_version": 1, "state": "CLOSED", "closure": None,
                       "promotion": None})


# --- start / eligibility ---------------------------------------------------

def test_start_creates_open_lane(feat: Path):
    res = _start(feat)
    assert res.cls == outcome.PASS
    feature_dir = feat / "specs" / "013-lane"
    data = lane.load(feature_dir)
    assert data["state"] == "OPEN"
    assert [a["key"] for a in data["eligibility"]["answers"]] == list(lane.ELIGIBILITY_CRITERIA)
    # minimal state: no full ledger created (Q1 / FR-006)
    assert not (feature_dir / "status.yaml").exists()


def test_start_blocks_when_ineligible(feat: Path):
    res = lane.cmd_start(feat, answers=["small"], bundle=None)
    assert res.cls == outcome.GATE_REJECTION
    assert "no-high-risk-category" in res.extra["ineligible"]


def test_start_refuses_when_lane_exists(feat: Path):
    _start(feat)
    with pytest.raises(SpecopsError):
        _start(feat)


def test_start_refuses_when_full_ledger_exists(feat: Path):
    (feat / "specs" / "013-lane" / "status.yaml").write_text("schema_version: 6\n")
    with pytest.raises(SpecopsError):
        _start(feat)


def test_start_records_bundle(feat: Path):
    _start(feat, bundle="two adjacent tweaks")
    data = lane.load(feat / "specs" / "013-lane")
    assert data["eligibility"]["bundled"] is True
    assert data["eligibility"]["bundle_note"] == "two adjacent tweaks"


# --- check -----------------------------------------------------------------

def test_check_clean_passes(feat: Path):
    _start(feat)
    _commit(feat, "src/util.py", "x = 1\n", "small tweak")
    res = lane.cmd_check(feat, staged=False)
    assert res.cls == outcome.PASS
    assert res.extra["detections"] == []


def test_check_flags_migration(feat: Path):
    _start(feat)
    _commit(feat, "db/migrations/003.sql", "ALTER TABLE t ADD c int;\n", "add migration")
    res = lane.cmd_check(feat, staged=False)
    assert res.cls == outcome.GATE_REJECTION
    assert "migration" in res.extra["categories"]


# --- attest ----------------------------------------------------------------

def test_attest_both_clear(feat: Path):
    _start(feat)
    res = lane.cmd_attest(feat, root_cause="clear", public_contract="clear")
    assert res.cls == outcome.PASS
    data = lane.load(feat / "specs" / "013-lane")
    kinds = [d["category"] for d in data["decisions"]]
    assert kinds == ["root-cause", "public-contract"]


def test_attest_flag_blocks(feat: Path):
    _start(feat)
    res = lane.cmd_attest(feat, root_cause="flag", public_contract="clear")
    assert res.cls == outcome.GATE_REJECTION
    assert "root-cause" in res.extra["flagged"]


def test_attest_rejects_bad_value(feat: Path):
    _start(feat)
    with pytest.raises(SpecopsError):
        lane.cmd_attest(feat, root_cause="maybe", public_contract="clear")


# --- close -----------------------------------------------------------------

def test_close_happy_path(feat: Path):
    _start(feat)
    _commit(feat, "src/util.py", "y = 2\n", "small tweak")
    lane.cmd_attest(feat, root_cause="clear", public_contract="clear")
    res = lane.cmd_close(feat)
    assert res.cls == outcome.PASS, res.human
    feature_dir = feat / "specs" / "013-lane"
    data = lane.load(feature_dir)
    assert data["state"] == "CLOSED"
    assert data["closure"]["gate_evidence"]["verdict"] == "APPROVED"
    assert (feature_dir / "retrospective.md").exists()


def test_close_blocks_without_attestation(feat: Path):
    _start(feat)
    _commit(feat, "src/util.py", "z = 3\n", "tweak")
    res = lane.cmd_close(feat)
    assert res.cls == outcome.GATE_REJECTION
    assert set(res.extra["unresolved_attestations"]) == {"root-cause", "public-contract"}


def test_close_blocks_on_unresolved_detection(feat: Path):
    _start(feat)
    _commit(feat, "db/migrations/004.sql", "DROP TABLE t;\n", "risky")
    lane.cmd_attest(feat, root_cause="clear", public_contract="clear")
    res = lane.cmd_close(feat)
    assert res.cls == outcome.GATE_REJECTION
    assert "migration" in res.extra["categories"]


# --- promote ---------------------------------------------------------------

def test_promote_is_lossless_and_lands_at_plan(feat: Path):
    _start(feat)
    _commit(feat, "src/a.py", "a = 1\n", "c1")
    _commit(feat, "src/b.py", "b = 2\n", "c2")
    before = set(_git(feat, "rev-list", "HEAD").splitlines())
    res = lane.cmd_promote(feat, reason="scope-growth")
    assert res.cls == outcome.PASS, res.human
    after = set(_git(feat, "rev-list", "HEAD").splitlines())
    assert before == after  # zero commit loss (P-1)
    feature_dir = feat / "specs" / "013-lane"
    led = yaml.safe_load((feature_dir / "status.yaml").read_text())
    assert led["current_phase"] == "PLAN"
    assert led["promoted_from_lane"] is True
    assert led["lane_provenance"]["lane_id"] == "013-lane"
    assert lane.load(feature_dir)["state"] == "PROMOTED"


def test_promote_twice_blocks(feat: Path):
    _start(feat)
    _commit(feat, "src/a.py", "a = 1\n", "c1")
    lane.cmd_promote(feat, reason="scope-growth")
    res = lane.cmd_promote(feat, reason="scope-growth")
    assert res.cls == outcome.GATE_REJECTION


# --- US4: closure evidence taxonomy + retrospective render -----------------

def test_closure_records_gate_evidence_taxonomy(feat: Path):
    _start(feat)
    _commit(feat, "src/util.py", "u = 1\n", "tweak")
    lane.cmd_attest(feat, root_cause="clear", public_contract="clear")
    lane.cmd_close(feat)
    data = lane.load(feat / "specs" / "013-lane")
    gates = data["closure"]["gate_evidence"]["gates"]
    # Every gate carries the Feature 012 disposition taxonomy.
    for g in gates:
        assert "name" in g and "status" in g
        assert g.get("disposition") in {
            "required", "optional", "skipped", "cached", "failed", "unavailable", None,
        }


def test_retrospective_md_is_rendered_projection(feat: Path):
    _start(feat)
    _commit(feat, "src/util.py", "u = 2\n", "tweak")
    lane.cmd_attest(feat, root_cause="clear", public_contract="clear")
    lane.cmd_close(feat)
    retro = (feat / "specs" / "013-lane" / "retrospective.md").read_text()
    assert "# Retrospective: 013-lane" in retro
    assert "APPROVED" in retro
    # Authoritative state stays in lane.yaml; retrospective is a projection.
    assert "small" in retro  # eligibility basis rendered


# --- US5: bundling combined-set evaluation ---------------------------------

def test_bundle_combined_set_halts_when_one_change_is_risky(feat: Path):
    _start(feat, bundle="two adjacent tweaks")
    _commit(feat, "src/copy.py", "TEXT = 'hi'\n", "tweak one")
    _commit(feat, "db/migrations/9.sql", "ALTER TABLE t ADD c int;\n", "risky tweak two")
    # The whole bundle is evaluated together — the risky change halts it.
    res = lane.cmd_check(feat, staged=False)
    assert res.cls == outcome.GATE_REJECTION
    assert "migration" in res.extra["categories"]
