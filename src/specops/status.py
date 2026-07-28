"""Ledger engine: init-spec, start-task, complete-task, transition-phase (US2)."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import cast

import git
import yaml

from specops import config, contextmap, fsutil, gitops, ledger, records, shell, speckit
from specops import evidence as evidence_mod
from specops.errors import SpecopsError
from specops.ledger import now_utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEDGER_FILENAME = "status.yaml"
PHASES = ["SPECIFY", "PLAN", "TASKS", "IMPLEMENT", "REVIEW", "DONE"]
TASK_STATUSES = ["PENDING", "IN_PROGRESS", "DONE"]

# The `<CLASS>:<summary>` evidence grammar now has a single owner (Feature 018 US3):
# :mod:`specops.evidence`. Task-close validates via ``evidence_mod.validate_string``.

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


def compact_status(root: Path) -> dict:
    """Return a compact, read-only snapshot of the active feature (Feature 014, FR-014).

    Shared read path for ``specops report``. Never mutates. Raises LedgerParseError
    when the active feature's ledger is unreadable/corrupt (the CLI maps that to an
    execution error). A missing active feature — or an active feature with no ledger
    yet — yields a snapshot with ``active_feature`` set (or None) and null/zero fields.
    """
    from specops import handoff

    feature_dir = speckit.resolve_feature_dir(root)
    empty_tasks = {"pending": 0, "in_progress": 0, "done": 0, "orphaned": 0, "total": 0}
    if feature_dir is None:
        return {
            "active_feature": None, "branch": None, "phase": None,
            "tasks": dict(empty_tasks), "active_task": None,
            "review": {"cycles": 0, "blocking_open": 0},
            "workflow_lane": ledger.DEFAULT_WORKFLOW_LANE,
        }
    if not _ledger_path(feature_dir).is_file():
        return {
            "active_feature": feature_dir.name, "branch": None, "phase": None,
            "tasks": dict(empty_tasks), "active_task": None,
            "review": {"cycles": 0, "blocking_open": 0},
            "workflow_lane": ledger.DEFAULT_WORKFLOW_LANE,
        }

    data = ledger.load_raw(feature_dir)
    # A hand-edited but YAML-parseable ledger may hold non-mapping task entries; ignore
    # them for counting so a malformed ledger degrades gracefully instead of crashing.
    all_tasks = data.get("tasks") or []
    tasks = [t for t in all_tasks if isinstance(t, dict)]
    cycles = data.get("review_cycles")

    def _count(status: str) -> int:
        return sum(1 for t in tasks if t.get("status") == status and not t.get("orphaned"))

    active_task = next(
        (t["id"] for t in tasks if t.get("status") == "IN_PROGRESS" and not t.get("orphaned")),
        None,
    )
    return {
        "active_feature": data.get("feature", feature_dir.name),
        "branch": data.get("branch"),
        "phase": data.get("current_phase"),
        "tasks": {
            "pending": _count("PENDING"),
            "in_progress": _count("IN_PROGRESS"),
            "done": _count("DONE"),
            "orphaned": sum(1 for t in tasks if t.get("orphaned")),
            "total": len(all_tasks),
        },
        "active_task": active_task,
        "review": {
            "cycles": len(cycles) if isinstance(cycles, list) else 0,
            "blocking_open": len(handoff.blocking_approval_check(data)),
        },
        "workflow_lane": data.get("workflow_lane", ledger.DEFAULT_WORKFLOW_LANE),
    }


def _sync_tasks(data: records.LedgerLike, tasks_text: str) -> None:
    """Sync ledger tasks[] from tasks.md content.

    New IDs → PENDING; vanished IDs → orphaned: true (preserved). (R5)
    """
    current_ids = speckit.extract_task_ids(tasks_text)
    existing = {t["id"]: t for t in data.get("tasks", [])}

    synced: list[records.TaskRecord] = []
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


def get_feature_dir(root: Path) -> Path:
    """Resolve the active feature directory from ``.specify/feature.json``.

    Public cross-module contract (Feature 018): handoff and trace resolve the feature
    dir through this one path. Raises :class:`SpecopsError` (exit 2) when no active
    feature can be resolved.
    """
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


def read_baseline(root: Path) -> str:
    """Return the ledger's baseline commit hash, or '' when absent. Read-only."""
    feature_dir = get_feature_dir(root)
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


