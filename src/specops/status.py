"""Ledger engine: init-spec, start-task, complete-task, transition-phase (US2)."""
from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import sys

import yaml

from specops import config, gitops, speckit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEDGER_FILENAME = "status.yaml"
PHASES = ["SPECIFY", "PLAN", "TASKS", "IMPLEMENT", "REVIEW", "DONE"]
TASK_STATUSES = ["PENDING", "IN_PROGRESS", "DONE"]
EVIDENCE_CLASSES = {"CLI_LOG", "TEST_REPORT", "SCREENSHOT_PATH", "CODE_DIFF"}
_EVIDENCE_RE = re.compile(
    r"^(?:[A-Z_]+:.+)(?:; [A-Z_]+:.+)*$"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today() -> str:
    return datetime.date.today().isoformat()


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _ledger_path(feature_dir: Path) -> Path:
    return feature_dir / LEDGER_FILENAME


def _load_ledger(feature_dir: Path) -> dict:
    path = _ledger_path(feature_dir)
    if not path.is_file():
        _fail(f"Ledger not found: {path}. Run 'specops status init-spec' first.", code=1)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        _fail(f"Cannot parse ledger {path}: {exc}", code=2)
    if not isinstance(data, dict):
        _fail(f"Ledger {path} has invalid structure.", code=2)
    return data


def _save_ledger(feature_dir: Path, data: dict) -> None:
    path = _ledger_path(feature_dir)
    data["updated_at"] = _today()
    path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")


def _fail(msg: str, code: int = 1) -> None:
    import typer
    typer.echo(msg, err=True)
    sys.exit(code)


def _ok(msg: str = "") -> None:
    import typer
    if msg:
        typer.echo(msg)
    sys.exit(0)


def _sync_tasks(data: dict, tasks_text: str) -> None:
    """
    Sync ledger tasks[] from tasks.md content.

    New IDs → PENDING; vanished IDs → orphaned: true (preserved). (R5)
    """
    current_ids = speckit.extract_task_ids(tasks_text)
    existing = {t["id"]: t for t in data.get("tasks", [])}

    synced = []
    for tid in current_ids:
        if tid in existing:
            synced.append(existing[tid])
        else:
            synced.append({
                "id": tid,
                "status": "PENDING",
                "started_commit": None,
                "commits": [],
                "evidence": None,
                "completed_at": None,
            })

    # Preserve orphaned entries
    for tid, task in existing.items():
        if tid not in current_ids:
            task["orphaned"] = True
            synced.append(task)

    data["tasks"] = synced


def _get_feature_dir(root: Path) -> Path:
    fd = speckit.resolve_feature_dir(root)
    if fd is None:
        _fail("Cannot resolve active feature directory. Check .specify/feature.json.")
    return fd


def _read_tasks_md(feature_dir: Path) -> str:
    tasks_md = feature_dir / "tasks.md"
    if tasks_md.is_file():
        return tasks_md.read_text(encoding="utf-8")
    return ""


def _validate_evidence(evidence: str) -> bool:
    """Return True when evidence matches `<CLASS>:<summary>[; ...]` with valid classes."""
    parts = evidence.split("; ")
    for part in parts:
        if ":" not in part:
            return False
        cls, _, _ = part.partition(":")
        if cls not in EVIDENCE_CLASSES:
            return False
    return bool(parts)


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_init_spec(root: Path, name: Optional[str]) -> None:
    """Create status.yaml for the active feature (cli-contract: init-spec)."""
    import typer

    feature_dir = _get_feature_dir(root)

    if name is not None:
        expected = root / "specs" / name
        if expected.resolve() != feature_dir.resolve():
            _fail(
                f"Provided name '{name}' resolves to '{expected}' "
                f"but active feature is '{feature_dir}'."
            )

    ledger_path = _ledger_path(feature_dir)
    if ledger_path.is_file():
        _fail(f"Ledger already exists: {ledger_path}")

    repo = gitops.find_repo(root)
    if repo is None:
        _fail("Not a Git repository.")

    branch = gitops.current_branch(repo)
    baseline = gitops.head_sha(repo)
    feature_name = feature_dir.name

    # Instantiate scaffold
    template = (_templates_dir() / "status.yaml").read_text(encoding="utf-8")
    content = (
        template
        .replace("{{feature-name}}", feature_name)
        .replace("{{branch}}", branch)
        .replace("{{commit-hash}}", baseline)
        .replace("{{YYYY-MM-DD}}", _today())
    )
    data = yaml.safe_load(content)

    # Sync tasks if tasks.md exists
    tasks_text = _read_tasks_md(feature_dir)
    if tasks_text:
        _sync_tasks(data, tasks_text)

    _save_ledger(feature_dir, data)
    try:
        rel = ledger_path.relative_to(root.resolve())
    except ValueError:
        rel = ledger_path
    typer.echo(f"Ledger created: {rel}")
    sys.exit(0)


def cmd_start_task(root: Path, task_id: str) -> None:
    """Mark task_id IN_PROGRESS (cli-contract: start-task)."""
    import typer

    feature_dir = _get_feature_dir(root)
    data = _load_ledger(feature_dir)

    # Re-sync tasks
    tasks_text = _read_tasks_md(feature_dir)
    _sync_tasks(data, tasks_text)

    tasks = data.get("tasks", [])
    task_map = {t["id"]: t for t in tasks}

    if task_id not in task_map:
        _fail(f"Task '{task_id}' not found in tasks.md.")

    task = task_map[task_id]
    if task["status"] == "DONE":
        _fail(f"Task '{task_id}' is already DONE.")
    if task["status"] == "IN_PROGRESS":
        _fail(f"Task '{task_id}' is already IN_PROGRESS.")

    # Single-active-task rule (R5/L2)
    active = [t for t in tasks if t["status"] == "IN_PROGRESS"]
    if active:
        _fail(
            f"Task '{active[0]['id']}' is already IN_PROGRESS. "
            "Complete or handle it before starting another."
        )

    repo = gitops.find_repo(root)
    if repo is None:
        _fail("Not a Git repository.")

    task["status"] = "IN_PROGRESS"
    task["started_commit"] = gitops.head_sha(repo)
    data["recovery"]["active_task"] = task_id

    _save_ledger(feature_dir, data)
    typer.echo(f"Task '{task_id}' started.")
    sys.exit(0)


def cmd_complete_task(
    root: Path, task_id: str, *, auto: bool, evidence: Optional[str]
) -> None:
    """Mark task_id DONE with evidence (cli-contract: complete-task)."""
    import typer

    if not auto and not evidence:
        _fail("Exactly one evidence source required: --auto or --evidence.")
    if auto and evidence:
        _fail("Provide --auto or --evidence, not both.")

    feature_dir = _get_feature_dir(root)
    data = _load_ledger(feature_dir)

    tasks_text = _read_tasks_md(feature_dir)
    _sync_tasks(data, tasks_text)

    tasks = data.get("tasks", [])
    task_map = {t["id"]: t for t in tasks}

    if task_id not in task_map:
        _fail(f"Task '{task_id}' not found in tasks.md.")

    task = task_map[task_id]
    if task["status"] != "IN_PROGRESS":
        _fail(f"Task '{task_id}' is not IN_PROGRESS (status: {task['status']}).")

    repo = gitops.find_repo(root)
    if repo is None:
        _fail("Not a Git repository.")

    started = task.get("started_commit")
    if not started:
        _fail(f"Task '{task_id}' has no started_commit; cannot harvest evidence.")

    if auto:
        # Run test_command
        cfg = _load_config(root)
        test_cmd = cfg.get("test_command", "")
        if not test_cmd:
            _fail("test_command not set in specops.json; cannot use --auto.")

        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            _fail(
                f"test_command failed (exit {result.returncode}). "
                f"Task '{task_id}' stays IN_PROGRESS."
            )

        # Harvest commits and diff
        commits = gitops.commits_in_range(repo, started)
        if not commits:
            _fail(f"No commits since task start ({started[:7]}). Commit your work first.")

        files = gitops.name_only_diff(repo, started)
        test_summary = result.stdout.strip().splitlines()
        test_line = test_summary[-1] if test_summary else "exit 0 (output not parseable)"
        code_diff = f"{len(files)} files across {len(commits)} commit(s): {', '.join(files[:5])}"

        evidence_str = f"TEST_REPORT:{test_line}; CODE_DIFF:{code_diff}"
        task["commits"] = commits
        if commits:
            data["recovery"]["last_commit"] = commits[0]
    else:
        # Caller-supplied evidence
        if not _validate_evidence(evidence):
            _fail(
                f"Invalid evidence format. Expected '<CLASS>:<summary>[; ...]' "
                f"with class in {sorted(EVIDENCE_CLASSES)}."
            )
        evidence_str = evidence
        # Still collect commits for L1
        commits = gitops.commits_in_range(repo, started)
        task["commits"] = commits
        if commits:
            data["recovery"]["last_commit"] = commits[0]

    task["evidence"] = evidence_str
    task["status"] = "DONE"
    task["completed_at"] = _today()
    data["recovery"]["active_task"] = None

    _save_ledger(feature_dir, data)
    typer.echo(f"Task '{task_id}' completed. Evidence: {evidence_str}")
    sys.exit(0)


def _load_config(root: Path) -> dict:
    try:
        return config.load(root)
    except config.ConfigError:
        return {}


def cmd_transition_phase(root: Path, phase: str, *, result: Optional[str]) -> None:
    """Advance the phase state machine (cli-contract: transition-phase)."""
    import typer

    feature_dir = _get_feature_dir(root)
    data = _load_ledger(feature_dir)

    current = data.get("current_phase", "SPECIFY")
    target = phase.upper()

    if target not in PHASES:
        _fail(f"Unknown phase '{target}'. Valid phases: {', '.join(PHASES)}.")

    current_idx = PHASES.index(current) if current in PHASES else -1
    target_idx = PHASES.index(target)

    # Normal forward transition
    valid = False
    if target_idx == current_idx + 1:
        valid = True
    # Special exception: REVIEW → IMPLEMENT with result=REJECTED
    elif current == "REVIEW" and target == "IMPLEMENT":
        if result and result.upper() == "REJECTED":
            valid = True
        else:
            _fail(
                "REVIEW → IMPLEMENT requires '-r REJECTED'. "
                "Supply the result to record a corrective round."
            )

    if not valid:
        _fail(
            f"Invalid transition: {current} → {target}. "
            f"Expected next phase: {PHASES[current_idx + 1] if current_idx + 1 < len(PHASES) else 'DONE (already at end)'}."
        )

    # Entering REVIEW: open a review cycle
    if target == "REVIEW":
        cycles = data.setdefault("review_cycles", [])
        round_num = len(cycles) + 1
        cycles.append({
            "round": round_num,
            "started_at": _today(),
            "completed_at": None,
            "result": None,
        })

    # Closing REVIEW via corrective REVIEW→IMPLEMENT(REJECTED)
    if current == "REVIEW" and target == "IMPLEMENT" and result and result.upper() == "REJECTED":
        cycles = data.get("review_cycles", [])
        if cycles:
            cycles[-1]["result"] = "REJECTED"
            cycles[-1]["completed_at"] = _today()
        # Open new review cycle placeholder for next round
        next_round = len(cycles) + 1
        cycles.append({
            "round": next_round,
            "started_at": None,
            "completed_at": None,
            "result": None,
        })

    # Entering DONE: require latest cycle APPROVED
    if target == "DONE":
        cycles = data.get("review_cycles", [])
        if not cycles:
            _fail("Cannot enter DONE: no review cycles recorded.")
        latest = cycles[-1]
        latest_result = (latest.get("result") or "").upper()
        if latest_result != "APPROVED":
            _fail(
                f"Cannot enter DONE: latest review cycle result is '{latest.get('result')}'. "
                "Must be APPROVED."
            )

    # Close review cycle when transitioning away from REVIEW with a result
    if current == "REVIEW" and target == "DONE" and result:
        cycles = data.get("review_cycles", [])
        if cycles and cycles[-1]["result"] is None:
            cycles[-1]["result"] = result.upper()
            cycles[-1]["completed_at"] = _today()

    data["current_phase"] = target
    _save_ledger(feature_dir, data)
    typer.echo(f"Phase transition: {current} → {target}.")
    sys.exit(0)
