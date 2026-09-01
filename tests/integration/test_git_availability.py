"""Feature 020 US3/US1: the git-availability precondition and CLI-surface guard.

Covers FR-012 (fail closed + doctor blocking finding), FR-013 (init first-step),
FR-010 (no new CLI command/option), and SC-008. Git-on-PATH is already an
implicit precondition today (GitPython required an installed git); these tests
lock the *diagnostic* behavior when it is absent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from specops import doctor, gitops, initializer
from specops.errors import SpecopsError


def _make_git_unavailable(monkeypatch) -> None:
    def _raise() -> str:
        raise gitops.GitError(gitops.GIT_UNAVAILABLE_MSG)

    monkeypatch.setattr(gitops, "ensure_git_available", _raise)


# --- FR-013: init validates git availability as its first step ---------------


def test_init_fails_closed_when_git_missing(monkeypatch, tmp_path: Path) -> None:
    _make_git_unavailable(monkeypatch)
    # Fail closed with a clean SpecopsError (exit 1 via the CLI boundary), before
    # the repo check or the `git init` subprocess — not an uncaught traceback.
    with pytest.raises(SpecopsError):
        initializer.run(tmp_path, non_interactive=True)


def test_init_checks_git_before_repo(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(gitops, "ensure_git_available",
                        lambda: (_ for _ in ()).throw(gitops.GitError("no git")))
    monkeypatch.setattr(gitops, "is_git_repo", lambda _root: calls.append("is_git_repo") or True)
    with pytest.raises(gitops.GitError):
        initializer.run(tmp_path, non_interactive=True)
    assert calls == []  # is_git_repo never reached — availability gate came first


# --- FR-012: doctor reports git availability as a blocking finding -----------


def _git_availability_finding(root: Path) -> doctor.Finding | None:
    for domain in doctor.diagnose(root):
        if domain.domain == doctor.D_ENVIRONMENT:
            for f in domain.findings:
                if f.id == "git-availability":
                    return f
    return None


def test_doctor_reports_git_available_ok(tmp_git_repo: Path) -> None:
    finding = _git_availability_finding(tmp_git_repo)
    assert finding is not None
    assert finding.severity == doctor.OK
    assert "git available" in finding.message


def test_doctor_reports_git_missing_as_blocking(monkeypatch, tmp_git_repo: Path) -> None:
    _make_git_unavailable(monkeypatch)
    finding = _git_availability_finding(tmp_git_repo)
    assert finding is not None
    assert finding.severity == doctor.BLOCKING


def test_doctor_git_missing_does_not_also_report_present(monkeypatch, tmp_git_repo: Path) -> None:
    # Speckit present + git absent must NOT emit the green "present" summary
    # alongside the blocking git-availability finding (self-contradiction,
    # code-review finding). The environment domain reports only the blocking one.
    (tmp_git_repo / ".specify" / "templates").mkdir(parents=True)
    _make_git_unavailable(monkeypatch)
    env = next(d for d in doctor.diagnose(tmp_git_repo) if d.domain == doctor.D_ENVIRONMENT)
    messages = [f.message for f in env.findings]
    assert "Git and Spec Kit repository present." not in messages
    assert any(f.id == "git-availability" and f.severity == doctor.BLOCKING for f in env.findings)


def test_doctor_does_not_crash_when_git_missing(monkeypatch, tmp_git_repo: Path) -> None:
    _make_git_unavailable(monkeypatch)
    # find_repo is skipped when git is unavailable; diagnose still returns every domain.
    domains = doctor.diagnose(tmp_git_repo)
    assert len(domains) == 10
    verdict = doctor._max_severity(domains)
    assert verdict == doctor.BLOCKING


# --- FR-010: no new CLI command or option (only additive doctor content) -----

# Frozen surface as of Feature 020 — a new command/group here would be a
# surface delta the feature explicitly forbids (golden replay cannot catch a
# newly *added* option/command, so this snapshot does).
_EXPECTED_COMMANDS = {
    "consistency", "doctor", "init", "preflight", "reconcile", "report", "review",
}
_EXPECTED_GROUPS = {
    "context", "extension", "feature", "gate", "handoff", "lane", "status", "trace",
}


def test_cli_command_surface_unchanged() -> None:
    from specops.cli import app

    assert {c.name for c in app.registered_commands} == _EXPECTED_COMMANDS
    assert {g.name for g in app.registered_groups} == _EXPECTED_GROUPS
