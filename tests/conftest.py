"""
Shared pytest fixtures: temporary Git repository and fake Speckit layout.
"""
import datetime
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from specops import ledger


@pytest.fixture()
def tmp_git_repo(tmp_path: Path) -> Path:
    """Return a path to a freshly initialised Git repository."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    readme = tmp_path / "README.md"
    readme.write_text("# test\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


@pytest.fixture()
def fake_speckit_repo(tmp_git_repo: Path) -> Path:
    """
    Return a Git repo with a minimal Speckit layout (Claude skills mode,
    invoke separator '-') including integration.json and a claude manifest.
    """
    root = tmp_git_repo

    # Speckit core dirs
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "integrations").mkdir(parents=True)

    # Claude skills prompts (full layout: specify, plan, tasks, implement)
    (root / ".claude" / "skills" / "speckit-specify").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-plan").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-tasks").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-implement").mkdir(parents=True)
    # speckit-taskstoissues shares the 'speckit-tasks' prefix — kept in the
    # fixture so resolution must not confuse it with the tasks prompt.
    (root / ".claude" / "skills" / "speckit-taskstoissues").mkdir(parents=True)
    (root / ".claude" / "skills" / "speckit-specify" / "SKILL.md").write_text("# specify prompt\n")
    (root / ".claude" / "skills" / "speckit-plan" / "SKILL.md").write_text("# plan prompt\n")
    (root / ".claude" / "skills" / "speckit-tasks" / "SKILL.md").write_text("# tasks prompt\n")
    (root / ".claude" / "skills" / "speckit-taskstoissues" / "SKILL.md").write_text(
        "# taskstoissues prompt\n"
    )
    (root / ".claude" / "skills" / "speckit-implement" / "SKILL.md").write_text(
        "# implement prompt\n"
    )

    # Speckit integration records
    integration = {
        "installed_integrations": ["claude"],
        "integration_settings": {"claude": {"invoke_separator": "-"}},
    }
    (root / ".specify" / "integration.json").write_text(json.dumps(integration))

    manifest = {
        "integration": "claude",
        "files": {
            ".claude/skills/speckit-specify/SKILL.md": "-",
            ".claude/skills/speckit-plan/SKILL.md": "-",
            ".claude/skills/speckit-tasks/SKILL.md": "-",
            ".claude/skills/speckit-taskstoissues/SKILL.md": "-",
            ".claude/skills/speckit-implement/SKILL.md": "-",
        },
    }
    (root / ".specify" / "integrations" / "claude.manifest.json").write_text(
        json.dumps(manifest)
    )

    # feature.json pointing to specs/001-demo
    (root / "specs" / "001-demo").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )

    return root


@pytest.fixture()
def ledger_in_review(tmp_git_repo: Path) -> Path:
    """Feature repo with status.yaml at REVIEW phase, one open review cycle."""
    root = tmp_git_repo
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-review-test"})
    )
    feature_dir = root / "specs" / "001-review-test"
    feature_dir.mkdir(parents=True)

    data = {
        "feature": "001-review-test",
        "branch": "main",
        "baseline": "abc1234",
        "created_at": str(datetime.date.today()),
        "updated_at": str(datetime.date.today()),
        "current_phase": "REVIEW",
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": [],
        "review_cycles": [
            {
                "round": 1,
                "started_at": str(datetime.date.today()),
                "completed_at": None,
                "result": None,
            }
        ],
    }
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    return root


def read_ledger(feature_dir: Path) -> dict:
    """Read and return the ledger YAML from feature_dir/status.yaml."""
    return yaml.safe_load((feature_dir / "status.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Context Map (Feature 008) fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "context_maps"


@pytest.fixture()
def context_map_repo(tmp_git_repo: Path) -> Path:
    """A git repo with a `.specify/` (+ specops/) layout but no map yet."""
    (tmp_git_repo / ".specify" / "templates").mkdir(parents=True)
    (tmp_git_repo / ".specify" / "specops").mkdir(parents=True)
    return tmp_git_repo


def write_map(root: Path, data: object) -> Path:
    """Write a context map (dict → YAML, or a raw string) to its canonical path."""
    from specops import contextmap

    p = contextmap.map_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else yaml.dump(data)
    p.write_text(text, encoding="utf-8")
    return p


def load_map_fixture(name: str) -> str:
    """Return the text of a named fixture under tests/fixtures/context_maps/."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def write_profiles(root: Path, data: object) -> Path:
    """Write a gate-profile config (dict → YAML, or a raw string) to its path (Feature 012)."""
    from specops import gateprofiles

    p = gateprofiles.profiles_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else yaml.dump(data)
    p.write_text(text, encoding="utf-8")
    return p


