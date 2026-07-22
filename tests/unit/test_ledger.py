"""Unit tests for the Ledger v2 core (Feature 006): classify, timestamps,
migration, invariants, and the concurrency-safe/stable/atomic save cycle."""
from __future__ import annotations

import copy
from pathlib import Path
from unittest.mock import patch

import pytest

from specops import ledger
from specops.errors import SpecopsError, StaleLedgerError
from tests.conftest import make_v1_ledger, make_v2_ledger

# ---------------------------------------------------------------------------
# classify (FR-001, FR-002) [SC-001]
# ---------------------------------------------------------------------------

def test_classify_absent_is_migratable() -> None:
    assert ledger.classify({"feature": "x"}) == ledger.MIGRATABLE


def test_classify_v1_is_migratable() -> None:
    assert ledger.classify({"schema_version": 1}) == ledger.MIGRATABLE


def test_classify_current() -> None:
    assert ledger.classify({"schema_version": ledger.CURRENT_SCHEMA}) == ledger.CURRENT


def test_classify_v2_is_migratable() -> None:
    # v2 predates the Feature 009 provenance schema (v3) → migratable, not current.
    assert ledger.classify({"schema_version": 2}) == ledger.MIGRATABLE


def test_classify_too_new() -> None:
    assert ledger.classify({"schema_version": 99}) == ledger.TOO_NEW


@pytest.mark.parametrize("sv", [0, -1, "two", 2.0, True])
def test_classify_unsupported(sv: object) -> None:
    assert ledger.classify({"schema_version": sv}) == ledger.UNSUPPORTED


# ---------------------------------------------------------------------------
# timestamps (FR-009, FR-010) [SC-007]
# ---------------------------------------------------------------------------

def test_now_utc_is_tz_aware() -> None:
    assert ledger.now_utc().endswith("+00:00")


def test_to_aware_date_only_to_utc_midnight() -> None:
    assert ledger.to_aware("2026-07-05") == "2026-07-05T00:00:00+00:00"


def test_to_aware_naive_datetime_gets_utc() -> None:
    assert ledger.to_aware("2026-07-05T12:30:00") == "2026-07-05T12:30:00+00:00"


def test_to_aware_offset_normalized_to_utc() -> None:
    assert ledger.to_aware("2026-07-05T09:30:00-03:00") == "2026-07-05T12:30:00+00:00"


def test_to_aware_none_stays_none() -> None:
    assert ledger.to_aware(None) is None


def test_artifact_for_phase() -> None:
    assert ledger.artifact_for_phase("SPECIFY") == "spec.md"
    assert ledger.artifact_for_phase("PLAN") == "plan.md"
    assert ledger.artifact_for_phase("IMPLEMENT") == "tasks.md"
    assert ledger.artifact_for_phase("DONE") == "tasks.md"
    assert ledger.artifact_for_phase(None) == "spec.md"


# ---------------------------------------------------------------------------
# migration (FR-003, FR-004, FR-008, FR-010, FR-028) [SC-001, SC-007]
# ---------------------------------------------------------------------------

def _v1_dict() -> dict:
    return {
        "feature": "001-demo",
        "branch": "main",
        "baseline": "abc1234",
        "created_at": "2026-07-05",
        "updated_at": "2026-07-06",
        "current_phase": "REVIEW",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [
            {"id": "T001", "status": "DONE", "started_commit": "aaa",
             "commits": ["bbb"], "evidence": "CLI_LOG:ok", "completed_at": "2026-07-06"},
        ],
        "review_cycles": [
            {"round": 1, "started_at": "2026-07-06", "completed_at": None, "result": None},
        ],
    }


def test_migrate_backfills_v2_fields() -> None:
    out = ledger.migrate_to_current(_v1_dict())
    assert out["schema_version"] == ledger.CURRENT_SCHEMA
    assert out["revision"] == 1
    assert out["workflow_lane"] == "full"
    assert out["active_artifact"] == "tasks.md"  # REVIEW → tasks.md
    assert out["recovery"]["last_consistent_revision"] == 1
    assert out["recovery"]["last_consistent_at"] == out["updated_at"]
    assert "migrated_from_backup" in out["recovery"]


