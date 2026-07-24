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