def snapshot_tree(root: Path) -> dict[str, bytes]:
    """Byte-snapshot every file under *root* (excluding `.git`) for read-only assertions.

    Feature 012 T004: shared helper for asserting a read-only command mutates neither
    the ledger nor the config (before/after byte-compare), reused by US3/polish tests.
    """
    snap: dict[str, bytes] = {}
    for f in sorted(root.rglob("*")):
        if f.is_file() and ".git" not in f.parts:
            snap[str(f.relative_to(root))] = f.read_bytes()
    return snap


# ---------------------------------------------------------------------------
# End-to-End Traceability (Feature 010) builders
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def make_trace_ledger(
    *, feature: str, branch: str, baseline: str,
    tasks: list | None = None, review_cycles: list | None = None,
    acknowledgements: list | None = None, phase: str = "REVIEW",
) -> dict:
    """Build a v4 ledger dict for trace fixtures (deterministic, no I/O)."""
    return {
        "schema_version": 4,
        "revision": 1,
        "feature": feature,
        "branch": branch,
        "baseline": baseline,
        "workflow_lane": "full",
        "created_at": "2026-07-21T00:00:00+00:00",
        "updated_at": "2026-07-21T00:00:00+00:00",
        "current_phase": phase,
        "recovery": {
            "active_task": None, "last_commit": None, "blockers": [],
            "last_consistent_revision": 1, "last_consistent_at": "2026-07-21T00:00:00+00:00",
            "migrated_from_backup": None,
        },
        "tasks": tasks or [],
        "review_cycles": review_cycles or [],
        "acknowledgements": acknowledgements or [],
        "workflow": {"skipped_steps": []},
    }


def make_task(tid: str, *, status: str = "DONE", evidence: str | None = "CLI_LOG:ok",
              commits: list | None = None, context_ids: list | None = None,
              digest: str | None = None) -> dict:
    """Build a v4 task record."""
    prov = (
        {"map": "present", "digest": digest or "d", "context_ids": context_ids, "output_version": 1}
        if context_ids is not None else {"map": "none"}
    )
    return {
        "id": tid, "status": status, "started_commit": "0" * 40,
        "commits": commits or [], "evidence": evidence, "completed_at": None,
        "context_provenance": prov,
    }


@pytest.fixture()
def trace_repo(tmp_git_repo: Path):
    """A git feature repo with a v4 ledger whose baseline is the scaffolding commit.

    Returns a builder callable: ``build(plan_paths=..., tasks=..., acks=...,
    changed={path: 'content'}, spec_scs=..., tasks_md=...)`` → the repo root, with
    the changed files committed and the ledger baseline anchored so the effective
    diff is exactly the ``changed`` set.
    """
    root = tmp_git_repo
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )
    feature_dir = root / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)

    def build(*, plan_paths=(), spec_scs=("SC-001",), tasks_md_tasks=(),
              tasks=None, review_cycles=None, acks=None, changed=None):
        spec = "\n".join(f"- **{sc}**: measurable outcome." for sc in spec_scs)
        (feature_dir / "spec.md").write_text("# Spec\n\n## Success Criteria\n\n" + spec + "\n")
        plan_lines = "\n".join(f"- `{p}` (create)" for p in plan_paths)
        (feature_dir / "plan.md").write_text("# Plan\n\n" + plan_lines + "\n")
        (feature_dir / "tasks.md").write_text("# Tasks\n\n" + "\n".join(tasks_md_tasks) + "\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "scaffolding")
        baseline = _git(root, "rev-parse", "HEAD")
        ledger = make_trace_ledger(
            feature="001-demo", branch=_git(root, "rev-parse", "--abbrev-ref", "HEAD"),
            baseline=baseline, tasks=tasks, review_cycles=review_cycles,
            acknowledgements=acks,
        )
        (feature_dir / "status.yaml").write_text(yaml.dump(ledger))
        for path, content in (changed or {}).items():
            fp = root / path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)
        if changed:
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "work")
        return root

    return build


# ---------------------------------------------------------------------------
# Structured Corrective Handoff (Feature 011) builders
# ---------------------------------------------------------------------------


def make_finding(
    fid: str, *, severity: str = "blocking", state: str = "OPEN", rule: str = "R1",
    file: str = "src/a.py", line: int | None = 1, action: str = "do the thing",
    expected_evidence: str = "a unit test", closure: str = "the test passes",
    task: str | None = None, commits: list | None = None, evidence: str | None = None,
) -> dict:
    """Build a v5 finding record (nested under a review cycle's handoff)."""
    return {
        "id": fid, "severity": severity, "rule": rule, "file": file, "line": line,
        "action": action, "expected_evidence": expected_evidence,
        "closure_criteria": closure, "state": state,
        "task": task, "commits": commits or [], "evidence": evidence,
        "fixed_at": None, "verified_at": None,
    }


