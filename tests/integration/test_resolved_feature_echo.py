"""The commands that read `.specify/feature.json` must name what they validated (#75).

A stale pointer makes `consistency` answer "ok" about a *different*, already-finished
feature, and nothing in the output says which one — the worst combination, a silent
failure that reports success. Naming the resolved feature makes a stale pointer visible
in the very output it would otherwise corrupt.

The line rides the same stream as the verdict (stdout on a pass, stderr on a failure),
so the "failure evidence is stderr-only" contract that `test_preflight_cli` pins holds
unchanged.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import cli, git


def _repo(tmp_path: Path, *, pointer: str, features: tuple[str, ...]) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    git(root, "config", "user.email", "t@t.com")
    git(root, "config", "user.name", "T")
    (root / "README.md").write_text("# test\n")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "init")

    (root / ".specify").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": pointer})
    )
    for name in features:
        d = root / "specs" / name
        d.mkdir(parents=True)
        (d / "spec.md").write_text("- **SC-001**: works\n")
        (d / "tasks.md").write_text("- [ ] T001 [SC-001] do it\n")
    return root


def test_consistency_names_the_feature_it_validated(tmp_path: Path) -> None:
    root = _repo(tmp_path, pointer="specs/001-done", features=("001-done",))
    result = cli(root, "consistency")
    assert result.returncode == 0
    assert "feature: specs/001-done" in result.stdout
    assert "consistency: ok" in result.stdout


def test_stale_pointer_is_visible_in_the_output_it_corrupts(tmp_path: Path) -> None:
    """The reported scenario: 006 is the feature under work, the pointer still says 005.

    `consistency` still validates 005 and still says ok — that is the pointer's
    meaning, not a bug in the check — but the answer now names 005, so the operator
    can see the question it actually answered.
    """
    root = _repo(
        tmp_path, pointer="specs/005-previous", features=("005-previous", "006-current")
    )
    # 006 is broken; if the pointer were followed to it, this would fail.
    (root / "specs" / "006-current" / "tasks.md").write_text("- [ ] T001 no coverage tag\n")

    result = cli(root, "consistency")
    assert result.returncode == 0
    assert "feature: specs/005-previous" in result.stdout
    assert "006-current" not in result.stdout


def test_consistency_failure_names_the_feature_on_stderr(tmp_path: Path) -> None:
    """On a failure the name goes to stderr with the violations — stdout stays clean."""
    root = _repo(tmp_path, pointer="specs/001-broken", features=("001-broken",))
    (root / "specs" / "001-broken" / "tasks.md").write_text("- [ ] T001 no coverage tag\n")

    result = cli(root, "consistency")
    assert result.returncode == 1
    assert "feature: specs/001-broken" in result.stderr
    assert "feature:" not in result.stdout


def test_consistency_json_carries_the_feature_key(tmp_path: Path) -> None:
    """Additive per-command key (docs/stability.md) — no output_version change."""
    root = _repo(tmp_path, pointer="specs/001-done", features=("001-done",))
    result = cli(root, "consistency", "--json")
    payload = json.loads(result.stdout)
    assert payload["feature"] == "specs/001-done"
    assert payload["output_version"] == 1


# ---------------------------------------------------------------------------
# preflight — the feature line and the per-gate wall clock (#73, #75)
# ---------------------------------------------------------------------------

def test_preflight_names_the_feature_and_summarises_the_suite(
    fake_speckit_repo: Path,
) -> None:
    from tests.unit.test_review import _all_pass_setup

    _all_pass_setup(fake_speckit_repo, test="python -c pass")
    result = cli(fake_speckit_repo, "preflight")
    assert result.returncode == 0, result.stderr
    assert "feature: 001-demo" in result.stdout
    # The suite always states how many gates actually executed (#73).
    assert "[gates] " in result.stdout
    assert "executed" in result.stdout


def test_preflight_json_carries_feature_and_duration(fake_speckit_repo: Path) -> None:
    """Both additive per-command keys; `status` and `output_version` unchanged."""
    from tests.unit.test_review import _all_pass_setup

    _all_pass_setup(fake_speckit_repo, test="python -c pass")
    payload = json.loads(cli(fake_speckit_repo, "preflight", "--json").stdout)
    assert payload["feature"] == "specs/001-demo"
    executed = [g for g in payload["gates"] if "duration_ms" in g]
    assert executed, payload["gates"]
    assert all(isinstance(g["duration_ms"], int) for g in executed)
    assert all(g["status"] in {"PASS", "FAIL", "SKIPPED"} for g in payload["gates"])


def test_preflight_second_run_is_cached_and_says_so(fake_speckit_repo: Path) -> None:
    """The revision-6 observation, pinned: a real run and its immediate re-run on an
    unchanged tree were indistinguishable from the output. Now they are not."""
    from tests.unit.test_review import _all_pass_setup

    _all_pass_setup(fake_speckit_repo, test="python -c pass")
    first = cli(fake_speckit_repo, "preflight").stdout
    second = cli(fake_speckit_repo, "preflight").stdout

    assert "[gate] test" in first and "CACHED" not in first
    assert "CACHED" in second
    assert "reused from cache" in second
    assert "0 executed" in second
