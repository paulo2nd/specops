"""Unit tests for structured evidence records (Feature 012, US2, T013).

Covers FR-006/FR-009/SC-005: cache-key-derived id determinism, volatile-field
exclusion, local artifact digest, legacy-string parsing (incl. malformed verbatim),
and idempotent append with supersession.
"""
from __future__ import annotations

from pathlib import Path

from specops import evidence


def _rec(**over):
    kw = dict(
        producer="gate:test@0.4.0", command="pytest -q", exit_code=0,
        timestamp="2026-07-23T00:00:00+00:00", commit_range="a..b",
        affected_paths=["src/x.py"], summary="ok", context_map_digest=None,
    )
    kw.update(over)
    return evidence.build_record(**kw)


def test_id_prefix_and_shape() -> None:
    rid = _rec()["id"]
    assert rid.startswith("EV-") and len(rid) == 3 + 12


def test_identical_key_same_id() -> None:
    assert _rec()["id"] == _rec()["id"]


def test_volatile_fields_excluded_from_id() -> None:
    a = _rec(timestamp="2026-01-01T00:00:00+00:00", exit_code=1, summary="different")
    b = _rec(timestamp="2099-12-31T00:00:00+00:00", exit_code=0, summary="ok")
    assert a["id"] == b["id"]  # only the cache key drives identity


def test_each_key_field_changes_id() -> None:
    base = _rec()["id"]
    assert _rec(producer="gate:lint@0.4.0")["id"] != base
    assert _rec(command="ruff .")["id"] != base
    assert _rec(commit_range="a..c")["id"] != base
    assert _rec(affected_paths=["src/y.py"])["id"] != base
    assert _rec(context_map_digest="deadbeef")["id"] != base


def test_affected_paths_sorted_for_stable_id() -> None:
    a = _rec(affected_paths=["b", "a"])
    b = _rec(affected_paths=["a", "b"])
    assert a["id"] == b["id"]
    assert a["affected_paths"] == ["a", "b"]


def test_worktree_digest_included_only_when_provided() -> None:
    """Feature 024: the gate-cache dimension is absent unless passed (id stays stable)."""
    base = evidence.cache_key(
        producer="gate:test@0.9.0", command="pytest", commit_range="a..b",
        affected_paths=["x"], context_map_digest=None,
    )
    assert "worktree_digest" not in base
    with_wt = evidence.cache_key(
        producer="gate:test@0.9.0", command="pytest", commit_range="a..b",
        affected_paths=["x"], context_map_digest=None, worktree_digest="w1",
    )
    assert with_wt["worktree_digest"] == "w1"
    assert evidence.derive_id(base) != evidence.derive_id(with_wt)


def test_auto_cache_key_shape_unchanged_no_migration() -> None:
    """An `auto`-style key (no digest) keeps the exact pre-feature tuple → stable ids."""
    key = evidence.cache_key(
        producer="auto", command="(auto)", commit_range="a..b",
        affected_paths=["x"], context_map_digest=None, subject="T001",
    )
    assert set(key) == {
        "producer", "command", "commit_range", "affected_paths",
        "context_map_digest", "subject",
    }


def test_artifact_digest(tmp_path: Path) -> None:
    f = tmp_path / "report.xml"
    f.write_bytes(b"hello")
    d = evidence.digest_artifact(f)
    assert d and d.startswith("sha256:")
    assert evidence.digest_artifact(tmp_path / "missing") is None
    f.write_bytes(b"changed")
    assert evidence.digest_artifact(f) != d  # a content change is detectable


def test_parse_legacy_conformant_multiple_records() -> None:
    recs = evidence.parse_legacy_string(
        "TEST_REPORT:643 passed; CODE_DIFF:+1/-0", timestamp="t", commit_range="a..b"
    )
    assert [r["summary"] for r in recs] == ["TEST_REPORT:643 passed", "CODE_DIFF:+1/-0"]
    assert all(r["producer"] == "auto" and r["command"] == "(migrated)" for r in recs)


def test_parse_legacy_malformed_preserved_verbatim() -> None:
    recs = evidence.parse_legacy_string("just some free prose", timestamp="t", commit_range="")
    assert len(recs) == 1
    assert recs[0]["summary"] == "just some free prose"  # zero-loss (FR-007)


def test_append_record_idempotent() -> None:
    ev: list = []
    r = _rec()
    evidence.append_record(ev, r)
    evidence.append_record(ev, _rec())  # identical id
    assert len(ev) == 1


def test_canonical_sort_orders_by_producer_then_timestamp_then_range() -> None:
    a = _rec(producer="gate:test@1", timestamp="2026-01-02T00:00:00+00:00")
    b = _rec(producer="gate:lint@1", timestamp="2026-01-01T00:00:00+00:00")
    c = _rec(producer="gate:test@1", timestamp="2026-01-01T00:00:00+00:00")
    ordered = evidence.canonical_sort([a, b, c])
    # gate:lint before gate:test; within gate:test, earlier timestamp first (FR-021)
    assert [r["producer"] for r in ordered] == ["gate:lint@1", "gate:test@1", "gate:test@1"]
    assert ordered[1]["timestamp"] <= ordered[2]["timestamp"]
    # deterministic + independent of insertion order
    assert evidence.canonical_sort([c, a, b]) == ordered


def test_append_record_supersede() -> None:
    ev: list = []
    old = _rec(commit_range="a..b")
    evidence.append_record(ev, old, supersede=True)
    new = _rec(commit_range="a..c")  # same producer, changed key → new id
    evidence.append_record(ev, new, supersede=True)
    assert len(ev) == 2
    assert ev[0]["superseded_by"] == new["id"]
    assert ev[1]["superseded_by"] is None


# --- Feature 018 (US3, T022): evidence.validate_string equivalence corpus -----

# The exact corpus the retired `status._validate_evidence` accepted/rejected, captured
# from its 11 tests before the grammar moved to evidence.py (SC-003). validate_string
# must reproduce that behavior identically.
import pytest  # noqa: E402


@pytest.mark.parametrize("value", [
    "TEST_REPORT:all tests passed",
    "TEST_REPORT:42 ok; CODE_DIFF:3 files",
    "CLI_LOG:run passed",
    "TEST_REPORT:42 ok; CODE_DIFF:3 files in 2 commits",
])
def test_validate_string_accepts(value: str) -> None:
    assert evidence.validate_string(value) is True


@pytest.mark.parametrize("value", [
    "",                       # empty
    "BAD_CLASS:something",    # unknown class
    "no colon here",         # no colon
    "CLI_LOG:",              # empty summary
    "LOG:x",                 # unknown class
    "CLI_LOG:a; done",       # orphan segment
    "CLI_LOG no colon",      # missing colon
])
def test_validate_string_rejects(value: str) -> None:
    assert evidence.validate_string(value) is False
