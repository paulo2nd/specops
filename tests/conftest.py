"""
Shared pytest fixtures: temporary Git repository and fake Speckit layout.
"""
import datetime
import json
import subprocess
from pathlib import Path

import pytest
import yaml


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
