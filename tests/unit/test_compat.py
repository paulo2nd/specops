"""Unit tests for the CLI-compatibility gate (compat.py, FR-016)."""
from __future__ import annotations

from specops import compat


def test_installed_version_resolves_under_editable_install() -> None:
    # The package is installed (editable) during development.
    assert compat.installed_version() is not None


def test_check_satisfied_at_floor(monkeypatch) -> None:
    monkeypatch.setattr(compat, "installed_version", lambda: compat.MIN_CLI_VERSION)
    result = compat.check()
    assert result.satisfied
    assert result.installed == compat.MIN_CLI_VERSION


def test_check_satisfied_for_newer(monkeypatch) -> None:
    monkeypatch.setattr(compat, "installed_version", lambda: "1.2.3")
    assert compat.check().satisfied


def test_check_fails_for_older(monkeypatch) -> None:
    monkeypatch.setattr(compat, "installed_version", lambda: "0.2.1")
    result = compat.check()
    assert not result.satisfied
    assert "older" in result.reason()


def test_check_fails_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(compat, "installed_version", lambda: None)
    result = compat.check()
    assert not result.satisfied
    assert "not installed" in result.reason()


def test_prerelease_below_floor_is_rejected(monkeypatch) -> None:
    # PEP 440: a pre-release of the floor version is *older* than the floor (#24).
    # 0.3.0rc1 < 0.3.0 and 0.3.0.dev1 < 0.3.0, so both must NOT satisfy >= 0.3.0.
    for pre in ("0.3.0rc1", "0.3.0.dev1", "0.3.0a1", "0.3.0b2"):
        monkeypatch.setattr(compat, "installed_version", lambda pre=pre: pre)
        assert not compat.check().satisfied, f"{pre} must not satisfy the 0.3.0 floor"


def test_prerelease_above_floor_satisfies(monkeypatch) -> None:
    # A pre-release of a *higher* version still clears the floor (version-aware,
    # not a blanket pre-release reject): 1.0.0.dev1 > 0.3.0.
    monkeypatch.setattr(compat, "installed_version", lambda: "1.0.0.dev1")
    assert compat.check().satisfied


def test_two_component_version_satisfies_three_component_floor(monkeypatch) -> None:
    # '0.3' means the same as the '0.3.0' floor — must not be rejected as older.
    monkeypatch.setattr(compat, "installed_version", lambda: "0.3")
    assert compat.check().satisfied


def test_malformed_installed_version_is_fail_closed(monkeypatch) -> None:
    # An unparseable installed version compares as not-satisfied (fail-closed, R7),
    # rather than crashing the gate.
    monkeypatch.setattr(compat, "installed_version", lambda: "not-a-version")
    assert not compat.check().satisfied
