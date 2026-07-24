"""Ledger engine: init-spec, start-task, complete-task, transition-phase (US2)."""
from __future__ import annotations

import copy
import re
from pathlib import Path

import git
import yaml

from specops import config, contextmap, gitops, ledger, shell, speckit
from specops import evidence as evidence_mod
from specops.errors import LedgerParseError, SpecopsError
from specops.ledger import now_utc

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


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _ledger_path(feature_dir: Path) -> Path:
    return feature_dir / LEDGER_FILENAME


def _load_ledger(feature_dir: Path) -> dict:
    """Read the ledger dict (delegates to the canonical ledger.load_raw)."""
    return ledger.load_raw(feature_dir)


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


def read_baseline(root: Path) -> str:
    """Return the ledger's baseline commit hash, or '' when absent. Read-only."""
    feature_dir = _get_feature_dir(root)
    data = _load_ledger(feature_dir)
    return str(data.get("baseline") or "")


# ---------------------------------------------------------------------------
# State-change precondition gate (Ledger v2) — shared by every mutating command
# ---------------------------------------------------------------------------


def _identity_mismatch(diverged: str) -> SpecopsError:
    return SpecopsError(
        f"Workspace identity mismatch ({diverged}): the ledger's {diverged} does "
        "not match the current workspace. State change refused. If this is a "
        "deliberate branch rename or history rewrite, run 'specops status rebaseline'."
    )


def _load_for_write(root: Path, feature_dir: Path) -> tuple[dict, int, list[str], git.Repo]:
    """Load, classify, identity-check, and (if needed) migrate the ledger for a write.

    Returns (data, base_revision, base_violations, repo). Refuses too-new/unsupported
    schemas and any workspace-identity mismatch (fail closed) before any mutation.
    Migratable ledgers are backed up and migrated in memory (persisted only on save).
    ``base_violations`` are the invariant violations already present at load time —
    pre-existing legacy defects that must not, on their own, block an unrelated
    command (only violations a command newly introduces are blocking; see _finalize).
    """
    on_disk = _load_ledger(feature_dir)

    cls = ledger.classify(on_disk)
    refusal = ledger.refusal_message(cls)
    if refusal is not None:
        raise SpecopsError(refusal)

    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")

    diverged = ledger.validate_identity(root, repo, on_disk)
    if diverged is not None:
        raise _identity_mismatch(diverged)

    base_revision = ledger.revision_of(on_disk)
    data = copy.deepcopy(on_disk)
    if cls == ledger.MIGRATABLE:
        backup_rel = ledger.backup_ledger(root, feature_dir)
        data = ledger.migrate_to_current(data)
        data.setdefault("recovery", {})["migrated_from_backup"] = backup_rel
    ledger.ensure_workflow_block(data)  # back-fill additive Feature 007 block
    base_violations = ledger.validate_invariants(data)
    return data, base_revision, base_violations, repo


def _finalize(
    feature_dir: Path, data: dict, base_revision: int, base_violations: list[str]
) -> None:
    """Commit the ledger with revision CAS, failing closed only on *new* invalid state.

    Invariant violations that already existed when the ledger was loaded
    (*base_violations* — legacy defects a v1 ledger may carry) do not block an
    unrelated command; only violations this command newly introduced are fatal.
    This upholds "never write new invalid state" without bricking legacy ledgers.
    """
    new_violations = [v for v in ledger.validate_invariants(data) if v not in base_violations]
    if new_violations:
        raise SpecopsError("Ledger invariant violation: " + "; ".join(new_violations))
    ledger.save(feature_dir, data, base_revision=base_revision)


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
        .replace("{{active-artifact}}", ledger.artifact_for_phase("SPECIFY"))
        .replace("{{timestamp}}", now_utc())
    )
    data = yaml.safe_load(content)

    tasks_text = _read_tasks_md(feature_dir)
    if tasks_text:
        _sync_tasks(data, tasks_text)

    ledger.write_new(feature_dir, data)
    try:
        rel = ledger_path.relative_to(root.resolve())
    except ValueError:
        rel = ledger_path
    return f"Ledger created: {rel}"


