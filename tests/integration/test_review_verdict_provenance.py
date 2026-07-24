"""Integration: fully-provenanced review verdict (Feature 012, US3, T025).

Covers FR-011/SC-004/SC-007: the verdict names each profile gate's disposition, reason,
covered inputs, and supporting evidence id; a required failure rejects while an optional
failure never blocks.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specops import review
from specops.errors import SpecopsError
from tests.conftest import write_profiles
from tests.unit.test_review import _all_pass_setup, _commit_all

OK = f'"{sys.executable}" -c "print(1)"'
FAIL = f'"{sys.executable}" -c "import sys; sys.exit(1)"'


def _gate(report, name):
    return next(r for r in report.results if r.name == name)


def test_verdict_carries_disposition_reason_inputs_evidence(fake_speckit_repo: Path) -> None:
    _all_pass_setup(fake_speckit_repo, test=OK)
    report = review.evaluate(fake_speckit_repo)
    assert report.passed
    t = _gate(report, "test")
    assert t.disposition == "required"
    assert t.reason == "always"
    assert t.evidence_id and t.evidence_id.startswith("EV-")
    assert t.commit_range and ".." in t.commit_range


def test_required_failure_rejects(fake_speckit_repo: Path) -> None:
    _all_pass_setup(fake_speckit_repo, test=FAIL)
    report = review.evaluate(fake_speckit_repo)
    assert not report.passed
    t = _gate(report, "test")
    assert t.status == "FAIL" and t.disposition == "failed"


def test_invalid_config_fails_closed_not_false_approve(fake_speckit_repo: Path) -> None:
    # A malformed gate-profiles.yaml must NOT silently degrade to the default lint/test
    # suite and return APPROVED — review fails closed (the fail-open bug).
    _all_pass_setup(fake_speckit_repo)
    write_profiles(fake_speckit_repo, {"profiles": [
        {"name": "security", "command": ""},  # required gate with an empty command → invalid
    ]})
    _commit_all(fake_speckit_repo, "add invalid gate profile")
    with pytest.raises(SpecopsError, match="Invalid gate-profiles.yaml"):
        review.evaluate(fake_speckit_repo)


def test_optional_failure_does_not_reject(fake_speckit_repo: Path) -> None:
    _all_pass_setup(fake_speckit_repo)  # empty specops.json commands
    write_profiles(fake_speckit_repo, {"output_version": 1, "profiles": [
        {"name": "unit", "command": OK, "applies": {"always": True},
         "timeout": 60, "required": True},
        {"name": "style", "command": FAIL, "applies": {"always": True},
         "timeout": 60, "required": False},
    ]})
    _commit_all(fake_speckit_repo, "add gate profiles")
    report = review.evaluate(fake_speckit_repo)
    assert report.passed  # the optional gate's failure does not block (0% false block)
    style = _gate(report, "style")
    assert style.disposition == "failed" and style.status == "PASS"
    unit = _gate(report, "unit")
    assert unit.disposition == "required" and unit.status == "PASS"