def make_cycle(
    *, round: int = 1, result: str | None = None, authorized_paths: list | None = None,
    findings: list | None = None, closed_at: str | None = None,
    started_at: str | None = "2026-07-22T00:00:00+00:00",
) -> dict:
    """Build a review-cycle record, optionally carrying a v5 handoff.

    A handoff is attached only when ``findings`` or ``authorized_paths`` is given
    (mirrors production: absence of a handoff == zero structured findings).
    """
    cycle: dict = {
        "round": round, "started_at": started_at, "completed_at": None,
        "result": result, "context_provenance": {"map": "none"},
    }
    if findings is not None or authorized_paths is not None:
        cycle["handoff"] = {
            "authorized_paths": authorized_paths or [],
            "closed_at": closed_at,
            "findings": findings or [],
        }
    return cycle


@pytest.fixture()
def handoff_repo(tmp_git_repo: Path):
    """A git feature repo with a v5 ledger at REVIEW carrying review cycles.

    Returns ``build(*, tasks=..., review_cycles=..., phase="REVIEW")`` → repo root,
    with the baseline anchored to the scaffolding commit (identity check passes)
    and the ledger at schema v5.
    """
    root = tmp_git_repo
    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-demo"})
    )
    feature_dir = root / "specs" / "001-demo"
    feature_dir.mkdir(parents=True)

    def build(*, tasks=None, review_cycles=None, phase="REVIEW",
              spec_scs=("SC-001",), tasks_md_tasks=()):
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n## Success Criteria\n\n"
            + "\n".join(f"- **{sc}**: measurable." for sc in spec_scs) + "\n")
        (feature_dir / "plan.md").write_text("# Plan\n")
        (feature_dir / "tasks.md").write_text("# Tasks\n\n" + "\n".join(tasks_md_tasks) + "\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "scaffolding")
        baseline = _git(root, "rev-parse", "HEAD")
        led = make_trace_ledger(
            feature="001-demo",
            branch=_git(root, "rev-parse", "--abbrev-ref", "HEAD"),
            baseline=baseline, tasks=tasks,
            review_cycles=review_cycles if review_cycles is not None else [make_cycle()],
            phase=phase,
        )
        led["schema_version"] = ledger.CURRENT_SCHEMA
        (feature_dir / "status.yaml").write_text(yaml.dump(led))
        return root

    return build


def head_commit(root: Path) -> str:
    """Return the current HEAD sha of the repo at *root* (for finding-fix links)."""
    return _git(root, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------
# Ledger v2 (Feature 006) synthetic ledger factories
# ---------------------------------------------------------------------------


def make_v1_ledger(
    feature_dir: Path,
    *,
    feature: str | None = None,
    branch: str = "main",
    baseline: str = "abc1234",
    phase: str = "SPECIFY",
    tasks: list | None = None,
    review_cycles: list | None = None,
) -> dict:
    """Write a v1-shaped ledger (no schema_version, date-only timestamps) and return it."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "feature": feature or feature_dir.name,
        "branch": branch,
        "baseline": baseline,
        "created_at": "2026-07-05",
        "updated_at": "2026-07-05",
        "current_phase": phase,
        "recovery": {"active_task": None, "last_commit": None, "blockers": []},
        "tasks": tasks or [],
        "review_cycles": review_cycles or [],
    }
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    return data


# ---------------------------------------------------------------------------
# Feature 009 — Context-Aware Planning and Impact builders
# ---------------------------------------------------------------------------

# A small dependency-graph map reused by 009 tests: web -> api -> config.
# Reverse dependents of `config` = {api, web}; of `api` = {web}.
DEP_GRAPH_MAP = {
    "schema_version": 1,
    "contexts": [
        {"id": "api", "match": ["src/api/**"],
         "reads": {"base": ["src/api"], "plan": ["docs/api.md", "src/api"]},
         "dependencies": ["config"], "gates": ["contract-tests"], "risk": {"tier": "high"}},
        {"id": "web", "match": ["src/web/**"],
         "reads": {"base": ["src/web"]}, "dependencies": ["api"]},
        {"id": "config", "match": ["src/config/**"],
         "reads": {"base": ["src/config"]}},
    ],
}


def context_provenance_of(record: dict) -> object:
    """Return a task/review-cycle record's ``context_provenance`` (or None)."""
    return record.get("context_provenance")


def make_v2_ledger(feature_dir: Path, *, revision: int = 1, **kwargs: object) -> dict:
    """Write a valid v2-shaped ledger and return it."""
    data = make_v1_ledger(feature_dir, **kwargs)  # type: ignore[arg-type]
    ts = "2026-07-05T00:00:00+00:00"
    data["schema_version"] = 2
    data["revision"] = revision
    data["workflow_lane"] = "full"
    data["active_artifact"] = "spec.md"
    data["created_at"] = ts
    data["updated_at"] = ts
    data["recovery"].update(
        {
            "last_consistent_revision": revision,
            "last_consistent_at": ts,
            "migrated_from_backup": None,
        }
    )
    (feature_dir / "status.yaml").write_text(yaml.dump(data))
    return data
