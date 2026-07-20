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


def test_prerelease_suffix_is_ignored(monkeypatch) -> None:
    monkeypatch.setattr(compat, "installed_version", lambda: "0.3.0.dev1")
    assert compat.check().satisfied
