"""Integration tests for `specops preflight` — exit codes, streams, ledger immutability
(Feature 004 behavior), plus the `specops review` deprecated-alias parity (Feature 017)."""
import json
import subprocess
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_preflight(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["specops", "preflight"],
        cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def _write_config(root: Path, lint: str = "", test: str = "") -> None:
    (root / "specops.json").write_text(json.dumps({
        "test_command": test,
        "lint_command": lint,
        "skills_dir": ".specify/skills",
    }))


def _write_ledger(root: Path, baseline: str, phase: str = "IMPLEMENT") -> Path:
    feature_dir = root / "specs" / "001-demo"
    data = {
        "feature": "001-demo",
        "branch": _git(root, "branch", "--show-current"),
        "baseline": baseline,
        "current_phase": phase,
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [],
        "review_cycles": [],
    }
    ledger = feature_dir / "status.yaml"
    ledger.write_text(yaml.dump(data))
    return ledger


def _all_pass_setup(root: Path, phase: str = "IMPLEMENT") -> Path:
    # Commit the Speckit scaffolding *before* the baseline (as a real feature
    # branches from a point that already contains it), so the post-baseline
    # effective diff is only SpecOps-managed state, which the Feature 010 drift
    # gate excludes — leaving zero unexplained paths.
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "scaffolding")
    baseline = _git(root, "rev-parse", "HEAD")
    _write_config(root)
    ledger = _write_ledger(root, baseline, phase=phase)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "setup")
    return ledger


# ---------------------------------------------------------------------------
# Exit codes and streams
# ---------------------------------------------------------------------------


