"""Tests for safe evidence caching (Feature 012, US3, T024).

Covers FR-009/SC-003: a gate is `cached` (no re-run) only when a non-superseded
evidence record with the matching cache-key id exists; any change to command, inputs
(paths), commit, or context-map digest forces a fresh run (the id no longer matches).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from specops import evidence, review
from specops.gateprofiles import ApplicabilityPredicate as AP
from specops.gateprofiles import GateProfile, SelectedGate

NAME, COMMAND, RANGE, PATHS, DIGEST = "test", "pytest -q", "a..b", ["src/x.py"], "d1"


def _profile(command: str = COMMAND) -> GateProfile:
    return GateProfile(name=NAME, command=command, applies=AP(always=True))


def _sel() -> SelectedGate:
    return SelectedGate(_profile(), True, "always")


def _matching_evidence() -> list[dict]:
    key = evidence.cache_key(
        producer=f"gate:{NAME}@{review._cli_version()}", command=COMMAND,
        commit_range=RANGE, affected_paths=PATHS, context_map_digest=DIGEST,
    )
    return [{"id": evidence.derive_id(key), "producer": f"gate:{NAME}", "superseded_by": None}]


def _run(monkeypatch: pytest.MonkeyPatch, *, existing: list[dict],
         command: str = COMMAND, paths=PATHS, commit_range: str = RANGE, digest: str = DIGEST):
    calls: list[str] = []

    def _spy(cmd, cwd, timeout=None):
        calls.append(cmd)
        from specops.shell import ShellResult
        return ShellResult(0, "", "", False)

    monkeypatch.setattr(review.shell, "run_client_command", _spy)
    sel = SelectedGate(_profile(command), True, "always")
    gr = review._run_profile_gate(sel, Path("."), list(paths), commit_range, digest, existing)
    return gr, calls


def test_cache_hit_reuses_without_running(monkeypatch: pytest.MonkeyPatch) -> None:
    gr, calls = _run(monkeypatch, existing=_matching_evidence())
    assert gr.disposition == "cached" and gr.status == "PASS"
    assert calls == []  # command not executed


def test_changed_command_forces_fresh_run(monkeypatch: pytest.MonkeyPatch) -> None:
    gr, calls = _run(monkeypatch, existing=_matching_evidence(), command="ruff .")
    assert gr.disposition != "cached"
    assert calls == ["ruff ."]


def test_changed_paths_forces_fresh_run(monkeypatch: pytest.MonkeyPatch) -> None:
    gr, calls = _run(monkeypatch, existing=_matching_evidence(), paths=["src/y.py"])
    assert gr.disposition != "cached" and calls != []


def test_changed_commit_forces_fresh_run(monkeypatch: pytest.MonkeyPatch) -> None:
    gr, calls = _run(monkeypatch, existing=_matching_evidence(), commit_range="a..c")
    assert gr.disposition != "cached" and calls != []


def test_changed_map_digest_forces_fresh_run(monkeypatch: pytest.MonkeyPatch) -> None:
    gr, calls = _run(monkeypatch, existing=_matching_evidence(), digest="d2")
    assert gr.disposition != "cached" and calls != []


def test_superseded_record_is_not_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    ev = _matching_evidence()
    ev[0]["superseded_by"] = "EV-newer"
    gr, calls = _run(monkeypatch, existing=ev)
    assert gr.disposition != "cached" and calls != []


# ---------------------------------------------------------------------------
# Feature 024: exit-code hardening, working-tree invalidation, git-dir round-trip
# ---------------------------------------------------------------------------


def _spy_shell(monkeypatch: pytest.MonkeyPatch, calls: list[str], rc: int = 0) -> None:
    from specops.shell import ShellResult

    def _s(cmd: str, cwd, timeout=None):  # noqa: ANN001
        calls.append(cmd)
        return ShellResult(rc, "", "", False)

    monkeypatch.setattr(review.shell, "run_client_command", _s)


def test_cache_hit_with_nonzero_exit_is_not_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature 024: a non-passing cached record must NOT be reported PASS (defensive)."""
    ev = _matching_evidence()
    ev[0]["exit_code"] = 1
    gr, calls = _run(monkeypatch, existing=ev)
    assert gr.disposition != "cached" and calls == [COMMAND]


def test_worktree_digest_change_invalidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A changed working-tree digest yields a new id → cache miss (FR-003)."""
    key = evidence.cache_key(
        producer=f"gate:{NAME}@{review._cli_version()}", command=COMMAND,
        commit_range=RANGE, affected_paths=PATHS, context_map_digest=DIGEST,
        worktree_digest="w1",
    )
    ev = [{"id": evidence.derive_id(key), "producer": f"gate:{NAME}",
           "superseded_by": None, "exit_code": 0}]
    sel = SelectedGate(_profile(), True, "always")
    calls: list[str] = []
    _spy_shell(monkeypatch, calls)
    hit = review._run_profile_gate(sel, Path("."), list(PATHS), RANGE, DIGEST, ev, "w1")
    assert hit.disposition == "cached" and calls == []
    miss = review._run_profile_gate(sel, Path("."), list(PATHS), RANGE, DIGEST, ev, "w2")
    assert miss.disposition != "cached" and calls == [COMMAND]


def test_fresh_pass_attaches_pending_record(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh pass carries a cacheable gate-run record for the caller to persist."""
    sel = SelectedGate(_profile(), True, "always")
    calls: list[str] = []
    _spy_shell(monkeypatch, calls)
    gr = review._run_profile_gate(sel, Path("."), list(PATHS), RANGE, DIGEST, [], "w1")
    assert gr.disposition == "required" and gr.pending_record is not None
    assert gr.pending_record["exit_code"] == 0
    assert gr.pending_record["producer"].startswith(f"gate:{NAME}@")


def test_evaluate_persists_and_reuses_across_runs(
    fake_speckit_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: review-soft records a passing test gate in the git-dir cache; a second
    identical evaluation reuses it (`cached`, no re-run) and the committed repo is
    byte-identical (cache lives in `.git`) — the terminal-gate reuse (US1/SC-005)."""
    from tests.conftest import snapshot_tree
    from tests.unit.test_review import _all_pass_setup

    root = fake_speckit_repo
    _all_pass_setup(root, test="true")
    calls: list[str] = []
    _spy_shell(monkeypatch, calls)

    before = snapshot_tree(root)
    r1 = review.evaluate(root)
    t1 = next(g for g in r1.results if g.name == "test")
    assert r1.passed and t1.disposition == "required" and calls == ["true"]

    r2 = review.evaluate(root)
    t2 = next(g for g in r2.results if g.name == "test")
    assert t2.disposition == "cached" and calls == ["true"]  # not re-executed
    assert snapshot_tree(root) == before  # committed ledger + working tree untouched
    assert all(
        g.disposition != "cached"
        for g in r2.results if g.name in {"reconcile", "working-tree", "drift"}
    )