def test_migrate_preserves_tasks_evidence_and_cycles() -> None:
    src = _v1_dict()
    out = ledger.migrate_to_current(src)
    assert out["tasks"][0]["evidence"] == "CLI_LOG:ok"
    assert out["tasks"][0]["commits"] == ["bbb"]
    assert out["review_cycles"][0]["round"] == 1
    assert out["current_phase"] == "REVIEW"


def test_migrate_converts_every_timestamp_to_aware() -> None:
    out = ledger.migrate_to_current(_v1_dict())
    assert out["created_at"] == "2026-07-05T00:00:00+00:00"
    assert out["updated_at"] == "2026-07-06T00:00:00+00:00"
    assert out["tasks"][0]["completed_at"] == "2026-07-06T00:00:00+00:00"
    assert out["review_cycles"][0]["started_at"] == "2026-07-06T00:00:00+00:00"


def test_migrate_idempotent_on_current() -> None:
    once = ledger.migrate_to_current(_v1_dict())
    twice = ledger.migrate_to_current(once)
    assert twice["schema_version"] == ledger.CURRENT_SCHEMA
    assert twice["revision"] == once["revision"]


def test_migrate_backfills_context_provenance_no_map_marker() -> None:
    # Feature 009: every task and review-cycle record gains the explicit no-map
    # marker (never an omitted field) so a pre-v3 ledger stays unambiguous.
    out = ledger.migrate_to_current(_v1_dict())
    assert out["tasks"][0]["context_provenance"] == {"map": "none"}
    assert out["review_cycles"][0]["context_provenance"] == {"map": "none"}


def test_migrate_refuses_too_new() -> None:
    with pytest.raises(SpecopsError):
        ledger.migrate_to_current({"schema_version": 99})


# ---------------------------------------------------------------------------
# Workflow block (Feature 007, FR-006) — additive within-v2 field [SC-004, SC-007]
# ---------------------------------------------------------------------------

def test_migrate_backfills_workflow_block() -> None:
    out = ledger.migrate_to_current(_v1_dict())
    assert out["workflow"] == {"skipped_steps": []}


def test_ensure_workflow_block_backfills_when_absent() -> None:
    data = {"feature": "x"}
    ledger.ensure_workflow_block(data)
    assert data["workflow"] == {"skipped_steps": []}


def test_ensure_workflow_block_idempotent_and_preserves_entries() -> None:
    entry = {"step": "clarify", "decision": "skip", "at": "2026-07-20T00:00:00+00:00"}
    data = {"workflow": {"skipped_steps": [entry]}}
    ledger.ensure_workflow_block(data)
    ledger.ensure_workflow_block(data)
    assert data["workflow"]["skipped_steps"] == [entry]


def test_ensure_workflow_block_repairs_wrong_shape() -> None:
    data = {"workflow": "oops"}
    ledger.ensure_workflow_block(data)
    assert data["workflow"] == {"skipped_steps": []}


# ---------------------------------------------------------------------------
# invariants (FR-025, FR-026) [SC-003]
# ---------------------------------------------------------------------------

def _valid_v2() -> dict:
    return {
        "schema_version": 2, "revision": 1, "current_phase": "IMPLEMENT",
        "recovery": {"active_task": "T001"},
        "tasks": [
            {"id": "T001", "status": "IN_PROGRESS", "evidence": None},
            {"id": "T000", "status": "DONE", "evidence": "CLI_LOG:ok"},
        ],
        "review_cycles": [],
    }


def test_invariants_valid() -> None:
    assert ledger.validate_invariants(_valid_v2()) == []


def test_invariants_bad_phase() -> None:
    d = _valid_v2()
    d["current_phase"] = "BOGUS"
    assert any("current_phase" in v for v in ledger.validate_invariants(d))


def test_invariants_two_active() -> None:
    d = _valid_v2()
    d["tasks"].append({"id": "T002", "status": "IN_PROGRESS", "evidence": None})
    assert any("IN_PROGRESS" in v for v in ledger.validate_invariants(d))


def test_invariants_done_without_evidence() -> None:
    d = _valid_v2()
    d["tasks"][1]["evidence"] = None
    assert any("without evidence" in v for v in ledger.validate_invariants(d))


