"""Frozen-shape contract test — status.yaml ledger, schema v8 (Feature 021/025). [SC-002][SC-007]

Locks the required-field set of each ledger record and pins the schema baseline at
CURRENT_SCHEMA == 8 (the migrated, written shape — NOT the template literal). A removal,
rename, or retype of a required field, or an unversioned schema bump, fails here.

Feature 025 (v8) added optional-only fields (``reviewed_range``/``review_role`` on a
review cycle, ``review_halt`` on the document) — additive, so no required-key set below
changes; only the pinned schema version moves 7 → 8.
"""
from __future__ import annotations

from specops import ledger, records

# Enumerated frozen baselines (data-model.md Entity 2). Hard-coded, not derived, so a
# silent change to the TypedDicts is caught.
_TASK_REQUIRED = {"id", "status", "started_commit", "commits", "evidence", "completed_at"}
_FINDING_REQUIRED = {
    "id", "severity", "rule", "file", "line", "action", "expected_evidence",
    "closure_criteria", "state", "task", "commits", "evidence", "fixed_at", "verified_at",
}
_EVIDENCE_REQUIRED = {
    "id", "producer", "command", "exit_code", "timestamp", "commit_range",
    "affected_paths", "summary", "superseded_by",
}


def test_ledger_schema_baseline_pinned() -> None:
    """SC-007: the frozen baseline is v9 (Feature 026 additive-only schema bump).

    The version moves with each additive bump; what this file freezes is the
    *required*-field set of every record, which an additive field never changes —
    see ``test_evidence_record_required_fields_frozen``, unchanged across v9.
    """
    assert ledger.CURRENT_SCHEMA == 9
    assert ledger.OLDEST_SUPPORTED == 1


def test_task_record_required_fields_frozen() -> None:
    assert set(records.TaskRecord.__required_keys__) == _TASK_REQUIRED


def test_finding_record_required_fields_frozen() -> None:
    assert set(records.FindingRecord.__required_keys__) == _FINDING_REQUIRED


def test_evidence_record_required_fields_frozen() -> None:
    assert set(records.EvidenceRecord.__required_keys__) == _EVIDENCE_REQUIRED


def test_new_optional_ledger_field_is_additive() -> None:
    """FR-007: optional fields may be added; the required set is a subset check so an
    additive v8 field would not trip this test (only a required-field change would)."""
    # LedgerDocument is total=False (all-optional); adding an optional key is additive.
    assert set(records.TaskRecord.__required_keys__) <= _TASK_REQUIRED | {"future_opt"}
