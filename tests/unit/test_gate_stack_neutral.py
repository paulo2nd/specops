"""Stack-neutrality of gate evidence (Feature 012, Polish, T041).

Covers FR-018/FR-019/SC-010: a gate result derives only from command + exit code +
captured summary + local digest — no test-framework-specific parsing, no remote store.
The record identity is a function of the cache key, never of the command's output
content, proving the core never interprets framework result formats.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from specops import evidence, review
from specops.gateprofiles import ApplicabilityPredicate as AP
from specops.gateprofiles import GateProfile, SelectedGate
from specops.shell import ShellResult

_GENERIC_FIELDS = {
    "id", "producer", "command", "exit_code", "timestamp",
    "commit_range", "affected_paths", "summary", "superseded_by",
}


def test_record_has_only_generic_fields() -> None:
    rec = evidence.build_record(
        producer="gate:test@1", command="pytest", exit_code=0, timestamp="t",
        commit_range="a..b", affected_paths=["x"], summary="<testsuite tests='5'/>",
    )
    # framework output is stored verbatim as the summary, never parsed into fields
    assert set(rec) == _GENERIC_FIELDS
    assert rec["summary"] == "<testsuite tests='5'/>"


def test_gate_identity_independent_of_command_output(monkeypatch: pytest.MonkeyPatch) -> None:
    sel = SelectedGate(GateProfile("test", "cmd", AP(always=True)), True, "always")

    monkeypatch.setattr(review.shell, "run_client_command",
                        lambda *a, **k: ShellResult(0, "<xml>A</xml>", "", False))
    a = review._run_profile_gate(sel, Path("."), ["x"], "a..b", None, [])

    monkeypatch.setattr(review.shell, "run_client_command",
                        lambda *a, **k: ShellResult(0, "<xml>B-different</xml>", "", False))
    b = review._run_profile_gate(sel, Path("."), ["x"], "a..b", None, [])

    # Same command/inputs → same evidence id regardless of output content: the core
    # does not parse the framework output to derive identity (Principle V).
    assert a.evidence_id == b.evidence_id


def test_artifact_digest_is_local_only(tmp_path: Path) -> None:
    f = tmp_path / "report.xml"
    f.write_bytes(b"<x/>")
    d = evidence.digest_artifact(f)
    assert d is not None and d.startswith("sha256:")  # a local content hash, no remote ref
    assert "://" not in d