class TestPreflightJsonOutcome:
    """Feature 007: `preflight --json` emits the stable outcome contract. [SC-006]"""

    def _run_json(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["specops", "preflight", "--json"],
            cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )

    def test_pass_emits_verdict_approved(self, fake_speckit_repo: Path) -> None:
        _all_pass_setup(fake_speckit_repo)
        r = self._run_json(fake_speckit_repo)
        assert r.returncode == 0
        obj = json.loads(r.stdout)
        assert obj["command"] == "preflight"  # Feature 017 FR-004: mirrors invoked name
        assert obj["class"] == "pass"
        assert obj["outcome"] == "ok"
        assert obj["verdict"] == "APPROVED"
        assert any(g["name"] == "reconcile" for g in obj["gates"])

    def test_gate_failure_emits_verdict_rejected_exit_one(self, fake_speckit_repo: Path) -> None:
        _all_pass_setup(fake_speckit_repo)
        (fake_speckit_repo / "stray.txt").write_text("x\n")
        r = self._run_json(fake_speckit_repo)
        assert r.returncode == 1
        obj = json.loads(r.stdout)
        assert obj["class"] == "gate-rejection"
        assert obj["verdict"] == "REJECTED"

    def test_corrupt_ledger_emits_infra_error_exit_two(self, fake_speckit_repo: Path) -> None:
        ledger = _all_pass_setup(fake_speckit_repo)
        ledger.write_text("{{{ not yaml :::")
        r = self._run_json(fake_speckit_repo)
        assert r.returncode == 2
        obj = json.loads(r.stdout)
        assert obj["class"] == "infra-error"

    def test_soft_rejection_exits_zero_with_verdict(self, fake_speckit_repo: Path) -> None:
        """US3: --soft keeps exit 0 on REJECTED so a do-while body can loop on it."""
        _all_pass_setup(fake_speckit_repo)
        (fake_speckit_repo / "stray.txt").write_text("x\n")
        r = subprocess.run(
            ["specops", "preflight", "--json", "--soft"],
            cwd=fake_speckit_repo, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        assert r.returncode == 0  # soft: does not abort the loop
        obj = json.loads(r.stdout)
        assert obj["verdict"] == "REJECTED"
        assert obj["class"] == "gate-rejection"


class TestPreflightExitCodes:
    def test_all_pass_exit_zero_report_on_stdout(self, fake_speckit_repo: Path) -> None:
        _all_pass_setup(fake_speckit_repo)
        result = _run_preflight(fake_speckit_repo)
        assert result.returncode == 0
        assert "[gate] reconcile" in result.stdout
        assert "[gate] working-tree" in result.stdout
        assert result.stderr == ""

    def test_gate_failure_exit_one_evidence_on_stderr(self, fake_speckit_repo: Path) -> None:
        _all_pass_setup(fake_speckit_repo)
        (fake_speckit_repo / "stray.txt").write_text("x\n")
        result = _run_preflight(fake_speckit_repo)
        assert result.returncode == 1
        assert "stray.txt" in result.stderr
        assert result.stdout == ""

    def test_corrupt_ledger_exit_two(self, fake_speckit_repo: Path) -> None:
        ledger = _all_pass_setup(fake_speckit_repo)
        ledger.write_text("{{{ not yaml :::")
        result = _run_preflight(fake_speckit_repo)
        assert result.returncode == 2

    def test_missing_config_exit_one_with_init_guidance(self, fake_speckit_repo: Path) -> None:
        baseline = _git(fake_speckit_repo, "rev-parse", "HEAD")
        _write_ledger(fake_speckit_repo, baseline)
        result = _run_preflight(fake_speckit_repo)
        assert result.returncode == 1
        assert "specops.json" in result.stderr
        assert "init" in result.stderr


# ---------------------------------------------------------------------------
# Ledger immutability (FR-007)
# ---------------------------------------------------------------------------


class TestPreflightReadOnly:
    def test_ledger_byte_identical_on_pass(self, fake_speckit_repo: Path) -> None:
        ledger = _all_pass_setup(fake_speckit_repo)
        before = ledger.read_bytes()
        result = _run_preflight(fake_speckit_repo)
        assert result.returncode == 0
        assert ledger.read_bytes() == before

    def test_ledger_byte_identical_on_failure(self, fake_speckit_repo: Path) -> None:
        ledger = _all_pass_setup(fake_speckit_repo)
        (fake_speckit_repo / "stray.txt").write_text("x\n")
        before = ledger.read_bytes()
        result = _run_preflight(fake_speckit_repo)
        assert result.returncode == 1
        assert ledger.read_bytes() == before


# ---------------------------------------------------------------------------
# CI gate invariants (US3): any phase, non-interactive
# ---------------------------------------------------------------------------


class TestPreflightCiGate:
    def test_runs_in_any_ledger_phase(self, fake_speckit_repo: Path) -> None:
        """No REVIEW-phase precondition: gates evaluate normally in TASKS."""
        _all_pass_setup(fake_speckit_repo, phase="TASKS")
        result = _run_preflight(fake_speckit_repo)
        assert result.returncode == 0
        assert "[gate] working-tree" in result.stdout

    def test_runs_from_subdirectory(self, fake_speckit_repo: Path) -> None:
        """Contract: usable from any directory inside the repository."""
        _all_pass_setup(fake_speckit_repo)
        subdir = fake_speckit_repo / "specs" / "001-demo"
        result = subprocess.run(
            ["specops", "preflight"],
            cwd=subdir, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        assert result.returncode == 0
        assert "[gate] working-tree" in result.stdout

    def test_non_interactive_with_closed_stdin(self, fake_speckit_repo: Path) -> None:
        """Closed stdin (CI): completes without prompting on pass and on failure."""
        _all_pass_setup(fake_speckit_repo)
        ok = subprocess.run(
            ["specops", "preflight"], cwd=fake_speckit_repo,
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120,
        )
        assert ok.returncode == 0
        (fake_speckit_repo / "stray.txt").write_text("x\n")
        fail = subprocess.run(
            ["specops", "preflight"], cwd=fake_speckit_repo,
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120,
        )
        assert fail.returncode == 1


# ---------------------------------------------------------------------------
# Feature 017: `specops review` deprecated-alias parity
# ---------------------------------------------------------------------------


def _run_review(root: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["specops", "review", *flags],
        cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )


class TestReviewAliasParity:
    """FR-002/FR-003/FR-004, SC-002: `specops review` is a behavior-identical alias of
    `specops preflight`, differing only by exactly one stderr deprecation line and the
    invoked-name-mirroring `command` value; stdout stays byte-identical."""

    def test_stdout_byte_identical_and_one_stderr_line_on_pass(
        self, fake_speckit_repo: Path
    ) -> None:
        _all_pass_setup(fake_speckit_repo)
        pre = _run_preflight(fake_speckit_repo)
        rev = _run_review(fake_speckit_repo)
        # Same exit code and byte-identical stdout (the notice never touches stdout).
        assert rev.returncode == pre.returncode == 0
        assert rev.stdout == pre.stdout
        # preflight is silent on stderr; review emits exactly one deprecation line.
        assert pre.stderr == ""
        stderr_lines = [ln for ln in rev.stderr.splitlines() if ln.strip()]
        assert len(stderr_lines) == 1
        assert "deprecated" in stderr_lines[0]
        assert "specops preflight" in stderr_lines[0]

    def test_json_stdout_is_clean_and_mirrors_review_name(
        self, fake_speckit_repo: Path
    ) -> None:
        _all_pass_setup(fake_speckit_repo)
        rev = _run_review(fake_speckit_repo, "--json")
        assert rev.returncode == 0
        obj = json.loads(rev.stdout)  # stdout is valid JSON, no notice mixed in
        assert obj["command"] == "review"  # FR-004: mirrors the invoked alias name
        # The notice is the only thing on stderr.
        assert "deprecated" in rev.stderr

    def test_json_stdout_byte_identical_except_command_value(
        self, fake_speckit_repo: Path
    ) -> None:
        _all_pass_setup(fake_speckit_repo)
        pre_proc = subprocess.run(
            ["specops", "preflight", "--json"], cwd=fake_speckit_repo,
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        pre = json.loads(pre_proc.stdout)
        rev = json.loads(_run_review(fake_speckit_repo, "--json").stdout)
        assert pre["command"] == "preflight" and rev["command"] == "review"
        assert pre.keys() == rev.keys()  # SC-005: no key renamed
        assert {k: v for k, v in pre.items() if k != "command"} == {
            k: v for k, v in rev.items() if k != "command"
        }

    def test_failure_parity_still_one_stderr_line(self, fake_speckit_repo: Path) -> None:
        _all_pass_setup(fake_speckit_repo)
        (fake_speckit_repo / "stray.txt").write_text("x\n")
        rev = _run_review(fake_speckit_repo)
        assert rev.returncode == 1  # same fail-closed exit as preflight
        # Deprecation notice + the gate evidence both land on stderr; the notice
        # is present exactly once and stdout stays empty (hard mode).
        assert rev.stdout == ""
        assert rev.stderr.count("specops review is deprecated") == 1
        assert "stray.txt" in rev.stderr


class TestReviewAliasHelp:
    """FR-014: `review` is marked deprecated in help; `preflight` is canonical."""

    def test_review_help_marks_deprecated(self, fake_speckit_repo: Path) -> None:
        r = subprocess.run(
            ["specops", "review", "--help"],
            cwd=fake_speckit_repo, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        assert r.returncode == 0
        assert "DEPRECATED" in r.stdout.upper()
        assert "preflight" in r.stdout

    def test_preflight_listed_as_command(self, fake_speckit_repo: Path) -> None:
        r = subprocess.run(
            ["specops", "--help"],
            cwd=fake_speckit_repo, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        )
        assert r.returncode == 0
        assert "preflight" in r.stdout
