"""`feature rename` — renumbering as a supported operation (Feature 026, US3).

A colleague's merge takes the number this feature reserved, so 026-y must become
027-y. Today that means hand-moving a directory, three artifacts, a branch reference
and a ledger that is explicitly not hand-editable — the field workaround was to delete
the ledger and re-run `init-spec`, destroying the audit trail the tool exists to keep
(#75). The rename is an *identity* change, not a history change: every recorded fact
travels through untouched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from specops import feature
from specops.errors import LedgerParseError, SpecopsError
from tests.conftest import git, make_v1_ledger

OLD = "specs/026-old-name"
NEW = "specs/027-new-name"


def _pointer(root: Path) -> str | None:
    p = root / ".specify" / "feature.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8")).get("feature_directory")


def _ledger(feature_dir: Path) -> dict:
    return yaml.safe_load((feature_dir / "status.yaml").read_text(encoding="utf-8"))


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo with a populated 026-old-name ledger: tasks, evidence, acks, cycles."""
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
        json.dumps({"feature_directory": OLD})
    )
    fd = root / OLD
    fd.mkdir(parents=True)
    (fd / "spec.md").write_text(
        "# Feature Specification: Old Name\n\n"
        "**Feature Branch**: `026-old-name`\n\n"
        "**Created**: 2026-09-01\n"
    )
    (fd / "plan.md").write_text(
        "# Plan\n\nArtifacts live under `specs/026-old-name/`.\n"
    )
    (fd / "tasks.md").write_text("- [ ] T001 do it\n")
    (fd / "checklists").mkdir()
    (fd / "checklists" / "requirements.md").write_text("Feature: 026-old-name\n")

    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    make_v1_ledger(
        fd, feature="026-old-name", branch=branch, baseline=git(root, "rev-parse", "HEAD"),
        tasks=[{"id": "T001", "status": "DONE", "started_commit": "a" * 40,
                "commits": ["b" * 40], "evidence": "CLI_LOG:done",
                "completed_at": "2026-09-01T00:00:00+00:00",
                "evidence_refs": ["EV-abc123def456"]}],
        review_cycles=[{"round": 1, "started_at": "2026-09-01",
                        "completed_at": "2026-09-01", "result": "APPROVED"}],
    )
    data = _ledger(fd)
    # A real feature's ledger carries the CAS revision counter; the v1 test builder
    # predates it. Preserving it across a rename is what keeps concurrent-write
    # detection meaningful afterwards.
    data["schema_version"] = 9
    data["revision"] = 7
    data["evidence"] = [{
        "id": "EV-abc123def456", "producer": "auto", "command": "c", "exit_code": 0,
        "timestamp": "2026-09-01T00:00:00+00:00", "commit_range": "a..b",
        "affected_paths": [], "summary": "CLI_LOG:done", "superseded_by": None,
    }]
    data["acknowledgements"] = [{"path": "src/x.py", "task": "T001", "reason": "tooling",
                                 "map_digest": None, "at": "2026-09-01T00:00:00+00:00"}]
    (fd / "status.yaml").write_text(yaml.dump(data))

    monkeypatch.delenv("SPECIFY_FEATURE_DIRECTORY", raising=False)
    return root


# ---------------------------------------------------------------------------
# T057 — every recorded fact survives
# ---------------------------------------------------------------------------

def test_every_ledger_record_survives_the_rename(repo: Path) -> None:
    """The rename is an identity change, not a history change."""
    before = _ledger(repo / OLD)
    feature.cmd_rename(repo, OLD, NEW)

    after = _ledger(repo / NEW)
    for key in ("tasks", "evidence", "acknowledgements", "review_cycles"):
        assert after[key] == before[key], f"{key} changed during the rename"
    assert after["revision"] == before["revision"]
    assert after["baseline"] == before["baseline"]


