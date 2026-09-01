"""`feature use` — repointing the active feature by command (Feature 026, US2).

`.specify/feature.json` selects the feature every command answers about, and nothing
wrote it: starting a new feature meant hand-editing the file, which sits awkwardly
with the workflow's own rule that ledger state is CLI-only (#75). Worse, the failure
was silent and reported success — `consistency` answering `ok` about a finished
feature while the one under work went unvalidated.

The repoint reports what it moved and what it left behind. It refuses only when the
write cannot take effect (an environment override outranks it) or the target is not a
feature — never because it disapproves of leaving work behind.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from specops import feature
from specops.errors import LedgerParseError, SpecopsError
from tests.conftest import git, make_v1_ledger


def _pointer(root: Path) -> str | None:
    p = root / ".specify" / "feature.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8")).get("feature_directory")


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Two features: 001-first (active, with a ledger) and 002-second (spec only)."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "t@t.com")
    git(root, "config", "user.name", "T")
    (root / "README.md").write_text("# test")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "init")

    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-first"})
    )
    first = root / "specs" / "001-first"
    first.mkdir(parents=True)
    (first / "spec.md").write_text("# First\n")
    (first / "plan.md").write_text("# Plan\n")
    (first / "tasks.md").write_text("- [ ] T001 a\n")
    make_v1_ledger(
        first, feature="001-first",
        branch=git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        baseline=git(root, "rev-parse", "HEAD"),
    )

    second = root / "specs" / "002-second"
    second.mkdir(parents=True)
    (second / "spec.md").write_text("# Second\n")

    monkeypatch.delenv("SPECIFY_FEATURE_DIRECTORY", raising=False)
    return root


# ---------------------------------------------------------------------------
# T042 — happy path and idempotency
# ---------------------------------------------------------------------------

def test_repoint_moves_the_pointer(repo: Path) -> None:
    out = feature.cmd_use(repo, "specs/002-second")
    assert _pointer(repo) == "specs/002-second"
    assert "001-first" in out and "002-second" in out


def test_repoint_is_idempotent(repo: Path) -> None:
    """Acceptance scenario 5: pointing at the already-active feature is a no-op."""
    before = (repo / ".specify" / "feature.json").read_bytes()
    out = feature.cmd_use(repo, "specs/001-first")
    assert (repo / ".specify" / "feature.json").read_bytes() == before
    assert "already" in out.lower()


def test_repoint_accepts_a_trailing_separator(repo: Path) -> None:
    feature.cmd_use(repo, "specs/002-second/")
    assert _pointer(repo) == "specs/002-second"


def test_repoint_stores_a_posix_relative_path(repo: Path) -> None:
    """The pointer is read by Spec Kit too; a backslash would make it platform-bound."""
    feature.cmd_use(repo, str(repo / "specs" / "002-second"))
    assert _pointer(repo) == "specs/002-second"


# ---------------------------------------------------------------------------
# T043 — missing downstream artifacts are reported, never fatal
# ---------------------------------------------------------------------------

def test_missing_artifacts_are_named_without_failing(repo: Path) -> None:
    """Acceptance scenario 3: pointing at a feature *before* planning it is the normal
    flow this command exists to serve."""
    out = feature.cmd_use(repo, "specs/002-second")
    assert _pointer(repo) == "specs/002-second"
    for missing in ("plan.md", "tasks.md", "status.yaml"):
        assert missing in out


def test_a_complete_feature_reports_nothing_missing(repo: Path) -> None:
    feature.cmd_use(repo, "specs/002-second")   # move away first
    out = feature.cmd_use(repo, "specs/001-first")
    assert "Not yet present" not in out


# ---------------------------------------------------------------------------
# T044 — unfinished work is reported, never a refusal
# ---------------------------------------------------------------------------

def _leave_work_in_progress(repo: Path) -> None:
    fd = repo / "specs" / "001-first"
    data = yaml.safe_load((fd / "status.yaml").read_text())
    data["tasks"] = [{"id": "T001", "status": "IN_PROGRESS", "started_commit": "a" * 40,
                      "commits": [], "evidence": None, "completed_at": None}]
    data["recovery"] = {"active_task": "T001", "last_commit": None}
    (fd / "status.yaml").write_text(yaml.dump(data))


def test_unfinished_work_is_reported_and_the_repoint_proceeds(repo: Path) -> None:
    """FR-012a: warn and proceed. A hard refusal would break the legitimate case of
    parking a feature to attend to another, and SpecOps does not judge intent."""
    _leave_work_in_progress(repo)
    out = feature.cmd_use(repo, "specs/002-second")
    assert _pointer(repo) == "specs/002-second"
    assert "T001" in out


def test_an_open_review_round_is_reported(repo: Path) -> None:
    fd = repo / "specs" / "001-first"
    data = yaml.safe_load((fd / "status.yaml").read_text())
    data["review_cycles"] = [{"round": 2, "started_at": "2026-09-01",
                              "completed_at": None, "result": None}]
    (fd / "status.yaml").write_text(yaml.dump(data))
    out = feature.cmd_use(repo, "specs/002-second")
    assert _pointer(repo) == "specs/002-second"
    assert "round 2" in out


def test_no_override_flag_is_needed_to_leave_work_behind(repo: Path) -> None:
    import inspect
    params = set(inspect.signature(feature.cmd_use).parameters)
    assert not {p for p in params if "force" in p or "override" in p}


# ---------------------------------------------------------------------------
# T045 — a never-initialized outgoing feature has nothing unfinished
# ---------------------------------------------------------------------------

def test_outgoing_feature_without_a_ledger_reports_no_warning(repo: Path) -> None:
    feature.cmd_use(repo, "specs/002-second")          # 002 has no ledger
    out = feature.cmd_use(repo, "specs/001-first")
    assert "unfinished" not in out.lower()


# ---------------------------------------------------------------------------
# T046 — a foreign ledger name is reported, not pre-judged
# ---------------------------------------------------------------------------

def test_a_ledger_naming_a_different_feature_is_reported_not_refused(repo: Path) -> None:
    """SpecOps records the pointer move and lets `consistency`/`reconcile` report the
    mismatch, rather than deciding for the operator that it is wrong."""
    second = repo / "specs" / "002-second"
    make_v1_ledger(second, feature="totally-different-name")
    out = feature.cmd_use(repo, "specs/002-second")
    assert _pointer(repo) == "specs/002-second"
    assert "totally-different-name" in out


# ---------------------------------------------------------------------------
# T047 — refusals (exit 1) leave the pointer untouched
# ---------------------------------------------------------------------------

def test_missing_directory_is_refused(repo: Path) -> None:
    before = (repo / ".specify" / "feature.json").read_bytes()
    with pytest.raises(SpecopsError, match="not found"):
        feature.cmd_use(repo, "specs/999-nope")
    assert (repo / ".specify" / "feature.json").read_bytes() == before


def test_directory_outside_specs_is_refused(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "spec.md").write_text("# x\n")
    before = (repo / ".specify" / "feature.json").read_bytes()
    with pytest.raises(SpecopsError, match="specs/"):
        feature.cmd_use(repo, str(outside))
    assert (repo / ".specify" / "feature.json").read_bytes() == before


def test_directory_without_a_spec_is_refused(repo: Path) -> None:
    (repo / "specs" / "003-empty").mkdir(parents=True)
    before = (repo / ".specify" / "feature.json").read_bytes()
    with pytest.raises(SpecopsError, match="spec.md"):
        feature.cmd_use(repo, "specs/003-empty")
    assert (repo / ".specify" / "feature.json").read_bytes() == before


def test_repoint_is_refused_when_an_override_names_elsewhere(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-010a: the override outranks the pointer file, so writing it would have no
    effect. Reporting success on a write that cannot take effect is the #75 failure
    mode itself — a silent no-op that says `ok`."""
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/001-first")
    before = (repo / ".specify" / "feature.json").read_bytes()
    with pytest.raises(SpecopsError) as exc:
        feature.cmd_use(repo, "specs/002-second")
    assert "SPECIFY_FEATURE_DIRECTORY" in exc.value.message
    assert (repo / ".specify" / "feature.json").read_bytes() == before


def test_repoint_is_allowed_when_the_override_names_the_target(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not a blanket refusal: writing the pointer to where the override already points
    is consistent, so it proceeds (and makes the pointer survive the override going away)."""
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/002-second")
    feature.cmd_use(repo, "specs/002-second")
    assert _pointer(repo) == "specs/002-second"


# ---------------------------------------------------------------------------
# T048 — infrastructure failures exit 2
# ---------------------------------------------------------------------------

def test_malformed_pointer_file_raises_exit_2(repo: Path) -> None:
    (repo / ".specify" / "feature.json").write_text("{not json")
    with pytest.raises(LedgerParseError) as exc:
        feature.cmd_use(repo, "specs/002-second")
    assert exc.value.exit_code == 2


def test_outside_a_git_repository_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "nogit"
    (root / ".specify").mkdir(parents=True)
    (root / "specs" / "001-x").mkdir(parents=True)
    (root / "specs" / "001-x" / "spec.md").write_text("# x\n")
    with pytest.raises(SpecopsError, match="[Gg]it"):
        feature.cmd_use(root, "specs/001-x")
