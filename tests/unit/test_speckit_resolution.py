"""Feature-resolution precedence and provenance (Feature 026, T006–T009).

SpecOps must resolve the active feature exactly as Spec Kit does, or the two tools
answer about different features from identical repository state — the #75 failure
through another door. Spec Kit's order (`.specify/scripts/**/common.ps1`) is:

    1. SPECIFY_FEATURE_DIRECTORY (relative values joined to the repo root)
    2. .specify/feature.json > feature_directory
    3. error

SpecOps adds a third level — the newest ``specs/NNN-*`` — retained for repositories
that run without a pointer file, but reported as an *inference* rather than passed
off as an explicit answer (FR-014a).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specops import speckit


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A Speckit layout with two features and the pointer on the first."""
    (tmp_path / ".specify" / "templates").mkdir(parents=True)
    for name in ("001-first", "002-second"):
        (tmp_path / "specs" / name).mkdir(parents=True)
    (tmp_path / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-first"}), encoding="utf-8"
    )
    monkeypatch.delenv("SPECIFY_FEATURE_DIRECTORY", raising=False)
    return tmp_path


# --- T006: precedence ---------------------------------------------------------

def test_override_outranks_the_pointer_file(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/002-second")
    fd = speckit.resolve_feature_dir(repo)
    assert fd is not None and fd.name == "002-second"


def test_pointer_file_wins_when_no_override(repo: Path) -> None:
    fd = speckit.resolve_feature_dir(repo)
    assert fd is not None and fd.name == "001-first"


def test_inference_only_when_neither_source_answers(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / ".specify" / "feature.json").unlink()
    fd = speckit.resolve_feature_dir(repo)
    assert fd is not None and fd.name == "002-second"  # newest by numeric prefix


def test_relative_override_is_joined_to_the_repo_root(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec Kit normalizes a relative override against the repo root; so must SpecOps."""
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/002-second")
    monkeypatch.chdir(tmp := repo / "specs")  # resolve from a different cwd
    assert tmp.exists()
    fd = speckit.resolve_feature_dir(repo)
    assert fd is not None and fd.resolve() == (repo / "specs" / "002-second").resolve()


def test_absolute_override_is_used_as_is(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", str(repo / "specs" / "002-second"))
    fd = speckit.resolve_feature_dir(repo)
    assert fd is not None and fd.name == "002-second"


# --- T007: the override is read, never persisted ------------------------------

def test_resolution_never_writes_the_pointer_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec Kit persists the override on its *write* path but passes -NoPersist for
    read-only resolution (issue #3025). Every SpecOps read is a read-only resolution,
    so persisting here would dirty the working tree on a plain `specops report`."""
    pointer = repo / ".specify" / "feature.json"
    before = pointer.read_bytes()
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/002-second")
    speckit.resolve_feature_dir(repo)
    assert pointer.read_bytes() == before


def test_resolution_creates_no_pointer_file_when_absent(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / ".specify" / "feature.json").unlink()
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/002-second")
    speckit.resolve_feature_dir(repo)
    assert not (repo / ".specify" / "feature.json").exists()


# --- T008: provenance ---------------------------------------------------------

def test_provenance_reports_override(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/002-second")
    resolved = speckit.resolve_feature(repo)
    assert resolved.source == "override"
    assert resolved.path is not None and resolved.path.name == "002-second"


def test_provenance_reports_pointer(repo: Path) -> None:
    resolved = speckit.resolve_feature(repo)
    assert resolved.source == "pointer"
    assert resolved.path is not None and resolved.path.name == "001-first"


def test_provenance_reports_inferred(repo: Path) -> None:
    (repo / ".specify" / "feature.json").unlink()
    resolved = speckit.resolve_feature(repo)
    assert resolved.source == "inferred"
    assert resolved.path is not None and resolved.path.name == "002-second"


def test_provenance_is_none_when_nothing_resolves(tmp_path: Path) -> None:
    resolved = speckit.resolve_feature(tmp_path)
    assert resolved.path is None and resolved.source is None


def test_legacy_entry_point_still_returns_a_bare_path(repo: Path) -> None:
    """`resolve_feature_dir` keeps its signature — every existing caller is unchanged."""
    fd = speckit.resolve_feature_dir(repo)
    assert isinstance(fd, Path)


# --- T009: an unresolvable override is reported, never silently ignored -------

def test_unresolvable_override_does_not_fall_back_to_the_pointer(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Silently falling back is how the two tools drift apart: Spec Kit would resolve
    the override's (missing) directory and fail, SpecOps would happily answer about
    the pointer's feature — the exact divergence this alignment removes."""
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/999-does-not-exist")
    resolved = speckit.resolve_feature(repo)
    assert resolved.source == "override"
    assert resolved.path is None
    assert resolved.error is not None and "999-does-not-exist" in resolved.error


def test_unresolvable_override_makes_the_bare_resolver_return_none(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/999-does-not-exist")
    assert speckit.resolve_feature_dir(repo) is None


def test_empty_override_is_treated_as_unset(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An exported-but-empty variable is not a selection — Spec Kit's `if ($env:...)`
    is falsy for an empty string, so the pointer file must still answer."""
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "")
    resolved = speckit.resolve_feature(repo)
    assert resolved.source == "pointer"
    assert resolved.path is not None and resolved.path.name == "001-first"
