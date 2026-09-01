"""Migration tests: ledger v8 → v9 amendment fields (Feature 026, T003).

Covers FR-022/SC-011: the v9 bump is additive — a v8 ledger whose evidence records
lack the new optional fields (`amendment`, `reason`) upgrades with zero data loss,
stays valid, and migration is idempotent. Parity with the v6→v7 and v7→v8 bumps:
a pure version bump with no backfill.

The v8 ledger is built inline, following the house pattern of the v6/v7 migration
tests — `tests/fixtures/` holds external *input* formats (context maps, gate
profiles, findings-input), not ledgers.
"""
from __future__ import annotations

from specops import ledger


def _v8_evidence() -> dict:
    return {
        "id": "EV-abc123def456", "producer": "auto", "command": "git diff --name-only",
        "exit_code": 0, "timestamp": "2026-08-01T00:00:00+00:00",
        "commit_range": "aaa111..bbb222", "affected_paths": ["src/a.py"],
        "summary": "CODE_DIFF: 1 file changed", "superseded_by": None,
    }


def _v8_task() -> dict:
    return {
        "id": "T001", "status": "DONE", "started_commit": "aaa111",
        "commits": ["bbb222"], "evidence": "CODE_DIFF: 1 file changed",
        "completed_at": "2026-08-01T00:00:00+00:00",
        "evidence_refs": ["EV-abc123def456"],
        # Present on any real v8 task (backfilled at v3); without it the v3 backfill
        # fires during migration and the pure-bump assertion rightly fails.
        "context_provenance": {"map": "none"},
    }


def _v8_ledger() -> dict:
    return {
        "schema_version": 8, "revision": 3, "feature": "f", "branch": "main",
        "baseline": "aaa111", "workflow_lane": "full", "active_artifact": "tasks.md",
        "created_at": "2026-08-01T00:00:00+00:00", "updated_at": "2026-08-01T00:00:00+00:00",
        "current_phase": "REVIEW",
        "recovery": {"active_task": None, "last_commit": "bbb222", "blockers": [],
                     "last_consistent_revision": 3,
                     "last_consistent_at": "2026-08-01T00:00:00+00:00",
                     "migrated_from_backup": None},
        "tasks": [_v8_task()], "evidence": [_v8_evidence()],
        "acknowledgements": [{"path": "src/x.py", "task": "T001", "reason": "tooling",
                              "map_digest": None, "at": "2026-08-01T00:00:00+00:00"}],
        "workflow": {"skipped_steps": []},
        "review_cycles": [{
            "round": 1, "started_at": "2026-08-01T00:00:00+00:00",
            "completed_at": "2026-08-01T01:00:00+00:00", "result": "APPROVED",
            "context_provenance": {"map": "none"},
            "reviewed_range": "aaa111..bbb222", "review_role": "anchor",
            "handoff": {"authorized_paths": [], "closed_at": None, "findings": []},
        }],
    }


def test_v8_is_migratable_to_v9() -> None:
    assert ledger.classify(_v8_ledger()) == ledger.MIGRATABLE
    out = ledger.migrate_to_current(_v8_ledger())
    assert out["schema_version"] == ledger.CURRENT_SCHEMA == 9


def test_v8_to_v9_is_a_pure_version_bump() -> None:
    """Every record survives byte-identical; only schema_version changes (SC-011)."""
    src = _v8_ledger()
    out = ledger.migrate_to_current(src)
    for key in ("tasks", "evidence", "acknowledgements", "review_cycles"):
        assert out[key] == src[key], f"{key} was modified by the v8→v9 migration"
    assert out["revision"] == src["revision"]
    assert out["feature"] == src["feature"] and out["branch"] == src["branch"]


def test_v8_evidence_lacks_the_new_optional_fields() -> None:
    out = ledger.migrate_to_current(_v8_ledger())
    record = out["evidence"][0]
    assert record["summary"] == "CODE_DIFF: 1 file changed"
    for new_field in ("amendment", "reason"):
        assert new_field not in record


def test_migrated_v9_ledger_passes_invariants() -> None:
    out = ledger.migrate_to_current(_v8_ledger())
    assert ledger.validate_invariants(out) == []


def test_v8_to_v9_migration_idempotent() -> None:
    once = ledger.migrate_to_current(_v8_ledger())
    twice = ledger.migrate_to_current(once)
    assert twice == once
    assert twice["schema_version"] == ledger.CURRENT_SCHEMA


def test_amendment_record_without_reason_is_an_invariant_violation() -> None:
    """FR-004/T013: `amendment: true` requires a non-empty reason."""
    data = ledger.migrate_to_current(_v8_ledger())
    data["evidence"].append({
        **_v8_evidence(), "id": "EV-nofield0000", "producer": "amend", "amendment": True,
    })
    violations = ledger.validate_invariants(data)
    assert any("reason" in v for v in violations), violations


def test_amendment_record_with_reason_is_valid() -> None:
    data = ledger.migrate_to_current(_v8_ledger())
    data["evidence"].append({
        **_v8_evidence(), "id": "EV-withreason0", "producer": "amend",
        "amendment": True, "reason": "original close recorded no gate run",
    })
    assert ledger.validate_invariants(data) == []


# --- T014: the template is a content seed, not a schema declaration -----------


def test_status_template_declares_no_schema_version() -> None:
    """#69 regression guard: a hard-coded version in the scaffold template can only
    drift into a false declaration on the next bump. `init-spec` normalizes the
    rendered template through `migrate_to_current`, so the seed must stay silent
    about its version — that is what makes a fresh ledger current by construction."""
    from pathlib import Path

    import specops

    template = Path(specops.__file__).parent / "templates" / "status.yaml"
    assert "schema_version" not in template.read_text(encoding="utf-8")
