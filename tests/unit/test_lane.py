"""Unit tests for the lightweight lane record + lifecycle (Feature 013).

Covers the record invariants, eligibility/start, status, check, attest, fail-closed
close (retrospective + evidence), and lossless promotion (commit-preservation).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from specops import lane, outcome
from specops.errors import LedgerParseError, SpecopsError
from tests.conftest import git


def _commit(root: Path, rel: str, content: str, msg: str) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    git(root, "add", "-A")
    git(root, "commit", "-m", msg)
    return git(root, "rev-parse", "HEAD")


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
    before = set(git(feat, "rev-list", "HEAD").splitlines())
    res = lane.cmd_promote(feat, reason="scope-growth")
    assert res.cls == outcome.PASS, res.human
    after = set(git(feat, "rev-list", "HEAD").splitlines())
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


# --- review-fix regressions -------------------------------------------------

def test_close_blocks_on_dirty_product_tree(feat: Path):
    """Findings 1/2: an uncommitted product change must block close (fail-closed)."""
    _start(feat)
    _commit(feat, "src/util.py", "u = 1\n", "tweak")
    lane.cmd_attest(feat, root_cause="clear", public_contract="clear")
    (feat / "src" / "leftover.py").write_text("secret = 1\n")  # uncommitted product file
    res = lane.cmd_close(feat)
    assert res.cls == outcome.GATE_REJECTION
    assert res.extra["uncommitted"] >= 1


def test_close_ignores_untracked_methodology_dir(feat: Path):
    """Findings 1/2 fix must not false-block: an untracked specs/<feature>/ (the lane's own
    lane.yaml, reported by git as a collapsed '?? specs/') is methodology state, not a dirty
    product tree. Commit only the product file so methodology files stay untracked."""
    _start(feat)
    (feat / "src").mkdir(exist_ok=True)
    (feat / "src" / "x.py").write_text("x = 1\n")
    git(feat, "add", "src/x.py")  # selective add — do NOT sweep specs/ or specops.json
    git(feat, "commit", "-m", "product only")
    lane.cmd_attest(feat, root_cause="clear", public_contract="clear")
    res = lane.cmd_close(feat)
    assert res.cls == outcome.PASS, res.human


def test_check_fails_closed_on_unresolvable_baseline(feat: Path):
    """Finding 3: an orphaned baseline must fail closed, not report 'nothing detected'."""
    _start(feat)
    feature_dir = feat / "specs" / "013-lane"
    data = lane.load(feature_dir)
    data["baseline"] = "deadbeef" * 5  # a SHA that does not resolve
    lane.save(feature_dir, data)
    with pytest.raises(LedgerParseError):
        lane.cmd_check(feat, staged=False)


def test_promote_fails_closed_on_diverged_baseline(feat: Path):
    """Finding 4: a baseline that is not an ancestor of HEAD must not promote silently."""
    _start(feat)
    _commit(feat, "src/a.py", "a = 1\n", "c1")
    feature_dir = feat / "specs" / "013-lane"
    data = lane.load(feature_dir)
    data["baseline"] = "deadbeef" * 5
    lane.save(feature_dir, data)
    with pytest.raises(LedgerParseError):
        lane.cmd_promote(feat, reason="scope-growth")
    assert not (feature_dir / "status.yaml").exists()  # no partial ledger


def test_check_does_not_flag_a_rename_as_destructive(feat: Path):
    """Finding 5: an ordinary file rename must not trip the destructive category."""
    _commit(feat, "src/old_name.py", "value = 1\n", "seed")
    _start(feat)
    git(feat, "mv", "src/old_name.py", "src/new_name.py")
    git(feat, "commit", "-m", "rename")
    res = lane.cmd_check(feat, staged=False)
    assert res.cls == outcome.PASS, res.extra


def test_promote_rejects_invalid_reason(feat: Path):
    """Finding 9: --reason must be validated against the documented enum."""
    _start(feat)
    with pytest.raises(SpecopsError):
        lane.cmd_promote(feat, reason="because")


def test_promote_creates_spec_stub(feat: Path):
    """Finding 7: promotion lands at PLAN and must leave a spec.md for the plan phase."""
    _start(feat)
    _commit(feat, "src/a.py", "a = 1\n", "c1")
    lane.cmd_promote(feat, reason="scope-growth")
    spec = feat / "specs" / "013-lane" / "spec.md"
    assert spec.is_file()
    assert "Promoted from the lightweight lane" in spec.read_text()


def test_flag_then_clear_supersedes_but_flag_only_blocks(feat: Path):
    """Finding 6: the latest attestation per category governs; a lone flag still blocks."""
    _start(feat)
    _commit(feat, "src/util.py", "u = 1\n", "tweak")
    # A lone flag blocks close.
    lane.cmd_attest(feat, root_cause="flag", public_contract="clear")
    blocked = lane.cmd_close(feat)
    assert blocked.cls == outcome.GATE_REJECTION
    assert "root-cause" in blocked.extra["unresolved_attestations"]
    # Re-attesting clear (after addressing it) supersedes and allows close.
    lane.cmd_attest(feat, root_cause="clear", public_contract="clear")
    ok = lane.cmd_close(feat)
    assert ok.cls == outcome.PASS, ok.human


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


# --- Feature 018: lane JSON envelope conformance (SC-001) -------------------


def _lane_cli(root: Path, *args: str):
    """Invoke the lane CLI in *root* (the emit path is where the envelope is built)."""
    import os

    from typer.testing import CliRunner

    from specops.cli import app

    runner = CliRunner()
    cwd = os.getcwd()
    os.chdir(root)
    try:
        return runner.invoke(app, list(args))
    finally:
        os.chdir(cwd)


def test_lane_json_carries_output_version_and_status(feat: Path) -> None:
    """The one sanctioned delta: lane ``--json`` gains the standard envelope fields
    (``output_version`` + top-level ``status``) that every other family already emits.
    Additive only — the pre-existing keys are unchanged."""
    result = _lane_cli(
        feat, "lane", "start", "--answers", ",".join(lane.ELIGIBILITY_CRITERIA), "--json"
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["output_version"] == lane.OUTPUT_VERSION
    assert payload["status"] == outcome.OK
    # additive: the envelope keys lane already emitted stay exactly as before
    assert payload["command"] == "lane-start"
    assert payload["outcome"] == "ok"
    assert payload["class"] == "pass"
    assert payload["lane_id"] == "013-lane"


def test_lane_json_status_is_blocked_on_gate_rejection(feat: Path) -> None:
    """A gate-rejection lane result carries status=blocked in the envelope."""
    result = _lane_cli(feat, "lane", "start", "--answers", "small", "--json")
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == outcome.BLOCKED
    assert payload["class"] == "gate-rejection"
    assert payload["output_version"] == lane.OUTPUT_VERSION
