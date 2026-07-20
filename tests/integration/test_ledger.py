"""Integration tests for the ledger — Quickstart Scenarios B and E, plus
Ledger v2 identity, concurrency, and interruption guarantees (Feature 006)."""
import copy
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from specops import ledger, status
from specops.errors import StaleLedgerError


def _commit(repo: Path, msg: str = "work") -> str:
    (repo / f"{msg}.txt").write_text(msg)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    return result.stdout.strip()


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["specops", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Scenario B — Full ledger loop
# ---------------------------------------------------------------------------

class TestScenarioB:
    def setup_method(self, fake_speckit_repo: Path) -> None:
        pass

    def test_full_ledger_loop(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"

        # Write tasks.md
        (feature_dir / "tasks.md").write_text(
            "- [ ] T001 First task\n- [ ] T002 Second task\n"
        )

        # Write specops.json with a passing test command
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "true", "lint_command": "", "skills_dir": ""})
        )

        # B-1: init-spec creates status.yaml
        r = _run(repo, "status", "init-spec")
        assert r.returncode == 0, r.stderr
        ledger_path = feature_dir / "status.yaml"
        assert ledger_path.is_file()

        data = yaml.safe_load(ledger_path.read_text())
        task_ids = [t["id"] for t in data["tasks"]]
        assert "T001" in task_ids and "T002" in task_ids

        # B-2: start T001
        r = _run(repo, "status", "start-task", "T001")
        assert r.returncode == 0, r.stderr

        # B-3: start T002 while T001 active → exit 1
        r = _run(repo, "status", "start-task", "T002")
        assert r.returncode == 1

        # B-4: commit work, then complete T001 --auto
        _commit(repo, "T001-work")
        r = _run(repo, "status", "complete-task", "T001", "--auto")
        assert r.returncode == 0, r.stderr

        data = yaml.safe_load(ledger_path.read_text())
        t001 = next(t for t in data["tasks"] if t["id"] == "T001")
        assert t001["status"] == "DONE"
        assert t001["evidence"] is not None
        assert "TEST_REPORT" in t001["evidence"]
        assert len(t001["commits"]) > 0

    def test_failing_test_command_blocks_completion(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"

        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "false", "lint_command": "", "skills_dir": ""})
        )

        _run(repo, "status", "init-spec")
        _run(repo, "status", "start-task", "T001")
        _commit(repo, "work")

        r = _run(repo, "status", "complete-task", "T001", "--auto")
        assert r.returncode == 1, "Failing test_command should prevent completion"

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        t001 = next(t for t in data["tasks"] if t["id"] == "T001")
        assert t001["status"] == "IN_PROGRESS"

    def test_manual_evidence_path(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"

        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "false", "lint_command": "", "skills_dir": ""})
        )

        _run(repo, "status", "init-spec")
        _run(repo, "status", "start-task", "T001")

        # B-6a: --evidence flag with failing test_command → ok
        r = _run(repo, "status", "complete-task", "T001", "--evidence", "CLI_LOG:manual check ok")
        assert r.returncode == 0, r.stderr

    def test_complete_without_flag_fails(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"

        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        (repo / "specops.json").write_text(json.dumps({"test_command": "true"}))

        _run(repo, "status", "init-spec")
        _run(repo, "status", "start-task", "T001")

        # B-6b: no flag → exit 1
        r = _run(repo, "status", "complete-task", "T001")
        assert r.returncode == 1


# ---------------------------------------------------------------------------
# Scenario E — Phase machine walk
# ---------------------------------------------------------------------------

class TestScenarioE:
    def test_phase_walk_and_corrective_loop(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")

        _run(repo, "status", "init-spec")

        # E-1: SPECIFY → PLAN
        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 0

        # E-2: skip TASKS → REVIEW (should fail)
        r = _run(repo, "status", "transition-phase", "REVIEW")
        assert r.returncode == 1

        # Walk to REVIEW
        _run(repo, "status", "transition-phase", "TASKS")
        _run(repo, "status", "transition-phase", "IMPLEMENT")
        r = _run(repo, "status", "transition-phase", "REVIEW")
        assert r.returncode == 0

        # E-3: REVIEW → IMPLEMENT -r REJECTED (corrective loop)
        r = _run(repo, "status", "transition-phase", "IMPLEMENT", "-r", "REJECTED")
        assert r.returncode == 0

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["current_phase"] == "IMPLEMENT"
        assert len(data["review_cycles"]) >= 2

        # E-4: transition DONE without APPROVED latest → fail
        _run(repo, "status", "transition-phase", "REVIEW")
        r = _run(repo, "status", "transition-phase", "DONE")
        assert r.returncode == 1


# ---------------------------------------------------------------------------
# T007 — SC-001: full lifecycle SPECIFY→DONE -r APPROVED via CLI only
# ---------------------------------------------------------------------------

class TestFullLifecycleSC001:
    def test_full_lifecycle_approve_via_cli(self, fake_speckit_repo: Path) -> None:
        """SPECIFY→PLAN→TASKS→IMPLEMENT→REVIEW→DONE -r APPROVED with no manual ledger edits."""
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 only task\n")
        (repo / "specops.json").write_text(
            json.dumps({"test_command": "true", "lint_command": "", "skills_dir": ""})
        )

        # Init ledger
        r = _run(repo, "status", "init-spec")
        assert r.returncode == 0, r.stderr

        # Phase walk: SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW
        for phase in ("PLAN", "TASKS", "IMPLEMENT", "REVIEW"):
            r = _run(repo, "status", "transition-phase", phase)
            assert r.returncode == 0, f"transition to {phase} failed: {r.stderr}"

        # Verify in REVIEW phase
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["current_phase"] == "REVIEW"
        assert len(data["review_cycles"]) == 1
        assert data["review_cycles"][0]["result"] is None

        # REVIEW → DONE -r APPROVED (no manual ledger edit)
        r = _run(repo, "status", "transition-phase", "DONE", "-r", "APPROVED")
        assert r.returncode == 0, r.stderr

        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["current_phase"] == "DONE"
        assert data["review_cycles"][-1]["result"] == "APPROVED"
        assert data["review_cycles"][-1]["completed_at"] is not None

    def test_invalid_result_rejected_by_cli(self, fake_speckit_repo: Path) -> None:
        """CLI rejects invalid result vocabulary before touching the ledger."""
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")

        _run(repo, "status", "init-spec")
        for phase in ("PLAN", "TASKS", "IMPLEMENT", "REVIEW"):
            _run(repo, "status", "transition-phase", phase)

        original = (feature_dir / "status.yaml").read_text()
        r = _run(repo, "status", "transition-phase", "DONE", "-r", "maybe")
        assert r.returncode == 1
        assert (feature_dir / "status.yaml").read_text() == original


# ---------------------------------------------------------------------------
# Feature 006 — US3: workspace identity gate [SC-003]
# ---------------------------------------------------------------------------

class TestWorkspaceIdentity:
    def _init(self, repo: Path) -> Path:
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        assert _run(repo, "status", "init-spec").returncode == 0
        return feature_dir

    def test_consistent_workspace_passes(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        self._init(repo)
        assert _run(repo, "status", "transition-phase", "PLAN").returncode == 0

    def test_branch_divergence_refused(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = self._init(repo)
        before = (feature_dir / "status.yaml").read_bytes()
        subprocess.run(["git", "checkout", "-b", "other"], cwd=repo, check=True,
                       capture_output=True)
        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 1
        assert "branch" in r.stderr.lower()
        assert (feature_dir / "status.yaml").read_bytes() == before

    def test_baseline_divergence_refused(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = self._init(repo)
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        data["baseline"] = "deadbeef" * 5  # unreachable commit
        (feature_dir / "status.yaml").write_text(yaml.dump(data))
        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 1
        assert "baseline" in r.stderr.lower()

    def test_feature_divergence_refused(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = self._init(repo)
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        data["feature"] = "999-wrong"
        (feature_dir / "status.yaml").write_text(yaml.dump(data))
        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 1
        assert "feature" in r.stderr.lower()


# ---------------------------------------------------------------------------
# Review remediation — identity escape hatch + gate consistency
# ---------------------------------------------------------------------------

class TestRebaselineAndGateConsistency:
    def _init(self, repo: Path) -> Path:
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        assert _run(repo, "status", "init-spec").returncode == 0
        return feature_dir

    def test_rebaseline_unblocks_after_branch_rename(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = self._init(repo)
        subprocess.run(["git", "branch", "-m", "renamed"], cwd=repo, check=True,
                       capture_output=True)
        # Identity gate refuses under the new branch name...
        assert _run(repo, "status", "transition-phase", "PLAN").returncode == 1
        # ...until the explicit re-baseline escape hatch re-anchors identity.
        r = _run(repo, "status", "rebaseline")
        assert r.returncode == 0, r.stderr
        assert "renamed" in r.stdout
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["branch"] == "renamed"
        # Now the state change proceeds.
        assert _run(repo, "status", "transition-phase", "PLAN").returncode == 0

    def test_rebaseline_migrates_v1_ledger(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                              capture_output=True, text=True).stdout.strip()
        # v1 ledger on the wrong branch name → identity refuses, rebaseline fixes + migrates.
        (feature_dir / "status.yaml").write_text(yaml.dump({
            "feature": "001-demo", "branch": "old-name", "baseline": head,
            "created_at": "2026-07-05", "updated_at": "2026-07-05",
            "current_phase": "SPECIFY",
            "recovery": {"active_task": None, "last_commit": None, "blockers": []},
            "tasks": [], "review_cycles": [],
        }))
        r = _run(repo, "status", "rebaseline")
        assert r.returncode == 0, r.stderr
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        assert data["schema_version"] == 2  # migrated as part of rebaseline
        assert data["branch"] != "old-name"

    def test_rebaseline_refuses_feature_mismatch(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = self._init(repo)
        data = yaml.safe_load((feature_dir / "status.yaml").read_text())
        data["feature"] = "999-wrong"
        (feature_dir / "status.yaml").write_text(yaml.dump(data))
        r = _run(repo, "status", "rebaseline")
        assert r.returncode == 1
        assert "feature" in r.stderr.lower()

    def test_migrate_refuses_on_identity_mismatch(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        # v1 ledger on a branch that no longer matches
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                              capture_output=True, text=True).stdout.strip()
        (feature_dir / "status.yaml").write_text(yaml.dump({
            "feature": "001-demo", "branch": "gone", "baseline": head,
            "created_at": "2026-07-05", "updated_at": "2026-07-05",
            "current_phase": "SPECIFY",
            "recovery": {"active_task": None, "last_commit": None, "blockers": []},
            "tasks": [], "review_cycles": [],
        }))
        before = (feature_dir / "status.yaml").read_bytes()
        r = _run(repo, "status", "migrate")
        assert r.returncode == 1  # migrate now fails closed like every write path
        assert "branch" in r.stderr.lower()
        assert (feature_dir / "status.yaml").read_bytes() == before

    def test_legacy_invariant_violation_does_not_block_unrelated_command(
        self, fake_speckit_repo: Path
    ) -> None:
        """A pre-existing (legacy) invariant defect must not brick unrelated commands."""
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                              capture_output=True, text=True).stdout.strip()
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo,
                               capture_output=True, text=True).stdout.strip()
        # v1 ledger carrying a legacy defect: a DONE task with no evidence.
        (feature_dir / "status.yaml").write_text(yaml.dump({
            "feature": "001-demo", "branch": branch, "baseline": head,
            "created_at": "2026-07-05", "updated_at": "2026-07-05",
            "current_phase": "SPECIFY",
            "recovery": {"active_task": None, "last_commit": None, "blockers": []},
            "tasks": [{"id": "T001", "status": "DONE", "started_commit": "x",
                       "commits": [], "evidence": None, "completed_at": None}],
            "review_cycles": [],
        }))
        # A phase transition (which does not touch the defective task) must succeed.
        r = _run(repo, "status", "transition-phase", "PLAN")
        assert r.returncode == 0, r.stderr
        assert yaml.safe_load((feature_dir / "status.yaml").read_text())["current_phase"] == "PLAN"

    def test_orphaned_active_task_still_blocks_start(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 a\n- [ ] T002 b\n")
        assert _run(repo, "status", "init-spec").returncode == 0
        assert _run(repo, "status", "start-task", "T001").returncode == 0
        # Remove the in-flight task from tasks.md so it becomes orphaned.
        (feature_dir / "tasks.md").write_text("- [ ] T002 b\n")
        r = _run(repo, "status", "start-task", "T002")
        assert r.returncode == 1  # orphaned in-flight T001 still blocks a new start
        assert "IN_PROGRESS" in r.stderr


# ---------------------------------------------------------------------------
# Feature 006 — US2: lost-update protection [SC-002]
# ---------------------------------------------------------------------------

class TestConcurrency:
    def _init(self, repo: Path) -> Path:
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        assert _run(repo, "status", "init-spec").returncode == 0
        return feature_dir

    def test_stale_write_rejected_first_change_survives(self, fake_speckit_repo: Path) -> None:
        feature_dir = self._init(fake_speckit_repo)
        base = ledger.revision_of(ledger.load_raw(feature_dir))

        first = ledger.load_raw(feature_dir)
        first["current_phase"] = "PLAN"
        ledger.save(feature_dir, first, base_revision=base)  # commits, revision advances

        stale = copy.deepcopy(first)
        stale["current_phase"] = "TASKS"
        with pytest.raises(StaleLedgerError):
            ledger.save(feature_dir, stale, base_revision=base)

        survived = ledger.load_raw(feature_dir)
        assert survived["current_phase"] == "PLAN"

    def test_single_winner_among_two_writers(self, fake_speckit_repo: Path) -> None:
        feature_dir = self._init(fake_speckit_repo)
        base = ledger.revision_of(ledger.load_raw(feature_dir))
        a = ledger.load_raw(feature_dir)
        a["current_phase"] = "PLAN"
        b = ledger.load_raw(feature_dir)
        b["current_phase"] = "PLAN"
        ledger.save(feature_dir, a, base_revision=base)
        with pytest.raises(StaleLedgerError):
            ledger.save(feature_dir, b, base_revision=base)


# ---------------------------------------------------------------------------
# Feature 006 — US4: interruption safety [SC-004]
# ---------------------------------------------------------------------------

class TestInterruptionSafety:
    def test_interrupted_transition_leaves_prior_ledger(self, fake_speckit_repo: Path) -> None:
        repo = fake_speckit_repo
        feature_dir = repo / "specs" / "001-demo"
        (feature_dir / "tasks.md").write_text("- [ ] T001 task\n")
        assert _run(repo, "status", "init-spec").returncode == 0
        before = (feature_dir / "status.yaml").read_bytes()

        with patch("os.replace", side_effect=OSError("power loss")), pytest.raises(OSError):
            status.cmd_transition_phase(repo, "PLAN", result=None)

        # Previous complete ledger still readable, interrupted change absent (SC-004)
        after = ledger.load_raw(feature_dir)
        assert (feature_dir / "status.yaml").read_bytes() == before
        assert after["current_phase"] == "SPECIFY"