def load_for_write(
    root: Path, feature_dir: Path
) -> tuple[records.LedgerDocument, int, list[str], git.Repo]:
    """Load, classify, identity-check, and (if needed) migrate the ledger for a write.

    Returns (data, base_revision, base_violations, repo). Refuses too-new/unsupported
    schemas and any workspace-identity mismatch (fail closed) before any mutation.
    Migratable ledgers are backed up and migrated in memory (persisted only on save).
    ``base_violations`` are the invariant violations already present at load time —
    pre-existing legacy defects that must not, on their own, block an unrelated
    command (only violations a command newly introduces are blocking; see finalize).
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
    data: records.LedgerLike = copy.deepcopy(on_disk)
    if cls == ledger.MIGRATABLE:
        backup_rel = ledger.backup_ledger(root, feature_dir)
        data = ledger.migrate_to_current(data)
        data.setdefault("recovery", {})["migrated_from_backup"] = backup_rel
    ledger.ensure_workflow_block(data)  # back-fill additive Feature 007 block
    base_violations = ledger.validate_invariants(data)
    # The one canonical cast point (Feature 019 US3): the document has been
    # classified, identity-checked, and (if needed) migrated — structurally known.
    return cast(records.LedgerDocument, data), base_revision, base_violations, repo


def finalize(
    feature_dir: Path, data: records.LedgerLike, base_revision: int,
    base_violations: list[str],
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
    feature_dir = get_feature_dir(root)

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
    # Completeness-checked render (FR-010): template drift fails loudly here
    # instead of scaffolding a ledger with silent {{...}} residue.
    content = fsutil.render_template(template, {
        "feature-name": feature_name,
        "branch": branch,
        "commit-hash": baseline,
        "active-artifact": ledger.artifact_for_phase("SPECIFY"),
        "timestamp": now_utc(),
    })
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


def synthesize_ledger_at_plan(feature_dir: Path, repo: git.Repo, lane_data: dict) -> Path:
    """Synthesize a full ledger at the PLAN phase from a promoted lightweight lane.

    Feature 013 (FR-015): builds ``status.yaml`` from the standard template, positioned at
    ``current_phase: PLAN`` with the lane's baseline, so the promoted change flows through
    plan → tasks → implement → review before DONE. The lane's branch commits are preserved
    by the branch itself (promotion never rewrites history); their context is carried into
    the ledger via :func:`ledger.attach_lane_provenance`. Fails if a ledger already exists.
    """
    ledger_path = _ledger_path(feature_dir)
    if ledger_path.is_file():
        raise SpecopsError(f"Ledger already exists: {ledger_path}")

    branch = gitops.current_branch(repo)
    baseline = str(lane_data.get("baseline") or gitops.head_sha(repo))
    ts = now_utc()
    template = (_templates_dir() / "status.yaml").read_text(encoding="utf-8")
    content = fsutil.render_template(template, {
        "feature-name": feature_dir.name,
        "branch": branch,
        "commit-hash": baseline,
        "active-artifact": ledger.artifact_for_phase("PLAN"),
        "timestamp": ts,
    })
    data = yaml.safe_load(content)
    data["current_phase"] = "PLAN"
    ledger.attach_lane_provenance(data, lane_data)
    ledger.write_new(feature_dir, data)
    # The lite lane never runs /speckit-specify, so no spec.md exists — but a ledger at
    # PLAN and the before_plan directive expect one. Seed a minimal specification stub from
    # the lane's context so the resumed full workflow has an artifact to plan against; the
    # human refines it before continuing (Feature 013 promotion, finding 7).
    spec_path = feature_dir / "spec.md"
    if not spec_path.is_file():
        elig = lane_data.get("eligibility") or {}
        answers = ", ".join(a.get("key", "") for a in elig.get("answers") or []) or "—"
        stub = (
            f"# Feature Specification: {feature_dir.name}\n\n"
            "**Status**: Promoted from the lightweight lane — refine before planning.\n\n"
            "## Context\n\n"
            "This feature began in the SpecOps lightweight lane and was promoted to the full "
            "workflow because its scope or risk grew beyond a small reversible change. The lane "
            f"baseline was `{baseline[:7]}`; eligibility was confirmed for: {answers}. The lane's "
            "stop-and-ask decisions are recorded under `lane_provenance` in `status.yaml`.\n\n"
            "## Next step\n\n"
            "Replace this stub with a real specification (run `/speckit-specify` to regenerate, "
            "or edit directly), then proceed with `/speckit-plan`.\n"
        )
        ledger.atomic_write(spec_path, stub)
    return ledger_path


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

    feature_dir = get_feature_dir(root)
    data, base_rev, base_violations, _repo = load_for_write(root, feature_dir)

    steps = data["workflow"]["skipped_steps"]  # ensured present by load_for_write
    steps[:] = [s for s in steps if s.get("step") != step]
    steps.append({"step": step, "decision": decision, "at": now_utc()})

    finalize(feature_dir, data, base_rev, base_violations)
    return f"Recorded optional step '{step}': {decision}."


def cmd_start_task(root: Path, task_id: str) -> str:
    """Mark task_id IN_PROGRESS (cli-contract: start-task)."""
    feature_dir = get_feature_dir(root)
    data, base_rev, base_violations, repo = load_for_write(root, feature_dir)

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

    finalize(feature_dir, data, base_rev, base_violations)
    return f"Task '{task_id}' started."


# ---------------------------------------------------------------------------
# Task-completion sub-steps (Feature 019 US2, research D3)
# ---------------------------------------------------------------------------


def _validate_evidence_args(auto: bool, evidence: str | None) -> None:
    """Exactly one evidence source: --auto XOR --evidence (checked pre-read)."""
    if not auto and not evidence:
        raise SpecopsError("Exactly one evidence source required: --auto or --evidence.")
    if auto and evidence:
        raise SpecopsError("Provide --auto or --evidence, not both.")


def _require_in_progress(
    task_map: dict[str, records.TaskRecord], task_id: str
) -> tuple[records.TaskRecord, str]:
    """Completion preconditions: known task, IN_PROGRESS, with a started_commit.

    Returns (task, started_commit) — the narrowed non-None start anchor.
    """
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
    return task, started


def _auto_evidence(
    root: Path, repo: git.Repo, task_id: str, started: str, changed_files: list[str]
) -> tuple[str, str, list[str]]:
    """--auto: run the client's test_command and harvest commits + diff (§III).

    Returns (evidence string, evidence command, commits).
    """
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
    return f"TEST_REPORT:{test_line}; CODE_DIFF:{code_diff}", test_cmd, commits


def _manual_evidence(
    evidence: str | None, repo: git.Repo, started: str
) -> tuple[str, str, list[str]]:
    """--evidence: validate the grammar; commits are still harvested when present."""
    if not evidence or not evidence_mod.validate_string(evidence):
        raise SpecopsError(
            f"Invalid evidence format. Expected '<CLASS>:<summary>[; ...]' "
            f"with class in {sorted(evidence_mod.EVIDENCE_CLASSES)}."
        )
    return evidence, "(evidence)", gitops.commits_in_range(repo, started)


def _record_completion(
    data: records.LedgerDocument, root: Path, task: records.TaskRecord,
    task_id: str, started: str,
    changed_files: list[str], evidence_str: str, evidence_command: str,
    commits: list[str],
) -> None:
    """Mutate the ledger: task DONE + provenance + the v6 structured evidence record."""
    task["commits"] = commits
    if commits:
        data["recovery"]["last_commit"] = commits[0]

    # Feature 009: snapshot context provenance (resolved context ids + map digest,
    # or an explicit no-map/invalid marker) for the task's effective changed paths.
    task["context_provenance"] = contextmap.provenance_for(root, changed_files)

    task["evidence"] = evidence_str
    task["status"] = "DONE"
    completed_at = now_utc()
    task["completed_at"] = completed_at
    data["recovery"]["active_task"] = None

    # Feature 012 (v6): record the structured evidence object + task reference,
    # alongside the retained legacy `<CLASS>:<summary>` string (FR-006/FR-007).
    task_commits = task.get("commits") or []
    head = task_commits[0] if task_commits else started
    commit_range = f"{started}..{head}" if head != started else str(started)
    ev_record = evidence_mod.build_record(
        producer="auto", command=evidence_command, exit_code=0,
        timestamp=completed_at, commit_range=commit_range,
        affected_paths=list(changed_files), summary=evidence_str,
        context_map_digest=contextmap.map_digest(root), subject=task_id,
    )
    stored = evidence_mod.append_record(data.setdefault("evidence", []), ev_record)
    task["evidence_refs"] = [stored["id"]]


def cmd_complete_task(
    root: Path, task_id: str, *, auto: bool, evidence: str | None
) -> str:
    """Mark task_id DONE with evidence (cli-contract: complete-task)."""
    _validate_evidence_args(auto, evidence)

    feature_dir = get_feature_dir(root)
    data, base_rev, base_violations, repo = load_for_write(root, feature_dir)

    _sync_tasks(data, _read_tasks_md(feature_dir))
    task_map = {t["id"]: t for t in data.get("tasks", [])}
    task, started = _require_in_progress(task_map, task_id)

    # Effective changed paths for this task (started_commit → HEAD), computed once
    # and reused for both --auto evidence and the Feature 009 context provenance.
    changed_files = gitops.name_only_diff(repo, started)

    if auto:
        evidence_str, evidence_command, commits = _auto_evidence(
            root, repo, task_id, started, changed_files
        )
    else:
        evidence_str, evidence_command, commits = _manual_evidence(evidence, repo, started)

    _record_completion(
        data, root, task, task_id, started, changed_files,
        evidence_str, evidence_command, commits,
    )
    finalize(feature_dir, data, base_rev, base_violations)
    return f"Task '{task_id}' completed. Evidence: {evidence_str}"


def cmd_show(root: Path) -> str:
    """Return the ledger summary as a plain-text string (read-only, no save)."""
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        raise SpecopsError(
            "Cannot resolve active feature directory. Check .specify/feature.json."
        )

    # Single ledger-loading authority (Feature 018 US3, SC-004): canonical
    # existence/parse/shape diagnostics live only in ledger.load_raw.
    data = ledger.load_raw(feature_dir)
    # Counts come from the one snapshot routine, which tolerantly filters non-mapping
    # task entries (FR-006) so a hand-edited ledger renders instead of crashing.
    snap = compact_status(root)

    feature_name = data.get("feature", feature_dir.name)
    branch = data.get("branch", "unknown")
    phase = data.get("current_phase", "unknown")

    counts = snap["tasks"]
    active = snap["active_task"] or "none"
    cycles = data.get("review_cycles") or []

    lines = [
        f"feature: {feature_name}",
        f"branch: {branch}",
        f"phase: {phase}",
        f"active task: {active}",
        (
            f"tasks: {counts['total']} total — "
            f"{counts['pending']} pending, {counts['in_progress']} in progress, "
            f"{counts['done']} done, {counts['orphaned']} orphaned"
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


# ---------------------------------------------------------------------------
# Phase-transition sub-steps (Feature 019 US2, research D3)
# ---------------------------------------------------------------------------


def _normalize_result(result: str | None) -> str | None:
    """R2: validate the result vocabulary BEFORE any ledger read/write."""
    if result is None:
        return None
    upper = result.upper()
    if upper not in ("APPROVED", "REJECTED"):
        raise SpecopsError(
            f"Invalid result '{result}'. Expected APPROVED or REJECTED."
        )
    return upper


def _validate_transition(current: str, target: str, normalized_result: str | None) -> None:
    """Enforce the phase sequence, incl. the corrective REVIEW→IMPLEMENT exception."""
    current_idx = PHASES.index(current) if current in PHASES else -1
    target_idx = PHASES.index(target)

    # Normal forward transition
    if target_idx == current_idx + 1:
        return
    # Special exception: REVIEW → IMPLEMENT with result=REJECTED
    if current == "REVIEW" and target == "IMPLEMENT":
        if normalized_result == "REJECTED":
            return
        raise SpecopsError(
            "REVIEW → IMPLEMENT requires '-r REJECTED'. "
            "Supply the result to record a corrective round."
        )
    next_phase = (
        PHASES[current_idx + 1] if current_idx + 1 < len(PHASES) else "DONE (already at end)"
    )
    raise SpecopsError(
        f"Invalid transition: {current} → {target}. Expected next phase: {next_phase}."
    )


def _enter_review(data: records.LedgerDocument, root: Path, repo: git.Repo) -> None:
    """Entering REVIEW: activate the corrective placeholder, or open a new cycle.

    REVIEW -> IMPLEMENT(REJECTED) creates the next-round placeholder so the
    corrective work has a stable round to reference. Re-entering REVIEW must
    activate that placeholder instead of appending a second open round.
    """
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
        cycles.append({
            "round": len(cycles) + 1,
            "started_at": now_utc(),
            "completed_at": None,
            "result": None,
            "context_provenance": cycle_prov,
        })


def _close_rejected_review(data: records.LedgerDocument) -> None:
    """Close the round REJECTED and open the next round's placeholder."""
    cycles = data.get("review_cycles", [])
    if cycles:
        cycles[-1]["result"] = "REJECTED"
        cycles[-1]["completed_at"] = now_utc()
    cycles.append({
        "round": len(cycles) + 1,
        "started_at": None,
        "completed_at": None,
        "result": None,
    })