def test_the_old_directory_is_gone_and_the_new_one_holds_everything(repo: Path) -> None:
    feature.cmd_rename(repo, OLD, NEW)
    assert not (repo / OLD).exists()
    for artifact in ("spec.md", "plan.md", "tasks.md", "status.yaml"):
        assert (repo / NEW / artifact).is_file()
    assert (repo / NEW / "checklists" / "requirements.md").is_file()


# ---------------------------------------------------------------------------
# T058 — identity moves
# ---------------------------------------------------------------------------

def test_ledger_feature_name_follows(repo: Path) -> None:
    feature.cmd_rename(repo, OLD, NEW)
    assert _ledger(repo / NEW)["feature"] == "027-new-name"


def test_spec_identity_header_is_rewritten(repo: Path) -> None:
    """FR-016a: the one structured header SpecOps owns."""
    feature.cmd_rename(repo, OLD, NEW)
    spec = (repo / NEW / "spec.md").read_text(encoding="utf-8")
    assert "**Feature Branch**: `027-new-name`" in spec
    assert "026-old-name" not in spec


def test_artifact_prose_is_never_rewritten(repo: Path) -> None:
    """FR-016b: rewriting prose risks mangling a deliberate reference to another
    feature or a quoted example. Those are reported for a human to judge."""
    before = (repo / OLD / "plan.md").read_bytes()
    feature.cmd_rename(repo, OLD, NEW)
    assert (repo / NEW / "plan.md").read_bytes() == before


# ---------------------------------------------------------------------------
# T059 — the branch reference
# ---------------------------------------------------------------------------

def test_branch_flag_updates_the_ledger_reference(repo: Path) -> None:
    git(repo, "branch", "-m", "027-new-name")
    feature.cmd_rename(repo, OLD, NEW, branch="027-new-name")
    assert _ledger(repo / NEW)["branch"] == "027-new-name"


def test_without_the_flag_the_branch_reference_is_left_alone(repo: Path) -> None:
    before = _ledger(repo / OLD)["branch"]
    out = feature.cmd_rename(repo, OLD, NEW)
    assert _ledger(repo / NEW)["branch"] == before
    assert "branch reference unchanged" in out


def test_branch_update_warns_that_the_next_command_fails_closed(repo: Path) -> None:
    """data-model §5: `validate_identity` refuses any write when the ledger's branch
    differs from the current one. Correct fail-closed behaviour — but a silent version
    of it is an inexplicable refusal three commands later."""
    out = feature.cmd_rename(repo, OLD, NEW, branch="027-new-name")
    assert "027-new-name" in out
    assert "git" in out.lower()


# ---------------------------------------------------------------------------
# T060 — the pointer follows only when it pointed here
# ---------------------------------------------------------------------------

def test_pointer_follows_the_active_feature(repo: Path) -> None:
    out = feature.cmd_rename(repo, OLD, NEW)
    assert _pointer(repo) == NEW
    assert "pointer followed" in out.lower()


def test_pointer_is_left_alone_when_another_feature_is_active(repo: Path) -> None:
    other = repo / "specs" / "020-other"
    other.mkdir(parents=True)
    (other / "spec.md").write_text("# Other\n")
    (repo / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/020-other"})
    )
    out = feature.cmd_rename(repo, OLD, NEW)
    assert _pointer(repo) == "specs/020-other"
    assert "unchanged" in out.lower()


# ---------------------------------------------------------------------------
# T061 — an override naming the source is refused
# ---------------------------------------------------------------------------

