"""Migration tests: ledger v5 → v6 structured evidence (Feature 012, US2, T014).

Covers FR-007/FR-019/SC-007: zero-loss string→record, idempotency, explicit empty
list, malformed-string verbatim preservation, and pre-v6 readability.
"""
from __future__ import annotations

from specops import ledger


def _v5_ledger(*tasks: dict) -> dict:
    return {
        "schema_version": 5, "revision": 1, "feature": "f", "branch": "main",
        "baseline": "abc", "workflow_lane": "full", "active_artifact": "tasks.md",
        "created_at": "2026-07-22T00:00:00+00:00", "updated_at": "2026-07-22T00:00:00+00:00",
        "current_phase": "REVIEW",
        "recovery": {"active_task": None, "last_commit": None, "blockers": [],
                     "last_consistent_revision": 1,
                     "last_consistent_at": "2026-07-22T00:00:00+00:00",
                     "migrated_from_backup": None},
        "tasks": list(tasks),
        "review_cycles": [], "acknowledgements": [], "workflow": {"skipped_steps": []},
    }


def _task(tid: str, evidence: str | None) -> dict:
    return {"id": tid, "status": "DONE", "evidence": evidence, "commits": ["c0ffee"],
            "completed_at": "2026-07-22T01:00:00+00:00", "context_provenance": {"map": "none"}}


def test_v5_is_migratable_to_v6() -> None:
    assert ledger.classify(_v5_ledger()) == ledger.MIGRATABLE
    out = ledger.migrate_to_current(_v5_ledger())
    assert out["schema_version"] == 6


def test_legacy_strings_become_structured_records_lossless() -> None:
    v5 = _v5_ledger(_task("T001", "TEST_REPORT:643 passed; CODE_DIFF:x"))
    out = ledger.migrate_to_current(v5)
    ev = out["evidence"]
    summaries = {r["summary"] for r in ev}
    assert summaries == {"TEST_REPORT:643 passed", "CODE_DIFF:x"}
    task = out["tasks"][0]
    assert task["evidence"] == "TEST_REPORT:643 passed; CODE_DIFF:x"  # string retained
    assert sorted(task["evidence_refs"]) == sorted(r["id"] for r in ev)


def test_absent_evidence_backfilled_to_empty_list() -> None:
    out = ledger.migrate_to_current(_v5_ledger(_task("T001", None)))
    assert out["evidence"] == []
    assert out["tasks"][0]["evidence_refs"] == []


def test_malformed_legacy_string_preserved_verbatim() -> None:
    out = ledger.migrate_to_current(_v5_ledger(_task("T001", "not-a-class free text")))
    assert len(out["evidence"]) == 1
    assert out["evidence"][0]["summary"] == "not-a-class free text"


def test_migration_idempotent() -> None:
    once = ledger.migrate_to_current(_v5_ledger(_task("T001", "CLI_LOG:x")))
    twice = ledger.migrate_to_current(once)
    assert twice["evidence"] == once["evidence"]
    assert twice["tasks"][0]["evidence_refs"] == once["tasks"][0]["evidence_refs"]


def test_backfill_evidence_directly_idempotent() -> None:
    data = _v5_ledger(_task("T001", "CLI_LOG:x"))
    ledger.backfill_evidence(data)
    first = [dict(r) for r in data["evidence"]]
    ledger.backfill_evidence(data)
    assert data["evidence"] == first


def test_migrated_ledger_passes_invariants() -> None:
    out = ledger.migrate_to_current(_v5_ledger(_task("T001", "TEST_REPORT:ok")))
    assert ledger.validate_invariants(out) == []