def _require_approved_cycle(cycles: list[records.ReviewCycleRecord]) -> None:
    """The single Feature 006 DONE cycle gate (Feature 019 US2, FR-004).

    Historically spelled verbatim in BOTH DONE branches of the transition
    command; the second (non-REVIEW) branch was statically unreachable —
    sequence validation only admits DONE from REVIEW — and is absorbed here
    as defense in depth rather than deleted.
    """
    if not cycles:
        raise SpecopsError("Cannot enter DONE: no review cycles recorded.")
    latest = cycles[-1]
    latest_result = (latest.get("result") or "").upper()
    if latest_result != "APPROVED":
        raise SpecopsError(
            f"Cannot enter DONE: latest review cycle result is '{latest.get('result')}'. "
            "Must be APPROVED."
        )


def _gate_done(
    data: records.LedgerDocument, current: str, normalized_result: str | None
) -> None:
    """The ordered DONE gates (Feature 011 findings gate, then Feature 006 cycle gate).

    Feature 011: block approval while any blocking finding is unverified
    (feature-global, across every round's handoff). An empty result — including
    a ledger with no handoffs at all — degrades to the Feature 006 cycle-result
    gate below (never retroactively blocks; roadmap Rule 5). Guards every DONE
    entry point (REVIEW->DONE, the APPROVED record, and a plain DONE).
    """
    from specops import handoff
    unverified = handoff.blocking_approval_check(data)
    if unverified:
        raise SpecopsError(
            "Cannot enter DONE: unverified blocking findings remain: "
            + ", ".join(unverified)
            + ". Verify them ('specops handoff finding verify') first."
        )

    cycles = data.get("review_cycles", [])
    if current == "REVIEW":
        # R1: apply the result to the open cycle BEFORE the gate check.
        if normalized_result == "REJECTED":
            raise SpecopsError(
                "Cannot enter DONE with result REJECTED. "
                "Use 'transition-phase IMPLEMENT -r REJECTED' to record a corrective round."
            )
        if normalized_result == "APPROVED" and cycles and cycles[-1]["result"] is None:
            cycles[-1]["result"] = "APPROVED"
            cycles[-1]["completed_at"] = now_utc()
    _require_approved_cycle(cycles)


