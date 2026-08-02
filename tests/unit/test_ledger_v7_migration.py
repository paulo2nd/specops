"""Migration tests: ledger v6 → v7 external-review-ingestion fields (Feature 015, T003).

Covers FR-015/SC-009: the v7 bump is additive — a v6 ledger whose findings lack the
new optional fields (`imported`, `producer`, `reviewed_digest`, `promotion`) upgrades
with zero data loss, stays valid, and migration is idempotent.
"""
from __future__ import annotations

from specops import ledger


def _v6_finding() -> dict:
    return {
        "id": "R1-F01", "severity": "blocking", "rule": "L2", "file": "src/a.py",
        "line": 42, "action": "fix", "expected_evidence": "a test", "closure_criteria": "passes",
        "state": "OPEN", "task": None, "commits": [], "evidence": None,
        "fixed_at": None, "verified_at": None,
    }


def _v6_ledger() -> dict:
    return {
        "schema_version": 6, "revision": 1, "feature": "f", "branch": "main",
        "baseline": "abc", "workflow_lane": "full", "active_artifact": "tasks.md",
        "created_at": "2026-07-25T00:00:00+00:00", "updated_at": "2026-07-25T00:00:00+00:00",
        "current_phase": "REVIEW",
        "recovery": {"active_task": None, "last_commit": None, "blockers": [],
                     "last_consistent_revision": 1,
                     "last_consistent_at": "2026-07-25T00:00:00+00:00",
                     "migrated_from_backup": None},
        "tasks": [], "evidence": [], "acknowledgements": [], "workflow": {"skipped_steps": []},
        "review_cycles": [{
            "round": 1, "started_at": "2026-07-25T00:00:00+00:00", "completed_at": None,
            "result": None, "context_provenance": {"map": "none"},
            "handoff": {"authorized_paths": [], "closed_at": None, "findings": [_v6_finding()]},
        }],
    }


def test_v6_is_migratable_to_v7() -> None:
    assert ledger.classify(_v6_ledger()) == ledger.MIGRATABLE
    out = ledger.migrate_to_current(_v6_ledger())
    assert out["schema_version"] == ledger.CURRENT_SCHEMA


def test_v6_findings_survive_migration_lossless() -> None:
    out = ledger.migrate_to_current(_v6_ledger())
    finding = out["review_cycles"][0]["handoff"]["findings"][0]
    # Existing fields preserved verbatim; new optional fields absent (not imported).
    assert finding["id"] == "R1-F01" and finding["severity"] == "blocking"
    assert finding["file"] == "src/a.py" and finding["state"] == "OPEN"
    for new_field in ("imported", "producer", "reviewed_digest", "promotion"):
        assert new_field not in finding


def test_migrated_v7_ledger_passes_invariants() -> None:
    out = ledger.migrate_to_current(_v6_ledger())
    assert ledger.validate_invariants(out) == []


def test_v6_to_v7_migration_idempotent() -> None:
    once = ledger.migrate_to_current(_v6_ledger())
    twice = ledger.migrate_to_current(once)
    assert twice["review_cycles"] == once["review_cycles"]
    assert twice["schema_version"] == once["schema_version"] == ledger.CURRENT_SCHEMA


def test_v6_finding_without_new_fields_has_no_structural_defect() -> None:
    # finding_structural_defects tolerates the absence of the v7 fields (never flags).
    assert ledger.finding_structural_defects(_v6_ledger()) == []
