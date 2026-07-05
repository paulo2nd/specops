"""Ledger engine: init-spec, start-task, complete-task, transition-phase (US2)."""
from __future__ import annotations

import datetime
import os
import re
import subprocess
from pathlib import Path

import yaml

from specops import config, gitops, speckit
from specops.errors import LedgerParseError, SpecopsError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEDGER_FILENAME = "status.yaml"
PHASES = ["SPECIFY", "PLAN", "TASKS", "IMPLEMENT", "REVIEW", "DONE"]
TASK_STATUSES = ["PENDING", "IN_PROGRESS", "DONE"]
EVIDENCE_CLASSES = {"CLI_LOG", "TEST_REPORT", "SCREENSHOT_PATH", "CODE_DIFF"}

_PART_RE = re.compile(
    r"^(" + "|".join(re.escape(c) for c in EVIDENCE_CLASSES) + r"):(.+)$"
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
        raise SpecopsError(
            f"Ledger not found: {path}. Run 'specops status init-spec' first."
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LedgerParseError(f"Cannot parse ledger {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LedgerParseError(f"Ledger {path} has invalid structure.")
    return data


def _save_ledger(feature_dir: Path, data: dict) -> None:
    """Write ledger atomically: write to .tmp, flush, os.replace onto status.yaml."""
    path = _ledger_path(feature_dir)
    tmp_path = feature_dir / (LEDGER_FILENAME + ".tmp")
    data["updated_at"] = _today()
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    tmp_path.write_text(content, encoding="utf-8")
    with open(tmp_path, "rb") as fh:
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(str(tmp_path), str(path))


def _sync_tasks(data: dict, tasks_text: str) -> None:
    """Sync ledger tasks[] from tasks.md content.

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
        raise SpecopsError(
            "Cannot resolve active feature directory. Check .specify/feature.json."
        )
    return fd


def _read_tasks_md(feature_dir: Path) -> str:
    tasks_md = feature_dir / "tasks.md"
    if tasks_md.is_file():
        return tasks_md.read_text(encoding="utf-8")
    return ""


def _validate_evidence(evidence: str) -> bool:
    """Return True when evidence matches the strict grammar: CLASS:summary[; CLASS:summary ...]."""
    if not evidence:
        return False
    parts = evidence.split("; ")
    for part in parts:
        m = _PART_RE.match(part)
        if not m:
            return False
        summary = m.group(2)
        if not summary or summary[0] == " ":
            return False
    return True


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_init_spec(root: Path, name: str | None) -> str:
    """Create status.yaml for the active feature (cli-contract: init-spec)."""
    feature_dir = _get_feature_dir(root)

    if name is not None:
        expected = root / "specs" / name
        if expected.resolve() != feature_dir.resolve():
            raise SpecopsError(
                f"Provided name '{name}' resolves to '{expected}' "
                f"but active feature is '{feature_dir}'."
            )

    ledger_path = _ledger_path(feature_dir)
    if ledger_path.is_file():
        raise SpecopsError(f"Ledger already exists: {ledger_path}")

    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")

    branch = gitops.current_branch(repo)
    baseline = gitops.head_sha(repo)
    feature_name = feature_dir.name

    template = (_templates_dir() / "status.yaml").read_text(encoding="utf-8")
    content = (
        template
        .replace("{{feature-name}}", feature_name)
        .replace("{{branch}}", branch)
        .replace("{{commit-hash}}", baseline)
        .replace("{{YYYY-MM-DD}}", _today())
    )
    data = yaml.safe_load(content)

    tasks_text = _read_tasks_md(feature_dir)
    if tasks_text:
        _sync_tasks(data, tasks_text)

    _save_ledger(feature_dir, data)
    try:
        rel = ledger_path.relative_to(root.resolve())
    except ValueError:
        rel = ledger_path
    return f"Ledger created: {rel}"


def cmd_start_task(root: Path, task_id: str) -> str:
    """Mark task_id IN_PROGRESS (cli-contract: start-task)."""
    feature_dir = _get_feature_dir(root)
    data = _load_ledger(feature_dir)

    tasks_text = _read_tasks_md(feature_dir)
    _sync_tasks(data, tasks_text)

    tasks = data.get("tasks", [])
    task_map = {t["id"]: t for t in tasks}

    if task_id not in task_map:
        raise SpecopsError(f"Task '{task_id}' not found in tasks.md.")

    task = task_map[task_id]
    if task["status"] == "DONE":
        raise SpecopsError(f"Task '{task_id}' is already DONE.")
    if task["status"] == "IN_PROGRESS":
        raise SpecopsError(f"Task '{task_id}' is already IN_PROGRESS.")

    # Single-active-task rule (R5/L2)
    active = [t for t in tasks if t["status"] == "IN_PROGRESS"]
    if active:
        raise SpecopsError(
            f"Task '{active[0]['id']}' is already IN_PROGRESS. "
            "Complete or handle it before starting another."
        )

    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")

    task["status"] = "IN_PROGRESS"
    task["started_commit"] = gitops.head_sha(repo)
    data["recovery"]["active_task"] = task_id

    _save_ledger(feature_dir, data)
    return f"Task '{task_id}' started."


def cmd_complete_task(
    root: Path, task_id: str, *, auto: bool, evidence: str | None
) -> str:
    """Mark task_id DONE with evidence (cli-contract: complete-task)."""
    if not auto and not evidence:
        raise SpecopsError("Exactly one evidence source required: --auto or --evidence.")
    if auto and evidence:
        raise SpecopsError("Provide --auto or --evidence, not both.")

    feature_dir = _get_feature_dir(root)
    data = _load_ledger(feature_dir)

    tasks_text = _read_tasks_md(feature_dir)
    _sync_tasks(data, tasks_text)

    tasks = data.get("tasks", [])
    task_map = {t["id"]: t for t in tasks}

    if task_id not in task_map:
        raise SpecopsError(f"Task '{task_id}' not found in tasks.md.")

    task = task_map[task_id]
    if task["status"] != "IN_PROGRESS":
        raise SpecopsError(
            f"Task '{task_id}' is not IN_PROGRESS (status: {task['status']})."
        )

    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")

    started = task.get("started_commit")
    if not started:
        raise SpecopsError(
            f"Task '{task_id}' has no started_commit; cannot harvest evidence."
        )

    if auto:
        cfg = _load_config(root)
        test_cmd = cfg.get("test_command", "")
        if not test_cmd:
            raise SpecopsError("test_command not set in specops.json; cannot use --auto.")

        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise SpecopsError(
                f"test_command failed (exit {result.returncode}). "
                f"Task '{task_id}' stays IN_PROGRESS."
            )

        commits = gitops.commits_in_range(repo, started)
        if not commits:
            raise SpecopsError(
                f"No commits since task start ({started[:7]}). Commit your work first."
            )

        files = gitops.name_only_diff(repo, started)
        test_summary = result.stdout.strip().splitlines()
        test_line = test_summary[-1] if test_summary else "exit 0 (output not parseable)"
        code_diff = f"{len(files)} files across {len(commits)} commit(s): {', '.join(files[:5])}"

        evidence_str = f"TEST_REPORT:{test_line}; CODE_DIFF:{code_diff}"
        task["commits"] = commits
        if commits:
            data["recovery"]["last_commit"] = commits[0]
    else:
        if not evidence or not _validate_evidence(evidence):
            raise SpecopsError(
                f"Invalid evidence format. Expected '<CLASS>:<summary>[; ...]' "
                f"with class in {sorted(EVIDENCE_CLASSES)}."
            )
        evidence_str = evidence
        commits = gitops.commits_in_range(repo, started)
        task["commits"] = commits
        if commits:
            data["recovery"]["last_commit"] = commits[0]

    task["evidence"] = evidence_str
    task["status"] = "DONE"
    task["completed_at"] = _today()
    data["recovery"]["active_task"] = None

    _save_ledger(feature_dir, data)
    return f"Task '{task_id}' completed. Evidence: {evidence_str}"


def cmd_show(root: Path) -> str:
    """Return the ledger summary as a plain-text string (read-only, no save)."""
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        raise SpecopsError(
            "Cannot resolve active feature directory. Check .specify/feature.json."
        )

    path = _ledger_path(feature_dir)
    if not path.is_file():
        raise SpecopsError(
            f"Ledger not found: {path}. Run 'specops status init-spec' first."
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LedgerParseError(f"Cannot parse ledger {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LedgerParseError(f"Ledger {path} has invalid structure.")

    feature_name = data.get("feature", feature_dir.name)
    branch = data.get("branch", "unknown")
    phase = data.get("current_phase", "unknown")

    tasks = data.get("tasks") or []
    pending = sum(1 for t in tasks if t.get("status") == "PENDING" and not t.get("orphaned"))
    in_progress = sum(
        1 for t in tasks if t.get("status") == "IN_PROGRESS" and not t.get("orphaned")
    )
    done = sum(1 for t in tasks if t.get("status") == "DONE" and not t.get("orphaned"))
    orphaned = sum(1 for t in tasks if t.get("orphaned"))
    total = len(tasks)

    active = next(
        (t["id"] for t in tasks if t.get("status") == "IN_PROGRESS" and not t.get("orphaned")),
        "none",
    )

    cycles = data.get("review_cycles") or []

    lines = [
        f"feature: {feature_name}",
        f"branch: {branch}",
        f"phase: {phase}",
        f"active task: {active}",
        (
            f"tasks: {total} total — "
            f"{pending} pending, {in_progress} in progress, {done} done, {orphaned} orphaned"
        ),
        f"review cycles: {len(cycles)}",
    ]
    for cycle in cycles:
        round_num = cycle.get("round", "?")
        result = cycle.get("result")
        started = cycle.get("started_at")
        completed = cycle.get("completed_at")
        if result is None:
            cycle_str = f"  round {round_num}: open"
        elif completed:
            cycle_str = f"  round {round_num}: {result} ({started} → {completed})"
        else:
            cycle_str = f"  round {round_num}: {result}"
        lines.append(cycle_str)

    return "\n".join(lines)


def _load_config(root: Path) -> dict:
    try:
        return config.load(root)
    except config.ConfigError:
        return {}


def cmd_transition_phase(root: Path, phase: str, *, result: str | None) -> str:
    """Advance the phase state machine (cli-contract: transition-phase)."""
    # R2: Validate result vocabulary BEFORE any ledger read/write
    normalized_result: str | None = None
    if result is not None:
        upper = result.upper()
        if upper not in ("APPROVED", "REJECTED"):
            raise SpecopsError(
                f"Invalid result '{result}'. Expected APPROVED or REJECTED."
            )
        normalized_result = upper

    feature_dir = _get_feature_dir(root)
    data = _load_ledger(feature_dir)

    current = data.get("current_phase", "SPECIFY")
    target = phase.upper()

    if target not in PHASES:
        raise SpecopsError(
            f"Unknown phase '{target}'. Valid phases: {', '.join(PHASES)}."
        )

    current_idx = PHASES.index(current) if current in PHASES else -1
    target_idx = PHASES.index(target)

    # Normal forward transition
    valid = False
    if target_idx == current_idx + 1:
        valid = True
    # Special exception: REVIEW → IMPLEMENT with result=REJECTED
    elif current == "REVIEW" and target == "IMPLEMENT":
        if normalized_result == "REJECTED":
            valid = True
        else:
            raise SpecopsError(
                "REVIEW → IMPLEMENT requires '-r REJECTED'. "
                "Supply the result to record a corrective round."
            )

    if not valid:
        next_phase = (
            PHASES[current_idx + 1] if current_idx + 1 < len(PHASES) else "DONE (already at end)"
        )
        raise SpecopsError(
            f"Invalid transition: {current} → {target}. Expected next phase: {next_phase}."
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
    if current == "REVIEW" and target == "IMPLEMENT" and normalized_result == "REJECTED":
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

    # R1: For DONE transitions, apply the result to the open cycle BEFORE the gate check
    if current == "REVIEW" and target == "DONE":
        cycles = data.get("review_cycles", [])
        if normalized_result == "REJECTED":
            raise SpecopsError(
                "Cannot enter DONE with result REJECTED. "
                "Use 'transition-phase IMPLEMENT -r REJECTED' to record a corrective round."
            )
        if normalized_result == "APPROVED" and cycles and cycles[-1]["result"] is None:
            cycles[-1]["result"] = "APPROVED"
            cycles[-1]["completed_at"] = _today()

        if not cycles:
            raise SpecopsError("Cannot enter DONE: no review cycles recorded.")
        latest = cycles[-1]
        latest_result = (latest.get("result") or "").upper()
        if latest_result != "APPROVED":
            raise SpecopsError(
                f"Cannot enter DONE: latest review cycle result is '{latest.get('result')}'. "
                "Must be APPROVED."
            )
    elif target == "DONE":
        cycles = data.get("review_cycles", [])
        if not cycles:
            raise SpecopsError("Cannot enter DONE: no review cycles recorded.")
        latest = cycles[-1]
        latest_result = (latest.get("result") or "").upper()
        if latest_result != "APPROVED":
            raise SpecopsError(
                f"Cannot enter DONE: latest review cycle result is '{latest.get('result')}'. "
                "Must be APPROVED."
            )

    data["current_phase"] = target
    _save_ledger(feature_dir, data)
    return f"Phase transition: {current} → {target}."
