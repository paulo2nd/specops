"""Integration tests for Ledger v2 migration and read-only safety (Feature 006).

Exercises the real `specops` CLI against synthetic v1 ledgers in a Git repo.
"""
import subprocess
from pathlib import Path

import yaml

from specops import ledger


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["specops", *args], cwd=repo, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    ).stdout.strip()


def _write_v1(
    feature_dir: Path,
    repo: Path,
    *,
    phase: str = "SPECIFY",
    tasks: list | None = None,
    review_cycles: list | None = None,
) -> None:
    """Write a v1-shaped ledger (no schema_version) with valid workspace identity."""
    data = {
        "feature": feature_dir.name,
        "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "baseline": _git(repo, "rev-parse", "HEAD"),
        "created_at": "2026-07-05",
        "updated_at": "2026-07-05",
        "current_phase": phase,
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": tasks or [],
        "review_cycles": review_cycles or [],
    }
    (feature_dir / "status.yaml").write_text(yaml.dump(data))


class TestExplicitMigration:
    def test_lossless_migration_and_backup(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        _write_v1(
            feature_dir, repo, phase="REVIEW",
            tasks=[{"id": "T001", "status": "DONE", "started_commit": "aaa",
                    "commits": ["bbb"], "evidence": "CLI_LOG:done", "completed_at": "2026-07-05"}],
            review_cycles=[{"round": 1, "started_at": "2026-07-05",
                            "completed_at": "2026-07-05", "result": "APPROVED"}],
        )

        r = _run(repo, "status", "migrate")
        assert r.returncode == 0, r.stderr
        assert "migrated" in r.stdout

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["schema_version"] == ledger.CURRENT_SCHEMA
        assert data["revision"] == 1
        # Losslessness (SC-001): task evidence + review cycle preserved
        assert data["tasks"][0]["evidence"] == "CLI_LOG:done"
        assert data["review_cycles"][0]["result"] == "APPROVED"
        # Feature 009: pre-v3 records gain the explicit no-map provenance marker
        assert data["tasks"][0]["context_provenance"] == {"map": "none"}
        assert data["review_cycles"][0]["context_provenance"] == {"map": "none"}
        # Timezone-aware (SC-007)
        assert data["created_at"].endswith("+00:00")
        # Backup recorded and present (FR-008a)
        backup_rel = data["recovery"]["migrated_from_backup"]
        assert backup_rel is not None
        assert (repo / backup_rel).is_file()

    def test_migrate_is_idempotent(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        _write_v1(feature_dir, repo)

        r1 = _run(repo, "status", "migrate")
        assert "migrated" in r1.stdout
        after_first = (feature_dir / "status.yaml").read_bytes()

        r2 = _run(repo, "status", "migrate")
        assert r2.returncode == 0
        assert "already current" in r2.stdout
        # Idempotent: no rewrite on the second run (FR-008, SC-005)
        assert (feature_dir / "status.yaml").read_bytes() == after_first


class TestAutoMigration:
    def test_state_change_auto_migrates(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        _write_v1(feature_dir, repo, phase="SPECIFY")

        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 0, r.stderr

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["schema_version"] == ledger.CURRENT_SCHEMA
        assert data["current_phase"] == "PLAN"
        assert data["active_artifact"] == "plan.md"
        assert data["recovery"]["migrated_from_backup"] is not None


class TestWorkflowBlockBackfill:
    """Feature 007: the additive `workflow` block is back-filled on a state change,
    for both a migrating v1 ledger and a current-schema ledger that predates it."""

    def _write_current_no_workflow(self, feature_dir: Path, repo: Path) -> None:
        ts = "2026-07-05T00:00:00+00:00"
        data = {
            "schema_version": ledger.CURRENT_SCHEMA, "revision": 1,
            "feature": feature_dir.name,
            "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
            "baseline": _git(repo, "rev-parse", "HEAD"),
            "workflow_lane": "full", "active_artifact": "spec.md",
            "created_at": ts, "updated_at": ts, "current_phase": "SPECIFY",
            "recovery": {"active_task": None, "last_commit": None, "blockers": [],
                         "last_consistent_revision": 1, "last_consistent_at": ts,
                         "migrated_from_backup": None},
            "tasks": [], "review_cycles": [],
        }
        (feature_dir / "status.yaml").write_text(yaml.dump(data))

    def test_current_gains_workflow_block_on_state_change(
        self, fake_speckit_repo: Path
    ) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        self._write_current_no_workflow(feature_dir, repo)

        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 0, r.stderr

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        # no re-migration (already current); additive back-fill only
        assert data["schema_version"] == ledger.CURRENT_SCHEMA
        assert data["workflow"] == {"skipped_steps": []}
        assert data["current_phase"] == "PLAN"

    def test_v1_migration_produces_workflow_block(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        _write_v1(feature_dir, repo, phase="SPECIFY")

        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 0, r.stderr

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["workflow"] == {"skipped_steps": []}


class TestReadOnlySafety:
    def test_show_does_not_migrate_v1(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        _write_v1(feature_dir, repo)
        before = (feature_dir / "status.yaml").read_bytes()

        r = _run(repo, "status", "show")
        assert r.returncode == 0, r.stderr
        assert "diagnostic" in r.stdout  # FR-029a
        assert (feature_dir / "status.yaml").read_bytes() == before  # SC-006

    def test_too_new_refuses_state_change_but_show_works(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        _write_v1(feature_dir, repo)
        # Bump to a too-new schema
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        data["schema_version"] = 99
        (feature_dir / "status.yaml").write_text(yaml.dump(data))
        before = (feature_dir / "status.yaml").read_bytes()

        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 1  # FR-005 refuse
        assert (feature_dir / "status.yaml").read_bytes() == before  # unchanged

        r = _run(repo, "status", "show")
        assert r.returncode == 0  # read-only still works (FR-029a)
        assert "diagnostic" in r.stdout
