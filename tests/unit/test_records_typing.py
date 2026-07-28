"""Feature 019 US3: runtime shape parity between the TypedDict schemas and the
dicts the factories actually emit (FR-005, the SC-007 serialization guard).

TypedDicts are static-only; these tests pin the schemas to reality so a future
factory change (new key, renamed key) cannot silently drift from `records.py`.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from specops import evidence, findings, records

_TEMPLATES = Path("src/specops/templates")


def _keys(td: type) -> set[str]:
    return set(td.__required_keys__) | set(td.__optional_keys__)  # type: ignore[attr-defined]


def test_finding_record_base_shape_matches_factory() -> None:
    rec = findings.new_finding(
        id="R1-F01", severity="blocking", rule="R1", file="src/a.py", line=1,
        action="fix it", expected_evidence="a test", closure_criteria="test passes",
    )
    assert set(rec.keys()) == set(records.FindingRecord.__required_keys__)  # type: ignore[attr-defined]


def test_finding_record_import_extras_are_declared_optional() -> None:
    rec = findings.new_finding(
        id="R1-F02", severity="advisory", rule="ext", file="src/b.py", line=None,
        action="look", imported={"contract_version": 1, "source_format": "json"},
        producer={"name": "tool", "version": "1"}, reviewed_digest={"path": "src/b.py"},
    )
    extras = set(rec.keys()) - set(records.FindingRecord.__required_keys__)  # type: ignore[attr-defined]
    assert extras <= set(records.FindingRecord.__optional_keys__)  # type: ignore[attr-defined]


def test_evidence_record_shape_matches_factory() -> None:
    rec = evidence.build_record(
        producer="auto", command="pytest", exit_code=0,
        timestamp="2026-07-27T00:00:00+00:00", commit_range="a..b",
        affected_paths=["src/a.py"], summary="TEST_REPORT:ok",
    )
    assert set(rec.keys()) == set(records.EvidenceRecord.__required_keys__)  # type: ignore[attr-defined]
    with_digest = evidence.build_record(
        producer="auto", command="pytest", exit_code=0,
        timestamp="2026-07-27T00:00:00+00:00", commit_range="a..b",
        affected_paths=[], summary="CLI_LOG:x", artifact_digest="sha256:00",
    )
    assert set(with_digest.keys()) - set(rec.keys()) <= set(
        records.EvidenceRecord.__optional_keys__  # type: ignore[attr-defined]
    )


def test_ledger_template_top_level_keys_are_declared() -> None:
    """Every key the scaffolded status.yaml ships is a declared LedgerDocument key."""
    template = (_TEMPLATES / "status.yaml").read_text(encoding="utf-8")
    rendered = (
        template
        .replace("{{feature-name}}", "001-demo")
        .replace("{{branch}}", "main")
        .replace("{{commit-hash}}", "0" * 40)
        .replace("{{active-artifact}}", "spec.md")
        .replace("{{timestamp}}", "2026-07-27T00:00:00+00:00")
    )
    data = yaml.safe_load(rendered)
    assert set(data.keys()) <= _keys(records.LedgerDocument)
    assert set(data["recovery"].keys()) <= _keys(records.RecoveryBlock)
    assert set(data["workflow"].keys()) <= _keys(records.WorkflowBlock)


def test_sync_tasks_new_task_shape_matches_task_record() -> None:
    """The dict `_sync_tasks` creates for a fresh task carries exactly the required keys."""
    from specops.status import _sync_tasks

    data: dict = {"tasks": []}
    _sync_tasks(data, "- [ ] T001 Do the thing\n")
    (task,) = data["tasks"]
    assert set(task.keys()) == set(records.TaskRecord.__required_keys__)  # type: ignore[attr-defined]