def test_invariants_orphan_exempt() -> None:
    d = _valid_v2()
    d["tasks"][1]["evidence"] = None
    d["tasks"][1]["orphaned"] = True  # orphaned DONE-without-evidence is exempt
    assert ledger.validate_invariants(d) == []


def test_invariants_review_rounds_must_increase() -> None:
    d = _valid_v2()
    d["current_phase"] = "REVIEW"
    d["review_cycles"] = [
        {"round": 1, "result": "APPROVED"},
        {"round": 1, "result": None},
    ]
    assert any("strictly increasing" in v for v in ledger.validate_invariants(d))


def test_invariants_at_most_one_open_cycle() -> None:
    d = _valid_v2()
    d["review_cycles"] = [
        {"round": 1, "result": None},
        {"round": 2, "result": None},
    ]
    assert any("open review cycle" in v for v in ledger.validate_invariants(d))


def test_invariants_recovery_active_task_mismatch() -> None:
    d = _valid_v2()
    d["recovery"]["active_task"] = "T999"
    assert any("active_task" in v for v in ledger.validate_invariants(d))


# ---------------------------------------------------------------------------
# revision_of
# ---------------------------------------------------------------------------

def test_revision_of_v1_is_zero() -> None:
    assert ledger.revision_of({"feature": "x"}) == 0


def test_revision_of_reads_int() -> None:
    assert ledger.revision_of({"revision": 5}) == 5


# ---------------------------------------------------------------------------
# save: revision CAS, stable no-op, recovery metadata (FR-011,12,13,24) [SC-002,4,5]
# ---------------------------------------------------------------------------

def test_save_advances_revision(tmp_path: Path) -> None:
    make_v2_ledger(tmp_path, revision=1)
    data = ledger.load_raw(tmp_path)
    data["current_phase"] = "PLAN"
    ledger.save(tmp_path, data, base_revision=1)
    assert ledger.load_raw(tmp_path)["revision"] == 2


def test_save_stable_noop_is_byte_identical(tmp_path: Path) -> None:
    make_v2_ledger(tmp_path, revision=3)
    before = (tmp_path / "status.yaml").read_bytes()
    data = ledger.load_raw(tmp_path)
    ledger.save(tmp_path, data, base_revision=3)  # nothing logical changed
    after = (tmp_path / "status.yaml").read_bytes()
    assert after == before
    assert ledger.load_raw(tmp_path)["revision"] == 3  # no bump


def test_save_stale_write_rejected_and_first_change_survives(tmp_path: Path) -> None:
    make_v2_ledger(tmp_path, revision=1)
    base = ledger.revision_of(ledger.load_raw(tmp_path))

    first = ledger.load_raw(tmp_path)
    first["current_phase"] = "PLAN"
    ledger.save(tmp_path, first, base_revision=base)  # disk revision -> 2

    stale = copy.deepcopy(first)
    stale["current_phase"] = "TASKS"
    with pytest.raises(StaleLedgerError):
        ledger.save(tmp_path, stale, base_revision=base)  # base is now stale

    survived = ledger.load_raw(tmp_path)
    assert survived["current_phase"] == "PLAN"
    assert survived["revision"] == 2


def test_save_records_recovery_metadata(tmp_path: Path) -> None:
    make_v2_ledger(tmp_path, revision=1)
    data = ledger.load_raw(tmp_path)
    data["current_phase"] = "PLAN"
    ledger.save(tmp_path, data, base_revision=1)
    rec = ledger.load_raw(tmp_path)["recovery"]
    assert rec["last_consistent_revision"] == 2
    assert rec["last_consistent_at"].endswith("+00:00")


def test_save_interruption_leaves_previous_intact(tmp_path: Path) -> None:
    make_v2_ledger(tmp_path, revision=1)
    before = (tmp_path / "status.yaml").read_bytes()
    data = ledger.load_raw(tmp_path)
    data["current_phase"] = "PLAN"
    with patch("os.replace", side_effect=OSError("disk full")), pytest.raises(OSError):
        ledger.save(tmp_path, data, base_revision=1)
    assert (tmp_path / "status.yaml").read_bytes() == before


def test_write_new_creates_ledger(tmp_path: Path) -> None:
    data = make_v1_ledger(tmp_path)
    data["schema_version"] = 2
    (tmp_path / "status.yaml").unlink()
    ledger.write_new(tmp_path, data)
    assert ledger.load_raw(tmp_path)["schema_version"] == 2


