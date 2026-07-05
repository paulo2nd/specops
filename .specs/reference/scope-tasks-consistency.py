#!/usr/bin/env python3
"""
scope-tasks-consistency: zero-token mechanical gate analogous to a lint,
executed by the architect before the scoping->implementing handoff.

Validates:
  1. Mandatory H2/H3 headers present in scope.md and tasks.md (methodology.md §10).
  2. Every "## Success Criteria" item in scope.md is covered by at least
     one task in tasks.md (heuristic based on significant-token overlap).
  3. Every "task-XX" reference in "**Dependencies**" resolves to an existing
     task block in tasks.md.
  4. Empirical existence of the paths in "**Files to Modify**" (methodology.md §17.4):
     - every bullet must carry a "(create)" or "(modify)" suffix;
     - "(modify)" suffix: Path.exists(repo_root/path) mandatory - FAIL when absent;
     - "(create)" suffix: Path(repo_root/path).parent.exists() mandatory - FAIL when absent;
     - mixed suffixes "(create OR extend)" / "(create OR modify)": accepts
       exists() OR parent.exists();
     - missing suffix: WARN (gradual transition for legacy artifacts).
     The textual anchor in scope.md remains an auxiliary WARN.

Output format:
  scope-tasks-consistency: <file>:<line> - <rule violated and corrective action>

Exit code 0 = ok. Exit code 1 = blocking (error). Warnings do not block.

Usage:
  python3 scripts/scope-tasks-consistency.py agents/features/<feature-name>/
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCOPE_REQUIRED_H2 = [
    "## Core Objective",
    "## Success Criteria",
    "## Required Skills & Gaps",
    "## Risks",
    "## Critical Constraints",
    "## Readiness Gate",
    "## AI Impact",
]
TASKS_REQUIRED_H2 = ["## Task Backlog"]
TASK_BULLET_KEYS = [
    "**Objective**",
    "**Acceptance Criteria**",
    "**Files to Modify**",
    "**Strategy**",
    "**Dependencies**",
]

# LEGACY HEURISTIC — reference only. This token-overlap coverage check (and its
# language-specific stopword list) is NOT carried into the SpecOps product: spec
# FR-012 replaces it with deterministic success-criterion ID traceability
# (tasks declare the SC-xxx IDs they cover), which is language-independent.
STOPWORDS = {
    "de", "da", "do", "das", "dos", "para", "com", "sem", "em", "na", "no", "nas", "nos",
    "e", "ou", "que", "se", "um", "uma", "uns", "umas", "o", "a", "os", "as", "ao", "aos",
    "the", "an", "of", "to", "in", "on", "with", "for", "and", "or", "by", "as", "is",
    "are", "be", "ser", "esta", "estao", "este", "esse", "essa", "isso", "isto",
    "por", "pelo", "pela", "pelos", "pelas", "sobre", "entre", "como", "quando",
    "apenas", "ja", "nao", "sim", "todo", "toda", "todos", "todas", "cada", "outro",
    "outra", "outros", "outras", "mesmo", "mesma", "mesmos", "mesmas",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")


def fail(violations: list[str], file: Path, line: int, message: str) -> None:
    violations.append(f"scope-tasks-consistency: {file}:{line} - {message}")


def warn(warnings: list[str], file: Path, line: int, message: str) -> None:
    warnings.append(f"scope-tasks-consistency: {file}:{line} - WARN {message}")


def tokens(text: str) -> set[str]:
    raw = TOKEN_RE.findall(text.lower())
    return {t for t in raw if len(t) >= 4 and t not in STOPWORDS}


def check_required_headers(
    file: Path, lines: list[str], required: list[str], violations: list[str]
) -> None:
    present = {line.strip(): idx + 1 for idx, line in enumerate(lines)}
    for header in required:
        if not any(line.strip() == header for line in lines):
            fail(violations, file, 1, f'mandatory header missing: "{header}" (methodology.md §10)')


def extract_section(lines: list[str], header: str) -> tuple[list[str], int]:
    """Returns the lines inside an H2 section and the starting line (1-based)."""
    start: int | None = None
    out: list[str] = []
    for idx, line in enumerate(lines):
        if line.strip() == header:
            start = idx + 1
            continue
        if start is not None:
            if line.startswith("## "):
                break
            out.append(line)
    return out, (start or 0)


def extract_success_criteria(scope_lines: list[str]) -> list[tuple[int, str]]:
    section, base = extract_section(scope_lines, "## Success Criteria")
    items: list[tuple[int, str]] = []
    for offset, line in enumerate(section):
        match = re.match(r"\s*-\s*\[\s*[xX ]?\s*\]\s*(.+)", line)
        if match:
            items.append((base + offset, match.group(1).strip()))
    return items


def extract_task_blocks(tasks_lines: list[str]) -> list[dict]:
    blocks: list[dict] = []
    current: dict | None = None
    current_field: str | None = None
    for idx, raw in enumerate(tasks_lines):
        stripped = raw.strip()
        header_match = re.match(r"###\s+(task-\d+):\s*(.*)", stripped)
        if header_match:
            if current is not None:
                blocks.append(current)
            current = {
                "id": header_match.group(1),
                "goal": header_match.group(2).strip(),
                "line": idx + 1,
                "fields": {key: [] for key in TASK_BULLET_KEYS},
                "raw_body": [],
            }
            current_field = None
            continue
        if current is None:
            continue
        current["raw_body"].append(raw)
        bullet_match = re.match(r"\s*-\s+(\*\*[^*]+\*\*):?\s*(.*)", raw)
        if bullet_match and bullet_match.group(1) in TASK_BULLET_KEYS:
            current_field = bullet_match.group(1)
            tail = bullet_match.group(2).strip()
            if tail:
                current["fields"][current_field].append((idx + 1, tail))
            continue
        sub_match = re.match(r"\s+-\s+(.+)", raw)
        if sub_match and current_field is not None:
            current["fields"][current_field].append((idx + 1, sub_match.group(1).strip()))
            continue
        if stripped.startswith("###") or stripped.startswith("## "):
            current_field = None
    if current is not None:
        blocks.append(current)
    return blocks


def check_success_criteria_coverage(
    scope_file: Path,
    scope_lines: list[str],
    blocks: list[dict],
    violations: list[str],
) -> None:
    task_corpora = []
    for block in blocks:
        text = " ".join([block["goal"], *block["raw_body"]])
        task_corpora.append((block["id"], tokens(text)))

    for line_no, criterion in extract_success_criteria(scope_lines):
        crit_tokens = tokens(criterion)
        if len(crit_tokens) < 2:
            continue
        if not task_corpora:
            fail(
                violations,
                scope_file,
                line_no,
                "Success Criteria without coverage: tasks.md has no task block",
            )
            continue
        covered = any(len(crit_tokens & task_tokens) >= 2 for _, task_tokens in task_corpora)
        if not covered:
            short = criterion[:80] + ("..." if len(criterion) > 80 else "")
            fail(
                violations,
                scope_file,
                line_no,
                f'Success Criteria "{short}" without coverage in tasks.md - add a task or remove the criterion',
            )


def check_dependencies(
    tasks_file: Path, blocks: list[dict], violations: list[str]
) -> None:
    valid_ids = {block["id"] for block in blocks}
    dep_re = re.compile(r"task-\d+")
    for block in blocks:
        for line_no, dep_line in block["fields"]["**Dependencies**"]:
            if not dep_line or dep_line.lower() in {"n/a", "`n/a`", "none"}:
                continue
            for ref in dep_re.findall(dep_line):
                if ref not in valid_ids:
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Dependencies references {ref}, nonexistent in the Task Backlog',
                    )


def scope_path_anchors(scope_text: str) -> set[str]:
    """Extracts tokens that look like path/module fragments cited in scope.md."""
    anchors: set[str] = set()
    path_re = re.compile(r"[A-Za-z0-9_./\-]+/[A-Za-z0-9_./\-]+")
    for match in path_re.findall(scope_text):
        for piece in re.split(r"[/.\\]", match):
            piece = piece.strip("`*_ ,;:()[]")
            if len(piece) >= 4 and piece.lower() not in STOPWORDS:
                anchors.add(piece.lower())
    code_re = re.compile(r"`([^`]+)`")
    for match in code_re.findall(scope_text):
        for piece in re.split(r"[/.\\\s]", match):
            piece = piece.strip("`*_ ,;:()[]")
            if len(piece) >= 4 and piece.lower() not in STOPWORDS:
                anchors.add(piece.lower())
    return anchors


PATH_IN_BACKTICKS_RE = re.compile(r"`([^`]+)`")
ACTION_SUFFIX_RE = re.compile(r"\(([^)]*?)\)")


def parse_files_to_modify_bullet(raw: str) -> tuple[str | None, str]:
    """
    Extracts (path, action) from a Files to Modify bullet.

    action returns: "modify" | "create" | "either" | "remove" | "unknown".
    path returns None when the bullet contains no identifiable path (e.g., "N/A").
    """
    text = raw.strip()
    if not text or text.lower() in {"n/a", "none", "`n/a`"}:
        return None, "unknown"

    backtick_match = PATH_IN_BACKTICKS_RE.search(text)
    if backtick_match:
        path = backtick_match.group(1).strip()
    else:
        # Fallback: takes everything before the first "(" as the candidate path.
        paren_idx = text.find("(")
        path = (text[:paren_idx] if paren_idx >= 0 else text).strip().strip("`")

    if not path or path.lower() in {"n/a", "none"}:
        return None, "unknown"

    has_create = False
    has_modify = False
    has_remove = False
    for match in ACTION_SUFFIX_RE.finditer(text):
        suffix = match.group(1).lower()
        if "create" in suffix:
            has_create = True
        if "modify" in suffix:
            has_modify = True
        if "remove" in suffix or "delete" in suffix:
            has_remove = True

    if has_create and has_modify:
        action = "either"
    elif has_create:
        action = "create"
    elif has_modify:
        action = "modify"
    elif has_remove:
        action = "remove"
    else:
        action = "unknown"

    return path, action


def file_existed_in_git(repo_root: Path, relative_path: str) -> bool:
    """Quickly checks whether the file was ever tracked in recent git history (HEAD or main)."""
    for ref in ["HEAD", "origin/main", "main"]:
        try:
            res = subprocess.run(
                ["git", "cat-file", "-e", f"{ref}:{relative_path}"],
                cwd=str(repo_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass
    return False


def check_files_to_modify(
    scope_file: Path,
    scope_text: str,
    tasks_file: Path,
    blocks: list[dict],
    repo_root: Path,
    violations: list[str],
    warnings: list[str],
) -> None:
    anchors = scope_path_anchors(scope_text)
    for block in blocks:
        for line_no, raw_path in block["fields"]["**Files to Modify**"]:
            path, action = parse_files_to_modify_bullet(raw_path)
            if path is None:
                continue

            # Empirical validation (methodology.md §17.4): real existence in the worktree.
            full = (repo_root / path).resolve()
            exists = full.exists()
            parent_exists = full.parent.exists()

            if action == "modify":
                if not exists:
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Files to Modify "{path}" marked (modify) but does not exist in the worktree - verify the path or switch the suffix to (create)',
                    )
            elif action == "create":
                if not parent_exists:
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Files to Modify "{path}" marked (create) but parent folder "{full.parent.relative_to(repo_root) if full.parent.is_relative_to(repo_root) else full.parent}" does not exist - confirm the destination or create the parent folder first',
                    )
            elif action == "either":
                if not exists and not parent_exists:
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Files to Modify "{path}" marked (create OR modify) but neither the file nor the parent folder exists - verify the path',
                    )
            elif action == "remove":
                if not exists:
                    if not file_existed_in_git(repo_root, path):
                        fail(
                            violations,
                            tasks_file,
                            line_no,
                            f'task {block["id"]} > Files to Modify "{path}" marked (remove) but it never existed in the Git history',
                        )
            else:  # unknown / no suffix
                warn(
                    warnings,
                    tasks_file,
                    line_no,
                    f'task {block["id"]} > Files to Modify "{path}" without a (create)/(modify)/(remove) suffix - add one to enable empirical verification (methodology.md §17.4)',
                )

            # Auxiliary textual-anchor heuristic against scope.md (kept as WARN).
            if anchors:
                pieces = [p.lower() for p in re.split(r"[/.\\\s]", path) if len(p) >= 4]
                if pieces and not any(p in anchors for p in pieces):
                    warn(
                        warnings,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Files to Modify "{path}" has no anchor in scope.md (module/path not mentioned)',
                    )


def check_unmapped_files_referenced(
    tasks_file: Path,
    blocks: list[dict],
    violations: list[str],
    warnings: list[str],
) -> None:
    # 1. Collect the paths declared in Files to Modify (across all feature tasks)
    declared_paths = set()
    for block in blocks:
        for _, raw_path in block["fields"]["**Files to Modify**"]:
            path, _ = parse_files_to_modify_bullet(raw_path)
            if path:
                declared_paths.add(path.replace("\\", "/").strip().lower())

    # Heuristic for explicit paths with an extension
    file_pattern = re.compile(r"([A-Za-z0-9_./\-]+\.(?:cs|csproj|json|yaml|md|sh))")

    # Heuristic for wiring symbols known in the project
    symbol_pattern = re.compile(
        r"([A-Za-z0-9_]+(?:DbContext|Worker|BackgroundService|ConsistencyChecker|ProjectionHandler|Endpoint|Command|Query))"
    )

    for block in blocks:
        # Analyzes Acceptance Criteria and Strategy
        lines_to_check = block["fields"]["**Acceptance Criteria**"] + block["fields"]["**Strategy**"]
        for line_no, content in lines_to_check:
            # Validate explicitly cited paths
            for file_ref in file_pattern.findall(content):
                file_ref_lower = file_ref.strip().lower()
                if not any(file_ref_lower in p or p in file_ref_lower for p in declared_paths):
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} mentions the file "{file_ref}" in its AC/Strategy, but it is not mapped in "Files to Modify" of any task.'
                    )

            # Validate wiring symbols (Warning only, to avoid false positives)
            for symbol_ref in symbol_pattern.findall(content):
                symbol_ref_lower = symbol_ref.strip().lower()
                if not any(symbol_ref_lower in p for p in declared_paths):
                    warn(
                        warnings,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} cites the symbol "{symbol_ref}" in its AC/Strategy, but no corresponding file is in "Files to Modify".'
                    )


def find_repo_root(start: Path) -> Path:
    """Walks up the hierarchy looking for .git to determine the repo root."""
    current = start.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd().resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "feature_dir",
        type=Path,
        help="Path to agents/features/<feature-name>/",
    )
    args = parser.parse_args()

    feature_dir: Path = args.feature_dir.resolve()
    scope_file = feature_dir / "scope.md"
    tasks_file = feature_dir / "tasks.md"
    repo_root = find_repo_root(feature_dir)

    if not scope_file.exists():
        print(
            f"scope-tasks-consistency: {scope_file} - scope.md missing; gate applicable only to feature_complete",
            file=sys.stderr,
        )
        return 1
    if not tasks_file.exists():
        print(
            f"scope-tasks-consistency: {tasks_file} - tasks.md missing; the architect must create it before the handoff",
            file=sys.stderr,
        )
        return 1

    scope_lines = scope_file.read_text(encoding="utf-8").splitlines()
    tasks_lines = tasks_file.read_text(encoding="utf-8").splitlines()
    scope_text = "\n".join(scope_lines)

    violations: list[str] = []
    warnings: list[str] = []

    check_required_headers(scope_file, scope_lines, SCOPE_REQUIRED_H2, violations)
    check_required_headers(tasks_file, tasks_lines, TASKS_REQUIRED_H2, violations)

    blocks = extract_task_blocks(tasks_lines)
    if not blocks:
        fail(
            violations,
            tasks_file,
            1,
            'no task block found (expected "### task-XX: [Goal]" under "## Task Backlog")',
        )

    check_success_criteria_coverage(scope_file, scope_lines, blocks, violations)
    check_dependencies(tasks_file, blocks, violations)
    check_files_to_modify(scope_file, scope_text, tasks_file, blocks, repo_root, violations, warnings)
    check_unmapped_files_referenced(tasks_file, blocks, violations, warnings)

    for line in warnings:
        print(line, file=sys.stderr)
    for line in violations:
        print(line, file=sys.stderr)

    if violations:
        print(
            f"scope-tasks-consistency: failed with {len(violations)} violation(s)",
            file=sys.stderr,
        )
        return 1

    print("scope-tasks-consistency: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