def cmd_transition_phase(
    root: Path, phase: str, *, result: str | None, if_needed: bool = False
) -> str:
    """Advance the phase state machine (cli-contract: transition-phase).

    When *if_needed* is set (Feature 007, C1), a request to transition to the
    phase the ledger is already in is a no-op-and-continue (exit 0, no write)
    rather than an error. This lets a workflow step issue a transition that an
    injected Principle IV directive may have already performed, without
    double-issuing or failing closed.

    A thin orchestrator over the named sub-steps above (Feature 019 US2):
    normalize → load → validate → cycle bookkeeping → DONE gates → persist.
    """
    normalized_result = _normalize_result(result)

    feature_dir = get_feature_dir(root)
    data, base_rev, base_violations, repo = load_for_write(root, feature_dir)

    current = data.get("current_phase", "SPECIFY")
    target = phase.upper()

    if target not in PHASES:
        raise SpecopsError(
            f"Unknown phase '{target}'. Valid phases: {', '.join(PHASES)}."
        )

    # Idempotent-tolerant: already in the target phase → no-op-and-continue.
    if if_needed and target == current:
        return f"Ledger already in {current}; transition to {target} is a no-op."

    _validate_transition(current, target, normalized_result)

    if target == "REVIEW":
        _enter_review(data, root, repo)
    if current == "REVIEW" and target == "IMPLEMENT" and normalized_result == "REJECTED":
        _close_rejected_review(data)
    if target == "DONE":
        _gate_done(data, current, normalized_result)

    data["current_phase"] = target
    data["active_artifact"] = ledger.artifact_for_phase(target)
    finalize(feature_dir, data, base_rev, base_violations)
    return f"Phase transition: {current} → {target}."


def cmd_migrate(root: Path) -> str:
    """Explicitly migrate the active feature's ledger to the current schema.

    Idempotent: 'already current' when nothing to do. Backs up the original
    (FR-008a) before a real migration and refuses too-new/unsupported ledgers.
    Like every write path, it fails closed on a workspace-identity mismatch
    (consistent with state changes; use 'rebaseline' after a deliberate move).
    """
    feature_dir = get_feature_dir(root)
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
    feature_dir = get_feature_dir(root)
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
    data: records.LedgerLike = copy.deepcopy(on_disk)
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

    finalize(feature_dir, data, base_rev, base_violations)
    return f"Rebaselined to branch '{new_branch}' at {new_baseline[:7]}."
