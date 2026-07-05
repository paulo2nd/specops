"""specops consistency: SC-ID coverage + plan path-suffix validation (US4, FR-012)."""
from __future__ import annotations

from pathlib import Path

from specops import gitops, speckit
from specops.errors import SpecopsError


def run(root: Path) -> tuple[list[str], list[str]]:
    """
    Validate SC-ID coverage traceability and plan path-suffix declarations.

    Returns (warnings, violations). Violations map to exit 1.
    Raises SpecopsError on blocking preconditions.
    """
    feature_dir = speckit.resolve_feature_dir(root)
    if feature_dir is None:
        raise SpecopsError("Cannot resolve active feature directory.")

    spec_path = feature_dir / "spec.md"
    tasks_path = feature_dir / "tasks.md"
    plan_path = feature_dir / "plan.md"

    violations: list[str] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # SC-ID coverage check (R6, FR-012)
    # ------------------------------------------------------------------
    if spec_path.is_file() and tasks_path.is_file():
        spec_text = spec_path.read_text(encoding="utf-8")
        tasks_text = tasks_path.read_text(encoding="utf-8")

        spec_scs = set(speckit.extract_sc_ids(spec_text))
        spec_lines = spec_text.splitlines()

        def _sc_line(sc_id: str) -> int:
            for i, line in enumerate(spec_lines, start=1):
                if f"**{sc_id}**:" in line:
                    return i
            return 0

        covered: dict[str, list[str]] = {sc: [] for sc in spec_scs}
        unknown_refs: list[tuple[str, int, str]] = []

        for lineno, line in enumerate(tasks_text.splitlines(), start=1):
            tags = speckit.extract_coverage_tags(line)
            task_ids = speckit.extract_task_ids(line)
            task_id = task_ids[0] if task_ids else "?"
            for tag in tags:
                if tag in spec_scs:
                    covered[tag].append(task_id)
                else:
                    unknown_refs.append((str(tasks_path), lineno, tag))

        for sc, covering_tasks in covered.items():
            if not covering_tasks:
                line_num = _sc_line(sc)
                violations.append(
                    f"consistency: {spec_path.name}:{line_num} - SC '{sc}' has no covering task"
                )

        for _file, lineno, tag in unknown_refs:
            violations.append(
                f"consistency: {tasks_path.name}:{lineno}"
                f" - coverage tag '{tag}' references unknown SC"
            )

    # ------------------------------------------------------------------
    # Path-suffix validation (FR-012)
    # ------------------------------------------------------------------
    if plan_path.is_file():
        plan_text = plan_path.read_text(encoding="utf-8")
        repo = gitops.find_repo(root)

        for lineno, line in enumerate(plan_text.splitlines(), start=1):
            parsed = speckit.parse_plan_path_action(line)
            if not parsed:
                continue

            raw_path, action = parsed
            candidate = root / raw_path if not raw_path.startswith("/") else Path(raw_path)

            if action == "modify":
                if not candidate.is_file():
                    violations.append(
                        f"consistency: {plan_path.name}:{lineno} - "
                        f"(modify) path '{raw_path}' does not exist in worktree"
                    )
            elif action == "create":
                if not candidate.parent.is_dir():
                    violations.append(
                        f"consistency: {plan_path.name}:{lineno} - "
                        f"(create) parent of '{raw_path}' does not exist"
                    )
            elif action == "remove":
                in_worktree = candidate.exists()
                in_history = False
                if repo is not None:
                    try:
                        repo.git.ls_files("--error-unmatch", raw_path)
                        in_history = True
                    except Exception:
                        pass
                if not in_worktree and not in_history:
                    violations.append(
                        f"consistency: {plan_path.name}:{lineno} - "
                        f"(remove) path '{raw_path}' not in worktree or Git history"
                    )

    return warnings, violations