_OPTIONAL_STEPS = ("clarify", "checklist", "analyze")
_STEP_DECISIONS = ("run", "skip")


def cmd_record_step(root: Path, step: str, *, decision: str) -> str:
    """Record a human run/skip decision for an optional lifecycle step (Feature 007, FR-006).

    Appends ``{step, decision, at}`` to the ledger's additive
    ``workflow.skipped_steps`` block. Re-recording the same step replaces its
    prior entry so a resumed workflow never accumulates duplicates.
    """
    if step not in _OPTIONAL_STEPS:
        raise SpecopsError(
            f"Unknown optional step '{step}'. Expected one of: {', '.join(_OPTIONAL_STEPS)}."
        )
    if decision not in _STEP_DECISIONS:
        raise SpecopsError(f"Invalid decision '{decision}'. Expected 'run' or 'skip'.")

    feature_dir = _get_feature_dir(root)
    data, base_rev, base_violations, _repo = _load_for_write(root, feature_dir)

    steps = data["workflow"]["skipped_steps"]  # ensured present by _load_for_write
    steps[:] = [s for s in steps if s.get("step") != step]
    steps.append({"step": step, "decision": decision, "at": now_utc()})

    _finalize(feature_dir, data, base_rev, base_violations)
    return f"Recorded optional step '{step}': {decision}."


def cmd_start_task(root: Path, task_id: str) -> str:
    """Mark task_id IN_PROGRESS (cli-contract: start-task)."""
    feature_dir = _get_feature_dir(root)
    data, base_rev, base_violations, repo = _load_for_write(root, feature_dir)

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

    # Single-active-task rule (R5/L2). An in-flight task that was orphaned
    # (removed from tasks.md) STILL blocks — its recorded work must be handled,
    # not silently abandoned by starting another task.
    active = [t for t in tasks if t["status"] == "IN_PROGRESS"]
    if active:
        raise SpecopsError(
            f"Task '{active[0]['id']}' is already IN_PROGRESS. "
            "Complete or handle it before starting another."
        )

    task["status"] = "IN_PROGRESS"
    task["started_commit"] = gitops.head_sha(repo)
    data["recovery"]["active_task"] = task_id

    _finalize(feature_dir, data, base_rev, base_violations)
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
    data, base_rev, base_violations, repo = _load_for_write(root, feature_dir)

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

    started = task.get("started_commit")
    if not started:
        raise SpecopsError(
            f"Task '{task_id}' has no started_commit; cannot harvest evidence."
        )

    # Effective changed paths for this task (started_commit → HEAD), computed once
    # and reused for both --auto evidence and the Feature 009 context provenance.
    changed_files = gitops.name_only_diff(repo, started)

    if auto:
        cfg = _load_config(root)
        test_cmd = cfg.get("test_command", "")
        if not test_cmd:
            raise SpecopsError("test_command not set in specops.json; cannot use --auto.")

        result = shell.run_client_command(test_cmd, root)
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

        files = changed_files
        test_summary = result.stdout.strip().splitlines()
        test_line = test_summary[-1] if test_summary else "exit 0 (output not parseable)"
        code_diff = f"{len(files)} files across {len(commits)} commit(s): {', '.join(files[:5])}"

        evidence_str = f"TEST_REPORT:{test_line}; CODE_DIFF:{code_diff}"
        evidence_command = test_cmd
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
        evidence_command = "(evidence)"
        commits = gitops.commits_in_range(repo, started)
        task["commits"] = commits
        if commits:
            data["recovery"]["last_commit"] = commits[0]

    # Feature 009: snapshot context provenance (resolved context ids + map digest,
    # or an explicit no-map/invalid marker) for the task's effective changed paths.
    task["context_provenance"] = contextmap.provenance_for(root, changed_files)

    task["evidence"] = evidence_str
    task["status"] = "DONE"
    task["completed_at"] = now_utc()
    data["recovery"]["active_task"] = None

    # Feature 012 (v6): record the structured evidence object + task reference,
    # alongside the retained legacy `<CLASS>:<summary>` string (FR-006/FR-007).
    task_commits = task.get("commits") or []
    head = task_commits[0] if task_commits else started
    commit_range = f"{started}..{head}" if head != started else str(started)
    ev_record = evidence_mod.build_record(
        producer="auto", command=evidence_command, exit_code=0,
        timestamp=task["completed_at"], commit_range=commit_range,
        affected_paths=list(changed_files), summary=evidence_str,
        context_map_digest=contextmap.map_digest(root), subject=task_id,
    )
    stored = evidence_mod.append_record(data.setdefault("evidence", []), ev_record)
    task["evidence_refs"] = [stored["id"]]

    _finalize(feature_dir, data, base_rev, base_violations)
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

    # Read-only diagnostic for abnormal schema states (FR-029a) — never mutates.
    diagnostic = ledger.diagnostic_line(ledger.classify(data))
    if diagnostic is not None:
        lines.append(f"diagnostic: {diagnostic}")
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


