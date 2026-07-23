"""Unit tests for the gate outcome taxonomy (Feature 012, US3, T022).

Covers FR-004/FR-008/SC-002: each run outcome maps to exactly one disposition;
`unavailable` (missing tool) is distinct from `failed`; a required failure blocks
(status FAIL) while an optional failure does not (status PASS, disposition recorded).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from specops import review
from specops.gateprofiles import ApplicabilityPredicate as AP
from specops.gateprofiles import GateProfile, SelectedGate
from specops.shell import ShellResult


def _sel(
    name: str, *, required: bool = True, command: str = "cmd", selected: bool = True,
) -> SelectedGate:
    return SelectedGate(
        GateProfile(name=name, command=command, applies=AP(always=True), required=required),
        selected, "always",
    )


def _run(
    monkeypatch: pytest.MonkeyPatch, sel: SelectedGate, result: ShellResult,
) -> review.GateResult:
    monkeypatch.setattr(review.shell, "run_client_command", lambda *a, **k: result)
    return review._run_profile_gate(sel, Path("."), [], "a..b", None, [])


def test_required_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    gr = _run(monkeypatch, _sel("t"), ShellResult(0, "", "", False))
    assert gr.status == "PASS" and gr.disposition == "required"
    assert gr.evidence_id and gr.commit_range == "a..b"


def test_required_failure_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    gr = _run(monkeypatch, _sel("t"), ShellResult(2, "boom", "", False))
    assert gr.status == "FAIL" and gr.disposition == "failed"


def test_optional_failure_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    gr = _run(monkeypatch, _sel("t", required=False), ShellResult(2, "boom", "", False))
    assert gr.status == "PASS"  # non-blocking
    assert gr.disposition == "failed"


def test_unavailable_distinct_from_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    gr = _run(monkeypatch, _sel("t"), ShellResult(127, "", "not found", False))
    assert gr.disposition == "unavailable" and gr.status == "FAIL"


def test_timeout_is_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    gr = _run(monkeypatch, _sel("t"), ShellResult(124, "", "", True))
    assert gr.disposition == "failed" and gr.status == "FAIL"
    assert any("timeout" in d for d in gr.detail)


def test_empty_command_is_benign_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    gr = _run(monkeypatch, _sel("t", command=""), ShellResult(0, "", "", False))
    assert gr.status == "SKIPPED" and gr.disposition == "skipped"


def test_not_selected_is_skipped() -> None:
    gr = review._run_profile_gate(_sel("t", selected=False), Path("."), [], "a..b", None, [])
    assert gr.status == "SKIPPED" and gr.disposition == "skipped"


def test_exactly_one_disposition_per_case(monkeypatch: pytest.MonkeyPatch) -> None:
    for result, expected in [
        (ShellResult(0, "", "", False), "required"),
        (ShellResult(1, "", "", False), "failed"),
        (ShellResult(127, "", "", False), "unavailable"),
        (ShellResult(124, "", "", True), "failed"),
    ]:
        gr = _run(monkeypatch, _sel("t"), result)
        assert gr.disposition == expected