# ---------------------------------------------------------------------------
# Ledger v4 — acknowledgements (Feature 010, T004)
# ---------------------------------------------------------------------------


def test_current_schema_is_v4() -> None:
    assert ledger.CURRENT_SCHEMA == 4


def test_backfill_acknowledgements_adds_empty_list() -> None:
    data = {"tasks": []}
    ledger.backfill_acknowledgements(data)
    assert data["acknowledgements"] == []


def test_backfill_acknowledgements_idempotent() -> None:
    data = {"acknowledgements": [{"path": "a", "task": "T001", "reason": "r"}]}
    ledger.backfill_acknowledgements(data)
    assert data["acknowledgements"] == [{"path": "a", "task": "T001", "reason": "r"}]


def test_migrate_v3_to_v4_backfills_acknowledgements() -> None:
    v3 = {
        "schema_version": 3, "revision": 2, "feature": "f", "branch": "main",
        "baseline": "abc", "workflow_lane": "full", "active_artifact": "spec.md",
        "created_at": "2026-07-05T00:00:00+00:00", "updated_at": "2026-07-05T00:00:00+00:00",
        "current_phase": "IMPLEMENT",
        "recovery": {"active_task": None, "last_commit": None, "blockers": [],
                     "last_consistent_revision": 2,
                     "last_consistent_at": "2026-07-05T00:00:00+00:00",
                     "migrated_from_backup": None},
        "tasks": [{"id": "T001", "status": "DONE", "evidence": "CLI_LOG:x",
                   "context_provenance": {"map": "none"}}],
        "review_cycles": [], "workflow": {"skipped_steps": []},
    }
    assert ledger.classify(v3) == ledger.MIGRATABLE
    out = ledger.migrate_to_current(v3)
    assert out["schema_version"] == 4
    assert out["acknowledgements"] == []
    # existing task + provenance preserved byte-for-byte
    assert out["tasks"][0]["evidence"] == "CLI_LOG:x"
    assert out["tasks"][0]["context_provenance"] == {"map": "none"}


def test_pre_v4_ledger_reads_without_acknowledgements(fake_speckit_repo: Path) -> None:
    # A v3 record with no acknowledgements key is a supported prior shape (read-compat).
    data = {"schema_version": 3, "tasks": [], "review_cycles": [], "current_phase": "SPECIFY"}
    assert ledger.validate_invariants(data) == []  # absent list is valid


def test_invariant_flags_malformed_acknowledgement() -> None:
    data = {"current_phase": "IMPLEMENT", "tasks": [{"id": "T001", "status": "DONE",
            "evidence": "x"}], "review_cycles": [],
            "acknowledgements": [{"path": "", "task": "T001", "reason": "r"}]}
    violations = ledger.validate_invariants(data)
    assert any("malformed" in v for v in violations)


def test_invariant_flags_unknown_task_acknowledgement() -> None:
    data = {"current_phase": "IMPLEMENT", "tasks": [{"id": "T001", "status": "DONE",
            "evidence": "x"}], "review_cycles": [],
            "acknowledgements": [{"path": "a", "task": "T999", "reason": "r"}]}
    violations = ledger.validate_invariants(data)
    assert any("unknown task 'T999'" in v for v in violations)


def test_invariant_accepts_valid_acknowledgement() -> None:
    data = {"current_phase": "IMPLEMENT", "tasks": [{"id": "T001", "status": "DONE",
            "evidence": "x"}], "review_cycles": [],
            "acknowledgements": [{"path": "a", "task": "T001", "reason": "r"}]}
    assert ledger.validate_invariants(data) == []


def test_invariant_accepts_acknowledgement_for_orphaned_task() -> None:
    # A task removed from tasks.md becomes orphaned but its ledger record remains,
    # so an acknowledgement referencing it is NOT dangling (Feature 010, Finding 5).
    data = {"current_phase": "IMPLEMENT",
            "tasks": [{"id": "T001", "status": "DONE", "evidence": "x", "orphaned": True}],
            "review_cycles": [],
            "acknowledgements": [{"path": "a", "task": "T001", "reason": "r"}]}
    assert ledger.validate_invariants(data) == []