def cmd_transition_phase(
    root: Path, phase: str, *, result: str | None, if_needed: bool = False
) -> str:
    """Advance the phase state machine (cli-contract: transition-phase).

    When *if_needed* is set (Feature 007, C1), a request to transition to the
    phase the ledger is already in is a no-op-and-continue (exit 0, no write)
    rather than an error. This lets a workflow step issue a transition that an
    injected Principle IV directive may have already performed, without
    double-issuing or failing closed.
    """
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
    data, base_rev, base_violations, repo = _load_for_write(root, feature_dir)

    current = data.get("current_phase", "SPECIFY")
    target = phase.upper()

    if target not in PHASES:
        raise SpecopsError(
            f"Unknown phase '{target}'. Valid phases: {', '.join(PHASES)}."
        )

    # Idempotent-tolerant: already in the target phase → no-op-and-continue.
    if if_needed and target == current:
        return f"Ledger already in {current}; transition to {target} is a no-op."

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

    # Entering REVIEW: start the corrective placeholder, or open a new cycle.
    # REVIEW -> IMPLEMENT(REJECTED) creates the next-round placeholder so the
    # corrective work has a stable round to reference. Re-entering REVIEW must
    # activate that placeholder instead of appending a second open round.
    if target == "REVIEW":
        cycles = data.setdefault("review_cycles", [])
        # Feature 009: provenance for the cycle's effective diff (baseline → HEAD).
        cycle_prov = contextmap.provenance_for(
            root, gitops.name_only_diff(repo, str(data.get("baseline") or ""), "HEAD")
        )
        pending = cycles[-1] if cycles else None
        if (
            pending
            and pending.get("result") is None
            and pending.get("started_at") is None
        ):
            pending["started_at"] = now_utc()
            pending["context_provenance"] = cycle_prov
        else:
            round_num = len(cycles) + 1
            cycles.append({
                "round": round_num,
                "started_at": now_utc(),
                "completed_at": None,
                "result": None,
                "context_provenance": cycle_prov,
            })

    # Closing REVIEW via corrective REVIEW→IMPLEMENT(REJECTED)
    if current == "REVIEW" and target == "IMPLEMENT" and normalized_result == "REJECTED":
        cycles = data.get("review_cycles", [])
        if cycles:
            cycles[-1]["result"] = "REJECTED"
            cycles[-1]["completed_at"] = now_utc()
        # Open new review cycle placeholder for next round
        next_round = len(cycles) + 1
        cycles.append({
            "round": next_round,
            "started_at": None,
            "completed_at": None,
            "result": None,
        })

    # Feature 011: block approval while any blocking finding is unverified
    # (feature-global, across every round's handoff). An empty result — including
    # a ledger with no handoffs at all — degrades to the existing Feature 006
    # cycle-result gate below (never retroactively blocks; roadmap Rule 5). Guards
    # every DONE entry point (REVIEW->DONE, the APPROVED record, and a plain DONE).
    if target == "DONE":
        from specops import handoff
        unverified = handoff.blocking_approval_check(data)
        if unverified:
            raise SpecopsError(
                "Cannot enter DONE: unverified blocking findings remain: "
                + ", ".join(unverified)
                + ". Verify them ('specops handoff finding verify') first."
            )

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
            cycles[-1]["completed_at"] = now_utc()

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
    data["active_artifact"] = ledger.artifact_for_phase(target)
    _finalize(feature_dir, data, base_rev, base_violations)
    return f"Phase transition: {current} → {target}."