def test_rename_is_refused_when_an_override_names_the_source(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-019a: the override outranks the pointer file, so completing the rename would
    leave it aimed at a directory that no longer exists — breaking every subsequent
    command with an error about a path the operator never typed."""
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", OLD)
    with pytest.raises(SpecopsError) as exc:
        feature.cmd_rename(repo, OLD, NEW)
    assert "SPECIFY_FEATURE_DIRECTORY" in exc.value.message
    assert (repo / OLD).is_dir() and not (repo / NEW).exists()


def test_rename_proceeds_when_the_override_names_another_feature(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only an override on the *source* is invalidated by the rename."""
    other = repo / "specs" / "020-other"
    other.mkdir(parents=True)
    (other / "spec.md").write_text("# Other\n")
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/020-other")
    feature.cmd_rename(repo, OLD, NEW)
    assert (repo / NEW).is_dir()


# ---------------------------------------------------------------------------
# T062 — remaining references are reported, not touched
# ---------------------------------------------------------------------------

def test_remaining_references_are_reported_with_file_and_line(repo: Path) -> None:
    out = feature.cmd_rename(repo, OLD, NEW)
    assert "plan.md:3" in out
    assert "checklists/requirements.md:1" in out


def test_reported_references_are_left_byte_identical(repo: Path) -> None:
    before = (repo / OLD / "checklists" / "requirements.md").read_bytes()
    feature.cmd_rename(repo, OLD, NEW)
    assert (repo / NEW / "checklists" / "requirements.md").read_bytes() == before


def test_a_clean_rename_reports_no_remaining_references(repo: Path) -> None:
    (repo / OLD / "plan.md").write_text("# Plan\n")
    (repo / OLD / "checklists" / "requirements.md").write_text("nothing here\n")
    out = feature.cmd_rename(repo, OLD, NEW)
    assert "remaining reference" not in out


# ---------------------------------------------------------------------------
# T063 — refusals leave everything untouched
# ---------------------------------------------------------------------------

def test_existing_target_is_refused(repo: Path) -> None:
    (repo / NEW).mkdir(parents=True)
    with pytest.raises(SpecopsError, match="already exists"):
        feature.cmd_rename(repo, OLD, NEW)
    assert (repo / OLD / "status.yaml").is_file()


def test_missing_source_is_refused(repo: Path) -> None:
    with pytest.raises(SpecopsError, match="not found"):
        feature.cmd_rename(repo, "specs/999-nope", NEW)
    assert not (repo / NEW).exists()


def test_source_without_a_spec_is_refused(repo: Path) -> None:
    (repo / OLD / "spec.md").unlink()
    with pytest.raises(SpecopsError, match="spec.md"):
        feature.cmd_rename(repo, OLD, NEW)


def test_target_outside_specs_is_refused(repo: Path, tmp_path: Path) -> None:
    with pytest.raises(SpecopsError, match="specs/"):
        feature.cmd_rename(repo, OLD, str(tmp_path / "elsewhere"))
    assert (repo / OLD).is_dir()


def test_renaming_onto_itself_is_refused(repo: Path) -> None:
    with pytest.raises(SpecopsError):
        feature.cmd_rename(repo, OLD, OLD)


# ---------------------------------------------------------------------------
# T064 — infrastructure failures exit 2
# ---------------------------------------------------------------------------

def test_unparseable_ledger_raises_exit_2(repo: Path) -> None:
    (repo / OLD / "status.yaml").write_text("{[not: valid yaml")
    with pytest.raises(LedgerParseError) as exc:
        feature.cmd_rename(repo, OLD, NEW)
    assert exc.value.exit_code == 2
    assert (repo / OLD).is_dir() and not (repo / NEW).exists()


def test_outside_a_git_repository_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "nogit"
    (root / ".specify").mkdir(parents=True)
    src = root / OLD
    src.mkdir(parents=True)
    (src / "spec.md").write_text("# x\n")
    with pytest.raises(SpecopsError, match="[Gg]it"):
        feature.cmd_rename(root, OLD, NEW)


# ---------------------------------------------------------------------------
# T065 — atomicity
# ---------------------------------------------------------------------------

def test_a_failed_directory_move_leaves_the_pre_rename_state(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-020: no half-moved directory, and no pointer aimed at nothing."""
    import os

    def _boom(*_a: object, **_k: object) -> None:
        raise OSError("disk on fire")

    monkeypatch.setattr(os, "rename", _boom)
    with pytest.raises(SpecopsError):
        feature.cmd_rename(repo, OLD, NEW)

    assert (repo / OLD).is_dir()
    assert not (repo / NEW).exists()
    assert _pointer(repo) == OLD          # the pointer is written last, so it never moved
    assert _ledger(repo / OLD)["feature"] == "026-old-name"   # identity write rolled back


def test_a_feature_with_no_ledger_can_still_be_renamed(repo: Path) -> None:
    """Renaming before `init-spec` is legitimate — there is simply no identity to carry."""
    (repo / OLD / "status.yaml").unlink()
    feature.cmd_rename(repo, OLD, NEW)
    assert (repo / NEW / "spec.md").is_file()
    assert _pointer(repo) == NEW


def test_a_failed_move_restores_a_header_that_was_not_the_directory_name(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback restores what the header *held*, not the old directory name.

    A `**Feature Branch**` header may legitimately name something else. Writing the
    directory name back on failure corrupts it instead of restoring the pre-rename state.
    """
    import os

    spec = repo / OLD / "spec.md"
    spec.write_text(spec.read_text().replace("`026-old-name`", "`feat/recovery`"))
    monkeypatch.setattr(os, "rename", lambda *_a, **_k: (_ for _ in ()).throw(OSError("no")))

    with pytest.raises(SpecopsError):
        feature.cmd_rename(repo, OLD, NEW)

    assert "**Feature Branch**: `feat/recovery`" in spec.read_text()


def test_non_ascii_ledger_content_is_not_escaped_by_the_rename(repo: Path) -> None:
    """The rename rewrites the ledger identity; it must not re-encode recorded facts.

    A local `yaml.dump` defaults to `allow_unicode=False` and turns every accent into
    a \\uXXXX escape — a rewrite of content this command promises never to touch.
    """
    data = _ledger(repo / OLD)
    data["evidence"][0]["summary"] = "CLI_LOG:validação — ok"
    (repo / OLD / "status.yaml").write_text(
        yaml.dump(data, allow_unicode=True), encoding="utf-8"
    )

    feature.cmd_rename(repo, OLD, NEW)

    raw = (repo / NEW / "status.yaml").read_text(encoding="utf-8")
    assert "validação — ok" in raw
    assert "\\u" not in raw


def test_a_malformed_pointer_aborts_before_the_identity_is_written(repo: Path) -> None:
    """The pointer read raises exit 2; doing it after the in-place writes would leave
    the source directory stamped with an identity its name does not carry."""
    (repo / ".specify" / "feature.json").write_text("{ not json")

    with pytest.raises(LedgerParseError):
        feature.cmd_rename(repo, OLD, NEW)

    assert _ledger(repo / OLD)["feature"] == "026-old-name"
    assert "`026-old-name`" in (repo / OLD / "spec.md").read_text()


def test_a_short_branch_name_does_not_match_inside_words(repo: Path) -> None:
    """A ledger recorded on `main` must not turn every "remaining"/"domain" in the
    artifacts into a stale reference — the scan matches whole identifiers only."""
    data = _ledger(repo / OLD)
    data["branch"] = "main"
    (repo / OLD / "status.yaml").write_text(yaml.dump(data), encoding="utf-8")
    (repo / OLD / "plan.md").write_text("# Plan\nremaining work in this domain\n")
    (repo / OLD / "checklists" / "requirements.md").write_text("maintainable\n")

    out = feature.cmd_rename(repo, OLD, NEW)
    assert "remaining reference" not in out

    # A real whole-word mention is still reported.
    (repo / NEW / "plan.md").write_text("# Plan\nbased on main\n")
    out = feature.cmd_rename(repo, NEW, "specs/028-third")
    assert "plan.md:2" in out


def test_branch_is_not_silently_dropped_when_the_feature_has_no_ledger(repo: Path) -> None:
    """--branch has nothing to record without a ledger; saying so beats exit 0 and
    a caller believing the reference was updated."""
    (repo / OLD / "status.yaml").unlink()
    out = feature.cmd_rename(repo, OLD, NEW, branch="027-new-name")
    assert "not recorded" in out