def cmd_migrate(root: Path) -> str:
    """Explicitly migrate the active feature's ledger to the current schema.

    Idempotent: 'already current' when nothing to do. Backs up the original
    (FR-008a) before a real migration and refuses too-new/unsupported ledgers.
    Like every write path, it fails closed on a workspace-identity mismatch
    (consistent with state changes; use 'rebaseline' after a deliberate move).
    """
    feature_dir = _get_feature_dir(root)
    on_disk = _load_ledger(feature_dir)

    cls = ledger.classify(on_disk)
    if cls == ledger.CURRENT:
        return "already current"
    refusal = ledger.refusal_message(cls)
    if refusal is not None:
        raise SpecopsError(refusal)

    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")
    diverged = ledger.validate_identity(root, repo, on_disk)
    if diverged is not None:
        raise _identity_mismatch(diverged)

    base_rev = ledger.revision_of(on_disk)
    backup_rel = ledger.backup_ledger(root, feature_dir)
    data = ledger.migrate_to_current(copy.deepcopy(on_disk))
    data.setdefault("recovery", {})["migrated_from_backup"] = backup_rel
    ledger.save(feature_dir, data, base_revision=base_rev)
    return f"migrated to schema v{ledger.CURRENT_SCHEMA}"


def cmd_rebaseline(root: Path) -> str:
    """Re-anchor the ledger's branch/baseline identity to the current workspace.

    The explicit, auditable escape hatch for a deliberate branch rename or
    history rewrite (FR-019a): it re-records the current branch and a fresh
    baseline (current HEAD) so subsequent state changes pass the identity gate.
    It refuses to cross feature identity — if the resolved feature no longer
    matches the ledger's `feature`, it fails closed (that is not a re-baseline).
    """
    feature_dir = _get_feature_dir(root)
    # Load + migrate (if needed) but bypass ONLY the branch/baseline identity check;
    # the feature-identity check is still enforced below.
    on_disk = _load_ledger(feature_dir)
    cls = ledger.classify(on_disk)
    refusal = ledger.refusal_message(cls)
    if refusal is not None:
        raise SpecopsError(refusal)

    repo = gitops.find_repo(root)
    if repo is None:
        raise SpecopsError("Not a Git repository.")

    resolved = speckit.resolve_feature_dir(root)
    if resolved is None or resolved.name != on_disk.get("feature"):
        raise SpecopsError(
            "Cannot rebaseline: the resolved feature does not match the ledger's "
            "feature. Rebaseline re-anchors branch/baseline only, never the feature."
        )

    base_rev = ledger.revision_of(on_disk)
    data = copy.deepcopy(on_disk)
    if cls == ledger.MIGRATABLE:
        backup_rel = ledger.backup_ledger(root, feature_dir)
        data = ledger.migrate_to_current(data)
        data.setdefault("recovery", {})["migrated_from_backup"] = backup_rel
    ledger.ensure_workflow_block(data)  # back-fill additive Feature 007 block
    base_violations = ledger.validate_invariants(data)

    new_branch = gitops.current_branch(repo)
    new_baseline = gitops.head_sha(repo)
    data["branch"] = new_branch
    data["baseline"] = new_baseline

    _finalize(feature_dir, data, base_rev, base_violations)
    return f"Rebaselined to branch '{new_branch}' at {new_baseline[:7]}."
